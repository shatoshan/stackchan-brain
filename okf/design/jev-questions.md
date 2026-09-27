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
| `situation` | choice | `pause_in_conversation`、`just_woken_no_talk`、`person_arrived`（話してよい）／`person_left_or_busy`、`robot_ignored`（黙る） |
| `speech_kind` | choice | `follow_up`、`question`、`time_remark`、`fixed_phrase` |
| `phrase` | choice | 定型フレーズ 4 種（`fixed_phrase` の時だけ使う） |
| `emotion` | choice | `neutral`、`happy`、`doubtful`、`sad`（StackChan の表情名。`sleepy` は眠りポーズに入るので使わない） |

- 首の見回しは Jev に聞かない（ルール）。`attention` 質問は試したが、実機で `look_around` が一度も選ばれず、話さない判定の場面もほとんど来なかったので外した。→ [brain](/services/brain.md)

[^code]

# 「話すべき確率」を直接聞かない理由（2026-09-26 の比較）

- boolean で「今話すべきか（うるさくしないように）」と聞くと、LLM（Luna、reasoning none）は 4 ケースすべて 0.08 を返し、状況を区別しなかった。[^m3-judge]
- 「相手は歓迎するか」に言い換えると、LLM は「お風呂に行った」場面でも 0.82 を返した。[^m3-judge]
- 状況を 4 択で分類させると、LLM は 4 ケースすべて正解。Jev も取れた 1 件は正解（`robot_ignored`、話してよい確率 0.09）。[^m3-judge]
- LLM の分類結果は確率として較正されていないので、フォールバック時は話してよい分類なら 1.0、それ以外は 0.0 として扱う。[^code]

# 実機での結果（2026-09-26）

- ロボットの質問に 27 秒返事がない場面で、Jev は `pause_in_conversation`（0.95）と判定し、happy の表情で話題の続きを言った。「ちょっと出かけてくる」の後は `person_left_or_busy` と判定し、話しかけなかった。人間が期待どおりと確認。[^m3-judge]
- `person_left_or_busy` / `robot_ignored` と判定したら、ユーザーが次に話すまでそのセッションの判定を止める（無駄な呼び出しを防ぐ）。[^code]

# カメラ情報の扱い（2026-09-26）

- 状態ブロブに `person`（カメラの顔検出）を入れ、状況に `person_arrived` を追加した。
- **自発発話の質**（#6、2026-09-27）: 実機の自発発話 35 件を見直すと、(1) follow_up が自分の直前の発言をなぞる・言い直す・反省する（「今度こそ左を向いたよ」「さっきの返し少し気取ってたね」）、(2) question が毎回「今日はどんな一日だった？」、(3) 定型の「ねえねえ。」だけで終わりほぼ返事が無い、(4) 話しかける時に LLM がツールを呼び、カメラの説明や中国語のタイムアウト文（「工具调用请求超时」）を読み上げる、が目立った。対処:
  - 指示文に共通の注意（許可を求めない、自分の直前の発言をなぞる・言い直す・反省しない、一言か二言）。follow_up は「相手が最後に話していた話題に、まだ言っていない新しい角度（素朴な質問、感想、関連する小さな話）で」。
  - 同じ端末で最近自分から言ったこと 5 件（`BRAIN_RECENT_PROACTIVE`、セッションをまたいで brain が覚える）を指示に添え、同じ内容・同じ質問を避けさせる。
  - 「ねえねえ。」を定型フレーズから外した。
  - llm-proxy が brain の指示には `tool_choice: none` を付ける（→ [llm-proxy](/services/llm-proxy.md)）。
  - 疑似端末で確認: 「新しいプロジェクトで緊張してる」の後、follow_up 3 回とも直前の励ましを繰り返さず新しい質問（「どんな担当になりそう？」など）、question は「今日はどんな一日だった？」を避けた。直前の指示文では 2 回中 1 回、直前の助言を言い換えていた。
- `person_arrived` の時は定型フレーズを使わず、LLM に「カメラで相手が戻ってきたのが見えた、おかえり等の一言」を指示する。定型文（verbatim）だと「戻ってきた」ことが xiaozhi-server の会話履歴に残らず、実機で相手の返事に「いってらっしゃい」と出かける前の文脈で答えてしまった。
- 最初の説明文では、LLM は「出かけてくる」と言った後に顔が映っても `person_left_or_busy` と判定した。「以前出かけると言っていても、今顔が見えるなら戻ってきた」「離れた＝カメラにも誰もいない」と明記して解決。[^evals]

# 評価

- 実機の判定はすべて `data/brain/judgments/YYYYMMDD.jsonl` に ID 付きで記録され、カメラの確認結果が新しければその時の写真も `images/` に保存される。`python3 evals/label.py`（`--open` で写真表示）で「話す / 黙る」のラベルを付けると `data/brain/evals/labeled.jsonl` に貯まり、`run.py --cases /data/evals/labeled.jsonl` で流せる。実際の会話と写真を含むのでローカルのみ（公開リポジトリには入れない）。
- 同じセッションで状況と直近の会話が前回と同じ判定は、ラベル付けの時に間引く。
- `run.py` はルールだけの判定器（秒数とカメラのみ、会話の中身を見ない）を必ず並べる。2026-09-27 時点で rule 6/8、llm 8/8、**jev 8/8**（BYOK 後、初めて Jev で評価。話すべき場面の p は 0.91〜0.96、黙るべき場面は 0.00〜0.07）。rule が落とすのは「お風呂に行く」「出かけてくる」のように会話の中身でしか分からない 2 件。ケースを増やすたびに、ルールで取れない場面を Jev / LLM が取れているかをこの差で見る。

- `evals/cases.jsonl` に状態ブロブと期待（話す / 黙る）を貯め、`docker compose exec -T brain python /evals/run.py` で現行ロジックを流す。[^evals]
- 2026-09-26 時点: 8 ケース（カメラ 2 件を含む）、LLM 判定で全問正解。Jev は 429 でほぼ未評価。

[^code]: brain/judge.py
[^evals]: evals/cases.jsonl
[^m3-judge]: 2026-09-26 M3 ステップ3 試験
