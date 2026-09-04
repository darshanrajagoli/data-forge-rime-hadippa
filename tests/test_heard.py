"""Heard-not-said reconciliation.

The property under test: after a barge-in, the conversation history must
contain the words that came out of the speaker, not the words that were
generated. Getting this wrong makes the agent believe it already gave the
driver a gate code it never finished saying.
"""

from __future__ import annotations

import pytest

from waypoint.heard import (
    DEFAULT_WORDS_PER_SECOND,
    HeardResult,
    HeardTracker,
    Method,
    WordMark,
    boundary_error_words,
)

SENTENCE = "Your next stop is twelve forty-seven Goff Street and the gate code is four four one seven"


def marks_for(sentence: str, ms_per_word: float = 300.0) -> list[WordMark]:
    """Evenly spaced word timings, standing in for Rime's WebSocket stream."""
    out = []
    for i, w in enumerate(sentence.split()):
        out.append(WordMark(w, i * ms_per_word, (i + 1) * ms_per_word))
    return out


@pytest.fixture
def tracker() -> HeardTracker:
    return HeardTracker()


# --------------------------------------------------------------------------
# Exact path: Rime word timestamps
# --------------------------------------------------------------------------


def test_word_timestamps_give_an_exact_boundary(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))

    result = tracker.cut("u1", at_ms=1500.0)  # exactly five words in

    assert result.method is Method.WORD_TIMESTAMPS
    assert result.exact is True
    assert result.words_heard == 5
    assert result.heard_text == "Your next stop is twelve"
    assert result.unheard_text.startswith("forty-seven")


def test_a_half_spoken_word_counts_as_unheard(tracker: HeardTracker) -> None:
    """Under-claiming is the safe direction.

    The cost of under-claiming is the agent repeating a word. The cost of
    over-claiming is a gate code the driver never received.
    """
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))

    result = tracker.cut("u1", at_ms=1450.0)  # mid-way through word 5

    assert result.words_heard == 4
    assert result.heard_text == "Your next stop is"
    assert "mid-word" in result.note


def test_cut_before_any_audio_yields_nothing_heard(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))
    result = tracker.cut("u1", at_ms=0.0)
    assert result.words_heard == 0
    assert result.heard_text == ""
    assert "interrupted before hearing any" in result.to_chat_text()


def test_cut_after_the_end_hears_everything(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))
    result = tracker.cut("u1", at_ms=999_999.0)
    assert result.words_heard == len(SENTENCE.split())
    assert result.unheard_text == ""
    assert result.interrupted is False


def test_marks_accumulate_across_calls(tracker: HeardTracker) -> None:
    """Rime streams timestamps; they arrive in chunks, not all at once."""
    all_marks = marks_for(SENTENCE)
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", all_marks[:5])
    tracker.attach_marks("u1", all_marks[5:])
    assert tracker.cut("u1", at_ms=3000.0).words_heard == 10


def test_only_arrived_marks_are_used(tracker: HeardTracker) -> None:
    """A word whose timestamp has not arrived cannot have been played."""
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE)[:4])
    result = tracker.cut("u1", at_ms=999_999.0)
    assert result.words_heard == 4


# --------------------------------------------------------------------------
# Estimated paths, and their honesty
# --------------------------------------------------------------------------


def test_duration_estimate_is_labelled_approximate(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.set_total_audio_ms("u1", 5400.0)

    result = tracker.cut("u1", at_ms=2700.0)

    assert result.method is Method.DURATION_ESTIMATE
    assert result.exact is False
    assert "approximate" in result.note
    assert "WebSocket" in result.note  # tells the reader how to get exactness
    assert 0 < result.words_heard < len(SENTENCE.split())


def test_rate_estimate_is_the_loudest_about_being_unreliable(
    tracker: HeardTracker,
) -> None:
    tracker.begin("u1", SENTENCE)
    result = tracker.cut("u1", at_ms=2000.0)
    assert result.method is Method.RATE_ESTIMATE
    assert result.exact is False
    assert "least reliable" in result.note


def test_known_method_reports_what_a_cut_would_use(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    assert tracker.known_method("u1") is Method.RATE_ESTIMATE
    tracker.set_total_audio_ms("u1", 5000.0)
    assert tracker.known_method("u1") is Method.DURATION_ESTIMATE
    tracker.attach_marks("u1", marks_for(SENTENCE)[:2])
    assert tracker.known_method("u1") is Method.WORD_TIMESTAMPS


def test_word_timestamps_win_over_duration(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.set_total_audio_ms("u1", 5400.0)
    tracker.attach_marks("u1", marks_for(SENTENCE))
    assert tracker.cut("u1", at_ms=1500.0).method is Method.WORD_TIMESTAMPS


def test_estimator_weights_by_character_mass(tracker: HeardTracker) -> None:
    """"a" and "unacceptable" do not take the same time to say."""
    text = "a a a supercalifragilistic"
    tracker.begin("u1", text)
    tracker.set_total_audio_ms("u1", 1000.0)
    # Half the audio elapsed; the long final word is most of the character mass,
    # so a character-weighted estimate should be past the three short words.
    assert tracker.cut("u1", at_ms=500.0).words_heard == 3


def test_boundary_error_is_signed_towards_danger() -> None:
    """Positive error means the estimator over-claimed, which is the bad way."""
    exact = HeardResult(
        "u1", SENTENCE, "a b c", "d e", 100.0, Method.WORD_TIMESTAMPS, 3, 5, ""
    )
    over = HeardResult(
        "u1", SENTENCE, "a b c d", "e", 100.0, Method.DURATION_ESTIMATE, 4, 5, ""
    )
    under = HeardResult(
        "u1", SENTENCE, "a b", "c d e", 100.0, Method.DURATION_ESTIMATE, 2, 5, ""
    )
    assert boundary_error_words(exact, over) == 1
    assert boundary_error_words(exact, under) == -1


# --------------------------------------------------------------------------
# What lands in the chat context
# --------------------------------------------------------------------------


def test_chat_text_is_truncated_and_marked(tracker: HeardTracker) -> None:
    """The whole point: history records what was heard, flagged as cut."""
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))
    result = tracker.cut("u1", at_ms=1500.0)

    chat = result.to_chat_text()

    assert chat.startswith("Your next stop is twelve")
    assert "cut off here" in chat
    assert "four four one seven" not in chat, (
        "the gate code was never played and must not appear in history"
    )


def test_completed_utterance_is_recorded_verbatim(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    result = tracker.complete("u1")
    assert result.method is Method.COMPLETE
    assert result.exact is True
    assert result.to_chat_text() == SENTENCE
    assert result.interrupted is False
    assert result.heard_fraction == 1.0


def test_heard_fraction(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))
    r = tracker.cut("u1", at_ms=1500.0)
    assert r.heard_fraction == pytest.approx(5 / len(SENTENCE.split()))


def test_result_serialises_with_its_method(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))
    d = tracker.cut("u1", at_ms=1500.0).to_dict()
    assert d["method"] == "word_timestamps"
    assert d["exact"] is True
    assert d["words_heard"] == 5
    assert "note" in d


# --------------------------------------------------------------------------
# Misuse
# --------------------------------------------------------------------------


def test_unknown_utterance_raises(tracker: HeardTracker) -> None:
    with pytest.raises(KeyError):
        tracker.cut("nope", at_ms=100.0)


def test_double_begin_raises(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    with pytest.raises(ValueError):
        tracker.begin("u1", SENTENCE)


def test_negative_cut_is_clamped(tracker: HeardTracker) -> None:
    tracker.begin("u1", SENTENCE)
    tracker.attach_marks("u1", marks_for(SENTENCE))
    assert tracker.cut("u1", at_ms=-50.0).words_heard == 0


def test_empty_text_is_survivable(tracker: HeardTracker) -> None:
    tracker.begin("u1", "")
    r = tracker.cut("u1", at_ms=100.0)
    assert r.words_heard == 0 and r.words_total == 0
    assert r.heard_fraction == 1.0


def test_rejects_nonpositive_rate() -> None:
    with pytest.raises(ValueError):
        HeardTracker(words_per_second=0)


def test_default_rate_is_documented_as_a_prior() -> None:
    assert 2.0 < DEFAULT_WORDS_PER_SECOND < 4.0
