#!/usr/bin/env python3
"""Second-order mutation test: does the suite guard the *wiring*, not just the core?

    python evidence/mutation_test_ii.py            # run the whole set
    python evidence/mutation_test_ii.py --list     # show the mutations, run none
    python evidence/mutation_test_ii.py --repair   # undo an interrupted run

No credentials, no network, no audio device.

Why this exists
---------------
``evidence/mutation_test.py`` reports 15/15 caught, and that number is real.
But every one of its fifteen mutations lands in code that a unit test calls
directly: ``TurnFence``, ``HeardTracker``, ``WaypointAgent._read`` /
``._write``, ``pronounce``, ``MetricsLog``. It measures the suite's
sensitivity exactly where the suite already points.

It never touches the layer that turns :class:`Settings` into a live
LiveKit + Rime session -- ``build_tts``, ``build_session``,
``attach_observers``, ``entrypoint`` -- roughly 220 lines of
``src/waypoint/agent.py``. ``tests/test_agent.py`` imports ``Deps`` and
``WaypointAgent`` and nothing else, so no test constructs any of it. It also
never touches the values that must match an external system (the Rime model,
speaker, language and sample rate), the system prompt, or the two scripts
whose failure maps onto a stated disqualifier in the brief.

That is a blind *region*, not a missing row: the mutations below are not
variations on the existing table, they are the categories the table has no
entry for. A mutant that SURVIVES here is a bug that could ship green.

Categories
----------
``A`` external contract -- a value that is only wrong relative to Rime's catalog.
``B`` wiring            -- the untested Settings-to-session layer.
``C`` prompt            -- the text that actually drives spoken behaviour.
``D`` gates             -- the scripts that stand in for the brief's disqualifiers.

Safety
------
Identical discipline to ``mutation_test.py``, and it takes *the same lock*, so
the two can never run concurrently and clobber each other's restores:

* refuses to start on an already-mutated tree,
* restores each file in a ``finally`` block,
* re-hashes every touched file before exiting,
* ``--repair`` reverts whatever an interrupted run left behind.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
#: Deliberately the same lock file mutation_test.py uses.
LOCK = ROOT / "evidence" / ".mutation_test.lock"

#: (name, category, file, original, mutated, note)
MUTANTS: list[tuple[str, str, str, str, str, str]] = [
    # -- A: values that are only wrong against the outside world -----------
    (
        "coda runs with a Mist-family voice",
        "A",
        "src/waypoint/config.py",
        '    default_speaker = "lyra" if model == "coda" else "cove"',
        '    default_speaker = "cove"',
        "'cove' is a real Rime voice, but a Mist one. The brief disqualifies "
        "a model/voice/language combination that fails the event preflight.",
    ),
    (
        "language code is not a Rime language code",
        "A",
        "src/waypoint/config.py",
        '    lang = _env("RIME_LANG", "eng") or "eng"',
        '    lang = _env("RIME_LANG", "en") or "en"',
        "Rime takes 'eng', not the ISO-639-1 'en'. Plausible to write, and "
        "only detectable against the live catalog.",
    ),
    (
        "audio is synthesised at telephony rate",
        "A",
        "src/waypoint/config.py",
        '        rime_sample_rate=_env_int("RIME_SAMPLE_RATE", 22050),',
        '        rime_sample_rate=_env_int("RIME_SAMPLE_RATE", 8000),',
        "README and banner both state PCM @ 22050 Hz. This ships 8 kHz.",
    ),
    (
        "build_tts hardcodes a different model than it discloses",
        "A",
        "src/waypoint/agent.py",
        '        "model": settings.rime_model,',
        '        "model": "mistv3",',
        "build_tts' own docstring claims the shipped and disclosed configs "
        "'cannot drift apart'. This drifts them: banner says coda, Rime "
        "receives mistv3.",
    ),
    # -- B: the untested wiring layer --------------------------------------
    (
        "the shipped transport silently becomes HTTP",
        "B",
        "src/waypoint/agent.py",
        '        "use_websocket": settings.rime_use_websocket,',
        '        "use_websocket": False,',
        "Kills streaming, kills aligned transcripts, kills word timestamps, "
        "and changes the endpoint -- while the banner still prints "
        "'WebSocket (wss)' and 'word_timestamps (exact)'.",
    ),
    (
        "word timestamps never reach the agent",
        "B",
        "src/waypoint/agent.py",
        "        use_tts_aligned_transcript=settings.rime_use_websocket,",
        "        use_tts_aligned_transcript=False,",
        "transcription_node stops receiving TimedString deltas, so "
        "heard-not-said degrades to the estimator with no disclosure.",
    ),
    (
        "barge-in is switched off entirely",
        "B",
        "src/waypoint/agent.py",
        '                "enabled": True,',
        '                "enabled": False,',
        "The product is an interruption-recovery agent. This disables "
        "interruption. Nothing else in the repository changes.",
    ),
    (
        "barge-in needs ten seconds of speech",
        "B",
        "src/waypoint/agent.py",
        '                "min_duration": settings.min_interruption_duration,',
        '                "min_duration": 10.0,',
        "Interruption stays 'enabled' but can never fire in a real turn. "
        "The banner still prints min_duration=0.4s.",
    ),
    (
        "markdown and emoji are spoken aloud",
        "C",
        "src/waypoint/agent.py",
        '        tts_text_transforms=["filter_emoji", "filter_markdown"],',
        "        tts_text_transforms=[],",
        "The prompt asks the model for no markdown; this removes the "
        "mechanism that holds when the model ignores it.",
    ),
    # -- C: the text that drives spoken behaviour --------------------------
    (
        "the written-for-the-ear rules are gone",
        "C",
        "src/waypoint/prompts.py",
        '- Answer first, detail second. Lead with the number or the name they asked for.\n'
        '- One or two sentences. If you need a third, you are explaining too much.\n'
        '- Never read a list. Two items joined by "and" is the limit. If there are more,\n'
        '  say how many there are and offer the first one.\n',
        "- Say as much as you like, in whatever order reads best.\n",
        "Front-loading, no-lists and say-the-number-once are the whole "
        "voice-experience story. Deleting them changes every spoken turn.",
    ),
    # -- D: the scripts that stand in for the brief's disqualifiers --------
    (
        "preflight passes with zero audio frames",
        "D",
        "scripts/preflight.py",
        "    if rendered.frames == 0:",
        "    if False:",
        "preflight is what certifies the shipped path before recording. "
        "This makes its central check unconditional.",
    ),
    (
        "preflight reports the wrong transport as correct",
        "D",
        "scripts/preflight.py",
        "    if rendered.transport != expected:",
        "    if False:",
        "preflight check 5 exists to prove the SHIPPED transport was the "
        "one exercised. This makes it unconditional, so an HTTP fallback "
        "would be certified as the WebSocket path.",
    ),
    (
        "the secret scanner always reports clean",
        "D",
        "scripts/secret_scan.py",
        "def scan(root: Path = ROOT) -> list[Finding]:\n    findings: list[Finding] = []",
        "def scan(root: Path = ROOT) -> list[Finding]:\n    return []\n    findings: list[Finding] = []",
        "Exposing a live credential is a stated disqualifier. Included as a "
        "control: this one SHOULD be caught, because tests/test_secret_scan.py "
        "exists. If it is, the contrast is the finding.",
    ),
]


# --------------------------------------------------------------------------
# Mechanics (deliberately the same shape as mutation_test.py)
# --------------------------------------------------------------------------


def run_suite(timeout: int = 600) -> tuple[bool, list[str]]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout,
    )
    failures = [
        line.split(" - ")[0].strip()
        for line in proc.stdout.splitlines()
        if line.startswith("FAILED")
    ]
    return proc.returncode != 0, failures


def read_source(path: pathlib.Path) -> str:
    """Read as text without newline translation.

    ``Path.read_text`` applies universal newlines and ``Path.write_text``
    translates back on write. On a CRLF checkout that round-trips exactly, but
    it makes the byte-level integrity check below depend on a translation
    rather than on the bytes. Reading and writing with ``newline=""`` takes
    translation out of the loop entirely, so a restore is byte-exact by
    construction and a dirty report is always a real one.
    """
    with path.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_source(path: pathlib.Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def newline_of(text: str) -> str:
    """The line ending the file actually uses, so edits keep it."""
    return "\r\n" if "\r\n" in text else "\n"


def localise(snippet: str, text: str) -> str:
    """Rewrite a table snippet's ``\\n`` into the file's own line ending."""
    return snippet.replace("\n", newline_of(text))


def integrity() -> list[tuple[str, str]]:
    """Sites whose *mutated* text is present in the tree right now."""
    found = []
    for name, _cat, rel, _old, new, _note in MUTANTS:
        try:
            text = read_source(ROOT / rel)
        except OSError:
            continue
        if localise(new, text) in text:
            found.append((rel, name))
    return found


def repair() -> int:
    fixed = []
    for name, _cat, rel, old, new, _note in MUTANTS:
        path = ROOT / rel
        try:
            text = read_source(path)
        except OSError:
            continue
        old_l, new_l = localise(old, text), localise(new, text)
        if new_l in text and old_l not in text:
            write_source(path, text.replace(new_l, old_l, 1))
            fixed.append(f"{rel}: {name}")
    if fixed:
        for f in fixed:
            print(f"    reverted {f}")
        print(f"  {len(fixed)} site(s) restored.")
    else:
        print("  Nothing to repair; the tree is clean.")
    return 0


CATEGORY_NAMES = {
    "A": "external contract (only wrong against Rime's catalog)",
    "B": "wiring (the untested Settings-to-session layer)",
    "C": "prompt / delivery (what is actually spoken)",
    "D": "gates (the brief's disqualifiers)",
}


def _run() -> int:
    fingerprints = {
        rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        for rel in {m[2] for m in MUTANTS}
    }

    print()
    print("=" * 78)
    print(" Mutation test II - is the *wiring* guarded, or only the core?")
    print("=" * 78)
    print("  A SURVIVED mutant here is a bug that could ship with a green suite.")
    print()

    survived: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    started = time.perf_counter()
    current_cat = ""

    for i, (name, cat, rel, old, new, note) in enumerate(MUTANTS, 1):
        if cat != current_cat:
            current_cat = cat
            print(f"  -- {cat}: {CATEGORY_NAMES[cat]}")
        path = ROOT / rel
        original = read_source(path)
        old_l, new_l = localise(old, original), localise(new, original)
        if old_l not in original:
            skipped.append(name)
            print(f"  {i:2d}. {name:47s} SKIP  (source moved on)")
            continue
        if original.count(old_l) > 1:
            skipped.append(name)
            print(f"  {i:2d}. {name:47s} SKIP  (target not unique)")
            continue

        write_source(path, original.replace(old_l, new_l, 1))
        try:
            caught, failures = run_suite()
        finally:
            write_source(path, original)
            # Verify the restore before moving on, rather than discovering a
            # bad restore fifteen minutes later at the end of the run.
            if read_source(path) != original:
                write_source(path, original)
                if read_source(path) != original:
                    print(f"  !! could not restore {rel}; stopping", file=sys.stderr)
                    raise SystemExit(2)

        if caught:
            first = failures[0].replace("tests/", "") if failures else ""
            print(f"  {i:2d}. {name:47s} caught  {first[:34]}")
        else:
            survived.append((name, rel, note))
            print(f"  {i:2d}. {name:47s} *** SURVIVED ***")

    dirty = [
        rel for rel, digest in fingerprints.items()
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest
    ]

    tested = len(MUTANTS) - len(skipped)
    elapsed = time.perf_counter() - started
    print()
    print("-" * 78)
    summary = f"  {tested - len(survived)}/{tested} mutants caught"
    if skipped:
        summary += f", {len(skipped)} skipped"
    print(f"{summary}   ({elapsed:.0f}s)")

    if dirty:
        print(f"  !! SOURCE NOT RESTORED: {dirty}", file=sys.stderr)
        print("     recover with: python evidence/mutation_test_ii.py --repair",
              file=sys.stderr)
        return 2

    if survived:
        print()
        print("  Mutants that shipped green -- each is a real hole:")
        for name, rel, note in survived:
            print(f"    - {name}  [{rel}]")
            for line in note.split(". "):
                if line.strip():
                    print(f"        {line.strip().rstrip('.')}.")
        print()
        print(f"  {len(survived)} of {tested} deliberate bugs were invisible to "
              "the test suite.")
        print("-" * 78)
        return 1

    print("  Every mutant was caught. The wiring is guarded too.")
    print("-" * 78)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true",
                        help="show the mutations and run none")
    parser.add_argument("--repair", action="store_true",
                        help="revert mutations left behind by an interrupted run")
    args = parser.parse_args()

    if args.list:
        cat = ""
        for i, (name, c, rel, _old, _new, note) in enumerate(MUTANTS, 1):
            if c != cat:
                cat = c
                print(f"\n-- {c}: {CATEGORY_NAMES[c]}")
            print(f"{i:2d}. {name}  [{rel}]")
            print(f"    {note}")
        return 0

    if args.repair:
        print()
        print("  Repairing mutation sites...")
        return repair()

    already = integrity()
    if already:
        print(file=sys.stderr)
        print("  Source is already mutated at these sites, so this run would",
              file=sys.stderr)
        print("  measure the wrong code and restore the wrong text:", file=sys.stderr)
        for rel, name in already:
            print(f"    {rel}: {name}", file=sys.stderr)
        print(file=sys.stderr)
        print("  Fix it with:  python evidence/mutation_test_ii.py --repair",
              file=sys.stderr)
        return 2

    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        print(file=sys.stderr)
        print(f"  Another mutation run holds {LOCK.name}.", file=sys.stderr)
        print("  Wait for it to finish. If you are certain nothing is running:",
              file=sys.stderr)
        print(f"      rm {LOCK}", file=sys.stderr)
        print("      python evidence/mutation_test_ii.py --repair", file=sys.stderr)
        return 2

    try:
        return _run()
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
