"""Heard-not-said reconciliation.

The problem this solves
-----------------------
When the driver barges in, Rime's audio stops mid-sentence. But the text that
was *generated* is the full sentence, and that full sentence is what a naive
agent writes into its chat context. The next turn is then reasoning from a
false premise: it believes the driver heard the whole thing.

The failure this produces is specific and irritating. The agent says "Your next
stop is 1247 Gough Street and the gate code is" -- the driver interrupts at
"Gough" -- and on the next turn the agent will not repeat the gate code,
because as far as it knows, it already told them.

So the assistant turn recorded in history must be the words that were actually
played out of the speaker, not the words that were generated.

Two methods, always labelled
----------------------------
:class:`Method.WORD_TIMESTAMPS`
    Exact. Rime's WebSocket streaming API emits word-level timestamps
    (``use_websocket=True`` on the plugin). We know precisely which word was
    playing when the cut landed. This is the path the shipped agent uses.

:class:`Method.DURATION_ESTIMATE`
    Approximate, and reported as approximate. Linear interpolation over
    characters against the utterance's total audio duration. It ignores
    pauses, per-phoneme duration variance and prosodic lengthening, so it is
    typically off by a word near clause boundaries.

The estimator is kept, and kept honest, for two reasons: it is the fallback
when the HTTP (non-streaming) path is active, and the gap between the two is
itself measurable evidence for why the WebSocket path is the right one.
``evidence/measure_heard_accuracy.py`` reports that gap in words.

Nothing here guesses silently. Every :class:`HeardResult` carries the method
that produced it and a human-readable note, and both are surfaced in the
transcript and in the audit log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

__all__ = [
    "Method",
    "WordMark",
    "HeardResult",
    "HeardTracker",
    "DEFAULT_WORDS_PER_SECOND",
]

#: Fallback speaking rate used only when neither word timestamps nor a total
#: audio duration are available. Measured for Rime ``coda`` at
#: ``speed_alpha=1.0`` over the fixture corpus; see
#: ``evidence/measure_heard_accuracy.py``. Treat as a coarse prior, not a
#: calibrated constant.
DEFAULT_WORDS_PER_SECOND = 2.9

_WORD_RE = re.compile(r"\S+")


class Method(str, Enum):
    """How a heard/unheard boundary was determined."""

    WORD_TIMESTAMPS = "word_timestamps"
    DURATION_ESTIMATE = "duration_estimate"
    RATE_ESTIMATE = "rate_estimate"
    COMPLETE = "complete"


#: Methods whose boundary is exact rather than inferred.
_EXACT = frozenset({Method.WORD_TIMESTAMPS, Method.COMPLETE})


@dataclass(frozen=True)
class WordMark:
    """One word-level timestamp as emitted by Rime's WebSocket stream."""

    word: str
    start_ms: float
    end_ms: float


@dataclass(frozen=True)
class HeardResult:
    """What the driver actually heard, and how confidently we know it."""

    utterance_id: str
    generated_text: str
    heard_text: str
    unheard_text: str
    cut_at_ms: float | None
    method: Method
    words_heard: int
    words_total: int
    note: str

    @property
    def interrupted(self) -> bool:
        return bool(self.unheard_text.strip())

    @property
    def exact(self) -> bool:
        """True when the boundary is known rather than inferred."""
        return self.method in _EXACT

    @property
    def heard_fraction(self) -> float:
        if not self.words_total:
            return 1.0
        return self.words_heard / self.words_total

    def to_chat_text(self) -> str:
        """The assistant turn as it should be written into the chat context.

        Only the heard words, plus an explicit marker so the LLM knows the turn
        was truncated and must not assume the rest landed. The marker is plain
        language rather than a special token because it has to survive being
        read by whatever model is configured.
        """
        if not self.interrupted:
            return self.generated_text
        heard = self.heard_text.rstrip()
        if not heard:
            return (
                "[the driver interrupted before hearing any of this reply]"
            )
        return (
            f"{heard} "
            "[cut off here - the driver interrupted and did not hear the rest]"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "utterance_id": self.utterance_id,
            "generated_text": self.generated_text,
            "heard_text": self.heard_text,
            "unheard_text": self.unheard_text,
            "cut_at_ms": None if self.cut_at_ms is None else round(self.cut_at_ms, 2),
            "method": self.method.value,
            "exact": self.exact,
            "words_heard": self.words_heard,
            "words_total": self.words_total,
            "heard_fraction": round(self.heard_fraction, 4),
            "note": self.note,
        }


@dataclass
class _Utterance:
    utterance_id: str
    text: str
    words: list[str]
    marks: list[WordMark] = field(default_factory=list)
    total_audio_ms: float | None = None
    closed: bool = False


class HeardTracker:
    """Tracks generated utterances and reconciles them against real playout.

    Usage from the agent::

        tracker.begin("u1", "Your next stop is 1247 Gough Street")
        tracker.attach_marks("u1", marks_from_rime)   # WebSocket path
        ...
        result = tracker.cut("u1", at_ms=1180.0)      # driver barged in
        chat_ctx.append(role="assistant", text=result.to_chat_text())
    """

    def __init__(self, words_per_second: float = DEFAULT_WORDS_PER_SECOND) -> None:
        if words_per_second <= 0:
            raise ValueError("words_per_second must be positive")
        self._wps = words_per_second
        self._utterances: dict[str, _Utterance] = {}

    # -- lifecycle -------------------------------------------------------

    def begin(self, utterance_id: str, text: str) -> None:
        """Register an utterance at the moment its text is handed to Rime."""
        if utterance_id in self._utterances:
            raise ValueError(f"utterance {utterance_id!r} already begun")
        self._utterances[utterance_id] = _Utterance(
            utterance_id=utterance_id,
            text=text,
            words=_WORD_RE.findall(text),
        )

    def attach_marks(self, utterance_id: str, marks: Iterable[WordMark]) -> None:
        """Attach Rime word-level timestamps as they stream in.

        Safe to call repeatedly; marks accumulate. Only the marks that have
        arrived before the cut are used, which is exactly right: a word whose
        timestamp has not arrived cannot have been played.
        """
        utt = self._require(utterance_id)
        utt.marks.extend(marks)

    def set_total_audio_ms(self, utterance_id: str, ms: float) -> None:
        """Record the full synthesised duration, enabling the linear estimator."""
        self._require(utterance_id).total_audio_ms = float(ms)

    def known_method(self, utterance_id: str) -> Method:
        """Which method a cut would use right now. Lets the agent log honestly."""
        utt = self._require(utterance_id)
        if utt.marks:
            return Method.WORD_TIMESTAMPS
        if utt.total_audio_ms:
            return Method.DURATION_ESTIMATE
        return Method.RATE_ESTIMATE

    # -- resolution ------------------------------------------------------

    def cut(self, utterance_id: str, at_ms: float) -> HeardResult:
        """Resolve an interrupted utterance at ``at_ms`` into the audio."""
        utt = self._require(utterance_id)
        utt.closed = True
        at_ms = max(0.0, float(at_ms))

        if utt.marks:
            return self._cut_by_marks(utt, at_ms)
        if utt.total_audio_ms:
            return self._cut_by_duration(utt, at_ms)
        return self._cut_by_rate(utt, at_ms)

    def complete(self, utterance_id: str) -> HeardResult:
        """Resolve an utterance that played to the end without interruption."""
        utt = self._require(utterance_id)
        utt.closed = True
        return HeardResult(
            utterance_id=utt.utterance_id,
            generated_text=utt.text,
            heard_text=utt.text,
            unheard_text="",
            cut_at_ms=None,
            method=Method.COMPLETE,
            words_heard=len(utt.words),
            words_total=len(utt.words),
            note="played to completion; nothing was withheld",
        )

    def discard(self, utterance_id: str) -> None:
        self._utterances.pop(utterance_id, None)

    # -- strategies ------------------------------------------------------

    def _cut_by_marks(self, utt: _Utterance, at_ms: float) -> HeardResult:
        """Exact boundary from Rime word timestamps.

        A word counts as heard only if its audio *finished* before the cut. A
        word that was half-played is treated as unheard: the driver may have
        caught a syllable, but we must not let the model assume they got the
        whole token. Under-claiming is the safe direction -- the cost is the
        agent occasionally repeating a word, and the cost of over-claiming is
        a gate code the driver never received.
        """
        heard_words = [m.word for m in utt.marks if m.end_ms <= at_ms]
        n = len(heard_words)
        total = max(len(utt.words), len(utt.marks))
        heard_text = " ".join(utt.words[:n]) if n <= len(utt.words) else utt.text
        unheard_text = " ".join(utt.words[n:]) if n < len(utt.words) else ""
        partial = next((m for m in utt.marks if m.start_ms < at_ms < m.end_ms), None)
        note = (
            f"exact: Rime word timestamps; cut at {at_ms:.0f}ms, "
            f"{n}/{total} words completed"
        )
        if partial is not None:
            note += f"; '{partial.word}' was mid-word and is counted as unheard"
        return HeardResult(
            utterance_id=utt.utterance_id,
            generated_text=utt.text,
            heard_text=heard_text,
            unheard_text=unheard_text,
            cut_at_ms=at_ms,
            method=Method.WORD_TIMESTAMPS,
            words_heard=n,
            words_total=total,
            note=note,
        )

    def _cut_by_duration(self, utt: _Utterance, at_ms: float) -> HeardResult:
        """Linear interpolation over characters against total audio duration."""
        total_ms = float(utt.total_audio_ms or 0.0)
        frac = 1.0 if total_ms <= 0 else min(1.0, at_ms / total_ms)
        n = self._words_from_fraction(utt, frac)
        return self._estimate_result(
            utt,
            n,
            at_ms,
            Method.DURATION_ESTIMATE,
            note=(
                f"approximate: linear interpolation over {total_ms:.0f}ms of "
                f"audio ({frac:.0%} elapsed). Ignores pauses and per-phoneme "
                "duration; typically +/-1 word near clause boundaries. Enable "
                "the Rime WebSocket path for an exact boundary."
            ),
        )

    def _cut_by_rate(self, utt: _Utterance, at_ms: float) -> HeardResult:
        """Coarsest fallback: a fixed words-per-second prior."""
        n = min(len(utt.words), int((at_ms / 1000.0) * self._wps))
        return self._estimate_result(
            utt,
            n,
            at_ms,
            Method.RATE_ESTIMATE,
            note=(
                f"approximate: fixed rate prior of {self._wps} words/sec, no "
                "audio duration and no word timestamps were available. This is "
                "the least reliable path and should not appear in a healthy run."
            ),
        )

    @staticmethod
    def _words_from_fraction(utt: _Utterance, frac: float) -> int:
        """Map an elapsed fraction to a word count, weighting by characters.

        Characters are a better proxy for time than words are, because "a" and
        "unacceptable" do not take the same time to say. We accumulate
        character mass and cut where it crosses the elapsed fraction.
        """
        if not utt.words:
            return 0
        lengths = [len(w) + 1 for w in utt.words]
        total_chars = sum(lengths)
        target = frac * total_chars
        acc = 0.0
        for i, length in enumerate(lengths):
            acc += length
            if acc > target:
                return i
        return len(utt.words)

    @staticmethod
    def _estimate_result(
        utt: _Utterance,
        n: int,
        at_ms: float,
        method: Method,
        note: str,
    ) -> HeardResult:
        n = max(0, min(n, len(utt.words)))
        return HeardResult(
            utterance_id=utt.utterance_id,
            generated_text=utt.text,
            heard_text=" ".join(utt.words[:n]),
            unheard_text=" ".join(utt.words[n:]),
            cut_at_ms=at_ms,
            method=method,
            words_heard=n,
            words_total=len(utt.words),
            note=note,
        )

    def _require(self, utterance_id: str) -> _Utterance:
        try:
            return self._utterances[utterance_id]
        except KeyError:
            raise KeyError(f"unknown utterance {utterance_id!r}") from None


def boundary_error_words(exact: HeardResult, estimated: HeardResult) -> int:
    """Signed word error of an estimate against the exact boundary.

    Positive means the estimator over-claimed (said the driver heard more than
    they did), which is the dangerous direction. Used by
    ``evidence/measure_heard_accuracy.py``.
    """
    return estimated.words_heard - exact.words_heard
