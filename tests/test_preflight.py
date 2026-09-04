"""The gate that decides whether the demo may be recorded.

``scripts/preflight.py`` is what ``DEMO_SCRIPT.md`` names as instruction one:
*"Run these and do not proceed until all three are clean."* It is also what
``SUBMISSION.md``'s eligibility checklist points at for the brief's
model/voice/language preflight requirement. Until this file existed it had no
tests at all, and it showed:

* ``check_rime`` called ``tts.synthesize()``, which the Rime plugin refuses on
  the shipped WebSocket configuration. The gate could never pass, in any
  configuration, with any credential.
* Its "WebSocket transport in use" check read a config flag and reported PASS
  without opening a socket.
* Its word-timestamp check was a loop over attributes that do not exist on the
  event, so it never counted anything and never failed.

All three were reporting green on checks that measured nothing. These tests
drive ``check_rime`` with a stubbed synthesis so every branch is exercised
without a credential or a network call.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "evidence"))

import preflight  # noqa: E402
from _rime import Rendered, WordTiming  # noqa: E402

from waypoint.config import Settings  # noqa: E402


def settings(**kw) -> Settings:
    base = dict(
        rime_model="coda", rime_speaker="lyra", rime_sample_rate=22050,
        rime_use_websocket=True, rime_api_key="placeholder-rime-key",
    )
    base.update(kw)
    return Settings(**base)


def good(**kw) -> Rendered:
    """A healthy render: audio, on the WebSocket path, with word timings."""
    base = dict(
        text="Next stop.", transport="websocket", frames=12,
        pcm=b"\x10\x20" * 22050, first_frame_ms=180.0,
        timings=[WordTiming("Next", 0.0, 240.0), WordTiming("stop.", 240.0, 520.0)],
    )
    base.update(kw)
    return Rendered(**base)


async def run(monkeypatch, settings_obj, rendered) -> preflight.Report:
    """Drive check_rime with a stubbed synthesis. No network, no credential."""
    async def fake_synth(_tts, _text, **_kw):
        return rendered

    monkeypatch.setattr(preflight, "synth", fake_synth)
    monkeypatch.setattr(
        "waypoint.agent.build_tts", lambda s: object(), raising=True
    )
    report = preflight.Report()
    await preflight.check_rime(report, settings_obj)
    return report


def labels(report: preflight.Report, status: str) -> list[str]:
    return [label for st, label, _ in report.rows if st == status]


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


async def test_a_healthy_render_passes_every_check(monkeypatch) -> None:
    r = await run(monkeypatch, settings(), good())
    assert r.failed == 0, labels(r, "FAIL")
    passed = " | ".join(labels(r, "PASS"))
    assert "synthesises" in passed
    assert "WebSocket transport exercised end to end" in passed
    assert "word timestamps arrived" in passed


# --------------------------------------------------------------------------
# Zero frames must fail. This is the check the gate exists for.
# --------------------------------------------------------------------------


async def test_zero_audio_frames_fails(monkeypatch) -> None:
    r = await run(monkeypatch, settings(), good(frames=0, pcm=b"", timings=[]))
    assert r.failed >= 1
    assert "Rime returned audio" in labels(r, "FAIL")


async def test_a_provider_error_fails_and_names_the_endpoint(monkeypatch) -> None:
    """The remediation text used to blame the API key for a code bug."""
    err = Rendered(text="x", transport="websocket", error="APIStatusError: 401")
    r = await run(monkeypatch, settings(), err)
    assert r.failed >= 1
    detail = next(d for st, _, d in r.rows if st == "FAIL")
    assert "401" in detail
    assert "wss://users-ws.rime.ai/ws3" in detail, "must name the endpoint it tried"
    assert "websocket" in detail, "must name the transport it attempted"


# --------------------------------------------------------------------------
# Check 5: the transport that was used, not the one configured
# --------------------------------------------------------------------------


async def test_a_silent_fallback_to_http_is_a_failure(monkeypatch) -> None:
    """Configured for WebSocket, answered over HTTP: the disclosure is now a lie.

    The previous implementation read ``settings.rime_use_websocket`` and
    printed PASS, so this exact situation certified itself as correct.
    """
    r = await run(monkeypatch, settings(), good(transport="http", timings=[]))
    assert r.failed >= 1
    assert "shipped transport was the one exercised" in labels(r, "FAIL")


async def test_configured_http_reports_a_warning_not_a_pass(monkeypatch) -> None:
    s = settings(rime_use_websocket=False)
    r = await run(monkeypatch, s, good(transport="http", timings=[]))
    assert r.failed == 0
    warned = " | ".join(labels(r, "WARN"))
    assert "WebSocket transport exercised end to end" in warned


# --------------------------------------------------------------------------
# Check 6: word timestamps, which sub-claim (c) depends on
# --------------------------------------------------------------------------


async def test_missing_word_timestamps_on_the_websocket_path_fails(monkeypatch) -> None:
    """Silent degradation to the estimator is exactly what must not pass."""
    r = await run(monkeypatch, settings(), good(timings=[]))
    assert r.failed >= 1
    assert "word timestamps arrived" in labels(r, "FAIL")


async def test_missing_word_timestamps_on_http_is_only_a_warning(monkeypatch) -> None:
    s = settings(rime_use_websocket=False)
    r = await run(monkeypatch, s, good(transport="http", timings=[]))
    assert r.failed == 0
    assert "word timestamps arrived" in labels(r, "WARN")


async def test_the_first_timed_word_is_reported(monkeypatch) -> None:
    """A judge should be able to see that timings are real, not a boolean."""
    r = await run(monkeypatch, settings(), good())
    detail = next(d for st, label, d in r.rows if label == "word timestamps arrived")
    assert "2 words timed" in detail
    assert "'Next'" in detail


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


async def test_a_slow_cold_first_frame_warns_rather_than_fails(monkeypatch) -> None:
    r = await run(monkeypatch, settings(), good(first_frame_ms=3200.0))
    assert r.failed == 0
    assert any("first audio frame" in label for label in labels(r, "WARN"))


async def test_audio_is_checked_for_being_silence(monkeypatch) -> None:
    r = await run(monkeypatch, settings(), good())
    detail = next(d for st, label, d in r.rows if "synthesises" in label)
    assert "RMS" in detail, "a run that returns silence should be visible"


def test_report_exit_semantics() -> None:
    r = preflight.Report()
    assert r.failed == 0 and r.warned == 0
    r.ok("fine")
    r.warn("noted")
    assert r.failed == 0 and r.warned == 1
    r.fail("broken")
    assert r.failed == 1
