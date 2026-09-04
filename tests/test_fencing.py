"""Invariants of the turn fence.

These tests are the actual claim. RIME_EVIDENCE.md asserts that a superseded
tool result is never spoken and never committed; this file is where that is
either true or false, and it runs with no network, no API key and no audio
device, so anyone can check it in about a second.

The last test is the important one. Rather than enumerating hand-picked
interleavings, it fuzzes thousands of random orderings of issue / barge-in /
resolve / cancel and asserts after every single operation that

  * the accounting identity holds (nothing leaked, nothing resolved twice), and
  * nothing was admitted that should have been fenced.

A hand-written test proves the cases its author thought of. This one covers
the orderings nobody thought of, which on a barge-in path is where the bugs
live.
"""

from __future__ import annotations

import random
import threading

import pytest

from waypoint.fencing import (
    Disposition,
    FenceError,
    ReanchorPolicy,
    TurnFence,
    args_fingerprint,
    summarise,
)


class FakeClock:
    """Deterministic monotonic clock so tests never sleep."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fence(clock: FakeClock) -> TurnFence:
    return TurnFence(clock=clock)


# --------------------------------------------------------------------------
# The headline property
# --------------------------------------------------------------------------


def test_result_from_current_generation_is_delivered(fence: TurnFence) -> None:
    ticket = fence.issue("eta_to", {"destination": "Gough"})
    decision = fence.admit(ticket)
    assert decision.disposition is Disposition.DELIVERED
    assert decision.speak and decision.commit


def test_result_superseded_by_barge_in_is_never_spoken(fence: TurnFence) -> None:
    """The failure this whole project exists to prevent."""
    ticket = fence.issue("eta_to", {"destination": "Oak Street"})
    fence.bump("user_barge_in")  # driver changes their mind mid-sentence
    decision = fence.admit(ticket)

    assert decision.disposition is Disposition.FENCED_STALE
    assert decision.speak is False
    assert decision.commit is False


def test_irreversible_tool_is_never_reanchored(fence: TurnFence) -> None:
    """A NEVER-policy write stays fenced even when the new turn wants it.

    This is the distinction between "stale" and "must not happen". An ETA
    lookup that is still wanted can be handed over. A second SMS cannot.
    """
    ticket = fence.issue(
        "notify_recipient",
        {"destination": "Gough", "message": "on my way"},
        ReanchorPolicy.NEVER,
    )
    fence.bump()
    # The new turn asks for the exact same thing.
    live = fence.issue(
        "notify_recipient",
        {"destination": "Gough", "message": "on my way"},
        ReanchorPolicy.NEVER,
    )
    decision = fence.admit(ticket)

    assert decision.disposition is Disposition.FENCED_TERMINAL
    assert not decision.speak and not decision.commit
    assert decision.satisfies is None
    fence.admit(live)  # keep the accounting balanced
    fence.assert_accounting()


def test_read_reanchors_when_new_turn_wants_the_same_lookup(
    fence: TurnFence,
) -> None:
    """The driver refined the request rather than abandoning it."""
    stale = fence.issue(
        "eta_to", {"destination": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
    )
    fence.bump()
    live = fence.issue(
        "eta_to", {"destination": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
    )

    decision = fence.admit(stale)

    assert decision.disposition is Disposition.REANCHORED
    assert decision.speak and decision.commit
    assert decision.satisfies is not None
    assert decision.satisfies.ticket_id == live.ticket_id


def test_read_does_not_reanchor_when_args_differ(fence: TurnFence) -> None:
    stale = fence.issue(
        "eta_to", {"destination": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
    )
    fence.bump()
    fence.issue(
        "eta_to", {"destination": "Haight"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
    )

    decision = fence.admit(stale)
    assert decision.disposition is Disposition.FENCED_STALE
    assert not decision.speak


def test_discard_policy_never_reanchors_even_on_exact_match(
    fence: TurnFence,
) -> None:
    stale = fence.issue("access_notes", {"d": "Gough"}, ReanchorPolicy.DISCARD)
    fence.bump()
    fence.issue("access_notes", {"d": "Gough"}, ReanchorPolicy.DISCARD)
    assert fence.admit(stale).disposition is Disposition.FENCED_STALE


# --------------------------------------------------------------------------
# The effect boundary
# --------------------------------------------------------------------------


def test_check_is_non_terminal(fence: TurnFence) -> None:
    """A peek must not consume the ticket; admit still has to happen."""
    ticket = fence.issue("mark_delivered", {"d": "Gough"}, ReanchorPolicy.NEVER)
    first = fence.check(ticket)
    second = fence.check(ticket)
    assert first.commit and second.commit
    assert fence.stats()["in_flight"] == 1
    assert fence.admit(ticket).disposition is Disposition.DELIVERED
    fence.assert_accounting()


def test_check_refuses_write_after_barge_in(fence: TurnFence) -> None:
    """The effect-boundary check is what actually protects a write.

    Cancellation cannot: by the time CancelledError arrives the POST has
    returned. So the check has to happen *before* the effect, and it has to
    say no.
    """
    ticket = fence.issue("mark_delivered", {"d": "Gough"}, ReanchorPolicy.NEVER)
    fence.bump("user_barge_in")
    assert fence.check(ticket).commit is False


def test_check_on_resolved_ticket_reports_cancelled(fence: TurnFence) -> None:
    ticket = fence.issue("eta_to", {"d": "x"})
    fence.admit(ticket)
    assert fence.check(ticket).commit is False


# --------------------------------------------------------------------------
# At-most-once delivery
# --------------------------------------------------------------------------


def test_double_admit_raises(fence: TurnFence) -> None:
    ticket = fence.issue("eta_to", {"d": "x"})
    fence.admit(ticket)
    with pytest.raises(FenceError, match="at-most-once"):
        fence.admit(ticket)


def test_admitting_foreign_ticket_raises(fence: TurnFence) -> None:
    other = TurnFence().issue("eta_to", {"d": "x"})
    with pytest.raises(FenceError, match="not issued by this fence"):
        fence.admit(other)


def test_cancel_then_admit_raises(fence: TurnFence) -> None:
    ticket = fence.issue("eta_to", {"d": "x"})
    fence.cancel(ticket)
    with pytest.raises(FenceError):
        fence.admit(ticket)


def test_double_cancel_is_tolerated(fence: TurnFence) -> None:
    """A cancel racing a result is normal and must not crash the session."""
    ticket = fence.issue("eta_to", {"d": "x"})
    fence.cancel(ticket)
    again = fence.cancel(ticket)
    assert again.disposition is Disposition.FENCED_CANCELLED
    assert again.detail == "already-resolved"
    fence.assert_accounting()


def test_concurrent_admit_only_one_wins(fence: TurnFence) -> None:
    """Under threads, exactly one admit succeeds and the rest raise."""
    ticket = fence.issue("eta_to", {"d": "x"})
    wins: list[bool] = []
    barrier = threading.Barrier(8)

    def attempt() -> None:
        barrier.wait()
        try:
            fence.admit(ticket)
            wins.append(True)
        except FenceError:
            pass

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(wins) == 1
    fence.assert_accounting()


# --------------------------------------------------------------------------
# Generation semantics
# --------------------------------------------------------------------------


def test_generation_is_monotonic(fence: TurnFence) -> None:
    seen = [fence.generation]
    for _ in range(20):
        seen.append(fence.bump())
    assert seen == sorted(seen)
    assert len(set(seen)) == len(seen)


def test_bump_for_is_idempotent_per_cause(fence: TurnFence) -> None:
    """One barge-in observed from three places must cost one generation.

    The agent reads ``speech_handle.interrupted`` at several boundaries and
    also gets a done-callback for the same handle. All of them call bump_for
    with the handle id.
    """
    start = fence.generation
    for _ in range(5):
        fence.bump_for("speech-abc", "speech_handle.interrupted")
    assert fence.generation == start + 1

    fence.bump_for("speech-def", "speech_handle.interrupted")
    assert fence.generation == start + 2


def test_ticket_issued_after_bump_is_current(fence: TurnFence) -> None:
    fence.bump()
    ticket = fence.issue("eta_to", {"d": "x"})
    assert fence.admit(ticket).disposition is Disposition.DELIVERED


def test_cancel_generation_drains_old_tickets(fence: TurnFence) -> None:
    old = [fence.issue(f"t{i}", {"i": i}) for i in range(3)]
    gen = fence.generation
    fence.bump()
    new = fence.issue("t_new", {})

    drained = fence.cancel_generation(gen, "turn_abandoned")

    assert drained == 3
    assert fence.stats()["in_flight"] == 1
    assert all(fence.check(t).commit is False for t in old)
    fence.admit(new)
    fence.assert_accounting()


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------


def test_every_ticket_produces_exactly_one_record(fence: TurnFence) -> None:
    a = fence.issue("a", {})
    b = fence.issue("b", {})
    c = fence.issue("c", {})
    fence.admit(a)
    fence.bump()
    fence.admit(b)
    fence.cancel(c)

    records = fence.records()
    assert len(records) == 3
    assert {r.ticket_id for r in records} == {a.ticket_id, b.ticket_id, c.ticket_id}
    fence.assert_accounting()


def test_record_captures_both_generations(fence: TurnFence, clock: FakeClock) -> None:
    ticket = fence.issue("eta_to", {"d": "Gough"})
    clock.advance(1.5)
    fence.bump()
    fence.admit(ticket)

    r = fence.records()[0]
    assert r.issued_generation == 0
    assert r.observed_generation == 1
    assert r.disposition is Disposition.FENCED_STALE
    assert r.latency_ms == pytest.approx(1500.0)
    assert "gen0->gen1" in r.detail


def test_on_record_sink_is_called(clock: FakeClock) -> None:
    seen = []
    f = TurnFence(clock=clock, on_record=seen.append)
    f.admit(f.issue("a", {}))
    assert len(seen) == 1 and seen[0].tool_name == "a"


def test_broken_record_sink_cannot_break_the_fence(clock: FakeClock) -> None:
    """Observability is not allowed to be a failure mode for safety."""

    def explode(_r: object) -> None:
        raise RuntimeError("visualiser died")

    f = TurnFence(clock=clock, on_record=explode)
    assert f.admit(f.issue("a", {})).speak is True
    f.assert_accounting()


def test_audit_json_round_trips(fence: TurnFence) -> None:
    import json

    fence.admit(fence.issue("a", {"x": 1}))
    fence.bump()
    fence.admit(fence.issue("b", {"y": 2}))
    parsed = json.loads(fence.audit_json())
    assert parsed["generation"] == 1
    assert len(parsed["records"]) == 2
    assert parsed["stats"]["issued"] == 2


def test_marks_record_why_each_generation_advanced(fence: TurnFence) -> None:
    fence.bump("user_barge_in")
    fence.bump("session_reset")
    reasons = [m["reason"] for m in fence.marks()]
    assert reasons == ["session_start", "user_barge_in", "session_reset"]


# --------------------------------------------------------------------------
# Fingerprints
# --------------------------------------------------------------------------


def test_fingerprint_is_order_independent() -> None:
    assert args_fingerprint({"a": 1, "b": 2}) == args_fingerprint({"b": 2, "a": 1})


def test_fingerprint_distinguishes_values() -> None:
    assert args_fingerprint({"d": "Gough"}) != args_fingerprint({"d": "Haight"})


def test_fingerprint_handles_empty_and_none() -> None:
    assert args_fingerprint(None) == args_fingerprint({})


def test_fingerprint_survives_unserialisable_values() -> None:
    class Weird:
        pass

    fp = args_fingerprint({"o": Weird()})
    assert isinstance(fp, str) and len(fp) == 16


# --------------------------------------------------------------------------
# Summary helper
# --------------------------------------------------------------------------


def test_summarise_counts_and_percentiles(fence: TurnFence, clock: FakeClock) -> None:
    for i in range(5):
        t = fence.issue(f"tool{i}", {"i": i})
        clock.advance(0.1 * (i + 1))
        fence.admit(t)
    s = summarise(fence.records())
    assert s["total"] == 5
    assert s["by_disposition"]["delivered"] == 5
    assert s["tool_latency_ms"]["max"] == pytest.approx(500.0)


def test_summarise_empty() -> None:
    s = summarise([])
    assert s["total"] == 0 and s["tool_latency_ms"]["p50"] == 0.0


# --------------------------------------------------------------------------
# The fuzz test
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_fuzz_random_interleavings_preserve_every_invariant(seed: int) -> None:
    """Random orderings of issue / barge-in / resolve / cancel.

    After *every* operation we assert the accounting identity. After every
    admission we assert the safety property directly from the ticket's own
    generation, independently of what the fence reported -- so the test cannot
    pass by agreeing with a bug in the code under test.
    """
    rng = random.Random(seed)
    clock = FakeClock()
    fence = TurnFence(clock=clock)
    live: list = []
    tools = ["eta_to", "access_notes", "mark_delivered", "notify_recipient"]
    destinations = ["Gough", "Haight", "Guerrero", "Noe"]
    policies = list(ReanchorPolicy)

    admitted_stale_without_reanchor = 0

    for _ in range(200):
        clock.advance(rng.uniform(0.001, 0.2))
        action = rng.choices(
            ["issue", "bump", "admit", "cancel", "check"],
            weights=[40, 15, 30, 8, 7],
        )[0]

        if action == "issue":
            t = fence.issue(
                rng.choice(tools),
                {"destination": rng.choice(destinations)},
                rng.choice(policies),
            )
            live.append(t)

        elif action == "bump":
            fence.bump_for(f"speech-{rng.randrange(10_000)}", "fuzz")

        elif action == "check" and live:
            fence.check(rng.choice(live))

        elif action == "admit" and live:
            t = live.pop(rng.randrange(len(live)))
            gen_at_issue = t.generation
            gen_now = fence.generation
            decision = fence.admit(t)

            # Independent restatement of the safety property.
            if gen_at_issue < gen_now:
                if decision.speak:
                    assert decision.disposition is Disposition.REANCHORED, (
                        "a superseded result was admitted without re-anchoring"
                    )
                    assert t.policy is ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
                    assert decision.satisfies is not None
                    assert decision.satisfies.args_fp == t.args_fp
                    assert decision.satisfies.generation == gen_now
                else:
                    admitted_stale_without_reanchor += 1
            else:
                assert decision.speak, "a current result was fenced"
                assert decision.disposition is Disposition.DELIVERED

            # A NEVER-policy ticket must never cross a boundary, full stop.
            if t.policy is ReanchorPolicy.NEVER and gen_at_issue < gen_now:
                assert decision.disposition is Disposition.FENCED_TERMINAL
                assert not decision.commit

        elif action == "cancel" and live:
            fence.cancel(live.pop(rng.randrange(len(live))))

        fence.assert_accounting()

    # Drain and confirm the books balance at the end too.
    for t in live:
        fence.cancel(t, "end of fuzz run")
    fence.assert_accounting()

    stats = fence.stats()
    assert stats["in_flight"] == 0
    assert len(fence.records()) == stats["issued"]


def test_fuzz_never_commits_a_stale_write() -> None:
    """Focused restatement: across many runs, zero NEVER-policy writes leak."""
    leaked = 0
    for seed in range(60):
        rng = random.Random(seed)
        fence = TurnFence(clock=FakeClock())
        live = []
        for _ in range(120):
            if rng.random() < 0.5:
                live.append(
                    fence.issue("mark_delivered", {"d": "Gough"}, ReanchorPolicy.NEVER)
                )
            if rng.random() < 0.25:
                fence.bump()
            if live and rng.random() < 0.5:
                t = live.pop(rng.randrange(len(live)))
                d = fence.admit(t)
                if d.commit and t.generation < d.observed_generation:
                    leaked += 1
        fence.assert_accounting()
    assert leaked == 0


# --------------------------------------------------------------------------
# Origin retirement
#
# Generation alone is not enough. It advances once per barge-in, so a *second*
# tool issued by an already-interrupted turn gets stamped with the new
# generation and looks fresh. These tests exist because acceptance scenario A2
# found exactly that hole.
# --------------------------------------------------------------------------


def test_second_tool_from_a_dead_turn_is_still_fenced(fence: TurnFence) -> None:
    """The regression. Three writes from one interrupted turn, none may land."""
    fence.bump_for("speech-1", "speech_handle.interrupted")

    decisions = []
    for tool in ("mark_delivered", "reschedule_stop", "notify_recipient"):
        t = fence.issue(tool, {"d": "Gough"}, ReanchorPolicy.NEVER, origin="speech-1")
        decisions.append(fence.admit(t))

    assert all(d.disposition is Disposition.FENCED_TERMINAL for d in decisions)
    assert not any(d.commit for d in decisions)
    fence.assert_accounting()


def test_check_also_refuses_a_dead_origin(fence: TurnFence) -> None:
    """The effect boundary must use the same test as the speech boundary."""
    fence.bump_for("speech-1", "interrupted")
    t = fence.issue("mark_delivered", {}, ReanchorPolicy.NEVER, origin="speech-1")
    assert fence.check(t).commit is False
    assert "retired" in fence.check(t).detail
    fence.admit(t)


def test_a_live_turn_is_unaffected_by_another_turns_retirement(
    fence: TurnFence,
) -> None:
    fence.bump_for("speech-1", "interrupted")
    t = fence.issue("eta_to", {"d": "Gough"}, origin="speech-2")
    assert fence.admit(t).disposition is Disposition.DELIVERED


def test_tickets_without_an_origin_are_governed_by_generation_only(
    fence: TurnFence,
) -> None:
    """Background work not tied to a turn still uses the generation rule."""
    t = fence.issue("eta_to", {"d": "x"})
    assert t.origin == ""
    assert fence.admit(t).disposition is Disposition.DELIVERED


def test_supersession_reason_names_the_retired_origin(fence: TurnFence) -> None:
    fence.bump_for("speech-7", "interrupted")
    t = fence.issue("eta_to", {}, origin="speech-7")
    record_detail = fence.admit(t).detail
    assert "speech-7" in record_detail
    assert "retired" in record_detail


def test_a_dead_turns_read_can_still_reanchor_to_a_live_one(
    fence: TurnFence,
) -> None:
    """Retirement kills the *turn*, not the *data*.

    A pure read with identical arguments that a live turn is asking for right
    now is still the right answer. Refusing to hand it over would cost the
    driver a round trip for no safety gain.
    """
    fence.bump_for("speech-1", "interrupted")
    stale = fence.issue(
        "eta_to", {"d": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH,
        origin="speech-1",
    )
    live = fence.issue(
        "eta_to", {"d": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH,
        origin="speech-2",
    )
    decision = fence.admit(stale)
    assert decision.disposition is Disposition.REANCHORED
    assert decision.satisfies is not None
    assert decision.satisfies.ticket_id == live.ticket_id
    fence.admit(live)
    fence.assert_accounting()


def test_reanchor_target_must_itself_be_from_a_live_turn(fence: TurnFence) -> None:
    """Two dead turns cannot validate each other."""
    fence.bump_for("speech-1", "interrupted")
    a = fence.issue(
        "eta_to", {"d": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH,
        origin="speech-1",
    )
    b = fence.issue(
        "eta_to", {"d": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH,
        origin="speech-1",
    )
    assert fence.admit(a).disposition is Disposition.FENCED_STALE
    assert fence.admit(b).disposition is Disposition.FENCED_STALE
    fence.assert_accounting()


def test_retirement_is_idempotent(fence: TurnFence) -> None:
    start = fence.generation
    for _ in range(4):
        fence.bump_for("speech-1", "interrupted")
    assert fence.generation == start + 1


@pytest.mark.parametrize("seed", range(30))
def test_fuzz_with_origins_never_leaks_a_write(seed: int) -> None:
    """Fuzz again, this time with turns that die and keep issuing work."""
    rng = random.Random(seed)
    fence = TurnFence(clock=FakeClock())
    live: list = []
    turns = [f"speech-{i}" for i in range(6)]
    leaked = 0

    for _ in range(250):
        action = rng.choices(
            ["issue", "retire", "admit", "cancel"], weights=[45, 20, 30, 5]
        )[0]

        if action == "issue":
            live.append(
                fence.issue(
                    rng.choice(["eta_to", "mark_delivered"]),
                    {"d": rng.choice(["Gough", "Haight"])},
                    rng.choice(list(ReanchorPolicy)),
                    origin=rng.choice(turns),
                )
            )
        elif action == "retire":
            fence.bump_for(rng.choice(turns), "fuzz interrupt")
        elif action == "admit" and live:
            t = live.pop(rng.randrange(len(live)))
            dead_turn = t.origin in fence._retired  # noqa: SLF001
            older_gen = t.generation < fence.generation
            d = fence.admit(t)
            if (dead_turn or older_gen) and d.commit:
                # Only a re-anchor may pass, and never for a NEVER-policy tool.
                assert d.disposition is Disposition.REANCHORED
                assert t.policy is ReanchorPolicy.REANCHOR_IF_ARGS_MATCH
                if t.policy is ReanchorPolicy.NEVER:
                    leaked += 1
        elif action == "cancel" and live:
            fence.cancel(live.pop(rng.randrange(len(live))))

        fence.assert_accounting()

    for t in live:
        fence.cancel(t, "end of run")
    fence.assert_accounting()
    assert leaked == 0
    assert fence.stats()["in_flight"] == 0


def test_reanchor_target_must_itself_be_reanchorable(fence: TurnFence) -> None:
    """A stale read must not be handed to a live NEVER-policy ticket.

    Found by a red-team pass. Target matching compared tool name and argument
    fingerprint but not policy, so a superseded REANCHOR ticket could satisfy a
    live ticket that had been explicitly declared un-re-anchorable. Tool
    policies are fixed per tool in the agent, so this was not reachable in the
    product -- but the fence should hold the invariant because it enforces it,
    not because every call site happens to agree.
    """
    stale = fence.issue(
        "notify_recipient", {"d": "Gough"},
        ReanchorPolicy.REANCHOR_IF_ARGS_MATCH, origin="s1",
    )
    fence.bump_for("s1", "barge-in")
    live = fence.issue(
        "notify_recipient", {"d": "Gough"}, ReanchorPolicy.NEVER, origin="s2"
    )

    decision = fence.admit(stale)

    assert decision.disposition is Disposition.FENCED_STALE
    assert not decision.speak and not decision.commit
    assert decision.satisfies is None
    fence.admit(live)
    fence.assert_accounting()


def test_reanchor_still_works_between_two_reanchorable_tickets(
    fence: TurnFence,
) -> None:
    """Guards the fix above from over-correcting into 'never re-anchor'."""
    stale = fence.issue(
        "eta_to", {"d": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH, origin="s1"
    )
    fence.bump_for("s1", "barge-in")
    live = fence.issue(
        "eta_to", {"d": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH, origin="s2"
    )
    decision = fence.admit(stale)
    assert decision.disposition is Disposition.REANCHORED
    assert decision.satisfies is not None
    assert decision.satisfies.ticket_id == live.ticket_id
    fence.admit(live)
    fence.assert_accounting()


def test_discard_policy_ticket_is_never_a_reanchor_target(fence: TurnFence) -> None:
    stale = fence.issue(
        "eta_to", {"d": "Gough"}, ReanchorPolicy.REANCHOR_IF_ARGS_MATCH, origin="s1"
    )
    fence.bump_for("s1", "barge-in")
    live = fence.issue("eta_to", {"d": "Gough"}, ReanchorPolicy.DISCARD, origin="s2")
    assert fence.admit(stale).disposition is Disposition.FENCED_STALE
    fence.admit(live)
    fence.assert_accounting()
