#!/usr/bin/env python3
"""Pronunciation experiment: does the respelling layer actually help?

    python evidence/measure_pronunciation.py                 # default sweep
    python evidence/measure_pronunciation.py --models coda mistv2
    python evidence/measure_pronunciation.py --no-audio       # text only

Requires ``RIME_API_KEY``. Writes clips and a report to
``evidence/results/pronunciation/``.

What the brief asks for
-----------------------
"For prompting or delivery claims, hold the model and voice constant, render at
least two text variants, save the clips, and explain which wording or
punctuation changed the result."

So: one voice per model, held constant; the same fixture corpus rendered under
every pronunciation strategy; every clip saved with a deterministic filename;
and a report that pairs them so a judge can listen to A and B back to back.

What this can and cannot establish
----------------------------------
It **can** establish that the text reaching Rime differs, that both variants
synthesise without error, and that the audio differs measurably. It saves the
clips so a human can hear which one says "Goff" and which says "Gow".

It **cannot** establish intelligibility on its own. Whether a driver hears the
right street is a listening judgement, and this script does not pretend to
automate it. It produces the listening test rather than substituting for one:
``report.md`` has a table with a blank verdict column, and
``docs/LISTENING_TEST.md`` says how to fill it in. Any row still blank is
reported as unverified, not as a pass.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import struct
import sys
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv

    for _n in (".env.local", ".env"):
        if (ROOT / _n).exists():
            load_dotenv(ROOT / _n, override=False)
except ImportError:
    pass

from _rime import probe, rime_session, synth  # noqa: E402
from livekit.plugins import rime  # noqa: E402

from waypoint.pronounce import (  # noqa: E402
    LEXICON,
    Strategy,
    apply_lexicon,
    resolve_strategy,
    speak_address,
    speak_code,
)

OUT = ROOT / "evidence" / "results" / "pronunciation"

#: One voice per model, held constant across strategies. The comparison is
#: between *text variants*, so anything else must not move.
VOICES = {"coda": "lyra", "mistv2": "cove", "mistv3": "cove"}


@dataclass
class Fixture:
    """One thing a driver has to get right by ear the first time."""

    fid: str
    kind: str
    raw: str
    why: str


def build_fixtures() -> list[Fixture]:
    out: list[Fixture] = [
        Fixture(
            "addr-gough", "address", "1247 Gough Street, unit 4B",
            "Gough is the standard example of English orthography giving TTS "
            "nothing usable. 'Gow' or 'Go' sends the driver to a street that "
            "is not on their route.",
        ),
        Fixture(
            "addr-haight", "address", "836 Haight Street",
            "One syllable, rhymes with gate. Commonly read as two.",
        ),
        Fixture(
            "addr-guerrero", "address", "2190 Guerrero Street, unit 2",
            "Spanish origin; stress on the second syllable.",
        ),
        Fixture(
            "addr-divisadero", "address", "3401 Divisadero Street, unit 11C",
            "Four syllables before the stress. Easy to garble at speed.",
        ),
        Fixture(
            "code-4417", "gate code", "gate code 4417",
            "Read as a quantity ('four thousand four hundred seventeen') it "
            "cannot be keyed into a pad.",
        ),
        Fixture(
            "code-0921", "gate code", "gate code 0921",
            "Leading zero. Must survive as a digit, not be dropped.",
        ),
        Fixture(
            "num-1207", "house number", "1207 Noe Street",
            "'Twelve oh seven', not 'one thousand two hundred seven'.",
        ),
        Fixture(
            "mixed", "full utterance",
            "Next stop 660 Vallejo Street, unit A. Gate code 1150. "
            "Then Kearny and Taraval.",
            "Everything at once, which is what an actual turn sounds like.",
        ),
    ]
    return out


def render_variant(fx: Fixture, strategy: Strategy, pause_ms: int) -> str:
    """Produce the text that will be sent to Rime for this variant."""
    if strategy is Strategy.NONE:
        return fx.raw
    if fx.kind == "address":
        head, _, tail = fx.raw.partition(",")
        parts = head.split(None, 1)
        number, street = (parts[0], parts[1]) if len(parts) == 2 else ("", head)
        unit = tail.replace("unit", "").strip() or None
        return speak_address(
            number, street, unit, strategy=strategy, pause_ms=pause_ms
        ).text
    if fx.kind == "gate code":
        digits = "".join(c for c in fx.raw if c.isdigit())
        return f"gate code {speak_code(digits, pause_ms=pause_ms)}"
    if fx.kind == "house number":
        parts = fx.raw.split(None, 1)
        return speak_address(parts[0], parts[1], strategy=strategy).text
    return apply_lexicon(fx.raw, strategy).text


async def synthesize(text: str, model: str, voice: str, strategy: Strategy,
                     pause_ms: int, path: Path) -> dict:
    """Render one variant through the real plugin and write a WAV."""
    sample_rate = 22050
    kwargs = {
        "model": model, "speaker": voice, "lang": "eng",
        "sample_rate": sample_rate, "use_websocket": True,
        "segment": "bySentence",
    }
    from waypoint.pronounce import MODEL_SUPPORTS_BRACKETS

    if MODEL_SUPPORTS_BRACKETS.get(model):
        kwargs["phonemize_between_brackets"] = strategy is Strategy.PHONEME
        kwargs["pause_between_brackets"] = pause_ms > 0

    tts = rime.TTS(**kwargs)
    rendered = await synth(tts, text)
    if rendered.error:
        return {"ok": False, "error": rendered.error, "transport": rendered.transport}
    if not rendered.pcm:
        return {"ok": False, "error": "no audio frames returned"}

    rendered.write_wav(path, sample_rate)
    pcm = rendered.pcm
    first_ms = rendered.first_frame_ms
    timed = len(rendered.timings)

    return {
        "ok": True,
        "transport": rendered.transport,
        "clip": str(path.relative_to(ROOT)).replace("\\", "/"),
        "bytes": len(pcm),
        "duration_s": round(len(pcm) / 2 / sample_rate, 3),
        "first_frame_ms": None if first_ms is None else round(first_ms, 1),
        "rms": round(rendered.rms(), 1),
        "word_timestamps": timed,
    }


async def main_async(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", default=["coda", "mistv2"])
    ap.add_argument(
        "--strategies", nargs="+", default=["none", "respell", "phoneme"]
    )
    ap.add_argument("--pause-ms", type=int, default=0)
    ap.add_argument("--no-audio", action="store_true", help="text variants only")
    args = ap.parse_args(argv)

    import os

    if not args.no_audio and not os.environ.get("RIME_API_KEY"):
        print(
            "RIME_API_KEY is not set. Either set it, or run with --no-audio to "
            "produce just the text-variant table.",
            file=sys.stderr,
        )
        return 2

    fixtures = build_fixtures()
    rows: list[dict] = []
    OUT.mkdir(parents=True, exist_ok=True)

    if not args.no_audio:
        # One cheap call before dozens of expensive ones. The plugin retries
        # each failure three times at two-second intervals, so without this a
        # wrong key costs minutes before it says anything useful.
        from waypoint.agent import build_tts
        from waypoint.config import load_settings

        async with rime_session():
            err = await probe(build_tts(load_settings()))
        if err:
            print(file=sys.stderr)
            print("  Rime is not reachable with this configuration:", file=sys.stderr)
            print(f"    {err}", file=sys.stderr)
            print(
                "  Nothing was rendered. Fix the credential or the model/voice "
                "pair, then re-run.",
                file=sys.stderr,
            )
            print(file=sys.stderr)
            return 2

    for model in args.models:
        voice = VOICES.get(model, "cove")
        for raw_strategy in args.strategies:
            # Non-strict: the sweep deliberately visits combinations Rime
            # ignores, so it can show what happens rather than refusing.
            requested = Strategy(raw_strategy)
            effective = resolve_strategy(requested, model, "eng", strict=False)
            downgraded = effective is not requested

            for fx in fixtures:
                text = render_variant(fx, effective, args.pause_ms)
                row = {
                    "fixture": fx.fid,
                    "kind": fx.kind,
                    "why_it_matters": fx.why,
                    "model": model,
                    "voice": voice,
                    "strategy_requested": requested.value,
                    "strategy_effective": effective.value,
                    "downgraded": downgraded,
                    "raw_text": fx.raw,
                    "sent_to_rime": text,
                    "changed": text != fx.raw,
                    "listening_verdict": "",   # filled in by a human
                }
                if not args.no_audio:
                    name = f"{model}-{voice}-{requested.value}-{fx.fid}.wav"
                    async with rime_session():
                        row.update(
                            await synthesize(
                                text, model, voice, effective, args.pause_ms,
                                OUT / name,
                            )
                        )
                rows.append(row)
                flag = "!" if downgraded else " "
                print(f" {flag} {model}/{requested.value:8s} {fx.fid:16s} -> {text[:64]}")

    payload = {
        "meta": {
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "models": args.models,
            "strategies": args.strategies,
            "voices_held_constant": VOICES,
            "pause_ms": args.pause_ms,
            "audio_rendered": not args.no_audio,
            "lexicon_entries": len(LEXICON),
            "limitation": (
                "Intelligibility is a listening judgement. This script renders "
                "and saves the variants; docs/LISTENING_TEST.md says how to "
                "score them. Rows with an empty listening_verdict are "
                "unverified and must be reported as such."
            ),
        },
        "rows": rows,
    }
    (OUT / "pronunciation.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (OUT / "report.md").write_text(to_markdown(payload), encoding="utf-8")

    errs = [r for r in rows if r.get("ok") is False]
    print()
    print(f"  {len(rows)} variants, {len(errs)} synthesis errors")
    print(f"  clips + report: {OUT}")
    if errs:
        for r in errs[:6]:
            print(f"    ! {r['model']}/{r['strategy_requested']} {r['fixture']}: {r['error']}")
    return 1 if errs else 0


def to_markdown(payload: dict) -> str:
    m = payload["meta"]
    lines = [
        "# Pronunciation experiment",
        "",
        f"- Run at: `{m['run_at']}`",
        f"- Models: {', '.join(m['models'])}  (voice held constant per model: "
        f"{m['voices_held_constant']})",
        f"- Strategies: {', '.join(m['strategies'])}",
        f"- Audio rendered: {m['audio_rendered']}",
        "",
        "**Limitation.** " + m["limitation"],
        "",
        "## Text variants",
        "",
        "| fixture | model | requested | effective | sent to Rime | clip | verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in payload["rows"]:
        clip = r.get("clip", "-")
        clip_cell = f"[wav]({Path(clip).name})" if clip != "-" else "-"
        eff = r["strategy_effective"] + (" *(downgraded)*" if r["downgraded"] else "")
        lines.append(
            f"| `{r['fixture']}` | {r['model']} | {r['strategy_requested']} | {eff} "
            f"| {r['sent_to_rime']} | {clip_cell} | "
            f"{r['listening_verdict'] or '_unverified_'} |"
        )
    lines += [
        "",
        "## Why each fixture is in the corpus",
        "",
    ]
    seen: set[str] = set()
    for r in payload["rows"]:
        if r["fixture"] in seen:
            continue
        seen.add(r["fixture"])
        lines.append(f"- **`{r['fixture']}`** ({r['kind']}) - {r['why_it_matters']}")
    lines += [
        "",
        "## Note on `coda`",
        "",
        "Rime documents `coda` as ignoring `phonemize_between_brackets`, "
        "`pause_between_brackets` and `reduce_latency`. Rows above where "
        "`requested = phoneme` and `model = coda` are marked *(downgraded)*: "
        "the run used respelling instead. That is why respelling is the "
        "shipped default -- it is the only strategy that survives a model "
        "change without silently becoming a no-op.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async(sys.argv[1:])))
