---
type: ExternalAPI
title: OpenAI GPT-6 Luna（ランタイム LLM）
description: 発話生成・要約に使う GPT-6 Luna の料金・推論設定と、Chat Completions で function calling を使う際の制約。
tags: [openai, gpt-6, luna, llm]
status: stable
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:45:00Z }
sources:
  - id: oa-model
    resource: https://developers.openai.com/api/docs/models/gpt-6-luna
    title: GPT-6 Luna Model | OpenAI API
    author: org:openai
  - id: oa-intro
    resource: https://openai.com/index/introducing-gpt-6-sol-and-luna/
    title: Introducing GPT-6 Sol and Luna（2026-09-22）
    author: org:openai
  - id: v-changelog
    resource: https://vercel.com/changelog/gpt-6-sol-and-luna-now-available-on-ai-gateway
    title: GPT-6 Sol and Luna now available on AI Gateway
    author: org:vercel
  - id: run-0926
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 実キーでの呼び出し（403）
  - id: v-catalog
    resource: https://ai-gateway.vercel.sh/v1/models
    title: AI Gateway モデルカタログ（2026-09-26）
---

> 2026-09-26 に有料クレジット投入後の実呼び出しで疎通を確認し `stable` に。function calling でツールが実際に呼ばれるケースと日本語品質の評価はまだ（下記「その他の未確認事項」）。日本語の応答品質・レイテンシ・function calling の実動作は未確認。

# 基本情報

- 2026-09-22 リリース。GPT-6 シリーズの高速・低コスト版で、上位は GPT-6 Sol。チャット・分類・軽いエージェント処理向け。[^oa-intro]
- Vercel AI Gateway のモデル ID: **`openai/gpt-6-luna`**（OpenAI 直なら `gpt-6-luna`）。[^v-changelog] [^oa-model]
- 料金: 入力 $0.10 / MTok、キャッシュ入力 $0.01、出力 $0.50。272K 入力トークン超は入力2倍・出力1.5倍。Gateway の表示も同額。[^oa-model] [^v-catalog]
  - 参考: Claude Haiku 4.5 は $1 / $5。Luna は約 1/10。
- コンテキスト 1,050,000 トークン、最大出力 128,000。入力はテキストと画像、出力はテキスト。知識カットオフ 2026-05-18。[^oa-model]
- Chat Completions と Responses の両 API に対応。ストリーミング・function calling・構造化出力・prompt caching に対応。[^oa-model]

# 推論努力（重要）

- `reasoning_effort`: `none` / `low` / `medium`（**デフォルト**）/ `high` / `xhigh` / `max`。[^oa-model]
- **「Chat Completions で function calling が使えるのは `reasoning_effort` が `none` の時だけ」**（OpenAI 公式）。[^oa-model]
- xiaozhi-server は Intent `function_call` で端末 MCP ツール（首・LED）や内蔵プラグインを tools として Chat Completions に渡す。しかし xiaozhi-server の OpenAI プロバイダには `reasoning_effort` を設定する口が無い。→ [llm-proxy](/services/llm-proxy.md) で `none` を注入している。
- 音声会話では推論トークンは遅延と出力課金を増やすだけなので、ランタイムは `none` を基本とする。
- 未確認: Gateway 経由（Vercel が内部で Responses API にマップする可能性がある）で `medium` のまま tools を送った場合に実際にエラーになるか。

# 利用条件（2026-09-26 観測）

- Vercel AI Gateway の **無料枠では使えない**。`403 RestrictedModelsError: Free tier users do not have access to this model`。有料クレジットのチャージが必要。ルーティング情報上のフォールバック候補は `bedrock`、`azure`。[^run-0926]

# 実測（2026-09-26、有料クレジット投入後）

- xiaozhi-server から `tools=8`、`reasoning_effort=none`、`stream=True` で呼び、**200**。「こんにちは」に対し「こんにちは。また会えてうれしいよ」を日本語で返した。tools を付けてもエラーにならない。[^run-0926]
- リクエスト受信からストリーム完了まで約 2.6 秒、ユーザー発話受信から最初の TTS 文送出まで約 3 秒（ログの秒単位で計測、1 回のみ）。[^run-0926]

# その他の未確認事項

- LLM が実際にツール（端末 MCP の首・LED 等）を呼ぶケース。M2 で実機接続時に確認する。
- 初トークンまでの時間を細かく測っていない。

- `temperature` はカタログ上 `true`（対応）だが、推論モデルでの挙動が不明なので設定では指定していない。
- `max_tokens` の扱い（OpenAI 直では推論モデルに `max_completion_tokens` が要る場合がある）。Gateway のカタログは `max_tokens` を supported として挙げている。[^v-catalog]
- Gateway 上の `zdr` は `some`（一部プロバイダのみ ZDR）。

[^oa-model]: GPT-6 Luna Model | OpenAI API
[^oa-intro]: Introducing GPT-6 Sol and Luna
[^v-changelog]: GPT-6 Sol and Luna on AI Gateway
[^v-catalog]: AI Gateway モデルカタログ
[^run-0926]: 2026-09-26 実キーでの呼び出し
