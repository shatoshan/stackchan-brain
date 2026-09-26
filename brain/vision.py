"""端末カメラの写真を受け取る HTTP 受け口（xiaozhi の Explain 互換）。

端末の take_photo は、MCP initialize で渡された vision.url に multipart（question, file）を POST し、
レスポンス本文をツール結果にする。brain の中継がその URL をここに書き換える。
- question が PRESENCE_QUESTION（brain が在席確認で撮らせたもの）: LAN 内で顔検出して結果を返す
- それ以外（LLM が撮らせたもの）: 元の xiaozhi-server の vision URL へそのまま転送する
根拠: okf/design/camera-presence.md
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path

import cv2
import numpy as np
from aiohttp import ClientSession, FormData, web

from relay import Relay

log = logging.getLogger("brain.vision")

PRESENCE_QUESTION = "__stackchan_brain_presence__"
MODEL_PATH = os.environ.get("BRAIN_FACE_MODEL", "/app/face_detection_yunet_2023mar.onnx")
SCORE_THRESHOLD = float(os.environ.get("BRAIN_FACE_SCORE", "0.7"))
FORWARD_HEADERS = ("authorization", "device-id", "client-id")


class FaceDetector:
    def __init__(self, model_path: str):
        self.detector = cv2.FaceDetectorYN.create(model_path, "", (320, 240), SCORE_THRESHOLD, 0.3, 5)

    def detect(self, jpeg: bytes) -> tuple[dict, np.ndarray | None]:
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return {"error": "decode failed"}, None
        h, w = img.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)
        faces = [] if faces is None else faces
        result = {"width": w, "height": h, "faces": len(faces)}
        if len(faces):
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])[:4]
            result.update({
                "largest_face_width_ratio": round(float(fw) / w, 3),
                "center_x": round(float(x + fw / 2) / w, 3),
                "center_y": round(float(y + fh / 2) / h, 3),
                "score": round(float(max(f[-1] for f in faces)), 3),
            })
            for f in faces:
                fx, fy, fw2, fh2 = (int(v) for v in f[:4])
                cv2.rectangle(img, (fx, fy), (fx + fw2, fy + fh2), (0, 255, 0), 2)
        return result, img


class VisionEndpoint:
    def __init__(self, relay: Relay, debug_dir: Path):
        self.relay = relay
        self.debug_dir = debug_dir
        self.detector: FaceDetector | None = None
        self.client: ClientSession | None = None

    async def start(self, app) -> None:
        self.detector = FaceDetector(MODEL_PATH)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.client = ClientSession()

    async def stop(self, app) -> None:
        if self.client:
            await self.client.close()

    async def handle(self, request: web.Request) -> web.Response:
        started = time.time()
        device_id = request.headers.get("Device-Id", "unknown")
        reader = await request.multipart()
        question, jpeg = "", b""
        async for part in reader:
            if part.name == "question":
                question = await part.text()
            elif part.name == "file":
                jpeg = await part.read()
        received = time.time()

        if question == PRESENCE_QUESTION:
            result, annotated = await asyncio.to_thread(self.detector.detect, jpeg)
            result["jpeg_bytes"] = len(jpeg)
            result["upload_s"] = round(received - started, 3)
            result["detect_s"] = round(time.time() - received, 3)
            self.relay.update_presence(device_id, result)
            if annotated is not None:
                cv2.imwrite(str(self.debug_dir / "last.jpg"), annotated)
            log.info("[%s] presence %s", device_id, json.dumps(result))
            return web.json_response({"success": True, "result": json.dumps(result)})

        # LLM が撮らせた写真は元の vision URL（xiaozhi-server の VLLM）へ転送する
        upstream = self.relay.vision_upstream.get(device_id)
        if not upstream:
            return web.json_response({"success": False, "message": "no upstream vision url"}, status=502)
        form = FormData()
        form.add_field("question", question)
        form.add_field("file", jpeg, filename="camera.jpg", content_type="image/jpeg")
        headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARD_HEADERS}
        async with self.client.post(upstream, data=form, headers=headers) as r:
            body = await r.read()
            log.info("[%s] forwarded photo (%d bytes, question=%r) -> %d", device_id, len(jpeg), question[:40], r.status)
            return web.Response(body=body, status=r.status, content_type=r.content_type)


def create_vision_app(relay: Relay, debug_dir: Path) -> web.Application:
    endpoint = VisionEndpoint(relay, debug_dir)
    app = web.Application(client_max_size=4 * 1024 * 1024)
    app.on_startup.append(endpoint.start)
    app.on_cleanup.append(endpoint.stop)
    app.router.add_post("/vision/explain", endpoint.handle)
    app.router.add_get("/healthz", lambda _: web.Response(text="ok"))
    return app
