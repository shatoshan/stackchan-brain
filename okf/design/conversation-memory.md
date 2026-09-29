---
type: Design
title: 会話の記憶
description: セッションが閉じたら brain が会話を日本語で要約して端末ごとに保存し、xiaozhi-server の context_providers と状態ブロブの両方に渡す。
tags: [design, memory, brain, xiaozhi-server]
status: draft
generated: { by: claude-code/opus-5.5, at: 2026-09-29T00:00:00Z }
sources:
  - id: issue
    resource: https://github.com/shatoshan/stackchan-brain/issues/5
    title: "#5 会話要約（記憶）の永続化と状態ブロブへの注入"
  - id: code
    resource: ../../brain/memory.py
    title: brain/memory.py
  - id: ctx-code
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/utils/context_provider.py
    title: core/utils/context_provider.py（server_0.9.6 イメージ内で確認）
  - id: prompt-mgr
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/utils/prompt_manager.py
    title: core/utils/prompt_manager.py（update_context_info、build_enhanced_prompt）
  - id: conn
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/connection.py
    title: core/connection.py（_init_prompt_enhancement）
  - id: mem-short
    resource: https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/788f530/main/xiaozhi-server/core/providers/memory/mem_local_short/mem_local_short.py
    title: core/providers/memory/mem_local_short/mem_local_short.py
  - id: run-0929
    resource: process:claude-code-session-2026-09-29
    title: 2026-09-29 実機のセッションログ 4 件で要約を試した結果
---

> `status: draft`: 実装し、過去の実機ログでの要約と、疑似端末での記憶の往復を確かめた。実機で翌日以降の会話に生きるかは未確認。

# 仕組み

- **いつ作るか**: brain の中継でセッションが閉じた時。セッションログ（`data/brain/sessions/`）からユーザー発話とロボットの発話を取り出し、ユーザー発話が 2 つ以上あれば要約する（`BRAIN_MEMORY_MIN_UTTERANCES`）。ツール表示（`% …`）と brain が差し込んだ指示は除く。[^code]
- **どう作るか**: 「これまでの記憶」と「今回の会話（日付付き）」を LLM（llm-proxy 経由の GPT-6 Luna、宛先ゲート対象外）に渡し、記憶を**書き直させる**（追記ではなく更新）。日本語の箇条書き、800 字以内、項目に日付。音声認識の崩れ・家族同士の会話・テレビが混ざることを伝え、意味が確かでないものは残させない。何も無ければ「なし」→ 保存しない。見出しや崩れた記号が混ざることがあるので、箇条書きの行だけを残す。[^code]
- **どこに置くか**: `data/brain/memory/<MAC>.json`（ローカルのみ）。
- **どう使うか**:
  - xiaozhi-server: `context_providers: [{url: http://brain:8011/context}]`。会話の開始時（接続ごとに 1 回、`_init_prompt_enhancement`）に `device-id` ヘッダ付きで GET し、`{"code": 0, "data": {...}}` の各項目を `- **キー：** 値` の形でシステムプロンプトの `{{ dynamic_context }}` に入れる（タイムアウト 3 秒、失敗しても会話は続く）。[^ctx-code] [^prompt-mgr] [^conn]
  - brain の判定: 状態ブロブの `memory` に同じ文を入れる（→ [状態ブロブ](/design/state-blob.md)）。
- 常時セッション（[決定 012](/decisions/012-firmware-always-on-session.md)）では、閉じてから約 10 秒で開き直す。要約は数秒で終わるので、次のセッションの開始時には更新済みになる（間に合わなければ一つ前の記憶が入る）。

# 内蔵の記憶（mem_local_short）を使わない理由

- xiaozhi-server には LLM で要約してローカルに保存する `mem_local_short` がある（今は `Memory: nomem`）。しかし要約の指示も保存形式（`时空档案`、`身份图谱` などのキー）も中国語で、その JSON がそのままシステムプロンプトに入る。中国語の few-shot でモデルが中国語で返した前例がある（→ [llm-proxy](/services/llm-proxy.md)）。[^mem-short]
- 本体の会話履歴には brain が差し込んだ指示も user 発話として入る。brain 側なら除ける。brain の判定からも同じ記憶を使える。

# 試した結果（2026-09-29、過去の実機ログ 4 件を順に）

- 9/26 夜の短い会話 → 何も記憶しない（正しい）。
- 9/26「今日もただいま」、首を上に向ける依頼 → 2 項目。
- 9/27 夕方 → 「モスバーガーに行き、焼きおにぎりを食べた (9/27)」などが追加され、前の項目は残った。
- 9/27 夜（常時セッション、崩れた発話が多い）→ 「勝負で十対ゼロで負けたらしい」「お風呂に行くよう勧めてくれた」などを追加。
- 誤り: 家族同士の「暇じゃないよ」を相手の発言として「忙しいときは邪魔しない」と記憶した。止めた発話も会話履歴に残す方針（→ [宛先ゲート](/design/addressee-gate.md)）の帰結で、要約では誰に向けた発話か区別できない。[^run-0929]
- 最初の版は日付に要約した日（9/29）を使っていた → 会話の日付を渡すように直した。

# 疑似端末での往復（2026-09-29）

- 1 つ目のセッションで「名前はしんご」「来週の土曜日に京都へ紅葉」「好きな食べ物は湯豆腐」→ 閉じてから 1.6 秒で `- 名前はしんご。- 好きな食べ物は湯豆腐。- 来週土曜日（10/10）に京都へ紅葉を見に行く予定。(9/29)`。
- 2 つ目のセッションで「僕のこと覚えてる？今度の週末の予定も言ってみて」→「もちろんしんごだよね。来週の土曜日、十月十日に京都へ紅葉を見に行く予定だったよ」。システムプロンプトの `<context>` に `- **これまでの会話で覚えていること：**` として入っていた。
- **落とし穴**: xiaozhi-server は接続直後、まず短い「快速提示词」（`prompt` そのまま）をシステムプロンプトにし、記憶などを入れた増強版は初期化スレッドで後から差し替える。接続直後に発話を送った試験では増強版が間に合わず「覚えていない」と答えた。実機はウェイクワード・常時セッションとも発話が届くのは接続から数秒後なので影響は小さいはず。[^conn] [^run-0929]

# 未確定・今後

- 実機で、翌日の会話に記憶が生かされるか。システムプロンプトが長くなりすぎないか。
- 家族ごとの記憶（顔で人を区別する案。LAN 内に限る）。
- 記憶の確認・削除の手段（今は `data/brain/memory/` のファイルを直接見る・消す）。

[^code]: brain/memory.py
[^ctx-code]: core/utils/context_provider.py
[^prompt-mgr]: core/utils/prompt_manager.py
[^conn]: core/connection.py
[^mem-short]: mem_local_short.py
[^run-0929]: 2026-09-29 要約の試験
