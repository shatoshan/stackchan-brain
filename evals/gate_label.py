"""宛先ゲートの記録（data/llm-proxy/gate/*.jsonl）に正解のラベルを付けて evals のケースにする。

    python3 evals/gate_label.py            # 未ラベルの記録を 1 件ずつ表示して入力

キー（誰に向けた発話か → 正しい動き）:
    p  StackChan 宛て（返事・操作・質問への答えが要る）→ 通す
    b  StackChan 宛てだが、相槌だけで十分（「うん」「大丈夫だよ」など）→ 相槌か黙る
    f  家族・ほかの人に向けた発話      → 黙る
    t  テレビ・動画・音楽               → 黙る
    s  独り言                           → 黙る
    Enter  分からない（聞き取りが崩れて意図が不明など）→ 飛ばす
    x  終了

- 記録時の Jev の答え（raw）もケースに残すので、evals/gate_sweep.py は Jev を呼び直さずに閾値を試せる
- 結果は data/brain/evals/gate_labeled.jsonl（ローカル、git には入れない。実際の会話を含むため）
- 流す: docker compose exec -T brain python /evals/gate_sweep.py
依存なし（標準ライブラリのみ）。
"""
import glob
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS = ROOT / "data" / "llm-proxy" / "gate"
OUT = ROOT / "data" / "brain" / "evals" / "gate_labeled.jsonl"

LABELS = {
    "p": ("robot", ["pass"]),
    "b": ("robot", ["backchannel", "drop"]),
    "f": ("people", ["drop"]),
    "t": ("media", ["drop"]),
    "s": ("self_talk", ["drop"]),
}
# ゲート除外前に記録された brain 自身の判定依頼（発話ではない）
NOT_UTTERANCE = ("State of a small companion",)


def load_records():
    for path in sorted(glob.glob(str(RECORDS / "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            u = (r.get("state") or {}).get("utterance", "")
            if not r.get("raw") or u.startswith(NOT_UTTERANCE):
                continue  # Jev が使えなかった記録は閾値の検討に使えない
            yield r


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    labeled = [json.loads(l) for l in open(OUT, encoding="utf-8")] if OUT.exists() else []
    done = {c["id"] for c in labeled}
    # 手で作った初期のケース（real-0927-*）と同じ発話は重ねない
    done_utterances = {c["state"]["utterance"] for c in labeled}
    candidates = [r for r in load_records()
                  if f"gate-{r['t']:.3f}" not in done and r["state"]["utterance"] not in done_utterances]

    print(f"未ラベル {len(candidates)} 件")
    print("p=StackChan宛て（返事・操作が要る） b=StackChan宛てだが相槌だけで十分 f=家族 t=テレビ s=独り言 Enter=飛ばす x=終了\n")
    with open(OUT, "a", encoding="utf-8") as out:
        for r in candidates:
            st, a = r["state"], r["raw"]
            probs = a["addressee"]["probabilities"]
            print("=" * 70)
            last = st.get("robot_last_spoke_seconds_ago")
            faces = st.get("camera_faces_in_view")
            print(time.strftime("%m-%d %H:%M:%S", time.localtime(r["t"])),
                  f"  ロボットが最後に話してから {'-' if last is None else f'{last}s'}  顔 {'-' if faces is None else faces}")
            for line in st.get("recent_conversation", []):
                print(f"   {line}")
            print(f"   >> 「{st['utterance']}」")
            print(f"   Jev: " + " ".join(f"{k}={v:.2f}" for k, v in sorted(probs.items(), key=lambda kv: -kv[1]))
                  + f"  response={a['response']['choice']}  → {r['decision']}")
            ans = input("   ラベル> ").strip().lower()
            if ans == "x":
                break
            if ans not in LABELS:
                continue
            addressee, expect = LABELS[ans]
            note = input("   メモ（任意）> ").strip()
            out.write(json.dumps({"id": f"gate-{r['t']:.3f}", "expect": expect, "addressee_label": addressee,
                                  "note": note, "state": st, "answers": [a], "decided": r["decision"]},
                                 ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
