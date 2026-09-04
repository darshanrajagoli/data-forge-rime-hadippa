#!/usr/bin/env python3
"""Rime time-to-first-audio, with cold and warm runs kept apart.

    python evidence/measure_latency.py                # 1 cold + 12 warm
    python evidence/measure_latency.py --warm 30
    python evidence/measure_latency.py --compare-transport

Requires ``RIME_API_KEY``. Writes ``evidence/results/latency.json`` and
``latency.md``.

What is measured, and where the stopwatch stops
-----------------------------------------------
``server_first_frame`` -- from handing text to :class:`rime.TTS` to the first
audio frame arriving in this process. It covers the Rime request, queueing and
synthesis, and on a cold run also TLS and the WebSocket upgrade.

It does **not** cover the LiveKit hop, the client jitter buffer or the speaker,
so it is **not** what the driver experiences. The end-to-end number lives in
the browser console (``client_first_audio``) because only the browser can see
its own output. This script says so on every table rather than letting the
smaller number stand in for the bigger one.

Cold and warm are reported separately and never averaged, because the first
call of a process carries connection setup that no later call pays.
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

from _rime import probe, rime_session, synth  # noqa: E402

from waypoint.config import load_settings  # noqa: E402
from waypoint.metrics import Boundary, MetricsLog, Warmth, percentile  # noqa: E402

OUT = ROOT / "evidence" / "results"

#: Short, realistic turns. Length matters for time-to-first-audio, so the
#: corpus is what the agent actually says rather than lorem ipsum.
UTTERANCES = [
    "Fourteen minutes to Goff Street.",
    "Next is stop three, twenty-one ninety Ger-RARE-oh Street, unit two.",
    "Gate code four four one seven.",
    "Eight left. Next few are Hate, Ger-RARE-oh and NO-ee.",
    "Marked S1 delivered.",
]


async def one_shot(tts, text: str) -> tuple[float | None, int, str | None]:
    """Return (ms to first frame, total frames, error).

    Uses :func:`_rime.synth`, which drives ``stream()`` or ``synthesize()``
    depending on ``tts.capabilities.streaming``. Calling ``synthesize()``
    directly, as this did, raises on the shipped WebSocket configuration
    before any network I/O -- so every number this script could ever have
    produced was an exception.
    """
    r = await synth(tts, text)
    return r.first_frame_ms, r.frames, r.error


async def run_series(
    log: MetricsLog, settings, use_websocket: bool, warm_n: int
) -> list[str]:
    """One cold call then ``warm_n`` warm calls on a single TTS instance."""
    from waypoint.agent import build_tts

    label = "websocket" if use_websocket else "http"
    errors: list[str] = []
    settings = type(settings)(
        **{**settings.__dict__, "rime_use_websocket": use_websocket}
    )
    tts = build_tts(settings)

    ms, frames, err = await one_shot(tts, UTTERANCES[0])
    if err:
        errors.append(f"cold/{label}: {err}")
    elif ms is not None:
        log.record(
            f"rime.first_frame.{label}", ms, Boundary.SERVER_FIRST_FRAME,
            warmth=Warmth.COLD, frames=frames, text=UTTERANCES[0][:40],
        )
        print(f"  {label:9s} cold  {ms:7.1f} ms  ({frames} frames)")

    for i in range(warm_n):
        text = UTTERANCES[(i % (len(UTTERANCES) - 1)) + 1]
        ms, frames, err = await one_shot(tts, text)
        if err:
            errors.append(f"warm[{i}]/{label}: {err}")
            continue
        if ms is None:
            continue
        log.record(
            f"rime.first_frame.{label}", ms, Boundary.SERVER_FIRST_FRAME,
            warmth=Warmth.WARM, frames=frames, text=text[:40],
        )
        print(f"  {label:9s} warm  {ms:7.1f} ms  ({frames} frames)")
    return errors


def to_markdown(log: MetricsLog, meta: dict) -> str:
    lines = [
        "# Rime time-to-first-audio",
        "",
        f"- Run at: `{meta['run_at']}`",
        f"- Model / voice: `{meta['model']}` / `{meta['voice']}`, lang `{meta['lang']}`",
        f"- Sample rate: {meta['sample_rate']} Hz",
        f"- Command: `python evidence/measure_latency.py --warm {meta['warm_n']}`",
        "",
        "## Where the stopwatch stops",
        "",
        "| boundary | what it includes | what it omits |",
        "|---|---|---|",
        "| `server_first_frame` (this file) | Rime request, queueing, synthesis; "
        "plus TLS and WebSocket upgrade on the cold run | the LiveKit hop, the "
        "client jitter buffer, the speaker |",
        "| `client_first_audio` (browser console) | all of the above, end to end | "
        "nothing this side of the driver's ear |",
        "",
        "**This file's numbers are not the driver's experience.** They are the "
        "provider-side component of it. The end-to-end figure is measured in "
        "the browser, where the audio actually plays.",
        "",
        "## Results",
        "",
        "| series | warmth | n | p50 | p95 | min | max |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in log.series():
        d = s.summary()
        if d["n"] == 0:
            continue
        lines.append(
            f"| `{d['name']}` | {d['warmth']} | {d['n']} | {d['p50_ms']} | "
            f"{d['p95_ms']} | {d['min_ms']} | {d['max_ms']} |"
        )
    lines += ["", "Percentiles are nearest-rank (`ceil(p/100 * n)`), not interpolated."]
    small = [s.summary() for s in log.series() if 0 < s.summary()["n"] < 10]
    if small:
        lines += [
            "",
            "**Small samples.** "
            + "; ".join(f"`{d['name']}`/{d['warmth']} n={d['n']}" for d in small)
            + ". Treat these as exploratory, not as a service level.",
        ]
    if meta.get("errors"):
        lines += ["", "## Errors", ""] + [f"- `{e}`" for e in meta["errors"]]
    return "\n".join(lines) + "\n"


async def main_async(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--warm", type=int, default=12, help="warm calls per series")
    ap.add_argument(
        "--compare-transport", action="store_true",
        help="also run the HTTP path, to show what the WebSocket path buys",
    )
    args = ap.parse_args(argv)

    if not os.environ.get("RIME_API_KEY"):
        print("RIME_API_KEY is not set.", file=sys.stderr)
        return 2

    settings = load_settings()
    print(f"\n  model={settings.rime_model} voice={settings.rime_speaker} "
          f"lang={settings.rime_lang} sr={settings.rime_sample_rate}\n")

    log = MetricsLog(f"latency-{time.strftime('%Y%m%dT%H%M%S')}")
    # One HTTP context for the whole run: opening one per call would reconnect
    # every time and make the cold/warm distinction meaningless.
    async with rime_session():
        from waypoint.agent import build_tts

        if err := await probe(build_tts(settings)):
            print(file=sys.stderr)
            print(f"  Rime is not reachable: {err}", file=sys.stderr)
            print(f"  endpoint: {settings.endpoint}", file=sys.stderr)
            print(file=sys.stderr)
            return 2
        errors = await run_series(log, settings, True, args.warm)
        if args.compare_transport:
            print()
            errors += await run_series(log, settings, False, args.warm)

    meta = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": settings.rime_model,
        "voice": settings.rime_speaker,
        "lang": settings.rime_lang,
        "sample_rate": settings.rime_sample_rate,
        "warm_n": args.warm,
        "errors": errors,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latency.json").write_text(
        json.dumps({"meta": meta, **json.loads(log.to_json())}, indent=2),
        encoding="utf-8",
    )
    (OUT / "latency.md").write_text(to_markdown(log, meta), encoding="utf-8")

    print()
    for s in log.series():
        d = s.summary()
        if d["n"]:
            print(f"  {d['name']:32s} {d['warmth']:5s} n={d['n']:<3d} "
                  f"p50={d['p50_ms']:.0f} p95={d['p95_ms']:.0f}")
    print(f"\n  wrote {OUT / 'latency.md'}")
    if errors:
        print(f"  {len(errors)} error(s):")
        for e in errors[:5]:
            print(f"    ! {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async(sys.argv[1:])))
