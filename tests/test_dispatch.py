"""The synthetic dispatch backend.

Two things matter here: that the mutation log is trustworthy (the fence tests
assert against it, so a broken log would make those tests lie), and that stop
resolution copes with what speech recognition actually hands over.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from waypoint.dispatch import (
    DEFAULT_MANIFEST_PATH,
    DispatchError,
    load_manifest,
    make_backend,
)


@pytest.fixture
def backend():
    return make_backend()


# --------------------------------------------------------------------------
# Resolution: what STT actually gives you
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    ["Gough", "gough", "Gough Street", "gough st", "GOUGH STREET", "S1", "s1"],
)
def test_a_stop_resolves_from_the_many_ways_it_gets_said(backend, ref: str) -> None:
    assert backend.manifest.resolve(ref).stop_id == "S1"


@pytest.mark.parametrize(
    "ordinal,expected",
    [("next", "S1"), ("first", "S1"), ("second", "S2"), ("third", "S3"), ("last", "S8")],
)
def test_ordinals(backend, ordinal: str, expected: str) -> None:
    assert backend.manifest.resolve(ordinal).stop_id == expected


def test_unknown_street_raises_a_domain_error(backend) -> None:
    with pytest.raises(DispatchError, match="Nonexistent"):
        backend.manifest.resolve("Nonexistent Boulevard")


def test_empty_reference_raises(backend) -> None:
    with pytest.raises(DispatchError):
        backend.manifest.resolve("")


def test_next_follows_delivery_progress(backend) -> None:
    import asyncio

    assert backend.manifest.resolve("next").stop_id == "S1"
    asyncio.get_event_loop_policy()
    # mark S1 delivered synchronously through the manifest
    stop = backend.manifest.by_id("S1")
    idx = backend.manifest.stops.index(stop)
    from waypoint.dispatch import Stop

    backend.manifest.stops[idx] = Stop(**{**stop.to_dict(), "status": "delivered"})
    assert backend.manifest.resolve("next").stop_id == "S2"


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


async def test_route_eta_is_deterministic(backend) -> None:
    """A re-anchored result must be provably identical to a re-run one.

    If ETAs were random, re-anchoring would be unfalsifiable: you could never
    show the handed-over value was the same as the value you skipped computing.
    """
    a = await backend.route_eta("Gough")
    b = await backend.route_eta("Gough")
    assert a == b
    assert a["eta_minutes"] > 0


async def test_different_stops_get_different_etas(backend) -> None:
    a = await backend.route_eta("Gough")
    b = await backend.route_eta("Haight")
    assert a["eta_minutes"] != b["eta_minutes"]


async def test_access_notes_carry_the_gate_code(backend) -> None:
    notes = await backend.access_notes("Gough")
    assert notes["gate_code"] == "4417"
    assert notes["unit"] == "4B"


async def test_remaining_stops_starts_full(backend) -> None:
    assert len(await backend.remaining_stops()) == 8


async def test_reads_leave_no_mutations(backend) -> None:
    await backend.route_eta("Gough")
    await backend.access_notes("Gough")
    await backend.remaining_stops()
    await backend.get_stop("next")
    assert backend.mutations() == []


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------


async def test_mark_delivered_is_logged_and_durable(backend) -> None:
    await backend.mark_delivered("Gough", "left at door", at_generation=3)
    (m,) = backend.mutations("mark_delivered")
    assert m.stop_id == "S1"
    assert m.detail == "left at door"
    assert m.at_generation == 3
    assert backend.manifest.by_id("S1").status == "delivered"


async def test_double_delivery_is_refused(backend) -> None:
    await backend.mark_delivered("Gough")
    with pytest.raises(DispatchError, match="already delivered"):
        await backend.mark_delivered("Gough")


async def test_reschedule_changes_status(backend) -> None:
    await backend.reschedule("Haight", "nobody home")
    assert backend.manifest.by_id("S2").status == "rescheduled"
    assert backend.mutations("reschedule")[0].detail == "nobody home"


async def test_notify_recipient_is_logged(backend) -> None:
    await backend.notify_recipient("Gough", "five minutes away")
    assert backend.mutations("notify_recipient")[0].detail == "five minutes away"


async def test_mutations_filter_by_op(backend) -> None:
    await backend.mark_delivered("Gough")
    await backend.notify_recipient("Haight", "hi")
    assert len(backend.mutations()) == 2
    assert len(backend.mutations("mark_delivered")) == 1


def test_reset_log(backend) -> None:
    backend.log.append(backend.log.__class__())  # type: ignore[arg-type]
    backend.reset_log()
    assert backend.mutations() == []


# --------------------------------------------------------------------------
# Latency
# --------------------------------------------------------------------------


async def test_latency_is_actually_awaited() -> None:
    """The stale-result race exists only because tools are slow."""
    import time

    b = make_backend(latency_ms=60.0)
    t0 = time.perf_counter()
    await b.route_eta("Gough")
    assert (time.perf_counter() - t0) * 1000 >= 50


async def test_jitter_is_seeded_and_reproducible() -> None:
    a = make_backend(latency_ms=1.0, jitter_ms=10.0)
    b = make_backend(latency_ms=1.0, jitter_ms=10.0)
    assert a._rng.random() == b._rng.random()


# --------------------------------------------------------------------------
# The data itself
# --------------------------------------------------------------------------


def test_manifest_ships_with_the_package() -> None:
    assert DEFAULT_MANIFEST_PATH.exists()


def test_manifest_is_labelled_synthetic() -> None:
    """The Rime brief requires synthetic or de-identified data. Say so in the file."""
    raw = json.loads(Path(DEFAULT_MANIFEST_PATH).read_text(encoding="utf-8"))
    assert "SYNTHETIC" in raw["_comment"].upper()


def test_no_real_looking_personal_data() -> None:
    """Recipients are placeholders; there are no phone numbers or emails."""
    raw = Path(DEFAULT_MANIFEST_PATH).read_text(encoding="utf-8")
    assert "@" not in raw
    for stop in load_manifest().stops:
        assert stop.recipient.startswith("Recipient ")


def test_manifest_covers_the_hard_street_names() -> None:
    """The pronunciation work needs a corpus that is genuinely hard."""
    from waypoint.pronounce import LEXICON

    hard = {e.token.lower() for e in LEXICON}
    streets = {s.street.split()[0].lower() for s in load_manifest().stops}
    assert len(streets & hard) >= 6


def test_address_line_is_the_written_form() -> None:
    stop = load_manifest().by_id("S1")
    assert stop.address_line == "1247 Gough Street Unit 4B, San Francisco"


def test_stops_are_sequenced_without_gaps() -> None:
    seqs = [s.sequence for s in load_manifest().stops]
    assert seqs == list(range(1, len(seqs) + 1))
