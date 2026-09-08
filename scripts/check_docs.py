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
* ``placeholders`` -- the demo video link reached ``SUBMISSION.md`` but not
  ``README.md``, whose deliverables table still read ``FILL: unlisted YouTube
  link`` -- the first table a judge sees.
* ``mutation_counts`` -- the README said "28 targets" and "13 targets" against
  harnesses that declare 15 and 19.
* ``clone_dir`` -- "Try it in 60 seconds" opened with ``cd waypoint``. The
  repository does not clone as ``waypoint``, so a judge following the README
  literally failed on the first command.
* ``test_count`` -- the suite size is quoted in nine files, and the README's
  module table said "109 tests" for a file that collects 112.
* ``per_file_tests`` -- RIME_EVIDENCE.md's per-file breakdown had drifted to
  summing 425 against a 609-test suite: two files were hundreds out and a third
  was missing entirely. It is the primary evidence document.

The link check used to live inline in ``.github/workflows/ci.yml``, where it
could not be run locally before pushing and could not be tested. It lives here
now, and ``tests/test_check_docs.py`` tests it.

Subset counts must be written as ``N of the M`` rather than a bare ``N tests``.
That is a documentation convention with a purpose: it makes the denominator
checkable on every line that quotes a fraction of the suite, and it leaves a
bare count unambiguously meaning the total.

**Known blind spots**, stated because a gate nobody knows the limits of is
worse than a smaller one:

* Counts spelled out in words are not checked. ``DEMO_SCRIPT.md`` narrates
  "six hundred and twenty tests" out loud, and this file would not notice if
  that drifted -- it was caught by hand once already.
* Anchors are not resolved. ``FILE.md#section`` is verified as far as
  ``FILE.md`` existing; a dead ``#section`` passes.
* External links are never fetched, so a dead URL passes.
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

#: ``[text](target)``. The ``[^)#]`` stops at a fragment so ``FILE.md#anchor``
#: is checked as ``FILE.md``; we verify files exist, not that anchors resolve.
_LINK = re.compile(r"\[[^\]]*\]\(([^)#]+?)\)")

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
_TEST_TOTAL = re.compile(r"\b(\d{3,})\s+(?:tests?|passed|passing)\b")

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
            covered = {p for m in subsets for p in range(m.start(), m.end())}
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
    "placeholders": "no FILL:/REPLACE-ME left in anything a judge reads",
    "mutation_counts": "mutation target counts match the harnesses",
    "clone_dir": "the documented clone directory is the real one",
    "test_count": "the quoted suite size matches what pytest collects",
    "per_file_tests": "a per-file test breakdown matches collection, and is complete",
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
            covered = {
                p
                for m in _TEST_SUBSET.finditer(line)
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

            def subset(m: re.Match[str]) -> str:
                if int(m.group(2)) == total:
                    return m.group(0)
                return f"{m.group(1)} of the {total}"

            line = _TEST_SUBSET.sub(subset, line)

            covered = {
                p
                for m in _TEST_SUBSET.finditer(line)
                for p in range(m.start(), m.end())
            }

            def bare(m: re.Match[str]) -> str:
                if m.start(1) in covered or int(m.group(1)) not in stale_totals:
                    return m.group(0)
                return m.group(0).replace(m.group(1), str(total), 1)

            line = _TEST_TOTAL.sub(bare, line)

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
            ran = len(CHECKS) - (2 if args.skip_collect else 0)
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
