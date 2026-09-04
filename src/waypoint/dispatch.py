"""Synthetic dispatch backend.

Everything here is fabricated. No real customer, address, phone number or
delivery exists in this repository, and none is fetched at runtime. The
addresses are real *street names* in San Francisco paired with invented house
numbers, because the pronunciation work in :mod:`waypoint.pronounce` needs a
corpus of genuinely hard street names to be worth anything -- "Gough" and
"Haight" are the point. Names attached to stops are placeholders.

The backend exists to make the fence testable under realistic conditions. Two
properties matter and both are configurable:

``latency_ms``
    Lookups take real wall-clock time. The stale-result race only exists
    because tools are slow; a mock that returns instantly cannot reproduce it.

``side_effecting``
    Some operations mutate durable state. Those are the ones that must never
    cross a turn boundary, and the ones cancellation cannot protect, because
    by the time ``CancelledError`` arrives the write has landed.

:class:`DispatchBackend` records every mutation in :attr:`DispatchBackend.log`
so tests can assert that a fenced write genuinely did not happen, rather than
asserting only that nothing was spoken.
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "Stop",
    "Manifest",
    "DispatchBackend",
    "DispatchError",
    "MutationRecord",
    "load_manifest",
    "DEFAULT_MANIFEST_PATH",
]

DEFAULT_MANIFEST_PATH = Path(__file__).parent / "data" / "manifest.json"


class DispatchError(RuntimeError):
    """A dispatch operation that failed for a domain reason, not a bug."""


@dataclass(frozen=True)
class Stop:
    """One delivery stop on the driver's manifest."""

    stop_id: str
    sequence: int
    house_number: str
    street: str
    unit: str | None
    city: str
    recipient: str
    access_note: str
    gate_code: str | None
    window_start: str
    window_end: str
    status: str = "pending"
    lat: float = 0.0
    lon: float = 0.0

    @property
    def address_line(self) -> str:
        """Written form. Use :func:`waypoint.pronounce.speak_address` for audio."""
        unit = f" Unit {self.unit}" if self.unit else ""
        return f"{self.house_number} {self.street}{unit}, {self.city}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Manifest:
    """The driver's route for the shift."""

    driver_id: str
    vehicle: str
    shift_date: str
    stops: list[Stop]

    def by_id(self, stop_id: str) -> Stop:
        for s in self.stops:
            if s.stop_id.lower() == stop_id.lower():
                return s
        raise DispatchError(f"no stop {stop_id!r} on this manifest")

    def by_street(self, street: str) -> Stop:
        """Resolve a stop the way a driver refers to one: by street name.

        Matching is loose on purpose. Speech recognition will hand us "gough"
        or "gough street" or "golf" for the same utterance, and a driver never
        says the stop id out loud.
        """
        needle = street.strip().lower()
        needle = _strip_suffix(needle)
        if not needle:
            raise DispatchError("no street given")
        for s in self.stops:
            if _strip_suffix(s.street.lower()) == needle:
                return s
        for s in self.stops:
            if needle in s.street.lower() or s.street.lower() in needle:
                return s
        raise DispatchError(f"no stop on {street!r} in today's manifest")

    def resolve(self, ref: str) -> Stop:
        """Resolve by stop id, street, or ordinal ('next', 'first', 'third')."""
        ref = (ref or "").strip()
        if not ref:
            raise DispatchError("no stop reference given")
        low = ref.lower()
        ordinals = {
            "next": 0, "first": 0, "second": 1, "third": 2,
            "fourth": 3, "fifth": 4, "last": -1,
        }
        pending = [s for s in self.stops if s.status == "pending"]
        if low in ordinals:
            pool = pending or self.stops
            try:
                return pool[ordinals[low]]
            except IndexError:
                raise DispatchError("no such stop in the remaining route") from None
        try:
            return self.by_id(ref)
        except DispatchError:
            return self.by_street(ref)


def _strip_suffix(street: str) -> str:
    for suf in (
        " street", " st", " avenue", " ave", " boulevard", " blvd",
        " drive", " dr", " road", " rd", " way", " terrace", " ter",
    ):
        if street.endswith(suf):
            return street[: -len(suf)].strip()
    return street.strip()


@dataclass(frozen=True)
class MutationRecord:
    """One durable change, recorded so tests can assert it did or did not happen."""

    op: str
    stop_id: str
    detail: str
    at_generation: int | None = None


@dataclass
class DispatchBackend:
    """In-memory dispatch system with configurable latency.

    Parameters
    ----------
    manifest:
        The route.
    latency_ms:
        Base latency for every operation. The demo runs at 1800ms to make the
        race visible on camera; the test suite runs at 0 for speed and uses
        explicit fence manipulation instead of sleeping.
    jitter_ms:
        Uniform jitter added to the base latency.
    seed:
        Seeds the jitter RNG so evidence runs are reproducible.
    """

    manifest: Manifest
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    seed: int = 1729
    log: list[MutationRecord] = field(default_factory=list)
    #: Every backend round trip, read or write. Counted so that a claim about
    #: work being *avoided* can be checked by counting calls rather than by
    #: timing something and hoping the number means what we say it means.
    call_count: int = 0
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    async def _delay(self) -> None:
        self.call_count += 1
        total = self.latency_ms
        if self.jitter_ms:
            total += self._rng.uniform(0, self.jitter_ms)
        if total > 0:
            await asyncio.sleep(total / 1000.0)

    # -- reads (side-effect free, re-anchorable) -------------------------

    async def get_stop(self, ref: str) -> Stop:
        await self._delay()
        return self.manifest.resolve(ref)

    async def route_eta(self, ref: str) -> dict[str, Any]:
        """Minutes and distance to a stop. Deterministic given the manifest."""
        await self._delay()
        stop = self.manifest.resolve(ref)
        # Deterministic pseudo-ETA: stable across runs, varies across stops, so
        # a re-anchored result is provably the same value as a re-run one.
        base = 4 + (sum(ord(c) for c in stop.stop_id) % 17)
        return {
            "stop_id": stop.stop_id,
            "eta_minutes": base,
            "distance_miles": round(0.4 + (base % 7) * 0.35, 1),
            "street": stop.street,
        }

    async def access_notes(self, ref: str) -> dict[str, Any]:
        await self._delay()
        stop = self.manifest.resolve(ref)
        return {
            "stop_id": stop.stop_id,
            "access_note": stop.access_note,
            "gate_code": stop.gate_code,
            "unit": stop.unit,
        }

    async def remaining_stops(self) -> list[Stop]:
        await self._delay()
        return [s for s in self.manifest.stops if s.status == "pending"]

    # -- writes (durable, never re-anchorable) ---------------------------

    async def mark_delivered(
        self, ref: str, note: str = "", at_generation: int | None = None
    ) -> dict[str, Any]:
        """Irreversible. Closes the stop and notifies the customer."""
        await self._delay()
        stop = self.manifest.resolve(ref)
        if stop.status == "delivered":
            raise DispatchError(f"{stop.stop_id} is already delivered")
        idx = self.manifest.stops.index(stop)
        self.manifest.stops[idx] = Stop(**{**stop.to_dict(), "status": "delivered"})
        self.log.append(
            MutationRecord("mark_delivered", stop.stop_id, note, at_generation)
        )
        return {"stop_id": stop.stop_id, "status": "delivered"}

    async def reschedule(
        self, ref: str, reason: str, at_generation: int | None = None
    ) -> dict[str, Any]:
        """Irreversible. Pushes the stop to a later route and messages dispatch."""
        await self._delay()
        stop = self.manifest.resolve(ref)
        idx = self.manifest.stops.index(stop)
        self.manifest.stops[idx] = Stop(**{**stop.to_dict(), "status": "rescheduled"})
        self.log.append(
            MutationRecord("reschedule", stop.stop_id, reason, at_generation)
        )
        return {"stop_id": stop.stop_id, "status": "rescheduled", "reason": reason}

    async def notify_recipient(
        self, ref: str, message: str, at_generation: int | None = None
    ) -> dict[str, Any]:
        """Irreversible. Sends an SMS. Cannot be unsent."""
        await self._delay()
        stop = self.manifest.resolve(ref)
        self.log.append(
            MutationRecord("notify_recipient", stop.stop_id, message, at_generation)
        )
        return {"stop_id": stop.stop_id, "sent": True}

    # -- introspection ---------------------------------------------------

    def mutations(self, op: str | None = None) -> list[MutationRecord]:
        if op is None:
            return list(self.log)
        return [m for m in self.log if m.op == op]

    def reset_log(self) -> None:
        self.log.clear()
        self.call_count = 0


def load_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> Manifest:
    """Load the synthetic manifest shipped with the package."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Manifest(
        driver_id=data["driver_id"],
        vehicle=data["vehicle"],
        shift_date=data["shift_date"],
        stops=[Stop(**s) for s in data["stops"]],
    )


def make_backend(
    latency_ms: float = 0.0,
    jitter_ms: float = 0.0,
    path: str | Path = DEFAULT_MANIFEST_PATH,
) -> DispatchBackend:
    return DispatchBackend(
        manifest=load_manifest(path), latency_ms=latency_ms, jitter_ms=jitter_ms
    )
