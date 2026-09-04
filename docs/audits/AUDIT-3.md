> **STATUS: every finding below that could be fixed in code has been fixed.**
> Two could not be, and they are not defects — they are work that needs a
> microphone, a Rime key and a human. They are listed as open at the bottom of
> this header and tracked in [`team/WORKFLOW.md`](../../team/WORKFLOW.md).
>
> This file is kept as a record of the review, not as a list of open defects.
> It was written by an independent adversarial pass against commit `8a1daeb`,
> and it is unusually good: it found the region the two previous passes had
> both walked past, and it defeated two of the fixes the previous pass had
> prompted.
>
> **Fixed in code:**
>
> | Finding | Fix |
> |---|---|
> | **N2** The acceptance harness could not fail — `evidence/` at 0% coverage, 0 mutation targets | `tests/test_acceptance_harness.py` (27 tests); `Scenario.passed` is no longer true for an empty scenario; `audit_run()` + `EXPECTED_SHAPE` make the shape of the run an assertion; 5 new mutation targets in group **E**, all caught |
> | **N4** `agent.py` wrote session evidence to a CWD-relative path | `session_evidence_dir()` resolves from `__file__` like every other path in the repo; `WAYPOINT_EVIDENCE_DIR` override; the path is logged *before* the session starts, and the write failure is no longer quiet |
> | **N5** No git remote; `REPLACE-ME` in the README badge | pushed to GitHub; the badge points at the real workflow |
> | **N6** Three documents shipped as unfilled `TODO` worksheets | moved out of the judged surface into `team/worksheets/` and reheaded as worksheets |
> | **N7** Internal team-process documents shipped to judges | `WORKFLOW.md` removed from the root; all team material now lives under `team/` |
> | **F10** *(defeated AUDIT-2 fix)* The allowlist **did** reduce detection — `re.search` returns only the first match, so `continue` skipped the whole rule and a real key sharing a line with `APIStatusError` was never seen | `finditer`, skipping only the allowlisted match; 68 new tests asserting position-independence in both directions; a mutation target that restores the bug |
> | **F2** *(defeated AUDIT-2 fix)* `Settings` did not model the plugin's scheme-based transport upgrade, so a `wss://` override disclosed HTTP **and** silently declined word timestamps that were already arriving | `Settings.effective_use_websocket`; every transport-derived field keys off it; `use_tts_aligned_transcript` fixed; the endpoint now carries the plugin's `/ws3`; the warning no longer describes a degradation that is not happening; 32 tests over the full flag × override cross-product, checked against the installed plugin |
>
> **Also fixed — found while fixing the above, not in the review:**
>
> | Defect | |
> |---|---|
> | A scenario that recorded **no checks** rendered as PASS — `all([])` is True | second vacuity path |
> | A **dropped scenario** reported `5/5 passed`, exit 0; an empty run reported `0/0`, exit 0 | third vacuity path |
> | `RIME_USE_WEBSOCKET=true` with an `http(s)://` override silently produced a WebSocket handshake against an HTTP path | now a startup warning |
> | An overridden `RIME_BASE_URL` disclosed the bare host while the socket was opened against `<host>/ws3` | the endpoint now matches what is called |
>
> **Open, and not fixable in code — this is the honest part:**
>
> | Finding | Why it is still open |
> |---|---|
> | **N1** There is no demo video | Needs a person, a microphone and five minutes. It is a stated eligibility requirement, and it is worth more than everything else in this table combined. [`DEMO_SCRIPT.md`](../../DEMO_SCRIPT.md) is written and ready to shoot. |
> | **N3** Not one second of audio has ever been synthesised | Needs a Rime API key. Two commands, both already written and — since AUDIT-2's F1 — actually callable. Disclosed as limitations 10 and 11 in [`RIME_EVIDENCE.md`](../../RIME_EVIDENCE.md). |
>
> The review scores the repository **65/100, ineligible** as it stood, and
> estimates the demo alone at +10 directly and +8 to +12 across the two 25%
> bands. We agree with that arithmetic, which is why it is the only thing in
> `team/WORKFLOW.md` marked as blocking.

---

# AUDIT-3 — third adversarial pass

Audited: `C:\Users\darsh\OneDrive\Desktop\DataForge\waypoint`, 2026-09-04, at
commit `8a1daeb`.
Rubric source: `Rime PS.pdf`, read before any document in this repository.
Method: offline execution on Python 3.12.0. `pip install -e ".[dev]"`, then
everything below was **run**, not read. Rime's live catalog was checked over
the network. No Rime or LiveKit credentials were available, so every finding
here is reproducible **without keys** unless marked otherwise.

No file in this repository was modified. Two files were temporarily mutated to
run the experiment in §2 and restored byte-exactly from backup; `git diff` is
empty and the SHA-256 of `evidence/run_acceptance.py` matches its
pre-experiment value (`7ebb9250…45a617`). The repository was left green.

Findings are ordered by what they cost. **N1 is the only one that can end the
submission**; N2 is the one that should change how you feel about your own
evidence. Five of the fixes prompted by pass 2 were attacked directly: three
held, two did not.

---

## 1. Verdict

A judge who spends ten minutes here will be impressed by the engineering, will
find nothing to watch, and will stop. `demo/` contains one empty `.gitkeep` and
there is not a single audio or video file anywhere in the repository — and the
brief lists "Omits the required demo" as an eligibility failure, not a
deduction. Everything else in this report is worth less than that one sentence.
Below the demo problem, the offline half of this submission remains genuinely
strong: 425 tests, 97–100% coverage across the six core modules, six acceptance
scenarios, two mutation harnesses, and — unusually — committed artifacts that
label themselves honestly (`audio_rendered: false`, every listening verdict
`_unverified_`, the latency run publishing its own two `401`s and an empty
results table rather than a number). That discipline is rare and it should not
be undersold. But the machinery that produces those artifacts has never itself
been tested: `evidence/` sits at **0% coverage with zero mutation targets**, and
I was able to make the acceptance harness report `6/6 PASS` on a codebase whose
headline safety property I had deliberately inverted. The engineering is real.
The proof that the engineering works is one layer thinner than this repository
believes.

---

## 2. What pass 2 missed

**Pass 1 looked in the tested code. Pass 2 looked in the untested code adjacent
to it. Neither looked at the code that manufactures the evidence.**

Both earlier regions are now covered. `scripts/preflight.py` and
`scripts/secret_scan.py` picked up tests and mutation targets; the wiring layer
got `tests/test_wiring.py`. The region that got neither is `evidence/` — the
directory whose output *is* the 20% "Evidence and reproducibility" score.

Measured, not asserted:

```
$ python -m coverage run --source=src/waypoint,web,scripts,evidence -m pytest -q
$ python -m coverage report --sort=cover

Name                                 Stmts   Miss  Cover
evidence\measure_heard_accuracy.py      97     97     0%
evidence\measure_latency.py            103    103     0%
evidence\measure_pronunciation.py      140    140     0%
evidence\mutation_test.py              145    145     0%
evidence\mutation_test_ii.py           167    167     0%
evidence\run_acceptance.py             241    241     0%
web\server.py                           60     60     0%
scripts\preflight.py                   169    104    38%
evidence\_rime.py                       87     48    45%
scripts\secret_scan.py                 132     46    65%
src\waypoint\agent.py                  320    100    69%
src\waypoint\dispatch.py               149      5    97%
src\waypoint\fencing.py                219      7    97%
src\waypoint\heard.py                  138      2    99%
src\waypoint\config.py                 142      1    99%
src\waypoint\pronounce.py              151      1    99%
src\waypoint\metrics.py                118      0   100%
```

The mutation tables confirm the same shape. `mutation_test.py` has 15 targets,
every one in `src/waypoint/`. `mutation_test_ii.py` has 13, in `src/waypoint/`
and `scripts/`. **Neither table contains a single target in `evidence/` or
`web/`.** The 28/28 score is real, and it is a statement about `src/` and
`scripts/` only.

### The experiment

`evidence/run_acceptance.py` funnels all 36 of its assertions through one
three-line method:

```python
def check(self, label: str, condition: bool, detail: str = "") -> None:
    self.checks.append(Check(label, bool(condition), detail))
```

Nothing tests it, nothing mutates it, and `Scenario.passed` is
`all(c.passed for c in self.checks)`. I changed `bool(condition)` to `True` — a
one-token mutation of exactly the kind both harnesses apply to `src/` all day:

1. `pytest` — **still passes, exit 0.** Nothing in 425 tests touches this file.
2. I then applied mutant #1 from their *own* table, the one whose note reads
   *"the headline claim, inverted"* — adding `Disposition.FENCED_STALE` to
   `_ADMITTING` in `src/waypoint/fencing.py`, which makes stale tool results
   speakable. That is the single defect this entire product exists to prevent.
3. `python evidence/run_acceptance.py` on that codebase:

```
  6/6 scenarios passed (36 checks)
  artifacts: ...\evidence\results\acceptance.json
             ...\evidence\results\acceptance.md
ACCEPTANCE EXIT CODE: 0
```

It printed `[PASS]` beside *"the unheard gate code is absent from the chat
context"* while the fence was configured to admit exactly that. It then
**overwrote the evidence artifacts with the green result**, and CI would have
uploaded them.

### Why this matters more than it looks

The repository's central rhetorical move — stated at `README.md:282`,
`RIME_EVIDENCE.md:258` and `SUBMISSION.md:71` — is *"'425 tests pass' is not
evidence; here is a mutation harness proving the tests would fail if the code
broke."* That argument is correct and it is the best thing about this
submission. But it is applied one level too shallow. The mutation harnesses
prove the **tests** would catch a regression. Nothing proves the **acceptance
harness** would, and the acceptance harness is what a judge actually runs, what
CI uploads, and what `RIME_EVIDENCE.md` points at.

A single wrong character in `Scenario.check` silently converts six scenarios and
36 checks into decoration, and the repository's entire verification apparatus —
425 tests, 28 mutants, four CI jobs across two operating systems — reports
green.

**Cost:** the 20% Evidence band rests on an artifact that cannot fail.
**Mark: overclaim a judge will catch.**

**Smallest fix (~10 minutes).** Add one entry to `mutation_test_ii.py`:

```python
(
    "the acceptance harness stops checking",
    "evidence/run_acceptance.py",
    "self.checks.append(Check(label, bool(condition), detail))",
    "self.checks.append(Check(label, True, detail))",
    "every acceptance claim becomes vacuous and the suite stays green",
),
```

For that mutant to be *caught*, the harness's oracle has to include
`run_acceptance.py` itself — so pair it with one test in `tests/`: assert that a
`Scenario` carrying a failing check reports `passed is False`, and that `main()`
returns a non-zero exit code. Three assertions close the hole that 10,582 lines
of Python currently leave open.

---

## 3. Are pass 2's fixes sound?

I attacked five. Two failed, three held.

### F10 — `VENDOR_IDENTIFIERS` — DEFEATED

`scripts/secret_scan.py:95-107` claims, in a docstring written specifically to
pre-empt this criticism:

> These are **subtracted from matches** rather than excluded by narrowing the
> pattern. … This list can only ever reduce noise; **it cannot reduce
> detection.**

It reduces detection. The scan loop calls `pattern.search(line)` — the *first*
match only — and on an allowlist hit does `continue`, abandoning the rest of the
line for that rule:

```python
m = pattern.search(line)
if not m:
    continue
if m.group(0) in VENDOR_IDENTIFIERS:
    continue          # <-- skips the RULE, not just this match
```

So any line where a vendor identifier appears *before* a real key is blind. Run
against `scan_text` directly, where `<KEY>` below stands for a LiveKit-shaped
literal — `API` followed by eighteen alphanumerics — written here as a
concatenation so that this document does not itself trip the scanner:

```
FLAGGED         A: key alone (what the two tests cover)
FLAGGED         B: key alone, bare in prose
*** MISSED ***  C: key on the SAME LINE as a vendor identifier
*** MISSED ***  D: APIStatusError: message='Invalid response status', key=<KEY>
```

Case D is not hypothetical. It is the exact shape already sitting in
`evidence/results/latency.md`, which currently reads `cold/websocket:
APIStatusError: message='Invalid response status', status_code=401` — and
`docs/MEASUREMENTS.md` explicitly instructs the reader to paste real tool output
into the repository. The moment someone does that with a key in the line, the
scanner says `clean`.

The two tests guarding this property —
`test_a_real_key_shaped_like_a_vendor_name_is_still_flagged` and
`test_the_allowlist_is_exact_not_a_prefix_match` — both put the key **alone** on
the line. Neither tests co-occurrence. This is the textbook shape the round-3
brief predicted: a test written to kill the specific mutant, not to specify the
behaviour.

**Cost:** this guards a named disqualifier — "Exposes a live credential or other
secret." **Mark: disqualifying (latent).**

**Smallest fix (~5 minutes), verified working:**

```python
for m in pattern.finditer(line):          # finditer, not search
    if m.group(0) in VENDOR_IDENTIFIERS:
        continue                          # skip THIS match only
    ... report and break ...
```

Re-run of the four cases with that change: A, B, C and D all flagged, while
`raise APIStatusError('Invalid response status')` and `except (APIStatusError,
APITimeoutError):` stay quiet. The fix keeps every property F10 was written to
protect and removes the false negative.

### F2 — `Settings.endpoint` derives from transport — DEFEATED

The fix is correct on the shipped default and wrong one environment variable
away. The installed plugin (`livekit.plugins.rime.tts` 1.7.1, lines 174-179)
upgrades the transport based on the URL scheme:

```python
if is_given(base_url):
    use_websocket = use_websocket or base_url.startswith(("ws://", "wss://"))
```

`Settings` does not model that. With `RIME_USE_WEBSOCKET=false` and
`RIME_BASE_URL=wss://users-ws.rime.ai` — both documented, at `.env.example:40`
and `README.md:171` ("Overridable via `RIME_BASE_URL`") — the two disagree:

```
WHAT WAYPOINT DISCLOSES                WHAT THE PLUGIN WILL ACTUALLY DO
  transport    : HTTP                    _base_url     : wss://users-ws.rime.ai
  heard method : duration_estimate       streaming cap : True
  warning      : "RIME_USE_WEBSOCKET=false: heard-not-said falls back to
                  the approximate duration estimator..."
```

The banner — the artifact the brief requires in order to make the active
provider observable, printed to a terminal that gets screen-recorded — states
the wrong transport and warns about a degradation that is not happening. Worse,
it is self-inflicted: `build_session` passes
`use_tts_aligned_transcript=settings.rime_use_websocket` (`agent.py:698`), so
word timestamps are on the wire and Waypoint declines to use them. The
heard-not-said boundary silently drops from exact to estimated.

The guarding test opens by excluding the case:

```python
s = load_settings()
assert s.rime_use_websocket, "this test assumes the shipped default"
```

**Cost:** the default path is correct, so this is not live today — but it is a
disclosure bug in the one artifact the brief singles out, reachable through a
documented variable. **Mark: overclaim a judge will catch.**

**Smallest fix (~5 minutes):** have `Settings` derive the effective transport
the way the plugin does, and key `transport`, `heard_method` and
`use_tts_aligned_transcript` off that single derived value:

```python
@property
def effective_use_websocket(self) -> bool:
    if self.rime_base_url:
        return self.rime_use_websocket or self.rime_base_url.startswith(("ws://", "wss://"))
    return self.rime_use_websocket
```

### F1 — `evidence/_rime.py`, the Rime call path — HELD (as far as offline goes)

Pass 2's headline was that no script could make a Rime call in any
configuration. That is fixed, and the proof is in the repository's own artifact.
`evidence/results/latency.json` records:

```
"cold/websocket: APIStatusError: message='Invalid response status',
 status_code=401, retryable=False"
```

A `401` means the request was constructed, transported and rejected by Rime for
credentials — exactly what a keyless machine should see, and categorically
different from the `TypeError`/`AttributeError` class of failure pass 2 found. I
could not take this further without a key. **Unconfirmed beyond the 401:** that
a *valid* key produces audio. Nothing in this repository has ever rendered a
sample, and that remains the largest unverified claim in the submission (N3).

### F4 — the secret-scan walk reaching `evidence/results/` — HELD

Planted a LiveKit-shaped key (`API` + `zz9Qm4Kd83Lx2Vb`) in
`evidence/results/_probe.md` and ran the scanner:

```
secret_scan: PROBLEMS FOUND
  evidence/results/_probe.md:1  [LiveKit API key (APIxxxxxxxxxxxx)]
```

Found. Probe removed. The narrowed `SKIP_DIRS` does what it claims.

### The catalog configuration — HELD, and I was wrong to suspect it

I expected a stale speaker list, because the brief explicitly warns against
"copying a stale speaker list into the application" and `config.py` hardcodes
`("coda", "mistv2", "mistv3")` with `lyra`/`cove` defaults. Checked against
Rime's live documentation: `coda` is the current flagship model, `lyra` is a
valid coda speaker, and `cove` is attested for `mistv2` in Rime's own documented
example. The hardcoded tuple also matches the pinned plugin's `TTSModels`
literal exactly, and `test_config.py::test_endpoint_constants_match_the_plugin`
is a real test that really runs — `livekit` is installed in this environment, so
it is not silently skipping. **This region is sound. Do not spend time on it.**

---

## 4. Findings, ordered by cost

### N1 — There is no demo. DISQUALIFYING

```
$ ls -la demo/
-rw-r--r-- 1 darsh 0 Sep  3 21:56 .gitkeep

$ find . -iname "*.mp4" -o -iname "*.mov" -o -iname "*.webm" -o -iname "*.wav" -o -iname "*.mp3"
(nothing)
```

The brief: *"A submission is not eligible for judging if it … Omits the required
demo."* It is also 10% outright, and it is the only evidence a judge gets for
the two 25% bands, because nothing else in this repository demonstrates
behaviour audibly.

**Cost:** the whole submission. **Fix:** record 4–5 minutes following
`DEMO_SCRIPT.md`, which is already written and is good. Everything else in this
report can be ignored until this is done.

### N2 — The acceptance harness cannot fail. Overclaim a judge will catch

Full evidence in §2. `evidence/` at 0% coverage and 0 mutation targets;
`Scenario.check` neutered leaves `pytest` green; with the fence inverted as
well, `run_acceptance.py` still reports `6/6 scenarios passed`, exits 0, and
overwrites its artifacts green.

**Cost:** the 20% Evidence band. **Fix:** §2 — one mutation entry plus three
assertions, ~10 minutes.

### N3 — Not one second of audio has ever been synthesised. Fails live

`evidence/results/latency.md` ships with an empty results table and two 401s.
`evidence/results/pronunciation/report.md` ships with `Audio rendered: False`
and 48 rows of `_unverified_`. `docs/LISTENING_NOTES.md` is a table of
`TODO | TODO | TODO`.

To be explicit about what is *good* here: none of those files lie. They label
themselves unverified, which is precisely what the brief asks for — *"Unverified
performance numbers receive no credit"* — and this project claims no credit
rather than inventing a number. That is the right call and most submissions get
it wrong. The finding is not dishonesty; it is that two of four work lanes have
produced nothing, and the product's audible qualities — the pronunciation of
`Guerrero` and `Divisadero`, speech-stop latency at the ear — are entirely
unevidenced in a competition scored on voice.

**Cost:** most of the "Rime integration and voice experience" band and a chunk
of "Hard voice engineering." **Fix:** a Rime free-tier key and one run each of
`evidence/measure_latency.py` and `evidence/measure_pronunciation.py`. This is
the same hour that produces the demo.

### N4 — `agent.py:819` writes session evidence to a CWD-relative path. Fails live

```python
out = Path("evidence/results/sessions")
```

This is the **only** CWD-relative path in the repository. Eleven other sites —
including every other file in `evidence/`, both mutation harnesses,
`preflight.py`, `secret_scan.py` and `web/server.py` — resolve from
`Path(__file__)`. Demonstrated:

```
cwd = ...\DataForge\waypoint  ->  ...\waypoint\evidence\results\sessions
cwd = C:\Users\darsh          ->  C:\Users\darsh\evidence\results\sessions   <-- outside the repo
```

The agent is started as `python -m waypoint.agent dev`, from wherever the
operator happens to be standing, and the failure is swallowed by `except
OSError: logger.warning(...)`. So the one code path in this entire codebase that
captures proof that a real session happened — fence audit trail, metrics,
heard-log — is the one that can silently write it somewhere else. Given that N3
is this submission's central weakness, that is an unlucky place for the only
path bug in the repository.

**Cost:** you record the demo, then cannot find the artifact that proves it.
**Fix (~2 minutes):** `out = ROOT / "evidence" / "results" / "sessions"` with
`ROOT = Path(__file__).resolve().parents[2]`, matching the rest of the repo.

### N5 — CI has never run, and the badge is a placeholder. Points lost

```
$ git remote -v
(empty)

README.md:3  [![verify](https://github.com/REPLACE-ME/waypoint/actions/...)]
```

Three commits, all made today between 11:32 and 11:53. There is no remote, so
the `verify` workflow has never executed anywhere, and the badge — the first
element on the README, above the title — renders broken. The workflow file
argues, correctly and at length, that its value is being *"executed on hardware
nobody on the team controls."* That argument is currently unexercised.

This one is known, not missed: `docs/VERIFICATION.md:49` and
`WORKFLOW.md:146,557` both track it. It is simply not done.

**Cost:** the cheapest credibility in the whole submission, unclaimed. A green
badge on a public repo is worth more to a ten-minute judge than another hundred
tests. **Fix (~5 minutes):** push to GitHub, replace `REPLACE-ME`.

### N6 — Three documents ship as unfilled worksheets. Points lost

`docs/LISTENING_NOTES.md` (a results table that is 24 cells of `TODO`),
`docs/VERIFICATION.md:22` (`TODO (expect: 425 passed) | TODO`) and
`docs/MEASUREMENTS.md` (an empty results table). Pass 2 raised this as F7 and
the fix table marks it done — but the fix added an owner banner (*"**Owner:
Rahul.** Fill every `TODO`…"*) rather than removing the TODOs. The document is
now a clearly-labelled blank worksheet instead of an unclearly-labelled one. A
judge browsing `docs/` still sees `| Gough Street | TODO | TODO | TODO |`.

Worth naming because it is the failure mode round 3 exists to catch — a fix that
satisfied the reviewer's sentence without satisfying the requirement — even
though the cost here is small.

**Cost:** small, but it advertises N3 to anyone who opens `docs/`.
**Fix:** fill them or delete them (§6). Do not ship them blank.

### N7 — Internal team-process documents ship to judges. Effort misspent

`WORKFLOW.md` is 578 lines — the second-largest document in the repository — and
it is a lane plan: four named teammates, a "Claude Pro / free" column, a "nobody
ever waits for anybody" rule and a 2.5–3 hour schedule. `SUBMISSION.md` opens
with *"Owner: Akshay. Fill the four `FILL:` blanks."* Neither is addressed to a
judge, and `WORKFLOW.md` documents in detail which lanes did not run.

**Cost:** small directly, but it is 578 lines of maintained surface returning
nothing, and it discloses the project's own gaps in the least flattering format.
**Fix:** see §6.

### Verified sound — do not spend your last hours here

Telling you where *not* to work is worth as much as a finding, and this project
is at real risk of being polished where it already shines.

- **The fence and its neighbours.** `fencing.py` 97%, `heard.py` 99%,
  `config.py` 99%, `pronounce.py` 99%, `metrics.py` 100%, `dispatch.py` 97%. I
  found nothing wrong in any of them.
- **Endpoint constants.** `RIME_WS_ENDPOINT` and `RIME_HTTP_ENDPOINT` verified
  equal to the installed plugin's `RIME_WS_BASE_URL + "/ws3"` and
  `RIME_BASE_URL`. The pin `livekit-agents[...]==1.7.1` is exact.
- **`attach_client_measurements`** (`agent.py:749`). Uncovered by tests, and
  correct anyway: type-checked, range-gated to 0–60000 ms, metric name truncated
  to 64 characters, browser samples tagged `source="browser"` on a separate
  `Boundary` so `MetricsLog` will not average them against server-side numbers.
  That is the right design and it is honestly documented.
- **The mutation harnesses' locking.** It worked correctly under a genuine
  concurrent-run attempt during this audit: the second harness refused to start
  and printed its repair instructions.
- **The artifacts' honesty.** Covered under N3, and it is the single most
  under-appreciated thing in this repository.

---

## 5. The score

Against the PDF's actual weights, for the repository **as it stands today**.

| Band | Weight | Score |
|---|---|---|
| Problem and necessity of voice | 25 | **22** |
| Hard voice engineering | 25 | **18** |
| Rime integration and voice experience | 20 | **12** |
| Evidence and reproducibility | 20 | **13** |
| Demo clarity | 10 | **0** |
| **Total** | **100** | **65 — see the eligibility note** |

**Eligibility overrides all of it.** The brief does not describe a missing demo
as a deduction; it lists it under "A submission is not eligible for judging if
it". Judged today the honest outcome is **ineligible**, and the 65 is what it
would score if the demo existed and showed what the code already does.

**Problem and necessity of voice — 22/25.** The strongest band. A driver with
both hands on the wheel who legally cannot look at a screen is a real user with
a real constraint, and the README's opening argument — that removing speech does
not degrade this product but deletes it — is exactly what the brief asks for.
The worked example of a gate code arriving for an abandoned stop is concrete and
persuasive. Docked slightly because the user is described rather than met: no
driver, no ride-along, no quote.

**Hard voice engineering — 18/25.** The turn fence is a genuine, well-chosen
hard problem, and the README does the rare thing of stating precisely what
LiveKit already does before claiming a contribution — which is the difference
between a contribution and a wrapper. The generation counter, the single
admission gate, at-most-once `admit()` and heard-not-said reconciliation are
real engineering, and 97% coverage plus 15 killed mutants on `fencing.py` back
them. Docked seven because every one of those claims is proved against a Python
attribute flipped in a harness. The brief asks for the hard problem solved
"under realistic conditions", and no barge-in has ever been performed by a human
voice against real streaming audio.

**Rime integration and voice experience — 12/20.** Configuration is correct and
current: right plugin, right model, valid speaker, exact endpoint, transport and
audio format disclosed in the banner and the browser console, no fallback
configured and the disclosure says so. That is most of "Rime integration". It
loses the "voice experience" half entirely, because there is no voice
experience — zero samples rendered, pronunciation unlistened, and the one
latency artifact is an empty table with two 401s. The F2 disclosure bug costs a
little more.

**Evidence and reproducibility — 13/20.** This would be the standout band —
offline-reproducible acceptance needing no keys, seeded fuzz whose safety
assertion is computed independently of the code under test, measurement
boundaries labelled and never averaged across, pinned versions, an archived
audit with every finding mapped to its fix. Docked seven for two reasons that
are both about the evidence rather than the code: the acceptance harness cannot
fail (§2), and the CI that carries the "verifiable by anyone, on any machine"
claim has never executed on any machine (N5).

**Demo clarity — 0/10.** There is no demo. `DEMO_SCRIPT.md` is a good script for
one.

### Best points per hour

**Record the demo.** Worth 10 points directly, and it converts the two 25% bands
from *claimed* to *demonstrated* — realistically +8 to +12 more across them —
and it removes the eligibility failure, which is not a point score but a gate.
Nothing else in this document is within a factor of five. The next best thing is
a Rime free-tier key and one `measure_latency.py` run, and that is the same
hour.

### What to cut to pay for it

Stop engineering. The code is finished and this audit found nothing wrong in the
core modules. Specifically: do not fill `docs/LISTENING_NOTES.md`, do not write
more tests, do not merge the two mutation harnesses, and do not act on N2, N4 or
the F10/F2 fixes until the demo is recorded — they are twenty minutes in total
and they belong *after*. The single exception is N5, because pushing to GitHub
takes five minutes and can run while you set up to record.

---

## 6. What to delete

Be willing to be unpopular about this. The repository is 10,582 lines of Python
and 3,756 lines of Markdown across thirteen documents. The Markdown is where the
waste is.

1. **`WORKFLOW.md` (578 lines) — delete before submitting.** An internal lane
   plan naming four teammates and their subscription tiers. It returns nothing
   to a judge and it is the clearest possible statement that two lanes produced
   no output. The single highest-value deletion in the repo.
2. **`docs/LISTENING_NOTES.md` (61 lines) — fill it or delete it.** A 24-cell
   `TODO` table reads as abandoned, which is worse than absent. If the listening
   test does not happen, say so in one sentence under limitations in
   `RIME_EVIDENCE.md`, where the brief already asks for limitations.
3. **`docs/VERIFICATION.md` (55 lines) — delete.** A human checklist with `TODO`
   result columns. Its content is already covered by CI and `preflight.py`, both
   of which actually execute.
4. **`SUBMISSION.md` — keep the content, cut the process.** Delete the "Owner:
   Akshay / fill the `FILL:` blanks / do not edit any other file" banner. The
   substance underneath is good and is the right document to hand a judge.
5. **`docs/MEASUREMENTS.md` — merge into `RIME_EVIDENCE.md`.** An empty results
   table in its own file is a promissory note. The brief asks for one
   `RIME_EVIDENCE.md`; give it one.

Two things I would **not** delete, against the instinct to trim:

- **`docs/audits/AUDIT-2.md` (1030 lines), the largest file in the repo.**
  Keeping a 1030-line list of your own defects in a judged submission looks
  reckless and is not. It is the most credible evidence in the repository that
  the claims elsewhere were adversarially tested, and its finding-to-fix header
  table is genuinely excellent. Keep it, and link it from the README with one
  sentence of framing.
- **The second mutation harness.** Roughly 880 lines across two files with
  near-identical machinery is a real duplication, and merging them is the
  obvious cleanup. Do not do it now. It is invisible to scoring and it would
  consume the hour that should produce the demo.

---

## Appendix — reproducing this audit

Every finding above, on a machine with no credentials.

```bash
pip install -e ".[dev]"
pip install coverage

# Section 2 -- coverage and the mutation-target map
python -m coverage run --source=src/waypoint,web,scripts,evidence -m pytest -q
python -m coverage report --sort=cover
grep -nE '"(src|scripts|evidence|web)/' evidence/mutation_test.py evidence/mutation_test_ii.py

# Section 2 -- the acceptance harness cannot fail
#  1. in evidence/run_acceptance.py, replace
#       self.checks.append(Check(label, bool(condition), detail))
#     with
#       self.checks.append(Check(label, True, detail))
#  2. in src/waypoint/fencing.py, add Disposition.FENCED_STALE to _ADMITTING
#  3. python -m pytest -q                 -> passes, exit 0
#     python evidence/run_acceptance.py   -> 6/6 scenarios passed, exit 0
#  4. restore both files; git diff must be empty

# Section 3 -- F4 held (planted key is found)
# The tail is kept in a variable so this document does not trip its own scanner.
TAIL=zz9Qm4Kd83Lx2Vb
echo "k = \"API${TAIL}\"" > evidence/results/_probe.md
python scripts/secret_scan.py ; rm evidence/results/_probe.md

# N1, N4, N5
ls -la demo/
find . -iname '*.mp4' -o -iname '*.wav' -o -iname '*.webm'
grep -n 'Path("evidence' src/waypoint/agent.py
git remote -v
grep -n REPLACE-ME README.md
```

F10 and F2, which need a little more than a shell one-liner:

```python
# F10 defeated -- a real key hides behind a vendor identifier on the same line
import sys; sys.path.insert(0, "scripts")
from pathlib import Path
from secret_scan import scan_text

key = "API" + "n8Kd93mZq7Lx2Vb0Rt"
for line in ['key = "' + key + '"',
             "API" + "StatusError: auth failed for " + key]:
    print(bool(scan_text(Path("x.md"), line + "\n", "x.md")), "|", line)
# -> True  ... / False ...   the second is the false negative
```

```python
# F2 defeated -- disclosure contradicts the shipped path
import os
os.environ["RIME_USE_WEBSOCKET"] = "false"
os.environ["RIME_BASE_URL"] = "wss://users-ws.rime.ai"

from waypoint.config import load_settings
from waypoint.agent import build_tts

s = load_settings()
print("discloses:", s.transport, "/", s.heard_method)
print("actually :", "streaming =", build_tts(s).capabilities.streaming)
# -> discloses: HTTP / duration_estimate (approximate)
#    actually : streaming = True
```

Repository state on exit: `git diff` empty, `pytest` 425 passed,
`run_acceptance.py` 6/6, `secret_scan.py` clean, every temporarily mutated file
restored and hash-verified.
