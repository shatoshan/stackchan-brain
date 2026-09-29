"""会話の記憶: セッションが閉じたら会話を LLM で要約し、端末ごとの記憶を更新して保存する。

- 記憶は日本語の箇条書き（人・好み・予定・出来事、日付付き）。前の記憶と今回の会話から書き直す（追記ではなく更新）
- 保存先は data/brain/memory/<MAC>.json（ローカルのみ）
- xiaozhi-server は会話の開始時に context_providers で GET /context を呼び、システムプロンプトの {{ dynamic_context }} に入れる
- brain の判定（状態ブロブの memory）にも同じものを入れる
xiaozhi-server 内蔵の mem_local_short を使わない理由: 要約の指示も保存形式も中国語で、そのままシステムプロンプトに入る。
根拠: okf/design/conversation-memory.md（GitHub #5）
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web

from relay import Session

log = logging.getLogger("brain.memory")

GATEWAY = os.environ.get("BRAIN_GATEWAY_URL", "http://llm-proxy:8080/v1")
MODEL = os.environ.get("BRAIN_MEMORY_MODEL", os.environ.get("LLM_MODEL", "openai/gpt-6-luna"))
# 要約するのは、ユーザー発話がこの数以上あったセッションだけ
MIN_USER_UTTERANCES = int(os.environ.get("BRAIN_MEMORY_MIN_UTTERANCES", "2"))
MAX_CHARS = int(os.environ.get("BRAIN_MEMORY_MAX_CHARS", "800"))
# brain が差し込んだ指示（会話ログには suppressed として残るが、念のため除く）
INSTRUCTION_PREFIX = "（ロボットから話しかける場面です"
WEEKDAYS = "月火水木金土日"

PROMPT = """あなたは卓上の小さなおしゃべりロボット「スタックチャン」の記憶係です。
「これまでの記憶」と「今回の会話」から、次に話す時に役立つ記憶を日本語の箇条書きで書き直してください。

- 残すもの: 相手（家族）の名前や呼び方、好き嫌い、予定、最近の出来事、繰り返し話題になること、ロボットへのお願い（例: 話しかけすぎないで）
- 日付が分かるものは「(9/27)」のように付ける。古くて重要でない項目は消してよい。全体で {max_chars} 字以内
- 会話は音声認識の結果で、聞き間違いや途中で切れた文、ロボットに向けていない家族同士の会話・テレビの音が混ざる。意味が確かでないものは記憶しない
- ロボット自身が言ったことは、相手が反応したものだけ残す
- 箇条書きだけを出力する（見出しや説明は不要）。記憶することが何もなければ、これまでの記憶をそのまま出す。これまでの記憶も無ければ「なし」とだけ出力する"""


def transcript_from_log(path: Path) -> list[str]:
    """セッションログからユーザー発話とロボットの発話を順に取り出す（ツール表示・差し込んだ指示は除く）。"""
    lines, robot = [], []
    for raw in path.read_text(encoding="utf-8").splitlines():
        e = json.loads(raw)
        m = e.get("msg") or {}
        if e.get("dir") != "down":
            continue
        if m.get("type") == "tts" and m.get("state") == "sentence_start" and m.get("text"):
            robot.append(m["text"])
        elif m.get("type") == "tts" and m.get("state") == "stop" and robot:
            lines.append(f"{time.strftime('%H:%M', time.localtime(e['t']))} ロボット: {'、'.join(robot)}")
            robot = []
        elif m.get("type") == "stt":
            text = str(m.get("text", ""))
            if text and not text.startswith("% ") and not text.startswith(INSTRUCTION_PREFIX):
                lines.append(f"{time.strftime('%H:%M', time.localtime(e['t']))} 人: {text}")
    return lines


class Memory:
    def __init__(self, directory: Path):
        self.dir = directory
        self.client: ClientSession | None = None
        self.locks: dict[str, asyncio.Lock] = {}

    async def start(self, app) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.client = ClientSession(timeout=ClientTimeout(total=60))

    async def stop(self, app) -> None:
        if self.client:
            await self.client.close()

    def _path(self, device_id: str) -> Path:
        return self.dir / f"{device_id.replace(':', '')}.json"

    def get(self, device_id: str) -> str:
        path = self._path(device_id)
        if not path.exists():
            return ""
        return json.loads(path.read_text(encoding="utf-8")).get("text", "")

    def on_session_closed(self, session: Session) -> None:
        asyncio.create_task(self._update(session))

    async def _update(self, session: Session) -> None:
        try:
            lines = transcript_from_log(session.log_path)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("[%s] memory: cannot read session log: %s", session.device_id, e)
            return
        if sum(" 人: " in line for line in lines) < MIN_USER_UTTERANCES:
            return
        lock = self.locks.setdefault(session.device_id, asyncio.Lock())
        async with lock:
            old = self.get(session.device_id)
            started = time.time()
            try:
                text = await self._summarize(old, lines, session.started_at)
            except Exception as e:  # noqa: BLE001 要約に失敗しても記憶は前のまま
                log.warning("[%s] memory: summarize failed: %s", session.device_id, str(e)[:200])
                return
            if not text:
                log.info("[%s] memory: nothing to remember from %d lines", session.device_id, len(lines))
                return
            record = {"device_id": session.device_id, "updated": round(time.time(), 3), "text": text,
                      "from_session": session.id}
            self._path(session.device_id).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
            log.info("[%s] memory updated from %d lines (%.1fs, %d chars)", session.device_id, len(lines),
                     time.time() - started, len(text))

    async def _summarize(self, old: str, lines: list[str], started_at: float) -> str:
        day = time.strftime("%Y-%m-%d", time.localtime(started_at)) + f" ({WEEKDAYS[time.localtime(started_at).tm_wday]})"
        user = (f"# これまでの記憶\n{old or '（まだ無い）'}\n\n# 今回の会話（{day}）\n" + "\n".join(lines[-200:]))
        body = {"model": MODEL, "max_tokens": 700,
                "messages": [{"role": "system", "content": PROMPT.format(max_chars=MAX_CHARS)},
                             {"role": "user", "content": user}]}
        # brain 自身の依頼なので宛先ゲートにかけない
        async with self.client.post(f"{GATEWAY}/chat/completions", json=body, headers={"X-StackChan-Source": "brain"}) as r:
            if r.status != 200:
                raise RuntimeError(f"llm {r.status}: {(await r.text())[:200]}")
            data = await r.json()
        # 箇条書きの行だけを残す（見出しや崩れた記号が混ざることがあった）
        items = [line.strip() for line in (data["choices"][0]["message"].get("content") or "").splitlines()]
        items = ["- " + line.lstrip("-・* ").strip() for line in items if line[:1] in ("-", "・", "*") and line.lstrip("-・* ").strip()]
        return "\n".join(items)[: MAX_CHARS * 2]  # 「なし」なら空

    async def context(self, request: web.Request) -> web.Response:
        """xiaozhi-server の context_providers 用。{"code": 0, "data": {...}} の各項目がシステムプロンプトに入る。"""
        device_id = request.headers.get("device-id", "")
        text = self.get(device_id) if device_id else ""
        data = {"これまでの会話で覚えていること": "\n" + text} if text else {}
        return web.json_response({"code": 0, "data": data})
