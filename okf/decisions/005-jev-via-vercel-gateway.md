---
type: Decision
title: "005: Jev は Vercel AI Gateway 経由で呼ぶ"
description: TypeSafe 本家ではなく Vercel AI Gateway 経由で Jev を使う。
tags: [decision, adr]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
  - id: v-typesafe
    resource: https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe
    title: Vercel AI Gateway — TypeSafe-compatible API
---

# 決定
Jev は Vercel AI Gateway（モデル ID `typesafe-ai/jev`）経由で呼ぶ。

# 理由
- TypeSafe 本家のコンソールが受付停止中（キックオフ時点の人間の確認。2026-09-26 のエージェント調査では一次情報で確認できず、console は 403）。
- Vercel の TypeSafe 互換 API は、公式クライアントのベース URL とキーを差し替えるだけで使える。[^v-typesafe]

# 訂正（2026-09-26）
- キックオフ時の理由「providerMetadata で確率を取れる」は不正確。Gateway では確率はレスポンスの `answers` に入る。結論（Vercel 経由）は変わらない。→ [Jev](/external/jev.md)

[^v-typesafe]: Vercel AI Gateway — TypeSafe-compatible API
