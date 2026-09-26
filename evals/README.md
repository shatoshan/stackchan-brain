# evals

直感層（brain の判定）の回帰テスト。

- `cases.jsonl` — 状態ブロブと期待（話す / 黙る）。実機の会話記録（`data/brain/judgments/`、`data/brain/sessions/`）から、判断が問題になった場面を切り出して足していく
- `run.py` — 現在の `brain/judge.py` の質問で全ケースを判定し、期待と比べる

```bash
docker compose exec -T brain python /evals/run.py
docker compose exec -T brain python /evals/run.py --llm-only   # Jev が 429 の時
```

判定の考え方は `okf/design/jev-questions.md`。
