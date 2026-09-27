"""LLM の返答（SSE ストリーム）から、読み上げてはいけない英語の独り言を取り除く。

GPT-6 Luna は reasoning_effort: none でも、崩れた発話を受けた時などに英語の思考メモ
（"Need ask clarify maybe ...", "natural. 1-2 sentences. Japanese."）を返答本文に混ぜることがある
（2026-09-27 実機）。ロボットは日本語でしか話さないので、英語が主の文が出たら、その文と
それ以降の本文をすべて捨てる（後に続く日本語も下書きの続きであることが多い）。ツール呼び出しは通す。
文単位で判定するため、本文は文末まで溜めてから流す（xiaozhi-server も文単位で TTS するので遅延はほぼ無い）。
"""

import json
import logging
import re

log = logging.getLogger("llm-proxy.filter")

# 文の区切り（全角・半角の文末、改行、英文のピリオド＋空白）
_SENTENCE_END = re.compile(r"(?<=[。！？!?\n])|(?<=\.)(?=\s)")
_JA = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def is_leak(sentence: str) -> bool:
    """日本語を含まない英語の文（英単語 2 つ以上）か、英単語の方が日本語の文字より多い文を「独り言」とみなす。
    「YouTube見てるの？」「iPhone 17 Pro の話？」「Hey Siri と OK Google、どっちが好き？」は通す。"""
    words = len(_LATIN_WORD.findall(sentence))
    ja = len(_JA.findall(sentence))
    return (ja == 0 and words >= 2) or (words >= 3 and ja < words)


class SpeechFilter:
    def __init__(self) -> None:
        self._lines = b""
        self._text = ""
        self._template: dict | None = None  # 本文だけの event を作り直す時の雛形（id, model など）
        self.stopped = False
        self.dropped: list[str] = []

    def _content_event(self, text: str) -> bytes:
        ev = {k: v for k, v in (self._template or {}).items() if k != "choices"}
        ev["choices"] = [{"index": 0, "delta": {"content": text}, "finish_reason": None}]
        return b"data: " + json.dumps(ev, ensure_ascii=False).encode() + b"\n\n"

    def _emit_text(self, final: bool) -> bytes:
        parts = _SENTENCE_END.split(self._text)
        # 最後の要素は文末に達していない残り（final なら全部流す）
        done, self._text = (parts, "") if final else (parts[:-1], parts[-1])
        out = b""
        for sentence in done:
            if not sentence:
                continue
            if not self.stopped and is_leak(sentence):
                self.stopped = True
                log.warning("dropped English monologue from LLM reply: %r", sentence[:200])
            if self.stopped:
                self.dropped.append(sentence)
                continue
            out += self._content_event(sentence)
        return out

    def _event(self, line: bytes) -> bytes:
        data = line[len(b"data:"):].strip()
        if data == b"[DONE]":
            return self._emit_text(final=True) + b"data: [DONE]\n\n"
        try:
            ev = json.loads(data)
        except json.JSONDecodeError:
            return line + b"\n\n"
        choices = ev.get("choices") or []
        if not choices:
            return line + b"\n\n"
        self._template = ev
        choice = choices[0]
        delta = choice.get("delta") or {}
        out = b""
        if isinstance(delta.get("content"), str):
            self._text += delta.pop("content")
            out += self._emit_text(final=False)
        finished = choice.get("finish_reason") is not None
        if finished:
            out += self._emit_text(final=True)
        # 本文以外（role、tool_calls、finish_reason、usage）があれば元の event として流す
        if finished or any(k for k in delta if k != "content") or ev.get("usage"):
            out += b"data: " + json.dumps(ev, ensure_ascii=False).encode() + b"\n\n"
        return out

    def feed(self, chunk: bytes) -> bytes:
        self._lines += chunk
        out = b""
        while b"\n" in self._lines:
            line, self._lines = self._lines.split(b"\n", 1)
            line = line.rstrip(b"\r")
            if line.startswith(b"data:"):
                out += self._event(line)
            elif line and not line.startswith(b":"):
                out += line + b"\n"
        return out

    def close(self) -> bytes:
        out = self.feed(b"\n") if self._lines else b""
        return out + (self._emit_text(final=True) if self._text else b"")
