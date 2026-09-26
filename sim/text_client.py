"""テキスト専用の最小疑似デバイス。

xiaozhi-server の WebSocket に hello を送り、`listen`/`detect` でテキストを 1 発話投げて、
返ってくる JSON（stt / llm / tts）と Opus フレーム数を表示する。音声の再生はしない。
プロトコルの根拠: okf/protocol/xiaozhi-protocol.md、使い方: okf/runbooks/simulator.md

    python sim/text_client.py --url ws://127.0.0.1:8000/xiaozhi/v1/ "こんにちは"

依存: websockets（xiaozhi-server イメージには同梱されている）
"""

import argparse
import asyncio
import json
import uuid

import websockets


async def run(url: str, text: str, device_id: str, timeout: float) -> int:
    headers = {
        "Authorization": "Bearer test-token",
        "Protocol-Version": "1",
        "Device-Id": device_id,
        "Client-Id": str(uuid.uuid4()),
    }
    async with websockets.connect(url, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "hello",
            "version": 1,
            "features": {"mcp": True},
            "transport": "websocket",
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
        }))
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        print("<< hello", hello)
        session_id = hello.get("session_id")

        await ws.send(json.dumps({"session_id": session_id, "type": "listen", "state": "detect", "text": text}))
        print(">> listen/detect", text)

        frames = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout)
            except asyncio.TimeoutError:
                print(f"!! {timeout}s 応答なし、終了")
                return 1
            except websockets.ConnectionClosed as e:
                # exit_commands 等でサーバーが接続を閉じた
                print(f"== サーバーが接続を閉じた (code={e.rcvd.code if e.rcvd else None})")
                return 0
            if isinstance(msg, bytes):
                frames += 1
                continue
            data = json.loads(msg)
            print("<<", data)
            if data.get("type") == "tts" and data.get("state") == "stop":
                print(f"== 完了: Opus フレーム {frames} 個受信")
                return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--url", default="ws://127.0.0.1:8000/xiaozhi/v1/")
    p.add_argument("--device-id", default="02:00:00:00:00:01")
    p.add_argument("--timeout", type=float, default=30.0)
    a = p.parse_args()
    raise SystemExit(asyncio.run(run(a.url, a.text, a.device_id, a.timeout)))


if __name__ == "__main__":
    main()
