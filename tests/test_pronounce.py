"""Pronunciation and delivery control.

Two things are being protected here.

1. Numbers come out in the form the driver will use them in. A gate code is
   keyed into a pad, so it is digits. A house number is looked for on a door,
   so it is "twelve forty-seven".
2. A pronunciation strategy the configured Rime model ignores is a *loud*
   failure, not a quiet one. Coda ignores bracket controls; asking for phonemes
   on Coda must raise rather than silently emit brackets that get read aloud
   or dropped.
"""

from __future__ import annotations

import pytest

from waypoint.pronounce import (
    LEXICON,
    MODEL_SUPPORTS_BRACKETS,
    LexEntry,
    PronunciationError,
    Strategy,
    apply_lexicon,
    lexicon_coverage,
    normalize_numbers_for_ear,
    render,
    resolve_strategy,
    speak_address,
    speak_code,
    speak_house_number,
    speak_unit,
)


# --------------------------------------------------------------------------
# Numbers for the ear
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,spoken",
    [
        ("1247", "twelve forty-seven"),
        ("1207", "twelve oh seven"),
        ("1200", "twelve hundred"),
        ("1000", "ten hundred"),
        ("836", "eight thirty-six"),
        ("805", "eight oh five"),
        ("800", "eight hundred"),
        ("42", "forty-two"),
        ("7", "seven"),
        ("15", "fifteen"),
    ],
)
def test_house_numbers_are_read_the_way_people_read_them(
    raw: str, spoken: str
) -> None:
    assert speak_house_number(raw) == spoken


def test_house_number_never_says_thousand() -> None:
    """"one thousand two hundred forty-seven" is not how an address is said."""
    for n in ("1247", "9911", "2190", "3401"):
        assert "thousand" not in speak_house_number(n)


def test_mixed_house_number_falls_back_to_digits() -> None:
    assert speak_house_number("120A") == "one two zero A"


def test_five_digit_number_is_read_digit_by_digit() -> None:
    assert speak_house_number("12345") == "one two three four five"


def test_gate_code_is_digit_by_digit() -> None:
    """A keypad code read as a quantity is unusable."""
    assert speak_code("4417") == "four four one seven"
    assert "thousand" not in speak_code("4417")


def test_gate_code_with_pause_brackets() -> None:
    assert speak_code("417", pause_ms=250) == "four <250> one <250> seven"


def test_gate_code_keeps_letters() -> None:
    assert speak_code("4A7") == "four A seven"


@pytest.mark.parametrize(
    "unit,spoken",
    [("4B", "unit four B"), ("11C", "unit eleven C"), ("A", "unit A"), (None, ""), ("", "")],
)
def test_units(unit: str | None, spoken: str) -> None:
    assert speak_unit(unit) == spoken


# --------------------------------------------------------------------------
# The lexicon
# --------------------------------------------------------------------------


def test_the_two_hard_ones() -> None:
    """Gough and Haight are the standard examples of English orthography
    giving a TTS engine nothing useful to work with."""
    assert apply_lexicon("Gough Street", Strategy.RESPELL).text == "Goff Street"
    assert apply_lexicon("Haight Street", Strategy.RESPELL).text == "Hate Street"


def test_lexicon_is_case_insensitive_and_word_bounded() -> None:
    assert apply_lexicon("gough", Strategy.RESPELL).text == "Goff"
    # Should not fire inside a longer word.
    assert apply_lexicon("Noel", Strategy.RESPELL).text == "Noel"


def test_multiword_entries_win_over_prefixes() -> None:
    out = apply_lexicon("Buena Vista Avenue", Strategy.RESPELL)
    assert out.text.startswith("BWAY-na VISS-ta")


def test_applied_list_records_every_substitution() -> None:
    out = apply_lexicon("Gough then Haight", Strategy.RESPELL)
    assert out.applied == ("Gough->Goff", "Haight->Hate")


def test_strategy_none_changes_nothing() -> None:
    out = apply_lexicon("Gough Street", Strategy.NONE)
    assert out.text == "Gough Street"
    assert out.applied == ()


def test_unknown_streets_pass_through() -> None:
    assert apply_lexicon("Main Street", Strategy.RESPELL).text == "Main Street"


def test_lexicon_entries_are_wellformed() -> None:
    for e in LEXICON:
        assert e.token and e.respell
        assert e.respell != e.token, f"{e.token} respells to itself"


def test_lexicon_has_no_duplicate_tokens() -> None:
    tokens = [e.token.lower() for e in LEXICON]
    assert len(tokens) == len(set(tokens))


def test_phoneme_column_ships_empty_and_says_so() -> None:
    """We do not invent strings in Rime's phoneme alphabet.

    An invented phoneme string is a guess wearing the costume of precision.
    Filling it needs synthesised audio posted to Rime's phonemize
    endpoint, which the shipped respell strategy does not require.
    """
    cov = lexicon_coverage()
    assert cov["with_verified_phoneme"] == 0
    assert "inventing" in cov["note"]
    assert cov["with_respelling"] == len(LEXICON)


def test_phoneme_strategy_falls_back_and_reports_it() -> None:
    out = apply_lexicon("Gough Street", Strategy.PHONEME)
    assert out.text == "Goff Street"
    assert any("no verified Rime phoneme" in n for n in out.notes)
    assert any("fallback" in a for a in out.applied)


def test_phoneme_strategy_emits_brackets_when_a_phoneme_exists() -> None:
    lex = [LexEntry(token="Gough", respell="Goff", phoneme="g0Af", verified=True)]
    out = apply_lexicon("Gough Street", Strategy.PHONEME, lexicon=lex)
    assert out.text == "{g0Af} Street"
    assert out.notes == ()


# --------------------------------------------------------------------------
# Model compatibility: the failure that must be loud
# --------------------------------------------------------------------------


def test_coda_does_not_support_bracket_controls() -> None:
    """Documented Rime behaviour, and the reason this module has two strategies."""
    assert MODEL_SUPPORTS_BRACKETS["coda"] is False
    assert MODEL_SUPPORTS_BRACKETS["mistv2"] is True


def test_phoneme_on_coda_raises_rather_than_no_opping() -> None:
    with pytest.raises(PronunciationError) as exc:
        resolve_strategy(Strategy.PHONEME, "coda")
    msg = str(exc.value)
    assert "coda" in msg
    assert "respell" in msg, "the error must name the fix"


def test_phoneme_on_mistv2_is_allowed() -> None:
    assert resolve_strategy(Strategy.PHONEME, "mistv2") is Strategy.PHONEME


def test_phoneme_on_non_english_mistv3_is_refused() -> None:
    assert resolve_strategy(Strategy.PHONEME, "mistv3", "eng") is Strategy.PHONEME
    with pytest.raises(PronunciationError):
        resolve_strategy(Strategy.PHONEME, "mistv3", "spa")


def test_non_strict_downgrades_instead_of_raising() -> None:
    """The evidence harness sweeps every combination on purpose."""
    assert (
        resolve_strategy(Strategy.PHONEME, "coda", strict=False) is Strategy.RESPELL
    )


def test_respell_works_on_every_model() -> None:
    for model in MODEL_SUPPORTS_BRACKETS:
        assert resolve_strategy(Strategy.RESPELL, model) is Strategy.RESPELL


def test_render_downgrade_is_disclosed_in_notes() -> None:
    out = render("Gough Street", strategy=Strategy.PHONEME, model="coda", strict=False)
    assert out.strategy is Strategy.RESPELL
    assert any("ignores bracket controls" in n for n in out.notes)


def test_render_strict_raises_on_coda() -> None:
    with pytest.raises(PronunciationError):
        render("Gough", strategy=Strategy.PHONEME, model="coda", strict=True)


# --------------------------------------------------------------------------
# Addresses end to end
# --------------------------------------------------------------------------


def test_full_address() -> None:
    out = speak_address("1247", "Gough Street", "4B")
    assert out.text == "twelve forty-seven Goff Street, unit four B"


def test_address_without_unit() -> None:
    assert speak_address("836", "Haight Street").text == "eight thirty-six Hate Street"


def test_address_with_pause_brackets() -> None:
    out = speak_address("836", "Haight Street", "2", pause_ms=300)
    assert " <300> " in out.text


def test_address_reports_which_lexicon_entries_fired() -> None:
    assert speak_address("1247", "Gough Street").applied == ("Gough->Goff",)


def test_rendered_serialises() -> None:
    d = speak_address("1247", "Gough Street", "4B").to_dict()
    assert d["strategy"] == "respell"
    assert d["applied"] == ["Gough->Goff"]


# --------------------------------------------------------------------------
# Free-text number normalisation
#
# Structured utterances go through speak_address / speak_code. This layer
# exists for the text the LLM writes itself, where digits arrive unannounced.
# --------------------------------------------------------------------------


def test_house_number_before_a_lexicon_street() -> None:
    out, applied = normalize_numbers_for_ear("Next stop 660 Vallejo Street")
    assert out == "Next stop six sixty Vallejo Street"
    assert applied == ["660->six sixty"]


def test_house_number_before_a_generic_street_suffix() -> None:
    out, _ = normalize_numbers_for_ear("Head to 1247 Maple Avenue")
    assert out.startswith("Head to twelve forty-seven Maple")


def test_house_number_before_a_bare_suffix() -> None:
    out, _ = normalize_numbers_for_ear("it is 836 St")
    assert "eight thirty-six" in out


def test_gate_code_becomes_digits() -> None:
    out, applied = normalize_numbers_for_ear("Gate code 1150 at the side door")
    assert out == "Gate code one one five zero at the side door"
    assert applied == ["1150->one one five zero"]


@pytest.mark.parametrize("prefix", ["code", "Code", "gate code", "PIN", "pin"])
def test_code_prefixes(prefix: str) -> None:
    out, _ = normalize_numbers_for_ear(f"{prefix} 4417")
    assert "four four one seven" in out


def test_leading_zero_in_a_code_survives() -> None:
    out, _ = normalize_numbers_for_ear("code 0921")
    assert out == "code zero nine two one"


@pytest.mark.parametrize(
    "text",
    [
        "14 minutes to the next stop",
        "0.4 miles away",
        "8 left on the route",
        "window closes at 11:00",
        "unit 4B on the second floor",
    ],
)
def test_ordinary_numbers_are_left_alone(text: str) -> None:
    """A general 'spell every number' pass would mangle these for no benefit."""
    out, applied = normalize_numbers_for_ear(text)
    assert out == text
    assert applied == []


def test_render_applies_numbers_then_the_lexicon() -> None:
    out = render("Next stop 660 Vallejo Street, gate code 1150")
    assert "six sixty" in out.text
    assert "Va-LAY-ho" in out.text
    assert "one one five zero" in out.text
    assert "660" not in out.text and "1150" not in out.text


def test_render_records_number_substitutions_first() -> None:
    out = render("836 Haight Street")
    assert out.applied[0] == "836->eight thirty-six"
    assert "Haight->Hate" in out.applied


def test_strategy_none_skips_number_normalisation() -> None:
    """The 'before' arm of the experiment must be genuinely untouched."""
    out = render("660 Vallejo Street", strategy=Strategy.NONE)
    assert out.text == "660 Vallejo Street"
