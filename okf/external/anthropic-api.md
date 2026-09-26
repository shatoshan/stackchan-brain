---
type: ExternalAPI
title: Anthropic Claude API（ランタイム LLM）
description: xiaozhi-server から OpenAI 互換レイヤーで Claude Haiku を呼ぶ際のモデル名・制約と、ネイティブ API への移行方針。
tags: [anthropic, claude, haiku, llm, openai-compat]
resource: https://api.anthropic.com/v1/
status: deprecated
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T07:40:00Z }
sources:
  - id: openai-compat
    resource: https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk
    title: OpenAI SDK compatibility
    author: org:anthropic
  - id: models
    resource: https://platform.claude.com/docs/en/models/overview
    title: Models overview
    author: org:anthropic
  - id: smoke
    resource: /runbooks/simulator.md
    title: 2026-09-26 疑似デバイスでの疎通（401 を確認）
---

> **deprecated（2026-09-26）**: ランタイム LLM は GPT-6 Luna（Vercel AI Gateway 経由）に切り替えた。→ [決定 008](/decisions/008-llm-via-vercel-gateway.md)、[GPT-6 Luna](/external/openai-gpt-6-luna.md)。以下は履歴として残す。

# 使い方（xiaozhi-server から）

- OpenAI SDK 互換レイヤー: `base_url=https://api.anthropic.com/v1/`、API キーに Claude API キー、`model` に Claude のモデル ID。[^openai-compat]
- xiaozhi-server の `type: openai` プロバイダでそのまま呼べる。2026-09-26、ダミーキーで `401 authentication_error: Invalid Anthropic API Key` が返ることを確認 = エンドポイントとリクエスト形式は通っている。[^smoke]
- 設定は `config/xiaozhi/config.template.yaml` の `LLM.AnthropicLLM`。

# モデル

| 用途 | モデル ID | 備考 |
|---|---|---|
| ランタイム LLM（発話生成・要約） | `claude-haiku-4-5-20251001`（エイリアス `claude-haiku-4-5`） | 2026-09-26 時点で最新の Haiku。$1 / MTok 入力、$5 / MTok 出力[^models] |
| 開発時の Claude Code 本体 | Opus 5.5 | |

- 実行時は日付付き ID で固定する（エイリアスは指す先が変わりうる）。`.env` の `ANTHROPIC_MODEL` で差し替え可能。

# 互換レイヤーの制約

- 公式が「主にモデル能力のテスト・比較用で、多くの用途で長期的・本番向けの解ではない」と明記。[^openai-compat]
- 無視されるフィールド: `frequency_penalty`、`presence_penalty`、`logprobs`、`response_format`、`seed`、`logit_bias`、`user`、`metadata`、`reasoning_effort`、tools の `strict` など。[^openai-compat]
- ストリーミング・function calling は使える（`strict` は無視）。prompt caching は使えない。[^openai-compat]
- **未確認（一次情報なし）**: 新しいモデルは `temperature` と `top_p` の同時指定を拒否するという報告が GitHub issue 上に複数ある。公式 API リファレンスでは明文化を確認できていない。設定では `temperature` だけを指定し `top_p` は書かない。

# 移行方針

- brain で会話ループ・要約を自前で書く段階（M3〜）では、Anthropic ネイティブ Messages API（公式 SDK）を使う。prompt caching と構造化出力が必要になるため。
- Bedrock / Vertex 経由は不採用（[決定 004](/decisions/004-no-bedrock.md)）。

[^openai-compat]: OpenAI SDK compatibility
[^models]: Models overview
[^smoke]: 疑似デバイスでの疎通
