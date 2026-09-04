#!/usr/bin/env python3
"""Refuse to ship a secret.

    python scripts/secret_scan.py          # scan the repo, exit 1 on a finding
    python scripts/secret_scan.py --staged # scan only what git has staged

"Exposes a live credential or other secret" is a listed disqualifier in the
Rime brief, and it is the one failure mode that cannot be fixed after
submission -- once a key is in a public commit it is burned even if the next
commit removes it.

So this runs three ways: from ``scripts/preflight.py``, from the ``pre-commit``
hook installed by ``scripts/install_hooks.sh``, and on its own.

The rules below are deliberately narrow. A scanner that cries wolf gets
disabled by the third person who hits a false positive on the day of the
deadline, so placeholders, obvious examples and the ``.env.example`` template
are all allowed through by design.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Directories never worth scanning.
#: Directories never worth scanning. Build output and virtualenvs only.
#:
#: ``results`` used to be here, which meant ``evidence/results/**`` -- a
#: directory of *committed* artifacts, and where the agent writes its session
#: dumps -- was never scanned. That is exactly the kind of file a stray
#: credential ends up in. Only the explicitly gitignored scratch subdirectory
#: is skipped now; see ``_is_skipped``.
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache",
    ".mypy_cache", "dist", "build", ".idea", ".vscode", ".ruff_cache",
}

#: Path fragments skipped by substring rather than by directory name, so a
#: generic word like "results" cannot blind the scanner to a whole tree.
SKIP_PATH_FRAGMENTS = ("evidence/results/tmp/",)


def _is_skipped(rel_posix: str) -> bool:
    return any(frag in rel_posix for frag in SKIP_PATH_FRAGMENTS)

#: Extensions worth scanning. Binary media cannot usefully be grepped and a
#: recorded demo is checked by eye, not by regex.
SCAN_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".yaml",
    ".yml", ".toml", ".md", ".txt", ".sh", ".bat", ".ps1", ".env", ".cfg",
    ".ini", ".conf", "",
}

#: Values that look like keys but are obviously not.
PLACEHOLDERS = re.compile(
    # "your-key", "your-api-key", "your-rime-api-key", "your_livekit_secret" --
    # the canonical placeholder shape used throughout .env.example and the docs.
    r"(your[-_ ][a-z0-9-_]{0,24}(key|secret|token)|xxx+|\.\.\.|<[^>]{1,40}>|placeholder|example|"
    r"changeme|replace[-_ ]?me|dummy|fake|sk_test_|redacted|\babc123\b|"
    r"lk_api_key_here|paste[-_ ]?here"
    # Template interpolation: the literal in the file is a variable name, not
    # a credential. Covers ${VAR}, {{var}}, {VAR} f-strings and %(var)s.
    r"|\$\{[^}]+\}|\{\{[^}]+\}\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%\([^)]+\)s"
    # Canonical documentation forms for a URL carrying userinfo.
    r"|:(secret|password|pass|token)@)",
    re.IGNORECASE,
)

#: Public vendor identifiers that happen to match the LiveKit key shape.
#:
#: The key rule below matches ``API`` followed by ten or more characters, which
#: is what a LiveKit API key looks like -- and also what LiveKit's own public
#: exception and option classes look like. Every one of these gets reported as
#: a leaked credential:
#:
#:     APIConnectionError  APIStatusError  APITimeoutError  APIConnectOptions
#:
#: That is not theoretical. Six places in this repository format errors as
#: ``f"{type(exc).__name__}: {exc}"``, and for any Rime or LiveKit failure that
#: name *is* one of these. The moment someone pastes real tool output into
#: ``team/worksheets/MEASUREMENTS.md`` -- which that file explicitly asks them to do -- the
#: pre-commit hook blocks the commit and reports a credential leak in a line
#: containing no credential. At 3am that reads as "I have burned a key."
#:
#: These are **subtracted from matches** rather than excluded by narrowing the
#: pattern. That direction matters. The obvious fix is a negative lookahead
#: rejecting CamelCase tails (``API(?![A-Z][a-z])...``), and it is wrong: it
#: also rejects real keys whose fourth character is a capital followed by a
#: lowercase, e.g. ``API`` + ``Rb7kQm2xLp9w``. That is a false negative in a
#: security control, which is strictly worse than the noise it removes.
#:
#: "Subtracted from matches" is a claim about the *scan loop*, not about this
#: list, and for one revision the loop did not honour it: it matched with
#: ``re.search`` and skipped the whole rule on an allowlist hit, so a real key
#: sharing a line with a vendor name was never looked at. The list was
#: innocent; the loop reduced detection. It now iterates every match on the
#: line and skips only the allowlisted ones, which is what makes the sentence
#: below true rather than merely intended.
#:
#: With that loop, this list can only ever reduce noise; it cannot reduce
#: detection. Both halves are tested, and the second half is tested in both
#: orders: see ``tests/test_secret_scan.py`` --
#: ``test_a_real_key_shaped_like_a_vendor_name_is_still_flagged`` and
#: ``test_a_key_after_a_vendor_name_on_the_same_line_is_found``.
VENDOR_IDENTIFIERS = frozenset({
    "APIConnectionError",
    "APIConnectOptions",
    "APIStatusError",
    "APITimeoutError",
    "APIConnectError",
    "APIError",
})

#: Inline escape hatch, on the offending line or the one above it.
#:
#: Needed for the cases no heuristic can resolve: a docstring showing the
#: *shape* of a credential, a test fixture, a regex that matches keys. Every
#: real scanner has one, and without it the first false positive on deadline
#: day gets the whole check switched off, which is strictly worse than a
#: scanner with an audited escape hatch.
PRAGMA = re.compile(r"secret[-_ ]?scan:\s*(allow|ignore)", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    excerpt: str


RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "LiveKit API key (APIxxxxxxxxxxxx)",
        re.compile(r"\bAPI[A-Za-z0-9]{10,}\b"),
    ),
    (
        "assigned secret-looking value",
        # The optional quotes around the *name* are what make this work on
        # JSON. Without them the pattern matched `api_key = "..."` but missed
        # `"api_key": "..."`, because the closing quote sits between the name
        # and the colon. JSON is the format of every committed artifact in
        # `evidence/results/` -- the directory that, until the same review,
        # `SKIP_DIRS` also excluded from the walk entirely. The two gaps hid
        # each other: nothing could find a key there, and nothing looked.
        re.compile(
            r"(?i)[\"']?\b(api[-_]?key|apikey|secret|token|password|passwd"
            r"|credential)\b[\"']?\s*[:=]\s*[\"']([^\"'\s]{16,})[\"']"
        ),
    ),
    (
        "OpenAI-style key",
        re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    ),
    (
        "Rime-style key",
        re.compile(r"(?i)\brime[-_]?(api[-_]?)?key\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{20,})"),
    ),
    (
        "private key block",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    (
        "credentials embedded in a URL",
        re.compile(r"\b[a-z]{2,6}://[^/\s:@]{2,}:[^/\s@]{6,}@"),
    ),
    (
        "AWS access key id",
        re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
]


def _is_template(path: Path) -> bool:
    """.env.example exists to hold placeholders. Scanning it is noise."""
    return path.name in {".env.example", "env.example"} or path.name.endswith(
        ".example"
    )


def _looks_placeholder(line: str) -> bool:
    return bool(PLACEHOLDERS.search(line))


def scan_text(path: Path, text: str, rel: str) -> list[Finding]:
    out: list[Finding] = []
    template = _is_template(path)
    for i, line in enumerate(text.splitlines(), start=1):
        if len(line) > 2000:
            continue
        if _looks_placeholder(line) or PRAGMA.search(line):
            continue
        # A pragma on the preceding line covers this one, so a long literal
        # can be annotated without wrapping the comment onto it.
        if i >= 2 and PRAGMA.search(text.splitlines()[i - 2]):
            continue
        # A line that is only documenting a variable name is fine.
        stripped = line.strip()
        if stripped.startswith("#") and "=" not in stripped:
            continue
        for rule, pattern in RULES:
            if template and rule != "private key block":
                continue
            # ``finditer``, not ``search``. The allowlist check skips a
            # *match*; with ``search`` it skipped the whole rule for the line,
            # because ``search`` only ever returns the first match. So a line
            # carrying a vendor class name *before* a real key went unscanned
            # past that class name -- a false negative in a security control,
            # which is precisely what the note on VENDOR_IDENTIFIERS promises
            # this design cannot produce.
            #
            # Not hypothetical. ``evidence/results/latency.md`` already reads
            # ``APIStatusError: message='Invalid response status', ...``, and
            # ``team/worksheets/MEASUREMENTS.md`` asks a human to paste real tool output
            # into the repository. One key in one such line and the scanner
            # reported ``clean``.
            #
            # See ``tests/test_secret_scan.py`` -- "a key hiding behind a
            # vendor name".
            m = next(
                (
                    hit
                    for hit in pattern.finditer(line)
                    if hit.group(0) not in VENDOR_IDENTIFIERS
                ),
                None,
            )
            if m is None:
                continue
            excerpt = line.strip()
            if len(excerpt) > 120:
                excerpt = excerpt[:117] + "..."
            out.append(Finding(rel, i, rule, excerpt))
            break
    return out


def iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        try:
            if _is_skipped(p.relative_to(root).as_posix()):
                continue
        except ValueError:
            pass
        if p.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if p.name.startswith(".env") and not p.name.endswith(".example"):
            # A real .env must never be committed; .gitignore covers it, and
            # scanning its contents would print the secret we are protecting.
            continue
        try:
            if p.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        yield p


def scan(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for p in iter_files(root):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        findings.extend(scan_text(p, text, str(p.relative_to(root)).replace("\\", "/")))
    return findings


def scan_staged(root: Path = ROOT) -> list[Finding]:
    try:
        names = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=root, text=True,
        ).split()
    except Exception:
        return scan(root)
    findings: list[Finding] = []
    for name in names:
        p = root / name
        if not p.is_file() or p.suffix.lower() not in SCAN_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        findings.extend(scan_text(p, text, name))
    return findings


def check_gitignore(root: Path = ROOT) -> list[str]:
    """The scanner is the second line of defence; .gitignore is the first."""
    gi = root / ".gitignore"
    if not gi.exists():
        return [".gitignore is missing"]
    body = gi.read_text(encoding="utf-8")
    problems = []
    for required in (".env", ".env.local"):
        if required not in body:
            problems.append(f".gitignore does not cover {required}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staged", action="store_true", help="scan staged files only")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    findings = scan_staged(ROOT) if args.staged else scan(ROOT)
    gitignore_problems = check_gitignore(ROOT)

    if not findings and not gitignore_problems:
        if not args.quiet:
            scope = "staged files" if args.staged else "the repository"
            print(f"secret_scan: clean. No credential found in {scope}.")
        return 0

    print("secret_scan: PROBLEMS FOUND", file=sys.stderr)
    for problem in gitignore_problems:
        print(f"  ! {problem}", file=sys.stderr)
    for f in findings:
        print(f"  {f.path}:{f.line}  [{f.rule}]", file=sys.stderr)
        print(f"      {f.excerpt}", file=sys.stderr)
    print(
        "\n  If any of these is a real credential: rotate it now, then remove "
        "it from the file.\n  A secret in a public commit is burned even if "
        "the next commit deletes it.\n  If it is a false positive, make the "
        "value obviously a placeholder.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
