# Red team prompt 3

> Paste everything below the line into a fresh Claude session with a machine
> and this repository. It is written to be run cold, by someone who has not
> seen the previous two reviews.

---

This project has survived two adversarial audits. Both found real, serious
defects. Your job is to find what the second one missed — and, unusually, to
audit the *fixes* it prompted.

Write your findings to `AUDIT-3.md` in the project root. That file is the
deliverable. Someone will work from it without talking to you, so it has to
stand on its own.

## Where things are

- Project: `C:\Users\darsh\OneDrive\Desktop\DataForge\waypoint`
- Brief: `C:\Users\darsh\OneDrive\Desktop\DataForge\Rime PS.pdf`.
  **Read it before you read anything this repository says about it.** The repo
  describes its own rubric compliance at length; that description is under
  audit, not evidence.
- Offline, no credentials:
  `pip install -e ".[dev]"`, then `pytest`, `python evidence/run_acceptance.py`,
  `python evidence/mutation_test.py`, `python evidence/mutation_test_ii.py`.
- The previous review is archived at `docs/audits/AUDIT-2.md`, with a header
  mapping each of its findings to the fix that followed. Read it late, not
  early — form your own view of the code first, then see whether theirs
  matches.

## What the two previous passes found, and the shape of it

So you do not spend your budget re-deriving it.

**Pass 1** found five defects, all inside `src/`. The pattern it named for
itself: *documentation and code disagreed, and the tests agreed with neither.*
Its sharpest find was a headline claim that had never been wired into the
running agent while its module tests stayed entirely green.

**Pass 2** found five more by noticing that pass 1 had only looked where tests
already existed. Everything it found lived **outside** the tested modules: four
scripts, none of which could make a single API call to the speech provider in
any configuration; a disclosed endpoint pointing at the wrong host; a ~220-line
wiring layer with no tests at all, where disabling the product's only feature
left the entire suite green.

So: pass 1 looked in the tested code. Pass 2 looked in the untested code
adjacent to it. **Both of those regions now have tests and mutation coverage.**
The interesting question is what region neither of them thought to name.

## Three things that make this pass different

**1. Audit the fixes.** Every fix to pass 2's findings was written by the same
author who wrote the bugs, immediately after being told about them, under time
pressure. That is the classic setup for a fix that satisfies the reviewer's
sentence without satisfying the requirement. Several fixes introduced new
abstractions (`evidence/_rime.py`), new invariants (`Settings.endpoint`), new
tests (`tests/test_wiring.py`, `tests/test_preflight.py`) and new allowlists
(`VENDOR_IDENTIFIERS`). Any of those can be wrong, over-fitted to the exact
mutation that prompted them, or quietly weaker than what it replaced. A test
written to kill a specific mutant is not the same as a test that specifies
behaviour.

**2. Nothing has ever run for real.** Not one second of audio has been
synthesised by this codebase. The browser console has been served and its
endpoints fetched, but no human has opened it, spoken into it, or interrupted
it. The agent has never held a session. Every claim about barge-in has been
proved against a Python attribute being flipped in a test harness. If you have
credentials — or can obtain free ones, both providers have free tiers — running
it end to end is the single highest-value thing available to you, and no
previous pass could do it.

**3. Judge whether this is the right amount of project.** Roughly 10,000 lines
of Python, 400 tests, 28 mutation targets, two mutation harnesses, thirteen
documents — and a demo video that does not exist, against a brief that lists
omitting it as a disqualifier. Previous passes asked "is this correct?" You
should also ask "is this proportionate, and what would you delete?" Effort in
the wrong place is a finding. Be willing to say that a thing the authors are
evidently proud of should be cut.

## How to work

Form your own hypotheses in the first hour and spend the rest where they point.
**Do not work through the topics in the order this document mentions them.** If
your report reads like a reply to this prompt, you audited the wrong artifact.

**Run it. Break it.** Delete a file and see whether anything notices. Feed the
fence an interleaving nobody would write. Run the suite in a different order,
on a fresh clone, with a cold cache. Both mutation harnesses report near-perfect
scores — write a mutation neither table contains and see whether it survives. A
suspiciously clean number is the best place to aim.

**Verify before you assert.** Every finding needs a command and its output, a
file and a line, or a quote from the PDF. An unverified suspicion is precisely
the failure mode you are here to catch — do not commit it yourself. Label
anything you suspect but could not confirm as unconfirmed, and say what would
confirm it. Both previous reviews did this well; match them.

**Read the brief as a scoring document, not a spec.** It has weights. A defect
that costs nothing is worth less than an omission that costs ten points, no
matter how satisfying it is to find.

## What `AUDIT-3.md` must contain

1. **Verdict.** One paragraph. A judge spends ten minutes; what happens?
2. **What pass 2 missed.** Your headline result. If the honest answer is
   "little of consequence, and here is why I believe that", say that instead —
   with the evidence that you looked properly.
3. **Are the fixes sound?** Take at least three of pass 2's fixes and try to
   defeat them. Say which held.
4. **Findings**, ordered by what they cost, each with evidence, the cost, and
   the smallest fix that actually addresses it. Mark each: disqualifying /
   overclaim a judge will catch / fails live / points lost / effort misspent.
5. **The score.** Out of 100, against the PDF's actual weights, banded, one
   paragraph of justification each. Then the single change with the best
   points-per-hour, and what you would cut to pay for it.
6. **What to delete.** Be specific and be willing to be unpopular.

## Calibration

Do not manufacture findings. If a region is genuinely sound, say so plainly and
move on — telling the team where *not* to spend their last hours is worth as
much as a bug, and this project has a real risk of being polished in the places
that already work.

Equally, do not soften anything to be agreeable. Two passes have now been
absorbed without argument; assume this one will be too. If the honest summary
is "the engineering is excellent and the submission is still going to lose
because nobody recorded a video", write that sentence.

**Four findings that are certainly real beat twenty that are mostly plausible.**

Start with the PDF. Then form your plan of attack before opening the
repository's own documentation.
