---
type: Decision
title: "011: 常時稼働は USB 給電を前提にする"
description: 長時間の会話セッション・定期撮影・センサによる会話開始を前提とする運用は、StackChan を USB 給電した状態で行う。バッテリー駆動時間と発熱は評価しない。
tags: [decision, adr, power, hardware]
status: stable
generated: { by: claude-code/opus-5.5, at: 2026-09-26T15:21:53Z }
sources:
  - id: suggestion
    resource: process:chat-2026-09-27
    title: 2026-09-27 のユーザー提案（「給電前提と割り切るなら、それを決定として書いてしまう手もある」）
    author: human:shingo
  - id: hw
    resource: /hardware/stackchan.md
    title: StackChan ハードウェア（550mAh バッテリー）
---

# 決定

- 自律発話の運用（長時間の会話セッション、沈黙中の定期撮影、今後のセンサによる会話開始）は **USB 給電した状態で行う**。バッテリー（550mAh）での連続稼働は目標にしない。[^suggestion] [^hw]
- したがって [決定 007](/decisions/007-proactive-speech-path.md) の検証表にあった「バッテリー・発熱は未評価」は、評価しないことにする。発熱で動作が不安定になるなどの問題が出た時だけ調べる。

# 理由

- 会話セッション中はマイク・Wi-Fi・音声処理が常時動き、カメラも定期的に動く。550mAh では実用的な時間持たない見込み。
- 机の上に置いて使う卓上ロボットなので、給電は現実的な前提。

[^suggestion]: 2026-09-27 のユーザー提案
[^hw]: StackChan ハードウェア
