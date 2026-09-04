"""Measurement discipline.

The property under test is structural: it must be impossible to produce a
number that silently mixes a cold run with a warm one, or a server-side flush
with a client-side playout. The Rime brief asks for exactly that separation,
and a number that violates it is worse than no number at all.
"""

from __future__ import annotations

import json

import pytest

from waypoint.metrics import Boundary, MetricsLog, Sample, Series, Stopwatch, Warmth, percentile


@pytest.fixture
def log() -> MetricsLog:
    return MetricsLog("test-run")


# --------------------------------------------------------------------------
# Percentiles
# --------------------------------------------------------------------------


def test_percentile_is_nearest_rank() -> None:
    """ceil(p/100 * n) th value, 1-indexed. n=10: p50 -> 5th, p95 -> 10th."""
    vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert percentile(vals, 50) == 50
    assert percentile(vals, 95) == 100
    assert percentile(vals, 100) == 100
    assert percentile(vals, 0) == 10


def test_percentile_does_not_depend_on_sample_count_parity() -> None:
    """Python's round() is banker's rounding; ceil is not, so p50 stays stable
    as one more sample arrives rather than flipping on parity."""
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5, 6], 50) == 3


def test_percentile_of_empty_is_zero() -> None:
    assert percentile([], 95) == 0.0


def test_percentile_of_one_value() -> None:
    assert percentile([42.0], 95) == 42.0


def test_percentile_does_not_interpolate() -> None:
    """Interpolation would invent precision a 20-sample run does not have."""
    assert percentile([1.0, 2.0], 50) in (1.0, 2.0)


# --------------------------------------------------------------------------
# Warmth
# --------------------------------------------------------------------------


def test_first_sample_is_cold_and_the_rest_are_warm(log: MetricsLog) -> None:
    a = log.record("ttfb", 900, Boundary.CLIENT_FIRST_AUDIO)
    b = log.record("ttfb", 300, Boundary.CLIENT_FIRST_AUDIO)
    c = log.record("ttfb", 280, Boundary.CLIENT_FIRST_AUDIO)
    assert a.warmth is Warmth.COLD
    assert b.warmth is Warmth.WARM and c.warmth is Warmth.WARM


def test_warmth_is_tracked_per_name_and_boundary(log: MetricsLog) -> None:
    assert log.record("x", 1, Boundary.SERVER_FLUSH).warmth is Warmth.COLD
    assert log.record("x", 1, Boundary.CLIENT_PLAYOUT).warmth is Warmth.COLD
    assert log.record("x", 1, Boundary.SERVER_FLUSH).warmth is Warmth.WARM


def test_warmth_can_be_forced(log: MetricsLog) -> None:
    s = log.record("x", 1, Boundary.IN_PROCESS, warmth=Warmth.WARM)
    assert s.warmth is Warmth.WARM


def test_cold_and_warm_never_share_a_series(log: MetricsLog) -> None:
    """The structural guarantee. A cold outlier cannot pollute a warm p95."""
    log.record("ttfb", 2000, Boundary.CLIENT_FIRST_AUDIO)   # cold
    for _ in range(9):
        log.record("ttfb", 300, Boundary.CLIENT_FIRST_AUDIO)  # warm

    series = {(s.name, s.warmth): s for s in log.series()}
    cold = series[("ttfb", Warmth.COLD)]
    warm = series[("ttfb", Warmth.WARM)]

    assert cold.n == 1 and cold.p50_ms if False else cold.n == 1
    assert warm.n == 9
    assert warm.summary()["max_ms"] == 300
    assert cold.summary()["max_ms"] == 2000


def test_boundaries_never_share_a_series(log: MetricsLog) -> None:
    log.record("stop", 120, Boundary.SERVER_FLUSH)
    log.record("stop", 210, Boundary.CLIENT_PLAYOUT)
    assert len(log.series()) == 2


# --------------------------------------------------------------------------
# Summaries
# --------------------------------------------------------------------------


def test_summary_flags_small_samples(log: MetricsLog) -> None:
    for _ in range(4):
        log.record("x", 100, Boundary.IN_PROCESS, warmth=Warmth.WARM)
    s = log.series()[0].summary()
    assert "caution" in s
    assert "indicative" in s["caution"]


def test_summary_drops_the_caution_at_ten_samples(log: MetricsLog) -> None:
    for _ in range(12):
        log.record("x", 100, Boundary.IN_PROCESS, warmth=Warmth.WARM)
    assert "caution" not in log.series()[0].summary()


def test_summary_has_stdev_from_two_samples(log: MetricsLog) -> None:
    log.record("x", 100, Boundary.IN_PROCESS, warmth=Warmth.WARM)
    log.record("x", 200, Boundary.IN_PROCESS, warmth=Warmth.WARM)
    assert "stdev_ms" in log.series()[0].summary()


def test_empty_series_summary_is_honest() -> None:
    s = Series("x", Boundary.IN_PROCESS, Warmth.WARM).summary()
    assert s["n"] == 0 and s["note"] == "no samples"


def test_every_boundary_is_documented_in_the_summary(log: MetricsLog) -> None:
    """A number whose measurement point is not explained is not evidence."""
    log.record("x", 1, Boundary.CLIENT_PLAYOUT)
    docs = log.summary()["boundaries_explained"]
    assert set(docs) == {b.value for b in Boundary}
    assert "driver actually experiences" in docs["client_playout"]
    assert "optimistic" in docs["server_flush"]


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------


def test_json_round_trips(log: MetricsLog) -> None:
    log.record("ttfb", 412.5, Boundary.CLIENT_FIRST_AUDIO, note="hello")
    parsed = json.loads(log.to_json())
    assert parsed["summary"]["run_id"] == "test-run"
    assert parsed["samples"][0]["value_ms"] == 412.5
    assert parsed["samples"][0]["boundary"] == "client_first_audio"
    assert parsed["samples"][0]["meta"]["note"] == "hello"


def test_write_creates_parent_directories(log: MetricsLog, tmp_path) -> None:
    log.record("x", 1, Boundary.IN_PROCESS)
    out = log.write(tmp_path / "deep" / "nested" / "metrics.json")
    assert out.exists()
    assert json.loads(out.read_text())["summary"]["n_samples"] == 1


def test_samples_filter_by_name(log: MetricsLog) -> None:
    log.record("a", 1, Boundary.IN_PROCESS)
    log.record("b", 2, Boundary.IN_PROCESS)
    assert len(log.samples("a")) == 1
    assert len(log.samples()) == 2


def test_run_id_is_generated_when_absent() -> None:
    assert MetricsLog().run_id


# --------------------------------------------------------------------------
# Stopwatch
# --------------------------------------------------------------------------


def test_stopwatch_context_manager(log: MetricsLog) -> None:
    with Stopwatch(log, "span", Boundary.IN_PROCESS) as sw:
        sum(range(10_000))
    assert sw.sample is not None
    assert sw.sample.value_ms >= 0
    assert log.samples("span")


def test_stopwatch_manual_with_extra_meta(log: MetricsLog) -> None:
    sw = Stopwatch(log, "span", Boundary.IN_PROCESS, tool="eta_to").start()
    s = sw.stop(disposition="delivered")
    assert s.meta == {"tool": "eta_to", "disposition": "delivered"}


def test_sample_is_immutable() -> None:
    s = Sample("x", 1.0, Boundary.IN_PROCESS)
    with pytest.raises(Exception):
        s.value_ms = 2.0  # type: ignore[misc]
