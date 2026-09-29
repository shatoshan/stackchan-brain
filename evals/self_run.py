"""「自分について聞かれた時に、ツール（self-mcp）で調べて答えられるか」の確認（決定 013）。

    docker compose exec -T brain python /evals/self_run.py

brain の中継に疑似端末としてつなぎ、self_cases.jsonl の質問をし、返事に期待する語のどれかが入っているかを見る。
LLM の答えは毎回変わるので厳密な正解判定ではなく、ツールが使われず推測で答える（「人の耳は…」など）退行を拾うためのもの。
xiaozhi-server は接続後にツールとシステムプロンプトを後から読み込むので、つないでから少し待って質問する。
"""
import asyncio
import json
import time

import aiohttp

RELAY = "ws://127.0.0.1:8010/xiaozhi/v1/"
DEVICE = "02:00:00:00:00:01"  # 疑似端末（実機の記憶や記録と混ざらない）
WAIT_AFTER_CONNECT = 3.0


async def ask(question: str) -> tuple[str, float]:
    async with aiohttp.ClientSession() as s, s.ws_connect(RELAY, headers={"Device-Id": DEVICE, "Client-Id": "evals",
                                                                          "Protocol-Version": "1"}) as ws:
        await ws.send_str(json.dumps({"type": "hello", "version": 1, "transport": "websocket",
                                      "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}}))
        while True:
            m = await ws.receive()
            if m.type == aiohttp.WSMsgType.TEXT and json.loads(m.data).get("type") == "hello":
                sid = json.loads(m.data)["session_id"]
                break
        await ws.send_str(json.dumps({"session_id": sid, "type": "listen", "state": "start", "mode": "auto"}))
        await asyncio.sleep(WAIT_AFTER_CONNECT)
        t0, first, said = time.time(), 0.0, []
        await ws.send_str(json.dumps({"session_id": sid, "type": "listen", "state": "detect", "text": question}))
        while True:
            m = await asyncio.wait_for(ws.receive(), 60)
            if m.type != aiohttp.WSMsgType.TEXT:
                continue
            d = json.loads(m.data)
            if d.get("type") == "tts" and d.get("state") == "sentence_start":
                first = first or time.time() - t0
                said.append(d["text"])
            if d.get("type") == "tts" and d.get("state") == "stop":
                return "".join(said), first


async def main() -> None:
    ok = total = 0
    for line in open("/evals/self_cases.jsonl", encoding="utf-8"):
        if not line.strip():
            continue
        c = json.loads(line)
        answer, first = await ask(c["question"])
        hit = any(k in answer for k in c["expect_any"])
        ok += hit
        total += 1
        print(f"{'OK' if hit else 'NG'} {c['id']:12} {first:4.1f}s 「{c['question']}」\n   → {answer[:120]}")
    print(f"\n{ok}/{total}")


if __name__ == "__main__":
    asyncio.run(main())
