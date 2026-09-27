"""宛先ゲート: xiaozhi-server がユーザー発話で LLM を呼ぶ前に、Jev で「誰に向けた発話か」「どんな返事が要るか」を分類する。

- ロボット宛てで返事が要る / 端末操作・外部ツールが要る → そのまま LLM（GPT-6 Luna）へ
- 相槌で足りる → LLM を呼ばず、短い相槌を返す
- 人同士の会話・テレビ・独り言 → LLM を呼ばず、空の応答を返す（xiaozhi-server は何も喋らない）
- Jev が使えない時は LLM へ渡す（fail-open）

Jev に流すのは許容、それ以外のモデルへの流出とコストを抑えるのが目的（GitHub #2）。
根拠: okf/design/addressee-gate.md
"""

import json
import logging
import os
import random
import time
from pathlib import Path

from aiohttp import ClientSession

import jev

log = logging.getLogger("llm-proxy.gate")

ENABLED = os.environ.get("LLM_GATE_ENABLED", "1") == "1"
BRAIN_URL = os.environ.get("BRAIN_CONTROL_URL", "http://brain:8011")
MIN_CONFIDENCE = float(os.environ.get("LLM_GATE_MIN_CONFIDENCE", "0.6"))
RECORD_DIR = Path(os.environ.get("LLM_GATE_RECORD_DIR", "/data/gate"))
BACKCHANNELS = ["うんうん。", "そっか。", "なるほどね。", "へえ。", "うん。"]
# brain が llm モードで差し込む指示（ロボットからの話しかけ）はゲートしない
BRAIN_INSTRUCTION_PREFIX = "（ロボットから話しかける場面です"

ADDRESSEE = {
    "robot": "Talking to the robot: answering it, asking it something, calling it, or giving it a command",
    "people": "Talking to another person in the room (e.g. family conversation), not to the robot",
    "media": "Sound from a TV, video, radio or music (broadcast phrases, narration, lyrics)",
    "self_talk": "Muttering to oneself or an exclamation that does not expect anyone to answer",
    "unclear": "Too short or garbled to tell who it is for",
}
RESPONSE = {
    "reply": "The robot should answer in words",
    "backchannel": "A short acknowledgement such as 'うんうん' or 'そっか' is enough",
    "none": "No response is needed at all",
    "action": "Needs an action or tool: moving the head, LED, reminders, volume, taking a photo, looking something up",
}
QUESTIONS = {
    "addressee": {"type": "choice", "criteria": ADDRESSEE,
                  "instructions": "`utterance` was just picked up by a small companion desk robot's microphone and transcribed "
                                  "(it may contain recognition errors). Who is it addressed to? Use `recent_conversation` "
                                  "(oldest first) and whether the robot just spoke to the person."},
    "response": {"type": "choice", "criteria": RESPONSE,
                 "instructions": "If the robot responds to `utterance`, what kind of response fits?"},
}


def user_text(message: dict) -> str | None:
    """xiaozhi-server の user メッセージから発話テキストを取り出す（ASR 由来は JSON 文字列）。"""
    content = message.get("content")
    if not isinstance(content, str):
        return None
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "content" in data:
            return str(data["content"])
    except json.JSONDecodeError:
        pass
    return content


def recent_conversation(messages: list, limit: int = 6) -> list[str]:
    lines = []
    for m in messages[:-1]:
        if m.get("role") == "user":
            t = user_text(m)
            if t and not t.startswith(BRAIN_INSTRUCTION_PREFIX):
                lines.append(f"person: {t}")
        elif m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"]:
            lines.append(f"robot: {m['content']}")
    return lines[-limit:]


async def brain_context(session: ClientSession) -> dict:
    try:
        async with session.get(f"{BRAIN_URL}/sessions", timeout=2) as r:
            sessions = await r.json()
    except Exception:  # noqa: BLE001 brain が落ちていてもゲートは動く
        return {}
    if not sessions:
        return {}
    # 最後に誰かが話した（またはつながった）セッション
    s = min(sessions, key=lambda x: min(v for v in (x.get("since_user_s"), x.get("since_robot_s"), x.get("age_s")) if v is not None))
    return {k: s.get(k) for k in ("since_injection_s", "since_robot_s", "faces_in_view", "face_checked_s_ago")}


def should_gate(payload: dict) -> str | None:
    """ゲート対象ならユーザー発話を返す。"""
    if not ENABLED:
        return None
    messages = payload.get("messages") or []
    if not messages or messages[-1].get("role") != "user":
        return None  # ツール結果の続きなど
    text = user_text(messages[-1])
    if not text or text.startswith(BRAIN_INSTRUCTION_PREFIX):
        return None
    return text


def _record(entry: dict) -> None:
    try:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        with (RECORD_DIR / time.strftime("%Y%m%d.jsonl")).open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("gate record failed: %s", e)


async def decide(session: ClientSession, payload: dict, text: str) -> tuple[str, str | None]:
    """("pass" | "backchannel" | "drop", 返す文) を決める。"""
    ctx = await brain_context(session)
    state = {
        "utterance": text,
        "recent_conversation": recent_conversation(payload.get("messages") or []),
        "robot_started_talking_on_its_own_seconds_ago": ctx.get("since_injection_s"),
        "robot_last_spoke_seconds_ago": ctx.get("since_robot_s"),
        "camera_faces_in_view": ctx.get("faces_in_view"),
    }
    entry = await classify(session, state)
    _record(entry)
    log.info("gate %s addressee=%s(%.2f) response=%s(%.2f) %.2fs %r", entry["decision"], entry.get("addressee"),
             entry.get("addressee_p") or 0, entry.get("response"), entry.get("response_p") or 0, entry["latency_s"], text[:40])
    return entry["decision"], entry.get("reply")


async def classify(session: ClientSession, state: dict) -> dict:
    """状態ブロブを Jev で分類して判定を返す（記録はしない。evals からも使う）。"""
    started = time.time()
    entry = {"t": round(started, 3), "state": state}
    try:
        res = await jev.evaluate(session, state, QUESTIONS)
    except Exception as e:  # noqa: BLE001 Jev が使えなければ LLM へ渡す
        entry.update(decision="pass", reason=f"jev unavailable: {str(e)[:120]}", jev_error=getattr(e, "status", None),
                     latency_s=round(time.time() - started, 3))
        return entry
    a = res["answers"]
    who, who_p = a["addressee"]["choice"], a["addressee"]["probabilities"].get(a["addressee"]["choice"], 0)
    kind, kind_p = a["response"]["choice"], a["response"]["probabilities"].get(a["response"]["choice"], 0)
    decision, reply = "pass", None
    if who in ("people", "media", "self_talk") and who_p >= MIN_CONFIDENCE and kind != "action":
        decision = "drop"
    elif who == "robot" and kind in ("backchannel", "none") and kind_p >= MIN_CONFIDENCE:
        decision, reply = "backchannel", random.choice(BACKCHANNELS)
    entry.update(decision=decision, reply=reply, addressee=who, addressee_p=round(who_p, 3), response=kind,
                 response_p=round(kind_p, 3), backend=res["backend"], latency_s=round(time.time() - started, 3), raw=a)
    return entry


def sse_reply(model: str, text: str | None) -> bytes:
    """OpenAI Chat Completions のストリーム形式で text（None なら空）を返す。"""
    def chunk(delta, finish=None):
        return ("data: " + json.dumps({"id": "gate", "object": "chat.completion.chunk", "created": int(time.time()),
                                       "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]},
                                      ensure_ascii=False) + "\n\n").encode()
    body = chunk({"role": "assistant"})
    if text:
        body += chunk({"content": text})
    return body + chunk({}, "stop") + b"data: [DONE]\n\n"
