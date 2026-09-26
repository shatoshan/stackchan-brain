---
type: ExternalAPI
title: Vercel AI Gateway（LLM と Jev の統一窓口）
description: LLM（GPT-6 Luna）と Jev を 1 本の API キーで呼ぶ Vercel AI Gateway のエンドポイント・認証・推論設定・カタログ。
tags: [vercel, ai-gateway, openai-compat, llm, jev]
resource: https://ai-gateway.vercel.sh
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:45:00Z }
sources:
  - id: v-chat
    resource: https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions
    title: OpenAI Chat Completions API with AI Gateway（last_updated 2026-09-08）
    author: org:vercel
  - id: v-reasoning
    resource: https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions/reasoning
    title: OpenAI Chat Completions Reasoning with AI Gateway
    author: org:vercel
  - id: v-catalog
    resource: https://ai-gateway.vercel.sh/v1/models
    title: AI Gateway モデルカタログ（認証なしで取得、2026-09-26）
    author: org:vercel
  - id: v-eval
    resource: https://vercel.com/docs/ai-gateway/modalities/evaluation
    title: Vercel AI Gateway — Evaluation（Jev）
  - id: run-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 xiaozhi-server → llm-proxy → Gateway の疎通（ダミーキーで 401）
---

# 使い分け

| 用途 | エンドポイント | 呼び出し元 |
|---|---|---|
| ランタイム LLM（[GPT-6 Luna](/external/openai-gpt-6-luna.md)） | `POST https://ai-gateway.vercel.sh/v1/chat/completions`（OpenAI Chat Completions 互換） | xiaozhi-server → [llm-proxy](/services/llm-proxy.md) |
| 直感層の判定（[Jev](/external/jev.md)） | `POST https://ai-gateway.vercel.sh/v1/evaluate` ほか | brain（M3〜） |

- 認証はどちらも `Authorization: Bearer $AI_GATEWAY_API_KEY`。**キーは 1 本で済む**。[^v-chat] [^v-eval]
- 採用理由は [決定 008](/decisions/008-llm-via-vercel-gateway.md)。

# OpenAI 互換 API（Chat Completions）

- ベース URL `https://ai-gateway.vercel.sh/v1`。OpenAI 公式クライアントは `base_url` と `api_key` の差し替えだけで使える。モデル ID は `<provider>/<model>` 形式。[^v-chat]
- エンドポイント: `GET /models`、`GET /models/{model}`、`POST /chat/completions`（ストリーミング・ツール呼び出し・構造化出力対応）、`POST /embeddings`。[^v-chat]
- 推論の制御: `reasoning` オブジェクト（Gateway 拡張、`enabled` / `effort` / `max_tokens` / `exclude`）。**標準の `reasoning_effort` フィールドは `reasoning.effort` の別名**で、両方あれば `reasoning` 側が優先。effort は `none`〜`max`。OpenAI には `reasoningEffort` としてマップされる。[^v-reasoning]
- 推論トークンは `usage.completion_tokens_details.reasoning_tokens` に出る（＝出力として課金される）。[^v-reasoning]
- エラー: 401 認証、429 レート制限など標準の HTTP ステータス。[^v-chat]

# モデルカタログ

- `GET https://ai-gateway.vercel.sh/v1/models` は **認証なしで取得でき**、各モデルの `pricing`（USD / トークン）、`supported_parameters`、`reasoning_options`、`zdr`、`no_training`、`context_window` が入っている。モデル ID・料金・ZDR 可否はここで確認するのが確実。[^v-catalog]
- 2026-09-26 時点の抜粋:[^v-catalog]

| ID | 入力 / 出力（per MTok） | zdr | 備考 |
|---|---|---|---|
| `openai/gpt-6-luna` | $0.10 / $0.50 | some | temperature 可、effort `none`〜`max`、regions us |
| `openai/gpt-6-luna-fast` | $0.20 / $1.00 | some | 高速サービス版（同モデル、2倍価格） |
| `anthropic/claude-haiku-4.5` | $1.00 / $5.00 | all | 参考（旧ランタイム候補） |
| `typesafe-ai/jev` | $0.042 / $0 | **none** | type: evaluation |

# 観測

- **無料枠（Free tier）では使えないモデルがある。** 2026-09-26、実キーで `openai/gpt-6-luna` を呼ぶと `403 no_providers_available` / `RestrictedModelsError`「Free tier users do not have access to this model. Upgrade to paid credits」。認証自体は通っている。同じキーで `typesafe-ai/jev` は 200。どのモデルが無料枠で使えるかはカタログからは読み取れない。[^run-0926]

- 2026-09-26、ダミーキーで xiaozhi-server → llm-proxy → Gateway を通し、Gateway から `401 Authentication failed. Create an API key and set in AI_GATEWAY_API_KEY ...` が返ることを確認。経路とリクエスト形式は通っている。実キーでの応答は未確認。[^run-0926]

[^v-chat]: OpenAI Chat Completions API with AI Gateway
[^v-reasoning]: OpenAI Chat Completions Reasoning with AI Gateway
[^v-catalog]: AI Gateway モデルカタログ
[^v-eval]: Vercel AI Gateway — Evaluation
[^run-0926]: 2026-09-26 疎通
