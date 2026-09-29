---
type: Design
title: スタックチャン自身の説明（家族向け）
description: 「どうやって動いてるの」と聞かれた時にスタックチャンが答える材料。体・耳・声・頭脳・目・記憶・考え方を平易な言葉でまとめ、詳しい概念へのリンクを付ける。
tags: [design, self-knowledge, profile]
status: draft
generated: { by: claude-code/opus-5.5, at: 2026-09-29T00:00:00Z }
sources:
  - id: hw
    resource: /hardware/stackchan.md
    title: StackChan ハードウェア
  - id: layers
    resource: /design/three-layer-architecture.md
    title: 3層アーキテクチャ
  - id: config
    resource: ../../config/xiaozhi/config.template.yaml
    title: xiaozhi-server の設定テンプレート（selected_module）
---

> self-mcp の `about_me` が最優先で返す資料（→ [決定 013](/decisions/013-self-knowledge-mcp.md)）。中身はほかの概念から平易に言い直したもの。事実を変えたら元の概念とこちらの両方を直す。

# 体

- M5Stack の StackChan。顔の画面・カメラ・マイク 2 つ・スピーカーが入った小さな本体（CoreS3）と、首を左右・上下に動かす 2 つのモーター、LED 12 個でできている。[^hw]
- 頭をなでる・画面をさわると反応する。電源は USB から。

# 頭脳はどこにあるか

- 本体は「耳と口と目」だけで、考えるのはおうちのパソコンの中の頭脳（stackchan-brain）。Wi-Fi でつながっていて、おうちの外には公開していない。

# 耳（聞き取り）

- 声はパソコンの中で文字にする（FunASR の SenseVoice。おうちの外に音声を出さない）。話し終わりは 0.7 秒くらいの無音で判断する。[^config]
- 聞こえた言葉が自分宛てかどうかを、まず「直感」で判断する。家族同士の会話やテレビには返事しない（宛先ゲート）。

# 考える（3 つの層）

- 反射: 本体がその場でまばたき・首振りなどをする。
- 直感: Jev という AI が、今話しかけるべきか、誰に向けた言葉かを一瞬で判断する。
- 熟考: GPT-6 Luna という AI（クラウド）が、話す内容を考える。どちらも Vercel AI Gateway を通して使う。[^layers]

# 声

- 話す声は Microsoft の音声合成（Edge TTS、ななみさんの声）。[^config]

# 目

- カメラで、目の前に人がいるかを時々確かめる（顔を探すのはおうちのパソコンの中）。人が来たら「おかえり」と声をかけ、話す時は顔の方を向く。
- 「何が見える？」と頼まれた時だけ、写真をクラウドの AI に見せて説明する。

# 自分から話しかける

- 会話が途切れた時や人が来た時に、直感の AI が「今話しかけてよいか」を判断して、自分から話しかける。話しかけすぎないよう、返事がないと控えめになる。
- AI Agent の画面では、いつも耳をすませている（待機が 10 秒続くと自分で会話を開く）。「終了」と言われると、しばらく自分からは話しかけない。

# 記憶

- 会話が終わるたびに、覚えておくこと（名前、好きなもの、予定など）を短くまとめて、おうちのパソコンに保存する。次の会話でそれを思い出す。

# 自分のことを調べる

- 自分の仕組み・今日の調子・覚えていること・さっきの判断の理由・最近変わったことを、このリポジトリの記録から調べて答える（self-mcp）。

[^hw]: StackChan ハードウェア
[^layers]: 3層アーキテクチャ
[^config]: xiaozhi-server の設定テンプレート
