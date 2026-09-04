"""Measurement, with the measurement boundary stated on every number.

The Rime brief is blunt about this: "measure what the user experiences, not a
convenient proxy", "distinguish model latency from network latency and warm
runs from cold runs", and "unverified performance numbers receive no credit".

So every sample carries three labels and nothing is aggregated across them:

``boundary``
    Where the stopwatch actually stopped. ``client_playout`` is the real one --
    the browser reporting when its audio output went silent, which is as close
    to the driver's ear as software can get. ``server_flush`` is when the agent
    stopped pushing frames, which is earlier by one network hop plus whatever
    the jitter buffer held. We report both and never quietly substitute the
    flattering one.

``warmth``
    ``cold`` is the first call of a session, when the TLS handshake, the
    WebSocket upgrade and any model load are still in the number. ``warm`` is
    everything after. Mixing them produces a p95 that describes nothing.

``run_id``
    Which evidence run produced it, so a number in ``RIME_EVIDENCE.md`` can be
    traced back to the JSON it came from.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "Boundary",
    "Warmth",
    "Sample",
    "Series",
    "MetricsLog",
    "Stopwatch",
    "percentile",
]


class Boundary(str, Enum):
    """Where a duration measurement stopped."""

    #: Browser reported its audio output actually went silent. Closest to the ear.
    CLIENT_PLAYOUT = "client_playout"
    #: Agent stopped pushing audio frames. Earlier than the ear by one hop.
    SERVER_FLUSH = "server_flush"
    #: First audio frame handed to the transport.
    SERVER_FIRST_FRAME = "server_first_frame"
    #: Browser rendered the first audible sample.
    CLIENT_FIRST_AUDIO = "client_first_audio"
    #: Purely in-process (tool duration, fence decision). No transport involved.
    IN_PROCESS = "in_process"


class Warmth(str, Enum):
    COLD = "cold"
    WARM = "warm"
    #: Not applicable (in-process measurements).
    NA = "n/a"


@dataclass(frozen=True)
class Sample:
    """One measurement. Immutable, self-describing, JSON-serialisable."""

    name: str
    value_ms: float
    boundary: Boundary
    warmth: Warmth = Warmth.NA
    run_id: str = ""
    at: float = field(default_factory=time.time)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["boundary"] = self.boundary.value
        d["warmth"] = self.warmth.value
        d["value_ms"] = round(self.value_ms, 3)
        d["at"] = round(self.at, 6)
        return d


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value at or above rank ceil(p/100 * n).

    Chosen over interpolation because with the sample counts an honest
    evidence run produces (tens, not thousands), an interpolated p95 invents
    precision that is not there.

    Uses ``ceil`` rather than ``round`` deliberately. Python's ``round`` is
    banker's rounding, so ``round(4.5) == 4`` but ``round(5.5) == 6``; a
    percentile whose answer depends on the parity of the sample count is not a
    number anyone should put in an evidence file.
    """
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    rank = math.ceil((p / 100.0) * n)
    k = max(0, min(n - 1, rank - 1))
    return round(s[k], 3)


@dataclass
class Series:
    """Samples sharing a name, boundary and warmth. The only unit we aggregate."""

    name: str
    boundary: Boundary
    warmth: Warmth
    values: list[float] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.values)

    def summary(self) -> dict[str, Any]:
        if not self.values:
            return {
                "name": self.name,
                "boundary": self.boundary.value,
                "warmth": self.warmth.value,
                "n": 0,
                "note": "no samples",
            }
        out = {
            "name": self.name,
            "boundary": self.boundary.value,
            "warmth": self.warmth.value,
            "n": self.n,
            "min_ms": round(min(self.values), 2),
            "p50_ms": percentile(self.values, 50),
            "p95_ms": percentile(self.values, 95),
            "max_ms": round(max(self.values), 2),
            "mean_ms": round(statistics.fmean(self.values), 2),
        }
        if self.n >= 2:
            out["stdev_ms"] = round(statistics.stdev(self.values), 2)
        if self.n < 10:
            out["caution"] = (
                f"n={self.n} is a small sample. Treat p95 as indicative, not "
                "as a service level. Reported because the brief asks for "
                "honest labelling of exploratory results, not because it is "
                "statistically settled."
            )
        return out


class MetricsLog:
    """Collects samples and writes the evidence JSON.

    Aggregation never crosses a (name, boundary, warmth) triple, so it is
    structurally impossible to produce a number that averages a cold run into
    a warm one or a server-side flush into a client-side playout.
    """

    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id or time.strftime("%Y%m%dT%H%M%S")
        self._samples: list[Sample] = []
        self._seen: set[tuple[str, str]] = set()

    def record(
        self,
        name: str,
        value_ms: float,
        boundary: Boundary,
        *,
        warmth: Warmth | None = None,
        **meta: Any,
    ) -> Sample:
        """Record one sample. Warmth is inferred as cold-on-first-sighting."""
        if warmth is None:
            key = (name, boundary.value)
            warmth = Warmth.COLD if key not in self._seen else Warmth.WARM
            self._seen.add(key)
        s = Sample(
            name=name,
            value_ms=float(value_ms),
            boundary=boundary,
            warmth=warmth,
            run_id=self.run_id,
            meta=dict(meta),
        )
        self._samples.append(s)
        return s

    def samples(self, name: str | None = None) -> list[Sample]:
        if name is None:
            return list(self._samples)
        return [s for s in self._samples if s.name == name]

    def series(self) -> list[Series]:
        buckets: dict[tuple[str, Boundary, Warmth], Series] = {}
        for s in self._samples:
            key = (s.name, s.boundary, s.warmth)
            if key not in buckets:
                buckets[key] = Series(s.name, s.boundary, s.warmth)
            buckets[key].values.append(s.value_ms)
        return [buckets[k] for k in sorted(buckets, key=lambda k: (k[0], k[1].value, k[2].value))]

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "n_samples": len(self._samples),
            "series": [s.summary() for s in self.series()],
            "boundaries_explained": {
                b.value: _BOUNDARY_DOC[b] for b in Boundary
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "summary": self.summary(),
                "samples": [s.to_dict() for s in self._samples],
            },
            indent=indent,
        )

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return p


_BOUNDARY_DOC: dict[Boundary, str] = {
    Boundary.CLIENT_PLAYOUT: (
        "Browser reported its audio output went silent. Includes network, "
        "jitter buffer and device latency. This is the number the driver "
        "actually experiences."
    ),
    Boundary.SERVER_FLUSH: (
        "Agent stopped handing frames to the transport. Excludes the last "
        "network hop and the client jitter buffer, so it is optimistic "
        "relative to the ear by roughly one RTT/2 plus buffer depth."
    ),
    Boundary.SERVER_FIRST_FRAME: (
        "First synthesised audio frame handed to the transport. Measures the "
        "STT+LLM+Rime pipeline, not what reached the speaker."
    ),
    Boundary.CLIENT_FIRST_AUDIO: (
        "Browser rendered the first audible sample. End-to-end perceived "
        "response time."
    ),
    Boundary.IN_PROCESS: (
        "Wholly inside the agent process. No transport involved, so no "
        "network component to separate out."
    ),
}


class Stopwatch:
    """A single timing span. Use as a context manager or start/stop manually."""

    __slots__ = ("_log", "_name", "_boundary", "_meta", "_t0", "_warmth", "sample")

    def __init__(
        self,
        log: MetricsLog,
        name: str,
        boundary: Boundary,
        warmth: Warmth | None = None,
        **meta: Any,
    ) -> None:
        self._log = log
        self._name = name
        self._boundary = boundary
        self._warmth = warmth
        self._meta = meta
        self._t0 = 0.0
        self.sample: Sample | None = None

    def start(self) -> "Stopwatch":
        self._t0 = time.perf_counter()
        return self

    def stop(self, **extra: Any) -> Sample:
        elapsed = (time.perf_counter() - self._t0) * 1000.0
        self.sample = self._log.record(
            self._name,
            elapsed,
            self._boundary,
            warmth=self._warmth,
            **{**self._meta, **extra},
        )
        return self.sample

    def __enter__(self) -> "Stopwatch":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()
