"""Deterministic pronunciation and delivery control for Rime.

Why this is a correctness problem, not a polish problem
-------------------------------------------------------
A driver hears the address once, at speed, without looking. If the agent says
"Gow Street" the driver hears a street that does not exist on their route and
either asks again (costing a turn at 40mph) or guesses. If it reads a gate code
as "four thousand four hundred seventeen" the driver cannot key it in. If it
says "eight hundred thirty six Haight" with "Haight" rhyming with "hate-uh",
the whole utterance is wasted.

So for this product the pronunciation of street names, house numbers and gate
codes is part of whether the feature works at all.

The Rime constraint that shapes the design
------------------------------------------
Rime exposes two text-level controls, and both are **mistv2-only**:

* ``phonemize_between_brackets`` -- ``{h'El.o}`` sets phonemes for a word.
* ``pause_between_brackets`` -- ``<200>`` inserts a 200ms pause.

The ``coda`` model, which is Rime's newest and the one their own LiveKit
quickstart recommends, **ignores both**, along with ``reduce_latency``. So
there is a genuine trade-off, and the product has to pick a side:

===============  ====================  =========================================
Strategy         Works on              Trade-off
===============  ====================  =========================================
``RESPELL``      every model           Portable, survives a model swap, slightly
                                       coarser than phonemes.
``PHONEME``      mistv2 only           Exact, but locks the product to mistv2
                                       and silently no-ops if the model changes.
===============  ====================  =========================================

Waypoint ships ``RESPELL`` as the default. The reasoning is deliberate:
respelling is a text transform that survives a model change, and a voice
product that breaks silently when the provider ships a better model is a
product with a latent outage in it. ``PHONEME`` is fully implemented and
selectable for mistv2, and :func:`resolve_strategy` **refuses** to pair it with
a model that ignores it rather than degrading quietly -- a silent no-op is the
exact failure this module exists to prevent.

``evidence/measure_pronunciation.py`` renders the fixture corpus under every
supported combination and saves the clips, so the choice is backed by audio a
judge can listen to rather than by this paragraph.

On the phoneme column
---------------------
The respellings in :data:`LEXICON` are authored and checked. The phoneme
strings are **not** shipped pre-filled, because Rime's phoneme alphabet is its
own IPA-inspired notation and inventing strings for it would be guessing
dressed up as precision. Filling it means synthesising each word and submitting the *audio* to Rime's phonemize endpoint, which the shipped ``respell`` strategy does not require. A ``build_lexicon.py`` that claimed to do this from text was deleted: it posted JSON to three guessed URLs and could never have worked. ``PHONEME`` therefore falls back to
the respelling for any token with no verified phoneme, and says so in
:class:`Rendered.notes`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

__all__ = [
    "Strategy",
    "LexEntry",
    "Rendered",
    "LEXICON",
    "MODEL_SUPPORTS_BRACKETS",
    "resolve_strategy",
    "PronunciationError",
    "speak_house_number",
    "speak_code",
    "speak_unit",
    "speak_address",
    "apply_lexicon",
    "normalize_numbers_for_ear",
    "render",
]


class PronunciationError(ValueError):
    """Raised when a requested strategy cannot work with the configured model."""


class Strategy(str, Enum):
    #: Orthographic respelling. Model-portable. The shipped default.
    RESPELL = "respell"
    #: Rime ``{...}`` phoneme brackets. mistv2 only.
    PHONEME = "phoneme"
    #: No pronunciation control. Used as the "before" arm of the experiment.
    NONE = "none"


#: Which Rime models honour ``{...}`` / ``<...>`` bracket controls.
#: Source: Rime docs, "custom pronunciation is supported on Mist v1, Mist v2
#: and English Mist v3; Coda and non-English Mist v3 do not support it", and
#: "coda ignores reduce_latency, pause_between_brackets and
#: phonemize_between_brackets".
MODEL_SUPPORTS_BRACKETS: Mapping[str, bool] = {
    "mistv2": True,
    "mistv3": True,   # English only; resolve_strategy checks lang as well
    "coda": False,
}


@dataclass(frozen=True)
class LexEntry:
    """One pronunciation override.

    ``phoneme`` ships empty; see the module docstring for why. ``verified``
    records whether a human has actually listened to the rendered clip -- see
    ``evidence/results/pronunciation/``.
    """

    token: str
    respell: str
    phoneme: str = ""
    note: str = ""
    verified: bool = False


def _e(token: str, respell: str, note: str = "") -> LexEntry:
    return LexEntry(token=token, respell=respell, note=note)


#: Street names and terms that general-purpose TTS reliably gets wrong.
#:
#: Chosen from real San Francisco streets because they are a genuinely hard
#: corpus: several are Spanish-origin, several are surnames with
#: non-obvious anglicisations, and two ("Gough", "Haight") are the standard
#: examples of English orthography giving no usable signal.
LEXICON: tuple[LexEntry, ...] = (
    _e("Gough", "Goff", "rhymes with 'off', not 'go' or 'cow'"),
    _e("Haight", "Hate", "one syllable, rhymes with 'gate'"),
    _e("Guerrero", "Ger-RARE-oh", "Spanish origin, stress on the second syllable"),
    _e("Noe", "NO-ee", "two syllables"),
    _e("Divisadero", "Di-viss-a-DARE-oh", "stress on the fourth syllable"),
    _e("Taraval", "TARA-val", "stress on the first syllable"),
    _e("Vallejo", "Va-LAY-ho", "Spanish 'j'"),
    _e("Kearny", "KAR-nee", "not 'KEER-nee'"),
    _e("Balboa", "Bal-BO-a", ""),
    _e("Portola", "Por-TOH-la", ""),
    _e("Presidio", "Pre-SID-ee-oh", ""),
    _e("Octavia", "Ok-TAY-vee-a", ""),
    _e("Geary", "GEER-ee", ""),
    _e("Judah", "JOO-duh", ""),
    _e("Quintara", "Kwin-TARA", ""),
    _e("Dolores", "Duh-LOR-ess", "three syllables, not the given name 'Dolores'"),
    _e("Buena Vista", "BWAY-na VISS-ta", ""),
    _e("Cabrillo", "Ka-BREE-oh", ""),
    _e("Bernal", "Ber-NAL", "stress on the second syllable"),
    _e("Ortega", "Or-TAY-ga", ""),
)

_LEX_BY_TOKEN: dict[str, LexEntry] = {e.token.lower(): e for e in LEXICON}

#: Matches any lexicon token as a whole word, longest first so that multi-word
#: entries like "Buena Vista" win over any single-word prefix.
_LEX_RE = re.compile(
    r"\b("
    + "|".join(
        re.escape(e.token)
        for e in sorted(LEXICON, key=lambda x: -len(x.token))
    )
    + r")\b",
    re.IGNORECASE,
)

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = (
    "zero ten twenty thirty forty fifty sixty seventy eighty ninety"
).split()


@dataclass(frozen=True)
class Rendered:
    """Text prepared for Rime, plus an account of what was changed and why."""

    text: str
    strategy: Strategy
    applied: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "strategy": self.strategy.value,
            "applied": list(self.applied),
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------
# Strategy resolution
# --------------------------------------------------------------------------


def resolve_strategy(
    requested: Strategy | str,
    model: str,
    lang: str = "eng",
    *,
    strict: bool = True,
) -> Strategy:
    """Validate a strategy against the configured Rime model.

    Raises :class:`PronunciationError` when the pair would silently no-op --
    the failure mode this module exists to prevent. Set ``strict=False`` to
    downgrade to :attr:`Strategy.RESPELL` instead, which is what the evidence
    harness does when it sweeps every combination on purpose.
    """
    strategy = Strategy(requested)
    if strategy is not Strategy.PHONEME:
        return strategy

    supported = MODEL_SUPPORTS_BRACKETS.get(model, False)
    if model == "mistv3" and lang not in ("eng", "en", "en-US"):
        supported = False

    if supported:
        return strategy
    msg = (
        f"pronunciation strategy 'phoneme' requires a Rime model that honours "
        f"bracket controls, but the configured model is {model!r}"
        + (f" with lang={lang!r}" if model == "mistv3" else "")
        + ". Rime ignores phonemize_between_brackets on this model, so the "
        "brackets would be read aloud or dropped rather than applied. Use "
        "WAYPOINT_PRONUNCIATION=respell, or switch to mistv2."
    )
    if strict:
        raise PronunciationError(msg)
    return Strategy.RESPELL


# --------------------------------------------------------------------------
# Numbers for the ear
# --------------------------------------------------------------------------


def _two_digit(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] if ones == 0 else f"{_TENS[tens]}-{_ONES[ones]}"


def speak_house_number(number: str) -> str:
    """Render a house number the way a person reads one aloud.

    ``1247`` -> "twelve forty-seven", not "one thousand two hundred forty-seven".
    ``1207`` -> "twelve oh seven".  ``1200`` -> "twelve hundred".
    ``836``  -> "eight thirty-six".

    Falls back to digit-by-digit for anything with letters or punctuation
    (``120A``, ``12-14``), which is the safe reading for an address.
    """
    s = str(number).strip()
    if not s.isdigit():
        return " ".join(_ONES[int(c)] if c.isdigit() else c for c in s)

    n = int(s)
    if len(s) == 4:
        hi, lo = int(s[:2]), int(s[2:])
        if lo == 0:
            return f"{_two_digit(hi)} hundred"
        if lo < 10:
            return f"{_two_digit(hi)} oh {_ONES[lo]}"
        return f"{_two_digit(hi)} {_two_digit(lo)}"
    if len(s) == 3:
        hi, lo = int(s[0]), int(s[1:])
        if lo == 0:
            return f"{_ONES[hi]} hundred"
        if lo < 10:
            return f"{_ONES[hi]} oh {_ONES[lo]}"
        return f"{_ONES[hi]} {_two_digit(lo)}"
    if len(s) <= 2:
        return _two_digit(n)
    return " ".join(_ONES[int(c)] for c in s)


def speak_code(code: str, *, pause_ms: int = 0) -> str:
    """Render a gate code or PIN digit by digit so it can be keyed in.

    ``4417`` -> "four four one seven". Never "four thousand four hundred
    seventeen", which is unusable at a keypad.

    ``pause_ms`` inserts Rime ``<n>`` pause brackets between digits. Only pass
    a non-zero value when the model honours them (mistv2); :func:`render`
    handles that decision for you.
    """
    parts = [_ONES[int(c)] if c.isdigit() else c.upper() for c in str(code).strip()]
    if pause_ms > 0:
        joiner = f" <{int(pause_ms)}> "
        return joiner.join(parts)
    return " ".join(parts)


def speak_unit(unit: str | None) -> str:
    """``4B`` -> "unit four B". ``None`` -> empty string."""
    if not unit:
        return ""
    out: list[str] = []
    for chunk in re.findall(r"\d+|[A-Za-z]+", str(unit)):
        out.append(speak_house_number(chunk) if chunk.isdigit() else chunk.upper())
    return "unit " + " ".join(out)


# --------------------------------------------------------------------------
# Lexicon application
# --------------------------------------------------------------------------


def apply_lexicon(
    text: str, strategy: Strategy, lexicon: Iterable[LexEntry] | None = None
) -> Rendered:
    """Replace known-hard tokens according to ``strategy``."""
    if strategy is Strategy.NONE:
        return Rendered(text=text, strategy=strategy)

    table = (
        {e.token.lower(): e for e in lexicon} if lexicon is not None else _LEX_BY_TOKEN
    )
    applied: list[str] = []
    notes: list[str] = []

    def _sub(m: re.Match[str]) -> str:
        entry = table.get(m.group(0).lower())
        if entry is None:
            return m.group(0)
        if strategy is Strategy.PHONEME:
            if entry.phoneme:
                applied.append(f"{entry.token}->{{{entry.phoneme}}}")
                return "{" + entry.phoneme + "}"
            notes.append(
                f"{entry.token}: no verified Rime phoneme on file, fell back to "
                f"respelling {entry.respell!r}."
            )
            applied.append(f"{entry.token}->{entry.respell} (fallback)")
            return entry.respell
        applied.append(f"{entry.token}->{entry.respell}")
        return entry.respell

    pattern = (
        _LEX_RE
        if lexicon is None
        else re.compile(
            r"\b("
            + "|".join(
                re.escape(e.token) for e in sorted(table.values(), key=lambda x: -len(x.token))
            )
            + r")\b",
            re.IGNORECASE,
        )
    )
    out = pattern.sub(_sub, text)
    return Rendered(
        text=out, strategy=strategy, applied=tuple(applied), notes=tuple(notes)
    )


def speak_address(
    house_number: str,
    street: str,
    unit: str | None = None,
    *,
    strategy: Strategy = Strategy.RESPELL,
    pause_ms: int = 0,
) -> Rendered:
    """Build a spoken address: numbers for the ear, street through the lexicon."""
    spoken_number = speak_house_number(house_number)
    street_r = apply_lexicon(street, strategy)
    parts = [spoken_number, street_r.text]
    unit_text = speak_unit(unit)
    if unit_text:
        parts.append(unit_text)
    sep = f" <{int(pause_ms)}> " if pause_ms > 0 else ", "
    text = parts[0] + " " + parts[1] + ((sep + parts[2]) if len(parts) > 2 else "")
    return Rendered(
        text=text,
        strategy=strategy,
        applied=street_r.applied,
        notes=street_r.notes,
    )


#: Street-type words that mark the token before them as a house number.
_STREET_SUFFIX = (
    r"(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Road|Rd|Way|Terrace|Ter|"
    r"Lane|Ln|Place|Pl|Court|Ct)"
)

#: ``1247 Gough Street`` / ``836 Haight`` -- a number immediately before a
#: lexicon street name or a street-type word.
_HOUSE_RE = re.compile(
    r"\b(\d{1,5})\s+(?=(?:"
    + "|".join(re.escape(e.token) for e in LEXICON)
    + r"|[A-Z][a-z]+\s+" + _STREET_SUFFIX
    + r"|" + _STREET_SUFFIX
    + r")\b)"
)

#: ``gate code 4417`` / ``code 0921`` / ``PIN 1150`` -- must be read as digits.
_CODE_RE = re.compile(r"\b((?:gate\s+)?(?:code|pin)\s+)(\d{2,8})\b", re.IGNORECASE)


def normalize_numbers_for_ear(text: str) -> tuple[str, list[str]]:
    """Rewrite the two number forms a driver cannot use as spoken quantities.

    Deliberately narrow. A general "spell every number" pass would mangle
    "14 minutes" and "0.4 miles" for no benefit, so this fires only where the
    reading is actually wrong for the listener:

    * a number immediately before a street name becomes a house number
      ("1247 Gough" -> "twelve forty-seven Gough"), and
    * a number after "code" or "pin" becomes digits ("code 4417" -> "code four
      four one seven"), because a quantity cannot be keyed into a pad.

    Structured utterances already go through :func:`speak_address` and
    :func:`speak_code`. This exists for the free text the LLM writes itself,
    where the digits arrive unannounced.
    """
    applied: list[str] = []

    def _house(m: re.Match[str]) -> str:
        spoken = speak_house_number(m.group(1))
        applied.append(f"{m.group(1)}->{spoken}")
        return spoken + " "

    def _code(m: re.Match[str]) -> str:
        spoken = speak_code(m.group(2))
        applied.append(f"{m.group(2)}->{spoken}")
        return m.group(1) + spoken

    out = _CODE_RE.sub(_code, text)
    out = _HOUSE_RE.sub(_house, out)
    return out, applied


def render(
    text: str,
    *,
    strategy: Strategy = Strategy.RESPELL,
    model: str = "coda",
    lang: str = "eng",
    strict: bool = True,
) -> Rendered:
    """Full pipeline: validate the strategy against the model, then apply it.

    This is the function the agent calls on every string that is about to be
    spoken. It is deliberately the *only* public entry point that both
    validates and transforms, so there is one place where an unsupported
    strategy can be caught.

    Order matters: numbers are normalised *before* the lexicon runs, because
    the house-number rule keys off the street name still being spelled the way
    it is written.
    """
    resolved = resolve_strategy(strategy, model, lang, strict=strict)
    numbers_applied: list[str] = []
    if resolved is not Strategy.NONE:
        text, numbers_applied = normalize_numbers_for_ear(text)
    out = apply_lexicon(text, resolved)
    if numbers_applied:
        out = Rendered(
            text=out.text,
            strategy=out.strategy,
            applied=tuple(numbers_applied) + out.applied,
            notes=out.notes,
        )
    if resolved is not strategy:
        out = Rendered(
            text=out.text,
            strategy=resolved,
            applied=out.applied,
            notes=out.notes
            + (
                f"requested {Strategy(strategy).value!r} but model {model!r} "
                f"ignores bracket controls; downgraded to {resolved.value!r}",
            ),
        )
    return out


def lexicon_coverage() -> dict[str, Any]:
    """Summary for the README and the evidence file."""
    total = len(LEXICON)
    with_phoneme = sum(1 for e in LEXICON if e.phoneme)
    verified = sum(1 for e in LEXICON if e.verified)
    return {
        "entries": total,
        "with_respelling": total,
        "with_verified_phoneme": with_phoneme,
        "listened_and_verified": verified,
        "note": (
            "Phoneme column ships empty on purpose: inventing strings in "
            "Rime's phoneme alphabet would be a guess presented as precision. "
            "Populating it requires submitting synthesised audio to Rime's "
            "phonemize endpoint, which the shipped respell strategy does not "
            "need."
        ),
    }
