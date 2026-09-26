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
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout

from relay import InjectError, Relay, Session

log = logging.getLogger("brain.judge")

GATEWAY = os.environ.get("BRAIN_GATEWAY_URL", "http://llm-proxy:8080/v1")
JEV_MODEL = os.environ.get("BRAIN_JEV_MODEL", "typesafe-ai/jev")
FALLBACK_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-6-luna")
INTERVAL = float(os.environ.get("BRAIN_JUDGE_INTERVAL", "5"))

# ルールによる足切り（秒・回数）
QUIET_AFTER_USER = float(os.environ.get("BRAIN_QUIET_AFTER_USER", "20"))
QUIET_AFTER_ROBOT = float(os.environ.get("BRAIN_QUIET_AFTER_ROBOT", "20"))
MIN_INJECTION_GAP = float(os.environ.get("BRAIN_MIN_INJECTION_GAP", "60"))
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
    "person_left_or_busy": "The person said they are leaving, going somewhere, sleeping, or busy (e.g. going to take a bath)",
    "robot_ignored": "The robot already started talking on its own and got no reply",
}
SPEAKABLE = {"pause_in_conversation", "just_woken_no_talk"}

SPEECH_KINDS = {
    "follow_up": "Continue or follow up on the recent conversation topic",
    "question": "Ask the person a light question about their day, plans or interests",
    "time_remark": "Make a short remark about the current time of day",
    "fixed_phrase": "A short friendly interjection from the fixed phrase list",
}
# 定型フレーズ（Jev が選ぶ）。キーは choice の名前
PHRASES = {
    "hey": "ねえねえ。",
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
IDLE_GLANCE_GAP = (float(os.environ.get("BRAIN_IDLE_GLANCE_GAP_MIN", "30")), float(os.environ.get("BRAIN_IDLE_GLANCE_GAP_MAX", "60")))

# llm モードで LLM に渡す指示（会話履歴には user 発話として残る）
LLM_INSTRUCTIONS = {
    "follow_up": "（ロボットから話しかける場面です。直前の会話の話題を踏まえて、一言だけ自然に話しかけてください。許可は求めないでください）",
    "question": "（ロボットから話しかける場面です。相手の今日の様子や好きなことについて、軽い質問を一つだけしてください。「聞いてもいい？」とは言わず、直接質問してください）",
    "time_remark": "（ロボットから話しかける場面です。今の時間帯について、ひとこと感想を言ってください）",
}


def build_state(session: Session, mood: float) -> dict:
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
        "person_detected": None,  # センサ値の取得経路は未実装
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
    def __init__(self, relay: Relay, record_dir: Path):
        self.relay = relay
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

    async def start(self, app) -> None:
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.client = ClientSession(timeout=ClientTimeout(total=15))
        self.task = asyncio.create_task(self.loop())

    async def stop(self, app) -> None:
        if self.task:
            self.task.cancel()
        if self.client:
            await self.client.close()

    def _record(self, entry: dict) -> None:
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
        if now - max(session.last_user_at, session.started_at) < QUIET_AFTER_USER:
            return "user_recent"
        if session.last_robot_end_at and now - session.last_robot_end_at < QUIET_AFTER_ROBOT:
            return "robot_recent"
        if session.last_injection_at and now - session.last_injection_at < MIN_INJECTION_GAP:
            return "injection_recent"
        if session.injections >= MAX_INJECTIONS_PER_SESSION:
            return "injection_limit"
        return None

    async def _ask_jev(self, state: dict) -> dict:
        body = {"model": JEV_MODEL, "state": state, "questions": QUESTIONS}
        async with self.client.post(f"{GATEWAY}/evaluate", json=body) as r:
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
        async with self.client.post(f"{GATEWAY}/chat/completions", json=body) as r:
            if r.status != 200:
                raise RuntimeError(f"llm {r.status}: {(await r.text())[:200]}")
            data = await r.json()
        a = json.loads(data["choices"][0]["message"]["content"])
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

    async def judge(self, session: Session) -> None:
        self._maybe_glance(session)
        mood = self._update_mood(session)
        if session.id in self.dormant:
            if session.last_user_at <= self.dormant[session.id]:
                return
            del self.dormant[session.id]
        reason = self._gate(session)
        if reason:
            return
        state = build_state(session, mood)
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
        if not speak and ans.get("situation") in ("person_left_or_busy", "robot_ignored"):
            self.dormant[session.id] = session.last_user_at
            action = {"dormant_until_user_speaks": True}
        if speak:
            kind = ans["speech_kind"]
            if kind == "fixed_phrase":
                mode, text = "verbatim", PHRASES[ans["phrase"]]
            else:
                mode, text = "llm", LLM_INSTRUCTIONS[kind]
            try:
                await self.relay.send_emotion(session, ans["emotion"])
                # 話しかける時は相手の方を向く（応答は待たない）
                asyncio.create_task(self._safe_head(session, FACE_POSE["yaw"], FACE_POSE["pitch"], 250))
                await self.relay.inject(text, mode, session.device_id)
                self.pending[session.device_id] = time.time()
                action = {"mode": mode, "kind": kind, "text": text, "emotion": ans["emotion"]}
                log.info("[%s] speak p=%.2f>=%.2f situation=%s kind=%s emotion=%s (%s %.2fs)", session.device_id,
                         ans["should_speak"], threshold, ans["situation"], kind, ans["emotion"], source, latency)
            except InjectError as e:
                action = {"error": str(e)}
        else:
            log.info("[%s] stay quiet p=%.2f<%.2f situation=%s (%s %.2fs)", session.device_id, ans["should_speak"], threshold,
                     ans["situation"], source, latency)
        self._record({"t": round(time.time(), 3), "device_id": session.device_id, "session": session.id,
                      "source": source, "latency_s": latency, "state": state, "threshold": round(threshold, 2),
                      "answers": {k: v for k, v in ans.items() if k != "raw"}, "raw": ans.get("raw"),
                      "action": action})

    async def _safe_head(self, session: Session, yaw: int, pitch: int, speed: int) -> None:
        try:
            await self.relay.move_head(session, yaw, pitch, speed)
        except Exception as e:  # noqa: BLE001 首が動かなくても会話は続ける
            log.warning("[%s] head move failed: %s", session.device_id, e)

    async def _glance(self, session: Session, yaw: int, pitch: int) -> None:
        """よそ見して、少ししたら正面に戻る。"""
        await self._safe_head(session, yaw, pitch, 150)
        await asyncio.sleep(random.uniform(2.5, 4.5))
        if session.state == "listening":
            await self._safe_head(session, FACE_POSE["yaw"], FACE_POSE["pitch"], 150)

    async def loop(self) -> None:
        while True:
            await asyncio.sleep(INTERVAL)
            for session in list(self.relay.sessions.values()):
                try:
                    await self.judge(session)
                except Exception as e:  # noqa: BLE001 1 セッションの失敗でループを止めない
                    log.warning("[%s] judge error: %s", session.device_id, e)
