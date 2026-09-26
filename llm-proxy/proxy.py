"""xiaozhi-server と Vercel AI Gateway の間に置く最小の中継。

xiaozhi-server の OpenAI プロバイダは reasoning_effort を送れないため、ここで既定値を注入する
（GPT-6 Luna は Chat Completions で function calling を使うには reasoning_effort: none が必須）。
Gateway の API キーもここで付与するので、xiaozhi-server の設定にキーを置かなくてよい。
根拠: okf/external/openai-gpt-6-luna.md、okf/decisions/008-llm-via-vercel-gateway.md
"""

import json
import logging
import os

from aiohttp import ClientSession, ClientTimeout, web

UPSTREAM = os.environ.get("LLM_PROXY_UPSTREAM", "https://ai-gateway.vercel.sh").rstrip("/")
API_KEY = os.environ["AI_GATEWAY_API_KEY"]
REASONING_EFFORT = os.environ.get("LLM_REASONING_EFFORT", "none")
PORT = int(os.environ.get("LLM_PROXY_PORT", "8080"))

# 上流へそのまま渡さないヘッダ
HOP_HEADERS = {"host", "authorization", "content-length", "transfer-encoding", "connection", "accept-encoding"}

log = logging.getLogger("llm-proxy")


async def handle(request: web.Request) -> web.StreamResponse:
    body = await request.read()
    if request.method == "POST" and request.path.endswith("/chat/completions") and body:
        payload = json.loads(body)
        # 呼び出し側が明示した値は尊重する
        if "reasoning_effort" not in payload and "reasoning" not in payload:
            payload["reasoning_effort"] = REASONING_EFFORT
        log.info("chat.completions model=%s reasoning_effort=%s tools=%d stream=%s",
                 payload.get("model"), payload.get("reasoning_effort"),
                 len(payload.get("tools") or []), payload.get("stream"))
        body = json.dumps(payload).encode()

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
    headers["Authorization"] = f"Bearer {API_KEY}"

    session: ClientSession = request.app["session"]
    async with session.request(request.method, UPSTREAM + request.path_qs, data=body, headers=headers) as upstream:
        response = web.StreamResponse(status=upstream.status)
        content_type = upstream.headers.get("Content-Type")
        if content_type:
            response.headers["Content-Type"] = content_type
        await response.prepare(request)
        # SSE をそのまま流す
        async for chunk in upstream.content.iter_any():
            await response.write(chunk)
        await response.write_eof()
        if upstream.status >= 400:
            log.warning("upstream %s %s -> %d", request.method, request.path, upstream.status)
        return response


async def on_startup(app: web.Application) -> None:
    app["session"] = ClientSession(timeout=ClientTimeout(total=300, sock_connect=10))


async def on_cleanup(app: web.Application) -> None:
    await app["session"].close()


async def health(_: web.Request) -> web.Response:
    return web.Response(text="ok")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/healthz", health)
    app.router.add_route("*", "/{path:.*}", handle)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
