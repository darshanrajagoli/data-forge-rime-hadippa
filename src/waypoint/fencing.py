"""Turn-fenced tool execution.

The problem this solves
-----------------------
A voice agent that supports barge-in has a race condition that a text agent
does not. When the driver interrupts mid-turn, three things are already in
flight:

1. Rime is streaming audio for a sentence the driver will never finish hearing.
2. One or more tool calls issued for the *superseded* turn are still running.
3. The chat context is about to record an assistant turn asserting that the
   driver heard the whole utterance.

LiveKit handles (1): it stops playout. Nothing in the stack handles (2) or (3).
When a stale tool result lands after the interruption, a naive agent speaks it
("The ETA to Oak Street is fourteen minutes") even though the driver has
already changed the destination, and commits its side effects.

For a driver with both hands on the wheel, that is not a cosmetic bug. It is a
delivery to the wrong address.

The fence
---------
:class:`TurnFence` is a monotonic generation counter with a single admission
gate.

* Every tool call is stamped, at issue time, with the current generation.
* Barge-in bumps the generation.
* Every tool result must pass :meth:`TurnFence.admit` before it may be spoken
  or committed. A result whose stamp is older than the current generation is
  fenced.

``admit()`` is the *only* place in the application where a tool result becomes
speakable. That is deliberate: the invariant is enforced at one choke point
rather than sprinkled across call sites, so it can be tested exhaustively
(``tests/test_fencing.py``) and audited at runtime (:meth:`TurnFence.records`).

Re-anchoring
------------
Discarding everything on every interruption is safe but wasteful, and it is not
what the driver wants. If the driver says "what's the ETA to Oak Street -- and
also tell me the traffic", the ETA lookup is still wanted; only the utterance
was superseded.

So each tool declares a :class:`ReanchorPolicy`. A pure read whose arguments
are unchanged in the new turn is *re-anchored*: the in-flight result is handed
to the new turn instead of being thrown away and re-issued. Side-effecting
tools never re-anchor.

This means the safety mechanism pays for itself. A fence that only ever
discarded work would cost latency; re-anchoring turns the fence into a
cross-turn deduplicating cache, so the common "user refines their request"
interruption gets *faster*, not slower. See ``evidence/measure_reanchor.py``.

Accounting invariant
--------------------
Every issued ticket resolves exactly once, into exactly one terminal
disposition::

    issued == delivered + reanchored + fenced_stale
                        + fenced_cancelled + fenced_terminal + in_flight

:meth:`TurnFence.assert_accounting` checks this identity. It is asserted after
every operation in the fuzz test, so a leaked or double-delivered ticket fails
the suite rather than reaching a driver.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence

__all__ = [
    "Disposition",
    "ReanchorPolicy",
    "ToolTicket",
    "FenceDecision",
    "FenceRecord",
    "TurnFence",
    "args_fingerprint",
]


# --------------------------------------------------------------------------
# Value types
# --------------------------------------------------------------------------


class ReanchorPolicy(str, Enum):
    """How a tool's in-flight result may be reused after a turn boundary.

    The policy is a property of the *tool*, not of the call, and it is a safety
    declaration: choosing wrongly here is the only way to defeat the fence, so
    the default is the conservative one.
    """

    #: Safe default. The result is discarded when superseded. Correct for any
    #: read whose value may have changed, and for anything cheap to redo.
    DISCARD = "discard"

    #: The result may be handed to the new turn if some live ticket in the
    #: current generation requests the same tool with identical arguments.
    #: Only ever correct for side-effect-free reads.
    REANCHOR_IF_ARGS_MATCH = "reanchor_if_args_match"

    #: The result may never cross a turn boundary under any circumstances.
    #: Correct for irreversible commits: dispatching a driver, charging a card,
    #: sending a message to a customer.
    NEVER = "never"


class Disposition(str, Enum):
    """Terminal outcome of a tool ticket. Exactly one per ticket."""

    #: Result arrived within its own generation. Speak it, commit it.
    DELIVERED = "delivered"

    #: Result was superseded but a live ticket in the current generation wanted
    #: exactly this. Speak it, commit it, re-attributed to the new turn.
    REANCHORED = "reanchored"

    #: Result was superseded by a barge-in. Never spoken, never committed.
    FENCED_STALE = "fenced_stale"

    #: Ticket was cancelled before it resolved (turn abandoned, session closed).
    FENCED_CANCELLED = "fenced_cancelled"

    #: Result was superseded and the tool is declared NEVER re-anchorable.
    #: Distinguished from FENCED_STALE because it is the disposition that
    #: protects against irreversible side effects, and we want it visible
    #: in the audit log rather than blended into ordinary staleness.
    FENCED_TERMINAL = "fenced_terminal"


#: Dispositions that permit the result to reach the driver.
_ADMITTING = frozenset({Disposition.DELIVERED, Disposition.REANCHORED})


def args_fingerprint(args: Mapping[str, Any] | None) -> str:
    """Stable fingerprint of a tool's arguments.

    Used to decide whether a superseded result answers the question the new
    turn is asking. Key order and whitespace are normalised so that two calls
    that mean the same thing compare equal; values are compared by their JSON
    form, which is the form they crossed the LLM boundary in anyway.
    """
    if not args:
        return "0" * 16
    try:
        blob = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        blob = repr(sorted(args.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ToolTicket:
    """A claim check for one in-flight tool call, stamped with its generation."""

    ticket_id: str
    tool_name: str
    args: Mapping[str, Any]
    args_fp: str
    generation: int
    policy: ReanchorPolicy
    issued_at: float
    #: Identity of the turn that issued this call -- in practice the LiveKit
    #: ``SpeechHandle.id``. A generation counter orders turns, but once a
    #: barge-in has advanced the counter it cannot also express "and that
    #: particular turn is dead". Without this, a *second* tool issued by an
    #: already-interrupted turn is stamped with the new generation and looks
    #: fresh. Empty string means "not tied to a turn".
    origin: str = ""

    def describe(self) -> str:
        at = f"@gen{self.generation}"
        return f"{self.tool_name}#{self.ticket_id[:8]}{at}"


@dataclass(frozen=True)
class FenceDecision:
    """The verdict from :meth:`TurnFence.admit`.

    ``speak`` and ``commit`` are separate because they are separate boundaries.
    A result may in principle be worth committing but not worth speaking; the
    fence keeps the distinction available rather than collapsing it, and the
    agent checks the one that matches what it is about to do.
    """

    disposition: Disposition
    speak: bool
    commit: bool
    ticket: ToolTicket
    observed_generation: int
    latency_ms: float
    detail: str = ""
    #: When the disposition is REANCHORED, the live ticket that this result
    #: satisfies. The caller should resolve that ticket instead of re-running.
    satisfies: ToolTicket | None = None

    @property
    def admitted(self) -> bool:
        return self.disposition in _ADMITTING


@dataclass(frozen=True)
class FenceRecord:
    """One immutable audit-log line. Written on every terminal disposition."""

    ticket_id: str
    tool_name: str
    args_fp: str
    issued_generation: int
    observed_generation: int
    disposition: Disposition
    issued_at: float
    resolved_at: float
    latency_ms: float
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "tool": self.tool_name,
            "args_fp": self.args_fp,
            "issued_generation": self.issued_generation,
            "observed_generation": self.observed_generation,
            "disposition": self.disposition.value,
            "issued_at": round(self.issued_at, 6),
            "resolved_at": round(self.resolved_at, 6),
            "latency_ms": round(self.latency_ms, 3),
            "detail": self.detail,
        }


@dataclass
class _GenerationMark:
    generation: int
    at: float
    reason: str


# --------------------------------------------------------------------------
# The fence
# --------------------------------------------------------------------------


class FenceError(RuntimeError):
    """Raised on misuse of the fence that would break its guarantees."""


class TurnFence:
    """Monotonic generation fence guarding tool results in a barge-in agent.

    Thread-safe. All public methods are non-blocking and safe to call from an
    asyncio event loop; the lock exists so that a tool result resolving on a
    worker thread cannot interleave with a barge-in on the loop thread.

    Parameters
    ----------
    clock:
        Monotonic time source, injectable so tests are deterministic and do
        not sleep.
    on_record:
        Optional sink called with each :class:`FenceRecord` as it is written.
        Used by the agent to stream the audit log to the demo visualiser.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        on_record: Callable[[FenceRecord], None] | None = None,
    ) -> None:
        self._clock = clock
        self._on_record = on_record
        self._lock = threading.RLock()
        self._generation = 0
        self._seq = 0
        self._live: dict[str, ToolTicket] = {}
        self._resolved: set[str] = set()
        self._retired: set[str] = set()
        self._records: list[FenceRecord] = []
        self._marks: list[_GenerationMark] = [
            _GenerationMark(0, self._clock(), "session_start")
        ]

    # -- generation ------------------------------------------------------

    @property
    def generation(self) -> int:
        """The generation currently accepting results."""
        with self._lock:
            return self._generation

    def bump(self, reason: str = "user_barge_in") -> int:
        """Advance the generation. Call this the instant a barge-in is detected.

        Everything in flight becomes stale as of this call. Returns the new
        generation. Monotonic: the generation never decreases, so a result can
        never be un-staled by a later event.
        """
        with self._lock:
            self._generation += 1
            self._marks.append(
                _GenerationMark(self._generation, self._clock(), reason)
            )
            return self._generation

    def bump_for(self, cause: str, reason: str = "user_barge_in") -> int:
        """Idempotent bump, keyed by cause.

        A single barge-in is observable from several places: the session's
        ``user_state_changed`` event, the speech handle's done callback, and a
        direct read of ``ctx.speech_handle.interrupted`` inside a running tool.
        All three should be able to drive the fence without racing to
        double-increment it, so the bump is keyed by the thing that caused it
        (in practice the ``SpeechHandle`` id) and only the first caller wins.

        This is what lets the agent poll ``speech_handle.interrupted``
        synchronously at each boundary instead of subscribing to an event and
        hoping it lands first. See ``agent.py``.
        """
        with self._lock:
            already = cause in self._retired
            self._retired.add(cause)
            if already:
                return self._generation
            return self.bump(reason)

    def marks(self) -> list[dict[str, Any]]:
        """Generation-change history, for the evidence log."""
        with self._lock:
            return [
                {"generation": m.generation, "at": round(m.at, 6), "reason": m.reason}
                for m in self._marks
            ]

    # -- ticket lifecycle ------------------------------------------------

    def issue(
        self,
        tool_name: str,
        args: Mapping[str, Any] | None = None,
        policy: ReanchorPolicy = ReanchorPolicy.DISCARD,
        origin: str = "",
    ) -> ToolTicket:
        """Stamp a tool call with the current generation.

        Must be called *before* the tool starts, on the same thread that
        observed the generation, so that a barge-in racing the issue is
        ordered rather than lost.
        """
        with self._lock:
            self._seq += 1
            ticket = ToolTicket(
                ticket_id=f"t{self._seq:06d}",
                tool_name=tool_name,
                args=dict(args or {}),
                args_fp=args_fingerprint(args),
                generation=self._generation,
                policy=policy,
                issued_at=self._clock(),
                origin=origin,
            )
            self._live[ticket.ticket_id] = ticket
            return ticket

    def admit(
        self,
        ticket: ToolTicket,
        *,
        live_args: Mapping[str, Any] | None = None,
    ) -> FenceDecision:
        """The gate. Decide whether a resolved tool result may reach the driver.

        This is the single choke point. Nothing in the agent speaks or commits
        a tool result without a :class:`FenceDecision` from here whose
        ``speak`` / ``commit`` flag is true.

        Parameters
        ----------
        ticket:
            The ticket returned by :meth:`issue` for this call.
        live_args:
            Optional explicit override for re-anchor matching. When omitted
            (the normal path) the fence looks for a live ticket in the current
            generation requesting the same tool with the same arguments, which
            is what actually happens when the driver refines a request.

        Raises
        ------
        FenceError
            If the ticket was never issued by this fence, or has already been
            resolved. At-most-once delivery is a guarantee, not a convention,
            so a double-admit is a bug that fails loudly rather than speaking
            twice.
        """
        with self._lock:
            now = self._clock()
            latency_ms = (now - ticket.issued_at) * 1000.0

            if ticket.ticket_id in self._resolved:
                raise FenceError(
                    f"ticket {ticket.describe()} already resolved; "
                    "admit() is at-most-once"
                )
            if ticket.ticket_id not in self._live:
                raise FenceError(
                    f"ticket {ticket.describe()} was not issued by this fence"
                )

            current = self._generation
            why = self._supersession_reason(ticket, current)

            # Fast path: the turn that asked is still the turn that is talking.
            if why is None:
                return self._resolve(
                    ticket,
                    Disposition.DELIVERED,
                    current,
                    latency_ms,
                    detail="in-generation",
                )

            # Superseded. What happens next depends on the tool's declared
            # policy, never on the call site.
            if ticket.policy is ReanchorPolicy.NEVER:
                return self._resolve(
                    ticket,
                    Disposition.FENCED_TERMINAL,
                    current,
                    latency_ms,
                    detail=f"policy=never; {why}",
                )

            if ticket.policy is ReanchorPolicy.REANCHOR_IF_ARGS_MATCH:
                # A retired origin does not block re-anchoring. The requesting
                # turn is dead, but the *data* is a pure read with identical
                # arguments that a live turn is asking for right now, so
                # handing it over is both safe and the whole point.
                target = self._find_reanchor_target(ticket, live_args, current)
                if target is not None:
                    return self._resolve(
                        ticket,
                        Disposition.REANCHORED,
                        current,
                        latency_ms,
                        detail=f"re-anchored despite {why}",
                        satisfies=target,
                    )

            return self._resolve(
                ticket,
                Disposition.FENCED_STALE,
                current,
                latency_ms,
                detail=why,
            )

    def check(self, ticket: ToolTicket) -> FenceDecision:
        """Non-terminal peek: is this ticket still current *right now*?

        Call this at the **effect boundary** -- immediately before an
        irreversible operation -- not just at the speech boundary.

        This distinction is the whole reason the fence exists rather than
        relying on task cancellation. When LiveKit detects a barge-in it calls
        ``cancel_and_wait`` on the tool executor task, which raises
        ``CancelledError`` inside the tool at its next await point. That is
        fine for a read. It is *not* a safety mechanism for a write, because
        the write may already have committed: cancelling a coroutine after its
        HTTP POST returned does not un-dispatch the driver, un-send the SMS or
        un-mark the delivery.

        So a side-effecting tool checks the fence, performs the effect, and
        only then admits the result. The window between check and effect is
        the residual risk, and it is bounded by one network call rather than
        by the whole tool duration. ``docs/THREAT_MODEL.md`` states this limit
        explicitly rather than claiming the fence is atomic.

        Does not resolve the ticket and writes no audit record; the ticket must
        still reach exactly one of :meth:`admit` or :meth:`cancel`.
        """
        with self._lock:
            now = self._clock()
            latency_ms = (now - ticket.issued_at) * 1000.0
            current = self._generation
            if ticket.ticket_id in self._resolved:
                return FenceDecision(
                    disposition=Disposition.FENCED_CANCELLED,
                    speak=False,
                    commit=False,
                    ticket=ticket,
                    observed_generation=current,
                    latency_ms=latency_ms,
                    detail="already-resolved",
                )
            why = self._supersession_reason(ticket, current)
            fresh = why is None
            return FenceDecision(
                disposition=(
                    Disposition.DELIVERED if fresh else Disposition.FENCED_STALE
                ),
                speak=fresh,
                commit=fresh,
                ticket=ticket,
                observed_generation=current,
                latency_ms=latency_ms,
                detail="peek (non-terminal)" if fresh else f"peek: {why}",
            )

    def cancel(self, ticket: ToolTicket, detail: str = "cancelled") -> FenceDecision:
        """Resolve a ticket as cancelled without running the admission logic.

        Idempotent in effect but not in bookkeeping: cancelling an already
        resolved ticket is a no-op that returns the fenced decision, because
        the caller racing a cancel against a result is normal and should not
        crash the session.
        """
        with self._lock:
            now = self._clock()
            latency_ms = (now - ticket.issued_at) * 1000.0
            if ticket.ticket_id in self._resolved:
                return FenceDecision(
                    disposition=Disposition.FENCED_CANCELLED,
                    speak=False,
                    commit=False,
                    ticket=ticket,
                    observed_generation=self._generation,
                    latency_ms=latency_ms,
                    detail="already-resolved",
                )
            if ticket.ticket_id not in self._live:
                raise FenceError(
                    f"ticket {ticket.describe()} was not issued by this fence"
                )
            return self._resolve(
                ticket,
                Disposition.FENCED_CANCELLED,
                self._generation,
                latency_ms,
                detail=detail,
            )

    def cancel_generation(self, generation: int, detail: str = "turn_abandoned") -> int:
        """Cancel every live ticket issued at or before ``generation``.

        Called when a turn is abandoned outright (session close, driver hangs
        up) so that no ticket leaks and the accounting identity still holds.
        """
        with self._lock:
            doomed = [
                t for t in self._live.values() if t.generation <= generation
            ]
            for t in doomed:
                self.cancel(t, detail=detail)
            return len(doomed)

    # -- introspection ---------------------------------------------------

    def in_flight(self) -> list[ToolTicket]:
        with self._lock:
            return sorted(self._live.values(), key=lambda t: t.ticket_id)

    def records(self) -> list[FenceRecord]:
        with self._lock:
            return list(self._records)

    def stats(self) -> dict[str, int]:
        """Counts by disposition, plus ``issued`` and ``in_flight``."""
        with self._lock:
            out = {d.value: 0 for d in Disposition}
            for r in self._records:
                out[r.disposition.value] += 1
            out["issued"] = self._seq
            out["in_flight"] = len(self._live)
            return out

    def assert_accounting(self) -> None:
        """Assert the exactly-once identity. Raises :class:`FenceError`.

        Called after every operation in the fuzz test. A leaked ticket or a
        double resolution fails here rather than in a driver's ear.
        """
        with self._lock:
            s = self.stats()
            terminal = (
                s[Disposition.DELIVERED.value]
                + s[Disposition.REANCHORED.value]
                + s[Disposition.FENCED_STALE.value]
                + s[Disposition.FENCED_CANCELLED.value]
                + s[Disposition.FENCED_TERMINAL.value]
            )
            if terminal + s["in_flight"] != s["issued"]:
                raise FenceError(
                    "fence accounting broken: "
                    f"terminal={terminal} in_flight={s['in_flight']} "
                    f"issued={s['issued']}"
                )
            if len(self._records) != len(self._resolved):
                raise FenceError(
                    "fence accounting broken: records "
                    f"({len(self._records)}) != resolved ({len(self._resolved)})"
                )

    def audit_json(self) -> str:
        """The full audit log, for ``RIME_EVIDENCE.md`` and the results dir."""
        with self._lock:
            return json.dumps(
                {
                    "generation": self._generation,
                    "marks": self.marks(),
                    "stats": self.stats(),
                    "records": [r.to_dict() for r in self._records],
                },
                indent=2,
            )

    # -- internals -------------------------------------------------------

    def _supersession_reason(self, ticket: ToolTicket, current: int) -> str | None:
        """Why this ticket is stale, or ``None`` if it is still current.

        Supersession has two independent causes and both are needed.

        *Generation* orders turns: a ticket issued before the latest barge-in
        belongs to an older turn.

        *Origin retirement* marks one specific turn dead. It is needed because
        the generation counter advances only once per barge-in: a *second*
        tool issued by an already-interrupted turn would be stamped with the
        new generation and would look fresh. That is not hypothetical -- it is
        what acceptance scenario A2 does, and it is how this branch was found.
        """
        if ticket.origin and ticket.origin in self._retired:
            return f"origin {ticket.origin!r} retired (turn interrupted)"
        if ticket.generation < current:
            return f"superseded gen{ticket.generation}->gen{current}"
        return None

    def _find_reanchor_target(
        self,
        ticket: ToolTicket,
        live_args: Mapping[str, Any] | None,
        current: int,
    ) -> ToolTicket | None:
        """Find a live ticket in the current generation this result satisfies.

        Explicit ``live_args`` wins when supplied (tests, and call sites that
        know the new turn's intent directly). Otherwise we match against the
        registry, which is the real behaviour: the new turn has already issued
        its own ticket for the same lookup, and we can satisfy it for free.
        """
        if live_args is not None:
            return (
                ticket
                if args_fingerprint(live_args) == ticket.args_fp
                else None
            )
        for cand in self._live.values():
            if cand.ticket_id == ticket.ticket_id:
                continue
            if (
                cand.generation == current
                and cand.tool_name == ticket.tool_name
                and cand.args_fp == ticket.args_fp
                and not (cand.origin and cand.origin in self._retired)
                # The target must itself be re-anchorable. Without this, a
                # stale read could be handed to a live NEVER-policy ticket
                # with the same name and arguments, quietly satisfying a
                # request that was declared un-re-anchorable. Tool policies are
                # fixed per tool today, so this is not reachable through the
                # agent -- but the invariant should hold because the fence
                # enforces it, not because the call sites happen to agree.
                and cand.policy is ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
            ):
                return cand
        return None

    def _resolve(
        self,
        ticket: ToolTicket,
        disposition: Disposition,
        observed_generation: int,
        latency_ms: float,
        detail: str = "",
        satisfies: ToolTicket | None = None,
    ) -> FenceDecision:
        """Write the terminal record. Called with the lock held."""
        self._live.pop(ticket.ticket_id, None)
        self._resolved.add(ticket.ticket_id)
        record = FenceRecord(
            ticket_id=ticket.ticket_id,
            tool_name=ticket.tool_name,
            args_fp=ticket.args_fp,
            issued_generation=ticket.generation,
            observed_generation=observed_generation,
            disposition=disposition,
            issued_at=ticket.issued_at,
            resolved_at=self._clock(),
            latency_ms=latency_ms,
            detail=detail,
        )
        self._records.append(record)
        if self._on_record is not None:
            try:
                self._on_record(record)
            except Exception:  # pragma: no cover - a broken sink must not
                pass          # break the fence; observability is not safety
        admitted = disposition in _ADMITTING
        return FenceDecision(
            disposition=disposition,
            speak=admitted,
            commit=admitted,
            ticket=ticket,
            observed_generation=observed_generation,
            latency_ms=latency_ms,
            detail=detail,
            satisfies=satisfies,
        )


def summarise(records: Sequence[FenceRecord] | Iterable[FenceRecord]) -> dict[str, Any]:
    """Aggregate an audit log into the numbers that go in the evidence file."""
    records = list(records)
    by_disp: dict[str, int] = {}
    latencies: list[float] = []
    for r in records:
        by_disp[r.disposition.value] = by_disp.get(r.disposition.value, 0) + 1
        latencies.append(r.latency_ms)
    latencies.sort()

    def pct(p: float) -> float:
        """Nearest-rank, ceil-based. Matches waypoint.metrics.percentile exactly;
        two different percentile definitions in one evidence file is a way to
        publish two different numbers for the same thing."""
        if not latencies:
            return 0.0
        rank = math.ceil((p / 100.0) * len(latencies))
        idx = max(0, min(len(latencies) - 1, rank - 1))
        return round(latencies[idx], 2)

    return {
        "total": len(records),
        "by_disposition": by_disp,
        "tool_latency_ms": {
            "p50": pct(50),
            "p95": pct(95),
            "max": round(latencies[-1], 2) if latencies else 0.0,
        },
    }
