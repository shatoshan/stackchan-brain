"""宛先ゲート（llm-proxy/gate.py）の evals。evals/gate_cases.jsonl を流し、期待と比べる。

    docker compose exec -T brain python /evals/gate_run.py

判定器を 2 つ並べる:
- rule: 名前で呼ばれた／ロボットが直前（20 秒以内）に話した → pass、それ以外 → drop（ベースライン）
- jev:  llm-proxy の /gate/classify（Jev が 429 等で使えない時は「--」）
cases の 1 行: {"id", "expect": ["pass" | "drop" | "backchannel", ...], "state": ゲートの状態ブロブ}
"""
import json
import time
import urllib.error
import urllib.request

URL = "http://llm-proxy:8080/gate/classify"
ROBOT_NAMES = ("スタックチャン", "スタックちゃん", "すたっくちゃん")


def rule(st: dict) -> str:
    if any(n in st["utterance"] for n in ROBOT_NAMES):
        return "pass"
    last = st.get("robot_last_spoke_seconds_ago")
    return "pass" if last is not None and last <= 20 else "drop"


def jev(st: dict) -> dict | None:
    for _ in range(3):
        req = urllib.request.Request(URL, data=json.dumps(st).encode(), headers={"Content-Type": "application/json"})
        res = json.load(urllib.request.urlopen(req, timeout=30))
        if res.get("jev_error") != 429:
            return res if "addressee" in res else None
        time.sleep(5)
    return None


score = {"rule": [0, 0], "jev": [0, 0]}
for line in open("/evals/gate_cases.jsonl"):
    if not line.strip():
        continue
    c = json.loads(line)
    r = rule(c["state"])
    ok = r in c["expect"]
    score["rule"][0] += ok
    score["rule"][1] += 1
    print(f"{'OK ' if ok else 'NG '} rule {c['id']:28} expect={'/'.join(c['expect']):18} got={r}")
    j = jev(c["state"])
    if j is None:
        print(f"--  jev  {c['id']:28} (Jev が使えず)")
        continue
    ok = j["decision"] in c["expect"]
    score["jev"][0] += ok
    score["jev"][1] += 1
    print(f"{'OK ' if ok else 'NG '} jev  {c['id']:28} expect={'/'.join(c['expect']):18} got={j['decision']:11} "
          f"addressee={j['addressee']}({j['addressee_p']}) response={j['response']}({j['response_p']}) {j['latency_s']}s")
print("\n正解数: " + "  ".join(f"{k}={v[0]}/{v[1]}" for k, v in score.items()))
