"""The agent's fence integration, driven directly.

These exercise the real :class:`WaypointAgent` methods against the real fence
and the real dispatch backend. The only fakes are the two LiveKit objects the
integration actually reads: a run context and a speech handle. That keeps the
tests honest -- they run the shipped code path, not a re-implementation of it
-- while needing no room, no network, no credentials and no audio device.

``_read`` and ``_write`` are where the framework meets the fence, so this is
the file that would catch a regression in the thing the demo claims.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from waypoint.agent import Deps, WaypointAgent
from waypoint.config import Settings
from waypoint.dispatch import DispatchError, make_backend
from waypoint.fencing import Disposition, ReanchorPolicy, TurnFence
from waypoint.heard import HeardTracker
from waypoint.metrics import MetricsLog
from waypoint.pronounce import Strategy


# --------------------------------------------------------------------------
# Minimal doubles for the two LiveKit objects the integration reads
# --------------------------------------------------------------------------


@dataclass
class FakeSpeechHandle:
    """Stands in for ``livekit.agents.voice.SpeechHandle``.

    The integration reads exactly two attributes off it, ``id`` and
    ``interrupted``, so those are the two this provides. Anything more would be
    modelling the framework rather than testing our use of it.
    """

    id: str = "speech-1"
    interrupted: bool = False


@dataclass
class FakeRunContext:
    speech_handle: FakeSpeechHandle


def build_agent(
    latency_ms: float = 0.0, pronunciation: Strategy = Strategy.RESPELL
) -> tuple[WaypointAgent, Deps]:
    settings = Settings(
        rime_model="coda",
        rime_speaker="lyra",
        pronunciation=pronunciation,
        dispatch_latency_ms=latency_ms,
        dispatch_jitter_ms=0.0,
        publish_fence_events=False,
    )
    deps = Deps(
        settings=settings,
        backend=make_backend(latency_ms=latency_ms),
        fence=TurnFence(),
        heard=HeardTracker(),
        metrics=MetricsLog("test"),
        room=None,
    )
    return WaypointAgent(deps), deps


@pytest.fixture
def agent_and_deps():
    return build_agent()


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


async def test_read_delivers_when_not_interrupted(agent_and_deps) -> None:
    agent, deps = agent_and_deps
    ctx = FakeRunContext(FakeSpeechHandle())

    out = await agent.eta_to(ctx, "Gough")

    assert "minutes" in out
    assert "SUPERSEDED" not in out
    assert deps.fence.stats()["delivered"] == 1
    deps.fence.assert_accounting()


async def test_read_after_barge_in_returns_the_superseded_marker(
    agent_and_deps,
) -> None:
    """The headline behaviour: a stale lookup never becomes a spoken value."""
    agent, deps = agent_and_deps
    handle = FakeSpeechHandle(interrupted=False)
    ctx = FakeRunContext(handle)

    async def barge_in_midway() -> str:
        # The driver starts talking while the lookup is in flight.
        handle.interrupted = True
        return await agent.eta_to(ctx, "Gough")

    out = await barge_in_midway()

    assert out.startswith("SUPERSEDED_RESULT")
    assert "14" not in out and "minutes" not in out
    assert deps.fence.stats()["fenced_stale"] == 1
    deps.fence.assert_accounting()


async def test_superseded_marker_is_an_instruction_not_a_value(
    agent_and_deps,
) -> None:
    """LiveKit retains the tool output in the chat context on an interrupted
    turn (``agent_activity.py``, "commit results of tools that finished despite
    the interruption"). So whatever we return *is* what the model reads on the
    next turn. It has to be self-describing, not a bare number.
    """
    agent, deps = agent_and_deps
    handle = FakeSpeechHandle()
    ctx = FakeRunContext(handle)
    handle.interrupted = True

    out = await agent.eta_to(ctx, "Gough")

    assert "Do not state it" in out
    assert "later turn" in out


async def test_read_reanchors_across_a_barge_in(agent_and_deps) -> None:
    """Driver refines rather than abandons: the in-flight lookup is reused."""
    agent, deps = agent_and_deps
    fence = deps.fence

    stale = fence.issue(
        "eta_to", {"destination": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
    )
    fence.bump("user_barge_in")
    live = fence.issue(
        "eta_to", {"destination": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
    )

    decision = fence.admit(stale)
    assert decision.disposition is Disposition.REANCHORED
    assert decision.satisfies is not None
    assert decision.satisfies.ticket_id == live.ticket_id
    fence.admit(live)
    fence.assert_accounting()


async def test_cancelled_read_resolves_the_ticket() -> None:
    """LiveKit cancels the tool task on barge-in; the ticket must not leak.

    Needs a slow backend so there is genuinely something in flight to cancel.
    """
    agent, deps = build_agent(latency_ms=200.0)
    ctx = FakeRunContext(FakeSpeechHandle())

    task = asyncio.create_task(agent.eta_to(ctx, "Gough"))
    await asyncio.sleep(0.02)
    assert deps.fence.stats()["in_flight"] == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    deps.fence.assert_accounting()
    assert deps.fence.stats()["in_flight"] == 0
    assert deps.fence.stats()["fenced_cancelled"] == 1


async def test_domain_error_is_spoken_not_raised(agent_and_deps) -> None:
    agent, deps = agent_and_deps
    ctx = FakeRunContext(FakeSpeechHandle())

    out = await agent.eta_to(ctx, "Nonexistent Boulevard")

    assert "did not work" in out
    deps.fence.assert_accounting()
    assert deps.fence.stats()["in_flight"] == 0


async def test_next_stop_speaks_a_pronounceable_address(agent_and_deps) -> None:
    agent, _ = agent_and_deps
    out = await agent.next_stop(FakeRunContext(FakeSpeechHandle()))
    assert "twelve forty-seven" in out
    assert "Goff" in out
    assert "Gough" not in out


async def test_access_notes_read_the_gate_code_as_digits(agent_and_deps) -> None:
    agent, _ = agent_and_deps
    out = await agent.access_notes(FakeRunContext(FakeSpeechHandle()), "Gough")
    assert "four four one seven" in out
    assert "thousand" not in out


async def test_stops_remaining(agent_and_deps) -> None:
    agent, _ = agent_and_deps
    out = await agent.stops_remaining(FakeRunContext(FakeSpeechHandle()))
    assert out.startswith("8 left")


# --------------------------------------------------------------------------
# Writes: the part cancellation cannot protect
# --------------------------------------------------------------------------


async def test_write_commits_when_current(agent_and_deps) -> None:
    agent, deps = agent_and_deps
    ctx = FakeRunContext(FakeSpeechHandle())

    out = await agent.mark_delivered(ctx, "Gough")

    assert "Marked S1 delivered" in out
    assert len(deps.backend.mutations("mark_delivered")) == 1


async def test_stale_write_is_refused_before_it_happens(agent_and_deps) -> None:
    """The effect boundary. Nothing durable may occur after supersession.

    This is the assertion that separates the fence from task cancellation:
    we check the backend's mutation log, not just what was said.
    """
    agent, deps = agent_and_deps
    handle = FakeSpeechHandle()
    ctx = FakeRunContext(handle)
    handle.interrupted = True

    out = await agent.mark_delivered(ctx, "Gough")

    assert out.startswith("REFUSED_STALE_WRITE")
    assert deps.backend.mutations() == [], "a superseded write reached the backend"
    assert deps.fence.stats()["fenced_terminal"] == 1
    deps.fence.assert_accounting()


async def test_stale_sms_is_never_sent(agent_and_deps) -> None:
    agent, deps = agent_and_deps
    handle = FakeSpeechHandle()
    handle.interrupted = True

    await agent.notify_recipient(FakeRunContext(handle), "Gough", "on my way")

    assert deps.backend.mutations("notify_recipient") == []


async def test_stale_reschedule_is_never_applied(agent_and_deps) -> None:
    agent, deps = agent_and_deps
    handle = FakeSpeechHandle()
    handle.interrupted = True

    await agent.reschedule_stop(FakeRunContext(handle), "Gough", "nobody home")

    assert deps.backend.mutations("reschedule") == []
    stop = deps.backend.manifest.by_id("S1")
    assert stop.status == "pending"


async def test_interruption_during_a_write_reports_committed_but_unconfirmed() -> None:
    """The honest case.

    If the driver interrupts *after* the write has been issued, the write
    lands. We do not pretend it did not. The model is told it happened and the
    driver did not hear the confirmation, so the next turn says so once.
    """
    agent, deps = build_agent(latency_ms=40.0)
    handle = FakeSpeechHandle()
    ctx = FakeRunContext(handle)

    task = asyncio.create_task(agent.mark_delivered(ctx, "Gough"))
    await asyncio.sleep(0.01)          # write is in flight, past the check
    handle.interrupted = True          # driver barges in
    out = await task

    assert out.startswith("COMMITTED_BUT_UNCONFIRMED")
    assert len(deps.backend.mutations("mark_delivered")) == 1, (
        "the write did happen; the agent must not claim otherwise"
    )
    assert "do it again" in out
    deps.fence.assert_accounting()


async def test_write_records_the_generation_it_committed_under() -> None:
    agent, deps = build_agent()
    await agent.mark_delivered(FakeRunContext(FakeSpeechHandle()), "Gough")
    assert deps.backend.mutations()[0].at_generation == 0


# --------------------------------------------------------------------------
# Bookkeeping across a whole conversation
# --------------------------------------------------------------------------


async def test_accounting_holds_across_a_mixed_conversation() -> None:
    agent, deps = build_agent()
    handle = FakeSpeechHandle()
    ctx = FakeRunContext(handle)

    await agent.next_stop(ctx)
    await agent.eta_to(ctx, "Gough")
    handle.interrupted = True
    handle.id = "speech-2"
    await agent.eta_to(ctx, "Haight")
    await agent.mark_delivered(ctx, "Gough")
    handle.interrupted = False
    handle.id = "speech-3"
    await agent.access_notes(ctx, "Haight")

    deps.fence.assert_accounting()
    stats = deps.fence.stats()
    assert stats["in_flight"] == 0
    assert stats["issued"] == len(deps.fence.records())


async def test_one_barge_in_advances_the_generation_once() -> None:
    """``_sync`` runs at three boundaries inside one write. One bump, not three.

    The agent reads ``speech_handle.interrupted`` synchronously rather than
    subscribing to an event, so the same barge-in is observed several times
    per tool call. ``bump_for`` keys on the handle id to collapse them.
    """
    agent, deps = build_agent()
    handle = FakeSpeechHandle(interrupted=True)

    before = deps.fence.generation
    await agent.mark_delivered(FakeRunContext(handle), "Gough")

    assert deps.fence.generation == before + 1


async def test_a_second_barge_in_advances_the_generation_again() -> None:
    """Different speech handle, different turn, another generation."""
    agent, deps = build_agent()
    before = deps.fence.generation

    await agent.mark_delivered(
        FakeRunContext(FakeSpeechHandle(id="speech-1", interrupted=True)), "Gough"
    )
    await agent.mark_delivered(
        FakeRunContext(FakeSpeechHandle(id="speech-2", interrupted=True)), "Haight"
    )

    assert deps.fence.generation == before + 2
    assert deps.backend.mutations() == [], "neither stale write may land"


async def test_metrics_are_recorded_for_every_admitted_tool() -> None:
    agent, deps = build_agent()
    ctx = FakeRunContext(FakeSpeechHandle())
    await agent.eta_to(ctx, "Gough")
    await agent.next_stop(ctx)
    names = {s.name for s in deps.metrics.samples()}
    assert names == {"tool.eta_to", "tool.next_stop"}


async def test_publish_is_a_noop_without_a_room() -> None:
    """Observability must never be able to break a session."""
    agent, deps = build_agent()
    deps.settings = Settings(publish_fence_events=True)
    deps.room = None
    deps.publish({"type": "fence"})  # must not raise
    await agent.eta_to(FakeRunContext(FakeSpeechHandle()), "Gough")


# --------------------------------------------------------------------------
# Regression: the error path used to bypass the fence
#
# `except DispatchError` cancelled the ticket and then returned a speakable
# string regardless of whether the turn was still alive. An error is a tool
# result, so a superseded turn's error reached the driver -- directly against
# the headline claim. Found by a red-team pass, not by the original suite.
# --------------------------------------------------------------------------


async def test_superseded_read_error_is_not_spoken() -> None:
    agent, deps = build_agent(latency_ms=120.0)
    handle = FakeSpeechHandle()
    ctx = FakeRunContext(handle)

    task = asyncio.create_task(agent.eta_to(ctx, "Nonexistent Boulevard"))
    await asyncio.sleep(0.02)
    handle.interrupted = True
    out = await task

    assert out.startswith("SUPERSEDED_RESULT")
    assert "did not work" not in out
    assert "Nonexistent" not in out
    deps.fence.assert_accounting()


async def test_superseded_write_error_is_not_spoken() -> None:
    agent, deps = build_agent(latency_ms=120.0)
    handle = FakeSpeechHandle()
    ctx = FakeRunContext(handle)

    task = asyncio.create_task(agent.mark_delivered(ctx, "Nonexistent Boulevard"))
    await asyncio.sleep(0.02)
    handle.interrupted = True
    out = await task

    assert out.startswith("SUPERSEDED_RESULT")
    deps.fence.assert_accounting()


async def test_a_live_turn_still_hears_its_error(agent_and_deps) -> None:
    """The fix must not silence errors on turns that are still alive."""
    agent, deps = agent_and_deps
    out = await agent.eta_to(FakeRunContext(FakeSpeechHandle()), "Nonexistent Blvd")
    assert "did not work" in out
    assert "SUPERSEDED" not in out


# --------------------------------------------------------------------------
# Regression: heard-not-said was never wired into the agent
#
# transcription_node registered the utterance with an EMPTY string, and nothing
# ever called cut(). The module tests passed because they fed the tracker real
# text directly. These tests go through the agent's own pipeline, which is the
# only thing that proves the claim in RIME_EVIDENCE.md sub-claim (c).
# --------------------------------------------------------------------------


from livekit.agents.types import TimedString  # noqa: E402


SPOKEN = "Your next stop is twelve forty-seven Goff Street gate code four four one seven"


async def _timed_stream(text: str, ms_per_word: float = 300.0):
    for i, w in enumerate(text.split()):
        yield TimedString(
            w + " ",
            start_time=(i * ms_per_word) / 1000.0,
            end_time=((i + 1) * ms_per_word) / 1000.0,
        )


class _FakeSession:
    def __init__(self, handle):
        self.current_speech = handle


async def _drive_transcription(agent, handle, text=SPOKEN):
    agent._session_override = _FakeSession(handle)
    async for _ in agent.transcription_node(_timed_stream(text), None):
        pass


async def test_transcription_node_registers_the_real_text(monkeypatch) -> None:
    """The bug: it used to register "" and every reconciliation returned ""."""
    agent, deps = build_agent()
    handle = FakeSpeechHandle(id="u-1")
    monkeypatch.setattr(type(agent), "session", property(lambda s: _FakeSession(handle)))

    async for _ in agent.transcription_node(_timed_stream(SPOKEN), None):
        pass

    result = deps.heard.cut("u-1", at_ms=1500.0)
    assert result.words_total == len(SPOKEN.split())
    assert result.heard_text.startswith("Your next stop is")
    assert result.heard_text != ""


async def test_reconcile_records_what_was_heard(monkeypatch) -> None:
    agent, deps = build_agent()
    handle = FakeSpeechHandle(id="u-2")
    monkeypatch.setattr(type(agent), "session", property(lambda s: _FakeSession(handle)))

    async for _ in agent.transcription_node(_timed_stream(SPOKEN), None):
        pass

    # Barge-in about 1.5s into playout.
    agent._utt_started["u-2"] = __import__("time").monotonic() - 1.5
    handle.interrupted = True
    await agent._reconcile_heard(handle)

    assert len(deps.heard_log) == 1
    r = deps.heard_log[0]
    assert r.interrupted
    assert r.exact, "should use Rime word timestamps, not an estimate"
    assert "four four one seven" not in r.to_chat_text(), (
        "the gate code was never played and must not enter the record"
    )
    assert "cut off here" in r.to_chat_text()


async def test_uninterrupted_utterance_is_recorded_complete(monkeypatch) -> None:
    agent, deps = build_agent()
    handle = FakeSpeechHandle(id="u-3")
    monkeypatch.setattr(type(agent), "session", property(lambda s: _FakeSession(handle)))

    async for _ in agent.transcription_node(_timed_stream(SPOKEN), None):
        pass
    await agent._reconcile_heard(handle)

    assert len(deps.heard_log) == 1
    assert deps.heard_log[0].interrupted is False
    assert deps.heard_log[0].words_heard == deps.heard_log[0].words_total


async def test_reconcile_is_safe_when_nothing_was_transcribed() -> None:
    agent, deps = build_agent()
    await agent._reconcile_heard(FakeSpeechHandle(id="never-spoke"))
    assert deps.heard_log == []


async def test_speech_done_callback_bumps_the_fence_once() -> None:
    agent, deps = build_agent()
    handle = FakeSpeechHandle(id="u-4", interrupted=True)
    before = deps.fence.generation
    agent._on_speech_done(handle)
    agent._on_speech_done(handle)
    await asyncio.sleep(0)
    assert deps.fence.generation == before + 1
