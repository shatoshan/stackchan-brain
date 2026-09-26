---
type: Design
title: 状態ブロブ仕様（ドラフト）
description: 直感層（Jev）に毎周期渡す固定フォーマット JSON。フィールドは実装時に確定する。
tags: [design, state, jev]
status: draft
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
---

# 含める予定の項目

| フィールド（仮） | 内容 |
|---|---|
| `now` | 時刻（ISO 8601、ローカル時刻＋曜日） |
| `person` | 人検出（顔検出数・顔サイズ・動体有無など層1で数値化したもの） |
| `seconds_since_last_utterance` | 最終発話からの秒数 |
| `recent_utterances` | 直近3発話の要約 |
| `mood` | 機嫌スコア |
| `utterances_today` | 本日の発話回数 |
| `events` | 外部イベント（option-quants シグナル等、MCP 経由） |
| `memory` | 前回セッションの要約（LLM が生成） |

[^kickoff]

# 未決事項

- 各フィールドの型・単位・欠損時の扱い。
- 人検出値の取得経路（[3層アーキテクチャ](/design/three-layer-architecture.md) の既知の制約を参照）。
- Jev の質問群（`should_speak` 等）の選択肢定義。evals/ に記録と再生の仕組みを作ってから確定し `stable` にする。

[^kickoff]: stackchan-brain キックオフ指示書
