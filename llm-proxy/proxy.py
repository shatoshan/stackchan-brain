"""xiaozhi-server と Vercel AI Gateway の間に置く最小の中継。

xiaozhi-server の OpenAI プロバイダは reasoning_effort を送れないため、ここで既定値を注入する
（GPT-6 Luna は Chat Completions で function calling を使うには reasoning_effort: none が必須）。
Gateway の API キーもここで付与するので、xiaozhi-server の設定にキーを置かなくてよい。
また、本体が会話履歴に差し込む中国語の固定文言（few-shot 例、ウェイクワード時の呼びかけ）を
完全一致で日本語に置き換える。これが残るとモデルが中国語で返答することがある。
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
# デバッグ用: 1 ならリクエスト本文（messages / tools）をログに出す。会話内容が残るので常用しない
LOG_BODY = os.environ.get("LLM_PROXY_LOG_BODY") == "1"

# 上流へそのまま渡さないヘッダ
HOP_HEADERS = {"host", "authorization", "content-length", "transfer-encoding", "connection", "accept-encoding"}

log = logging.getLogger("llm-proxy")

# xiaozhi-server server_0.9.6 が差し込む中国語の固定文言 → 日本語。完全一致のみ置換する。
# 出典: core/connection.py _inject_tool_call_fewshot、core/handle/textHandler/listenMessageHandler.py
REWRITES = {
    "给我讲个故事吧": "お話を聞かせて",
    "好呀，你想听什么类型的呀？童话、冒险还是搞笑的？选一个我给你开讲~": "いいよ、どんなお話がいい？昔話、冒険、おもしろい話から選んでね。",
    "已直接回复": "直接返答しました",
    "拜拜": "バイバイ",
    "再见，下次再聊~": "またね、また話そうね。",
    "退出意图已处理": "終了処理をしました",
    "嘿，你好呀": "スタックチャン、こんにちは",
}


# 文中に埋め込まれる中国語の固定指示 → 日本語（部分置換）。
# 出典: core/providers/vllm/openai.py（画像説明の質問末尾に「(请使用中文回复)」を固定で付ける。結果はそのまま読み上げられる）
SUBSTRING_REWRITES = {
    "(请使用中文回复)": "（日本語で、1〜2文の短い話し言葉で答えてください）",
}


def _rewrite_text(text: str) -> tuple[str, bool]:
    if text in REWRITES:
        return REWRITES[text], True
    changed = False
    for old, new in SUBSTRING_REWRITES.items():
        if old in text:
            text = text.replace(old, new)
            changed = True
    return text, changed


def rewrite_messages(messages: list) -> int:
    """messages 内の固定文言を置き換え、置き換えた件数を返す。"""
    count = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"], changed = _rewrite_text(content)
            count += changed
        elif isinstance(content, list):
            # 画像付きメッセージ（[{type: text}, {type: image_url}]）の文章部分
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    part["text"], changed = _rewrite_text(part["text"])
                    count += changed
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                continue
            if not isinstance(args, dict):
                continue
            changed = False
            for key, value in args.items():
                if isinstance(value, str) and value in REWRITES:
                    args[key] = REWRITES[value]
                    changed = True
            if changed:
                fn["arguments"] = json.dumps(args, ensure_ascii=False)
                count += 1
    return count


async def handle(request: web.Request) -> web.StreamResponse:
    body = await request.read()
    if request.method == "POST" and request.path.endswith("/chat/completions") and body:
        payload = json.loads(body)
        # 呼び出し側が明示した値は尊重する
        if "reasoning_effort" not in payload and "reasoning" not in payload:
            payload["reasoning_effort"] = REASONING_EFFORT
        rewritten = rewrite_messages(payload.get("messages") or [])
        log.info("chat.completions model=%s reasoning_effort=%s tools=%d stream=%s rewritten=%d",
                 payload.get("model"), payload.get("reasoning_effort"),
                 len(payload.get("tools") or []), payload.get("stream"), rewritten)
        if LOG_BODY:
            log.info("request body: %s", json.dumps(payload, ensure_ascii=False))
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
