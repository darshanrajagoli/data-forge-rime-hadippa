#!/usr/bin/env python3
"""Refuse to ship documentation that lies.

    python scripts/check_docs.py            # all checks, exit 1 on a finding
    python scripts/check_docs.py --list     # show what is checked, run nothing
    python scripts/check_docs.py --skip-collect   # no pytest subprocess

The brief scores "evidence and reproducibility" at 20% and says judges score
the shipped code and demonstrated behaviour, "not unsupported README claims".
The failure mode that costs those marks is not a missing document, it is a
document that was true last week: a link to a file somebody renamed, a count
that drifted when a test was added, a ``FILL:`` nobody filled.

Every check below exists because that exact defect actually shipped in this
repository and was caught by a human reading carefully rather than by anything
automated:

* ``links`` -- ``team/LISTENING_NOTES.md`` was written from a template one
  directory deeper, kept its ``../../`` prefixes, and broke the docs job. CI
  went red on two commits and nobody noticed, while the README badge and
  SUBMISSION.md both advertised a green build.
* ``anchors`` -- a stated blind spot rather than an oversight: the link check
  truncates at the ``#`` on purpose. A renamed heading silently orphans every
  table-of-contents entry pointing at it, GitHub serves the page anyway and
  drops the reader at the top, and AUDIT-5 downgraded a wording fix to FIX IF
  TIME partly because nothing would catch that mistake.
* ``placeholders`` -- the demo video link reached ``SUBMISSION.md`` but not
  ``README.md``, whose deliverables table still read ``FILL: unlisted YouTube
  link`` -- the first table a judge sees.
* ``mutation_counts`` -- the README said "28 targets" and "13 targets" against
  harnesses that declare 15 and 19.
* ``clone_dir`` -- "Try it in 60 seconds" opened with ``cd waypoint``. The
  repository does not clone as ``waypoint``, so a judge following the README
  literally failed on the first command.
* ``test_count`` -- the suite size is quoted in nine files, and the README's
  module table said "109 tests" for a file that collects 112. It later said
  "628 passes" while five other lines of the same file said 653, because the
  noun alternation held ``passed`` and ``passing`` but not ``passes``.
* ``per_file_tests`` -- RIME_EVIDENCE.md's per-file breakdown had drifted to
  summing 425 against a 609-test suite: two files were hundreds out and a third
  was missing entirely. It is the primary evidence document. The same claim
  made in prose drifted three times in a row -- 36, 80, 93 -- inside the one
  paragraph written to prove this submission is careful with numbers, because
  a two-digit count next to a filename is below every other rule's floor.
* ``spelled_counts`` -- DEMO_SCRIPT.md narrates the suite size out loud, which
  is where a stale number is least visible and most quoted. It drifted twice
  while every digit check was green, so words are parsed now rather than listed
  as a known gap.

``--fix`` rewrites the counts that can be inferred unambiguously, which is what
keeps an audit-and-fix loop from oscillating: adding one test used to mean
thirty hand edits across eleven files, each one a chance to introduce the next
finding.

The link check used to live inline in ``.github/workflows/ci.yml``, where it
could not be run locally before pushing and could not be tested. It lives here
now, and ``tests/test_check_docs.py`` tests it.

Two documentation conventions make otherwise-unenforceable numbers checkable.
Both trade a small constraint on wording for a number that cannot drift:

* Subset counts are written ``N of the M`` rather than a bare ``N tests``, so
  the denominator is checkable on every line quoting a fraction of the suite --
  which leaves a bare count unambiguously meaning the total.
* A per-file count in prose is written ``N in `tests/<file>.py```, so the file
  it refers to is named in the same span and the right value is known exactly.

Both must sit on one line. ``--fix`` rewrites line by line, so a claim wrapped
across two lines is neither checked nor repaired.

A number written outside these shapes is not merely unchecked, it is *reliably*
wrong eventually: every stale count this gate has caught was one no rule could
see.

**Known blind spots**, stated because a gate nobody knows the limits of is
worse than a smaller one:

* A count is only checked in the shapes above. A three-digit number followed by
  some other noun is invisible -- the README shipped "628 passes" against a
  653-test suite for exactly this reason, and the repair was to add the noun
  rather than to match any word after a number. AUDIT-5 DNF 1 measured that
  looser rule at 132 candidate matches in the tracked markdown, most of them
  not counts at all.
* External links are never fetched, so a dead URL passes.
* Anchors are resolved against this repository's headings only. An anchor into
  a file outside it, or into one this module does not read, is skipped rather
  than guessed at.
* The pragma below suppresses every check on the line it covers.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The repository as it exists on GitHub. A clone lands in a directory of this
#: name, so any documented ``cd`` after a ``git clone`` has to agree with it.
REPO_NAME = "data-forge-rime-hadippa"

#: Exempt from the placeholder check, deliberately.
#:
#: ``docs/audits/`` and ``VERIFICATION.md`` are adversarial reports whose whole
#: job is to quote the defects they found; a report that may not name
#: ``REPLACE-ME`` cannot report that ``REPLACE-ME`` shipped. ``team/`` is
#: internal working material where an honest ``TODO`` beats an invented number.
#:
#: They are still link-checked. Being a bug report is not a licence to link to
#: a file that does not exist.
PLACEHOLDER_EXEMPT_PREFIXES = ("docs/audits/", "team/")
PLACEHOLDER_EXEMPT_FILES = ("VERIFICATION.md",)

#: Tokens that mean "somebody meant to come back to this".
PLACEHOLDER_TOKENS = ("FILL:", "REPLACE-ME", "<this repo>", "TKTK", "XXX")

#: Inline escape hatch, mirroring ``secret_scan.py``'s ``secret-scan: allow``.
#:
#: A document sometimes needs to quote a number that is deliberately no longer
#: true. The demo video was recorded when the suite was 573 tests and says so
#: out loud; the honest fix is to explain the discrepancy, not to pretend the
#: narration said something else. Without a pragma the only ways to say that
#: are to exempt the whole file or to delete the sentence, and both are worse.
#:
#: In markdown, write it as an HTML comment on the line above, where it is
#: invisible when rendered:
#:
#:     <!-- check-docs: allow -- the recorded video really does say 573 -->
#:     > "Five hundred and seventy-three tests..."
#:
#: Like the secret scanner's pragma it covers the line it is on and the line
#: after, so it can sit above the text it excuses rather than cluttering it.
#: It suppresses every check on that line, so it should carry a reason.
PRAGMA = re.compile(r"check[-_ ]?docs:\s*(allow|ignore)", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    """One problem, located precisely enough to fix without searching."""

    check: str
    path: str
    line: int
    detail: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"  [{self.check}] {where}\n      {self.detail}"


def _markdown_files(root: Path) -> list[Path]:
    """Every markdown file worth checking, in a stable order.

    ``docs/**`` rather than ``docs/*`` -- the archived audits live in a
    subdirectory and their links need checking too.
    """
    seen = (
        sorted(root.glob("*.md"))
        + sorted(root.glob("docs/**/*.md"))
        + sorted(root.glob("team/**/*.md"))
        + sorted(root.glob("evidence/**/*.md"))
    )
    return [p for p in seen if ".venv" not in p.parts]


def _rel(root: Path, path: Path) -> str:
    """POSIX-style repo-relative path, so findings read the same on Windows."""
    return path.relative_to(root).as_posix()


def _exempt_lines(text: str) -> set[int]:
    """1-indexed line numbers covered by a ``check-docs: allow`` pragma.

    The pragma covers its own line and the next one, so it can sit above the
    sentence it excuses. Deliberately not wider: a marker that covered a whole
    block would let a real defect drift in underneath an old excuse.
    """
    covered: set[int] = set()
    for i, line in enumerate(text.splitlines(), start=1):
        if PRAGMA.search(line):
            covered.add(i)
            covered.add(i + 1)
    return covered


# --------------------------------------------------------------------------
# links
# --------------------------------------------------------------------------

#: ``[text](target)``, with any ``#fragment`` matched but not captured, so
#: ``FILE.md#anchor`` is checked as ``FILE.md``.
#:
#: The fragment group is not decoration. The previous pattern ended
#: ``([^)#]+?)\)`` and was documented as "stops at a fragment" -- it does not.
#: Requiring ``)`` immediately after a run containing no ``#`` means an
#: anchored link simply never matched, so ``[text](docs/GONE.md#anything)``
#: pointing at a file that does not exist was reported by nothing at all.
#: Found by writing a test that asserted the documented behaviour and watching
#: it fail. A pure ``#anchor`` still does not match here, which is correct:
#: ``check_anchors`` owns those.
_LINK = re.compile(r"\[[^\]]*\]\(([^)#]+?)(?:#[^)]*)?\)")

#: Inline and fenced code, stripped before link matching. A link inside a code
#: span is being *displayed*, not offered for the reader to follow.
_FENCE = re.compile(r"^```.*?^```", re.M | re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def _strip_code(text: str) -> str:
    """Blank out code, preserving line count so findings keep their numbers."""

    def blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return _INLINE_CODE.sub(blank, _FENCE.sub(blank, text))


@functools.lru_cache(maxsize=None)
def _tracked(root: Path) -> frozenset[str]:
    """Every path git actually tracks, POSIX-style, or empty outside a repo."""
    proc = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True
    )
    if proc.returncode != 0:
        return frozenset()
    return frozenset(ln.strip() for ln in proc.stdout.splitlines() if ln.strip())


def _is_tracked(root: Path, target: Path, tracked: frozenset[str]) -> bool:
    """True if the target, or anything under it, is committed."""
    try:
        rel = target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:  # outside the repository; existence is all we can check
        return True
    return rel in tracked or any(t.startswith(rel + "/") for t in tracked)


def check_links(root: Path) -> list[Finding]:
    """Every local markdown link points at something a reader will actually have.

    Two conditions, not one. The file has to exist, and it has to be *committed*
    -- because the thing a judge unzips is the repository, not the working tree
    of whoever wrote the link.

    That distinction cost a CI round. ``evidence/results/README.md`` linked to
    ``acceptance.md``, which is deliberately gitignored: ``team/WORKFLOW.md``
    has four people run the acceptance harness, and four runs would collide on
    a file nobody owns. It was sitting in the author's tree because they had run
    the harness, so every local check passed, and the link was dead for
    everyone else. Checking existence alone cannot see that; checking against
    ``git ls-files`` can, and now the local run agrees with CI.
    """
    tracked = _tracked(root)
    findings: list[Finding] = []
    for f in _markdown_files(root):
        raw = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(raw)
        text = _strip_code(raw)
        for i, line in enumerate(text.splitlines(), start=1):
            if i in exempt:
                continue
            for m in _LINK.finditer(line):
                target = m.group(1).strip()
                if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                    continue
                dest = f.parent / target
                if not dest.resolve().exists():
                    findings.append(
                        Finding(
                            "links",
                            _rel(root, f),
                            i,
                            f"link target does not exist: {target}",
                        )
                    )
                elif tracked and not _is_tracked(root, dest, tracked):
                    findings.append(
                        Finding(
                            "links",
                            _rel(root, f),
                            i,
                            f"link target exists here but is not committed, so "
                            f"a fresh clone will not have it: {target}",
                        )
                    )
    return findings


# --------------------------------------------------------------------------
# anchors
# --------------------------------------------------------------------------

#: ``## 10. The adversarial audits`` -- the heading text an anchor is built from.
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)

#: ``[text](#anchor)`` and ``[text](FILE.md#anchor)``.
_ANCHOR_LINK = re.compile(r"\[[^\]]*\]\((?:([^)#]*\.md))?#([^)]+)\)")


def _slug(heading: str) -> str:
    """GitHub's heading-to-anchor rule, as far as this repository needs it.

    Lowercase, drop everything that is not a word character, whitespace or a
    hyphen, then hyphenate the spaces. Emoji, backticks, bold markers and
    trailing punctuation all disappear, which is why ``## 10. The adversarial
    audits`` becomes ``10-the-adversarial-audits``.

    Each space becomes its own hyphen -- runs are *not* collapsed. That is not
    a detail: ``## 9. What is not proven -- read this`` loses the dash, leaves
    two spaces behind, and GitHub renders the anchor with two hyphens. A
    collapsing implementation reports every heading containing a dash as a
    broken link, which is how this function was written the first time.
    """
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s", "-", s.strip())


def _slugs(text: str) -> set[str]:
    """Every anchor a document defines, including GitHub's ``-1`` duplicates."""
    out: set[str] = set()
    for m in _HEADING.finditer(_strip_code(text)):
        base = _slug(m.group(1))
        if not base:
            continue
        if base not in out:
            out.add(base)
            continue
        n = 1
        while f"{base}-{n}" in out:
            n += 1
        out.add(f"{base}-{n}")
    return out


def check_anchors(root: Path) -> list[Finding]:
    """Every ``#section`` link points at a heading that exists.

    This was a documented blind spot rather than an oversight: ``check_links``
    deliberately truncates at the ``#`` and verifies only that the file exists.
    The cost of that showed up in AUDIT-5's finding 6, where renaming a heading
    would have silently killed the table-of-contents entry pointing at it --
    the finding was classified FIX IF TIME partly *because* nothing would catch
    the mistake if the fix were done carelessly.

    A dead anchor fails quietly: GitHub serves the page and drops the reader at
    the top with no error, so it survives exactly the skim a judge gives a
    25 KB document. Closing it costs one traversal of files already in memory.

    Anchors into files this checker does not read are skipped rather than
    guessed at, and so are anchors inside code spans -- documentation that
    *displays* a link is not offering one.
    """
    docs = {_rel(root, f): f.read_text(encoding="utf-8") for f in _markdown_files(root)}
    slugs = {rel: _slugs(text) for rel, text in docs.items()}

    findings: list[Finding] = []
    for rel, raw in docs.items():
        exempt = _exempt_lines(raw)
        for i, line in enumerate(_strip_code(raw).splitlines(), start=1):
            if i in exempt:
                continue
            for m in _ANCHOR_LINK.finditer(line):
                target, anchor = m.group(1), m.group(2).strip()
                if target:
                    dest = (root / rel).parent / target
                    try:
                        key = _rel(root, dest.resolve())
                    except ValueError:
                        continue  # outside the repository; check_links owns it
                    if key not in slugs:
                        continue  # missing file is check_links's finding, not ours
                else:
                    key = rel
                if anchor.lower() not in slugs[key]:
                    where = f"{target}#{anchor}" if target else f"#{anchor}"
                    findings.append(
                        Finding(
                            "anchors",
                            rel,
                            i,
                            f"link to {where} has no matching heading in "
                            f"{key}. Renaming a heading breaks every link to "
                            f"it, and the browser gives no error.",
                        )
                    )
    return findings


# --------------------------------------------------------------------------
# placeholders
# --------------------------------------------------------------------------


def _placeholder_checked(rel: str) -> bool:
    """Fail closed: a document is checked unless it is *explicitly* excused.

    This used to require membership in a ``SHIPPED_DOCS`` allowlist, which is
    the wrong direction for a gate: a judge-facing document added tomorrow
    would not be on the list, so it would ship with its ``FILL:`` blanks intact
    and nothing would say so. The defect this whole file exists to prevent
    would have walked straight back in through a new file.

    Inverting it changes nothing today -- the allowlist happened to name every
    root-level and ``docs/`` markdown file except the exempt ones -- and closes
    that door for every file added later.
    """
    if rel.startswith(PLACEHOLDER_EXEMPT_PREFIXES):
        return False
    if rel in PLACEHOLDER_EXEMPT_FILES:
        return False
    return True


def check_placeholders(root: Path) -> list[Finding]:
    """No unfilled blanks in anything a judge reads."""
    findings: list[Finding] = []
    for f in _markdown_files(root):
        rel = _rel(root, f)
        if not _placeholder_checked(rel):
            continue
        text = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(text)
        for i, line in enumerate(text.splitlines(), start=1):
            if i in exempt:
                continue
            for token in PLACEHOLDER_TOKENS:
                if token in line:
                    findings.append(
                        Finding(
                            "placeholders",
                            rel,
                            i,
                            f"unfilled placeholder {token!r}: {line.strip()[:90]}",
                        )
                    )
    return findings


# --------------------------------------------------------------------------
# mutation_counts
# --------------------------------------------------------------------------


def _load_mutants(path: Path) -> int:
    """Import a mutation harness and count its declared table.

    Importing rather than parsing: the count that matters is the one the
    harness will actually run, and a regex over the source could be fooled by
    a commented-out entry.
    """
    spec = importlib.util.spec_from_file_location(f"_mut_{path.stem}", path)
    if spec is None or spec.loader is None:  # pragma: no cover - unreachable
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return len(module.MUTANTS)


#: ``N targets`` / ``N of N`` claims in prose, e.g. "between them 34 targets".
_TARGETS = re.compile(r"\b(\d+)\s+targets\b")


def check_mutation_counts(root: Path) -> list[Finding]:
    """Counts quoted in the docs match the harnesses' declared tables."""
    core = _load_mutants(root / "evidence" / "mutation_test.py")
    wiring = _load_mutants(root / "evidence" / "mutation_test_ii.py")
    valid = {core, wiring, core + wiring}

    findings: list[Finding] = []
    for f in _markdown_files(root):
        rel = _rel(root, f)
        if rel.startswith(PLACEHOLDER_EXEMPT_PREFIXES) or rel in PLACEHOLDER_EXEMPT_FILES:
            continue
        text = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(text)
        for i, line in enumerate(text.splitlines(), start=1):
            if i in exempt:
                continue
            for m in _TARGETS.finditer(line):
                claimed = int(m.group(1))
                if claimed not in valid:
                    findings.append(
                        Finding(
                            "mutation_counts",
                            rel,
                            i,
                            f"claims {claimed} mutation targets; the harnesses "
                            f"declare {core} + {wiring} = {core + wiring}",
                        )
                    )
    return findings


# --------------------------------------------------------------------------
# clone_dir
# --------------------------------------------------------------------------

#: ``cd X`` at the start of a line or chained after ``&&`` / ``;`` / ``|``.
#: The chained form is the one that shipped -- ``git clone <this repo> && cd
#: waypoint`` -- so anchoring to line starts alone would miss the real defect.
_CD = re.compile(r"(?:^|&&|;)\s*cd\s+([A-Za-z0-9._/-]+)\s*(?=$|&&|;|\n)", re.M)


def check_clone_dir(root: Path) -> list[Finding]:
    """A documented ``cd`` after ``git clone`` names the real clone directory.

    This is the first command a judge runs. Getting it wrong costs a reader
    who was willing to try the repository, which is the most expensive kind of
    reader to lose.
    """
    findings: list[Finding] = []
    for f in _markdown_files(root):
        rel = _rel(root, f)
        if rel.startswith(PLACEHOLDER_EXEMPT_PREFIXES) or rel in PLACEHOLDER_EXEMPT_FILES:
            continue
        raw = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(raw)
        lines = raw.splitlines()
        for i, line in enumerate(lines, start=1):
            if i in exempt or "git clone" not in line:
                continue
            # The cd may be on the same line (`git clone X && cd Y`) or on one
            # of the next few, allowing for a blank line between them.
            window = [line] + lines[i : i + 3]
            for m in _CD.finditer("\n".join(window)):
                target = m.group(1)
                if target != REPO_NAME:
                    findings.append(
                        Finding(
                            "clone_dir",
                            rel,
                            i,
                            f"documents 'cd {target}' after a clone, but the "
                            f"repository clones as '{REPO_NAME}'",
                        )
                    )
    return findings


# --------------------------------------------------------------------------
# test_count
# --------------------------------------------------------------------------

#: A claim about the size of the whole suite: "573 tests", "573 passed".
#:
#: Every inflection of "pass" is listed on purpose. AUDIT-5 finding 3 was a
#: README line reading "628 passes" against a suite of 653. It survived four
#: adversarial passes *and* a gate written to catch exactly that, because this
#: alternation held ``passed`` and ``passing`` but not ``passes``. One letter.
#:
#: Extending the list of *nouns* is cheap and safe -- this one was verified
#: against every tracked markdown file to add no new findings before it was
#: made. Extending it to "any word after a three-digit number" is neither, and
#: AUDIT-5 DNF 1 says why: the tracked markdown holds 132 such numbers and most
#: of them are not suite totals. Add nouns here; do not loosen the shape.
_TEST_TOTAL = re.compile(r"\b(\d{3,})\s+(?:tests?|pass|passes|passed|passing)\b")

#: A claim about part of it: "112 of the 573 tests", "70 of them".
#:
#: Subset counts must be written in this form. That is a documentation rule
#: with a purpose: spelling out the denominator makes the total checkable on
#: every line that quotes a fraction of it, and a bare "109 tests" next to a
#: module name is then unambiguously a total claim -- and a wrong one. That
#: exact sentence shipped in the README's module table, reading 109 against a
#: `test_fencing.py` that collects 112.
_TEST_SUBSET = re.compile(r"\b(\d+)\s+of\s+(?:the\s+)?(\d{3,})\b")


@functools.lru_cache(maxsize=None)
def _collect_output(root: Path) -> str:
    """Raw ``pytest --collect-only -q`` output, once per process.

    Both count checks need it, and the test suite calls them repeatedly.
    The repository cannot change mid-run, so caching is safe and turns four
    subprocess collections into one.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return proc.stdout


# --------------------------------------------------------------------------
# counts spelled out in words
# --------------------------------------------------------------------------
#
# DEMO_SCRIPT.md narrates the suite size out loud, and a narration is where a
# stale number is least visible and most quoted -- it is what the presenter
# says on camera. This drifted silently twice while the digit checks were
# green, so it is checked now rather than listed as a known gap.

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_ONES_R = {v: k for k, v in _UNITS.items()}
_TENS_R = {v: k for k, v in _TENS.items()}

#: A spelled-out count immediately followed by a suite-size noun. The noun is
#: what separates a total from a subset: "a hundred and twelve *of them* are on
#: the fence" is a fraction and is left alone, exactly as in the digit rule.
_WORD_TOTAL = re.compile(
    r"\b((?:a|one|two|three|four|five|six|seven|eight|nine)\s+hundred"
    r"(?:\s+and)?(?:[\s-]+[a-z]+)*?)\s+(?:tests?|passed|passing|passes)\b",
    re.IGNORECASE,
)


def words_to_int(phrase: str) -> int | None:
    """Parse "six hundred and thirty-two". Returns None if it is not a number."""
    total = 0
    current = 0
    saw = False
    for word in re.split(r"[\s-]+", phrase.strip().lower()):
        if word in ("and", ""):
            continue
        if word == "a":
            current, saw = 1, True
        elif word in _UNITS:
            current, saw = current + _UNITS[word], True
        elif word in _TENS:
            current, saw = current + _TENS[word], True
        elif word == "hundred":
            current, saw = max(current, 1) * 100, True
        elif word == "thousand":
            total, current, saw = total + max(current, 1) * 1000, 0, True
        else:
            return None
    return total + current if saw else None


def int_to_words(n: int) -> str:
    """Render 100-9999 the way the narration reads it."""
    if not 100 <= n <= 9999:
        raise ValueError(n)
    parts = []
    if n >= 1000:
        parts.append(f"{_ONES_R[n // 1000]} thousand")
        n %= 1000
    if n >= 100:
        parts.append(f"{_ONES_R[n // 100]} hundred")
        n %= 100
    if n:
        if parts:
            parts.append("and")
        if n < 20:
            parts.append(_ONES_R[n])
        elif n % 10 == 0:
            parts.append(_TENS_R[n])
        else:
            parts.append(f"{_TENS_R[n - n % 10]}-{_ONES_R[n % 10]}")
    return " ".join(parts)


def check_spelled_counts(root: Path, actual: int) -> list[Finding]:
    """A suite size spelled out in words matches the one pytest collects."""
    findings: list[Finding] = []
    for f in _markdown_files(root):
        rel = _rel(root, f)
        if rel.startswith(PLACEHOLDER_EXEMPT_PREFIXES) or rel in PLACEHOLDER_EXEMPT_FILES:
            continue
        text = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(text)
        for i, line in enumerate(text.splitlines(), start=1):
            if i in exempt:
                continue
            for m in _WORD_TOTAL.finditer(line):
                claimed = words_to_int(m.group(1))
                if claimed is not None and claimed != actual:
                    findings.append(
                        Finding(
                            "spelled_counts",
                            rel,
                            i,
                            f'"{m.group(1)}" is {claimed}; pytest collects '
                            f"{actual} ({int_to_words(actual)})",
                        )
                    )
    return findings


def collected_test_count(root: Path) -> int:
    """How many tests pytest actually collects.

    Three output shapes are handled because pytest's ``-q`` collection summary
    depends on version and on whether a plugin overrides the terminal reporter.
    This repository prints one ``path: N`` line per file and no grand total, so
    the per-file sum is the load-bearing branch rather than a fallback.
    """
    out = _collect_output(root)

    m = re.search(r"^(\d+) tests? collected", out, re.M)
    if m:
        return int(m.group(1))

    per_file = re.findall(r"^\S+\.py: (\d+)$", out, re.M)
    if per_file:
        return sum(int(n) for n in per_file)

    return sum(1 for ln in out.splitlines() if "::" in ln)


def check_test_count(root: Path, actual: int) -> list[Finding]:
    """Suite size quoted in the docs matches what pytest collects.

    Both forms are checked against the same ground truth: a bare count is the
    total, and the denominator of an ``N of the M`` is the total too.
    """
    findings: list[Finding] = []
    for f in _markdown_files(root):
        rel = _rel(root, f)
        if rel.startswith(PLACEHOLDER_EXEMPT_PREFIXES) or rel in PLACEHOLDER_EXEMPT_FILES:
            continue
        text = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(text)
        for i, line in enumerate(text.splitlines(), start=1):
            if i in exempt:
                continue
            subsets = list(_TEST_SUBSET.finditer(line))
            for m in subsets:
                part, whole = int(m.group(1)), int(m.group(2))
                if whole != actual:
                    findings.append(
                        Finding(
                            "test_count",
                            rel,
                            i,
                            f"'{m.group(0)}' uses {whole} as the suite total; "
                            f"pytest collects {actual}",
                        )
                    )
                elif part > whole:
                    findings.append(
                        Finding(
                            "test_count",
                            rel,
                            i,
                            f"'{m.group(0)}' claims a subset larger than the suite",
                        )
                    )

            # Spans already accounted for by a subset match are not also total
            # claims -- "112 of the 573 tests" must not read as "573 tests".
            #
            # A prose per-file claim is excluded for the same reason, and it
            # matters as soon as any single test file passes a hundred: "the
            # 102 tests in `tests/test_check_docs.py`" is a per-file count that
            # happens to have three digits, and without this it would be
            # reported as a wrong suite total. `check_per_file_tests` owns that
            # span and validates it against collection for that exact file,
            # which is strictly stronger than the total rule could be.
            covered = {
                p
                for m in (*subsets, *_PROSE_PER_FILE.finditer(line))
                for p in range(m.start(), m.end())
            }
            for m in _TEST_TOTAL.finditer(line):
                if m.start(1) in covered:
                    continue
                claimed = int(m.group(1))
                if claimed != actual:
                    findings.append(
                        Finding(
                            "test_count",
                            rel,
                            i,
                            f"claims {claimed} tests as the suite total; "
                            f"pytest collects {actual}. If this is a subset, "
                            f"write it as 'N of the {actual}'",
                        )
                    )
    return findings


# --------------------------------------------------------------------------
# per_file_tests
# --------------------------------------------------------------------------

#: A row of the per-file breakdown in RIME_EVIDENCE.md:
#:     | `test_fencing.py` | **112** | every fence invariant, ... |
#: The count may be bolded, so the emphasis markers are stripped.
_TABLE_ROW = re.compile(
    r"^\|\s*`(test_[a-z_]+\.py)`\s*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|", re.M
)

#: The same claim made in prose rather than in a table:
#:     ...and the 94 in `tests/test_check_docs.py` were added afterwards
#:
#: This is a documentation *convention*, in the same spirit as ``N of the M``
#: for subsets: a per-file count written in prose must use the form
#: ``N in `tests/<file>.py```, and every occurrence of that form is checked
#: against collection.
#:
#: It exists because one sentence -- the "one discrepancy, flagged rather than
#: hidden" paragraph, whose whole purpose is to prove this submission is
#: scrupulous about numbers -- got this count wrong three times in a row while
#: every gate stayed green. The table rule above could not see it (it is not a
#: table), ``_TEST_TOTAL`` could not see it (a per-file count is two digits,
#: below the three-digit floor that keeps module counts from being read as
#: suite totals), and ``_TEST_SUBSET`` validated only its denominator. A
#: number that no gate reaches drifts on exactly the schedule you would expect.
#:
#: The narrow shape is deliberate. Matching "any number near a filename" would
#: fire on "112 on the fence" and on suite totals quoted beside a path; that
#: was tried and rejected. Requiring the connector to be a bare "in" keeps the
#: rule unambiguous, and ``fix_counts`` repairs it, so adopting it costs a
#: rewording once and nothing thereafter.
_PROSE_PER_FILE = re.compile(r"\b(\d+)\s+(?:tests?\s+)?in\s+`tests/(test_[a-z_]+\.py)`")


def collected_per_file(root: Path) -> dict[str, int]:
    """Tests collected, per test file."""
    out: dict[str, int] = {}
    for m in re.finditer(r"^(\S+\.py): (\d+)$", _collect_output(root), re.M):
        out[Path(m.group(1)).name] = int(m.group(2))
    return out


def check_per_file_tests(root: Path, actual: dict[str, int]) -> list[Finding]:
    """A documented per-file test breakdown matches collection, and is complete.

    RIME_EVIDENCE.md's breakdown drifted to the point of summing to 425 against
    a 573-test suite: two files were hundreds out and a third was missing
    altogether. A table of counts is evidence, and evidence that disagrees with
    the repository is worse than no table -- a judge who checks one row and
    finds it wrong has no reason to trust the next one.
    """
    if not actual:  # collection failed; test_count will report the real problem
        return []

    findings: list[Finding] = []
    for f in _markdown_files(root):
        rel = _rel(root, f)
        if rel.startswith(PLACEHOLDER_EXEMPT_PREFIXES) or rel in PLACEHOLDER_EXEMPT_FILES:
            continue
        text = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(text)

        # Prose claims first: they are independent of whether this file also
        # carries a table, so they must not be skipped by the `not rows` guard.
        for m in _PROSE_PER_FILE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            if line in exempt:
                continue
            claimed, name = int(m.group(1)), m.group(2)
            if name not in actual:
                findings.append(
                    Finding(
                        "per_file_tests",
                        rel,
                        line,
                        f"names {name}, which pytest does not collect",
                    )
                )
            elif claimed != actual[name]:
                findings.append(
                    Finding(
                        "per_file_tests",
                        rel,
                        line,
                        f"says {claimed} in {name}; pytest collects "
                        f"{actual[name]}",
                    )
                )

        rows = [
            m for m in _TABLE_ROW.finditer(text)
            if (text.count("\n", 0, m.start()) + 1) not in exempt
        ]
        if not rows:
            continue

        listed: set[str] = set()
        for m in rows:
            name, claimed = m.group(1), int(m.group(2))
            listed.add(name)
            line = text.count("\n", 0, m.start()) + 1
            if name not in actual:
                findings.append(
                    Finding(
                        "per_file_tests",
                        rel,
                        line,
                        f"lists {name}, which pytest does not collect",
                    )
                )
            elif claimed != actual[name]:
                findings.append(
                    Finding(
                        "per_file_tests",
                        rel,
                        line,
                        f"{name} listed as {claimed}; pytest collects "
                        f"{actual[name]}",
                    )
                )

        # A breakdown that silently omits a file understates the suite. Only
        # enforced on tables that are evidently meant as an inventory, so a doc
        # quoting two rows as an example is not forced to list all thirteen.
        #
        # The threshold was "missing at most one", which left a table missing
        # *two* files unchecked -- and the real defect omitted one file while
        # two other rows were hundreds out, so a second omission was well
        # within reach. Half the suite is the signal that a table is trying to
        # be exhaustive; below that it reads as illustrative.
        if len(listed) * 2 >= len(actual):
            for missing in sorted(set(actual) - listed):
                findings.append(
                    Finding(
                        "per_file_tests",
                        rel,
                        text.count("\n", 0, rows[0].start()) + 1,
                        f"breakdown omits {missing} ({actual[missing]} tests), "
                        f"so it understates the suite",
                    )
                )
    return findings


CHECKS = {
    "links": "every local markdown link points at a file that exists",
    "anchors": "every #section link points at a heading that exists",
    "placeholders": "no FILL:/REPLACE-ME left in anything a judge reads",
    "mutation_counts": "mutation target counts match the harnesses",
    "clone_dir": "the documented clone directory is the real one",
    "test_count": "the quoted suite size matches what pytest collects",
    "per_file_tests": "per-file test counts match collection, in tables and in prose",
    "spelled_counts": "a suite size written out in words matches collection too",
}


# --------------------------------------------------------------------------
# --fix
# --------------------------------------------------------------------------


def fix_counts(root: Path, actual: dict[str, int]) -> list[str]:
    """Rewrite the counts that drifted, and report what changed.

    This exists to make the audit-fix loop converge. Adding one test changes
    the suite total, which is quoted in eleven files plus a per-file table row,
    and ``check_test_count`` enforces every one of them. Done by hand that is a
    thirty-edit cascade per round, which is both tedious and a reliable source
    of new mistakes -- a reviewer who suggests "add a test for X" should not be
    triggering a documentation rewrite that can itself break.

    Only unambiguous rewrites are made:

    * **Per-file table rows** are keyed by filename, so the right number is
      known exactly.
    * **``N of the M``** denominators are the suite total by definition.
    * **Bare totals** are rewritten only where the same value appears in three
      or more files. A stale total is quoted everywhere; a one-off module count
      written bare is local, and rewriting that to the suite total would make
      the checker pass on a document that had become wrong.

    Deliberately *not* rewritten, because the right value cannot be inferred:
    mutation target counts (15, 19 and 34 are all valid, so a wrong one gives
    no clue which was meant) and counts spelled out in words. Both are still
    reported by the checks.

    Lines under a ``check-docs: allow`` pragma are never touched.
    """
    total = sum(actual.values())
    changes: list[str] = []

    # Which bare values look like a stale total rather than a local count.
    seen: dict[int, set[str]] = {}
    for f in _markdown_files(root):
        text = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(text)
        for i, line in enumerate(text.splitlines(), start=1):
            if i in exempt:
                continue
            # Subset spans and prose per-file spans are both owned by other
            # rules; a bare-total rewrite must not reach inside them.
            covered = {
                p
                for m in (
                    *_TEST_SUBSET.finditer(line),
                    *_PROSE_PER_FILE.finditer(line),
                )
                for p in range(m.start(), m.end())
            }
            for m in _TEST_TOTAL.finditer(line):
                if m.start(1) in covered:
                    continue
                seen.setdefault(int(m.group(1)), set()).add(_rel(root, f))
    stale_totals = {v for v, files in seen.items() if len(files) >= 3 and v != total}

    for f in _markdown_files(root):
        rel = _rel(root, f)
        if rel.startswith(PLACEHOLDER_EXEMPT_PREFIXES) or rel in PLACEHOLDER_EXEMPT_FILES:
            continue
        text = f.read_text(encoding="utf-8")
        exempt = _exempt_lines(text)
        out: list[str] = []

        for i, line in enumerate(text.splitlines(), start=1):
            if i in exempt:
                out.append(line)
                continue
            before = line

            def row(m: re.Match[str]) -> str:
                name = m.group(1)
                if name not in actual or int(m.group(2)) == actual[name]:
                    return m.group(0)
                return m.group(0).replace(m.group(2), str(actual[name]), 1)

            line = _TABLE_ROW.sub(row, line)

            def prose_file(m: re.Match[str]) -> str:
                """The prose form of a per-file count, keyed by filename.

                Unambiguous for the same reason the table row is: the file it
                is talking about is named right there, so the correct value is
                known exactly rather than inferred from a threshold.
                """
                name = m.group(2)
                if name not in actual or int(m.group(1)) == actual[name]:
                    return m.group(0)
                return m.group(0).replace(m.group(1), str(actual[name]), 1)

            line = _PROSE_PER_FILE.sub(prose_file, line)

            def subset(m: re.Match[str]) -> str:
                if int(m.group(2)) == total:
                    return m.group(0)
                return f"{m.group(1)} of the {total}"

            line = _TEST_SUBSET.sub(subset, line)

            # Subset spans and prose per-file spans are both owned by other
            # rules; a bare-total rewrite must not reach inside them.
            covered = {
                p
                for m in (
                    *_TEST_SUBSET.finditer(line),
                    *_PROSE_PER_FILE.finditer(line),
                )
                for p in range(m.start(), m.end())
            }

            def bare(m: re.Match[str]) -> str:
                if m.start(1) in covered or int(m.group(1)) not in stale_totals:
                    return m.group(0)
                return m.group(0).replace(m.group(1), str(total), 1)

            line = _TEST_TOTAL.sub(bare, line)

            def spelled(m: re.Match[str]) -> str:
                claimed = words_to_int(m.group(1))
                if claimed is None or claimed == total:
                    return m.group(0)
                words = int_to_words(total)
                if m.group(1)[:1].isupper():
                    words = words[:1].upper() + words[1:]
                return m.group(0).replace(m.group(1), words, 1)

            line = _WORD_TOTAL.sub(spelled, line)

            if line != before:
                changes.append(f"{rel}:{i}\n    - {before.strip()}\n    + {line.strip()}")
            out.append(line)

        new = "\n".join(out) + ("\n" if text.endswith("\n") else "")
        if new != text:
            f.write_text(new, encoding="utf-8")

    return changes


def run_all(root: Path, skip_collect: bool = False) -> list[Finding]:
    findings = (
        check_links(root)
        + check_anchors(root)
        + check_placeholders(root)
        + check_mutation_counts(root)
        + check_clone_dir(root)
    )
    if not skip_collect:
        # One collection run feeds both count checks.
        per_file = collected_per_file(root)
        total = sum(per_file.values()) or collected_test_count(root)
        findings += check_test_count(root, total)
        findings += check_per_file_tests(root, per_file)
        findings += check_spelled_counts(root, total)
    return findings


def main() -> int:
    # Findings quote the documents they came from, and those contain em dashes
    # and arrows. A Windows console defaults to cp1252, where printing one
    # raises UnicodeEncodeError -- so the checker would crash while reporting a
    # problem instead of reporting it. Degrade the character, never the report.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover - old/odd streams
            pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show checks, run none")
    ap.add_argument(
        "--skip-collect",
        action="store_true",
        help="skip the pytest subprocess (faster; drops the test_count check)",
    )
    ap.add_argument(
        "--fix",
        action="store_true",
        help="rewrite drifted counts, then check. Use after adding a test.",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.list:
        for name, why in CHECKS.items():
            print(f"  {name:16} {why}")
        return 0

    if args.fix:
        if args.skip_collect:
            print("--fix needs a collection; drop --skip-collect.", file=sys.stderr)
            return 2
        changes = fix_counts(ROOT, collected_per_file(ROOT))
        if changes:
            print(f"check_docs --fix: rewrote {len(changes)} line(s).")
            for c in changes:
                print("  " + c)
        else:
            print("check_docs --fix: nothing to rewrite.")
        print()

    findings = run_all(ROOT, skip_collect=args.skip_collect)

    if not findings:
        if not args.quiet:
            ran = len(CHECKS) - (3 if args.skip_collect else 0)
            print(f"check_docs: clean. {ran} checks passed.")
        return 0

    print("check_docs: PROBLEMS FOUND", file=sys.stderr)
    for f in findings:
        print(str(f), file=sys.stderr)
    print(
        f"\n  {len(findings)} finding(s). Documentation that contradicts the "
        "repository\n  costs more than documentation that says less -- fix the "
        "document or fix\n  the claim.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
