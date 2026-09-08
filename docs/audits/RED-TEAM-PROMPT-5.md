# Red team prompt 5 — the one to run before submitting

> **This is the current prompt.** Paste everything below the line into a fresh
> Claude Code session opened on this repository. Prompts 3 and 4 are kept for
> the record; 4 was run by the author against their own work, which is the weak
> form, and its findings are already fixed.
>
> It is written for **convergence**: the submission is nearly final, so the
> goal is one audit whose findings can be applied without starting a new cycle
> of breakage. Read the "Convergence contract" section carefully — it is the
> part that makes this different from a normal review.

---

You are auditing a hackathon submission that is due imminently. It has survived
four adversarial passes. Your job is to find what would cost marks or
eligibility **at judging**, and to report it so precisely that fixing it cannot
start a new cycle of breakage.

Write your findings to `AUDIT-5.md` in the project root. That file is the
deliverable. The person or model applying your fixes will not be able to ask
you anything, so it has to stand alone.

## 0. Establish the green state — do this first, before reading anything

```bash
pip install -e ".[dev]"

pytest                                  # expect: 653 passed
python evidence/run_acceptance.py       # expect: 6/6 scenarios passed (36 checks)
python scripts/secret_scan.py           # expect: clean
python scripts/check_docs.py            # expect: clean, 7 checks passed
python scripts/preflight.py --offline   # expect: PASS, 1 expected WARN
```

Record the actual output of each. **These five commands are the regression
contract.** Every finding you write must state which of them would still pass
after your fix is applied. If you cannot get all five green *before* you start,
stop and report that as finding number one — it means the submitted tree is
already broken and nothing else matters.

Two slower ones, worth running once in the background while you read:

```bash
python evidence/mutation_test.py        # expect: 15/15 caught, ~8 min
python evidence/mutation_test_ii.py     # expect: 19/19 caught, ~6 min
```

**Never run those two at the same time.** They edit source in place, they take
a lock, and a killed run leaves a mutated tree. If you see a dirty tree, run
either with `--repair`.

## 1. The convergence contract — the part that matters most

The problem with this loop is not finding defects. It is that fixes introduce
new defects, and each round costs a re-verification the deadline cannot afford.
This has already happened here: a fix added a documentation file, that file
linked to a generated artifact that is gitignored, and CI went red on every
matrix cell.

So every finding you write **must** carry all six of these. A finding missing
any of them is not actionable and you should either complete it or drop it:

| Field | What it must contain |
|---|---|
| **Claim** | One sentence. What is wrong. |
| **Evidence** | The exact command you ran and its output. Not a description of what you think would happen. |
| **Cost at judging** | Which scoring band or eligibility rule this touches, and what a judge would actually see. |
| **Minimal fix** | The smallest change that resolves it. Name files and lines. If the fix is more than ~20 lines or touches more than 3 files, say so explicitly — that is a signal it should be classified DO NOT FIX. |
| **Blast radius** | What else could break. Which of the five green-state commands could turn red. Which documents quote the thing you are changing. |
| **Verification** | The exact command that proves the fix worked, *and* the command that proves nothing else broke. Usually the five above. |

Then classify every finding as exactly one of:

- **FIX NOW** — costs marks or eligibility, and the fix is small and contained.
- **FIX IF TIME** — real but minor, and the fix is safe. The applier may skip it.
- **DO NOT FIX** — you believe the risk of changing it now exceeds the cost of
  leaving it. Say so and explain. **This classification is encouraged.** A
  correct "leave this alone" is worth more to this submission than a marginal
  improvement that breaks a green build the night before a deadline.

Rank FIX NOW findings by cost at judging, highest first.

## 2. Where things are

- Brief: `Rime PS.pdf`, one directory above the repository. **Read it before
  you read anything this repository says about it.** The repo describes its own
  rubric compliance at length; that description is under audit, not evidence.
- Start with `HANDOFF.md` for what the project is, `RIME_EVIDENCE.md` for what
  it claims, `SUBMISSION.md` for what is being submitted.
- Previous reviews: `docs/audits/AUDIT-2.md`, `AUDIT-3.md`. Read them late —
  form your own view first, then see whether theirs matches.

## 3. What the previous passes found, so you do not re-derive it

- **Pass 1** looked in the tested code: documentation and code disagreed, and
  the tests agreed with neither.
- **Pass 2** looked in the untested code beside it: four scripts that could not
  make a single call to the speech provider, a disclosed endpoint pointing at
  the wrong host, a wiring layer where disabling the product's only feature
  left the whole suite green.
- **Pass 3** asked who tests the thing that manufactures the proof, and found
  one token that made all 36 acceptance checks vacuous while every other job
  stayed green.
- **Pass 4** attacked `scripts/check_docs.py`, the gate added after pass 3, and
  found it failed **open** in three separate ways: a placeholder allowlist that
  silently excused any document added later, a completeness rule that let a
  table omit two files, and a file glob that could not see `evidence/` at all.
  It also found the mixed pronunciation result had flattened into a success in
  three documents.

Each pass found the region its predecessor had no reason to look at. **Keep
that habit and drop their targets** — those regions now have tests and mutation
coverage.

## 4. Suggested regions, in rough order of expected yield

You are not required to use these. If you see a better line of attack, take it
and say why.

**a. The gap between the working tree and what a judge receives.** This is
where the last real break came from, and it is structurally the easiest place
to be wrong, because every local check passes. The submission is a **ZIP**, not
a clone. Build one, extract it somewhere unrelated, and work only from there:

```bash
git clone <this repo> /tmp/judge && cd /tmp/judge
```

Then follow `README.md` literally, typing only what it tells you to type. Pass
3's version of this found `cd waypoint`, a directory that does not exist.
Check: does anything depend on files that are gitignored? on being a git clone?
on a virtualenv that already exists? Does the documented activation command
work in the shell you are actually in?

**b. The numbers.** No committed artifact backs the Rime measurements — the
repository says so, repeatedly and deliberately. That makes arithmetic the only
available check. Verify every derived figure against the tables in
`team/MEASUREMENTS.md`: the p50 and p95 deltas between transports, the spread
figures, the cold penalty, "1 of 48", "2.96 words". Confirm the same number
agrees across `RIME_EVIDENCE.md` §4, `SUBMISSION.md`, `README.md` and
`team/START-HERE.md`. One transcription error here outweighs any code defect,
because the brief disqualifies unverified performance numbers claimed as
verified.

**c. Overclaiming.** The repository was careful to say the audible half was
unmeasured. It now says it was measured once and the artifact was lost. Every
sentence that changed is a chance to have upgraded a hedge into a claim. The
pronunciation result is genuinely mixed — respelling is load-bearing for gate
codes on `mistv2` and a *net negative* for street names on `coda`. Check that
both halves survive everywhere they are cited, and that nothing has quietly
become a win.

**d. The gate, again.** `scripts/check_docs.py` grew four times under deadline
pressure and is the newest code here. Pass 4 found three fail-open holes; there
is no reason to think it found the last one. Look at `_exempt_lines`, the
`check-docs: allow` pragma, `_strip_code`, the `_is_tracked` git lookup, and
`fix_counts` — especially whether `--fix` can ever write a *wrong* number
confidently. Ask what it does on a repository with no `.git`, and whether that
is the right behaviour for a ZIP.

**e. Anything you think the previous four passes were wrong about.** Including
this prompt. If the framing here is steering you away from something, say so.

## 5. Do not touch

Not because they are perfect, but because they are verified and the deadline is
real. If you believe one of these is wrong, write it up as a finding with
evidence — do not change it.

- `src/waypoint/fencing.py` and the fence semantics. 112 tests and 34 mutants.
- The six acceptance scenarios and their pass criteria.
- The committed failed artifacts in `evidence/results/` (`latency.md` with its
  two `401`s, the pronunciation report with `Audio rendered: false`). They are
  deliberate. Replacing them with hand-written files would manufacture a
  provenance they do not have.
- `.github/workflows/ci.yml` job structure.
- The demo video and its narration. It is recorded and cannot be re-cut.

## 6. Traps that have already cost a round

- **The count cascade.** The suite size is quoted across eleven files, a
  per-file table, and a narration spelled out in words. All of it is enforced.
  **If your fix changes the number of tests, run `python scripts/check_docs.py
  --fix` and commit what it rewrites.** Do not hand-edit these and do not
  report the cascade itself as a finding — it is a solved problem.
- **The working tree lies.** `check_docs` cross-references `git ls-files` now,
  but assume there are other places where your machine has something a fresh
  clone does not.
- **CI cancels in progress.** Pushing several commits quickly cancels the
  earlier runs, and a cancelled run renders as a red badge. Before concluding
  CI is broken, check whether the run was cancelled rather than failed.
- **The mutation harnesses rewrite source.** Never run both at once. Never
  commit while one is running.
- **`check-docs: allow`** exists for numbers that are deliberately stale, like
  the recorded narration's 573. It covers its own line and the next one only.

## 7. Rules

- **Verify by running, not by reading.** A claim you did not execute is a
  hypothesis, and you must label it as one.
- **Falsify your own findings before writing them.** A finding that dissolves
  under a second look costs the next reader more than silence would have.
- **Do not fix anything.** Report only. The fix and the finding coming from
  different heads is the entire value of this exercise.
- **Cap yourself at eight FIX NOW findings.** If you have more, you are
  reporting noise; re-rank and cut. There is no cap on DO NOT FIX.
- **Say what you checked and found sound.** Pass 3's most useful section was
  that one. It tells the next pass where not to look.
- **If you find nothing in a region, say so and say how you looked.** "I could
  not break X, here is what I tried" is a real result.

## 8. How to end

Finish `AUDIT-5.md` with a section titled **Verdict**, containing exactly:

1. Whether the five green-state commands passed for you, with their output.
2. Whether, in your judgement, this submission is safe to submit **as it stands
   today** — yes or no, and if no, the shortest list of FIX NOW findings that
   changes the answer to yes.
3. A one-line answer to: if you had to leave every finding unfixed and submit
   right now, what is the single worst thing a judge would notice?

That third question is the one that matters. Answer it plainly.
