"""self-mcp: スタックチャンが「自分のこと」を答えるための MCP サーバー（読み取り専用）。

xiaozhi-server のサーバー側 MCP クライアント（data/.mcp_server_settings.json）から streamable-http で呼ばれ、
会話中の LLM が必要な時だけツールを呼ぶ。材料はこのリポジトリの知識と記録:
- okf/（仕組み・決定・変更の記録）       → about_me、recent_changes
- brain の操作 API と data/brain/        → my_status、what_i_remember、why
- data/llm-proxy/gate/（宛先ゲートの記録） → why
家族の会話の本文は返さない（宛先ゲートで LLM に渡さなかったものを、ここから漏らさないため）。
追加ビルドを避けるため、mcp ライブラリ同梱の xiaozhi-server イメージで実行する。
根拠: okf/decisions/013-self-knowledge-mcp.md
"""

import glob
import json
import os
import re
import time
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

OKF = Path(os.environ.get("SELF_OKF_DIR", "/okf"))
BRAIN_DATA = Path(os.environ.get("SELF_BRAIN_DATA", "/data/brain"))
GATE_DIR = Path(os.environ.get("SELF_GATE_DIR", "/data/gate"))
BRAIN_URL = os.environ.get("SELF_BRAIN_URL", "http://brain:8011")
PORT = int(os.environ.get("SELF_MCP_PORT", "8020"))
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-6-luna")
MAX_CHARS = 1500  # 1 つのツール結果の上限（音声で答えるので長い資料は要らない）
PROFILE = "design/self-profile.md"  # 家族向けの自己説明

mcp = FastMCP(
    "stackchan-self",
    instructions="スタックチャン自身の仕組み・今の状態・判断の理由・最近の変化を調べるツール。"
                 "結果は資料なので、そのまま読み上げず、相手に合わせて短く言い換えること。",
    host="0.0.0.0",
    port=PORT,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"self-mcp:{PORT}", f"localhost:{PORT}", f"127.0.0.1:{PORT}"],
    ),
)


# ---------- okf ----------

def _concepts() -> list[dict]:
    """okf の概念ファイル（deprecated を除く）を読む。"""
    out = []
    for path in sorted(OKF.glob("*/*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = {}, text
        if text.startswith("---"):
            end = text.find("\n---", 3)
            for line in text[3:end].splitlines():
                m = re.match(r"^(title|description|status):\s*(.*)$", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip().strip('"')
            body = text[end + 4:]
        if fm.get("status") == "deprecated":
            continue  # 古い概念は根拠に使わない（okf のルール）
        body = re.sub(r"^\[\^[^\]]+\]:.*$", "", body, flags=re.M)   # 脚注の定義
        body = re.sub(r"\[\^[^\]]+\]", "", body)                     # 脚注の参照
        body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)         # リンクは文字だけ
        out.append({"path": str(path.relative_to(OKF)), "title": fm.get("title", path.stem),
                    "description": fm.get("description", ""), "status": fm.get("status", ""), "body": body.strip()})
    return out


def _bigrams(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text.lower())
    return {text[i:i + 2] for i in range(len(text) - 1)}


@mcp.tool()
def about_me(topic: str = "") -> str:
    """スタックチャン自身の仕組み（体・耳・声・頭脳・カメラ・記憶・考え方の 3 層・決めごとの理由など）を調べる。
    「どうやって動いてるの」「耳はどこ」「なんでクラウドを使うの」のように自分について聞かれた時に使う。
    topic は調べたいことを日本語で短く（空なら全体の概要）。"""
    concepts = _concepts()
    profile = next((c for c in concepts if c["path"] == PROFILE), None)
    # まず家族向けの自己説明（okf/design/self-profile.md）から、話題に合う節を返す
    parts = []
    if profile:
        sections = re.split(r"^# ", profile["body"], flags=re.M)[1:]
        q = _bigrams(topic)
        ranked = sorted(sections, key=lambda sec: -len(q & _bigrams(sec))) if topic.strip() else sections
        parts.append("## 自分の説明（家族向け）\n" + "\n".join("# " + sec.strip() for sec in ranked[:3 if topic.strip() else 99]))
    # 詳しい資料（開発者向け）も 1 つ添える。「詳しく」と頼まれた時の材料
    if topic.strip():
        q = _bigrams(topic)
        scored = sorted(((3 * len(q & _bigrams(c["title"] + c["description"])) + len(q & _bigrams(c["body"][:3000])), c)
                         for c in concepts if c["path"] != PROFILE), key=lambda x: -x[0])
        if scored and scored[0][0] > 0:
            c = scored[0][1]
            note = "（未確認の内容を含む）" if c["status"] == "draft" else ""
            parts.append(f"## 詳しい資料: {c['title']}{note}\n{c['description']}\n{c['body'][:500]}")
    return ("\n\n".join(parts) or "自分の説明の資料が見つからなかった。")[:MAX_CHARS]


@mcp.tool()
def recent_changes(days: int = 7) -> str:
    """スタックチャン自身に最近入った変更（できるようになったこと、直したこと）を調べる。
    「最近なにが変わったの」「新しくできるようになったことは」と聞かれた時に使う。"""
    text = (OKF / "log.md").read_text(encoding="utf-8")
    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - max(1, days) * 86400))
    out, current = [], None
    for line in text.splitlines():
        m = re.match(r"^## (\d{4}-\d{2}-\d{2})", line)
        if m:
            current = m.group(1)
            continue
        if current and current >= cutoff and line.startswith("* "):
            entry = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line[2:]).replace("**", "").replace("`", "")
            out.append(f"{current[5:]} {entry[:220]}")
    return ("\n".join(out) or f"この {days} 日間の変更の記録は無い。")[:MAX_CHARS]


# ---------- 今の状態・記憶 ----------

def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.load(r)


def _read_jsonl(pattern: str) -> list[dict]:
    rows = []
    for path in sorted(glob.glob(pattern)):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


@mcp.tool()
def my_status() -> str:
    """スタックチャン自身の今日の調子（お話しした回数、自分から話しかけた回数、聞き流した回数、使っている AI）を調べる。
    「調子どう」「今日は何回話した」と聞かれた時に使う。"""
    today = time.strftime("%Y%m%d")
    lines = [f"考えるのに使っている AI: {LLM_MODEL}"]
    try:
        sessions = _get_json(f"{BRAIN_URL}/sessions")
        lines.append(f"いまつながっている会話: {len(sessions)} 件")
    except Exception:  # noqa: BLE001
        lines.append("いまの接続状況は分からなかった")
    n_sessions = len(glob.glob(str(BRAIN_DATA / "sessions" / f"{today}-*.jsonl")))
    judgments = _read_jsonl(str(BRAIN_DATA / "judgments" / f"{today}.jsonl"))
    spoke = sum(1 for j in judgments if (j.get("action") or {}).get("mode"))
    gate = _read_jsonl(str(GATE_DIR / f"{today}.jsonl"))
    passed = sum(1 for g in gate if g.get("decision") == "pass")
    dropped = sum(1 for g in gate if g.get("decision") == "drop")
    jev_ok = sum(1 for g in gate + judgments if g.get("raw") or g.get("source") == "jev")
    lines += [f"今日の会話のセッション: {n_sessions} 回",
              f"今日自分から話しかけた回数: {spoke} 回（話すか迷って判断した回数 {len(judgments)} 回）",
              f"今日聞こえた声: 返事したもの {passed} 件、自分宛てではないと思って聞き流したもの {dropped} 件",
              f"直感の AI（Jev）が答えた回数: {jev_ok} 回"]
    return "\n".join(lines)


@mcp.tool()
def what_i_remember() -> str:
    """スタックチャンがこれまでの会話で覚えていること（記憶）を調べる。「ぼくのこと何覚えてる」と聞かれた時に使う。"""
    items = []
    for path in sorted((BRAIN_DATA / "memory").glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        updated = time.strftime("%m/%d %H:%M", time.localtime(rec.get("updated", 0)))
        items.append(f"（{updated} 更新）\n{rec.get('text', '')}")
    return ("\n\n".join(items) or "まだ何も覚えていない。")[:MAX_CHARS]


# ---------- 判断の理由 ----------

SITUATION_JA = {
    "pause_in_conversation": "会話がちょっと途切れたので、話の続きをしようと思った",
    "just_woken_no_talk": "起こされたのに誰も話さなかったので、声をかけようと思った",
    "person_arrived": "カメラで人が目の前に来たのが見えた",
    "person_left_or_busy": "相手が出かけた・忙しそうだと思った",
    "robot_ignored": "さっき自分から話しかけたのに返事がなかった",
}
ADDRESSEE_JA = {"robot": "自分（スタックチャン）宛て", "people": "家族同士の会話", "media": "テレビや動画の音",
                "self_talk": "ひとりごと", "unclear": "聞き取れず誰宛てか分からない"}


def _ago(t: float) -> str:
    s = int(time.time() - t)
    if s >= 86400:
        return time.strftime("%m/%d %H:%M", time.localtime(t))
    return f"{s // 3600} 時間前" if s >= 3600 else f"{s // 60} 分前" if s >= 60 else f"{s} 秒前"


@mcp.tool()
def why(kind: str = "spoke") -> str:
    """スタックチャン自身の直近の判断の理由を調べる。
    kind: "spoke"（なぜ自分から話しかけたか）/ "quiet"（なぜ自分から話しかけなかったか）/
    "ignored"（なぜ聞こえた声に返事をしなかったか）。
    「さっきなんで話しかけたの」「なんで返事しなかったの」と聞かれた時に使う。"""
    if kind == "ignored":
        gate = []
        for path in sorted(GATE_DIR.glob("*.jsonl"))[-3:]:
            gate += _read_jsonl(str(path))
        drops = [g for g in gate if g.get("decision") in ("drop", "backchannel")][-3:]
        if not drops:
            return "最近、返事をしなかった声の記録は無い。"
        out = []
        for g in reversed(drops):
            p = g.get("p_robot", 0)
            if g["decision"] == "backchannel":
                reason = "自分宛てだけど、相槌で十分だと思ったので相槌だけにした"
            elif p < 0.8:
                who = ADDRESSEE_JA.get(g.get("addressee"), "")
                guess = f"（いちばんありそうなのは「{who}」）" if g.get("addressee") != "robot" and who else ""
                reason = f"自分宛てだという自信が足りなかったので黙った{guess}"
            else:
                reason = "自分宛てだけど、返事は要らないと思ったので黙った"
            out.append(f"{_ago(g['t'])}: {reason}（自分宛ての確からしさ {p:.2f}。0.8 以上で自分宛てとみなす）")
        return "\n".join(out) + "\n（家族の会話の中身は記録から読み上げない）"
    judgments = []
    for path in sorted((BRAIN_DATA / "judgments").glob("*.jsonl"))[-3:]:
        judgments += _read_jsonl(str(path))
    if kind == "spoke":
        picks = [j for j in judgments if (j.get("action") or {}).get("mode")][-1:]
    else:
        picks = [j for j in judgments if not (j.get("action") or {}).get("mode")][-1:]
    if not picks:
        return "最近、その判断の記録は無い。"
    j = picks[0]
    a = j.get("answers", {})
    sit = a.get("situation", "")
    person = (j.get("state") or {}).get("person") or {}
    lines = [f"{_ago(j['t'])} の判断: {SITUATION_JA.get(sit, sit)}",
             f"話しかけたい気持ちの強さ {a.get('should_speak', 0):.2f}（この時は {j.get('threshold', 0):.2f} 以上なら話す）"]
    if person:
        lines.append(f"カメラに映っていた顔: {person.get('faces_in_view')} 人")
    if (j.get("action") or {}).get("dormant_until_user_speaks"):
        lines.append("相手が話しかけてくれるまで、自分からは話さないことにした")
    if j.get("state", {}).get("proactive_utterances_this_session"):
        lines.append(f"この会話で自分から話しかけた回数: {j['state']['proactive_utterances_this_session']} 回（多いほど控えめにする）")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
