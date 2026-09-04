"""Waypoint: a hands-free dispatch copilot for delivery drivers.

Run it::

    python -m waypoint.agent console        # talk to it in the terminal
    python -m waypoint.agent dev            # connect to a LiveKit room
    python -m waypoint.agent --print-config # show the exact shipped config

Where the fence attaches to LiveKit
-----------------------------------
LiveKit 1.7 already does part of this job, and it is worth being precise about
which part, because the rest is what Waypoint adds.

On a barge-in, ``AgentActivity`` calls ``cancel_and_wait`` on the tool
executor task and then does this (``voice/agent_activity.py``)::

    # commit results of tools that finished despite the interruption (#3702), so
    # the next inference doesn't run them again
    ...
    self._agent._chat_ctx.insert(interrupted_tool_messages)

with each output rewritten by ``_interrupted_tool_output`` to carry
``reply_required = False``.

That is a sound design. It stops the *immediate* stale utterance, and it keeps
the result so the model does not pay to re-run the lookup. But it deliberately
leaves the raw stale value sitting in the chat context with nothing marking it
as superseded. The model reads ``route_eta(Oak Street) -> 14 minutes`` on the
next turn and states it as current, for a destination the driver has already
changed. Suppressing the immediate reply does not suppress the deferred one.

And ``reply_required=False`` governs *speech*, not *effects*. Cancellation is
not a safety mechanism for a write: by the time ``CancelledError`` arrives, the
HTTP POST that marked the delivery has already returned 200.

So Waypoint adds three things on top:

1. **A generation stamp and an admission gate** (:mod:`waypoint.fencing`), so a
   superseded read is written into the context already labelled as superseded
   rather than as a bare value.
2. **An effect-boundary check**, so an irreversible write is refused *before*
   it happens rather than cancelled after it lands.
3. **Re-anchoring**, so the common case -- the driver refining a request rather
   than abandoning it -- reuses the in-flight lookup instead of paying for it
   twice.

Why bumping only on interruption is complete
--------------------------------------------
The fence advances its generation on barge-in and on nothing else. That is not
a simplification; it is exhaustive, and the reason is in the framework. In the
*non*-interrupted path ``AgentActivity`` does ``await exe_task`` -- tools are
awaited to completion before the turn ends. So the only way a tool result can
outlive the turn that asked for it is an interruption. Bumping on ordinary turn
boundaries as well would add no safety and would risk fencing a valid result if
the bump raced ahead of the issue.

The signal is read synchronously from ``ctx.speech_handle.interrupted`` at each
boundary rather than subscribed to as an event, so there is no window where a
tool observes a stale generation because the event had not been dispatched yet.
:meth:`waypoint.fencing.TurnFence.bump_for` makes that read idempotent across
the several places it happens.

Safety lives in code, not in the prompt
---------------------------------------
The superseded marker returned to the model is for conversational coherence
only. Nothing that matters depends on the model honouring it: the write is
blocked by :meth:`TurnFence.check` before it executes, and the audit log
records what happened either way. A prompt is not a control.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterable, Awaitable, Callable

from livekit import agents, rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    ModelSettings,
    RunContext,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.agents.types import TimedString
from livekit.plugins import rime, silero

from .config import ConfigError, Settings, load_settings
from .dispatch import DispatchBackend, DispatchError, Stop, make_backend
from .fencing import Disposition, FenceRecord, ReanchorPolicy, TurnFence
from .heard import HeardResult, HeardTracker, WordMark
from .metrics import Boundary, MetricsLog
from .prompts import SUPERSEDED_MARKER, build_instructions, GREETING
from .pronounce import Strategy, speak_address, speak_code, speak_house_number, render

logger = logging.getLogger("waypoint")


def session_evidence_dir() -> Path:
    """Where a live run leaves its audit trail.

    Resolved from ``__file__``, the way every other path in this repository is
    -- ``scripts/``, ``evidence/`` and ``web/`` all derive a ``ROOT`` that way.
    This one site used ``Path("evidence/results/sessions")``, which is relative
    to the process's working directory, and the agent is started as
    ``python -m waypoint.agent dev`` from wherever the operator happens to be
    standing. Run it from a home directory and the fence audit trail, the
    metrics and the heard-log were written to ``~/evidence/results/sessions``
    -- outside the repository, with the failure swallowed by ``except
    OSError``.

    That is an unlucky path for the *one* code path that captures proof a real
    session happened, which is this submission's thinnest evidence.

    ``WAYPOINT_EVIDENCE_DIR`` overrides it, for a non-editable install (where
    ``parents[2]`` lands in site-packages) and for tests.
    """
    override = os.environ.get("WAYPOINT_EVIDENCE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "evidence" / "results" / "sessions"


FENCE_TOPIC = "waypoint.fence"


# --------------------------------------------------------------------------
# Shared per-session state
# --------------------------------------------------------------------------


def _origin(ctx: RunContext) -> str:
    """Identity of the turn issuing a tool call: the ``SpeechHandle`` id.

    Stamped onto every ticket so a turn that has already been interrupted
    cannot issue fresh-looking work. The generation counter advances once per
    barge-in, so on its own it cannot distinguish "issued before the barge-in"
    from "issued by the dead turn after it". See
    :meth:`waypoint.fencing.TurnFence._supersession_reason`.
    """
    handle = getattr(ctx, "speech_handle", None)
    return str(getattr(handle, "id", "")) if handle is not None else ""


@dataclass
class Deps:
    """Everything the agent needs, injected so tests can supply fakes."""

    settings: Settings
    backend: DispatchBackend
    fence: TurnFence
    heard: HeardTracker
    metrics: MetricsLog
    room: rtc.Room | None = None
    #: Every resolved utterance, in order. This is the audit trail for the
    #: heard-not-said claim, written to evidence/results/sessions/ on shutdown
    #: so the claim leaves a record rather than only a log line.
    heard_log: list[HeardResult] = field(default_factory=list)

    def publish(self, payload: dict[str, Any]) -> None:
        """Push an event to the demo visualiser. Never raises.

        Observability must not be able to break the session, so every failure
        here is swallowed and logged. The audit log in the fence remains the
        source of truth; this is only the live view.
        """
        if not self.settings.publish_fence_events or self.room is None:
            return
        try:
            lp = self.room.local_participant
            if lp is None:
                return
            data = json.dumps(payload).encode("utf-8")
            asyncio.create_task(lp.publish_data(data, topic=FENCE_TOPIC))
        except Exception:
            logger.debug("fence event publish failed", exc_info=True)


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------


class WaypointAgent(Agent):
    def __init__(self, deps: Deps) -> None:
        self.deps = deps
        #: utterance id -> monotonic time the first transcription delta landed.
        self._utt_started: dict[str, float] = {}
        super().__init__(instructions=build_instructions(deps.settings))

    # -- lifecycle -------------------------------------------------------

    async def on_enter(self) -> None:
        self.deps.publish(
            {"type": "config", "config": self.deps.settings.to_dict()}
        )
        await self.session.say(self._voice(GREETING), allow_interruptions=True)

    # -- pipeline overrides ----------------------------------------------

    async def transcription_node(
        self, text: AsyncIterable[str | TimedString], model_settings: ModelSettings
    ) -> AsyncIterable[str | TimedString]:
        """Capture the utterance text and Rime's word timestamps.

        With ``use_tts_aligned_transcript=True`` and the Rime plugin in
        WebSocket mode, the deltas arriving here are :class:`TimedString`
        instances carrying per-word ``start_time`` / ``end_time`` in seconds.
        Those are what make the heard/unheard boundary exact rather than
        estimated; on the HTTP path they are absent and
        :class:`~waypoint.heard.HeardTracker` says so in its result.

        Both the *text* and the *marks* are collected here and registered
        together once the stream ends, because
        :meth:`HeardTracker.attach_marks` requires the utterance to exist and
        the utterance's word list is what the marks are counted against. An
        earlier version registered the utterance with an empty string and then
        attached marks to it, which made every reconciliation return the empty
        string -- silently, because the unit tests exercised the tracker
        directly with real text and never went through this node.

        ``t0`` is the moment the first delta arrives, which is the closest
        in-process proxy we have for the start of playout. It is used as the
        origin for the cut position in :meth:`_reconcile_heard`, and its error
        is documented there.
        """
        handle = self.session.current_speech
        utt_id = handle.id if handle is not None else "unknown"
        marks: list[WordMark] = []
        chunks: list[str] = []

        async for delta in text:
            if not chunks and utt_id not in self._utt_started:
                self._utt_started[utt_id] = time.monotonic()
            chunks.append(str(delta))
            if isinstance(delta, TimedString):
                st, en = delta.start_time, delta.end_time
                if isinstance(st, (int, float)) and isinstance(en, (int, float)):
                    marks.append(
                        WordMark(str(delta), float(st) * 1000.0, float(en) * 1000.0)
                    )
            yield delta

        full_text = "".join(chunks).strip()
        if not full_text:
            return
        try:
            self.deps.heard.begin(utt_id, full_text)
        except ValueError:
            return  # already registered; a retry of the same utterance
        if marks:
            self.deps.heard.attach_marks(utt_id, marks)

    # -- heard-not-said reconciliation ------------------------------------

    def _on_speech_done(self, handle: Any) -> None:
        """Sync callback from LiveKit. Hands off to the async reconciliation."""
        gen_bumped = False
        if handle.interrupted:
            gen = self.deps.fence.bump_for(handle.id, "speech_handle.interrupted")
            gen_bumped = True
            self.deps.publish(
                {"type": "generation", "generation": gen, "reason": "barge_in"}
            )
        try:
            asyncio.create_task(self._reconcile_heard(handle))
        except RuntimeError:  # pragma: no cover - no running loop
            logger.debug("no loop for heard reconciliation", exc_info=True)
        if gen_bumped:
            logger.info("barge-in on %s", handle.id)

    async def _reconcile_heard(self, handle: Any) -> None:
        """Correct the record to what the driver actually heard.

        This is the third claim in ``RIME_EVIDENCE.md`` and this method is
        where it either happens or does not. When an utterance is cut short,
        LiveKit records the assistant turn that was *generated*. We append a
        correction stating what was *played*, so the next inference cannot
        assume the driver received a gate code that was never spoken.

        The cut position is ``now - t0`` where ``t0`` is when the first
        transcription delta arrived. That is a proxy for the start of playout,
        not playout itself: it omits the transport hop and the client jitter
        buffer, so it reads slightly *late*, which biases towards believing the
        driver heard more than they did. Rime's word timestamps then place the
        boundary within that window exactly. The residual error is one
        network hop and is stated in ``docs/THREAT_MODEL.md`` (R6), not hidden.
        """
        utt_id = handle.id
        t0 = self._utt_started.pop(utt_id, None)
        try:
            if not handle.interrupted:
                result = self.deps.heard.complete(utt_id)
            else:
                elapsed_ms = (time.monotonic() - t0) * 1000.0 if t0 else 0.0
                result = self.deps.heard.cut(utt_id, elapsed_ms)
        except KeyError:
            return  # nothing was ever transcribed for this handle
        finally:
            self.deps.heard.discard(utt_id)

        self.deps.heard_log.append(result)
        self.deps.publish({"type": "heard", "result": result.to_dict()})

        if not result.interrupted:
            return

        logger.info(
            "heard %d/%d words (%s)",
            result.words_heard, result.words_total, result.method.value,
        )
        try:
            ctx = self.chat_ctx.copy()
            ctx.add_message(
                role="system",
                content=(
                    "[playback record] The driver heard only: "
                    f'"{result.heard_text}". The rest of that reply was cut off '
                    "by their interruption and never played, so they did not "
                    "receive it. Do not assume they did. "
                    f"({result.note})"
                ),
            )
            await self.update_chat_ctx(ctx)
        except Exception:
            # A failure to annotate must not end the session; the audit log
            # above still records what happened.
            logger.warning("could not append playback record", exc_info=True)

    # -- fence integration ------------------------------------------------

    def _sync(self, ctx: RunContext) -> None:
        """Advance the fence if this turn has already been interrupted.

        Read synchronously at every boundary. Idempotent per speech handle, so
        calling it from three places costs one generation, not three.
        """
        handle = getattr(ctx, "speech_handle", None)
        if handle is not None and handle.interrupted:
            gen = self.deps.fence.bump_for(handle.id, "speech_handle.interrupted")
            self.deps.publish(
                {"type": "generation", "generation": gen, "reason": "barge_in"}
            )

    def _on_record(self, record: FenceRecord) -> None:
        self.deps.publish(
            {
                "type": "fence",
                "record": record.to_dict(),
                "stats": self.deps.fence.stats(),
                "generation": self.deps.fence.generation,
            }
        )

    async def _read(
        self,
        ctx: RunContext,
        name: str,
        args: dict[str, Any],
        work: Callable[[], Awaitable[Any]],
        speak: Callable[[Any], str],
    ) -> str:
        """Run a side-effect-free lookup behind the fence.

        Reads are re-anchorable: if the driver interrupted only to refine the
        request, and the new turn wants the same lookup, the in-flight result
        is handed over instead of being discarded and re-issued.
        """
        fence = self.deps.fence
        # Issue *before* syncing. The ticket must record the generation the
        # turn believed it was in when it asked; syncing first would advance
        # the generation and then stamp the ticket with the new one, laundering
        # a request made by an already-dead turn into a fresh one.
        ticket = fence.issue(
            name, args, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH, origin=_origin(ctx)
        )
        self._sync(ctx)
        self.deps.publish(
            {
                "type": "issued",
                "ticket": ticket.ticket_id,
                "tool": name,
                "args": args,
                "generation": ticket.generation,
                "policy": ticket.policy.value,
            }
        )
        try:
            result = await work()
        except asyncio.CancelledError:
            fence.cancel(ticket, "cancelled by framework on interruption")
            raise
        except DispatchError as exc:
            # An error is still a tool result. If the turn that asked is dead,
            # the driver must not hear about it either -- they have already
            # moved on, and "that did not work" about an abandoned request is
            # exactly as confusing as a stale answer.
            self._sync(ctx)
            superseded = not fence.check(ticket).commit
            fence.cancel(ticket, f"domain error: {exc}")
            return SUPERSEDED_MARKER if superseded else f"That did not work. {exc}"
        except Exception:
            fence.cancel(ticket, "tool raised")
            raise

        self._sync(ctx)
        decision = fence.admit(ticket)
        self.deps.metrics.record(
            f"tool.{name}", decision.latency_ms, Boundary.IN_PROCESS,
            disposition=decision.disposition.value,
        )
        if not decision.speak:
            logger.info(
                "fenced read", extra={"tool": name, "disp": decision.disposition.value}
            )
            return SUPERSEDED_MARKER
        if decision.disposition is Disposition.REANCHORED:
            logger.info("re-anchored read", extra={"tool": name})
        return self._voice(speak(result))

    async def _write(
        self,
        ctx: RunContext,
        name: str,
        args: dict[str, Any],
        work: Callable[[int], Awaitable[Any]],
        speak: Callable[[Any], str],
    ) -> str:
        """Run an irreversible operation behind the fence.

        The fence is checked at the **effect boundary** -- immediately before
        the write -- because a write that has already committed cannot be
        undone by cancelling the coroutine that issued it.

        If the driver interrupts *during* the write, the write still lands. We
        do not pretend otherwise: the result comes back labelled as committed
        but unconfirmed, so the next turn tells the driver what happened rather
        than leaving them to discover it.
        """
        fence = self.deps.fence
        # Issue before syncing -- see the note in ``_read``.
        ticket = fence.issue(name, args, ReanchorPolicy.NEVER, origin=_origin(ctx))
        self._sync(ctx)
        self.deps.publish(
            {
                "type": "issued",
                "ticket": ticket.ticket_id,
                "tool": name,
                "args": args,
                "generation": ticket.generation,
                "policy": ticket.policy.value,
            }
        )

        # Effect boundary. Nothing irreversible has happened yet.
        self._sync(ctx)
        pre = fence.check(ticket)
        if not pre.commit:
            fence.admit(ticket)
            logger.info("refused stale write", extra={"tool": name})
            return (
                "REFUSED_STALE_WRITE: the driver interrupted before this was "
                "carried out, so it was not done. Nothing changed. Ask what "
                "they want now."
            )

        try:
            result = await work(pre.observed_generation)
        except asyncio.CancelledError:
            fence.cancel(ticket, "cancelled during write; effect may have landed")
            raise
        except DispatchError as exc:
            self._sync(ctx)
            superseded = not fence.check(ticket).commit
            fence.cancel(ticket, f"domain error: {exc}")
            return SUPERSEDED_MARKER if superseded else f"That did not work. {exc}"
        except Exception:
            fence.cancel(ticket, "tool raised")
            raise

        # The write has now happened and is durable.
        self._sync(ctx)
        decision = fence.admit(ticket)
        self.deps.metrics.record(
            f"tool.{name}", decision.latency_ms, Boundary.IN_PROCESS,
            disposition=decision.disposition.value,
        )
        if not decision.speak:
            return (
                "COMMITTED_BUT_UNCONFIRMED: this was carried out, but the "
                "driver interrupted before hearing the confirmation. Tell them "
                "plainly that it is done, on the next turn. Do not repeat it "
                "as if it were new, and do not do it again."
            )
        return self._voice(speak(result))

    def _voice(self, text: str) -> str:
        """Last stop before Rime: apply the pronunciation strategy."""
        s = self.deps.settings
        out = render(
            text,
            strategy=s.pronunciation,
            model=s.rime_model,
            lang=s.rime_lang,
            strict=False,
        )
        return out.text

    # -- tools: reads -----------------------------------------------------

    @function_tool
    async def next_stop(self, ctx: RunContext) -> str:
        """Get the driver's next pending delivery stop with its address."""

        def say(stop: Stop) -> str:
            addr = speak_address(
                stop.house_number,
                stop.street,
                stop.unit,
                strategy=self.deps.settings.pronunciation,
                pause_ms=self.deps.settings.effective_pause_ms,
            )
            return (
                f"Next is stop {stop.sequence}, {addr.text}. "
                f"Window closes at {stop.window_end}."
            )

        return await self._read(
            ctx, "next_stop", {}, lambda: self.deps.backend.get_stop("next"), say
        )

    @function_tool
    async def eta_to(self, ctx: RunContext, destination: str) -> str:
        """Get driving time and distance to a stop.

        Args:
            destination: Street name, stop id, or an ordinal like "next".
        """

        def say(r: dict[str, Any]) -> str:
            street = render(
                r["street"],
                strategy=self.deps.settings.pronunciation,
                model=self.deps.settings.rime_model,
                strict=False,
            ).text
            return (
                f"{r['eta_minutes']} minutes to {street}, "
                f"{r['distance_miles']} miles."
            )

        return await self._read(
            ctx,
            "eta_to",
            {"destination": destination},
            lambda: self.deps.backend.route_eta(destination),
            say,
        )

    @function_tool
    async def access_notes(self, ctx: RunContext, destination: str) -> str:
        """Get gate code, unit and access instructions for a stop.

        Args:
            destination: Street name, stop id, or an ordinal like "next".
        """

        def say(r: dict[str, Any]) -> str:
            parts = [r["access_note"]]
            if r.get("unit"):
                parts.append(f"It is {r['unit']}.")
            if r.get("gate_code"):
                code = speak_code(
                    r["gate_code"], pause_ms=self.deps.settings.effective_pause_ms
                )
                parts.append(f"Gate code is {code}.")
            return " ".join(parts)

        return await self._read(
            ctx,
            "access_notes",
            {"destination": destination},
            lambda: self.deps.backend.access_notes(destination),
            say,
        )

    @function_tool
    async def stops_remaining(self, ctx: RunContext) -> str:
        """Count how many stops are still pending on today's route."""

        def say(stops: list[Stop]) -> str:
            if not stops:
                return "That is the route done. Nothing left."
            streets = ", ".join(
                render(
                    s.street,
                    strategy=self.deps.settings.pronunciation,
                    model=self.deps.settings.rime_model,
                    strict=False,
                ).text
                for s in stops[:3]
            )
            return f"{len(stops)} left. Next few are {streets}."

        return await self._read(
            ctx, "stops_remaining", {}, self.deps.backend.remaining_stops, say
        )

    # -- tools: writes ----------------------------------------------------

    @function_tool
    async def mark_delivered(
        self, ctx: RunContext, destination: str, note: str = ""
    ) -> str:
        """Mark a stop delivered. This is irreversible and closes the stop.

        Args:
            destination: Street name or stop id.
            note: Optional short delivery note.
        """
        return await self._write(
            ctx,
            "mark_delivered",
            {"destination": destination, "note": note},
            lambda gen: self.deps.backend.mark_delivered(
                destination, note, at_generation=gen
            ),
            lambda r: f"Marked {r['stop_id']} delivered.",
        )

    @function_tool
    async def reschedule_stop(
        self, ctx: RunContext, destination: str, reason: str
    ) -> str:
        """Push a stop to a later route and notify dispatch. Irreversible.

        Args:
            destination: Street name or stop id.
            reason: Why it is being rescheduled.
        """
        return await self._write(
            ctx,
            "reschedule_stop",
            {"destination": destination, "reason": reason},
            lambda gen: self.deps.backend.reschedule(
                destination, reason, at_generation=gen
            ),
            lambda r: f"Rescheduled {r['stop_id']}. Dispatch has been told.",
        )

    @function_tool
    async def notify_recipient(
        self, ctx: RunContext, destination: str, message: str
    ) -> str:
        """Text the recipient at a stop. The message cannot be unsent.

        Args:
            destination: Street name or stop id.
            message: Short message to send.
        """
        return await self._write(
            ctx,
            "notify_recipient",
            {"destination": destination, "message": message},
            lambda gen: self.deps.backend.notify_recipient(
                destination, message, at_generation=gen
            ),
            lambda r: "Message sent.",
        )


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------


def build_tts(settings: Settings) -> rime.TTS:
    """Construct the Rime TTS exactly as documented in the README.

    Every argument here is mirrored in ``Settings.banner()`` so the shipped
    configuration and the disclosed configuration cannot drift apart.
    """
    kwargs: dict[str, Any] = {
        "model": settings.rime_model,
        "speaker": settings.rime_speaker,
        "lang": settings.rime_lang,
        "sample_rate": settings.rime_sample_rate,
        "speed_alpha": settings.rime_speed_alpha,
        "use_websocket": settings.effective_use_websocket,
    }
    if settings.effective_use_websocket:
        kwargs["segment"] = settings.rime_segment
    if settings.rime_base_url:
        kwargs["base_url"] = settings.rime_base_url
    # Bracket controls exist only on models that honour them. Setting them on
    # coda would be a silent no-op, which is the failure this codebase is about.
    if settings.supports_brackets:
        kwargs["phonemize_between_brackets"] = (
            settings.pronunciation is Strategy.PHONEME
        )
        kwargs["pause_between_brackets"] = settings.pause_ms > 0
    return rime.TTS(**kwargs)


def build_session(settings: Settings, deps: Deps) -> AgentSession:
    return AgentSession(
        stt=inference.STT(settings.stt_model, language=settings.stt_language),
        llm=inference.LLM(settings.llm_model),
        tts=build_tts(settings),
        vad=silero.VAD.load(),
        # Rime's WebSocket stream carries word timestamps; this is what routes
        # them into transcription_node, and therefore into heard-not-said.
        #
        # `effective_use_websocket`, not the raw flag: the plugin upgrades the
        # transport from a `wss://` override, and reading the raw flag here
        # declined timestamps that were already arriving. See
        # `Settings.effective_use_websocket`.
        use_tts_aligned_transcript=settings.effective_use_websocket,
        turn_handling=TurnHandlingOptions(
            interruption={
                "enabled": True,
                "mode": settings.interruption_mode,
                "min_duration": settings.min_interruption_duration,
                "min_words": settings.min_interruption_words,
                "resume_false_interruption": settings.resume_false_interruption,
                "false_interruption_timeout": settings.false_interruption_timeout,
            },
            preemptive_generation={"enabled": settings.preemptive_generation},
        ),
        tts_text_transforms=["filter_emoji", "filter_markdown"],
    )


def attach_observers(
    session: AgentSession, deps: Deps, agent: WaypointAgent
) -> None:
    """Wire session events to the fence, the metrics log and the visualiser."""

    @session.on("speech_created")
    def _on_speech(ev: Any) -> None:
        handle = getattr(ev, "speech_handle", None)
        if handle is None:
            return
        try:
            handle.add_done_callback(agent._on_speech_done)
        except Exception:
            logger.debug("could not attach speech done callback", exc_info=True)

    @session.on("agent_state_changed")
    def _on_agent_state(ev: Any) -> None:
        deps.publish({"type": "state", "who": "agent", "state": str(ev.new_state)})

    @session.on("user_state_changed")
    def _on_user_state(ev: Any) -> None:
        deps.publish({"type": "state", "who": "user", "state": str(ev.new_state)})

    @session.on("user_input_transcribed")
    def _on_transcript(ev: Any) -> None:
        if getattr(ev, "is_final", False):
            deps.publish(
                {"type": "transcript", "who": "user", "text": str(ev.transcript)}
            )

    @session.on("error")
    def _on_error(ev: Any) -> None:
        logger.error("session error: %s", getattr(ev, "error", ev))
        deps.publish({"type": "error", "detail": str(getattr(ev, "error", ev))})


def attach_client_measurements(room: rtc.Room, deps: Deps) -> None:
    """Record the browser's own measurements into the metrics log.

    The console times its audio output going silent after the driver starts
    speaking. That number includes the last network hop and the client jitter
    buffer, so it is the one the driver actually experiences -- the agent's
    server-side flush is earlier and therefore flattering.

    Both are kept, tagged with different :class:`Boundary` values, and
    :class:`~waypoint.metrics.MetricsLog` will not aggregate across them. The
    browser is not a trusted source of truth, so a malformed or implausible
    payload is dropped rather than recorded.
    """

    @room.on("data_received")
    def _on_data(packet: Any) -> None:
        if getattr(packet, "topic", None) != "waypoint.client":
            return
        try:
            payload = json.loads(bytes(packet.data).decode("utf-8"))
        except Exception:
            return
        if payload.get("type") != "client_measurement":
            return
        try:
            value = float(payload["value_ms"])
            metric = str(payload["metric"])[:64]
            boundary = Boundary(str(payload.get("boundary", "client_playout")))
        except (KeyError, TypeError, ValueError):
            return
        if not (0.0 <= value <= 60_000.0):
            return
        deps.metrics.record(
            f"client.{metric}", value, boundary, source="browser"
        )
        logger.info("client measurement %s = %.0f ms", metric, value)


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    settings = load_settings()
    settings.require_runtime_keys()
    print(settings.banner(), flush=True)

    deps = Deps(
        settings=settings,
        backend=make_backend(
            latency_ms=settings.dispatch_latency_ms,
            jitter_ms=settings.dispatch_jitter_ms,
        ),
        fence=TurnFence(),
        heard=HeardTracker(),
        metrics=MetricsLog(),
        room=ctx.room,
    )
    agent = WaypointAgent(deps)
    deps.fence._on_record = agent._on_record  # noqa: SLF001 - deliberate wiring

    ctx.log_context_fields = {"room": ctx.room.name}
    session = build_session(settings, deps)
    attach_observers(session, deps, agent)
    attach_client_measurements(ctx.room, deps)

    async def _dump() -> None:
        """Write the session's audit trail so a run leaves evidence behind."""
        logger.info("fence stats: %s", deps.fence.stats())
        out = session_evidence_dir()
        try:
            out.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%S")
            (out / f"fence-{stamp}.json").write_text(
                deps.fence.audit_json(), encoding="utf-8"
            )
            deps.metrics.write(out / f"metrics-{stamp}.json")
            (out / f"heard-{stamp}.json").write_text(
                json.dumps(
                    {
                        "utterances": len(deps.heard_log),
                        "interrupted": sum(1 for h in deps.heard_log if h.interrupted),
                        "records": [h.to_dict() for h in deps.heard_log],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            logger.info("wrote session evidence to %s", out)
        except OSError:
            # Loud, and with the path in it. This is the only artifact proving
            # a real session happened; a swallowed failure here is the
            # difference between having recorded evidence and thinking you did.
            logger.warning(
                "COULD NOT WRITE SESSION EVIDENCE to %s -- the recording has no "
                "audit trail. Set WAYPOINT_EVIDENCE_DIR to a writable path.",
                out,
                exc_info=True,
            )

    # Said before the session starts, not after it ends: the operator needs to
    # know where to look while they are still set up to record.
    logger.info("session evidence will be written to %s", session_evidence_dir())
    ctx.add_shutdown_callback(_dump)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


def _print_config() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    print(settings.banner())
    missing = settings.missing_keys()
    if missing:
        print(
            "\nNot runnable yet - missing: " + ", ".join(missing)
            + "\nCopy .env.example to .env.local and fill it in."
        )
        return 1
    print("\nAll required credentials present. Run `python scripts/preflight.py` next.")
    return 0


def main() -> None:
    if "--print-config" in sys.argv:
        raise SystemExit(_print_config())
    cli.run_app(server)


if __name__ == "__main__":
    main()
