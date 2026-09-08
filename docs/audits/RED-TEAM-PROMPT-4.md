# Red team prompt 4

> Paste everything below the line into a fresh Claude session with a machine
> and this repository. It is written to be run cold, by someone who has not
> seen the previous three reviews.

---

This project has survived three adversarial audits. All three found real
defects. Since the third, a fourth wave of changes landed under deadline
pressure — and **that wave is your primary target**, because nothing has
audited it.

Write your findings to `AUDIT-4.md` in the project root. That file is the
deliverable. Someone will work from it without talking to you, so it has to
stand on its own.

## Where things are

- Project: `C:\Users\darsh\OneDrive\Desktop\DataForge\waypoint`
- Brief: `C:\Users\darsh\OneDrive\Desktop\DataForge\Rime PS.pdf`.
  **Read it before you read anything this repository says about it.** The repo
  describes its own rubric compliance at length; that description is under
  audit, not evidence.
- Offline, no credentials: `pip install -e ".[dev]"`, then `pytest`,
  `python evidence/run_acceptance.py`, `python evidence/mutation_test.py`,
  `python evidence/mutation_test_ii.py`, `python scripts/secret_scan.py`,
  `python scripts/check_docs.py`.
- Previous reviews: `docs/audits/AUDIT-2.md`, `docs/audits/AUDIT-3.md`. Read
  them late, not early — form your own view first.

## The shape of the first three passes

So you do not spend your budget re-deriving it.

- **Pass 1** looked in the tested code: documentation and code disagreed, and
  the tests agreed with neither.
- **Pass 2** looked in the untested code next to it: four scripts that could
  not make a single call to the speech provider, a disclosed endpoint pointing
  at the wrong host, a wiring layer where disabling the product's only feature
  left the whole suite green.
- **Pass 3** asked who tests the thing that manufactures the proof, and found
  one token that made all 36 acceptance checks vacuous while every other job
  stayed green.

Each pass found the region the previous one had no reason to look at. **Keep
that habit and drop their targets.** Those three regions now have tests and
mutation coverage.

## The region nobody has audited: the evidence-integrity layer

Between audit 3 and now, one author under deadline pressure:

1. Wrote `scripts/check_docs.py` — a **new gate** with six checks, wired into
   CI, into `scripts/preflight.py`, and into the pre-submit checklist.
2. Rewrote `team/MEASUREMENTS.md` and `team/LISTENING_NOTES.md` from another
   person's hand-filled worksheets, and **transcribed numbers between
   documents by hand**.
3. Folded those numbers into `RIME_EVIDENCE.md` §4, `SUBMISSION.md`,
   `README.md`, `HANDOFF.md` and `team/START-HERE.md`.
4. Marked the pre-submit checklist complete.

That is the classic setup, and it is the same one pass 3 exploited: a new
mechanism whose job is to certify correctness, written by the person whose work
it certifies, immediately, at speed.

### Five specific things to attack

**1. Who checks `check_docs.py`?** This is pass 3's question aimed at the newest
gate. It has 36 tests in `tests/test_check_docs.py` — written by the same author
in the same sitting. Find the mutation that makes it report `clean` on a repo
that is actually broken. Consider: the exemption lists
(`PLACEHOLDER_EXEMPT_PREFIXES`, `PLACEHOLDER_EXEMPT_FILES`, `SHIPPED_DOCS`) —
does a document silently drop out of checking by not being on a list? What
happens to a doc added tomorrow? `_strip_code` blanks fenced and inline code
before link matching; what real link does that hide? `check_per_file_tests`
only enforces completeness when a table already looks complete
(`len(listed) >= len(actual) - 1`) — construct the table that exploits that.
`collected_test_count` has three parsing branches and a silent `0` fallback;
what makes it return a wrong number rather than no number? Note that
`check_per_file_tests` returns `[]` on an empty collection — is the failure
actually reported anywhere, or does it vanish?

**2. Are the transcribed numbers internally consistent?** No committed artifact
backs them — the repository says so, loudly, in several places. That makes
arithmetic the only available check. Verify every derived claim against the
tables: the p50 and p95 deltas between transports, the spread figures, the cold
penalty, "1 of 48", "2.96 words". Check the same number reported in
`team/MEASUREMENTS.md`, `RIME_EVIDENCE.md` §4, `SUBMISSION.md`, `README.md` and
`team/START-HERE.md` still agrees across all five. One transcription error here
is worth more than a code bug, because the brief disqualifies unverified
performance numbers claimed as verified.

**3. Does any document now overclaim?** The repository was previously careful to
say the audible half was unmeasured. It now says it was measured once and the
artifact was lost. Every sentence that changed is a chance to have quietly
upgraded a hedge into a claim. Grep for anything asserting the pronunciation
layer works, and check it against `team/LISTENING_NOTES.md`, where two fixtures
scored **worse** with respelling than without. Does the mixed result survive
into every document that cites it, or does it flatten into a win somewhere?

**4. The `_unverified_` question.** `evidence/results/pronunciation/report.md`
still ships with `Audio rendered: false` and every verdict `_unverified_`,
while `team/LISTENING_NOTES.md` carries real verdicts. Two files in one
repository disagree about whether the same experiment has been scored. The
repository claims this is deliberate and explained. Decide whether the
explanation is actually adequate or whether a judge would reasonably read it as
a contradiction — and say which, plainly.

**5. The shipped artifact.** The submission is a ZIP, not a clone. Build one,
extract it somewhere with no relationship to this checkout, and follow
`README.md` literally, typing only what it tells you to type. Pass 3's
equivalent found `cd waypoint`, a directory that does not exist. Find this
pass's version of that. Check in particular that the documented virtualenv
activation works on the shell you are actually in, and that nothing in the
repository depends on being a git clone.

## Rules

- **Verify by running, not by reading.** A claim you did not execute is a
  hypothesis. Say which of your findings you ran and which you reasoned about.
- **Falsify your own findings before writing them.** Pass 3's most useful
  section was the one listing what it checked and found *sound*. Reproduce
  that: a finding that dissolves under a second look, written up as real,
  costs the next reader more than silence.
- **Rank by what it costs at judging**, not by how clever it is. An eligibility
  failure outranks everything. A number a judge can prove wrong outranks a
  design opinion. A design opinion is usually not worth writing down.
- **Do not fix anything.** Report only. The fix and the finding should come
  from different heads — that is why the previous three passes were useful.
- If you find nothing in a region, **say so explicitly and say what you did to
  look.** "I could not break X, here is how I tried" is a real result and the
  next pass needs it.
