---
type: Decision
title: "001: 頭脳はサーバー側に置く"
description: ファーム改変を最小化し、会話・自律性のロジックはサーバー側に置く。
tags: [decision, adr]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T08:00:00Z }
sources:
  - id: kickoff
    resource: ../../docs/KICKOFF.md
    title: stackchan-brain キックオフ指示書（human:shingo 作成）
    author: human:shingo

---

# 決定
ファームウェアの改変を最小化し、頭脳（判定・生成・記憶）をサーバー側に置く。

# 理由
- 公式ファームの AI エージェント部分は XiaoZhi プロトコルでサーバーに外出しされている（ASR / LLM / TTS はすべてサーバー側）。→ [公式ファーム](/firmware/official-firmware.md)
- ロジックをサーバーに置けば、ESP-IDF のビルド・書き込みなしに反復できる。

# 帰結
- 端末に残すのは反射層のみ（[3層アーキテクチャ](/design/three-layer-architecture.md)）。
