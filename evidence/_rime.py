"""Driving Rime from outside the agent worker.

Every script in this directory, plus ``scripts/preflight.py``, needs to make a
real Rime call without an ``AgentSession`` around it. That takes two things
that are easy to get wrong, and were:

**1. The transport decides the method, not the caller.**
``TTS.synthesize()`` is the *one-shot HTTP* path. The Rime plugin raises
unconditionally if you call it on a TTS built with ``use_websocket=True``::

    RuntimeError: Rime TTS one-shot synthesize requires use_websocket=False
                  at construction time

WebSocket is Waypoint's shipped default (``config.py``: ``rime_use_websocket:
bool = True``), because word timestamps only arrive on that path. So every
script that called ``synthesize()`` could never work in the shipped
configuration — which was all of them.

:func:`synth` picks the method from ``tts.capabilities.streaming``, the public
capability flag the framework itself dispatches on
(``livekit/agents/voice/agent.py`` uses ``StreamAdapter`` only when
``not tts.capabilities.streaming``). No private attribute is read, so this
keeps working if the plugin changes how it records the choice.

**2. Plugins need an HTTP context.**
The plugin calls ``utils.http_context.http_session()``, which raises outside a
job context::

    RuntimeError: Attempted to use an http session outside of a job context

The agent worker opens one; a bare script does not. :func:`rime_session` opens
it. This affects *both* transports, so fixing the method choice alone is not
enough.

Neither failure is reachable from the shipped agent — it runs inside a job
context and the framework drives streaming TTS through ``stream()``. Both were
confined to the proof apparatus, which is a worse place for them than it
sounds: it meant nothing that needed a Rime credential had ever run.

Word timings
------------
They are not on the event. ``SynthesizedAudio`` carries only ``frame``,
``request_id``, ``is_final``, ``segment_id`` and ``delta_text``. The plugin
pushes :class:`TimedString` objects through ``AudioEmitter.push_timed_transcript``
and the framework attaches them to the *audio frame's* userdata under
``USERDATA_TIMED_TRANSCRIPT`` (``"lk.timed_transcripts"``). :class:`Rendered`
collects them from there.
"""

from __future__ import annotations

import contextlib
import struct
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from livekit.agents.types import USERDATA_TIMED_TRANSCRIPT
from livekit.agents.utils import http_context

__all__ = ["rime_session", "synth", "probe", "Rendered", "WordTiming"]


@dataclass(frozen=True)
class WordTiming:
    """One word timestamp as it arrived from Rime, in milliseconds."""

    word: str
    start_ms: float
    end_ms: float


@dataclass
class Rendered:
    """Everything one synthesis produced, plus how it was obtained."""

    text: str
    #: ``"websocket"`` or ``"http"`` -- which method was actually used.
    transport: str
    frames: int = 0
    pcm: bytes = b""
    #: Milliseconds from the request to the first audio frame in this process.
    first_frame_ms: float | None = None
    timings: list[WordTiming] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.frames > 0

    def duration_s(self, sample_rate: int) -> float:
        """Seconds of 16-bit mono audio."""
        return len(self.pcm) / 2 / max(sample_rate, 1)

    def rms(self) -> float:
        """Loudness, as a cheap sanity check that the audio is not silence."""
        n = len(self.pcm) // 2
        if n == 0:
            return 0.0
        samples = struct.unpack(f"<{n}h", self.pcm[: n * 2])
        return (sum(s * s for s in samples) / n) ** 0.5

    def write_wav(self, path: Path, sample_rate: int) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(self.pcm)
        return path


@contextlib.asynccontextmanager
async def rime_session() -> AsyncIterator[None]:
    """Open the HTTP context a plugin needs outside the agent worker.

    Wrap the whole of a script's async main in this, once. Opening it per call
    would reconnect on every synthesis and make cold/warm latency meaningless.
    """
    async with http_context.open():
        yield


async def synth(tts, text: str, *, timeout: float = 60.0) -> Rendered:
    """Synthesise ``text`` over whichever transport ``tts`` was built for.

    Never raises for a provider-side failure: the error is captured on the
    returned :class:`Rendered` so a measurement script can report it per item
    and carry on rather than dying on the first bad fixture. Programming errors
    (a wrong argument type, a cancelled task) still propagate.
    """
    streaming = bool(tts.capabilities.streaming)
    out = Rendered(text=text, transport="websocket" if streaming else "http")
    t0 = time.perf_counter()

    try:
        if streaming:
            stream = tts.stream()
            stream.push_text(text)
            stream.flush()
            stream.end_input()
        else:
            stream = tts.synthesize(text)
    except Exception as exc:  # construction/dispatch failure
        out.error = f"{type(exc).__name__}: {exc}"
        return out

    try:
        async for ev in stream:
            frame = getattr(ev, "frame", None)
            if frame is None:
                continue
            if out.first_frame_ms is None:
                out.first_frame_ms = (time.perf_counter() - t0) * 1000.0
            out.frames += 1
            out.pcm += bytes(frame.data)
            for ts in (frame.userdata or {}).get(USERDATA_TIMED_TRANSCRIPT) or []:
                start, end = getattr(ts, "start_time", None), getattr(ts, "end_time", None)
                if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                    out.timings.append(
                        WordTiming(str(ts).strip(), float(start) * 1000.0,
                                   float(end) * 1000.0)
                    )
    except Exception as exc:
        out.error = f"{type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(Exception):
            await stream.aclose()

    return out


async def probe(tts) -> str | None:
    """One short synthesis, to fail fast on a bad credential.

    A measurement script can render dozens of fixtures, and the plugin retries
    each failure three times at two-second intervals. With a wrong key that is
    several minutes of waiting before the first useful message. Call this once
    at the top of a run and abort on a non-``None`` return.

    Returns the error string, or ``None`` if the credential and the
    model/voice/language triple all work.
    """
    r = await synth(tts, "Preflight.")
    if r.error:
        return r.error
    if r.frames == 0:
        return "the request succeeded but returned no audio frames"
    return None
