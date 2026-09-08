"""The documentation integrity checker.

``scripts/check_docs.py`` exists because five documentation defects shipped in
this repository and every one of them was caught by a person reading carefully
rather than by anything automated. A checker that is itself unchecked would be
the same class of mistake one level up, so this file tests both halves of its
job: that it catches each defect it was written for, and that it stays quiet on
the legitimate constructions that look like those defects.

The second half is load-bearing. ``docs/audits/`` and ``VERIFICATION.md`` are
adversarial reports whose whole purpose is to quote the placeholders they
found, and ``RIME_EVIDENCE.md`` legitimately writes "112 of the 573 tests". A
checker that fires on those gets its exemptions widened until it checks
nothing.

The last test in this file runs every check against the real repository. That
is the one that would have caught the broken ``../../`` links, so it is the one
that must never be marked ``xfail``.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_docs import (  # noqa: E402
    CHECKS,
    REPO_NAME,
    Finding,
    check_clone_dir,
    check_links,
    check_mutation_counts,
    check_per_file_tests,
    check_placeholders,
    check_test_count,
    collected_per_file,
    collected_test_count,
    run_all,
)


def write(root: Path, rel: str, text: str) -> Path:
    """Create a markdown file inside a fake repository."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return p


def checks(findings: list[Finding]) -> list[str]:
    return [f.check for f in findings]


def details(findings: list[Finding]) -> str:
    return "\n".join(f.detail for f in findings)


# ---------------------------------------------------------------- links


def test_link_to_a_missing_file_is_a_finding(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "See [the notes](team/NOTES.md).")
    found = check_links(tmp_path)
    assert checks(found) == ["links"]
    assert "team/NOTES.md" in details(found)


def test_link_to_an_existing_file_is_not(tmp_path: Path) -> None:
    write(tmp_path, "team/NOTES.md", "notes")
    write(tmp_path, "README.md", "See [the notes](team/NOTES.md).")
    assert check_links(tmp_path) == []


def test_the_real_bug_a_worksheet_moved_up_one_directory(tmp_path: Path) -> None:
    """The defect that turned CI red for two commits.

    ``team/LISTENING_NOTES.md`` was copied from a template in
    ``team/worksheets/`` and kept its ``../../`` prefixes, which from ``team/``
    point outside the repository entirely.
    """
    write(tmp_path, "docs/LISTENING_TEST.md", "method")
    write(
        tmp_path,
        "team/LISTENING_NOTES.md",
        "The method is in [LISTENING_TEST.md](../../docs/LISTENING_TEST.md).",
    )
    found = check_links(tmp_path)
    assert checks(found) == ["links"]

    # ...and one ``../`` is correct.
    write(
        tmp_path,
        "team/LISTENING_NOTES.md",
        "The method is in [LISTENING_TEST.md](../docs/LISTENING_TEST.md).",
    )
    assert check_links(tmp_path) == []


def test_external_and_anchor_links_are_skipped(tmp_path: Path) -> None:
    write(
        tmp_path,
        "README.md",
        """
        [video](https://youtu.be/EChOFjIuyNM)
        [mail](mailto:someone@example.com)
        [section](#the-claim)
        """,
    )
    assert check_links(tmp_path) == []


def test_a_link_shown_inside_code_is_not_followed(tmp_path: Path) -> None:
    """Documentation that *displays* markdown syntax is not offering a link."""
    write(
        tmp_path,
        "README.md",
        """
        Write it as `[text](some/path.md)` in the table.

        ```markdown
        [another](also/missing.md)
        ```
        """,
    )
    assert check_links(tmp_path) == []


def test_findings_report_the_line_the_link_is_on(tmp_path: Path) -> None:
    write(
        tmp_path,
        "README.md",
        """
        line one
        line two
        [broken](nope.md)
        """,
    )
    assert check_links(tmp_path)[0].line == 3


# --------------------------------------------------------- placeholders


def test_an_unfilled_placeholder_in_the_readme_is_a_finding(tmp_path: Path) -> None:
    """The defect that left the deliverables table blank on the front page."""
    write(
        tmp_path,
        "README.md",
        "| **Demo video** | `FILL: unlisted YouTube link` |",
    )
    found = check_placeholders(tmp_path)
    assert checks(found) == ["placeholders"]
    assert "FILL:" in details(found)


def test_the_filled_link_is_not_a_finding(tmp_path: Path) -> None:
    write(
        tmp_path,
        "README.md",
        "| **Demo video** | https://youtu.be/EChOFjIuyNM |",
    )
    assert check_placeholders(tmp_path) == []


@pytest.mark.parametrize(
    "rel",
    ["docs/audits/AUDIT-3.md", "VERIFICATION.md", "team/WORKFLOW.md"],
)
def test_reports_and_worksheets_may_quote_placeholders(
    tmp_path: Path, rel: str
) -> None:
    """A bug report that may not name ``REPLACE-ME`` cannot report it."""
    write(tmp_path, rel, "The badge still said `REPLACE-ME` and a `FILL:` blank.")
    assert check_placeholders(tmp_path) == []


def test_a_doc_nobody_ships_is_not_placeholder_checked(tmp_path: Path) -> None:
    """Only the documents on the shipped list are held to this standard."""
    write(tmp_path, "SCRATCH.md", "`FILL: something`")
    assert check_placeholders(tmp_path) == []


# ------------------------------------------------------ mutation_counts


def _fake_harnesses(root: Path, core: int, wiring: int) -> None:
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "mutation_test.py").write_text(
        f"MUTANTS = {[('a', 'b', 'c', 'd', 'e')] * core!r}\n", encoding="utf-8"
    )
    (root / "evidence" / "mutation_test_ii.py").write_text(
        f"MUTANTS = {[('a', 'b', 'c', 'd', 'e')] * wiring!r}\n", encoding="utf-8"
    )


def test_a_drifted_mutation_count_is_a_finding(tmp_path: Path) -> None:
    """The README said 28 and 13 against harnesses declaring 15 and 19."""
    _fake_harnesses(tmp_path, core=15, wiring=19)
    write(
        tmp_path,
        "README.md",
        """
        between them 28 targets:
        mutation_test_ii.py    # 13 targets, everything else
        """,
    )
    found = check_mutation_counts(tmp_path)
    assert checks(found) == ["mutation_counts", "mutation_counts"]
    assert "15 + 19 = 34" in details(found)


@pytest.mark.parametrize("claimed", [15, 19, 34])
def test_each_harness_count_and_their_sum_are_accepted(
    tmp_path: Path, claimed: int
) -> None:
    _fake_harnesses(tmp_path, core=15, wiring=19)
    write(tmp_path, "README.md", f"between them {claimed} targets")
    assert check_mutation_counts(tmp_path) == []


def test_the_count_comes_from_the_table_not_from_prose(tmp_path: Path) -> None:
    """Adding a mutant changes the answer without anybody editing the check."""
    _fake_harnesses(tmp_path, core=16, wiring=19)
    write(tmp_path, "README.md", "between them 34 targets")
    assert "16 + 19 = 35" in details(check_mutation_counts(tmp_path))


# ----------------------------------------------------------- clone_dir


def test_the_wrong_clone_directory_is_a_finding(tmp_path: Path) -> None:
    """The first command a judge runs, and it failed."""
    write(
        tmp_path,
        "README.md",
        """
        ```bash
        git clone <this repo> && cd waypoint
        ```
        """,
    )
    found = check_clone_dir(tmp_path)
    assert checks(found) == ["clone_dir"]
    assert REPO_NAME in details(found)


def test_the_right_clone_directory_on_the_following_line(tmp_path: Path) -> None:
    write(
        tmp_path,
        "README.md",
        f"""
        ```bash
        git clone https://github.com/x/{REPO_NAME}
        cd {REPO_NAME}
        ```
        """,
    )
    assert check_clone_dir(tmp_path) == []


def test_a_cd_unrelated_to_a_clone_is_ignored(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "```bash\ncd evidence\n```")
    assert check_clone_dir(tmp_path) == []


# ---------------------------------------------------------- test_count


def test_a_stale_total_is_a_finding(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "pytest    # 573 passed")
    found = check_test_count(tmp_path, actual=580)
    assert checks(found) == ["test_count"]
    assert "pytest collects 580" in details(found)


def test_the_current_total_is_not(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "pytest    # 573 passed")
    assert check_test_count(tmp_path, actual=573) == []


def test_a_subset_claim_is_read_as_a_subset(tmp_path: Path) -> None:
    """"112 of the 573 tests" must not be read as a claim that 112 is the total."""
    write(tmp_path, "docs/ARCHITECTURE.md", "112 of the 573 tests live on this module")
    assert check_test_count(tmp_path, actual=573) == []


def test_a_subset_with_a_stale_denominator_is_a_finding(tmp_path: Path) -> None:
    write(tmp_path, "docs/ARCHITECTURE.md", "112 of the 573 tests live here")
    assert "uses 573 as the suite total" in details(
        check_test_count(tmp_path, actual=580)
    )


def test_a_subset_larger_than_the_suite_is_a_finding(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "900 of the 573 tests")
    assert "larger than the suite" in details(check_test_count(tmp_path, actual=573))


def test_a_bare_module_count_is_treated_as_a_total_claim(tmp_path: Path) -> None:
    """The README's module table said "109 tests" for a file collecting 112.

    Requiring the ``N of the M`` form for subsets is what makes this
    detectable: a bare count is unambiguously a claim about the whole suite.
    """
    write(tmp_path, "README.md", "| `fencing.py` | The turn fence, 109 tests. |")
    assert "write it as 'N of the 573'" in details(
        check_test_count(tmp_path, actual=573)
    )


# ------------------------------------------------------ per_file_tests


REAL_BREAKDOWN = """
    | File | Tests | Covers |
    |---|---|---|
    | `test_fencing.py` | **112** | every fence invariant |
    | `test_agent.py` | 28 | the fence integration |
    """


def test_a_drifted_row_is_a_finding(tmp_path: Path) -> None:
    """RIME_EVIDENCE.md listed 66 for a file collecting 158."""
    write(tmp_path, "RIME_EVIDENCE.md", REAL_BREAKDOWN)
    found = check_per_file_tests(
        tmp_path, {"test_fencing.py": 112, "test_agent.py": 66}
    )
    assert checks(found) == ["per_file_tests"]
    assert "test_agent.py listed as 28; pytest collects 66" in details(found)


def test_a_matching_breakdown_is_not(tmp_path: Path) -> None:
    write(tmp_path, "RIME_EVIDENCE.md", REAL_BREAKDOWN)
    assert (
        check_per_file_tests(tmp_path, {"test_fencing.py": 112, "test_agent.py": 28})
        == []
    )


def test_an_omitted_file_understates_the_suite(tmp_path: Path) -> None:
    """The breakdown was missing ``test_acceptance_harness.py`` entirely."""
    write(tmp_path, "RIME_EVIDENCE.md", REAL_BREAKDOWN)
    found = check_per_file_tests(
        tmp_path,
        {"test_fencing.py": 112, "test_agent.py": 28, "test_acceptance_harness.py": 27},
    )
    assert "omits test_acceptance_harness.py (27 tests)" in details(found)


def test_a_row_naming_a_file_pytest_does_not_collect(tmp_path: Path) -> None:
    write(tmp_path, "RIME_EVIDENCE.md", REAL_BREAKDOWN)
    found = check_per_file_tests(tmp_path, {"test_fencing.py": 112})
    assert "which pytest does not collect" in details(found)


def test_a_short_example_table_is_not_forced_to_be_complete(tmp_path: Path) -> None:
    """A doc quoting two rows as an illustration is not an inventory."""
    write(tmp_path, "RIME_EVIDENCE.md", REAL_BREAKDOWN)
    actual = {f"test_{n}.py": 1 for n in "abcdefgh"}
    actual.update({"test_fencing.py": 112, "test_agent.py": 28})
    found = check_per_file_tests(tmp_path, actual)
    assert [f for f in found if "omits" in f.detail] == []


def test_no_breakdown_anywhere_is_not_a_finding(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "no table here")
    assert check_per_file_tests(tmp_path, {"test_fencing.py": 112}) == []


def test_a_failed_collection_reports_nothing_here(tmp_path: Path) -> None:
    """``test_count`` reports the real problem; this check stays quiet."""
    write(tmp_path, "RIME_EVIDENCE.md", REAL_BREAKDOWN)
    assert check_per_file_tests(tmp_path, {}) == []


# ------------------------------------------- the real repository passes


def test_collection_finds_the_suite() -> None:
    """Guards the parsing, not the count.

    ``pytest --collect-only -q`` prints one ``path: N`` line per file in this
    repository and no grand total. An earlier version of this parser looked
    only for "N tests collected", found nothing, and reported a total of zero
    -- which would have failed every count check for the wrong reason.
    """
    per_file = collected_per_file(ROOT)
    assert per_file, "collection returned nothing; the parser is broken"
    assert all(v > 0 for v in per_file.values())
    assert sum(per_file.values()) == collected_test_count(ROOT)


def test_every_named_check_runs() -> None:
    assert set(CHECKS) == {
        "links",
        "placeholders",
        "mutation_counts",
        "clone_dir",
        "test_count",
        "per_file_tests",
    }


def test_this_repository_is_clean() -> None:
    """The whole point.

    Every defect this module was written for shipped here. If this fails, the
    documentation disagrees with the repository -- fix the document or fix the
    claim, but do not skip this test.
    """
    findings = run_all(ROOT)
    assert not findings, "\n" + "\n".join(str(f) for f in findings)
