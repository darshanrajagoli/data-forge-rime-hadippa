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
    check_spelled_counts,
    check_test_count,
    collected_per_file,
    collected_test_count,
    int_to_words,
    run_all,
    words_to_int,
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


def test_an_unlisted_root_document_is_checked_too(tmp_path: Path) -> None:
    """This test used to assert the opposite, and the opposite was a hole.

    While the check required membership in a ``SHIPPED_DOCS`` allowlist, a
    scratch file was unchecked -- and so was any real document added after the
    list was written. Running RED-TEAM-PROMPT-4 against this module surfaced
    it: the gate failed open. It fails closed now, and an exemption has to be
    written down deliberately.
    """
    write(tmp_path, "SCRATCH.md", "`FILL: something`")
    assert checks(check_placeholders(tmp_path)) == ["placeholders"]


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
        "spelled_counts",
    }


def test_this_repository_is_clean() -> None:
    """The whole point.

    Every defect this module was written for shipped here. If this fails, the
    documentation disagrees with the repository -- fix the document or fix the
    claim, but do not skip this test.
    """
    findings = run_all(ROOT)
    assert not findings, "\n" + "\n".join(str(f) for f in findings)


# ------------------------------------------------- the check-docs pragma


def test_a_pragma_on_the_line_above_excuses_a_stale_number(tmp_path: Path) -> None:
    """The real case: the demo video narration says a number that has moved on.

    The video was filmed at 573 tests and says so out loud. Explaining that is
    more honest than deleting the sentence or exempting the whole file.
    """
    write(
        tmp_path,
        "DEMO_SCRIPT.md",
        """
        <!-- check-docs: allow -- the recorded narration really does say 573 -->
        > It was filmed with a suite of 573 tests.
        """,
    )
    assert check_test_count(tmp_path, actual=609) == []


def test_a_pragma_on_the_same_line_also_works(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "573 tests <!-- check-docs: allow -- historical -->")
    assert check_test_count(tmp_path, actual=609) == []


def test_the_pragma_does_not_reach_the_line_after_next(tmp_path: Path) -> None:
    """The hole must stay exactly two lines wide.

    A marker that covered a whole block would let a genuine defect drift in
    underneath an excuse written months earlier for something else.
    """
    write(
        tmp_path,
        "README.md",
        """
        <!-- check-docs: allow -- excuses the next line only -->
        573 tests, deliberately historical
        480 tests, nobody excused this one
        """,
    )
    found = check_test_count(tmp_path, actual=609)
    assert len(found) == 1
    assert "480" in details(found)


def test_the_pragma_does_not_leak_to_other_files(tmp_path: Path) -> None:
    write(tmp_path, "DEMO_SCRIPT.md", "<!-- check-docs: allow -->\n573 tests")
    write(tmp_path, "README.md", "573 tests")
    found = check_test_count(tmp_path, actual=609)
    assert [f.path for f in found] == ["README.md"]


@pytest.mark.parametrize(
    "marker",
    ["check-docs: allow", "check_docs: allow", "CHECK-DOCS: IGNORE", "checkdocs:allow"],
)
def test_pragma_spellings(tmp_path: Path, marker: str) -> None:
    """Matches the tolerance of secret_scan.py's pragma, for one convention."""
    write(tmp_path, "README.md", f"<!-- {marker} -->\n573 tests")
    assert check_test_count(tmp_path, actual=609) == []


def test_an_unexcused_line_in_a_file_that_uses_a_pragma_is_still_checked(
    tmp_path: Path,
) -> None:
    """Using the hatch once does not switch the file off."""
    write(
        tmp_path,
        "README.md",
        """
        <!-- check-docs: allow -->
        573 tests, excused

        some prose

        [broken](nope.md)
        """,
    )
    assert checks(check_links(tmp_path)) == ["links"]


def test_the_pragma_suppresses_every_check_on_its_line(tmp_path: Path) -> None:
    """It is a line-level hatch, not a per-check one -- so it needs a reason."""
    write(tmp_path, "README.md", "<!-- check-docs: allow -->\n[gone](missing.md)")
    assert check_links(tmp_path) == []


def test_a_pragma_cannot_hide_a_placeholder_in_a_shipped_doc_by_accident(
    tmp_path: Path,
) -> None:
    """Only the two covered lines are excused; the rest of the doc is not."""
    write(
        tmp_path,
        "README.md",
        """
        <!-- check-docs: allow -->
        `FILL: excused on purpose`
        `FILL: this one is a real defect`
        """,
    )
    found = check_placeholders(tmp_path)
    assert len(found) == 1
    assert "real defect" in details(found)


# ------------------------------- holes found by running RED-TEAM-PROMPT-4


def test_a_document_added_later_is_placeholder_checked_by_default(
    tmp_path: Path,
) -> None:
    """The gate fails closed.

    It used to require membership in a SHIPPED_DOCS allowlist. A judge-facing
    document written after that list was drawn up -- a PITCH.md, a
    ONE-PAGER.md -- was therefore unchecked, and would have shipped with its
    blanks intact. That is the exact defect this module exists to prevent,
    walking back in through a file nobody remembered to enumerate.
    """
    write(tmp_path, "PITCH.md", "| Demo | `FILL: link goes here` |")
    found = check_placeholders(tmp_path)
    assert checks(found) == ["placeholders"]
    assert "PITCH.md" == found[0].path


def test_a_new_doc_under_docs_is_also_checked(tmp_path: Path) -> None:
    write(tmp_path, "docs/ONE-PAGER.md", "`FILL: the number`")
    assert checks(check_placeholders(tmp_path)) == ["placeholders"]


def test_the_exemptions_still_hold_after_inverting(tmp_path: Path) -> None:
    """Failing closed must not start firing on the reports that quote defects."""
    write(tmp_path, "docs/audits/AUDIT-9.md", "it still said `REPLACE-ME`")
    write(tmp_path, "VERIFICATION.md", "the table read `FILL: link`")
    write(tmp_path, "team/NOTES.md", "`FILL: measure this`")
    assert check_placeholders(tmp_path) == []


def test_a_breakdown_missing_two_files_is_still_a_finding(tmp_path: Path) -> None:
    """The completeness threshold used to allow exactly this.

    "Missing at most one" left a table omitting two files unchecked. The real
    defect omitted one file while two other rows were hundreds out, so a second
    omission was well within reach.
    """
    write(
        tmp_path,
        "RIME_EVIDENCE.md",
        """
        | File | Tests | Covers |
        |---|---|---|
        | `test_a.py` | 10 | a |
        | `test_b.py` | 10 | b |
        | `test_c.py` | 10 | c |
        """,
    )
    actual = {"test_a.py": 10, "test_b.py": 10, "test_c.py": 10,
              "test_d.py": 10, "test_e.py": 10}
    omissions = [f for f in check_per_file_tests(tmp_path, actual) if "omits" in f.detail]
    assert len(omissions) == 2
    assert "test_d.py" in details(omissions)
    assert "test_e.py" in details(omissions)


def test_a_two_row_illustration_is_still_not_forced_to_be_complete(
    tmp_path: Path,
) -> None:
    """The other half of the trade-off: below half the suite it reads as a sample."""
    write(
        tmp_path,
        "RIME_EVIDENCE.md",
        """
        | File | Tests | Covers |
        |---|---|---|
        | `test_a.py` | 10 | a |
        """,
    )
    actual = {f"test_{c}.py": 10 for c in "abcdefgh"}
    assert [f for f in check_per_file_tests(tmp_path, actual) if "omits" in f.detail] == []


def test_a_failed_collection_is_still_reported_loudly_somewhere(
    tmp_path: Path,
) -> None:
    """per_file_tests goes quiet on an empty collection; test_count must not.

    Otherwise a broken collection would look like a clean run.
    """
    write(tmp_path, "README.md", "620 tests")
    assert check_per_file_tests(tmp_path, {}) == []
    assert checks(check_test_count(tmp_path, actual=0)) == ["test_count"]


def test_evidence_markdown_is_checked_too(tmp_path: Path) -> None:
    """A third fail-open gap, found by adding a file the checker could not see.

    ``_markdown_files`` globbed the repository root, ``docs/`` and ``team/``.
    ``evidence/`` was invisible -- which is the directory a judge browses for
    the artifacts, and where ``evidence/results/README.md`` explains why two
    committed reports show failures. A broken link in the one document written
    to prevent confusion would have shipped unnoticed.
    """
    write(tmp_path, "evidence/results/README.md", "See [the notes](../../team/GONE.md).")
    found = check_links(tmp_path)
    assert checks(found) == ["links"]
    assert found[0].path == "evidence/results/README.md"


def test_generated_evidence_artifacts_do_not_trip_the_checker(tmp_path: Path) -> None:
    """Including evidence/ must not start firing on committed tool output.

    ``acceptance.md`` and the pronunciation report are generated files full of
    numbers and table rows. If checking them produced findings, the pressure
    would be to exclude the directory again rather than to fix anything.
    """
    write(
        tmp_path,
        "evidence/results/acceptance.md",
        """
        - Commit: `abc1234`
        | **A2** A superseded write never reaches the backend | ... | 6/6 | PASS |
        | `addr-gough` | coda | none | 1247 Gough Street | - | _unverified_ |
        """,
    )
    assert check_links(tmp_path) == []
    assert check_placeholders(tmp_path) == []
    assert check_per_file_tests(tmp_path, {"test_a.py": 1}) == []


# ----------------------------------- links must point at *committed* files


def _git_repo(root: Path) -> None:
    """A real repository, so ``git ls-files`` has something to say."""
    import subprocess

    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(args, cwd=root, check=True, capture_output=True)


def _commit_all(root: Path) -> None:
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "x"], cwd=root, check=True, capture_output=True
    )


def test_a_link_to_a_generated_file_is_a_finding(tmp_path: Path) -> None:
    """The bug that turned CI red on the final commit.

    ``evidence/results/README.md`` linked to ``acceptance.md``, which is
    deliberately gitignored -- four people run the acceptance harness and four
    runs would collide. The file was in the author's tree because they had run
    it, so every local check passed and the link was dead for everyone else.

    Existence alone cannot see this. Only ``git ls-files`` can.
    """
    _git_repo(tmp_path)
    write(tmp_path, ".gitignore", "generated.md\n")
    write(tmp_path, "README.md", "See [the run](generated.md).")
    _commit_all(tmp_path)
    write(tmp_path, "generated.md", "produced by a script")  # exists, untracked

    found = check_links(tmp_path)
    assert checks(found) == ["links"]
    assert "not committed" in details(found)


def test_a_link_to_a_committed_file_is_not(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    write(tmp_path, "kept.md", "committed")
    write(tmp_path, "README.md", "See [the notes](kept.md).")
    _commit_all(tmp_path)
    assert check_links(tmp_path) == []


def test_a_link_to_a_committed_directory_is_not(tmp_path: Path) -> None:
    """``docs/audits/`` is a directory link; tracking is by the files inside."""
    _git_repo(tmp_path)
    write(tmp_path, "docs/audits/AUDIT-3.md", "report")
    write(tmp_path, "README.md", "See [the audits](docs/audits/).")
    _commit_all(tmp_path)
    assert check_links(tmp_path) == []


def test_outside_a_git_repository_only_existence_is_checked(tmp_path: Path) -> None:
    """A ZIP without .git must still be checkable, not fail every link."""
    write(tmp_path, "kept.md", "here")
    write(tmp_path, "README.md", "See [the notes](kept.md).")
    assert check_links(tmp_path) == []


# ----------------------------------------------- counts spelled out in words


@pytest.mark.parametrize(
    "n", [100, 112, 573, 609, 628, 632, 700, 999, 1000, 1207, 9999]
)
def test_number_words_round_trip(n: int) -> None:
    assert words_to_int(int_to_words(n)) == n


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("six hundred and thirty-two", 632),
        ("a hundred and twelve", 112),
        ("five hundred and seventy-three", 573),
        ("six hundred and nine", 609),
        ("one thousand two hundred and seven", 1207),
        ("not a number at all", None),
    ],
)
def test_parsing_the_forms_the_narration_actually_uses(phrase, expected) -> None:
    assert words_to_int(phrase) == expected


def test_a_stale_spelled_out_total_is_a_finding(tmp_path: Path) -> None:
    """The narration drifted twice while every digit check stayed green.

    It is the number the presenter says on camera, so it is simultaneously the
    least visible in a diff and the most quoted to a judge.
    """
    write(tmp_path, "DEMO_SCRIPT.md", '> "Six hundred and twenty-eight tests."')
    found = check_spelled_counts(tmp_path, actual=632)
    assert checks(found) == ["spelled_counts"]
    assert "is 628" in details(found)
    assert "six hundred and thirty-two" in details(found)


def test_the_current_spelled_out_total_is_not(tmp_path: Path) -> None:
    write(tmp_path, "DEMO_SCRIPT.md", '> "Six hundred and thirty-two tests."')
    assert check_spelled_counts(tmp_path, actual=632) == []


def test_a_spelled_out_subset_is_left_alone(tmp_path: Path) -> None:
    """"A hundred and twelve of them are on the fence" is a fraction.

    The noun is what separates the two, exactly as in the digit rule: a total
    is followed by "tests", a subset by "of them".
    """
    write(
        tmp_path,
        "DEMO_SCRIPT.md",
        '> "Six hundred and thirty-two tests. A hundred and twelve of them are\n'
        '> on the fence alone, and seventy of those are seeded fuzz runs."',
    )
    assert check_spelled_counts(tmp_path, actual=632) == []


def test_the_pragma_covers_the_spelled_out_check_too(tmp_path: Path) -> None:
    """The recorded narration says 573 and always will."""
    write(
        tmp_path,
        "DEMO_SCRIPT.md",
        "<!-- check-docs: allow -- the video really does say this -->\n"
        '> The narration says "five hundred and seventy-three tests".',
    )
    assert check_spelled_counts(tmp_path, actual=632) == []
