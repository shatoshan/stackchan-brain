"""端末 ⇔ xiaozhi-server の WebSocket 透過中継。

端末は OTA で受け取った URL（xiaozhi-server の server.websocket）に接続してくるので、
それを brain に向けると全セッションがここを通る。メッセージは改変せずに双方向へ流し、
JSON メッセージだけをセッションログに記録する。
根拠: okf/decisions/007-proactive-speech-path.md、okf/protocol/xiaozhi-protocol.md
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import ClientSession, WSMsgType, web

log = logging.getLogger("brain.relay")

# 上流へ引き継ぐヘッダ（xiaozhi-server が読むもの）
FORWARD_HEADERS = ("authorization", "protocol-version", "device-id", "client-id")
# ログで省略する大きなペイロード
MAX_LOGGED_CHARS = 2000
# xiaozhi-server が LLM を通さずそのまま読み上げる接頭辞（listenMessageHandler.py）
VERBATIM_PREFIX = "[device_call]"
# 差し込みの条件（秒）
MIN_GAP_AFTER_ROBOT = float(os.environ.get("BRAIN_MIN_GAP_AFTER_ROBOT", "1.5"))
MIN_GAP_AFTER_USER = float(os.environ.get("BRAIN_MIN_GAP_AFTER_USER", "3.0"))
# llm モードで送ってはいけない語（wakeup_words / exit_commands と完全一致すると誤動作する）
RESERVED_WORDS = {w for w in os.environ.get(
    "BRAIN_RESERVED_WORDS", "HiStackChan,スタックチャン,ハイスタックチャン,終了,おしまい").split(",") if w}
PUNCT = set("！＂＃＄％＆＇（）＊＋，－。／：；＜＝＞？＠［＼］＾＿｀｛｜｝～" + "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~" + " 　")


def normalize(text: str) -> str:
    """xiaozhi-server の remove_punctuation_and_length と同じ正規化。"""
    return "".join(c for c in text if c not in PUNCT)


class InjectError(Exception):
    """差し込めない（状態が合わない等）。"""


@dataclass
class Session:
    id: str
    device_id: str
    started_at: float
    device_ws: web.WebSocketResponse
    upstream_ws: object
    log_path: Path
    session_id: str | None = None  # xiaozhi-server が hello で払い出す ID
    last_activity: float = field(default_factory=time.time)
    # 端末の状態（メッセージから推定）: connecting / listening / speaking / idle
    state: str = "connecting"
    last_user_at: float = 0.0      # 最後にユーザー発話（stt）が届いた時刻
    last_robot_end_at: float = 0.0  # 最後に tts stop が届いた時刻
    injections: int = 0
    # 差し込んだ文の stt は端末に流さない（画面に「ユーザー発話」として出るのを防ぐ）
    suppress_stt: set = field(default_factory=set)

    def info(self) -> dict:
        now = time.time()
        return {
            "id": self.id, "device_id": self.device_id, "session_id": self.session_id,
            "state": self.state, "age_s": round(now - self.started_at),
            "since_user_s": round(now - self.last_user_at) if self.last_user_at else None,
            "since_robot_s": round(now - self.last_robot_end_at) if self.last_robot_end_at else None,
            "injections": self.injections,
        }


class Relay:
    def __init__(self, upstream_url: str, log_dir: Path):
        self.upstream_url = upstream_url
        self.log_dir = log_dir
        self.sessions: dict[str, Session] = {}
        self.client: ClientSession | None = None

    async def start(self, app: web.Application) -> None:
        self.client = ClientSession()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def stop(self, app: web.Application) -> None:
        if self.client:
            await self.client.close()

    def _record(self, session: Session, direction: str, data: dict | str) -> None:
        entry = {"t": round(time.time(), 3), "dir": direction}
        if isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False)
            entry["msg"] = data if len(text) <= MAX_LOGGED_CHARS else {"type": data.get("type"), "truncated": len(text)}
        else:
            entry["raw"] = data[:MAX_LOGGED_CHARS]
        with session.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _summarize(self, session: Session, direction: str, msg: dict) -> None:
        """会話の要点だけを標準ログに出す。"""
        mtype = msg.get("type")
        if mtype == "stt":
            log.info("[%s] user: %s", session.device_id, msg.get("text"))
        elif mtype == "tts" and msg.get("state") == "sentence_start":
            log.info("[%s] robot: %s", session.device_id, msg.get("text"))
        elif mtype == "mcp":
            payload = msg.get("payload") or {}
            if payload.get("method") == "tools/call":
                params = payload.get("params") or {}
                log.info("[%s] tool call: %s %s", session.device_id, params.get("name"),
                         json.dumps(params.get("arguments"), ensure_ascii=False))
        elif mtype in ("hello", "listen", "abort"):
            log.info("[%s] %s %s", session.device_id, direction, json.dumps(msg, ensure_ascii=False))

    @staticmethod
    def _track_state(session: Session, direction: str, data: dict) -> None:
        mtype, state = data.get("type"), data.get("state")
        now = time.time()
        if direction == "up" and mtype == "listen":
            if state == "start":
                session.state = "listening"
            elif state == "stop":
                session.state = "idle"
        elif direction == "down" and mtype == "tts":
            if state == "start":
                session.state = "speaking"
            elif state == "stop":
                session.state = "listening"
                session.last_robot_end_at = now
        elif direction == "down" and mtype == "stt" and not str(data.get("text", "")).startswith("% "):
            session.last_user_at = now

    async def inject(self, text: str, mode: str = "verbatim", device_id: str | None = None) -> dict:
        """聞き取り中のセッションに発話を差し込む。

        verbatim: [device_call] 接頭辞で LLM を通さずそのまま読み上げる
        llm:      text をユーザー発話として渡し、LLM に返答を生成させる（会話履歴に user として残る）
        """
        text = text.strip()
        if not text:
            raise InjectError("text is empty")
        if mode not in ("verbatim", "llm"):
            raise InjectError(f"unknown mode: {mode}")
        if mode == "llm" and normalize(text) in RESERVED_WORDS:
            raise InjectError("text matches a wake word / exit command")
        candidates = [s for s in self.sessions.values() if device_id in (None, s.device_id)]
        if not candidates:
            raise InjectError("no active session")
        session = max(candidates, key=lambda s: s.last_activity)
        now = time.time()
        if session.state != "listening" or not session.session_id:
            raise InjectError(f"device is {session.state}")
        if session.last_robot_end_at and now - session.last_robot_end_at < MIN_GAP_AFTER_ROBOT:
            raise InjectError("robot just finished speaking")
        if session.last_user_at and now - session.last_user_at < MIN_GAP_AFTER_USER:
            raise InjectError("user just spoke")

        payload_text = VERBATIM_PREFIX + text if mode == "verbatim" else text
        # サーバーが返す stt（verbatim は接頭辞を除いた文、llm はそのまま）を端末に流さない
        session.suppress_stt.add(normalize(text))
        msg = {"session_id": session.session_id, "type": "listen", "state": "detect", "text": payload_text}
        await session.upstream_ws.send_str(json.dumps(msg, ensure_ascii=False))
        session.injections += 1
        self._record(session, "inject", {"mode": mode, "text": text})
        log.info("[%s] inject(%s): %s", session.device_id, mode, text)
        return session.info()

    async def _pump(self, session: Session, source, sink, direction: str) -> str:
        """source から sink へ流し続け、source 側が閉じたら direction を返す。"""
        async for msg in source:
            session.last_activity = time.time()
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    await sink.send_str(msg.data)
                    self._record(session, direction, msg.data)
                    continue
                # サーバーは stt の句読点を一部落とすので正規化して比べる
                if direction == "down" and data.get("type") == "stt" and normalize(str(data.get("text", ""))) in session.suppress_stt:
                    session.suppress_stt.discard(normalize(str(data["text"])))
                    self._record(session, "down-suppressed", data)
                    continue
                await sink.send_str(msg.data)
                self._track_state(session, direction, data)
                if direction == "down" and data.get("type") == "hello" and data.get("session_id"):
                    session.session_id = data["session_id"]
                self._record(session, direction, data)
                self._summarize(session, direction, data)
            elif msg.type == WSMsgType.BINARY:
                await sink.send_bytes(msg.data)
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR):
                break
        return direction

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARD_HEADERS}
        device_id = request.headers.get("Device-Id") or request.query.get("device-id") or "unknown"

        device_ws = web.WebSocketResponse(autoping=True, max_msg_size=0)
        await device_ws.prepare(request)

        upstream_url = self.upstream_url + (f"?{request.query_string}" if request.query_string else "")
        try:
            upstream_ws = await self.client.ws_connect(upstream_url, headers=headers, max_msg_size=0, autoping=True)
        except Exception as e:  # noqa: BLE001 上流に繋がらなければ端末側も閉じる
            log.error("[%s] upstream connect failed: %s", device_id, e)
            await device_ws.close(code=1011, message=b"upstream unavailable")
            return device_ws

        sid = uuid.uuid4().hex[:12]
        started = time.time()
        log_path = self.log_dir / f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(started))}-{device_id.replace(':', '')}-{sid}.jsonl"
        session = Session(sid, device_id, started, device_ws, upstream_ws, log_path)
        self.sessions[sid] = session
        log.info("[%s] session %s open (log %s)", device_id, sid, log_path.name)

        up = asyncio.create_task(self._pump(session, device_ws, upstream_ws, "up"))
        down = asyncio.create_task(self._pump(session, upstream_ws, device_ws, "down"))
        try:
            done, pending = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            closed_by = "?"
            for task in done:
                if task.exception():
                    log.warning("[%s] pump error: %s", device_id, task.exception())
                else:
                    # up の pump が終わった = 端末側が閉じた
                    closed_by = "device" if task.result() == "up" else "server"
        finally:
            # 片側が閉じたらもう片側も閉じ、閉じ理由を伝える
            code = upstream_ws.close_code or device_ws.close_code or 1000
            await upstream_ws.close()
            await device_ws.close(code=code)
            self.sessions.pop(sid, None)
            self._record(session, "meta", {"type": "closed", "by": closed_by, "code": code})
            log.info("[%s] session %s closed by %s (code %s, %.0fs)", device_id, sid, closed_by, code, time.time() - started)
        return device_ws


def create_control_app(relay: Relay) -> web.Application:
    """ホスト（127.0.0.1）からだけ使う操作 API。"""

    async def sessions(_: web.Request) -> web.Response:
        return web.json_response([s.info() for s in relay.sessions.values()])

    async def say(request: web.Request) -> web.Response:
        body = await request.json()
        try:
            info = await relay.inject(body.get("text", ""), body.get("mode", "verbatim"), body.get("device_id"))
        except InjectError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=409)
        return web.json_response({"ok": True, "session": info})

    app = web.Application()
    app.router.add_get("/sessions", sessions)
    app.router.add_post("/say", say)
    return app


def create_app() -> web.Application:
    relay = Relay(
        upstream_url=os.environ.get("BRAIN_UPSTREAM_WS", "ws://xiaozhi-server:8000/xiaozhi/v1/"),
        log_dir=Path(os.environ.get("BRAIN_SESSION_LOG_DIR", "/data/sessions")),
    )
    app = web.Application()
    app["relay"] = relay
    app.on_startup.append(relay.start)
    app.on_cleanup.append(relay.stop)
    app.router.add_get("/xiaozhi/v1/", relay.handle)
    app.router.add_get("/xiaozhi/v1", relay.handle)
    app.router.add_get("/healthz", lambda _: web.Response(text="ok"))
    return app
