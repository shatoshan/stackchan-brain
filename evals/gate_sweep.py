"""宛先ゲートの閾値（ロボット宛ての確率の下限）を動かして、ラベル付きケースの正解数と誤りの内訳を比べる。

    docker compose exec -T brain python /evals/gate_sweep.py                  # 保存済みの Jev の答えだけで計算
    docker compose exec -T brain python /evals/gate_sweep.py --runs 3         # 1 ケース 3 回分の答えが揃うまで Jev を呼ぶ
    docker compose exec -T brain python /evals/gate_sweep.py --detail 0.8     # その閾値での誤りと揺れを一覧

- Jev の答えは一度取ったら /data/evals/gate_answers.jsonl に貯め、閾値だけを変えて再計算する（Jev を何度も呼ばない）
- 判定規則は llm-proxy の gate.decide_from_answers を /gate/decide 経由で使う（規則をここに複製しない）
- 誤りの種類: 聞き流し = 通すべき発話を止めた / 割り込み = 黙るべき発話に返事・相槌をした
- ケースが少ないうちは、正解数だけで閾値を決めない（誤りの内訳とケース数を一緒に見る）
ケースの形式は evals/gate_label.py（ラベル付き、answers あり）と evals/gate_cases.jsonl（answers なし）の両方を読める。
"""
import argparse
import json
import os
import statistics
import time
import urllib.request
from collections import Counter

PROXY = os.environ.get("GATE_PROXY_URL", "http://llm-proxy:8080")
CACHE = "/data/evals/gate_answers.jsonl"


def post(path: str, body: dict, timeout: float = 30) -> dict:
    req = urllib.request.Request(PROXY + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def load_cases(paths: list[str]) -> list[dict]:
    cases = []
    for path in paths:
        if not os.path.exists(path):
            print(f"（{path} が無いので飛ばす）")
            continue
        for line in open(path, encoding="utf-8"):
            if line.strip():
                cases.append(json.loads(line))
    return cases


def load_cache() -> dict[str, list]:
    pool: dict[str, list] = {}
    if os.path.exists(CACHE):
        for line in open(CACHE, encoding="utf-8"):
            if line.strip():
                c = json.loads(line)
                pool.setdefault(c["id"], []).append(c["answers"])
    return pool


def fetch(case: dict, need: int, pool: list) -> None:
    """答えが need 個になるまで Jev（/gate/classify）を呼んで貯める。"""
    while len(pool) < need:
        res = None
        for _ in range(3):
            res = post("/gate/classify", case["state"])
            if res.get("raw") or res.get("jev_error") != 429:
                break
            time.sleep(5)
        if not res or not res.get("raw"):
            print(f"   Jev が使えず: {case['id']} {res.get('reason') if res else ''}")
            return
        pool.append(res["raw"])
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": case["id"], "t": round(time.time(), 3), "answers": res["raw"]}, ensure_ascii=False) + "\n")


def error_kind(expect: list[str], got: str) -> str | None:
    if got in expect:
        return None
    return "聞き流し" if "pass" in expect else "割り込み"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=["/data/evals/gate_labeled.jsonl", "/evals/gate_cases.jsonl"])
    ap.add_argument("--runs", type=int, default=0, help="1 ケースあたりの Jev の答えがこの数になるまで呼ぶ（0 なら呼ばない）")
    ap.add_argument("--thresholds", type=float, nargs="+", default=[round(0.5 + 0.05 * i, 2) for i in range(10)])
    ap.add_argument("--detail", type=float, help="この閾値での誤りと、実行ごとに判定が割れたケースを一覧する")
    args = ap.parse_args()

    cases = load_cases(args.cases)
    cache = load_cache()
    pools = {}
    for c in cases:
        pools[c["id"]] = list(c.get("answers") or []) + cache.get(c["id"], [])
        if args.runs:
            fetch(c, args.runs, pools[c["id"]])
    usable = [c for c in cases if pools[c["id"]]]
    runs = [len(pools[c["id"]]) for c in usable]
    print(f"ケース {len(usable)} 件（答えなし {len(cases) - len(usable)} 件）、答えは 1 ケース {min(runs, default=0)}〜{max(runs, default=0)} 回分")
    expects = Counter("通す" if "pass" in c["expect"] else "黙る/相槌" for c in usable)
    print("内訳: " + "  ".join(f"{k} {v}" for k, v in expects.items()) + "\n")

    decided: dict[tuple, list[str]] = {}
    for th in sorted(set(args.thresholds + ([args.detail] if args.detail is not None else []))):
        for c in usable:
            decided[(th, c["id"])] = [post("/gate/decide", {"answers": a, "utterance": c["state"]["utterance"], "robot_min": th})["decision"]
                                      for a in pools[c["id"]]]

    print("閾値   正解(全回の平均)  多数決   聞き流し  割り込み  判定が割れたケース")
    for th in sorted(args.thresholds):
        acc, maj_ok, kinds, split = [], 0, Counter(), 0
        for c in usable:
            ds = decided[(th, c["id"])]
            acc.append(sum(d in c["expect"] for d in ds) / len(ds))
            maj = Counter(ds).most_common(1)[0][0]
            maj_ok += maj in c["expect"]
            if k := error_kind(c["expect"], maj):
                kinds[k] += 1
            split += len(set(ds)) > 1
        print(f"{th:.2f}   {sum(acc):5.1f}/{len(usable):<3}        {maj_ok:3}/{len(usable):<3}  {kinds['聞き流し']:6}    {kinds['割り込み']:6}    {split}")

    if args.detail is not None:
        th = args.detail
        print(f"\n--- 閾値 {th:.2f} の誤り（多数決）と揺れ ---")
        for c in usable:
            ds = decided[(th, c["id"])]
            maj = Counter(ds).most_common(1)[0][0]
            ps = [a["addressee"]["probabilities"].get("robot", 0.0) for a in pools[c["id"]]]
            kind = error_kind(c["expect"], maj)
            if kind or len(set(ds)) > 1:
                spread = f"{min(ps):.2f}〜{max(ps):.2f}" if len(ps) > 1 else f"{ps[0]:.2f}"
                print(f"{kind or '揺れ':6} expect={'/'.join(c['expect']):16} got={'/'.join(ds):24} robot={spread:10} 「{c['state']['utterance'][:30]}」")
        multi = [c for c in usable if len(pools[c["id"]]) > 1]
        if multi:
            spreads = [max(p) - min(p) for p in ([a["addressee"]["probabilities"].get("robot", 0.0) for a in pools[c["id"]]] for c in multi)]
            print(f"\nロボット宛ての確率の揺れ（同じ発話を複数回、{len(multi)} 件）: 平均 {statistics.mean(spreads):.2f}、最大 {max(spreads):.2f}")


if __name__ == "__main__":
    main()
