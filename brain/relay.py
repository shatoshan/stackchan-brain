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

    async def _pump(self, session: Session, source, sink, direction: str) -> str:
        """source から sink へ流し続け、source 側が閉じたら direction を返す。"""
        async for msg in source:
            session.last_activity = time.time()
            if msg.type == WSMsgType.TEXT:
                await sink.send_str(msg.data)
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    self._record(session, direction, msg.data)
                    continue
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
