# AUDIT-5 — pre-submission audit

**Auditor:** fifth adversarial pass · **Date:** 2026-09-09
**Tree audited:** `61d2ba1`, clean working tree
**Rule followed:** report only. Nothing here was fixed by its author.

Read §0 before touching anything. Read §7 before running
`python scripts/check_docs.py --fix`, because this document is itself a trap
for that command and §7 explains why.

---

## 0. Green state — established before reading anything

All five regression-contract commands were run on `61d2ba1` with a clean
working tree, in this order, before any analysis began.

| # | Command | Result |
|---|---|---|
| 1 | `pytest` | `653 passed in 26.66s` |
| 2 | `python evidence/run_acceptance.py` | `6/6 scenarios passed (36 checks)` |
| 3 | `python scripts/secret_scan.py` | `secret_scan: clean. No credential found in the repository.` |
| 4 | `python scripts/check_docs.py` | `check_docs: clean. 7 checks passed.` |
| 5 | `python scripts/preflight.py --offline` | 7 `[PASS]`, 1 `[WARN]` (Rime shipped path, expected), `Ready, with 1 warning(s).` |

The two slow harnesses were run once, sequentially, never concurrently:

- `python evidence/mutation_test.py` → `15/15 mutants caught   (482s)`
- `python evidence/mutation_test_ii.py` → `19/19 mutants caught   (380s)`
- `git status --porcelain` after both → empty. Lock released cleanly.

**The submitted tree is not broken.** Everything below is a defect found inside
a green build.

---

## 1. FIX NOW — ranked by cost at judging

Five. Finding 5 is procedural and must be executed **last**, after any of
findings 1–4 are applied and pushed.

---

### FIX NOW 1 — `README.md:337` asserts the opposite of what this repository's own mutation harness proves

**Claim.** The README's Evidence section states that the current test suite
stays green when barge-in is disabled. `evidence/mutation_test_ii.py` target B
proves that exact mutation is caught — and the README cites that same harness
four lines later as proof the tests are load-bearing.

**Evidence.**

```
$ sed -n '333,341p' README.md
The second harness exists because the first one had a shape. All fifteen of its
targets land in code a unit test calls directly, and **9 of the first 12
mutations written against the wiring layer survived** - including
`interruption {"enabled": False}`, which disables the only feature this product
has. All 653 tests, all six acceptance scenarios and the first harness's 15/15
stayed green with barge-in switched off. `tests/test_wiring.py` and
`tests/test_preflight.py` were written to close that, and did.

Current result: **15/15 and 19/19 - 34 of 34, none surviving.** Both run in CI.
```

```
$ grep -n -A5 '"barge-in is switched off entirely"' evidence/mutation_test_ii.py
123:        "barge-in is switched off entirely",
124:        "B",
125:        "src/waypoint/agent.py",
126:        '                "enabled": True,',
127:        '                "enabled": False,',
```

```
$ python evidence/mutation_test_ii.py
  ...
  19/19 mutants caught   (380s)
```

That mutant is caught **by the suite the same sentence says stays green under
it.**

How the sentence became false — the numeral has been mechanically rewritten
five times into a statement about a fixed moment in the past:

```
$ for c in d08701 d5c6b18 2177e67 779e107 b10b90c 61d2ba1; do \
    echo "$c -> $(git show $c:README.md | grep -oE 'All [0-9]+')"; done
d08701 -> All 425
d5c6b18 -> All 609
2177e67 -> All 626
779e107 -> All 632
b10b90c -> All 653
61d2ba1 -> All 653
```

(The numeral is truncated out of the grep on purpose — the full phrase at every
one of those commits is `All <n> tests, all six acceptance scenarios`, and
printing it in full here would trip this repository's own count check. That is
finding 1 in miniature.)

`425` was true when written. Every later value is the count cascade rewriting a
historical claim into a present-tense one. `tests/test_wiring.py` — the 45
tests written *specifically* to catch this mutant — is inside today's total.

**Cost at judging.** Evidence and reproducibility, 20%. This is the paragraph
whose entire purpose is to argue the suite is load-bearing, in the section a
judge reads to decide whether to trust the test count at all. A judge who reads
it and runs the command printed nine lines below sees the repository contradict
itself. It also brushes Hard voice engineering (25%), because the sentence now
literally reads as "disabling our only feature breaks nothing."

**Minimal fix.** One file, two lines. Remove the numeral — do **not** replace it
with a different one (see Blast radius):

- `README.md:337` from
  `has. All 653 tests, all six acceptance scenarios and the first harness's 15/15`
  to
  `has. The whole suite as it stood then, all six acceptance scenarios and the`
- `README.md:338` from
  ``stayed green with barge-in switched off. `tests/test_wiring.py` and``
  to
  ``first harness's 15/15 stayed green with barge-in switched off. `tests/test_wiring.py` and``

**Blast radius.** The numeral **must be deleted, not corrected.** Any other
three-digit value followed by `tests` there fails `check_test_count`
(`_TEST_TOTAL`, `scripts/check_docs.py:414`) because `README.md` is not exempt;
and `--fix` will not repair it either, because `fix_counts` only rewrites bare
totals that appear in three or more files (`scripts/check_docs.py:785`). So a
wrong number there is a permanently red gate. Deleting the numeral is the only
stable state. `grep -rn "stayed green with barge-in"` returns `README.md` only —
no other document quotes this sentence. Of the five commands only #4
(`check_docs`) can turn red, and only if a numeral is left behind.

**Verification.**
```bash
grep -n "barge-in switched off" README.md      # proves the fix
python scripts/check_docs.py                   # proves nothing else broke
pytest && python evidence/run_acceptance.py && python scripts/secret_scan.py \
  && python scripts/preflight.py --offline
```

---

### FIX NOW 2 — the "we flag our discrepancies" paragraph has three wrong numbers and arithmetic that does not close

**Claim.** `SUBMISSION.md:55` and `DEMO_SCRIPT.md:188–193` are the two places
the submission deliberately draws a judge's eye to a number in order to
demonstrate honesty about numbers. Both give the repository's suite size as 628
(it is 653), and both say `tests/test_check_docs.py` added 36 tests (it collects
80). The stated arithmetic reaches neither figure.

**Evidence.**

<!-- check-docs: allow -- quoting SUBMISSION.md's own stale text verbatim as evidence -->
> `SUBMISSION.md:55` — "…when the suite was 573 tests, and the narration says so out loud. **It is 628 here.** The **36 new tests** are `tests/test_check_docs.py`…"

<!-- check-docs: allow -- quoting DEMO_SCRIPT.md's own stale text verbatim as evidence -->
> `DEMO_SCRIPT.md:188-190` — "It was filmed with a suite of 573 tests. … and the **repository says 628**. `tests/test_check_docs.py` added **36 tests** afterwards"

```
$ python -m pytest --collect-only -q | grep test_check_docs
tests/test_check_docs.py: 80

$ python -c "print(573+36, 573+80)"
609 653
```

The claimed pair (573, +36) yields 609 — not the claimed 628, and not the real
653. The true pair closes exactly: **573 + 80 = 653.** `RIME_EVIDENCE.md:106`
already records `test_check_docs.py` as 80, and that table is enforced by
`check_per_file_tests`, so 80 is verified ground truth rather than an inference.

Why the gate did not catch it, by two independent routes:

```
$ python -c "
import re; p=re.compile(r'\b(\d{3,})\s+(?:tests?|passed|passing)\b')
print(p.findall('It is 628 here.'), p.findall('repository says 628.'))"
[] []
```

Neither phrase has the shape `NNN tests|passed|passing`, so `_TEST_TOTAL` never
sees them. Separately, `SUBMISSION.md:54` carries a `check-docs: allow` pragma
placed to excuse the genuinely-stale `573`; because the pragma suppresses
*every* check on the line it covers and line 55 is one long line, it also
excuses the accidentally-stale `628` sitting beside it.

**Cost at judging.** Evidence and reproducibility, 20% — and the most expensive
kind of error available here. The brief says unverified numbers receive no
credit and that judges score shipped behaviour "not unsupported README claims."
`SUBMISSION.md` is the first document a judge opens. This paragraph invites
scrutiny of a number and then fails it, which retroactively discounts every
other figure in the submission — including the Rime measurements, which are
correct.

**Minimal fix.** Two files, four token replacements, no structural change:

- `SUBMISSION.md:55` — `It is 628 here.` → `It is 653 here.`
- `SUBMISSION.md:55` — `The 36 new tests are` → `The 80 new tests are`
- `DEMO_SCRIPT.md:190` — `repository says 628.` → `repository says 653.`
- `DEMO_SCRIPT.md:190` — `added 36 tests afterwards` → `added 80 tests afterwards`

Leave every `573` and both `check-docs: allow` pragmas exactly as they are — the
573 is the recorded narration and is correctly excused.

**Blast radius.** `VERIFICATION.md:15` and `:115` also say 628 and 36. **Do not
touch them.** That document is a dated fresh-clone record from 2026-09-06, when
both figures were true; it is signed by a named person and is in
`PLACEHOLDER_EXEMPT_FILES`. Rewriting a dated verification record to today's
numbers would manufacture provenance — the same error the team correctly
refused to make with `evidence/results/`. `team/WORKFLOW.md` and
`team/WHATSAPP-KICKOFF.md` also hold 628; internal, exempt, leave them. Of the
five commands only #4 can move, and only toward green.

**Verification.**
```bash
grep -n "It is 653 here\|80 new tests" SUBMISSION.md
grep -n "repository says 653\|added 80 tests" DEMO_SCRIPT.md
python scripts/check_docs.py
pytest && python evidence/run_acceptance.py && python scripts/secret_scan.py \
  && python scripts/preflight.py --offline
```

---

### FIX NOW 3 — `README.md:319` quotes a stale suite total the gate structurally cannot see

**Claim.** The README says the suite is 628 in the sentence that opens its
mutation-testing argument, while lines 24, 125, 279, 300 and 337 of the same
file say 653.

**Evidence.**
```
$ sed -n '319p' README.md
`pytest` reporting 628 passes is not evidence on its own - a suite that stays

$ python scripts/check_docs.py
check_docs: clean. 7 checks passed.

$ python -c "
import re; p=re.compile(r'\b(\d{3,})\s+(?:tests?|passed|passing)\b')
print('653 passes  ->', p.findall('653 passes'))
print('653 passing ->', p.findall('653 passing'))"
653 passes  -> []
653 passing -> ['653']
```

(Demonstrated with 653 rather than 628 so that this document does not itself
trip the check it is describing. The behaviour is identical for any value.)

The noun is `passes`. `_TEST_TOTAL` matches `test`, `tests`, `passed` and
`passing` — not `passes`. One letter is the entire reason this survived four
adversarial passes and a gate written specifically to catch it.

**Cost at judging.** Evidence and reproducibility, 20%. Lower than finding 2
only because it is not in a paragraph advertising its own accuracy. A judge
scanning the README sees 653 four times and 628 once, in the sentence
introducing the strongest evidence the project has.

**Minimal fix.** One file, one line — and change the noun so the gate guards it
from now on:

- `README.md:319` — ``` `pytest` reporting 628 passes is not evidence on its own ``` → ``` `pytest` reporting 653 passing is not evidence on its own ```

**Blast radius.** Changing `passes` → `passing` deliberately brings the line
*inside* `_TEST_TOTAL`'s coverage, so future drift here fails the build instead
of shipping. 653 matches collection, so `check_docs` stays green.
`RIME_EVIDENCE.md:260` and `HANDOFF.md:323` carry the same argument as
`"653 tests pass"` and are already correct — do not touch them. No other file
quotes this sentence. Only command #4 can move, toward green.

**Verification.**
```bash
sed -n '319p' README.md
python scripts/check_docs.py
pytest && python evidence/run_acceptance.py && python scripts/secret_scan.py \
  && python scripts/preflight.py --offline
```

---

### FIX NOW 4 — `README.md:301` understates the gate it is advertising

**Claim.** The README's Evidence table says `scripts/check_docs.py` runs 6
checks. It runs 7.

**Evidence.**
```
$ sed -n '301p' README.md
| The docs still match the repository | `python scripts/check_docs.py` | no | 6 checks |

$ python scripts/check_docs.py
check_docs: clean. 7 checks passed.

$ python scripts/check_docs.py --list | wc -l
7

$ python scripts/check_docs.py --list | awk '{print $1}'
links
placeholders
mutation_counts
clone_dir
test_count
per_file_tests
spelled_counts
```

(Only the check names are printed here; the full `--list` descriptions quote the
literal placeholder tokens the gate hunts for, and pasting them into a
root-level document trips the `placeholders` check. See §7.)

Seven names, seven checks reported. `spelled_counts` was added in `b10b90c` and
the README's count did not move with it. Nothing in `check_docs` validates its
own advertised check count — this is the only number in that table no gate
guards.

**Cost at judging.** Evidence and reproducibility, 20%, low magnitude. It is
the one row a judge can falsify in three seconds by running the command in the
adjacent cell, on a table whose entire premise is "our documentation matches our
repository."

**Minimal fix.** `README.md:301` — `| no | 6 checks |` → `| no | 7 checks |`.
One file, one line.

**Blast radius.** None. `_TEST_TOTAL` requires three digits, so neither
`6 checks` nor `7 checks` is touched by any count check; this edit cannot make
`check_docs` red. No other document states a check count for `check_docs` —
every other `N checks` hit in the tree is the acceptance harness's `36 checks`,
which is correct everywhere.

**Verification.**
```bash
sed -n '301p' README.md && python scripts/check_docs.py --list | wc -l
python scripts/check_docs.py
pytest && python evidence/run_acceptance.py && python scripts/secret_scan.py \
  && python scripts/preflight.py --offline
```

---

### FIX NOW 5 — the submission ZIP has no rebuild gate, and was wrong 28 minutes into this audit

**Claim.** The artifact judges receive is a hand-made ZIP with no script, no
check and no gate. It is correct *right now*. It was three commits stale earlier
today, pinned at exactly the commit whose CI was red — and **applying any of
findings 1–4 makes it stale again.** This is the mandatory last step, not an
optional one.

**Evidence.** The ZIP as it stood at 00:13 today:

```
$ git -C <extracted-zip> rev-parse HEAD
d7ce41385788a8bc1d11b7222ce66f087e1f539d

$ git log --oneline d7ce413..61d2ba1
61d2ba1 Add the red-team prompt to run before submitting, designed for convergence
b10b90c Check counts spelled out in words, closing the last silent-drift channel
779e107 Fix the CI break, and make the local check see what CI sees

$ cd <extracted-zip> && python scripts/check_docs.py
check_docs: PROBLEMS FOUND
  [links] evidence/results/README.md:13
      link target does not exist: acceptance.md
  [links] evidence/results/README.md:13
      link target does not exist: acceptance.json

  2 finding(s). ...
```

That ZIP was built one minute after `d7ce413` (00:12:44); the CI fix landed at
00:26:19, thirteen minutes later. A judge unzipping it and running the
documented gate got a failure, while the README badge — served from
`origin/main`, not from the ZIP — showed green. The two can disagree silently
and indefinitely.

The ZIP was rebuilt at 00:41, during this audit, and is now correct:

```
$ git -C <extracted-zip-2> rev-parse HEAD
61d2ba153a89547ab02b6c8f4268480389b3523a
$ git -C <extracted-zip-2> status --porcelain      # empty

$ cd <extracted-zip-2>
$ python -m pytest                      -> 653 passed in 28.50s
$ python evidence/run_acceptance.py     -> 6/6 scenarios passed (36 checks)
$ python scripts/secret_scan.py         -> secret_scan: clean.
$ python scripts/check_docs.py          -> check_docs: clean. 7 checks passed.
$ python scripts/preflight.py --offline -> Ready, with 1 warning(s).
```

How it is built — the reassuring part:

```
$ cat <extracted-zip-2>/.git/logs/HEAD
0000...0000 61d2ba1... clone: from https://github.com/darshanrajagoli/data-forge-rime-hadippa
```

It is a fresh `git clone` of GitHub `main`, zipped with `.git/` included. That
is clean **by construction** — it can never carry an uncommitted edit, a
gitignored artifact, or a half-restored mutation. Its only failure mode is
staleness against `origin/main`, and staleness is silent. There is no script
for it: `grep -rn "zip\|Compress-Archive" scripts/ .github/` returns nothing but
a comment in `check_docs.py`.

**Cost at judging.** Potentially the whole Evidence and reproducibility band
(20%), and the only finding here that is invisible to every local check. It is
also the exact failure mode this audit loop exists to prevent: a fix lands, the
working tree and GitHub go green, and the artifact the judge holds does not move.

**Minimal fix.** No file edit. A procedure, run **after** findings 1–4 are
committed and pushed:

```bash
# 1. push, and let the run finish (a cancelled run renders as a red badge)
# 2. rebuild from origin, never from the working tree
cd /tmp && rm -rf zipbuild && mkdir zipbuild && cd zipbuild
git clone https://github.com/darshanrajagoli/data-forge-rime-hadippa
# 3. verify BEFORE zipping
cd data-forge-rime-hadippa
git rev-parse HEAD           # must equal origin/main
git status --porcelain       # must be empty
python scripts/check_docs.py # must be clean, 7 checks
cd .. && zip -r Waypoint-DataForge2026-Rime.zip data-forge-rime-hadippa
```

**Blast radius.** None on the repository — no tracked file changes. The risk is
the reverse: skipping the step. Two cautions. `git clone` captures the current
`origin/main`, so do this *after* the push completes. And **never build the ZIP
from the working tree while a mutation harness is running** — both harnesses
hold a source file deliberately broken for the ~25 s it takes to run the suite
against each of their 34 targets, so a working-tree zip taken in that window
would ship a planted bug to the judges. The current ZIP was built at 00:41,
mid-`mutation_test_ii.py`, and escaped only because it clones from GitHub rather
than reading from disk. That is luck in the process design, not in the timing —
but do not rely on it.

**Verification.** The five commands, run inside a fresh extraction of the ZIP,
not in the working tree:
```bash
cd <fresh extraction> && pytest && python evidence/run_acceptance.py \
  && python scripts/secret_scan.py && python scripts/check_docs.py \
  && python scripts/preflight.py --offline
```

---

## 2. FIX IF TIME

### FIX IF TIME 6 — "Three adversarial audits, kept in full" links to a directory holding two

**Claim.** Three documents promise three archived audits; `docs/audits/` holds
two audit reports. The count is now also an undercount — five passes have run.

**Evidence.**
```
$ ls docs/audits/
AUDIT-2.md  AUDIT-3.md  RED-TEAM-PROMPT-3.md  RED-TEAM-PROMPT-4.md  RED-TEAM-PROMPT-5.md

$ grep -rn "adversarial audits, kept in full\|audits (3, kept in full)" --include=*.md .
./README.md:18:| **Three adversarial audits, kept in full** | [`docs/audits/`](docs/audits/) |
./SUBMISSION.md:13:| **Adversarial audits (3, kept in full)** | [`docs/audits/`](docs/audits/) |
./SUBMISSION.md:91:| Adversarial audits (3, kept in full) | [`docs/audits/`](docs/audits/) |
```

`HANDOFF.md:379` explains it — pass 1 was never written up as a file — so the
claim is defensible if a judge reads §10 of a 25 KB document first. From the
deliverables table on the README's first screen, "kept in full" reads as a
promise the directory does not keep.

**Cost at judging.** Evidence and reproducibility, small. It is the first table
a judge sees and the one row they can falsify with a single click.

**Minimal fix.** Change the wording, not the count, in three places:
`Three adversarial audits, kept in full` → `Adversarial audit reports, kept in
full` (`README.md:18`), and `Adversarial audits (3, kept in full)` →
`Adversarial audit reports, kept in full` (`SUBMISSION.md:13` and `:91`). Two
files, three lines. This sidesteps having to decide whether the true number is
2, 3, 4 or 5 hours before a deadline.

**Blast radius.** `HANDOFF.md:27` and `:379` also say "the three adversarial
audits", as a TOC entry and the heading it points at. Leaving them is fine, and
is why this is FIX IF TIME: if you change one you must change both, and
`HANDOFF.md:27` is an anchor link (`#10-the-three-adversarial-audits`) whose
target heading must change with it or the anchor dies silently — `check_docs`
does not resolve anchors (stated blind spot, `scripts/check_docs.py:60`).
**If you are short on time, skip this finding entirely.** None of the five
commands can turn red from the three-line version.

**Verification.**
```bash
grep -rn "kept in full" --include=*.md .
python scripts/check_docs.py
```

### FIX IF TIME 7 — `evidence/results/README.md` omits one of the artifacts it inventories

**Claim.** That file exists to state what is in `evidence/results/` and what
state each file is in. Its table covers `acceptance`, `latency`,
`pronunciation` and `sessions`, but not `heard_accuracy.{md,json}`, which
`evidence/measure_heard_accuracy.py` writes into the same directory and which
`RIME_EVIDENCE.md:288` names in its Artifact column.

**Evidence.**
```
$ grep -n "heard_accuracy" evidence/results/README.md
(no output)

$ grep -n "heard_accuracy" evidence/measure_heard_accuracy.py
7:Requires ``RIME_API_KEY``. Writes ``evidence/results/heard_accuracy.{json,md}``.
232:    (OUT / "heard_accuracy.json").write_text(
235:    (OUT / "heard_accuracy.md").write_text(to_markdown(payload), encoding="utf-8")

$ grep -n "heard_accuracy" RIME_EVIDENCE.md
288:| Estimator error vs word timestamps | ... | in-process | `results/heard_accuracy.md` |
```

**Cost at judging.** Very small. A judge cross-referencing RIME_EVIDENCE §4's
Artifact column against the directory's own inventory finds one row
unexplained — in the document written specifically so no such reconstruction is
needed.

**Minimal fix.** One table row in `evidence/results/README.md`, after the
`pronunciation` row, naming the files in backticks and explaining the absence
(the 2026-09-07 run was never uploaded; the numbers live in
`team/MEASUREMENTS.md`). One file, one line.

**Blast radius.** One real hazard: **write the filenames as code spans, not as
markdown links.** `check_links` requires a link target to exist *and* be
tracked; these files do not exist, so link syntax fails the gate immediately —
which is precisely the defect that broke CI in `d7ce413` and was fixed in
`779e107` by converting the `acceptance.md` links to code spans. A link to
`../../team/MEASUREMENTS.md` is fine: it exists and is tracked. Only command #4
can turn red, and only if you use link syntax on a file that does not exist.

**Verification.**
```bash
python scripts/check_docs.py    # must stay "clean. 7 checks passed."
```

---

## 3. DO NOT FIX

Eight. Each is real. In each case I judge the risk of changing it tonight higher
than the cost of leaving it.

### DNF 1 — `_TEST_TOTAL` does not match `passes`, `here`, or a bare numeral

`scripts/check_docs.py:414` is `\b(\d{3,})\s+(?:tests?|passed|passing)\b`. It
misses `628 passes` (finding 3), `It is 628 here` and `repository says 628.`
(finding 2). Widening it is the obvious repair and **it is the wrong move
tonight.** A sweep of the tracked markdown finds 132 three-digit numbers
followed by a word (`git ls-files '*.md' | xargs grep -oE "[0-9]{3,}[ -]+[A-Za-z]+"`,
excluding years), including `350` and `425` in the archived audits, `112`,
`158`, and the deliberately-stale `573`. A wider pattern turns the gate red in
files nobody has time to re-verify, in the last hours before a deadline. Fix
the four wrong sentences instead. Widen the pattern after the deadline.

### DNF 2 — `--fix` can, and already did, write a confidently wrong number

Region (d) asked whether `--fix` can ever write a *wrong* number confidently. It
can, it is not hypothetical, and finding 1 is the damage. Reproduced in
isolation against a synthetic tree shaped like this repository (628 present in
three-plus files):

<!-- check-docs: allow -- verbatim --fix reproduction output; the line is the finding -->
> `--fix` reported one change in `AUDIT-5.md:3`, rewriting `… records 628 passed, but pytest now collects 653.` into `… records 653 passed, but pytest now collects 653.` — `CORRUPTED: True`.

The mechanism is `fix_counts` at `scripts/check_docs.py:785`:
`stale_totals = {v for v, files in seen.items() if len(files) >= 3 and v != total}`.
The `seen` survey walks **every** markdown file including the exempt ones, so
`628` — present in `VERIFICATION.md`, `team/WORKFLOW.md`,
`team/WHATSAPP-KICKOFF.md` and `team/worksheets/VERIFICATION.md` — is registered
as a stale total. The rewrite pass then skips exempt paths, so nothing is
damaged **today**. But any non-exempt document that legitimately quotes
a stale total written in that shape has it silently rewritten to the current
value, and `check_docs` then
certifies the result. A root-level audit report is exactly such a document —
see §7.

**Do not change `fix_counts`.** It is eighty lines of careful reasoning, it is
covered by `tests/test_check_docs.py`, and its threshold heuristic is
defensible. Changing it hours before a deadline, in the one file whose four
previous revisions each introduced a new hole, is how the next round starts.

### DNF 3 — `PLACEHOLDER_EXEMPT_PREFIXES` is reused by three unrelated checks

`check_test_count`, `check_clone_dir` and the `fix_counts` rewrite pass all gate
on `PLACEHOLDER_EXEMPT_PREFIXES` / `PLACEHOLDER_EXEMPT_FILES`
(`scripts/check_docs.py:88-92`), a list whose docstring justifies exemption
purely on placeholder-token grounds — a bug report has to be able to name the
very tokens it is reporting. That reasoning does not transfer to
test counts. The consequence: `VERIFICATION.md` — a **root-level, judge-facing**
document — is exempt from every count check, which is why its stale `628` sits
unflagged.

DO NOT FIX, because the current behaviour is accidentally correct.
`VERIFICATION.md` is a dated record of a real run on 2026-09-06, when 628 was
true. Splitting the exemption lists would immediately turn the gate red on a
document that must not change.

### DNF 4 — `_strip_code` protects only the link check

`_strip_code` is called in `check_links` and nowhere else, so `placeholders`,
`test_count`, `clone_dir`, `mutation_counts` and `spelled_counts` all read raw
lines including fenced code. Pasting genuine tool output containing a count from
another moment therefore trips the gate as if it were a prose claim. That is
arguably correct — a stale number in a code fence still misleads — but it is why
`VERIFICATION.md` needed a whole-file exemption rather than a pragma, and it is
a constraint on this document (§7). Changing it loosens four checks at once.
Leave it.

### DNF 5 — `web/index.html:330` hardcodes the provider disclosure banner

The green `SPEECH PROVIDER: RIME — primary, no fallback configured` banner —
the thing Shot 3 of the demo points a camera at, and this repository's answer to
the brief's "make the active speech provider observable" — is a string literal
rendered unconditionally:

```
$ sed -n '330p' web/index.html
    `<div class="provider">SPEECH PROVIDER: RIME &mdash; primary, no fallback configured</div>` +
```

Every other row in that panel is derived from `/api/config`
(`web/index.html:317-327`), and `web/server.py:68` states the endpoint exists
"so the demo can show which speech provider is actually active, which the Rime
brief requires to be observable." The headline is the one line that observes
nothing. `Settings.to_dict()` (`src/waypoint/config.py:274`) has no `provider`
key to bind it to, though `pipeline.tts` is `f"rime/{model}:{speaker}"` and is
derived.

Leave it, for three reasons. It is not false — Rime is the only TTS in the
codebase and `rime_model` is a `Literal`, so no reachable configuration makes
that banner wrong. A proper fix touches `web/server.py`, `web/index.html` and
wants a new key in `to_dict()`: three files, one of them tested and
mutation-covered. And `web/` has **zero test and zero mutation coverage** —
`grep -rn "web/" tests/ evidence/mutation_test*.py` returns a single comment —
so a change there is unverifiable by the regression contract. This is the right
thing to fix first *after* the deadline and the wrong thing to touch before it.

### DNF 6 — `cove` on `mistv2` (unverified hypothesis, labelled as such)

**This is a hypothesis. I did not confirm it.** `src/waypoint/config.py:393`
defaults the speaker to `cove` for the mist models, and
`team/LISTENING_NOTES.md` reports that arm as `mistv2/cove`. Rime's published
voices page, read through a summarising fetch, described `cove` as a Mist **v3**
voice and did not list it for v2; a second fetch of the models page was
inconclusive, and I did not query the live catalog endpoint.

Against my hypothesis: `SUBMISSION.md:145` states that `mistv2`/`cove`/`eng`
"synthesised successfully against live Rime on 2026-09-07," which is direct
first-hand evidence and outranks my reading of a docs page. It also does not
touch eligibility — the brief disqualifies a combination "used in the demo"
that fails preflight, and the demo ships `coda`/`lyra`/`eng`, which I did
confirm is valid (`lyra` is listed as a Coda voice in the live catalog docs).
Leave it. If someone has a key and five spare minutes,
`RIME_MODEL=mistv2 python scripts/preflight.py` settles it — but do not let it
block submission.

### DNF 7 — the ZIP ships `.git/`, including full history and the red-team prompts

The submission carries `.git/` with all 26 commits, so a judge can read
`git log` — including `Fix the CI break` and `Close two holes that
RED-TEAM-PROMPT-4 found in check_docs.py itself` — plus three red-team prompts
under `docs/audits/`. I checked whether this leaks anything disqualifying. It
does not:

```
$ git grep -I -nE "(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16})" $(git rev-list --all)
  -> only tests/test_secret_scan.py fixtures: "AKIAIOSFODNN7EXAMPLE", "AKIAZZZZQQQQWWWWEEE1"

$ git grep -I -nE "RIME_API_KEY\s*[=:]\s*['\"]?[A-Za-z0-9_-]{16,}" $(git rev-list --all)
  -> only placeholders: "your-rime-api-key", "xxxxxxxxxxxxxxxxxxxxxxxx", "rk_dummy_key_for_audit"

$ cat <extracted-zip>/.git/config
  -> plain https remote, no embedded token
```

No live credential in any blob in any commit, across all 26 commits and 359
objects. The eligibility rule "exposes a live credential or other secret" is not
touched. Whether shipping the history helps or hurts is a judgement call; I read
it as provenance in a submission whose whole argument is checkability. Leave it —
stripping `.git/` would also remove what makes `check_docs`'s `git ls-files`
cross-reference work inside the ZIP (DNF 8).

### DNF 8 — `_tracked()` returns empty outside a git repo, and that is the right behaviour

Region (d) asked what `check_docs` does on a repository with no `.git`.
`_tracked` (`scripts/check_docs.py:186`) returns an empty frozenset when
`git ls-files` fails, and `check_links` guards with
`elif tracked and not _is_tracked(...)` — so the committed-ness half of the link
check degrades to existence-only. That is a fail-open, and it is **correct**: in
an extracted ZIP with no history, whatever exists is exactly what the judge has,
so existence is the only meaningful test. Because this ZIP *does* ship `.git/`,
the strict check runs anyway — which is how I confirmed the stale ZIP was broken.

One residual edge, not worth acting on: if a judge extracts a `.git`-less ZIP
*inside* another git repository, `git ls-files` succeeds and returns the outer
repo's files, and every link is reported untracked — a noisy fail-closed. Low
probability, harmless direction, and the current ZIP is immune because it
carries its own `.git`.

---

## 4. What I checked and found sound

Recorded so pass 6 does not spend its budget here.

**The numbers (region b) — verified, no defect.** I recomputed every derived
figure in `team/MEASUREMENTS.md` from its own tables and cross-checked each
against `RIME_EVIDENCE.md` §4, `SUBMISSION.md:63-66`, `README.md:311` and
`team/START-HERE.md:128`:

| Derived claim | Arithmetic | Agrees across |
|---|---|---|
| WS 14.5 ms faster at p50 | 408.86 − 394.35 = 14.51 | MEASUREMENTS, RIME_EVIDENCE, SUBMISSION |
| WS 47.3 ms faster at p95 | 477.19 − 429.93 = 47.26 | MEASUREMENTS, RIME_EVIDENCE |
| WS warm spread 52 ms | 432.17 − 379.99 = 52.18 | MEASUREMENTS, RIME_EVIDENCE, SUBMISSION |
| HTTP warm spread 175 ms | 569.72 − 395.04 = 174.68 | MEASUREMENTS, RIME_EVIDENCE, SUBMISSION |
| Cold penalty 120.5 ms slower | 1346.12 − 1225.63 = 120.49 | MEASUREMENTS, RIME_EVIDENCE |
| Headline 394 ms p50 | 394.35 rounded | README, START-HERE |
| `2.96 words`, `1 of 48`, `n=20`, `n=1` | verbatim | MEASUREMENTS, RIME_EVIDENCE, SUBMISSION |

Every raw table row is identical between `team/MEASUREMENTS.md:35-38` and
`RIME_EVIDENCE.md:312-315`. Every derived figure rounds correctly from the table
it cites. Cold and warm are labelled and never averaged anywhere.
`server_first_frame` is named as the boundary — and explicitly named as *not*
the driver's ear — in all four documents. **I could not find a transcription
error.** This region is clean.

**Overclaiming (region c) — verified, no defect.** The mixed pronunciation
result survives intact in all eight places it is cited:
`team/LISTENING_NOTES.md` (both findings, pointing in opposite directions),
`docs/LISTENING_TEST.md:54-58`, `RIME_EVIDENCE.md:340-345`, `SUBMISSION.md:71`,
`README.md` limitation 4, `HANDOFF.md:363-364`, `team/START-HERE.md:132-138`
and `evidence/results/README.md:37`. Every one keeps **both** halves:
load-bearing for gate codes on `mistv2`, and a net negative for street names on
`coda`. Nowhere has it flattened into a win. The "measured once, artifact lost"
story is stated with its provenance weakness in all four places it appears, and
`evidence/results/` still holds the two `401`s and the `_unverified_` rows
rather than a manufactured replacement.

**Eligibility — all six disqualifiers checked, none triggered.**

- Verifiable Rime integration: `build_tts()`, `livekit-plugins-rime==1.7.1` pinned.
- Not incidental: only TTS; word timestamps are a functional dependency of claim (c).
- Working product path: `python -m waypoint.agent console`.
- Demo present and reachable — I resolved it rather than trusting the link.
  `GET https://www.youtube.com/oembed?url=https://youtu.be/EChOFjIuyNM` returns
  `{"title": "waypoint demo final", "author_name": "Arrya Sridhar", …}`. A
  private or removed video returns an error here. 4:30 is under the 5:00 cap.
- No live credential: `secret_scan` clean, plus the full-history sweep in DNF 7.
- Model / voice / language: `coda`/`lyra`/`eng`. I confirmed against Rime's live
  voices documentation that `lyra` is a valid Coda voice, so the shipped and
  demonstrated combination is current-catalog. `.env.example` is 69 lines and
  every value in it is a placeholder.

**The repository and CI — green, and I checked the badge itself rather than the
claim about it.** `origin/main` is `61d2ba1`; the repository is public;
`GET …/ci.yml/badge.svg` contains the literal text `passing`. GitHub's side is
healthy and the badge is not a cancelled run rendering red.

**The reference acceptance run — the reproducibility claim holds exactly.**
`evidence/results/README.md` promises a fresh run differs from
`evidence/reference-run/acceptance.md` "only in the timestamp, the commit and
the sub-millisecond timings":

```
$ diff evidence/reference-run/acceptance.md evidence/results/acceptance.md
3,4c3,4   <  Run at: 2026-09-08T23:44:38+0530  /  Commit: d5c6b18
          >  Run at: 2026-09-09T00:37:31+0530  /  Commit: 61d2ba1
81c81     <  ...costing about 411ms.        >  ...costing about 406ms.
83c83     <  0.004ms in-process, against a 411ms round trip.
          >  0.003ms in-process, against a 406ms round trip.
```

Four lines, all three permitted categories, every verdict identical. The claim
is precisely true.

**Per-file test table — correct and self-consistent.** `RIME_EVIDENCE.md:102-114`
sums to exactly 653 (158+112+63+45+80+34+29+28+27+22+22+22+11), verified by hand
and enforced by `check_per_file_tests`.

**Where I looked and found nothing.** I attacked `web/index.html` (692 lines) on
the theory that the demo console was the region no previous pass had reason to
examine: it has no tests, no mutation targets, and it is what the camera points
at. I grepped it for `fake|simulat|mock|placeholder|Math.random`-driven data and
read the measurement and fence-board paths. **The console measures real audio
and renders real configuration; nothing is faked.** The only defect there is the
hardcoded banner (DNF 5). That is a real result: the demo shows what it claims
to show.

I also could not break the `check-docs: allow` pragma. It covers its own line
and the next, `_exempt_lines` is exact, and both live instances
(`DEMO_SCRIPT.md:187`, `SUBMISSION.md:54`) are correctly placed. Its one
weakness — suppressing *every* check on a long line, which is how `628` rode
along beside `573` — is documented in the source at line 109 and is a
consequence of the design rather than a bug in it.

---

## 5. The most important thing you are missing

Not a defect. The four passes before me, and this one, have all been auditing
the same 20% of the rubric.

**Your evidence apparatus is now stronger than your product argument, and the
rubric does not reward it in that proportion.** Evidence and reproducibility is
20%. Against it you have two mutation harnesses, a documentation gate with 80
tests of its own, five red-team passes, an archived audit trail and an
independent fresh-clone verification. Meanwhile Problem and necessity of voice
(25%) and Rime integration and voice experience (20%) — 45% together — rest on
assertions that no apparatus checks.

Two things I would spend remaining attention on, in order.

**1. Your shipped default contradicts your own measurement, and you noticed and
then did not act on it.** `WAYPOINT_PRONUNCIATION=respell` is the default, the
demo runs `coda`, and `team/LISTENING_NOTES.md` says in your own words: "On this
model the respelling layer is a **net negative** for street names." You then
write, correctly, "the measurement says one is worth building" — and ship the
default your measurement argues against. A judge in the Rime integration and
voice experience band may reasonably ask why. Your answer in `README.md` is
portability, which is an engineering answer to a voice-experience question.

Your data points at a specific, small policy: **respell numeric tokens on every
model; respell lexicon street names only where plain text is known to fail.**
That is the conclusion your own evidence supports, and it would turn your most
uncomfortable result into your strongest product decision.

I am **not** telling you to build it tonight. `pronounce.py` carries 63 tests
and mutation target 13, and this audit exists to stop new code landing before a
deadline. But you can capture the reasoning for free: one paragraph in the
README's Coda/Mist section saying the measurement points at a per-model policy,
that you scoped it, and that you declined to ship it on one listener's evidence.
That converts "they ignored their own data" into "they read their own data and
drew a bounded conclusion" — the more impressive posture, at the cost of prose
only.

**2. Nobody outside the four of you has heard this product, and the 25% band is
about a user.** Your listening test has one listener, who built the thing and
knew what each clip was supposed to say. You say so, which is to your credit.
The necessity-of-voice argument — a driver legally cannot use a screen — is
asserted in the README and never tested against a person.
`team/LISTENING_NOTES.md` calls the outside-listener gap out under "Outside
listener: None," and it was never closed. One driver, or one person who has
never seen the lexicon scoring the `none` arm, is worth more to the 25% and 20%
bands than any further hardening of the 20% band you have already saturated.

**A third, smaller point about volume.** Your repository root holds six markdown
files totalling roughly 120 KB, plus `docs/` and `team/`; `README.md` alone is
30 KB and `RIME_EVIDENCE.md` is 32 KB. A judge has minutes. The brief says they
score shipped code and demonstrated behaviour, "not unsupported README claims" —
past a certain length a README stops being evidence and becomes something to
skim. You are also shipping three red-team prompts inside the submission, which
reads as rigour to a generous judge and as anxiety to a tired one. I would not
delete anything this close to the deadline. But if you are editing the README
anyway for findings 1, 3 and 4, check that its first screen still puts the fence
and the demo above the audit apparatus. It currently does. Keep it that way.

---

## 6. Where the framing steered wrong

The prompt pointed at `scripts/check_docs.py` as the newest and most suspect
code, and at the measurements as the likeliest transcription failure. Both were
reasonable and both were mostly wrong for this pass: the numbers are clean (§4),
and `check_docs` is sound — its holes let *documents* drift, they do not
misreport.

The defect that mattered most came from the opposite direction. It was not
introduced by a person writing a wrong number. It was introduced **by the
convergence machinery itself.** `--fix` exists to stop a count cascade turning
into thirty hand edits per round, and it does that. It also, silently and five
times over, rewrote a sentence describing a fixed historical event into a claim
about the present — and `check_docs` then certified the result as correct,
because the number matched collection.

So the region no pass had reason to look at was not a module. It was **the
automated fixer's blind spot: a number that is true as a fact about the past and
false as a claim about the present.** A gate that checks numbers against current
reality cannot tell those apart, and an auto-fixer that rewrites them makes it
worse the more reliably it runs. That is worth a sentence in `check_docs.py`'s
docstring after the deadline, and it is why finding 1 is ranked first.

The prompt's instruction to treat DO NOT FIX as a first-class result was right,
and §3 is the longest section here because of it.

---

## 7. Constraint this document places on the applier — read before running `--fix`

`AUDIT-5.md` sits in the repository root, which is **not** in
`PLACEHOLDER_EXEMPT_PREFIXES`. Three consequences.

1. **This file is inside the gate, and the gate caught it.** It is scanned by
   `links`, `placeholders`, `test_count`, `clone_dir` and `spelled_counts`. The
   first draft of this document failed all of that with **18 findings** — six
   `placeholders` hits from quoting the literal blank-tokens the gate hunts for,
   and twelve `test_count` hits from quoting `425`, `609`, `626`, `632` and
   `628` as evidence. It was rewritten until clean: every stale count now either
   carries a `check-docs: allow` pragma on the line above or is phrased so
   `_TEST_TOTAL` cannot match it, and no blank-token appears literally.
   Verified:
   `python scripts/check_docs.py` → `clean. 7 checks passed.` **with this file
   present in the root.**

   That first failure is worth recording as a result in its own right: it is
   direct evidence that **pass 4's fix is real.** The hole pass 4 found was an
   allowlist that silently excused any document added later; the inverted,
   fail-closed version caught a brand-new root-level document on its first run,
   with no configuration. That check is doing its job.

   It is also the practical constraint on anyone writing the next audit: a
   document whose job is to quote wrong numbers cannot live at the repository
   root without pragmas. Point 3 below is the cheaper route.

2. **Do not run `python scripts/check_docs.py --fix` while this file is in the
   root**, unless you re-read it afterwards. `628` is registered as a stale
   total (DNF 2), so any unpragma'd stale total written in that shape would be
   rewritten to the current value — corrupting quoted evidence into nonsense — and
   the checker would then report clean. The pragmas prevent it, but the safe
   move is simpler: apply findings 1–4 by hand. **None of them changes the
   number of tests**, so `--fix` is not needed at all this round.

3. If you would rather not carry the risk, move this file to
   `docs/audits/AUDIT-5.md`, which is exempt from every check above. Nothing
   links to it from anywhere, so moving it breaks nothing.

**No finding in this audit changes the test count.** The count cascade is not in
play. Do not run `--fix`.

---

## Verdict

**1. The five green-state commands.** All five passed, on `61d2ba1` with a clean
tree, before any analysis:

```
pytest                                -> 653 passed in 26.66s
python evidence/run_acceptance.py     -> 6/6 scenarios passed (36 checks)
python scripts/secret_scan.py         -> secret_scan: clean. No credential found in the repository.
python scripts/check_docs.py          -> check_docs: clean. 7 checks passed.
python scripts/preflight.py --offline -> 7 [PASS], 1 [WARN] (Rime shipped path, expected)
                                         Ready, with 1 warning(s).
```

Both mutation harnesses also passed — 15/15 and 19/19 — leaving a clean tree.
The same five commands were then run inside a fresh extraction of the current
submission ZIP, and all five passed there too.

**2. Is this safe to submit as it stands today? Yes.**

No eligibility rule is touched. No measurement is wrong. No claim is
unsupported. The demo resolves, the repository is public, CI is green, and the
ZIP a judge would download right now is at `HEAD` and passes all five commands.
Submitting without changing a line costs a small amount of credit in the 20%
evidence band to four stale numbers, and nothing else.

The four documentation fixes are worth about twenty minutes and I would make
them — findings 1 and 2 especially, because they are self-contradictions inside
the evidence sections rather than mere staleness. **But if you make them,
finding 5 becomes mandatory: rebuild the ZIP from `origin/main` after the push,
and verify it before uploading.** A fixed repository with a stale ZIP is
strictly worse than the unfixed state you have now, because it is the one
failure your local checks cannot see. If you cannot do both, do neither and
submit what you have.

**3. If you fixed nothing and submitted right now, the single worst thing a
judge would notice:**

The one paragraph in `SUBMISSION.md` that exists to prove you are scrupulous
about numbers gets its own numbers wrong — it says the suite is 628 when every
other line says 653, and its arithmetic, 573 + 36, reaches neither figure.
