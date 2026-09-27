"""Jev（TypeSafe System One）クライアント。呼び先を環境変数で切り替える。

- JEV_BACKEND=gateway（既定）: Vercel AI Gateway の /v1/evaluate（キーは AI_GATEWAY_API_KEY）
- JEV_BACKEND=typesafe: TypeSafe の /v1/systemone を直接（キーは TYPESAFE_API_KEY）

入出力は Vercel の形式（質問の型 boolean / choice / score、答えの boolean は {"probability"}）に揃える。
TypeSafe 直接では boolean を noul に読み替え、答えの {"noul": p} を {"probability": p} に戻す。
根拠: okf/external/jev.md
"""

import asyncio
import os

from aiohttp import ClientSession

BACKEND = os.environ.get("JEV_BACKEND", "gateway")
GATEWAY_URL = os.environ.get("LLM_PROXY_UPSTREAM", "https://ai-gateway.vercel.sh").rstrip("/") + "/v1/evaluate"
GATEWAY_MODEL = os.environ.get("JEV_GATEWAY_MODEL", "typesafe-ai/jev")
TYPESAFE_URL = os.environ.get("TYPESAFE_API_URL", "https://api.typesafe.ai/v1/systemone")
TYPESAFE_MODEL = os.environ.get("JEV_TYPESAFE_MODEL", "jev-latest")


class JevError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"jev {status}: {body[:200]}")
        self.status = status


# 429 / 529（混雑）の時の再試行の待ち時間（秒）。TypeSafe のドキュメントは指数バックオフでの再試行を案内している。
# 宛先ゲートは返事の遅れに直結するので短めにする
RETRY_DELAYS = [float(x) for x in os.environ.get("JEV_RETRY_DELAYS", "0.3,0.8").split(",") if x]


async def evaluate(session: ClientSession, state, questions: dict, timeout: float = 10.0) -> dict:
    """Vercel 形式の questions を受け取り、Vercel 形式の {"answers": ..., "backend": ..., "attempts": n} を返す。"""
    for attempt, delay in enumerate([0.0] + RETRY_DELAYS):
        if delay:
            await asyncio.sleep(delay)
        try:
            res = await _evaluate_once(session, state, questions, timeout)
            res["attempts"] = attempt + 1
            return res
        except JevError as e:
            if e.status not in (429, 529) or attempt == len(RETRY_DELAYS):
                raise


async def _evaluate_once(session: ClientSession, state, questions: dict, timeout: float) -> dict:
    if BACKEND == "typesafe":
        qs = {k: dict(v, type="noul") if v.get("type") == "boolean" else v for k, v in questions.items()}
        headers = {"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"}
        url, body = TYPESAFE_URL, {"model": TYPESAFE_MODEL, "state": state, "questions": qs}
    else:
        headers = {"Authorization": f"Bearer {os.environ['AI_GATEWAY_API_KEY']}"}
        url, body = GATEWAY_URL, {"model": GATEWAY_MODEL, "state": state, "questions": questions}
    async with session.post(url, json=body, headers=headers, timeout=timeout) as r:
        text = await r.text()
        if r.status != 200:
            raise JevError(r.status, text)
        data = await r.json(content_type=None)
    answers = data.get("answers", {})
    for k, a in answers.items():
        if isinstance(a, dict) and "noul" in a and "probability" not in a:
            a["probability"] = a.pop("noul")
            a["type"] = "boolean"
    return {"answers": answers, "backend": BACKEND, "model": data.get("model"), "providerMetadata": data.get("providerMetadata")}
