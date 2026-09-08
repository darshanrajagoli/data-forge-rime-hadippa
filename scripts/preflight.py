#!/usr/bin/env python3
"""Preflight: prove the shipped path works before the demo, not during it.

    python scripts/preflight.py            # full check, needs credentials
    python scripts/preflight.py --offline  # everything that needs no network

The Rime brief lists "uses a model, voice, or language combination that fails
the event preflight and is not corrected before the deadline" as a
disqualifier, and separately requires that the *exact* endpoint, model, audio
format and transport used in the final demo be the one that was tested. So
this script does not check a plausible configuration; it constructs the real
:class:`livekit.plugins.rime.TTS` from the real :class:`Settings` and
synthesises real audio through it.

Checks, in order of how badly each one ruins a demo:

1. Configuration loads and is internally consistent.
2. No secret has leaked into the repository.
3. Every required credential is present.
4. The Rime model / speaker / language combination actually synthesises.
5. The WebSocket path works, since that is what the shipped config uses.
6. Word timestamps arrive, since heard-not-said depends on them.

Exit code 0 means the demo can be recorded.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evidence"))

from _rime import rime_session, synth  # noqa: E402

RESET, RED, GREEN, YELLOW, DIM = (
    "\033[0m", "\033[31m", "\033[32m", "\033[33m", "\033[2m"
)


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []
        self.failed = 0
        self.warned = 0

    def ok(self, label: str, detail: str = "") -> None:
        self.rows.append(("PASS", label, detail))

    def warn(self, label: str, detail: str = "") -> None:
        self.warned += 1
        self.rows.append(("WARN", label, detail))

    def fail(self, label: str, detail: str = "") -> None:
        self.failed += 1
        self.rows.append(("FAIL", label, detail))

    def render(self) -> None:
        print()
        print("=" * 72)
        print(" Waypoint preflight")
        print("=" * 72)
        for status, label, detail in self.rows:
            colour = {"PASS": GREEN, "WARN": YELLOW, "FAIL": RED}[status]
            print(f"  {colour}[{status}]{RESET} {label}")
            if detail:
                for line in detail.splitlines():
                    print(f"         {DIM}{line}{RESET}")
        print("-" * 72)
        if self.failed:
            print(f"  {RED}{self.failed} check(s) failed.{RESET} Do not record yet.")
        elif self.warned:
            print(f"  {YELLOW}Ready, with {self.warned} warning(s).{RESET}")
        else:
            print(f"  {GREEN}All checks passed. The shipped path works.{RESET}")
        print("=" * 72)


# --------------------------------------------------------------------------


def check_config(r: Report):
    from waypoint.config import ConfigError, load_settings

    try:
        settings = load_settings()
    except ConfigError as exc:
        r.fail("configuration is valid", str(exc))
        return None
    r.ok(
        "configuration is valid",
        f"{settings.rime_model}/{settings.rime_speaker} lang={settings.rime_lang} "
        f"{settings.transport} pronunciation={settings.pronunciation.value}",
    )
    for w in settings.warnings:
        r.warn("disclosed degradation", w)
    return settings


def check_secrets(r: Report) -> None:
    from secret_scan import scan  # type: ignore[import-not-found]

    findings = scan(ROOT)
    if findings:
        r.fail(
            "no secret in the repository",
            "\n".join(f"{f.path}:{f.line} {f.rule}" for f in findings[:10]),
        )
    else:
        r.ok("no secret in the repository", "scripts/secret_scan.py found nothing")


def check_docs(r: Report, skip_collect: bool) -> None:
    """The documentation still describes this repository.

    Cheap, offline, and it belongs in the gate that decides the demo may be
    recorded: a judge reads the README before they run anything, and a README
    that fails on its first command costs more than a slow one.
    """
    from check_docs import run_all  # type: ignore[import-not-found]

    findings = run_all(ROOT, skip_collect=skip_collect)
    if findings:
        r.fail(
            "documentation matches the repository",
            "\n".join(str(f).strip() for f in findings[:10]),
        )
    else:
        r.ok(
            "documentation matches the repository",
            "scripts/check_docs.py found nothing",
        )


def check_credentials(r: Report, settings) -> bool:
    missing = settings.missing_keys()
    if missing:
        r.fail(
            "all credentials present",
            "missing: " + ", ".join(missing)
            + "\ncopy .env.example to .env.local and fill it in",
        )
        return False
    r.ok("all credentials present", "values redacted; see --print-config")
    return True


async def check_rime(r: Report, settings) -> None:
    """Synthesise through the real plugin with the real settings.

    Every check below is made against what the call *did*, not against what
    the configuration says it intends to do. An earlier version reported
    "WebSocket transport in use" by reading ``settings.rime_use_websocket``
    without ever opening a socket, and counted word timestamps with a loop
    over attributes that do not exist on the event. Both passed while
    measuring nothing.
    """
    from waypoint.agent import build_tts

    sentence = (
        "Next stop, twelve forty-seven Goff Street, unit four B. "
        "Gate code four four one seven."
    )
    try:
        tts = build_tts(settings)
    except Exception as exc:
        r.fail("Rime TTS constructs", f"{type(exc).__name__}: {exc}")
        return

    rendered = await synth(tts, sentence)

    if rendered.error:
        r.fail(
            f"Rime synthesises with {settings.rime_model}/{settings.rime_speaker}",
            f"{rendered.error}\n"
            f"transport attempted: {rendered.transport}\n"
            f"endpoint: {settings.endpoint}\n"
            "A 401 means RIME_API_KEY is wrong. A 4xx naming the voice means "
            "the model/speaker pair is not in the live catalog: check "
            "https://docs.rime.ai/api-reference/voices",
        )
        return

    if rendered.frames == 0:
        r.fail(
            "Rime returned audio",
            "the request succeeded but produced no frames; the speaker may not "
            "exist for this model",
        )
        return

    seconds = rendered.duration_s(settings.rime_sample_rate)
    r.ok(
        f"Rime synthesises with {settings.rime_model}/{settings.rime_speaker}",
        f"{rendered.frames} frames, {len(rendered.pcm):,} bytes, about "
        f"{seconds:.1f}s of audio @ {settings.rime_sample_rate} Hz "
        f"(RMS {rendered.rms():.0f}, so it is not silence)",
    )

    if rendered.first_frame_ms is not None:
        label = "first audio frame (cold, includes TLS + connect)"
        if rendered.first_frame_ms > 2000:
            r.warn(label, f"{rendered.first_frame_ms:.0f} ms - slow, but cold")
        else:
            r.ok(label, f"{rendered.first_frame_ms:.0f} ms")

    # Check 5: the transport that was actually used, not the one configured.
    expected = "websocket" if settings.rime_use_websocket else "http"
    if rendered.transport != expected:
        r.fail(
            "shipped transport was the one exercised",
            f"configured for {expected} but the call went over "
            f"{rendered.transport}",
        )
    elif rendered.transport == "websocket":
        r.ok(
            "WebSocket transport exercised end to end",
            f"audio arrived over {settings.endpoint} - this is the shipped "
            "path, and it is what carries word timestamps",
        )
    else:
        r.warn(
            "WebSocket transport exercised end to end",
            "RIME_USE_WEBSOCKET is false, so this run used HTTP. The demo will "
            "work, but heard-not-said degrades to the approximate estimator.",
        )

    # Check 6: word timestamps actually arrived. Sub-claim (c) depends on them.
    if rendered.timings:
        first = rendered.timings[0]
        r.ok(
            "word timestamps arrived",
            f"{len(rendered.timings)} words timed; first is "
            f"{first.word!r} at {first.start_ms:.0f}-{first.end_ms:.0f} ms. "
            "This is what makes the heard/unheard boundary exact.",
        )
    elif settings.rime_use_websocket:
        r.fail(
            "word timestamps arrived",
            "the WebSocket path returned audio but no word timestamps, so "
            "heard-not-said would silently fall back to the estimator. "
            "RIME_EVIDENCE.md sub-claim (c) depends on these.",
        )
    else:
        r.warn(
            "word timestamps arrived",
            "none, as expected on the HTTP path.",
        )


def check_pronunciation(r: Report, settings) -> None:
    from waypoint.pronounce import lexicon_coverage, speak_address

    out = speak_address("1247", "Gough Street", "4B", strategy=settings.pronunciation)
    if "Gough" in out.text:
        r.fail("hard street names are transformed", f"got {out.text!r}")
        return
    r.ok("hard street names are transformed", f"-> {out.text!r}")

    cov = lexicon_coverage()
    if settings.pronunciation.value == "phoneme" and cov["with_verified_phoneme"] == 0:
        r.warn(
            "phoneme lexicon is populated",
            "WAYPOINT_PRONUNCIATION=phoneme but no phonemes are on file, so "
            "every token falls back to its respelling. Either accept that, or "
            "set WAYPOINT_PRONUNCIATION=respell to make the intent explicit.",
        )
    else:
        r.ok(
            "pronunciation lexicon",
            f"{cov['entries']} entries, "
            f"{cov['with_verified_phoneme']} with verified Rime phonemes",
        )


def check_tests(r: Report) -> None:
    import subprocess

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
    except Exception as exc:
        r.warn("offline test suite passes", f"could not run pytest: {exc}")
        return
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    summary = tail[-1] if tail else "(no output)"
    if proc.returncode == 0:
        r.ok("offline test suite passes", summary)
    else:
        r.fail("offline test suite passes", summary)


def check_acceptance(r: Report) -> None:
    import subprocess

    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "evidence" / "run_acceptance.py"), "--json-only"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
    except Exception as exc:
        r.warn("acceptance scenarios pass", f"could not run: {exc}")
        return
    line = next(
        (l for l in (proc.stdout or "").splitlines() if "scenarios passed" in l),
        "(no summary)",
    )
    if proc.returncode == 0:
        r.ok("acceptance scenarios pass", line.strip())
    else:
        r.fail("acceptance scenarios pass", line.strip())


# --------------------------------------------------------------------------


async def main_async(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--offline", action="store_true", help="skip everything needing the network"
    )
    ap.add_argument("--skip-tests", action="store_true", help="skip pytest")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from dotenv import load_dotenv

        for name in (".env.local", ".env"):
            p = ROOT / name
            if p.exists():
                load_dotenv(p, override=False)
    except ImportError:
        pass

    r = Report()
    settings = check_config(r)
    check_secrets(r)
    if settings is None:
        r.render()
        return 1

    check_pronunciation(r, settings)
    # --skip-tests also skips the doc checks that need a pytest collection;
    # the rest (links, placeholders, counts) still run.
    check_docs(r, skip_collect=args.skip_tests)
    if not args.skip_tests:
        check_tests(r)
        check_acceptance(r)

    if args.offline:
        r.warn(
            "Rime shipped path tested",
            "skipped: --offline. Run without it before recording the demo.",
        )
    elif check_credentials(r, settings):
        # Plugins need an HTTP context outside the agent worker.
        async with rime_session():
            await check_rime(r, settings)

    r.render()
    return 1 if r.failed else 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async(sys.argv[1:])))


if __name__ == "__main__":
    main()
