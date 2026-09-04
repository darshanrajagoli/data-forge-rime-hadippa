"""The harness that produces the evidence.

Three adversarial passes looked at this project. The first looked at the tested
code, the second at the untested code beside it, and the third asked a better
question: who tests the thing that manufactures the proof?

Nobody did. ``evidence/`` sat at 0% coverage with zero mutation targets, and
every one of the 36 assertions in ``run_acceptance.py`` funnelled through a
single three-line method that nothing exercised. Changing ``bool(condition)``
to ``True`` in ``Scenario.check`` left the entire suite green. The reviewer
then *also* inverted the fence -- making stale tool results speakable, the one
defect this product exists to prevent -- and ``run_acceptance.py`` still
printed ``6/6 scenarios passed``, exited 0, and overwrote its committed
artifacts with that result. CI would have uploaded them.

That is not a gap in a test. It is a gap in the argument. This repository's
best claim is that "the tests pass" is not evidence, and here is a mutation
harness proving the tests would fail if the code broke. The claim was true and
applied one level too shallow: the mutation harnesses prove the *tests* bite,
and nothing proved the *acceptance harness* did -- and the acceptance harness
is what a judge actually runs.

So this file tests the oracle. Every test below fails against a harness made
vacuous in one of the three ways it could be:

    1. ``check()`` recording a constant     -- the reviewer's mutation
    2. a scenario recording no checks       -- ``all([])`` is True
    3. a scenario dropped from SCENARIOS    -- ``0/0 passed``, exit 0

Paired with entries in ``evidence/mutation_test_ii.py`` that apply exactly
those mutations to the shipped file and require this suite to go red.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evidence"))

from run_acceptance import (  # noqa: E402
    EXPECTED_CHECKS,
    EXPECTED_SHAPE,
    SCENARIOS,
    Scenario,
    audit_run,
    main_async,
    to_markdown,
)


def scenario(id_: str = "X", n_pass: int = 0, n_fail: int = 0) -> Scenario:
    s = Scenario(id=id_, title="t", claim="c", procedure="p")
    for i in range(n_pass):
        s.check(f"pass {i}", True)
    for i in range(n_fail):
        s.check(f"fail {i}", False)
    return s


def full_run() -> list[Scenario]:
    return [scenario(i, n_pass=n) for i, n in EXPECTED_SHAPE.items()]


# --------------------------------------------------------------------------
# 1. check() must record the condition it was given
# --------------------------------------------------------------------------


def test_a_false_condition_is_recorded_as_a_failure() -> None:
    """The reviewer's mutation, stated as a requirement.

    ``self.checks.append(Check(label, True, detail))`` passes every other test
    in this repository. It fails here, which is the entire point of this file.
    """
    s = scenario(n_fail=1)
    assert s.checks[0].passed is False
    assert s.passed is False


@pytest.mark.parametrize(
    "condition,expected",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("", False),
        ("x", True),
        ([], False),
        ([0], True),
        (None, False),
    ],
)
def test_check_coerces_truthiness_and_keeps_the_answer(condition, expected) -> None:
    """``bool(condition)``, not ``condition``: the stored value has to be a real
    bool so that ``acceptance.json`` round-trips through JSON as one."""
    s = Scenario(id="X", title="t", claim="c", procedure="p")
    s.check("l", condition)
    assert s.checks[0].passed is expected
    assert isinstance(s.checks[0].passed, bool)


def test_one_failure_among_many_passes_still_fails_the_scenario() -> None:
    assert scenario(n_pass=20, n_fail=1).passed is False


def test_a_scenario_with_only_passing_checks_passes() -> None:
    """The other direction. A harness that can only ever fail is as useless as
    one that can only ever pass, and would bury a real regression in noise."""
    assert scenario(n_pass=3).passed is True


def test_the_label_and_detail_survive_into_the_record() -> None:
    """A failing check has to say which claim failed. ``[FAIL]`` with no label
    sends someone reading CI output back to the source to guess."""
    s = Scenario(id="X", title="t", claim="c", procedure="p")
    s.check("the gate code was never spoken", False, detail="found in turn 2")
    assert s.checks[0].label == "the gate code was never spoken"
    assert s.checks[0].detail == "found in turn 2"
    assert "FAIL" in s.checks[0].line()
    assert "the gate code was never spoken" in s.checks[0].line()


# --------------------------------------------------------------------------
# 2. all([]) is True -- a scenario that checked nothing proved nothing
# --------------------------------------------------------------------------


def test_a_scenario_that_recorded_no_checks_does_not_pass() -> None:
    """The second vacuity path, which the review did not name.

    Delete the body of a scenario and ``all(c.passed for c in [])`` is True, so
    it renders as PASS with ``0/0`` beside it and the totals still add up.
    """
    assert scenario().passed is False


def test_the_run_audit_names_an_empty_scenario() -> None:
    run = full_run()
    run[-1].checks.clear()
    problems = audit_run(run)
    assert any("A6" in p and "no checks" in p for p in problems)


# --------------------------------------------------------------------------
# 3. the shape of the run is itself an assertion
# --------------------------------------------------------------------------


def test_a_complete_run_audits_clean() -> None:
    assert audit_run(full_run()) == []


def test_a_dropped_scenario_is_caught() -> None:
    """``0/0 scenarios passed`` exits 0. So does 5/5 when there should be 6."""
    problems = audit_run(full_run()[:-1])
    assert any("did not run" in p and "A6" in p for p in problems)
    assert audit_run([]), "an empty run must not audit clean"


def test_a_scenario_that_lost_a_check_is_caught() -> None:
    run = full_run()
    run[0].checks.pop()
    assert any("A1" in p and "expected" in p for p in audit_run(run))


def test_a_scenario_that_gained_a_check_is_caught() -> None:
    """Exact, not a minimum. Adding a claim is fine; adding one without saying
    so in EXPECTED_SHAPE is how a count drifts from what the docs state."""
    run = full_run()
    run[0].check("extra", True)
    assert any("A1" in p for p in audit_run(run))


def test_duplicate_scenario_ids_are_caught() -> None:
    run = full_run()
    run[1].id = "A1"
    assert any("duplicate" in p for p in audit_run(run))


def test_an_unknown_scenario_id_is_caught() -> None:
    run = full_run()
    run[0].id = "A9"
    problems = audit_run(run)
    assert any("A9" in p for p in problems)
    assert any("A1" in p for p in problems)


def test_expected_checks_matches_the_table() -> None:
    assert EXPECTED_CHECKS == sum(EXPECTED_SHAPE.values()) == 36
    assert len(EXPECTED_SHAPE) == len(SCENARIOS) == 6


# --------------------------------------------------------------------------
# 4. the exit code, and the artifacts
# --------------------------------------------------------------------------


def test_the_real_run_has_the_shape_it_claims(tmp_path) -> None:
    """The end-to-end check, run against the real scenarios.

    This is the one that ties EXPECTED_SHAPE to reality rather than to itself.
    It costs about eight seconds and it is the only thing standing between a
    green ``pytest`` and a harness that checks nothing.
    """
    code = asyncio.run(main_async(["--json-only", "--out", str(tmp_path)]))
    assert code == 0

    payload = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))
    assert payload["meta"]["harness_intact"] is True
    assert payload["meta"]["harness_problems"] == []

    shape = {s["id"]: len(s["checks"]) for s in payload["scenarios"]}
    assert shape == EXPECTED_SHAPE
    assert all(s["passed"] for s in payload["scenarios"])
    assert sum(shape.values()) == EXPECTED_CHECKS


def test_a_failing_scenario_produces_a_non_zero_exit(tmp_path, monkeypatch) -> None:
    """``run_acceptance.py`` gates CI and the demo checklist. If a real
    regression cannot turn it red, neither can anything else."""

    async def broken() -> Scenario:
        s = Scenario(id="A1", title="t", claim="c", procedure="p")
        for _ in range(EXPECTED_SHAPE["A1"] - 1):
            s.check("ok", True)
        s.check("deliberately failing", False)
        return s

    monkeypatch.setattr("run_acceptance.SCENARIOS", [broken] + list(SCENARIOS[1:]))
    code = asyncio.run(main_async(["--json-only", "--out", str(tmp_path)]))
    assert code == 1

    payload = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))
    assert payload["meta"]["harness_intact"] is True, "shape was fine; a claim failed"
    a1 = next(s for s in payload["scenarios"] if s["id"] == "A1")
    assert a1["passed"] is False


def test_a_malformed_run_produces_a_non_zero_exit(tmp_path, monkeypatch) -> None:
    """A dropped scenario must not report success, even though every check that
    did run passed."""
    monkeypatch.setattr("run_acceptance.SCENARIOS", list(SCENARIOS[:-1]))
    code = asyncio.run(main_async(["--json-only", "--out", str(tmp_path)]))
    assert code == 1

    payload = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))
    assert payload["meta"]["harness_intact"] is False
    assert any("A6" in p for p in payload["meta"]["harness_problems"])


def test_the_markdown_artifact_declares_a_broken_harness() -> None:
    """The artifact is what gets committed, uploaded by CI and read by a judge.
    It has to carry the warning, not just the terminal that produced it."""
    meta = {
        "run_at": "x",
        "commit": "y",
        "python": "3.12",
        "harness_intact": False,
        "harness_problems": ["A6 did not run"],
        "expected_shape": EXPECTED_SHAPE,
    }
    md = to_markdown(full_run()[:-1], meta)
    assert "HARNESS FAILURE" in md
    assert "A6 did not run" in md
    assert "not evidence" in md


def test_the_markdown_artifact_declares_an_intact_harness() -> None:
    meta = {
        "run_at": "x",
        "commit": "y",
        "python": "3.12",
        "harness_intact": True,
        "harness_problems": [],
        "expected_shape": EXPECTED_SHAPE,
    }
    md = to_markdown(full_run(), meta)
    assert "**intact**" in md
    assert "HARNESS FAILURE" not in md
