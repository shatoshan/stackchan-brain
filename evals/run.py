"""evals/cases.jsonl を brain の現在の判定ロジック（judge.py）で流し、期待と比べる。

    docker compose exec -T brain python /evals/run.py            # Jev と LLM の両方
    docker compose exec -T brain python /evals/run.py --llm-only # Jev が混んでいる時
    docker compose exec -T brain python /evals/run.py --cases /data/evals/labeled.jsonl  # 実機からラベル付けしたセット（ローカル）

cases.jsonl の 1 行: {"id", "expect_speak": bool, "note", "state": 状態ブロブ}
閾値は mood と proactive_utterances_this_session から judge と同じ式で出す。
"""
import argparse
import asyncio
import json
import sys

sys.path.insert(0, "/app")
from judge import BASE_THRESHOLD, Judge  # noqa: E402
from aiohttp import ClientSession, ClientTimeout  # noqa: E402


async def main(llm_only: bool, cases_path: str) -> int:
    cases = [json.loads(l) for l in open(cases_path) if l.strip()]
    judge = Judge(relay=None, record_dir=None)
    judge.client = ClientSession(timeout=ClientTimeout(total=30))
    failures = 0
    try:
        for c in cases:
            st = c["state"]
            threshold = min(0.95, BASE_THRESHOLD + 0.1 * st.get("proactive_utterances_this_session", 0) - 0.2 * (st.get("mood", 0.6) - 0.5))
            results = {}
            if not llm_only:
                for _ in range(3):
                    try:
                        results["jev"] = await judge._ask_jev(st)
                        break
                    except RuntimeError as e:
                        if "429" not in str(e):
                            raise
                        await asyncio.sleep(5)
            results["llm"] = await judge._ask_llm(st)
            for source, a in results.items():
                speak = a["should_speak"] >= threshold
                ok = speak == c["expect_speak"]
                failures += not ok
                print(f"{'OK ' if ok else 'NG '} {source:3} {c['id']:32} expect={'speak' if c['expect_speak'] else 'quiet':5} "
                      f"p={a['should_speak']:.2f} th={threshold:.2f} situation={a['situation']} kind={a['speech_kind']}")
            if not llm_only and "jev" not in results:
                print(f"--  jev {c['id']:32} (429 で取れず)")
    finally:
        await judge.client.close()
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--llm-only", action="store_true")
    p.add_argument("--cases", default="/evals/cases.jsonl")
    a = p.parse_args()
    raise SystemExit(asyncio.run(main(a.llm_only, a.cases)))
