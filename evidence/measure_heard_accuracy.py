#!/usr/bin/env python3
"""How wrong is the estimator, when Rime's word timestamps are the ground truth?

    python evidence/measure_heard_accuracy.py
    python evidence/measure_heard_accuracy.py --cuts 12

Requires ``RIME_API_KEY``. Writes ``evidence/results/heard_accuracy.{json,md}``.

The question
------------
:mod:`waypoint.heard` has two ways to find the heard/unheard boundary after a
barge-in. Rime's WebSocket stream gives word-level timestamps, which make it
exact. Without them, we interpolate over character mass against total audio
duration, which is approximate.

The shipped configuration uses the WebSocket path. This script is the reason:
it renders real utterances through Rime, takes the real word timings as ground
truth, cuts at many points, and reports how far the estimator is off -- in
words, signed, so the dangerous direction is visible.

Positive error means the estimator **over-claimed**: it believed the driver
heard more than they did. That is the direction that loses a gate code, so it
is reported separately from the symmetric error.

If word timestamps do not arrive, the script says so and exits non-zero rather
than reporting an error of zero. An unverifiable claim is worse than an absent
one.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
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

from _rime import rime_session, synth  # noqa: E402

from waypoint.config import load_settings  # noqa: E402
from waypoint.heard import (  # noqa: E402
    HeardTracker,
    Method,
    WordMark,
    boundary_error_words,
)

OUT = ROOT / "evidence" / "results"

UTTERANCES = [
    "Your next stop is twelve forty-seven Goff Street, unit four B, and the "
    "gate code is four four one seven.",
    "Fourteen minutes to Ger-RARE-oh Street. The window closes at one pm.",
    "Eight stops left. The next few are Hate Street, Ger-RARE-oh and NO-ee.",
    "That one is marked delivered. Buzzer is broken, so use the keypad on the "
    "left of the gate.",
]


async def timings(text: str, settings) -> tuple[list[WordMark], float, str | None]:
    """Synthesise and collect Rime's word timestamps plus total duration.

    Delegates to :func:`_rime.synth`, which picks the transport from
    ``tts.capabilities.streaming`` and returns the word timings it found on
    each audio frame's userdata.

    Two bugs lived here. The first read ``ev.timed_words`` / ``ev.words`` /
    ``ev.alignment``, none of which exist on ``SynthesizedAudio``. The second
    was worse and outlived the fix to the first: this function called
    ``tts.synthesize()``, which the Rime plugin refuses when built for
    WebSocket -- while the script above refuses to run *unless* WebSocket is
    on. Two mutually exclusive preconditions, so it could not succeed in any
    configuration, and its "no word timestamps arrived" message would have
    fired for the wrong reason on every run.
    """
    from waypoint.agent import build_tts

    rendered = await synth(build_tts(settings), text)
    if rendered.error:
        return [], 0.0, rendered.error

    marks = [
        WordMark(t.word, t.start_ms, t.end_ms) for t in rendered.timings
    ]
    duration_ms = rendered.duration_s(settings.rime_sample_rate) * 1000.0
    return marks, duration_ms, None


def compare(text: str, marks: list[WordMark], duration_ms: float, cuts: int):
    """Cut at ``cuts`` evenly spaced points and compare the two methods."""
    rows = []
    for i in range(1, cuts + 1):
        at = duration_ms * i / (cuts + 1)

        exact_t = HeardTracker()
        exact_t.begin("u", text)
        exact_t.attach_marks("u", marks)
        exact = exact_t.cut("u", at)

        est_t = HeardTracker()
        est_t.begin("u", text)
        est_t.set_total_audio_ms("u", duration_ms)
        est = est_t.cut("u", at)

        rows.append(
            {
                "cut_ms": round(at, 1),
                "exact_words": exact.words_heard,
                "estimated_words": est.words_heard,
                "error_words": boundary_error_words(exact, est),
                "exact_method": exact.method.value,
                "estimated_method": est.method.value,
                "exact_heard": exact.heard_text,
                "estimated_heard": est.heard_text,
            }
        )
    return rows


def to_markdown(payload: dict) -> str:
    m, rows = payload["meta"], payload["rows"]
    errs = [r["error_words"] for r in rows]
    over = [e for e in errs if e > 0]
    lines = [
        "# Heard-not-said: estimator error against Rime word timestamps",
        "",
        f"- Run at: `{m['run_at']}`",
        f"- Model / voice: `{m['model']}` / `{m['voice']}`, WebSocket",
        f"- Utterances: {m['utterances']}, cuts per utterance: {m['cuts']}",
        f"- Total comparisons: {len(rows)}",
        "",
        "## Result",
        "",
        f"- Mean absolute error: **{statistics.fmean(abs(e) for e in errs):.2f} words**"
        if errs else "- no comparisons",
        f"- Max absolute error: **{max(abs(e) for e in errs)} words**" if errs else "",
        f"- Over-claimed (estimator thought the driver heard more than they did): "
        f"**{len(over)} of {len(errs)}** comparisons, worst **+{max(over) if over else 0}** words",
        "",
        "Positive error is the dangerous direction: it means the transcript "
        "would have recorded a word the driver never heard. That is how a gate "
        "code goes missing. The exact path has zero error by construction, "
        "which is why it is the shipped default and why "
        "`RIME_USE_WEBSOCKET=false` prints a warning at startup.",
        "",
        "## Per-cut detail",
        "",
        "| cut (ms) | exact words | estimated | error | estimated text |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        sign = f"+{r['error_words']}" if r["error_words"] > 0 else str(r["error_words"])
        lines.append(
            f"| {r['cut_ms']:.0f} | {r['exact_words']} | {r['estimated_words']} "
            f"| {sign} | {r['estimated_heard'][-46:]} |"
        )
    return "\n".join(x for x in lines if x != "") + "\n"


async def main_async(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cuts", type=int, default=9, help="cut points per utterance")
    args = ap.parse_args(argv)

    if not os.environ.get("RIME_API_KEY"):
        print("RIME_API_KEY is not set.", file=sys.stderr)
        return 2

    settings = load_settings()
    if not settings.rime_use_websocket:
        print(
            "RIME_USE_WEBSOCKET is false, so no word timestamps will arrive and "
            "there is no ground truth to compare against. Set it to true.",
            file=sys.stderr,
        )
        return 2

    all_rows, errors = [], []
    async with rime_session():
        rows_for = [(text, *(await timings(text, settings))) for text in UTTERANCES]
    for text, marks, duration_ms, err in rows_for:
        if err:
            errors.append(err)
            continue
        if not marks:
            errors.append(
                "no word timestamps arrived for: " + text[:48]
                + " ... The Rime plugin exposes them on the WebSocket path; if "
                "this persists, the plugin's event shape has changed and the "
                "attribute names in timings() need updating."
            )
            continue
        rows = compare(text, marks, duration_ms, args.cuts)
        for r in rows:
            r["utterance"] = text[:56]
        all_rows.extend(rows)
        print(f"  {len(marks):3d} word marks, {duration_ms:7.0f} ms  {text[:52]}")

    if not all_rows:
        print("\n  No comparisons produced. Nothing written.", file=sys.stderr)
        for e in errors[:4]:
            print(f"    ! {e}", file=sys.stderr)
        return 1

    payload = {
        "meta": {
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model": settings.rime_model,
            "voice": settings.rime_speaker,
            "utterances": len(UTTERANCES) - len(errors),
            "cuts": args.cuts,
            "errors": errors,
        },
        "rows": all_rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "heard_accuracy.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (OUT / "heard_accuracy.md").write_text(to_markdown(payload), encoding="utf-8")

    errs = [r["error_words"] for r in all_rows]
    print(f"\n  {len(all_rows)} comparisons")
    print(f"  mean |error| = {statistics.fmean(abs(e) for e in errs):.2f} words")
    print(f"  over-claimed in {sum(1 for e in errs if e > 0)} of {len(errs)}")
    print(f"  wrote {OUT / 'heard_accuracy.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async(sys.argv[1:])))
