---
type: Design
title: 3層アーキテクチャ（反射 / 直感 / 熟考）
description: 端末の反射、Jev の直感、LLM（GPT-6 Luna）の熟考に役割と時間スケールを分ける全体設計。
tags: [architecture, design, jev, haiku]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo
---

# 層の定義

| 層 | 場所 | 時間スケール | 役割 |
|---|---|---|---|
| 1. 反射 | 端末（ESP32） | ms | 近接・照度・IMU・音量の閾値判定、まばたき、視線追従。既存ファームのまま |
| 2. 直感 | brain（[Jev](/external/jev.md)） | 数百 ms、1〜5 秒周期 | [状態ブロブ](/design/state-blob.md) → `should_speak` / `speech_kind` / `emotion` / `escalate_to_llm` / `attention_target` を確率付きで判定 |
| 3. 熟考 | brain（[GPT-6 Luna](/external/openai-gpt-6-luna.md)） | 秒 | 発話生成、会話要約（記憶）、状態ブロブに戻す文脈の更新 |

[^kickoff]

# 規則

- 発話閾値は機嫌パラメータで動的に変える。
- 定型フレーズ集からの選択は Jev に任せ、LLM は自由生成が必要な時だけ呼ぶ。**Jev に生成させない。LLM を毎秒呼ばない。**
- 会話ログはセッションごとに LLM で要約して永続化し、次回の状態ブロブに含める。
- カメラ等は層1で数値化（顔検出数・顔サイズ・動体有無）してから状態ブロブへ。「何が写っているか」が必要な時だけ LLM（Luna は画像入力可）で 1 フレームを短文化して混ぜる。

[^kickoff]

# 変更履歴

- 2026-09-26: 熟考層の LLM を Claude Haiku から GPT-6 Luna に変更（[決定 008](/decisions/008-llm-via-vercel-gateway.md)）。キックオフ指示書の表記（Haiku）はこれで置き換わる。

# 既知の制約

- 層2・3が決めた発話を端末に届ける経路は、xiaozhi-server に外部 API が無いため未確定。→ [決定 007](/decisions/007-proactive-speech-path.md)
- 層1のセンサ値（近接・IMU 等）を端末からサーバーへ送る仕組みは、現行ファームの XiaoZhi プロトコル上には見当たらない（端末→サーバーの型は hello/listen/abort/mcp/iot 等のみ）。M3 までに要調査。→ [XiaoZhi プロトコル](/protocol/xiaozhi-protocol.md)

[^kickoff]: stackchan-brain キックオフ指示書
