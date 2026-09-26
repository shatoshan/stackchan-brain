"""テキスト専用の最小疑似デバイス。

xiaozhi-server の WebSocket に hello を送り、`listen`/`detect` でテキストを 1 発話投げて、
返ってくる JSON（stt / llm / tts）と Opus フレーム数を表示する。音声の再生はしない。
プロトコルの根拠: okf/protocol/xiaozhi-protocol.md、使い方: okf/runbooks/simulator.md

    python sim/text_client.py --url ws://127.0.0.1:8000/xiaozhi/v1/ "こんにちは"
    python sim/text_client.py --url ws://brain:8010/xiaozhi/v1/ --hold 60   # 聞き取り状態で待ち、届いた発話を表示

依存: websockets（xiaozhi-server イメージには同梱されている）
"""

import argparse
import asyncio
import json
import uuid

import websockets


async def hold(ws, session_id: str, seconds: float) -> int:
    """実機の auto モードと同じく listen/start を送り、届くメッセージを seconds 秒表示する。"""
    await ws.send(json.dumps({"session_id": session_id, "type": "listen", "state": "start", "mode": "auto"}))
    print(f">> listen/start (auto)、{seconds:.0f} 秒待機")
    loop = asyncio.get_running_loop()
    end = loop.time() + seconds
    frames = 0
    while (remaining := end - loop.time()) > 0:
        try:
            msg = await asyncio.wait_for(ws.recv(), remaining)
        except asyncio.TimeoutError:
            break
        except websockets.ConnectionClosed as e:
            print(f"== サーバーが接続を閉じた (code={e.rcvd.code if e.rcvd else None})")
            return 0
        if isinstance(msg, bytes):
            frames += 1
            continue
        data = json.loads(msg)
        if data.get("type") != "mcp":
            print("<<", data)
        if data.get("type") == "tts" and data.get("state") == "stop":
            print(f"== Opus フレーム {frames} 個")
            frames = 0
    return 0


async def run(url: str, text: str, device_id: str, timeout: float, hold_seconds: float = 0) -> int:
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
        if hold_seconds:
            return await hold(ws, session_id, hold_seconds)

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
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--url", default="ws://127.0.0.1:8000/xiaozhi/v1/")
    p.add_argument("--device-id", default="02:00:00:00:00:01")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--hold", type=float, default=0, help="テキストを送らず、聞き取り状態で指定秒数待つ")
    a = p.parse_args()
    if not a.text and not a.hold:
        p.error("text か --hold のどちらかが必要")
    raise SystemExit(asyncio.run(run(a.url, a.text, a.device_id, a.timeout, a.hold)))


if __name__ == "__main__":
    main()
