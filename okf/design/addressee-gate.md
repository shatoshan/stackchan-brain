---
type: Design
title: 宛先ゲート（LLM を呼ぶ前に Jev で発話を分類する）
description: xiaozhi-server がユーザー発話で LLM を呼ぶ直前に llm-proxy で Jev に「誰宛てか・どんな返事が要るか」を分類させ、LLM を呼ばずに済むものは相槌か無応答で返す。
tags: [design, jev, llm-proxy, privacy, cost]
status: draft
stale_after: 2026-12-27T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-27T07:09:53Z }
sources:
  - id: code
    resource: ../../llm-proxy/gate.py
    title: llm-proxy/gate.py
  - id: issue
    resource: https://github.com/shatoshan/stackchan-brain/issues/2
    title: GitHub #2 Jev による発話の宛先ゲート
  - id: request
    resource: process:chat-2026-09-27
    title: 2026-09-27 のユーザー要望（Jev に流すのは可、それ以外のモデルはコスト的に制限）
    author: human:shingo
  - id: run-0927
    resource: process:claude-code-session-2026-09-27
    title: 2026-09-27 の疑似デバイス試験と evals
---

> `status: draft` の理由: evals（14 件）では全問正解だが、閾値をこのケースに合わせて決めたばかりで、実機の記録での確認がまだ。

# 目的

会話セッション中の周囲の音声（家族の会話、テレビ）も ASR で文字起こしされ、そのまま LLM（GPT-6 Luna）が呼ばれる。Jev に流すのは許容し、それ以外のモデルへのコストと流出を抑える。[^request] [^issue]

# 置き場所

- **llm-proxy。** xiaozhi-server が ASR の結果で LLM を呼ぶ直前の経路で、止められるのはここだけ。brain の中継は、LLM 呼び出しより前に文字起こしを見られない（stt は LLM 呼び出しとほぼ同時に流れる）。
- 対象: `/chat/completions` で最後のメッセージが user のもの。ツール結果の続き、画像説明（VLLM）、brain が差し込む llm モードの指示（`（ロボットから話しかける場面です` で始まる）、brain 自身の LLM 代替判定（ヘッダ `X-StackChan-Source: brain`、または `response_format` 付き）は対象外。[^code]
  - 最初は brain の代替判定の依頼（「State of a small companion desk robot…」）までゲートにかけていた。実機試験の記録で発覚し、ヘッダで除外した。
- ASR 由来の user メッセージは `{"content": "...", "language": "ja", "emotion": "😶"}` という JSON 文字列。疑似デバイスのテキストは素の文字列。両方扱う。[^code]

# 状態と質問

- 状態: `utterance`、`recent_conversation`（リクエスト内の会話履歴から最大 6 件）、`robot_started_talking_on_its_own_seconds_ago`・`robot_last_spoke_seconds_ago`・`camera_faces_in_view`（brain の `GET /sessions` から）。
- 質問: `addressee`（robot / people / media / self_talk / unclear）、`response`（reply / backchannel / none / action）。[^code]

# 振る舞い

| 条件 | 動き |
|---|---|
| ロボット宛ての確率 < 0.5（`LLM_GATE_ROBOT_MIN`）かつ 人・テレビ・独り言の合計 > 不明 | LLM を呼ばず空の応答（xiaozhi-server は `tts start`→`stop` だけで何も喋らない） |
| addressee が robot で response が backchannel・none（≥ 0.6） | LLM を呼ばず相槌（「うんうん。」等）を返す |
| それ以外（robot で reply・action、unclear 等） | LLM へそのまま |
| Jev が使えない（429 等） | LLM へそのまま（fail-open） |

- 空の応答・相槌だけの応答を xiaozhi-server が問題なく扱うことは、偽の LLM を立てて確認した（空: 音声 0 フレーム、相槌: 読み上げ）。[^run-0927]
- 判定は `data/llm-proxy/gate/YYYYMMDD.jsonl` に記録。`LLM_GATE_ENABLED=0` で無効。

# 実機試験（2026-09-27）

- BYOK が効く前（Jev 429）の家族の会話 3 件（日曜日の話、抱き枕の話）は fail-open で LLM に渡り、ロボットが会話に割り込んだ。同じ 3 件を BYOK 後の Jev で分類し直すと、3 件とも人宛て（ロボット宛て 0.21〜0.32）で止められた。実際の会話で家族の名前を含むので、公開の evals には入れない。[^run-0927]
- BYOK 後に届いた発話は「左を向いて」「元に戻れ」などロボット宛ての 4 件で、すべて通した（ロボット宛て 0.74〜1.00、判定 0.33〜0.43 秒）。
- テレビの音声は ASR の記録に出てこず、ゲートまで届いていない。Jev が使える状態で人同士の会話・テレビを試すのは未実施。

# Jev の呼び先

- llm-proxy の `jev.py` が Jev を呼ぶ。`JEV_BACKEND=gateway`（Vercel AI Gateway）と `typesafe`（TypeSafe 直接）を切り替えられる。brain の判定ループも llm-proxy の `/jev/evaluate` 経由になった。→ [Jev](/external/jev.md)

# 評価

- `evals/gate_cases.jsonl`（14 件）と `docker compose exec -T brain python /evals/gate_run.py`。比較用のルール判定（名前で呼ばれた／ロボットが 20 秒以内に話した → pass）を並べる。
- 2026-09-27（BYOK 後）: **jev 14/14**、rule 10/14。
  - 最初の判定規則（最有力の分類が人・テレビ・独り言で確率 ≥ 0.6、かつ response が action でない時だけ止める）では 12/14 だった。落としたのは (1)「お母さん、醤油取って」＝人宛て 0.81 だが、人への頼みごとが response=action と分類され通ってしまった、(2) ロボットの発話直後のテレビ＝ロボット宛て 0.43・テレビ 0.43 と拮抗し、0.6 に届かなかった。
  - ロボット宛ての確率で分けるように変更。通すべきケースはロボット宛て 0.83〜1.00、止めるべきケースは 0.01〜0.23（拮抗した 1 件だけ 0.43）だったので、境を 0.5 にした。action はロボット宛ての時だけ意味を持つ。
  - 14 件に合わせて決めた暫定値。止めすぎるとロボット宛ての言葉を聞き流し、通しすぎるとテレビに返事をする。実機の記録（`data/llm-proxy/gate/`）で調整する。
- 以前の記録（rule のみ）: 10/14。ルールが落とすのは、名前なしの端末操作（「右を向いて」）、ロボットの発話直後の短い相槌、家族の会話にロボットの名前が出る場合、ロボットの発話直後のテレビ音声。[^run-0927]
- 遅延: ゲートは LLM 呼び出しの前に直列で入るので、Jev の応答時間がそのまま応答遅延に加わる。evals では 0.3〜1.0 秒（再試行が入ると 2 秒程度）。

[^code]: llm-proxy/gate.py
[^issue]: GitHub #2
[^request]: 2026-09-27 のユーザー要望
[^run-0927]: 2026-09-27 の疑似デバイス試験と evals
