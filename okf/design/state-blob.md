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

# 現在の実装（`brain/judge.py` の `build_state`、2026-09-26）

```json
{"now": "2026-09-26 21:29 (土)", "session_age_seconds": 60, "seconds_since_user_spoke": 33,
 "seconds_since_robot_spoke": 26, "recent_conversation": ["user: …", "robot: …"],
 "proactive_utterances_this_session": 0, "mood": 0.6,
 "person": {"faces_in_view": 1, "largest_face_width_ratio": 0.31, "seconds_face_visible": 20,
            "seconds_since_face_seen": 0, "checked_seconds_ago": 3}}
```

- `recent_conversation` は中継が記録した直近 6 発話（古い順）。ロボットの発話は 1 回の返答をまとめて 1 件。
- `person` はカメラの顔検出（→ [カメラで在席を知る](/design/camera-presence.md)）。確認していない / 30 秒以上古い時は null。
- センサ値・外部イベント・前回セッションの要約はまだ無い。

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
