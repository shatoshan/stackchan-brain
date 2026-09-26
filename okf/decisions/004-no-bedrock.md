---
type: Decision
title: "004: Bedrock / Vertex は使わない"
description: Claude は Anthropic API を直接使い、Bedrock / Vertex 経由にはしない。
tags: [decision, adr]
status: deprecated
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo

---

> **deprecated（2026-09-26）**: LLM を Vercel AI Gateway 経由の GPT-6 Luna に切り替えたため前提が変わった。→ [決定 008](/decisions/008-llm-via-vercel-gateway.md)

# 決定
Claude は Anthropic API（まず OpenAI 互換レイヤー、後にネイティブ）を直接呼ぶ。Amazon Bedrock / Google Vertex AI は使わない。

# 理由
- LiteLLM プロキシを挟めば可能だが、料金は同等で、IAM 設定と構成要素が増えるだけ。

# 参照
- [Anthropic API](/external/anthropic-api.md)
