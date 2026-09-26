---
type: ExternalAPI
title: Jev（TypeSafe System One Model）via Vercel AI Gateway
description: 直感層の構造化判定に使う Jev の呼び方（Vercel AI Gateway）、料金・制限、レスポンス形式。
tags: [jev, typesafe, vercel, ai-gateway, classification]
status: draft
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:45:00Z }
sources:
  - id: ts-blog
    resource: https://typesafe.ai/blog/introducing-system-one-models-and-jev
    title: Introducing System One Models and Jev
    author: org:typesafe-ai
  - id: ts-models
    resource: https://docs.typesafe.ai/models.md
    title: TypeSafe docs — Models
    author: org:typesafe-ai
  - id: ts-api
    resource: https://docs.typesafe.ai/api.md
    title: TypeSafe docs — API
  - id: ts-py
    resource: https://docs.typesafe.ai/sdk/python/api/clients/sync.md
    title: typesafe-sdk Python client
  - id: v-eval
    resource: https://vercel.com/docs/ai-gateway/modalities/evaluation
    title: Vercel AI Gateway — Evaluation
    author: org:vercel
  - id: v-typesafe
    resource: https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe
    title: Vercel AI Gateway — TypeSafe-compatible API
    author: org:vercel
  - id: v-models
    resource: https://vercel.com/ai-gateway/models?capabilities=evaluation
    title: Vercel AI Gateway models (evaluation)
  - id: v-cl-launch
    resource: https://vercel.com/changelog/typesafe-ai-jev-now-available-on-ai-gateway
    title: Vercel changelog — Jev on AI Gateway (2026-09-16)
  - id: v-cl-client
    resource: https://vercel.com/changelog/ai-gateway-now-supports-typesafe-clients-and-http-api-for-jev
    title: Vercel changelog — TypeSafe clients & HTTP API (2026-09-21)
  - id: v-what
    resource: https://vercel.com/i/what-is-jev
    title: What is Jev (Vercel)
  - id: run-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 llm-proxy 経由での実呼び出し
  - id: run-0926b
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 M3 判定ループでの利用
  - id: v-catalog
    resource: https://ai-gateway.vercel.sh/v1/models
    title: AI Gateway モデルカタログ（2026-09-26）
  - id: or-jev
    resource: https://openrouter.ai/docs/guides/community/jev
    title: OpenRouter — Jev guide
  - id: cf-jev
    resource: https://developers.cloudflare.com/ai/models/typesafe/jev/
    title: Cloudflare Workers AI — typesafe/jev
---

> `status: draft` の理由: 最小リクエスト 1 件で疎通しただけで、判定品質・レート制限・フォールバック時の挙動は未確認。

# 実測（2026-09-26）

- `POST https://ai-gateway.vercel.sh/v1/evaluate` に boolean 質問 1 問（`should_speak`）を送り **200**。応答は `{"answers":{"should_speak":{"type":"boolean","probability":0.59}}, "model":"typesafe-ai/jev", "providerMetadata":{"typesafe":{"confidence":{}}, "gateway":{...}}}`。[^run-0926]
- **Vercel の無料枠でも使える**（同じキーで GPT-6 Luna は 403）。[^run-0926]
- 上流（typesafe-ai）の処理時間 約 160ms、コスト \$0.000012。ルーティングは `typesafe-ai` 優先、フォールバック `digitalocean`。[^run-0926]
- `providerMetadata.typesafe.confidence` キーは Gateway 経由でも存在するが、boolean 質問では空オブジェクトだった。確率本体は `answers` 側。[^run-0926]

# 使ってみて分かったこと（2026-09-26、M3）

- `score` 型は `criteria` に段階ごとの説明の **配列** が必須（無いと 400 `questions.<name>.criteria: expected array`）。答えは 0 始まりの段階ごとの確率と、その期待値 `score`。[^run-0926b]
- `choice` の答えには `probabilities` に加えて `confidence` が付く。[^run-0926b]
- 4 問（choice 4 つ）で約 0.5〜0.6 秒、1 回 $0.000025〜0.000037。[^run-0926b]
- **混雑による 429 が頻発する。** `rate_limit_exceeded`「The upstream provider is currently experiencing high demand」。最小のリクエストでも同じで、こちらのリクエスト内容とは無関係。約 30 分の試験中、成功は数回だけだった。brain は 429 で Jev を 60 秒〜10 分止め、その間は LLM の分類で代替する。[^run-0926b]
- 使い方の設計は [直感層の質問設計](/design/jev-questions.md)。

# 何に使うか

- **生成しない構造化判定**。状態（テキスト / JSON）と質問群を渡すと、事前定義した選択肢から較正済み確率付きで答える。直感層で使う（[3層アーキテクチャ](/design/three-layer-architecture.md)）。[^ts-blog]
- 入力は **テキストのみ**（文字列・JSON オブジェクト・配列）。画像・音声不可。[^ts-models] [^v-what]
- レイテンシ 70〜500ms（TypeSafe 公称）。[^ts-blog]

# モデル ID とバージョン

| 経路 | モデル ID |
|---|---|
| **Vercel AI Gateway（採用）** | `typesafe-ai/jev`[^v-eval] |
| TypeSafe 本家 | `jev-1.13.0`（`jev-latest` / `jev-preview` も同じ）[^ts-models] |
| OpenRouter | `typesafe/jev-1.13`、エイリアス `~typesafe/jev-latest`[^or-jev] |
| Cloudflare Workers AI | `typesafe/jev`[^cf-jev] |

- 未確認: Vercel 上でバージョン（1.13）を固定指定できるか。

# 呼び方（Vercel AI Gateway）

- 認証: `Authorization: Bearer $AI_GATEWAY_API_KEY`（Vercel OIDC トークンも可）。[^v-eval]
- 方法は3つ:[^v-eval] [^v-typesafe]
  1. HTTP: `POST https://ai-gateway.vercel.sh/v1/evaluate`
  2. TypeSafe 互換 API: ベース URL `https://ai-gateway.vercel.sh/typesafe`（`POST /typesafe/v1/systemone`、`GET /typesafe/v1/models`）。**公式クライアントはベース URL とキーを差し替えるだけで使える**（JS: `@typesafe-ai/sdk` の `baseURL`、Python: `typesafe-sdk` の `base_url`[^ts-py]）
  3. AI SDK 7（`experimental_evaluate` / `gateway.evaluationModel('typesafe-ai/jev')`）
- OpenAI / Anthropic 互換エンドポイントでは **呼べない**。[^v-eval]
- ZDR: `providerOptions: { gateway: { zeroDataRetention: true, only: ["typesafe-ai"] } }`。No-Training もリクエスト単位で指定できると changelog にあるが、キー名は未確認。[^v-eval] [^v-cl-launch]
  - ⚠ ただし Gateway のモデルカタログ（`GET /v1/models`、2026-09-26）では `typesafe-ai/jev` の `zdr` は `none`、`no_training` は `all`。ZDR 指定は通らない可能性が高い。[^v-catalog]
- キーは LLM と共通の `AI_GATEWAY_API_KEY`（[Vercel AI Gateway](/external/vercel-ai-gateway.md)、[決定 008](/decisions/008-llm-via-vercel-gateway.md)）。

# リクエスト / レスポンス

- リクエスト: `model`、`state`（文字列 / オブジェクト / 配列）、`questions`（名前→{`type`, `instructions`, `criteria`} のマップ）。[^v-eval]
- 質問タイプ:[^v-eval] [^ts-api]
  - `choice`: `criteria` は `{選択肢名: 説明}`、**最大 255 択**。答えは `{choice, probabilities: {...}}`
  - `score`: 2〜10 段階。答えは `{score, probabilities}`
  - `boolean`（TypeSafe 本家 API では `noul`）: 答えは `{probability}`
- **確率は `answers` 側に入る**。`providerMetadata.gateway` はルーティング・コスト情報だけ。[^v-eval]
  - ⚠ キックオフ指示書（docs/KICKOFF.md §3）の「Choice/Score の信頼度は providerMetadata で返る」とは食い違う。AI SDK の TypeSafe 直結プロバイダでは `providerMetadata.typesafe.confidence` があるが、Gateway 経由で出るかは未確認。
- コンテキスト: TypeSafe は 1 リクエスト 64k（`state` + 最長の質問で 32k）。Vercel の表記は 32K。[^ts-models] [^v-models]

# 料金・制限・提供状況

- 料金: 入力 $0.042 / MTok、出力無料（Vercel 表記は $0.04）。[^ts-models] [^v-models]
- レート制限: TypeSafe 本家は 250,000 tokens/s、1,200 req/min。**Vercel 側の制限は未確認**。[^ts-models]
- 提供状況: Vercel AI Gateway で 2026-09-16 から提供、TypeSafe クライアント / HTTP 対応は 2026-09-21。preview / beta 表記なし。[^v-cl-launch] [^v-cl-client]
- TypeSafe 本家はブログ上 "early access"。コンソールの受付停止は一次情報で確認できていない（console.typesafe.ai は 403）。

# フォールバック

- Jev が使えない期間は、同じ質問群を GPT-6 Luna に JSON で答えさせる実装を用意し、インターフェースを揃える（確率は取れないので擬似値）。[Jev 質問設計](/design/state-blob.md) を共有する。

[^ts-blog]: Introducing System One Models and Jev
[^ts-models]: TypeSafe docs — Models
[^ts-api]: TypeSafe docs — API
[^ts-py]: typesafe-sdk Python client
[^v-eval]: Vercel AI Gateway — Evaluation
[^v-typesafe]: Vercel AI Gateway — TypeSafe-compatible API
[^v-models]: Vercel AI Gateway models
[^v-cl-launch]: Vercel changelog — Jev launch
[^v-cl-client]: Vercel changelog — TypeSafe clients
[^v-what]: What is Jev
[^v-catalog]: AI Gateway モデルカタログ
[^run-0926]: 2026-09-26 実呼び出し
[^run-0926b]: 2026-09-26 M3 判定ループでの利用
[^or-jev]: OpenRouter — Jev guide
[^cf-jev]: Cloudflare Workers AI — typesafe/jev
