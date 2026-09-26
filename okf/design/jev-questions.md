---
type: Design
title: 直感層の質問設計（Jev に何を聞くか）
description: 自分から話しかけるかを Jev に判定させる質問の形。「話すべき確率」ではなく「状況の分類」を聞く理由と、ルールとの分担。
tags: [design, jev, judge, evals]
status: draft
stale_after: 2026-12-26T00:00:00Z
generated: { by: claude-code/opus-5.5, at: 2026-09-26T12:36:16Z }
sources:
  - id: code
    resource: ../../brain/judge.py
    title: brain/judge.py
  - id: evals
    resource: ../../evals/cases.jsonl
    title: evals/cases.jsonl
  - id: m3-judge
    resource: process:claude-code-session-2026-09-26
    title: 2026-09-26 M3 ステップ3 判定ループの試験（evals と実機）
---

> `status: draft` の理由: evals が 6 ケースしかなく、Jev の混雑で Jev 側の評価がほとんど取れていない。閾値も暫定。

# 分担

| 担当 | 何を決めるか |
|---|---|
| ルール（brain） | うるささの上限。ユーザー / ロボットの発話から 20 秒は黙る、自発発話の間隔 60 秒以上、1 セッション 4 回まで、聞き取り状態のときだけ |
| Jev（直感） | 今の状況の分類、話し方の種類、定型フレーズ、表情。確率付き |
| 閾値（brain） | 話してよい状況の確率の合計 ≥ 0.6 ＋ 0.1×このセッションの自発回数 − 0.2×(機嫌 − 0.5) |
| LLM（熟考） | 定型フレーズ以外の発話文の生成（xiaozhi-server の LLM 経路へ `llm` モードで差し込む） |

[^code]

# 質問（`brain/judge.py` の `QUESTIONS`）

| 名前 | 型 | 選択肢 |
|---|---|---|
| `situation` | choice | `pause_in_conversation`、`just_woken_no_talk`（話してよい）／`person_left_or_busy`、`robot_ignored`（黙る） |
| `speech_kind` | choice | `follow_up`、`question`、`time_remark`、`fixed_phrase` |
| `phrase` | choice | 定型フレーズ 5 種（`fixed_phrase` の時だけ使う） |
| `emotion` | choice | `neutral`、`happy`、`doubtful`、`sad`（StackChan の表情名。`sleepy` は眠りポーズに入るので使わない） |

[^code]

# 「話すべき確率」を直接聞かない理由（2026-09-26 の比較）

- boolean で「今話すべきか（うるさくしないように）」と聞くと、LLM（Luna、reasoning none）は 4 ケースすべて 0.08 を返し、状況を区別しなかった。[^m3-judge]
- 「相手は歓迎するか」に言い換えると、LLM は「お風呂に行った」場面でも 0.82 を返した。[^m3-judge]
- 状況を 4 択で分類させると、LLM は 4 ケースすべて正解。Jev も取れた 1 件は正解（`robot_ignored`、話してよい確率 0.09）。[^m3-judge]
- LLM の分類結果は確率として較正されていないので、フォールバック時は話してよい分類なら 1.0、それ以外は 0.0 として扱う。[^code]

# 実機での結果（2026-09-26）

- ロボットの質問に 27 秒返事がない場面で、Jev は `pause_in_conversation`（0.95）と判定し、happy の表情で話題の続きを言った。「ちょっと出かけてくる」の後は `person_left_or_busy` と判定し、話しかけなかった。人間が期待どおりと確認。[^m3-judge]
- `person_left_or_busy` / `robot_ignored` と判定したら、ユーザーが次に話すまでそのセッションの判定を止める（無駄な呼び出しを防ぐ）。[^code]

# 評価

- `evals/cases.jsonl` に状態ブロブと期待（話す / 黙る）を貯め、`docker compose exec -T brain python /evals/run.py` で現行ロジックを流す。[^evals]
- 2026-09-26 時点: 6 ケース、LLM 判定で全問正解。Jev は 429 でほぼ未評価。

[^code]: brain/judge.py
[^evals]: evals/cases.jsonl
[^m3-judge]: 2026-09-26 M3 ステップ3 試験
