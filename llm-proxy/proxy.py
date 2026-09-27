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

import gate
import jev
from speech_filter import SpeechFilter
from rewrites import FEWSHOT_ID_PREFIX, REWRITES, SUBSTRING_REWRITES

UPSTREAM = os.environ.get("LLM_PROXY_UPSTREAM", "https://ai-gateway.vercel.sh").rstrip("/")
API_KEY = os.environ["AI_GATEWAY_API_KEY"]
REASONING_EFFORT = os.environ.get("LLM_REASONING_EFFORT", "none")
PORT = int(os.environ.get("LLM_PROXY_PORT", "8080"))
# デバッグ用: 1 ならリクエスト本文（messages / tools）をログに出す。会話内容が残るので常用しない
LOG_BODY = os.environ.get("LLM_PROXY_LOG_BODY") == "1"
# 返答の本文から英語の独り言を取り除く（speech_filter.py）。0 で無効
FILTER_ENABLED = os.environ.get("LLM_PROXY_SPEECH_FILTER", "1") == "1"

# 上流へそのまま渡さないヘッダ
HOP_HEADERS = {"host", "authorization", "content-length", "transfer-encoding", "connection", "accept-encoding",
               "x-stackchan-source"}

log = logging.getLogger("llm-proxy")





def _rewrite_text(text: str) -> tuple[str, bool]:
    if text in REWRITES:
        return REWRITES[text], True
    changed = False
    for old, new in SUBSTRING_REWRITES.items():
        if old in text:
            text = text.replace(old, new)
            changed = True
    return text, changed


_warned: set = set()
_fewshot_missing_streak = 0


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        log.warning("UPSTREAM CHANGED? %s（xiaozhi-server の文言が変わった可能性。scripts/check_upstream_strings.py を実行）", message)


def check_expected_strings(payload: dict, rewritten: int) -> None:
    """置換が効くはずのリクエストで効いていなければ警告する（イメージ更新で文言が変わると静かに壊れるため）。"""
    messages = payload.get("messages") or []
    global _fewshot_missing_streak
    if payload.get("tools"):
        ids = [c.get("id", "") for m in messages for c in (m.get("tool_calls") or [])]
        # セッション最初の 1 往復は few-shot が入らないことがあるので、連続で見当たらない時だけ警告する
        if not any(i.startswith(FEWSHOT_ID_PREFIX) for i in ids):
            _fewshot_missing_streak += 1
            if _fewshot_missing_streak >= 5:
                _warn_once("fewshot-missing", "tools 付きのリクエストで few-shot（id が fewshot_ で始まる tool_call）が 5 回連続で見当たらない")
            return
        _fewshot_missing_streak = 0
        if rewritten == 0:
            _warn_once("fewshot-not-rewritten", "few-shot はあるが中国語の固定文言が 1 件も置換されなかった")
    for m in messages:
        content = m.get("content")
        if isinstance(content, list) and any(isinstance(p, dict) and p.get("type") == "image_url" for p in content):
            texts = " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
            if not any(new in texts for new in SUBSTRING_REWRITES.values()):
                _warn_once("vllm-suffix-missing", "画像説明のリクエストに日本語指示が入っていない（中国語指示の置換が効いていない）")


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
        check_expected_strings(payload, rewritten)
        log.info("chat.completions model=%s reasoning_effort=%s tools=%d stream=%s rewritten=%d",
                 payload.get("model"), payload.get("reasoning_effort"),
                 len(payload.get("tools") or []), payload.get("stream"), rewritten)
        if LOG_BODY:
            log.info("request body: %s", json.dumps(payload, ensure_ascii=False))
        # 宛先ゲート: ユーザー発話なら Jev で分類し、LLM を呼ばずに済むものは ここで返す
        text = gate.should_gate(payload, request.headers)
        if text is not None:
            decision, reply = await gate.decide(request.app["session"], payload, text)
            if decision != "pass":
                return web.Response(body=gate.sse_reply(payload.get("model", ""), reply), content_type="text/event-stream")
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
        # SSE を流す。本文に英語の独り言が混ざったら、そこから先の本文を捨てる（speech_filter.py）
        streaming = bool(content_type and content_type.startswith("text/event-stream") and upstream.status == 200)
        filt = SpeechFilter() if streaming and FILTER_ENABLED else None
        async for chunk in upstream.content.iter_any():
            out = filt.feed(chunk) if filt else chunk
            if out:
                await response.write(out)
        if filt:
            out = filt.close()
            if out:
                await response.write(out)
        await response.write_eof()
        if upstream.status >= 400:
            log.warning("upstream %s %s -> %d", request.method, request.path, upstream.status)
        return response


async def jev_evaluate(request: web.Request) -> web.Response:
    """brain 用の Jev 窓口（Vercel 形式）。呼び先は JEV_BACKEND で切り替わる。"""
    body = await request.json()
    try:
        res = await jev.evaluate(request.app["session"], body["state"], body["questions"])
    except jev.JevError as e:
        return web.json_response({"error": {"message": str(e)}}, status=e.status)
    return web.json_response(res)


async def gate_classify(request: web.Request) -> web.Response:
    """evals 用: 状態ブロブを宛先ゲートで分類して返す（記録しない）。"""
    return web.json_response(await gate.classify(request.app["session"], await request.json()))


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
    app.router.add_post("/jev/evaluate", jev_evaluate)
    app.router.add_post("/gate/classify", gate_classify)
    app.router.add_route("*", "/{path:.*}", handle)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
