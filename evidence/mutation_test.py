#!/usr/bin/env python3
"""Do the tests actually mean anything? Break the code and find out.

    python evidence/mutation_test.py            # run the whole set (~3 min)
    python evidence/mutation_test.py --list     # show the mutations, run none
    python evidence/mutation_test.py --repair   # undo an interrupted run

No credentials, no network, no audio device.

Why this exists
---------------
"425 tests pass" is not evidence. A suite that stays green when you break the
thing it is supposed to be guarding is worse than no suite, because it converts
absence of signal into false confidence. The only way to know a test asserts
something is to make the assertion false and watch it fail.

So this script does exactly that: it edits the source to introduce one
specific, plausible bug, runs the whole suite, records whether anything
noticed, and puts the file back. A mutant that **survives** is a hole in the
tests, and the script exits non-zero so it cannot be quietly ignored.

Every mutation below is a bug someone could really write. Six of them *were*
really written during this project's development -- those are marked
``REAL BUG``, because a regression test that has never seen its regression is
a guess. Two of the six were found only by an adversarial review pass after the
project was first declared finished, including one where a headline claim had
never been wired into the agent at all while its module tests stayed green.

Reading the output
------------------
``caught``      a test failed. Good: that behaviour is genuinely guarded.
``SURVIVED``    the suite passed with broken code. That is a finding.

Safety
------
This script rewrites source files in place, so it is careful about it:

* **It takes an exclusive lock.** Two copies running at once clobber each
  other's restores and leave the tree mutated. That is not hypothetical -- it
  happened during development, and repairing it by hand is why ``--repair``
  exists.
* **It refuses to start on an already-mutated tree**, so a corrupted checkout
  is reported rather than measured.
* It restores each file in a ``finally`` block and re-checks every site before
  exiting.
* ``--repair`` reverts whatever an interrupted run left behind, using the same
  table, so recovery does not depend on git.
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
LOCK = ROOT / "evidence" / ".mutation_test.lock"

#: (name, file, original, mutated, note)
#:
#: ``note`` says why the mutation is interesting. ``REAL BUG`` marks one that
#: was actually written during development, so its regression test is verified
#: against the thing it exists to catch rather than assumed to work.
MUTANTS: list[tuple[str, str, str, str, str]] = [
    (
        "stale results become speakable",
        "src/waypoint/fencing.py",
        "_ADMITTING = frozenset({Disposition.DELIVERED, Disposition.REANCHORED})",
        "_ADMITTING = frozenset({Disposition.DELIVERED, Disposition.REANCHORED,"
        " Disposition.FENCED_STALE})",
        "the headline claim, inverted",
    ),
    (
        "turn-origin retirement is ignored",
        "src/waypoint/fencing.py",
        '        if ticket.origin and ticket.origin in self._retired:\n'
        '            return f"origin {ticket.origin!r} retired (turn interrupted)"',
        '        if False:\n            return "unreachable"',
        "REAL BUG - a dead turn could issue fresh-looking work",
    ),
    (
        "irreversible writes become re-anchorable",
        "src/waypoint/fencing.py",
        "            if ticket.policy is ReanchorPolicy.NEVER:",
        "            if ticket.policy is ReanchorPolicy.DISCARD:",
        "an SMS could be sent twice",
    ),
    (
        "re-anchor target need not be re-anchorable",
        "src/waypoint/fencing.py",
        "                and cand.policy is ReanchorPolicy.REANCHOR_IF_ARGS_MATCH",
        "                and True",
        "REAL BUG - found by red-team review",
    ),
    (
        "the generation never advances",
        "src/waypoint/fencing.py",
        "            self._generation += 1",
        "            self._generation += 0",
        "the fence silently stops fencing",
    ),
    (
        "admit becomes at-least-once",
        "src/waypoint/fencing.py",
        '            if ticket.ticket_id in self._resolved:\n'
        '                raise FenceError(\n'
        '                    f"ticket {ticket.describe()} already resolved; "\n'
        '                    "admit() is at-most-once"\n'
        '                )',
        "            if False:\n                pass",
        "the same answer could be spoken twice",
    ),
    (
        "the effect-boundary check is skipped",
        "src/waypoint/agent.py",
        "        if not pre.commit:",
        "        if False:",
        "writes commit after supersession",
    ),
    (
        "the ticket is issued after syncing",
        "src/waypoint/agent.py",
        "        ticket = fence.issue(name, args, ReanchorPolicy.NEVER,"
        " origin=_origin(ctx))\n        self._sync(ctx)",
        "        self._sync(ctx)\n        ticket = fence.issue(name, args,"
        " ReanchorPolicy.NEVER)",
        "REAL BUG - laundered a dead turn into a fresh one",
    ),
    (
        "a superseded error is spoken anyway",
        "src/waypoint/agent.py",
        '            return SUPERSEDED_MARKER if superseded else f"That did not'
        ' work. {exc}"\n        except Exception:\n            fence.cancel(ticket,'
        ' "tool raised")\n            raise\n\n        self._sync(ctx)\n'
        "        decision = fence.admit(ticket)",
        '            return f"That did not work. {exc}"\n        except Exception:\n'
        '            fence.cancel(ticket, "tool raised")\n            raise\n\n'
        "        self._sync(ctx)\n        decision = fence.admit(ticket)",
        "REAL BUG - the error path bypassed the fence entirely",
    ),
    (
        "the utterance is registered with empty text",
        "src/waypoint/agent.py",
        "            self.deps.heard.begin(utt_id, full_text)",
        '            self.deps.heard.begin(utt_id, "")',
        "REAL BUG - heard-not-said silently returned nothing",
    ),
    (
        "reconciliation never runs",
        "src/waypoint/agent.py",
        "        utt_id = handle.id\n        t0 = self._utt_started.pop(utt_id, None)",
        "        return\n        utt_id = handle.id\n"
        "        t0 = self._utt_started.pop(utt_id, None)",
        "REAL BUG - sub-claim (c) was never wired in",
    ),
    (
        "a half-spoken word counts as heard",
        "src/waypoint/heard.py",
        "heard_words = [m.word for m in utt.marks if m.end_ms <= at_ms]",
        "heard_words = [m.word for m in utt.marks if m.start_ms <= at_ms]",
        "over-claims in the dangerous direction",
    ),
    (
        "gate codes are read as quantities",
        "src/waypoint/pronounce.py",
        "    parts = [_ONES[int(c)] if c.isdigit() else c.upper()"
        " for c in str(code).strip()]",
        "    parts = [str(code).strip()]",
        "the driver cannot key in the code",
    ),
    (
        "phoneme-on-coda no-ops instead of raising",
        "src/waypoint/pronounce.py",
        "    if strict:\n        raise PronunciationError(msg)",
        "    if False:\n        raise PronunciationError(msg)",
        "the exact silent failure the layer exists to prevent",
    ),
    (
        "cold and warm runs share a series",
        "src/waypoint/metrics.py",
        "            key = (s.name, s.boundary, s.warmth)",
        "            key = (s.name, s.boundary, Warmth.WARM)",
        "a cold outlier pollutes every published p95",
    ),
]



# --------------------------------------------------------------------------
# File I/O
#
# Read and write with ``newline=""`` so no newline translation happens. With
# ``Path.read_text`` / ``Path.write_text`` the round trip is only guaranteed at
# the *text* level, not at the byte level -- and this script verifies its own
# restores with a SHA-256 over the bytes. A single run during development
# reported "SOURCE NOT RESTORED" for two files whose mutated text was in fact
# absent, i.e. the content was fine and only the digest disagreed. The
# mechanism was never identified, which is precisely why the I/O is now exact
# rather than merely equivalent: a false "your checkout is corrupted" twenty
# minutes before a deadline is expensive, and until this repository had git
# history there was nothing to recover from.
#
# ``localise`` translates the table's newlines to whatever the file actually
# uses, so a CRLF checkout matches the same way a LF one does.
# --------------------------------------------------------------------------


def read_source(path: pathlib.Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_source(path: pathlib.Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


#: Built from ordinals rather than escapes so that no editor, heredoc or
#: newline-translating tool in the chain can quietly rewrite them -- which
#: is the exact class of problem these helpers exist to defend against.
LF = chr(10)
CRLF = chr(13) + chr(10)


def newline_of(text: str) -> str:
    """The line ending this file actually uses."""
    return CRLF if CRLF in text else LF


def localise(snippet: str, text: str) -> str:
    """Match the table's LF snippets against a file that may be CRLF.

    The MUTANTS table is written with LF. A checkout on Windows may be
    CRLF, in which case a multi-line snippet would not be found and every
    such mutation would silently report SKIP -- looking like coverage
    while measuring nothing.
    """
    return snippet.replace(LF, newline_of(text))

# --------------------------------------------------------------------------
# Tree integrity
# --------------------------------------------------------------------------


def integrity() -> list[tuple[str, str]]:
    """Sites whose ORIGINAL code is missing. An empty list means clean."""
    out: list[tuple[str, str]] = []
    for name, rel, old, _new, _note in MUTANTS:
        text = read_source(ROOT / rel)
        if localise(old, text) not in text:
            out.append((rel, name))
    return out


def repair() -> int:
    """Revert whatever a killed run left behind. Recovery without git."""
    fixed = 0
    for name, rel, old, new, _note in MUTANTS:
        path = ROOT / rel
        text = read_source(path)
        old_l, new_l = localise(old, text), localise(new, text)
        if new_l in text and old_l not in text:
            write_source(path, text.replace(new_l, old_l, 1))
            print(f"  reverted  {rel}: {name}")
            fixed += 1
    remaining = integrity()
    if remaining:
        print("  STILL BROKEN - these sites hold neither version:", file=sys.stderr)
        for rel, name in remaining:
            print(f"    {rel}: {name}", file=sys.stderr)
        return 2
    print(f"  {fixed} site(s) reverted; all {len(MUTANTS)} sites are original.")
    return 0


def run_suite(timeout: int = 400) -> tuple[bool, list[str]]:
    """Run the suite. Returns (something failed, failing test ids)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout,
    )
    failures = [
        line.split(" - ")[0].strip()
        for line in proc.stdout.splitlines()
        if line.startswith("FAILED")
    ]
    return proc.returncode != 0, failures


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------


def _run() -> int:
    fingerprints = {
        rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        for rel in {m[1] for m in MUTANTS}
    }

    print()
    print("=" * 78)
    print(" Mutation test - deliberately breaking the code to see what notices")
    print("=" * 78)
    print("  A SURVIVED mutant is a hole in the test suite, not a pass.")
    print()

    survived: list[str] = []
    skipped: list[str] = []
    started = time.perf_counter()

    for i, (name, rel, old, new, note) in enumerate(MUTANTS, 1):
        path = ROOT / rel
        original = read_source(path)
        old_l, new_l = localise(old, original), localise(new, original)
        if old_l not in original:
            skipped.append(name)
            print(f"  {i:2d}. {name:47s} SKIP  (source moved on)")
            continue

        write_source(path, original.replace(old_l, new_l, 1))
        try:
            caught, failures = run_suite()
        finally:
            write_source(path, original)

        # Verify this restore now, not at the end of the run. A bad restore
        # should stop the run rather than surface fifteen minutes later with
        # the tree already mutated for a different reason.
        if read_source(path) != original:
            print(f"  !! restore of {rel} did not round-trip; stopping",
                  file=sys.stderr)
            return 2

        if caught:
            first = failures[0].replace("tests/", "") if failures else ""
            print(f"  {i:2d}. {name:47s} caught  {first[:36]}")
        else:
            survived.append(name)
            print(f"  {i:2d}. {name:47s} *** SURVIVED ***")
        if "REAL BUG" in note:
            print(f"      {note}")

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
        print(
            "     recover with: python evidence/mutation_test.py --repair",
            file=sys.stderr,
        )
        return 2
    if survived:
        print("  !! Holes in the test suite:", file=sys.stderr)
        for name in survived:
            print(f"       - {name}", file=sys.stderr)
        return 1
    print("  Every deliberate bug was caught by a test. The suite is load-bearing.")
    print("-" * 78)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list", action="store_true", help="show the mutations and run none"
    )
    parser.add_argument(
        "--repair", action="store_true",
        help="revert mutations left behind by an interrupted run, then stop",
    )
    args = parser.parse_args()

    if args.list:
        for i, (name, rel, _old, _new, note) in enumerate(MUTANTS, 1):
            print(f"{i:2d}. {name}  [{rel}]  -- {note}")
        return 0

    if args.repair:
        print()
        print("  Repairing mutation sites...")
        return repair()

    # Refuse to measure a tree that is already broken: the numbers would
    # describe the wrong code, and the restore would write back the wrong text.
    already = integrity()
    if already:
        print(file=sys.stderr)
        print(
            "  Source is already mutated at these sites, so this run would",
            file=sys.stderr,
        )
        print(
            "  measure the wrong code and restore the wrong text:", file=sys.stderr
        )
        for rel, name in already:
            print(f"    {rel}: {name}", file=sys.stderr)
        print(file=sys.stderr)
        print(
            "  Fix it with:  python evidence/mutation_test.py --repair",
            file=sys.stderr,
        )
        return 2

    # One run at a time. Concurrent runs clobber each other's restores.
    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        print(file=sys.stderr)
        print(f"  Another mutation run holds {LOCK.name}.", file=sys.stderr)
        print(
            "  Wait for it to finish. If you are certain nothing is running:",
            file=sys.stderr,
        )
        print(f"      rm {LOCK}", file=sys.stderr)
        print(
            "      python evidence/mutation_test.py --repair", file=sys.stderr
        )
        return 2

    try:
        return _run()
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
