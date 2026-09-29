"""直感層: 状態ブロブを作り、Jev に「今話しかけるか・何を話すか」を判定させて差し込む。

- 数秒ごとに聞き取り中のセッションを見て、まず単純なルールで候補を絞る（Jev を無駄に呼ばない）
- Jev（Vercel AI Gateway の /v1/evaluate、llm-proxy 経由）で判定。失敗したら LLM に JSON で答えさせる
- 定型フレーズはそのまま読み上げ（verbatim）、それ以外は LLM に生成させる（llm）
- 判定はすべて data/brain/judgments/YYYYMMDD.jsonl に記録する（evals の素材）
根拠: okf/design/three-layer-architecture.md、okf/design/state-blob.md、okf/external/jev.md
"""

import asyncio
import json
import logging
import os
import random
import time
from collections import deque
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout

from relay import InjectError, Relay, Session
from vision import PRESENCE_QUESTION

log = logging.getLogger("brain.judge")

GATEWAY = os.environ.get("BRAIN_GATEWAY_URL", "http://llm-proxy:8080/v1")
JEV_URL = os.environ.get("BRAIN_JEV_URL", "http://llm-proxy:8080/jev/evaluate")
FALLBACK_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-6-luna")
INTERVAL = float(os.environ.get("BRAIN_JUDGE_INTERVAL", "5"))

# ルールによる足切り（秒・回数）
QUIET_AFTER_USER = float(os.environ.get("BRAIN_QUIET_AFTER_USER", "20"))
QUIET_AFTER_ROBOT = float(os.environ.get("BRAIN_QUIET_AFTER_ROBOT", "20"))
# まだ誰も話していないセッション（ウェイクワードやタッチで開いた直後）は早めに判定する
QUIET_AFTER_OPEN = float(os.environ.get("BRAIN_QUIET_AFTER_OPEN", "5"))
MIN_INJECTION_GAP = float(os.environ.get("BRAIN_MIN_INJECTION_GAP", "60"))
# 状況が変わらないまま「黙る」が続いたら、判定の間隔を INTERVAL の 2 倍から倍々で延ばす（この秒数まで）。
# 同じ状況に 5 秒ごと 108 回続けて「黙る」と答えさせていた（#26、2026-09-29）
QUIET_BACKOFF_MAX = float(os.environ.get("BRAIN_QUIET_BACKOFF_MAX", "60"))
MAX_INJECTIONS_PER_SESSION = int(os.environ.get("BRAIN_MAX_INJECTIONS_PER_SESSION", "4"))
# Jev が落ちている時の扱い: 一定時間 Jev を呼ばず（指数的に延長）、LLM 判定も間引く
JEV_COOLDOWN_MIN = float(os.environ.get("BRAIN_JEV_COOLDOWN_MIN", "60"))
JEV_COOLDOWN_MAX = float(os.environ.get("BRAIN_JEV_COOLDOWN_MAX", "600"))
FALLBACK_MIN_INTERVAL = float(os.environ.get("BRAIN_FALLBACK_MIN_INTERVAL", "30"))
# 話すかどうかの閾値（機嫌と、このセッションで既に話しかけた回数で上下する）
BASE_THRESHOLD = float(os.environ.get("BRAIN_SPEAK_THRESHOLD", "0.6"))

WEEKDAYS = "月火水木金土日"

# 今の状況の分類。話してよい状況の確率の合計を「話す確率」とする。
# 「話すべきか」を直接確率で聞くより安定した（evals/cases.jsonl、okf/design/jev-questions.md）
SITUATIONS = {
    "pause_in_conversation": "The person is still there and the conversation just paused; a natural chance to continue the topic or start a light one",
    "just_woken_no_talk": "The person woke the robot up but has not said anything yet",
    "person_arrived": "The camera ('person.faces_in_view' > 0) shows someone in front of the robot now and nobody is talking. "
                      "This applies even if the person earlier said they were leaving: seeing a face again means they came back",
    "person_left_or_busy": "The person said they are leaving, going somewhere, sleeping, or busy (e.g. going to take a bath), "
                           "and the camera does not currently show anyone ('person' is null or faces_in_view is 0)",
    "robot_ignored": "The robot already started talking on its own and got no reply",
}
SPEAKABLE = {"pause_in_conversation", "just_woken_no_talk", "person_arrived"}

SPEECH_KINDS = {
    "follow_up": "Continue or follow up on the recent conversation topic",
    "question": "Ask the person a light question about their day, plans or interests",
    "time_remark": "Make a short remark about the current time of day",
    "fixed_phrase": "A short friendly interjection from the fixed phrase list",
}
# 定型フレーズ（Jev が選ぶ）。キーは choice の名前。
# 「ねえねえ。」だけで終わるものは、呼びかけて何も言わないので返事がほぼ無く外した（#6、2026-09-27）
PHRASES = {
    "here": "ぼく、ここにいるよ。",
    "quiet": "なんだか静かだね。",
    "humming": "ふんふーん♪",
    "look": "ちらっ。",
}
# 自分から話しかける時に使う表情（sleepy は眠りポーズに入るので使わない）
EMOTIONS = {
    "neutral": "calm, ordinary",
    "happy": "cheerful, glad",
    "doubtful": "curious, wondering",
    "sad": "a little lonely",
}
# 首の向け方。「相手」の位置はセンサが無いので正面（yaw 0）とみなす
FACE_POSE = {"yaw": 0, "pitch": int(os.environ.get("BRAIN_FACE_PITCH", "20"))}
# 見回しは Jev に聞かず、ルールで動かす（聞き取り中に誰も話さない時間が続いたら、ランダムな間隔でよそ見）
IDLE_GLANCE_AFTER = float(os.environ.get("BRAIN_IDLE_GLANCE_AFTER", "25"))
# カメラでの在席確認（brain/vision.py）。聞き取り中にこの間隔で take_photo を呼ぶ。0 で無効
PRESENCE_INTERVAL = float(os.environ.get("BRAIN_PRESENCE_INTERVAL", "20"))
# 撮影のたびに端末がシャッター音を鳴らす（ファーム固定）ので、会話中は撮らない。
# 誰も話さない時間がこれ以上続いたら撮り始める。相手が離れた後（判定休止中）は戻りを見るため短い間隔で撮る
PRESENCE_AFTER_QUIET = float(os.environ.get("BRAIN_PRESENCE_AFTER_QUIET", "30"))
PRESENCE_INTERVAL_DORMANT = float(os.environ.get("BRAIN_PRESENCE_INTERVAL_DORMANT", "15"))
PRESENCE_FRESH = float(os.environ.get("BRAIN_PRESENCE_FRESH", "30"))  # これより古い確認結果は使わない
CAMERA_HFOV = float(os.environ.get("BRAIN_CAMERA_HFOV", "60"))      # 水平画角（度）。顔の位置→首の yaw
CAMERA_YAW_SIGN = float(os.environ.get("BRAIN_CAMERA_YAW_SIGN", "1"))  # 画像の右が yaw の正なら 1
# 垂直画角（度）。水平 60° と画像の 4:3 から 2·atan(tan(30°)·3/4) ≈ 47°。pitch は 90 が上、画像の y は下向きに増える
CAMERA_VFOV = float(os.environ.get("BRAIN_CAMERA_VFOV", "47"))
CAMERA_PITCH_SIGN = float(os.environ.get("BRAIN_CAMERA_PITCH_SIGN", "1"))  # 画像の上が pitch の正（上向き）なら 1
PITCH_RANGE = (5, 60)  # 顔を追う時の pitch の範囲（端末の範囲は 0〜90）
# 「終了」で閉じた後、自動で開き直したセッションでも、この秒数はカメラに顔が映っただけでは話しかけない
QUIET_AFTER_EXIT = float(os.environ.get("BRAIN_QUIET_AFTER_EXIT", "1800"))
IDLE_GLANCE_GAP = (float(os.environ.get("BRAIN_IDLE_GLANCE_GAP_MIN", "30")), float(os.environ.get("BRAIN_IDLE_GLANCE_GAP_MAX", "60")))

# llm モードで LLM に渡す指示（会話履歴には user 発話として残る）。
# 2026-09-27 までの実機 35 件で、follow_up が自分の直前の発言をなぞる・言い直す・反省する（「今度こそ左を向いたよ」
# 「さっきの返し少し気取ってたね」）、question が毎回「今日はどんな一日だった？」になる、が目立った（#6）
COMMON_RULES = "許可は求めず、自分の直前の発言をなぞったり、言い直したり、反省したりしないでください。一言か二言で。"
LLM_INSTRUCTIONS = {
    "follow_up": "（ロボットから話しかける場面です。相手が最後に話していた話題について、まだ言っていない新しい角度"
                 "（素朴な質問、自分の感想、関連する小さな話）で自然に話しかけてください。直前の自分の助言や励ましを繰り返さないでください。"
                 + COMMON_RULES + "）",
    "question": "（ロボットから話しかける場面です。相手の今日の様子や好きなことについて、軽い質問を一つだけしてください。"
                "「聞いてもいい？」とは言わず、直接質問してください。" + COMMON_RULES + "）",
    "time_remark": "（ロボットから話しかける場面です。今の時間帯について、ひとこと感想を言ってください。" + COMMON_RULES + "）",
    # 定型文だと「相手が戻ってきた」ことが会話履歴に残らず、その後の返答が噛み合わないので LLM に言わせる
    "person_arrived": "（ロボットから話しかける場面です。カメラで、相手が目の前に来た（戻ってきた）のが見えました。"
                      "「おかえり」など、来てくれたことへの短い一言を言ってください。" + COMMON_RULES + "）",
}
# 同じ端末で最近自分から言ったことを、この件数まで指示に添えて繰り返しを避ける
RECENT_PROACTIVE = int(os.environ.get("BRAIN_RECENT_PROACTIVE", "5"))


def with_recent(instruction: str, recent: list[str]) -> str:
    """指示の末尾に、最近自分から言ったこと（同じ内容・同じ質問を避ける）を添える。"""
    if not recent:
        return instruction
    said = "、".join(f"「{t}」" for t in recent)
    return instruction[:-1] + f"最近自分から言ったこと（同じ内容や同じ質問は避ける）: {said}）"


def person_state(session: Session) -> dict | None:
    """カメラの在席確認結果を状態ブロブ用にまとめる（確認していなければ None）。"""
    p = session.presence
    if not p or time.time() - p["checked_at"] > PRESENCE_FRESH:
        return None
    now = time.time()
    return {
        "faces_in_view": p.get("faces", 0),
        "largest_face_width_ratio": p.get("largest_face_width_ratio"),
        "seconds_face_visible": round(now - session.face_since) if session.face_since else 0,
        "seconds_since_face_seen": round(now - session.last_face_at) if session.last_face_at else None,
        "checked_seconds_ago": round(now - p["checked_at"]),
    }


def build_state(session: Session, mood: float, memory: str = "") -> dict:
    """状態ブロブ（okf/design/state-blob.md の暫定版）。"""
    now = time.time()
    lt = time.localtime(now)
    recent = [f"{role}: {text}" for role, text, _ in list(session.transcript)[-6:]]
    return {
        "now": time.strftime("%Y-%m-%d %H:%M", lt) + f" ({WEEKDAYS[lt.tm_wday]})",
        "session_age_seconds": round(now - session.started_at),
        "seconds_since_user_spoke": round(now - session.last_user_at) if session.last_user_at else None,
        "seconds_since_robot_spoke": round(now - session.last_robot_end_at) if session.last_robot_end_at else None,
        "recent_conversation": recent,
        "proactive_utterances_this_session": session.injections,
        "mood": round(mood, 2),
        "person": person_state(session),  # カメラ（None は未確認）
        "memory": memory or None,  # これまでの会話の要約（brain/memory.py）
    }


QUESTIONS = {
    "situation": {"type": "choice",
                  "instructions": "Which best describes the current situation for a small companion desk robot in a voice session? "
                                  "recent_conversation is oldest first.",
                  "criteria": SITUATIONS},
    "speech_kind": {"type": "choice", "instructions": "If the robot speaks now, what kind of utterance fits best?",
                    "criteria": SPEECH_KINDS},
    "phrase": {"type": "choice", "instructions": "If the robot uses a fixed phrase, which one fits the situation best?",
               "criteria": {k: v for k, v in PHRASES.items()}},
    "emotion": {"type": "choice", "instructions": "Which facial expression should the robot show while speaking?",
                "criteria": EMOTIONS},
}


class Judge:
    def __init__(self, relay: Relay, record_dir: Path, memory=None):
        self.relay = relay
        self.memory = memory  # brain/memory.py の Memory（無ければ記憶なし）
        self.record_dir = record_dir
        self.mood: dict[str, float] = {}      # device_id -> 0..1
        self.pending: dict[str, float] = {}   # device_id -> 差し込み時刻（反応を見て機嫌を更新する）
        self.client: ClientSession | None = None
        self.task: asyncio.Task | None = None
        self.jev_blocked_until = 0.0
        self.jev_cooldown = JEV_COOLDOWN_MIN
        self.last_fallback: dict[str, float] = {}  # device_id -> 最後に LLM で判定した時刻
        # 相手が離れた / 無視された と判定したセッションは、次にユーザーが話すまで判定しない
        # session.id -> 判定時点の last_user_at
        self.dormant: dict[str, float] = {}
        self.next_glance_gap: dict[str, float] = {}  # session.id -> 次のよそ見までの間隔
        self.auto_seen: set[str] = set()  # 自動で開いたセッションのうち、休止に入れたもの
        # device_id -> 最近自分から言ったこと（セッションをまたいで持つ）
        self.recent_proactive: dict[str, deque] = {}
        self.greeted_face: dict[str, float] = {}  # device_id -> あいさつした時の face_since
        self.backoff: dict[str, tuple] = {}  # session.id -> (状況の要約, 次に判定してよい時刻, 間隔)
        self.proactive_logged: dict[str, float] = {}  # session.id -> 記録済みの差し込み時刻

    async def start(self, app) -> None:
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.client = ClientSession(timeout=ClientTimeout(total=15))
        self.task = asyncio.create_task(self.loop())

    async def stop(self, app) -> None:
        if self.task:
            self.task.cancel()
        if self.client:
            await self.client.close()

    def _record(self, entry: dict, session: Session | None = None) -> None:
        """判定を記録する。カメラの確認結果が新しければ、その時の写真も保存する（evals/label.py でラベル付けする素材）。"""
        entry["id"] = f"{time.strftime('%Y%m%d-%H%M%S')}-{entry.get('session', 'x')}-{int(time.time() * 1000) % 1000:03d}"
        if session and session.presence and time.time() - session.presence.get("checked_at", 0) <= PRESENCE_FRESH:
            src = Path(os.environ.get("BRAIN_CAMERA_DIR", "/data/camera")) / "last.jpg"
            if src.exists():
                img_dir = self.record_dir / "images"
                img_dir.mkdir(exist_ok=True)
                dst = img_dir / f"{entry['id']}.jpg"
                dst.write_bytes(src.read_bytes())
                entry["image"] = f"images/{dst.name}"
        path = self.record_dir / time.strftime("%Y%m%d.jsonl")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _update_mood(self, session: Session) -> float:
        """直前の自発発話に相手が反応したら機嫌を上げ、無反応なら下げる。"""
        mood = self.mood.get(session.device_id, 0.6)
        sent = self.pending.get(session.device_id)
        if sent and session.last_robot_end_at > sent:
            if session.last_user_at > sent:
                mood = min(1.0, mood + 0.1)
                self.pending.pop(session.device_id)
            elif time.time() - session.last_robot_end_at > QUIET_AFTER_USER:
                mood = max(0.0, mood - 0.1)
                self.pending.pop(session.device_id)
        self.mood[session.device_id] = mood
        return mood

    @staticmethod
    def _gate(session: Session) -> str | None:
        """話しかけてはいけない理由（無ければ None）。"""
        now = time.time()
        if session.state != "listening" or not session.session_id:
            return f"state={session.state}"
        if not session.transcript:
            if now - session.started_at < QUIET_AFTER_OPEN:
                return "just_opened"
        elif now - max(session.last_user_at, session.started_at) < QUIET_AFTER_USER:
            return "user_recent"
        if session.last_robot_end_at and now - session.last_robot_end_at < QUIET_AFTER_ROBOT:
            return "robot_recent"
        if session.last_injection_at and now - session.last_injection_at < MIN_INJECTION_GAP:
            return "injection_recent"
        if session.injections >= MAX_INJECTIONS_PER_SESSION:
            return "injection_limit"
        return None

    async def _ask_jev(self, state: dict) -> dict:
        # llm-proxy の Jev 窓口（Gateway 経由か TypeSafe 直接かは llm-proxy の JEV_BACKEND で決まる）
        body = {"state": state, "questions": QUESTIONS}
        async with self.client.post(JEV_URL, json=body) as r:
            if r.status != 200:
                raise RuntimeError(f"jev {r.status}: {(await r.text())[:200]}")
            data = await r.json()
        a = data["answers"]
        probs = a["situation"]["probabilities"]
        return {
            "should_speak": round(sum(v for k, v in probs.items() if k in SPEAKABLE), 3),
            "situation": a["situation"]["choice"],
            "speech_kind": a["speech_kind"]["choice"],
            "phrase": a["phrase"]["choice"],
            "emotion": a["emotion"]["choice"],
            "raw": a,
            "cost": data.get("providerMetadata", {}).get("gateway", {}).get("cost"),
        }

    async def _ask_llm(self, state: dict) -> dict:
        """Jev が使えない時のフォールバック。同じ質問に JSON で答えさせる（確率は擬似値）。"""
        prompt = (
            "State of a small companion desk robot in a voice session (recent_conversation is oldest first):\n"
            + json.dumps(state, ensure_ascii=False)
            + "\n\nAnswer JSON only with these keys:\n"
            + "situation: which best describes the current situation, one of " + json.dumps(SITUATIONS, ensure_ascii=False)
            + "\nspeech_kind: if the robot speaks now, one of " + json.dumps(SPEECH_KINDS)
            + "\nphrase: if it uses a fixed phrase, one of " + json.dumps(PHRASES, ensure_ascii=False)
            + "\nemotion: facial expression, one of " + json.dumps(EMOTIONS)
        )
        body = {"model": FALLBACK_MODEL, "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}, "max_tokens": 100}
        # brain 自身の判定依頼なので、llm-proxy の宛先ゲートにかけない目印を付ける
        async with self.client.post(f"{GATEWAY}/chat/completions", json=body, headers={"X-StackChan-Source": "brain"}) as r:
            if r.status != 200:
                raise RuntimeError(f"llm {r.status}: {(await r.text())[:200]}")
            data = await r.json()
        # LLM は JSON の後ろに余計な文字列を付けることがあるので、先頭の JSON オブジェクトだけ読む
        text = data["choices"][0]["message"]["content"].strip()
        a, _ = json.JSONDecoder().raw_decode(text[text.find("{"):])
        if a.get("situation") not in SITUATIONS:
            a["situation"] = "robot_ignored"
        # LLM は分類だけ使う（確率は較正されていないので 1 / 0）
        a["should_speak"] = 1.0 if a["situation"] in SPEAKABLE else 0.0
        if a.get("speech_kind") not in SPEECH_KINDS:
            a["speech_kind"] = "fixed_phrase"
        if a.get("phrase") not in PHRASES:
            a["phrase"] = "hey"
        if a.get("emotion") not in EMOTIONS:
            a["emotion"] = "neutral"
        return a

    def _maybe_glance(self, session: Session) -> None:
        """聞き取り中に誰も話さない時間が続いたら、ときどきよそ見する（反射に近い振る舞いなので Jev は使わない）。"""
        if session.state != "listening" or not session.session_id:
            return
        now = time.time()
        quiet_since = max(session.last_user_at, session.last_robot_end_at, session.started_at)
        if now - quiet_since < IDLE_GLANCE_AFTER:
            return
        gap = self.next_glance_gap.setdefault(session.id, random.uniform(*IDLE_GLANCE_GAP))
        if now - max(session.last_head_move_at, quiet_since) < gap:
            return
        self.next_glance_gap[session.id] = random.uniform(*IDLE_GLANCE_GAP)
        yaw, pitch = random.choice((-1, 1)) * random.randint(15, 35), random.randint(10, 30)
        session.last_head_move_at = now  # 応答を待たずに次の判定を抑える
        asyncio.create_task(self._glance(session, yaw, pitch))
        log.info("[%s] idle glance yaw=%d pitch=%d", session.device_id, yaw, pitch)

    @staticmethod
    def _signature(session: Session) -> tuple:
        """判定の材料のうち、時間の経過以外で変わるもの。これが同じ間は Jev の答えもほぼ変わらない。"""
        p = session.presence
        faces = p.get("faces") if p and time.time() - p.get("checked_at", 0) <= PRESENCE_FRESH else None
        return (len(session.transcript), session.last_user_at, session.last_robot_end_at, session.injections,
                bool(faces) if faces is not None else None, session.face_since)

    def _collect_proactive(self, session: Session) -> None:
        """差し込み後の最初のロボット発話を「自分から言ったこと」として覚える。"""
        at = session.last_injection_at
        if not at or self.proactive_logged.get(session.id) == at:
            return
        said = next((text for role, text, t in session.transcript if role == "robot" and t > at), None)
        if said:
            self.recent_proactive.setdefault(session.device_id, deque(maxlen=RECENT_PROACTIVE)).append(said)
            self.proactive_logged[session.id] = at

    async def judge(self, session: Session) -> None:
        self._collect_proactive(session)
        self._maybe_check_presence(session)
        self._maybe_glance(session)
        mood = self._update_mood(session)
        if session.auto_opened and session.id not in self.auto_seen:
            # 端末が自動で開いたセッションは、誰かに起こされたわけではない。話すか顔が映るまで休止から始める
            self.auto_seen.add(session.id)
            self.dormant[session.id] = session.started_at
        if session.id in self.dormant:
            since = self.dormant[session.id]
            exited = self.relay.last_exit_at.get(session.device_id, 0)
            # ユーザーが話すか、休止後にカメラに顔が新しく映ったら判定を再開する（「終了」の後しばらくは話した時だけ）
            face_wakes = session.face_since > since and time.time() - exited > QUIET_AFTER_EXIT
            if session.last_user_at <= since and not face_wakes:
                return
            del self.dormant[session.id]
        reason = self._gate(session)
        if reason:
            return
        # 状況が前回と同じで前回「黙る」だったら、間隔を空ける（#26）
        signature = self._signature(session)
        backoff = self.backoff.get(session.id)
        if backoff and backoff[0] == signature and time.time() < backoff[1]:
            return
        state = build_state(session, mood, self.memory.get(session.device_id) if self.memory else "")
        started = time.time()
        ans = None
        source = "jev"
        if started >= self.jev_blocked_until:
            try:
                ans = await self._ask_jev(state)
                self.jev_cooldown = JEV_COOLDOWN_MIN
            except Exception as e:  # noqa: BLE001 Jev が落ちても会話は止めない
                self.jev_blocked_until = time.time() + self.jev_cooldown
                log.warning("jev unavailable, pausing %.0fs: %s", self.jev_cooldown, str(e)[:120])
                self.jev_cooldown = min(JEV_COOLDOWN_MAX, self.jev_cooldown * 2)
        if ans is None:
            # LLM での代替判定は間引く（原則4: LLM を高頻度で呼ばない）
            if time.time() - self.last_fallback.get(session.device_id, 0) < FALLBACK_MIN_INTERVAL:
                return
            self.last_fallback[session.device_id] = time.time()
            source = "llm"
            ans = await self._ask_llm(state)
        latency = round(time.time() - started, 3)
        # このセッションで話しかけた回数が多いほど、機嫌が悪いほど話しにくくする
        threshold = min(0.95, BASE_THRESHOLD + 0.1 * session.injections - 0.2 * (mood - 0.5))
        speak = ans["should_speak"] >= threshold
        action = None
        # 同じ「人が来た」に 2 度あいさつしない（顔が見え始めた時刻で区別する。#25）
        arrival_greeted = (ans.get("situation") == "person_arrived" and session.face_since
                           and self.greeted_face.get(session.device_id) == session.face_since)
        if speak and arrival_greeted:
            speak = False
            action = {"skip": "already_greeted_this_arrival"}
        if not speak and ans.get("situation") in ("person_left_or_busy", "robot_ignored"):
            self.dormant[session.id] = time.time()
            action = {"dormant_until_user_speaks": True}
        if speak:
            kind = ans["speech_kind"]
            if ans.get("situation") == "person_arrived":
                kind = "person_arrived"
            if kind == "fixed_phrase":
                mode, text = "verbatim", PHRASES[ans["phrase"]]
            else:
                mode, text = "llm", with_recent(LLM_INSTRUCTIONS[kind], list(self.recent_proactive.get(session.device_id, [])))
            try:
                await self.relay.send_emotion(session, ans["emotion"])
                # 話しかける時は相手の方を向く（カメラで顔が見えていればその方向、応答は待たない）
                asyncio.create_task(self._face_person(session))
                await self.relay.inject(text, mode, session.device_id)
                self.pending[session.device_id] = time.time()
                if kind == "person_arrived":
                    self.greeted_face[session.device_id] = session.face_since
                action = {"mode": mode, "kind": kind, "text": text, "emotion": ans["emotion"]}
                log.info("[%s] speak p=%.2f>=%.2f situation=%s kind=%s emotion=%s (%s %.2fs)", session.device_id,
                         ans["should_speak"], threshold, ans["situation"], kind, ans["emotion"], source, latency)
            except InjectError as e:
                action = {"error": str(e)}
        else:
            log.info("[%s] stay quiet p=%.2f th=%.2f situation=%s%s (%s %.2fs)", session.device_id, ans["should_speak"],
                     threshold, ans["situation"], " (already greeted)" if arrival_greeted else "", source, latency)
        if speak or (action or {}).get("dormant_until_user_speaks"):
            self.backoff.pop(session.id, None)
        else:
            same = backoff and backoff[0] == signature
            interval = min(QUIET_BACKOFF_MAX, backoff[2] * 2 if same else INTERVAL * 2)
            self.backoff[session.id] = (signature, time.time() + interval, interval)
        self._record({"t": round(time.time(), 3), "device_id": session.device_id, "session": session.id,
                      "source": source, "latency_s": latency, "state": state, "threshold": round(threshold, 2),
                      "answers": {k: v for k, v in ans.items() if k != "raw"}, "raw": ans.get("raw"),
                      "action": action}, session)

    async def _safe_head(self, session: Session, yaw: int, pitch: int, speed: int) -> None:
        try:
            await self.relay.move_head(session, yaw, pitch, speed)
        except Exception as e:  # noqa: BLE001 首が動かなくても会話は続ける
            log.warning("[%s] head move failed: %s", session.device_id, e)

    async def _face_person(self, session: Session) -> None:
        p = session.presence
        if p and p.get("faces") and time.time() - p["checked_at"] <= PRESENCE_FRESH:
            try:
                res = await self.relay.call_device_tool(session, "self.robot.get_head_angles", {})
                cur = json.loads(res["result"]["content"][0]["text"])
                yaw = cur["yaw"] + CAMERA_YAW_SIGN * (p["center_x"] - 0.5) * CAMERA_HFOV
                yaw = int(max(-60, min(60, yaw)))
                pitch = cur["pitch"] + CAMERA_PITCH_SIGN * (0.5 - p.get("center_y", 0.5)) * CAMERA_VFOV
                pitch = int(max(PITCH_RANGE[0], min(PITCH_RANGE[1], pitch)))
                log.info("[%s] face at x=%.2f y=%.2f -> yaw %d pitch %d (was %d, %d)", session.device_id, p["center_x"],
                         p.get("center_y", 0.5), yaw, pitch, cur["yaw"], cur["pitch"])
                await self._safe_head(session, yaw, pitch, 250)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("[%s] face tracking failed: %s", session.device_id, e)
        await self._safe_head(session, FACE_POSE["yaw"], FACE_POSE["pitch"], 250)

    async def _check_presence(self, session: Session) -> None:
        """brain の目印付きで take_photo を呼ぶ。結果は brain/vision.py が session.presence に入れる。"""
        session.presence_requested_at = time.time()
        try:
            await self.relay.call_device_tool(session, "self.camera.take_photo",
                                              {"question": PRESENCE_QUESTION}, timeout=20)
        except Exception as e:  # noqa: BLE001
            log.warning("[%s] presence check failed: %s", session.device_id, e)

    def _maybe_check_presence(self, session: Session) -> None:
        if not PRESENCE_INTERVAL or session.state != "listening" or not session.session_id:
            return
        now = time.time()
        if session.id in self.dormant:
            interval = PRESENCE_INTERVAL_DORMANT
        else:
            quiet_since = max(session.last_user_at, session.last_robot_end_at, session.started_at)
            if now - quiet_since < PRESENCE_AFTER_QUIET:
                return
            interval = PRESENCE_INTERVAL
        if now - getattr(session, "presence_requested_at", 0) < interval:
            return
        session.presence_requested_at = time.time()
        asyncio.create_task(self._check_presence(session))

    async def _glance(self, session: Session, yaw: int, pitch: int) -> None:
        """よそ見して、少ししたら正面に戻る。"""
        await self._safe_head(session, yaw, pitch, 150)
        await asyncio.sleep(random.uniform(2.5, 4.5))
        if session.state == "listening":
            await self._safe_head(session, FACE_POSE["yaw"], FACE_POSE["pitch"], 150)

    async def loop(self) -> None:
        while True:
            await asyncio.sleep(INTERVAL)
            # 閉じたセッションの記録を捨てる（常時セッションでは無音タイムアウトのたびに開き直すので溜まる）
            for ids in (self.dormant, self.next_glance_gap, self.proactive_logged, self.backoff):
                for sid in [k for k in ids if k not in self.relay.sessions]:
                    del ids[sid]
            self.auto_seen &= self.relay.sessions.keys()
            for session in list(self.relay.sessions.values()):
                try:
                    await self.judge(session)
                except Exception as e:  # noqa: BLE001 1 セッションの失敗でループを止めない
                    log.warning("[%s] judge error: %s", session.device_id, e)
