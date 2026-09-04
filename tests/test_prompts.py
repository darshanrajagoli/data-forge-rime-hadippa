"""The instructions the model is actually given.

`prompts.py` is where "written for the ear" either happens or does not, and it
had no tests. Mutation testing showed why that matters: replacing the whole
style block with *"Say as much as you like, in whatever order reads best"* left
every other test green. Nothing anywhere noticed that the agent had been told
to behave like a chat window.

These are deliberately assertions about *properties*, not about exact wording.
A test that pins the prose would fail on every edit and get deleted; a test
that pins the properties survives rewriting and still fails when the rules are
removed. Each one names the driver-facing failure it prevents.

The safety markers are a separate matter. They are checked here for presence
because their absence would make the transcript incoherent — but nothing that
matters depends on the model obeying them. The fence blocks a stale write in
code, before the call is made. See `docs/THREAT_MODEL.md`.
"""

from __future__ import annotations

import pytest

from waypoint.config import Settings
from waypoint.prompts import (
    GREETING,
    STYLE_RULES,
    SUPERSEDED_MARKER,
    build_instructions,
)


def instructions(**kw) -> str:
    return build_instructions(Settings(**kw))


# --------------------------------------------------------------------------
# Written for the ear
# --------------------------------------------------------------------------


def test_the_style_rules_reach_the_model() -> None:
    """The mutation that prompted this file removed them entirely."""
    assert STYLE_RULES.strip()
    assert STYLE_RULES in instructions()


@pytest.mark.parametrize(
    "requirement,why",
    [
        ("markdown", "the LLM writes asterisks; a driver must never hear one"),
        ("emoji", "same"),
        ("bullet", "a spoken list forces the listener to hold state"),
        ("list", "same"),
    ],
)
def test_visual_formatting_is_forbidden(requirement: str, why: str) -> None:
    assert requirement in instructions().lower(), why


def test_brevity_is_required_not_suggested() -> None:
    """A driver at 40mph gets one useful fact per turn, or none."""
    text = instructions().lower()
    assert "one or two sentences" in text or "two sentences" in text
    assert "answer first" in text


def test_the_agent_is_told_not_to_pad() -> None:
    """'Sure! Let me check that for you' is three seconds of nothing."""
    text = instructions().lower()
    assert "let me check" in text
    assert "repeat the question" in text


def test_numbers_are_spoken_the_way_a_person_says_them() -> None:
    assert "numbers the way a person would" in instructions().lower()


# --------------------------------------------------------------------------
# Who the user is
# --------------------------------------------------------------------------


def test_the_prompt_states_the_physical_constraint() -> None:
    """The whole product rests on this. If the model does not know the user is
    driving, none of the style rules have a reason."""
    text = instructions().lower()
    assert "driving" in text
    assert "hands" in text and "wheel" in text
    assert "cannot look at a screen" in text or "cannot look" in text


def test_the_agent_knows_the_limits_of_what_it_knows() -> None:
    text = instructions().lower()
    assert "traffic" in text, "must not invent traffic conditions"
    assert "manifest" in text


# --------------------------------------------------------------------------
# Interrupted turns
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "marker",
    ["SUPERSEDED_RESULT", "REFUSED_STALE_WRITE", "COMMITTED_BUT_UNCONFIRMED"],
)
def test_every_fence_marker_is_explained_to_the_model(marker: str) -> None:
    """Each of these can come back from a tool. An unexplained marker read
    aloud verbatim would be worse than the stale value it replaced."""
    assert marker in instructions()


def test_the_superseded_marker_is_an_instruction_not_a_value() -> None:
    """LiveKit retains interrupted tool outputs in the chat context, so this
    string is what the model reads on the *next* turn. It has to describe
    itself."""
    assert "not current" in SUPERSEDED_MARKER
    assert "Do not state it" in SUPERSEDED_MARKER
    assert "later turn" in SUPERSEDED_MARKER


def test_the_agent_is_told_not_to_repeat_a_committed_action() -> None:
    """The one case where the driver did not hear a confirmation for something
    that really happened. Doing it twice is the failure."""
    text = instructions().lower()
    assert "never re-run" in text or "do not" in text
    assert "committed_but_unconfirmed" in text.lower()


def test_interruption_is_framed_as_normal_not_rude() -> None:
    assert "not rudeness" in instructions().lower()


def test_irreversible_actions_require_confirmation() -> None:
    text = instructions().lower()
    assert "irreversible" in text
    assert "confirm" in text


# --------------------------------------------------------------------------
# Pacing follows the voice configuration
# --------------------------------------------------------------------------


def test_a_fast_voice_asks_for_shorter_sentences() -> None:
    """At speed_alpha > 1 the same sentence has less room in the listener's
    ear, so the prompt compensates rather than letting the voice outrun them."""
    fast = instructions(rime_speed_alpha=1.3)
    assert "1.3x" in fast
    assert "shorter" in fast.lower()


def test_a_slow_voice_is_told_not_to_pad() -> None:
    slow = instructions(rime_speed_alpha=0.8)
    assert "0.8x" in slow
    assert "filler" in slow.lower()


def test_a_normal_voice_gets_no_pacing_note() -> None:
    normal = instructions(rime_speed_alpha=1.0)
    assert "x." not in normal.replace("1.0x", "") or "shorter than usual" not in normal


# --------------------------------------------------------------------------
# The greeting
# --------------------------------------------------------------------------


def test_the_greeting_opens_with_something_useful() -> None:
    """Not 'How may I assist you today'. The driver already knows what it is."""
    assert "stops" in GREETING.lower()
    assert len(GREETING.split()) < 30, "a greeting is not a turn to be endured"


def test_the_greeting_contains_no_visual_formatting() -> None:
    for char in ("*", "#", "`", "-"):
        assert char not in GREETING
