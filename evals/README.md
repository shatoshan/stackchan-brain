# evals

直感層（brain の判定）の回帰テスト。

- `cases.jsonl` — 状態ブロブと期待（話す / 黙る）。実機の会話記録（`data/brain/judgments/`、`data/brain/sessions/`）から、判断が問題になった場面を切り出して足していく
- `run.py` — 現在の `brain/judge.py` の質問で全ケースを判定し、期待と比べる

```bash
docker compose exec -T brain python /evals/run.py
docker compose exec -T brain python /evals/run.py --llm-only   # Jev が 429 の時
```

判定の考え方は `okf/design/jev-questions.md`。

## 宛先ゲート（llm-proxy）

- `gate_cases.jsonl` + `gate_run.py` — 公開用の 14 件で、現在の規則とルール判定を比べる
- `gate_label.py`（ホストで実行）— 実機のゲート記録（`data/llm-proxy/gate/`）に正解を付けて `data/brain/evals/gate_labeled.jsonl` に貯める。記録時の Jev の答えも残す
- `gate_sweep.py` — 閾値を動かして正解数と誤りの内訳（聞き流し / 割り込み）を比べる。Jev の答えは `data/brain/evals/gate_answers.jsonl` に貯め、閾値だけを変えて再計算する

```bash
python3 evals/gate_label.py
docker compose exec -T brain python /evals/gate_sweep.py                    # 貯めた答えだけで計算（Jev を呼ばない）
docker compose exec -T brain python /evals/gate_sweep.py --runs 3 --detail 0.8   # 3 回分揃える。0.8 での誤りと揺れ
```

実際の会話を含むラベル付きデータはローカル（`data/`）のみ。公開してよい代表例だけを匿名化して `gate_cases.jsonl` に移す。
