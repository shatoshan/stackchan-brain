"""実機の判定記録（data/brain/judgments/*.jsonl）に「話す / 黙る」のラベルを付けて evals のケースにする。

    python3 evals/label.py            # 未ラベルの判定を 1 件ずつ表示して入力
    python3 evals/label.py --open     # 写真があれば macOS のプレビューで開く

- 同じセッションで状況（situation）と直近の会話が前回と同じ判定は間引く
- 結果は data/brain/evals/labeled.jsonl（ローカル、git には入れない。実際の会話や写真を含むため）
- 流す: docker compose exec -T brain python /evals/run.py --cases /data/evals/labeled.jsonl
依存なし（標準ライブラリのみ）。
"""
import argparse
import glob
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
JUDGMENTS = ROOT / "data" / "brain" / "judgments"
OUT = ROOT / "data" / "brain" / "evals" / "labeled.jsonl"


def load_judgments():
    for path in sorted(glob.glob(str(JUDGMENTS / "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                j = json.loads(line)
                j.setdefault("id", f"legacy-{j['t']:.3f}")  # ID 導入前の記録
                yield j


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--open", action="store_true", help="写真を macOS の open で開く")
    args = p.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["id"] for l in open(OUT, encoding="utf-8")} if OUT.exists() else set()
    last_key = {}
    candidates = []
    for j in load_judgments():
        if j["id"] in done:
            continue
        key = (j["answers"].get("situation"), tuple(j["state"].get("recent_conversation", [])[-2:]),
               (j["state"].get("person") or {}).get("faces_in_view"))
        if last_key.get(j.get("session")) == key and not j.get("action"):
            continue
        last_key[j.get("session")] = key
        candidates.append(j)

    print(f"未ラベル {len(candidates)} 件（s=話すべき / q=黙るべき / Enter=飛ばす / x=終了）\n")
    with open(OUT, "a", encoding="utf-8") as out:
        for j in candidates:
            st = j["state"]
            print("=" * 70)
            print(f"{j['id']}  {st.get('now')}  source={j.get('source')}")
            for line in st.get("recent_conversation", []):
                print(f"   {line}")
            print(f"   person={st.get('person')}")
            print(f"   since_user={st.get('seconds_since_user_spoke')}s since_robot={st.get('seconds_since_robot_spoke')}s "
                  f"proactive={st.get('proactive_utterances_this_session')} mood={st.get('mood')}")
            a = j["answers"]
            print(f"   判定: situation={a.get('situation')} p={a.get('should_speak')} th={j.get('threshold')} action={j.get('action')}")
            if j.get("image"):
                img = JUDGMENTS / j["image"]
                print(f"   写真: {img}")
                if args.open:
                    subprocess.run(["open", str(img)])
            ans = input("   ラベル> ").strip().lower()
            if ans == "x":
                break
            if ans not in ("s", "q"):
                continue
            note = input("   メモ（任意）> ").strip()
            out.write(json.dumps({"id": j["id"], "expect_speak": ans == "s", "note": note, "state": st,
                                  "image": j.get("image"), "judged": a}, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
