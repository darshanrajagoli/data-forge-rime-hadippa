"""The layer that decides what actually ships.

``build_tts`` and ``build_session`` translate :class:`Settings` into the two
objects that determine which Rime model speaks, over which transport, at which
sample rate, and **whether barge-in is switched on at all**. Roughly 220 lines
of `agent.py` that every other test walked straight past.

That gap was found by mutation testing, and it was not subtle. Setting
``interruption {"enabled": False}`` in ``build_session`` disables the only
feature this product has, and before this file existed the entire suite stayed
green, all six acceptance scenarios passed, and the original mutation harness
still reported 15/15. Nothing anywhere noticed that the product had been turned
off.

The tests below assert against *constructed objects*, not against the
`Settings` they came from. That distinction is the whole point: a test that
reads `settings.rime_model` and compares it to `settings.rime_model` proves
nothing. These read `tts.model`, `tts._ws_url()` and
`session.options.turn_handling` -- what the framework will actually use.

``inference.STT`` requires LiveKit credentials at construction, so
:func:`env` supplies placeholders. No network call is made by any test here.

Every test that builds an ``AgentSession`` is ``async``. That is not
decoration: ``AgentSession.__init__`` calls ``asyncio.get_event_loop()``, which
raises once an earlier async test has closed the loop and left none current.
Written synchronously these passed in isolation and failed in a full run --
order-dependent flakiness, which is worse than a plain failure because it looks
like a fluke.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import waypoint.agent

from waypoint.agent import attach_observers, build_session, build_tts, Deps
from waypoint.config import (
    RIME_HTTP_ENDPOINT,
    RIME_WS_ENDPOINT,
    Settings,
    load_settings,
)
from waypoint.dispatch import make_backend
from waypoint.fencing import TurnFence
from waypoint.heard import HeardTracker
from waypoint.metrics import MetricsLog
from waypoint.pronounce import Strategy


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Placeholder credentials. ``inference.STT`` refuses to construct without."""
    monkeypatch.setenv("LIVEKIT_URL", "wss://placeholder.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "placeholder-livekit-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "placeholder-livekit-secret-value")
    monkeypatch.setenv("RIME_API_KEY", "placeholder-rime-key")
    for k in ("RIME_MODEL", "RIME_SPEAKER", "RIME_USE_WEBSOCKET", "RIME_LANG",
              "RIME_SAMPLE_RATE", "RIME_BASE_URL", "WAYPOINT_PRONUNCIATION",
              "WAYPOINT_INTERRUPTION_MODE", "WAYPOINT_MIN_INTERRUPTION_DURATION",
              "WAYPOINT_PREEMPTIVE_GENERATION"):
        monkeypatch.delenv(k, raising=False)


def deps(settings: Settings) -> Deps:
    return Deps(
        settings=settings,
        backend=make_backend(),
        fence=TurnFence(),
        heard=HeardTracker(),
        metrics=MetricsLog("wiring"),
    )


# --------------------------------------------------------------------------
# build_tts: the Rime configuration that reaches the wire
# --------------------------------------------------------------------------


def test_build_tts_uses_the_model_and_voice_it_discloses() -> None:
    """`build_tts`'s docstring claims the shipped and disclosed configs
    "cannot drift apart". This is the assertion that makes that true."""
    s = load_settings()
    tts = build_tts(s)

    assert tts.model == s.rime_model
    url = tts._ws_url()
    assert f"modelId={s.rime_model}" in url
    assert f"speaker={s.rime_speaker}" in url
    assert f"samplingRate={s.rime_sample_rate}" in url
    assert f"lang={s.rime_lang}" in url


#: Every combination of the two variables that decide the transport. The
#: fourth row is the one that broke: the plugin upgrades a `false` flag from
#: the URL scheme, so Waypoint disclosed HTTP, warned about a degradation that
#: was not happening, and -- worse than either -- passed
#: `use_tts_aligned_transcript=False`, declining word timestamps that were
#: already on the wire.
#:
#: Written as a cross-product rather than as the one failing case on purpose.
#: The previous test opened by asserting the shipped default and therefore
#: excluded exactly the configuration that was wrong.
TRANSPORT_MATRIX = [
    (True, None),
    (True, "wss://users-ws.rime.ai"),
    (True, "ws://localhost:9000"),
    (True, "https://users.rime.ai/v1/rime-tts"),
    (False, None),
    (False, "wss://users-ws.rime.ai"),
    (False, "ws://localhost:9000"),
    (False, "https://users.rime.ai/v1/rime-tts"),
]


@pytest.mark.parametrize("flag,base_url", TRANSPORT_MATRIX)
def test_the_disclosed_transport_is_the_one_the_plugin_uses(
    flag: bool, base_url: str | None
) -> None:
    """Checked against the installed plugin, not against our own belief.

    `capabilities.streaming` is what the framework dispatches on, so it is the
    ground truth for which transport a configuration actually gets. If Rime
    changes the inference rule, this fails instead of the banner going quietly
    wrong.
    """
    s = Settings(
        rime_use_websocket=flag,
        rime_base_url=base_url,
        rime_api_key="placeholder-rime-key",
    )
    actual = build_tts(s).capabilities.streaming
    assert s.effective_use_websocket is actual, (
        f"RIME_USE_WEBSOCKET={flag}, RIME_BASE_URL={base_url!r}: "
        f"disclosing {s.transport} but the plugin streams={actual}"
    )
    assert (s.transport == "WebSocket (wss)") is actual
    assert ("exact" in s.heard_method) is actual


@pytest.mark.parametrize("flag,base_url", TRANSPORT_MATRIX)
def test_word_timestamps_are_requested_exactly_when_available(
    flag: bool, base_url: str | None
) -> None:
    """The functional half of the same bug.

    `use_tts_aligned_transcript` is what routes TimedStrings into
    `transcription_node`, and therefore what makes heard-not-said exact rather
    than estimated. Reading the raw flag here silently downgraded it.
    """
    s = Settings(
        rime_use_websocket=flag,
        rime_base_url=base_url,
        rime_api_key="placeholder-rime-key",
    )
    streaming = build_tts(s).capabilities.streaming
    assert s.effective_use_websocket is streaming
    src = inspect.getsource(build_session)
    assert "use_tts_aligned_transcript=settings.effective_use_websocket" in src, (
        "build_session must key aligned transcripts off the effective "
        "transport, not the raw flag"
    )


def test_build_tts_transport_matches_the_setting() -> None:
    s = load_settings()
    assert build_tts(s).capabilities.streaming is s.effective_use_websocket

    http = Settings(rime_use_websocket=False, rime_api_key="placeholder-rime-key")
    assert build_tts(http).capabilities.streaming is False


@pytest.mark.parametrize("flag,base_url", TRANSPORT_MATRIX)
def test_the_disclosed_endpoint_is_the_one_that_will_be_called(
    flag: bool, base_url: str | None
) -> None:
    """The disclosure bug, pinned.

    ``Settings.endpoint`` is printed in the startup banner, served by
    ``/api/config``, rendered in the browser console two lines under the
    speech-provider badge, and stated in the README as one of the six fields
    the brief names explicitly. It previously reported the HTTP host on every
    run while streaming over the WebSocket one.

    Every row is checked, including the overrides -- the earlier version of
    this test asserted the shipped default first and so never reached them.
    """
    s = Settings(
        rime_use_websocket=flag,
        rime_base_url=base_url,
        rime_api_key="placeholder-rime-key",
    )
    tts = build_tts(s)
    if tts.capabilities.streaming:
        actual = tts._ws_url().split("?")[0]
    else:
        actual = tts._base_url
    assert s.endpoint == actual, f"disclosing {s.endpoint} but calling {actual}"


def test_websocket_and_http_are_different_hosts() -> None:
    """Not two paths on one host -- a genuinely different endpoint."""
    from urllib.parse import urlparse

    assert urlparse(RIME_WS_ENDPOINT).hostname != urlparse(RIME_HTTP_ENDPOINT).hostname
    assert RIME_WS_ENDPOINT.startswith("wss://")
    assert RIME_HTTP_ENDPOINT.startswith("https://")


def test_endpoint_constants_match_the_plugin() -> None:
    """Vendor drift must fail the suite, not the disclosure.

    ``config.py`` duplicates these so it stays free of the LiveKit dependency.
    This is the check that keeps the duplicate honest: if Rime moves a host and
    the plugin follows, this fails instead of the banner quietly going stale.
    """
    from livekit.plugins.rime.tts import RIME_BASE_URL, RIME_WS_BASE_URL

    assert RIME_HTTP_ENDPOINT == RIME_BASE_URL
    assert RIME_WS_ENDPOINT == RIME_WS_BASE_URL + "/ws3"


def test_an_explicit_base_url_override_is_disclosed(monkeypatch) -> None:
    """The disclosed URL is the one the socket is opened against.

    Note the ``/ws3``: that suffix is the plugin's, not ours -- on the
    WebSocket path it builds ``f"{base_url}/ws3?{params}"``. Disclosing the
    bare host the operator typed would be disclosing a URL nothing calls,
    which is the same class of error as naming the wrong host.
    """
    monkeypatch.setenv("RIME_BASE_URL", "wss://custom.example.test")
    s = load_settings()
    assert s.endpoint == "wss://custom.example.test/ws3"
    assert s.to_dict()["rime"]["base_url_source"] == "RIME_BASE_URL override"

    tts = build_tts(Settings(**{**s.__dict__, "rime_api_key": "placeholder-rime-key"}))
    assert s.endpoint == tts._ws_url().split("?")[0]


def test_an_http_override_is_disclosed_without_a_ws3_suffix(monkeypatch) -> None:
    monkeypatch.setenv("RIME_USE_WEBSOCKET", "false")
    monkeypatch.setenv("RIME_BASE_URL", "https://custom.example.test/v1/rime-tts")
    s = load_settings()
    assert s.effective_use_websocket is False
    assert s.endpoint == "https://custom.example.test/v1/rime-tts"


def test_a_ws_override_does_not_warn_about_a_degradation_that_is_not_happening(
    monkeypatch,
) -> None:
    """The banner is screen-recorded. It said heard-not-said had fallen back
    to the estimator while word timestamps were arriving normally."""
    monkeypatch.setenv("RIME_USE_WEBSOCKET", "false")
    monkeypatch.setenv("RIME_BASE_URL", "wss://users-ws.rime.ai")
    s = load_settings()
    joined = " ".join(s.warnings)
    assert "falls back to the approximate duration estimator" not in joined
    assert "overridden by RIME_BASE_URL" in joined
    assert s.heard_method.startswith("word_timestamps")


def test_a_websocket_flag_against_an_http_url_is_called_out(monkeypatch) -> None:
    """`use_websocket=True` beats the scheme, so the plugin opens a WebSocket
    against an HTTP path. That cannot work; say so before the first word."""
    monkeypatch.setenv("RIME_USE_WEBSOCKET", "true")
    monkeypatch.setenv("RIME_BASE_URL", "https://users.rime.ai/v1/rime-tts")
    joined = " ".join(load_settings().warnings)
    assert "WebSocket handshake against" in joined


def test_bracket_controls_are_only_set_on_models_that_honour_them() -> None:
    """Coda ignores them. Setting them there would be a silent no-op, which is
    the exact failure the pronunciation layer exists to prevent."""
    coda = Settings(rime_model="coda", rime_api_key="placeholder-rime-key")
    assert coda.supports_brackets is False
    build_tts(coda)  # must not raise

    mist = Settings(
        rime_model="mistv2", rime_speaker="cove", pause_ms=200,
        pronunciation=Strategy.PHONEME, rime_api_key="placeholder-rime-key",
    )
    assert mist.supports_brackets is True
    build_tts(mist)


# --------------------------------------------------------------------------
# build_session: whether the product's only feature is switched on
# --------------------------------------------------------------------------


async def test_barge_in_is_enabled() -> None:
    """The mutation that started this file.

    Disabling interruption turns Waypoint into a text agent that talks. Every
    other test, all six acceptance scenarios and the original mutation harness
    passed with it off.
    """
    s = load_settings()
    interruption = build_session(s, deps(s)).options.turn_handling["interruption"]

    assert interruption["enabled"] is True
    assert interruption["mode"] == s.interruption_mode
    assert interruption["min_duration"] == s.min_interruption_duration
    assert interruption["min_words"] == s.min_interruption_words


async def test_barge_in_threshold_is_not_absurd() -> None:
    """A ten-second threshold is 'enabled' and useless. Bound it."""
    s = load_settings()
    d = build_session(s, deps(s)).options.turn_handling["interruption"]["min_duration"]
    assert 0.05 <= d <= 1.5, f"min_duration={d}s is not a usable barge-in threshold"


async def test_false_interruption_recovery_is_configured() -> None:
    """Road noise will fire the detector. The agent has to resume."""
    s = load_settings()
    i = build_session(s, deps(s)).options.turn_handling["interruption"]
    assert i["resume_false_interruption"] is s.resume_false_interruption
    assert i["false_interruption_timeout"] == s.false_interruption_timeout


async def test_aligned_transcripts_are_requested() -> None:
    """This is what routes Rime's word timestamps into transcription_node,
    and therefore the whole of sub-claim (c)."""
    s = load_settings()
    assert build_session(s, deps(s)).options.use_tts_aligned_transcript is True


async def test_markdown_and_emoji_are_filtered_before_speech() -> None:
    """The LLM writes asterisks. A driver should never hear one."""
    s = load_settings()
    transforms = build_session(s, deps(s)).options.tts_text_transforms
    assert "filter_emoji" in transforms
    assert "filter_markdown" in transforms


async def test_preemptive_generation_follows_the_setting() -> None:
    s = load_settings()
    pg = build_session(s, deps(s)).options.turn_handling["preemptive_generation"]
    assert pg["enabled"] is s.preemptive_generation


async def test_session_is_built_with_the_configured_models() -> None:
    s = load_settings()
    session = build_session(s, deps(s))
    assert session.llm is not None
    assert session.stt is not None
    assert session.tts is not None
    assert session.tts.model == s.rime_model


# --------------------------------------------------------------------------
# attach_observers
# --------------------------------------------------------------------------


async def test_attach_observers_registers_every_handler() -> None:
    """A silent observer layer means an empty fence board on camera."""
    from waypoint.agent import WaypointAgent

    s = load_settings()
    d = deps(s)
    session = build_session(s, d)
    agent = WaypointAgent(d)

    attach_observers(session, d, agent)

    for event in ("speech_created", "agent_state_changed", "user_state_changed",
                  "user_input_transcribed", "error"):
        assert session._events.get(event), f"no handler registered for {event}"


def test_publish_survives_having_no_room() -> None:
    """Observability must never be able to break a session."""
    s = load_settings()
    d = deps(s)
    d.publish({"type": "fence", "anything": True})  # must not raise


# --------------------------------------------------------------------------
# Where a live run leaves its evidence
#
# This was the only CWD-relative path in the repository. Every other site --
# scripts/, evidence/, web/ -- resolves a ROOT from __file__. The agent is
# started as `python -m waypoint.agent dev` from wherever the operator is
# standing, and the write failure was swallowed by `except OSError`, so the
# one path that captures proof a real session happened is the one that could
# silently put it outside the repository.
# --------------------------------------------------------------------------


def test_session_evidence_lands_in_the_repository_whatever_the_cwd(
    tmp_path, monkeypatch
) -> None:
    from waypoint.agent import session_evidence_dir

    monkeypatch.delenv("WAYPOINT_EVIDENCE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    out = session_evidence_dir()

    assert out.is_absolute()
    assert tmp_path not in out.parents, "followed the working directory"
    assert out.parts[-3:] == ("evidence", "results", "sessions")

    root = Path(waypoint.agent.__file__).resolve().parents[2]
    assert out == root / "evidence" / "results" / "sessions"


def test_the_evidence_directory_can_be_overridden(tmp_path, monkeypatch) -> None:
    """For a non-editable install, where parents[2] lands in site-packages."""
    from waypoint.agent import session_evidence_dir

    monkeypatch.setenv("WAYPOINT_EVIDENCE_DIR", str(tmp_path / "elsewhere"))
    assert session_evidence_dir() == (tmp_path / "elsewhere").resolve()


def test_the_operator_is_told_where_the_evidence_goes_before_recording() -> None:
    """Logged at session start, not only at shutdown. Knowing the path after
    the take is over is knowing it too late."""
    src = inspect.getsource(waypoint.agent.entrypoint)
    announce = src.index("session evidence will be written to")
    register = src.index("add_shutdown_callback")
    assert announce < register
