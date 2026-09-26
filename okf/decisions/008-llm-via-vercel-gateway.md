---
type: Decision
title: "008: ランタイム LLM は GPT-6 Luna、LLM と Jev は Vercel AI Gateway に統一"
description: コスト効率のため Haiku から GPT-6 Luna に切り替え、LLM と Jev を 1 本の Vercel AI Gateway キーで呼ぶ。
tags: [decision, adr, llm, vercel]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:45:00Z }
sources:
  - id: user-0926
    resource: process:chat-2026-09-26
    title: 2026-09-26 のユーザー指示（コスト効率の観点で Luna、Gateway を統合してキー管理を楽に）
    author: human:shingo
  - id: v-catalog
    resource: https://ai-gateway.vercel.sh/v1/models
    title: AI Gateway モデルカタログ（2026-09-26）
  - id: oa-model
    resource: https://developers.openai.com/api/docs/models/gpt-6-luna
    title: GPT-6 Luna Model | OpenAI API
---

# 決定

- ランタイム LLM（xiaozhi-server の会話、および熟考層の発話生成・要約）を Claude Haiku から **OpenAI GPT-6 Luna**（`openai/gpt-6-luna`）に切り替える。[^user-0926]
- LLM と Jev はどちらも **Vercel AI Gateway** 経由で呼び、API キーは `AI_GATEWAY_API_KEY` の 1 本にする。Anthropic API キーは使わない。[^user-0926]
- xiaozhi-server からは [llm-proxy](/services/llm-proxy.md) を挟んで呼ぶ。

# 理由

- コスト: Luna は $0.10 / $0.50 per MTok、Haiku 4.5 は $1 / $5。[^v-catalog]
- キー管理: 秘密情報が 1 つになり、利用量・請求も Gateway に集約される。
- llm-proxy が要る理由: Luna は Chat Completions で function calling を使うのに `reasoning_effort: none` が必須だが、xiaozhi-server にはそれを送る設定が無い。[^oa-model]

# 帰結

- [決定 004](/decisions/004-no-bedrock.md)（Anthropic 直、Bedrock 不採用）は前提が変わったので `deprecated`。[Anthropic API](/external/anthropic-api.md) も `deprecated`。
- Jev のフォールバック（同じ質問群を LLM に JSON で答えさせる）も Luna で行う。
- Gateway 上の ZDR は Luna が `some`、Jev が `none`。ZDR を必須にはできない。[^v-catalog]
- 将来モデルを変える時は `.env` の `LLM_MODEL` を差し替えるだけで済む（Gateway の他モデルも同じキーで呼べる）。

[^user-0926]: 2026-09-26 のユーザー指示
[^v-catalog]: AI Gateway モデルカタログ
[^oa-model]: GPT-6 Luna Model | OpenAI API
