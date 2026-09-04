> **STATUS: every finding below has been fixed.** This file is kept as a
> record of the review, not as a list of open defects. It was written by an
> independent adversarial pass against the state of the project on
> 2026-09-04, and it is the reason for most of what changed afterwards.
>
> What it found, and where the fix lives:
>
> | Finding | Fix |
> |---|---|
> | **F1** No script could make a Rime API call (two bugs, four call sites) | `evidence/_rime.py` — transport-aware `synth()` + `http_context.open()`; all four call sites rewired; `tests/test_preflight.py` |
> | **F2** The disclosed endpoint was the HTTP host while streaming over WebSocket | `Settings.endpoint` derives from transport; `test_wiring.py::test_the_disclosed_endpoint_is_the_one_that_will_be_called` |
> | **F3** The mutation suite did not cover the wiring layer (9/12 survived) | `tests/test_wiring.py` (16 tests); `evidence/mutation_test_ii.py` adopted into CI; now 11/11 caught |
> | **F4** The secret-scan test could not fail, and the walk skipped `evidence/results/` | `test_scan_walks_the_tree_and_finds_a_planted_key` + narrowed `SKIP_DIRS`; also fixed a JSON-shaped-credential blind spot this exposed |
> | **F5** Not a git repository | initialised and committed |
> | **F6** `build_lexicon.py` targeted an endpoint that does not exist | script deleted, README promise replaced with the real constraint |
> | **F7** Four document defects | A6 table row, bug count, README web extra, worksheets |
> | **F8** Client stopwatch could under-sample in sentence gaps | now gated on `agent_state`, and gap-sourced samples are counted and shown |
> | **F9** Mutation-harness restore fidelity | exact `newline=""` I/O and per-mutation restore verification in both harnesses |
> | **F10** The scanner flagged LiveKit's own exception names | `VENDOR_IDENTIFIERS` allowlist, subtracted from matches so detection is unchanged |
>
> Two of its judgements were also checked and **not** adopted verbatim: the
> suggested `tts._use_websocket` read was replaced with the public
> `tts.capabilities.streaming`, and its F6 endpoint detail could not be
> independently confirmed — the script was deleted anyway, because a promise
> that cannot be verified should not be in a README.

# AUDIT-2 — second adversarial pass

Audited: `C:\Users\darsh\OneDrive\Desktop\DataForge\waypoint`, 2026-09-04.
Rubric source: `Rime PS.pdf` (read first, before any repo document).
Method: offline execution. `pip install -e ".[dev]"`, then everything was run,
not read. Rime's live catalog and LiveKit's plugin documentation were checked
over the network. No Rime or LiveKit credentials were available, so every
finding below is reproducible **without keys** unless explicitly marked.

Two files were added: this one, and **`evidence/mutation_test_ii.py`** — the
executable form of §3, safe to run (it takes the same lock as the existing
harness and restores byte-exactly). No existing file was modified. The
repository was left green: `pytest` 350 passed, `run_acceptance.py` 6/6,
`mutation_test.py` 15/15, `secret_scan.py` clean, all local markdown links
resolving, every mutation site verified original.

Findings are ordered by cost. **F1 is the one that matters**; F2–F5 are real
and cheap; F8 is explicitly unconfirmed and F9 is explicitly unreproduced,
labelled as such rather than dressed up.

---

## 1. Verdict

A judge who spends ten minutes here comes away impressed and then cannot
verify the thing they were most impressed by. The offline half of this
submission is exceptional — 350 tests, six acceptance scenarios, seeded fuzz
whose safety assertion is computed independently of the code under test, a
mutation suite that genuinely earns its 15/15, and a README that states
precisely what LiveKit already does before claiming a contribution. That is
rarer than it sounds and it should not be undersold. But **no script in this
repository can make a single Rime API call, in any configuration, even with
valid credentials** — two independent bugs across four call sites — and the
consequence is that `scripts/preflight.py` can never exit 0, `DEMO_SCRIPT.md`
instructs you not to record until it does, two of four people's work lanes
produce nothing, and **not one audio sample has ever been rendered by this
codebase**. There is no demo, which the PDF lists as a disqualifier. The
engineering is real; the evidence that it works under real conditions does not
exist yet, and the one script written to produce it is broken in a way that
misreports itself as a credentials problem. Judged today: **ineligible, on
"Omits the required demo."** Judged on the artifact, **65/100**. The gap
between 65 and roughly 82 is about ninety minutes of work, and it is all in
one place.

---

## 2. What the first pass missed

The first pass fixed five bugs and characterised its own blind spot correctly:
*documentation and code disagreed, and the tests agreed with neither.* It then
looked for that pattern **inside the modules that have tests**. Every one of
its five fixes landed in `src/waypoint/`.

The pattern continues, undisturbed, in the four scripts that sit **outside**
the test suite and outside the agent worker — `scripts/preflight.py`,
`evidence/measure_latency.py`, `evidence/measure_pronunciation.py`,
`evidence/measure_heard_accuracy.py`. Those four are precisely the scripts
that would have produced every Rime-dependent number in the submission. All
four are dead.

The sharpest single instance, and the one that best illustrates the shape:

`evidence/measure_heard_accuracy.py` **refuses to run unless
`RIME_USE_WEBSOCKET=true`** (line 204: *"RIME_USE_WEBSOCKET is false, so no
word timestamps will arrive and there is no ground truth to compare against.
Set it to true."* → `return 2`). It then calls `tts.synthesize(text)` at line
102 — a method the Rime plugin raises on **when `use_websocket` is true**. The
script has two mutually exclusive preconditions. It cannot succeed under any
configuration that has ever existed.

And its docstring (lines 88–93) documents, at length, the *previous* bug the
first pass fixed in that very function — reading `ev.timed_words` /
`ev.words` / `ev.alignment`, which do not exist. The first pass corrected the
attribute read inside a function that can never execute. That is the whole
finding in miniature: the audit checked the line, not the path.

```
$ RIME_API_KEY="rk_dummy_key_for_audit" python evidence/measure_heard_accuracy.py --cuts 3
  No comparisons produced. Nothing written.
    ! RuntimeError: Rime TTS one-shot synthesize requires use_websocket=False at construction time
    ! RuntimeError: Rime TTS one-shot synthesize requires use_websocket=False at construction time
    ! RuntimeError: Rime TTS one-shot synthesize requires use_websocket=False at construction time
    ! RuntimeError: Rime TTS one-shot synthesize requires use_websocket=False at construction time
$ echo $?
1
```

No credentials needed to reproduce. The RuntimeError precedes all I/O.

---

## 3. The mutation-test blind spot

**It has one, it is large, and it is a region rather than a missing row.**

15/15 is real. I re-ran it: `15/15 mutants caught (162s)`, exit 0, working tree
clean. The lock, the refuse-to-start-on-a-dirty-tree guard, `--repair`, and the
`REAL BUG` annotations are careful, honest engineering and the number should be
trusted for what it measures.

What it measures is the **tested core**. Sorted by file, the fifteen mutations
are: `fencing.py` ×6, `agent.py` ×5, `pronounce.py` ×2, `heard.py` ×1,
`metrics.py` ×1. Every one lands in code that a unit test calls directly. The
five in `agent.py` all target `_read` / `_write` / `_reconcile_heard` /
`transcription_node`.

Not one lands in the ~220-line wiring layer at `src/waypoint/agent.py:655–876`
— `build_tts`, `build_session`, `attach_observers`, `attach_client_measurements`,
`entrypoint` — which is the layer that decides which Rime model, voice,
language, sample rate and transport are used, and **whether barge-in is
switched on at all**. It cannot land there, because nothing tests it:

```
$ grep -n "from waypoint.agent import" tests/test_agent.py
20:from waypoint.agent import Deps, WaypointAgent
```

`Deps` and `WaypointAgent`. Nothing else. `build_tts` — the single most
rubric-relevant function in the project — appears in **zero** tests:

```
$ grep -rn "base_url\|endpoint\|_ws_url\|build_tts" tests/
(no output)
```

Nor does the table touch the values that are only wrong relative to an external
system, the system prompt, or the two scripts that stand in for the PDF's
disqualifiers.

I wrote `evidence/mutation_test_ii.py` to measure that region — twelve
mutations in four categories the existing table has no entry for, each a bug
someone could plausibly write, each target verified to resolve uniquely so no
result is a silent SKIP. Result:

```
$ python evidence/mutation_test_ii.py
  -- A: external contract (only wrong against Rime's catalog)
   1. coda runs with a Mist-family voice              caught  FAILED test_config.py::test_defaul
   2. language code is not a Rime language code       caught  FAILED test_config.py::test_defaul
   3. audio is synthesised at telephony rate          caught  FAILED test_config.py::test_banner
   4. build_tts hardcodes a different model than it discloses *** SURVIVED ***
  -- B: wiring (the untested Settings-to-session layer)
   5. the shipped transport silently becomes HTTP     *** SURVIVED ***
   6. word timestamps never reach the agent           *** SURVIVED ***
   7. barge-in is switched off entirely               *** SURVIVED ***
   8. barge-in needs ten seconds of speech            *** SURVIVED ***
  -- C: prompt / delivery (what is actually spoken)
   9. markdown and emoji are spoken aloud             *** SURVIVED ***
  10. the written-for-the-ear rules are gone          *** SURVIVED ***
  -- D: gates (the brief's disqualifiers)
  11. preflight passes with zero audio frames         *** SURVIVED ***
  12. the secret scanner always reports clean         *** SURVIVED ***

  3/12 mutants caught   (161s)
  9 of 12 deliberate bugs were invisible to the test suite.
```

Read mutant **7** again. `build_session`'s interruption block set to
`"enabled": False` disables barge-in. This product *is* barge-in recovery. All
350 tests pass, all six acceptance scenarios pass, and the original mutation
suite still reports 15/15. Nothing in the repository notices that the product's
only feature has been switched off.

Two things worth saying precisely about that result:

- **Category A is mostly healthy.** Three of four value mutations were caught,
  by `test_config.py`. The suite does defend the Rime configuration values,
  which is better than I expected and better than the file-coverage map
  suggests. The exception (mutant 4) is the one that bypasses `Settings`
  entirely by hardcoding a model inside `build_tts` — which falsifies that
  function's own docstring claim that the shipped and disclosed configs
  *"cannot drift apart."*
- **Mutant 12 was my control and I predicted it wrong.** I expected
  `tests/test_secret_scan.py` (40 tests) to catch a scanner that always
  returns clean. It does not. See F4 — that is a finding in its own right, and
  the contrast with Category A is the useful signal: the suite tests rule
  *engines* thoroughly and tests *wiring* not at all.

**Why CI never caught any of this.** `.github/workflows/ci.yml:69` runs
`python scripts/preflight.py --offline --skip-tests`. `--offline` skips
`check_rime` — the only broken part. The single automated check of the
preflight script runs it in the mode that bypasses the bug.

---

## 4. Findings, ordered by what they cost

### F1 — No script in the repository can make a Rime API call. Two bugs, four call sites. **Highest cost.**

Two independent root causes, both offline-reproducible:

**F1a — `synthesize()` is the HTTP-only method.** The pinned plugin
(`livekit/plugins/rime/tts.py:330`) raises unconditionally when the TTS was
built for WebSocket, which is the shipped default (`config.py:118`,
`rime_use_websocket: bool = True`):

```
$ RIME_API_KEY=dummy python -c "
from waypoint.config import load_settings; from waypoint.agent import build_tts
s = load_settings(); print('use_websocket =', s.rime_use_websocket)
build_tts(s).synthesize('x')"
use_websocket = True
RuntimeError: Rime TTS one-shot synthesize requires use_websocket=False at construction time
```

Call sites: `scripts/preflight.py:149`, `evidence/measure_latency.py:74`,
`evidence/measure_pronunciation.py:177` (which explicitly sets
`"use_websocket": True` at line 159, then calls `synthesize` eighteen lines
later), `evidence/measure_heard_accuracy.py:102`.

**F1b — the plugin needs an HTTP context none of these scripts opens.** The
plugin calls `utils.http_context.http_session()`, which requires the agent
worker's job context or an explicit `http_context.open()`. This kills **both**
transports, so it is not fixed by fixing F1a:

```
$ RIME_API_KEY=dummy python -c "...build_tts(replace(s, rime_use_websocket=False)).synthesize(...)"
HTTP arm: use_websocket = False | base_url = https://users.rime.ai/v1/rime-tts
# secret-scan: allow  (the exception name below trips the LiveKit key rule -- see F10)
HTTP arm FAILED: APIConnectionError: Connection error.
  (caused by RuntimeError: Attempted to use an http session outside of a job context...)
```

**What this costs.** `scripts/preflight.py` cannot exit 0. With four valid
credentials it prints this, every time, and blames the wrong thing:

```
$ LIVEKIT_URL=... LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=... RIME_API_KEY=... \
    python scripts/preflight.py --skip-tests
  [PASS] configuration is valid          coda/lyra lang=eng WebSocket (wss) pronunciation=respell
  [PASS] no secret in the repository
  [PASS] hard street names are transformed
  [PASS] pronunciation lexicon           20 entries, 0 with verified Rime phonemes
  [PASS] all credentials present
  [FAIL] Rime synthesises with coda/lyra
         RuntimeError: Rime TTS one-shot synthesize requires use_websocket=False at construction time
         Check RIME_API_KEY, and check the model/speaker pair against the live catalog at ...
  1 check(s) failed. Do not record yet.
```

The remediation text sends the reader to their API key and the live catalog.
Both are fine. `DEMO_SCRIPT.md:16` says *"Run these and do not proceed until
all three are clean"* with `preflight` first; `SUBMISSION.md`'s eligibility
self-check leaves *"Model / voice / language passes the event preflight"*
unticked because it cannot be ticked; and `docs/MEASUREMENTS.md` /
`docs/LISTENING_NOTES.md` ship as TODO templates awaiting output that cannot be
produced. **Lanes B and C of `WORKFLOW.md` — 120 person-minutes — produce
nothing.** There are zero `.wav`/`.mp3`/`.pcm` files in the repository;
`pronunciation.json` records `"audio_rendered": false`. Two artifacts promised
by `RIME_EVIDENCE.md` §4 (*"Each writes a committed artifact"*) do not exist:
`evidence/results/latency.md`, `evidence/results/heard_accuracy.md`.

The PDF is directly on point: *"Test the shipped path. Verify the exact
endpoint, region, framework, model, audio format, and transport used in the
final demo,"* and *"Unverified performance numbers receive no credit."*

**Crucially — and this is the good news — the shipped agent is unaffected.**
Both bugs are confined to out-of-worker scripts. The framework drives a
streaming-capable TTS via `stream()`, not `synthesize()`
(`livekit/agents/voice/agent.py:593`, `async with wrapped_tts.stream(...)`;
`StreamAdapter` is used only `if not activity.tts.capabilities.streaming`,
line 574), and the agent runs inside a job context. I confirmed
`build_session()` constructs correctly with `use_tts_aligned_transcript=True`,
`interruption {enabled: True, mode: 'adaptive', min_duration: 0.4}` and
`tts_text_transforms ['filter_emoji','filter_markdown']`. **The product is
correctly wired. It is the proof apparatus that is broken.**

**Smallest real fix** — one shared helper, four call sites. Verified working:

```python
# evidence/_rime.py  (new)
from contextlib import asynccontextmanager
from livekit.agents.utils import http_context
from livekit.agents.types import USERDATA_TIMED_TRANSCRIPT

@asynccontextmanager
async def rime_session():
    """Plugins outside the agent worker need their own HTTP context."""
    async with http_context.open():
        yield

async def synth(tts, text):
    """Drive whichever transport the TTS was actually built for."""
    frames, timed, pcm = 0, 0, bytearray()
    first_ms = None
    t0 = time.perf_counter()
    if tts._use_websocket:
        stream = tts.stream()
        stream.push_text(text); stream.flush(); stream.end_input()
    else:
        stream = tts.synthesize(text)
    try:
        async for ev in stream:
            if first_ms is None:
                first_ms = (time.perf_counter() - t0) * 1000.0
            f = getattr(ev, "frame", None)
            if f is None:
                continue
            frames += 1
            pcm.extend(bytes(f.data))
            timed += len((f.userdata or {}).get(USERDATA_TIMED_TRANSCRIPT) or [])
    finally:
        await stream.aclose()
    return first_ms, frames, timed, bytes(pcm)
```

Then wrap each script's async main in `async with rime_session():` and replace
its `tts.synthesize(...)` loop with `await synth(tts, text)`. I verified the
combination reaches Rime's live service on the shipped path:

```
$ RIME_API_KEY="rk_dummy_key_for_audit" python -c "<http_context.open() + tts.stream()>"
# secret-scan: allow  (exception name trips the LiveKit key rule -- see F10)
WS shipped path -> APIStatusError: message='Invalid response status', status_code=401, retryable=False
```

A 401 on a dummy key is the correct answer, and it proves the fix is sufficient
in shape: real handshake, real endpoint, real auth rejection. With a valid key
this path works. **Estimate: 45–60 minutes for all four scripts.**

While in there, `preflight.py` has two further defects in the same function
that the fix should close, because its docstring promises both:

- *"5. The WebSocket path works, since that is what the shipped config uses."*
  Lines 191–196 report `[PASS] WebSocket transport in use` from
  `if settings.rime_use_websocket:` — reading a config flag. It never opens a
  WebSocket.
- *"6. Word timestamps arrive, since heard-not-said depends on them."* Lines
  157–159 are a dead loop over a dead variable:
  ```python
  for attr in ("segment_id", "start_time", "end_time"):
      if getattr(ev, attr, None) is not None:
          break
  ```
  `timed_words` is initialised at line 145 and never incremented.
  `SynthesizedAudio` fields are `['frame','request_id','is_final','segment_id',
  'delta_text']` — `segment_id` always exists so the loop breaks immediately,
  and `start_time`/`end_time` never exist on it at all. Word timings ride on
  `frame.userdata[USERDATA_TIMED_TRANSCRIPT]`
  (`livekit/agents/tts/tts.py:1103`). Check 6 is not implemented. The helper
  above returns `timed`, so this becomes `if timed == 0: r.fail(...)`.

### F2 — The disclosed endpoint is wrong, on all four disclosure surfaces

The PDF names `endpoint` twice: in the README requirement (*"the exact Rime
model ID, speaker, language, endpoint, audio format, and transport used"*) and
in the build rules (*"Verify the exact endpoint..."*). It is the one field this
project gets wrong.

```
$ RIME_API_KEY=dummy python -c "<build_tts(load_settings()) then _ws_url()>"
--- what the CODE will actually do ---
use_websocket  : True
plugin base_url: wss://users-ws.rime.ai
ACTUAL WS URL  : wss://users-ws.rime.ai/ws3?speaker=lyra&modelId=coda&audioFormat=pcm&samplingRate=22050&segment=bySentence&lang=eng&speedAlpha=1.0
--- what the BANNER discloses ---
endpoint       : default (users.rime.ai)
transport      : WebSocket (wss)
```

`users.rime.ai` is the **HTTP** host (`https://users.rime.ai/v1/rime-tts`),
used only when `use_websocket=False`. Confirmed independently against
LiveKit's own Rime plugin documentation — *"HTTP synthesis:
`https://users.rime.ai/v1/rime-tts`; WebSocket streaming:
`wss://users-ws.rime.ai`"* — and a third time by the live 401 handshake in F1.

Surfaces, all wrong: `README.md:170` (`| Endpoint | Rime default
(users.rime.ai) |`), the startup banner (`config.py:269`, printed on every run
and, per `config.py:85–96`, *"printed to a terminal that will be
screen-recorded for the demo video"*), `GET /api/config` (verified live), and
the browser console (`web/index.html:322`, `["endpoint", r.base_url]`) —
rendered two lines under the green `SPEECH PROVIDER: RIME` badge that
`DEMO_SCRIPT.md` Shot 3 tells you to point at for two seconds. **It will be on
camera.**

`build_tts`'s docstring claims *"Every argument here is mirrored in
`Settings.banner()` so the shipped configuration and the disclosed
configuration cannot drift apart."* This is the drift.

**Smallest real fix** — make the disclosure derive from the transport instead
of from the override, in `config.py`:

```python
RIME_WS_DEFAULT   = "wss://users-ws.rime.ai/ws3"
RIME_HTTP_DEFAULT = "https://users.rime.ai/v1/rime-tts"

@property
def endpoint(self) -> str:
    if self.rime_base_url:
        return self.rime_base_url
    return RIME_WS_DEFAULT if self.rime_use_websocket else RIME_HTTP_DEFAULT
```

Use `self.endpoint` in `to_dict()["rime"]["base_url"]`, and correct
`README.md:170` to `wss://users-ws.rime.ai/ws3` (`https://users.rime.ai/v1/rime-tts`
on the HTTP path). **Estimate: 10 minutes.** Add one test asserting the
disclosed endpoint's host equals the host in `build_tts(settings)._ws_url()` —
that is the assertion whose absence let this through.

### F3 — The mutation suite does not cover the wiring layer

Full detail in §3. 9 of 12 wiring/prompt/gate mutations ship green, including
barge-in disabled entirely.

**Smallest real fix.** `evidence/mutation_test_ii.py` already exists and runs
(161s, no credentials, same lock, byte-exact restore, `--list` and `--repair`).
Add it to `ci.yml` beside the existing mutation job and cite both numbers.
Then close the three worst holes with tests that construct the wiring — this is
the cheapest possible coverage for the highest-stakes code:

```python
def test_build_session_enables_barge_in_and_aligned_transcripts():
    s = Settings(rime_api_key="x", livekit_api_key="x", livekit_api_secret="x",
                 livekit_url="wss://x")
    with patch.object(silero.VAD, "load", return_value=object()):
        sess = build_session(s, None)
    assert sess.options.use_tts_aligned_transcript is True
    itr = sess.options.turn_handling["interruption"]
    assert itr["enabled"] is True
    assert itr["min_duration"] == s.min_interruption_duration
    assert sess.options.tts_text_transforms == ["filter_emoji", "filter_markdown"]

def test_build_tts_uses_the_settings_it_discloses():
    s = Settings(rime_api_key="x")
    tts = build_tts(s)
    assert tts.model == s.rime_model
    assert tts._use_websocket is s.rime_use_websocket
    assert s.rime_speaker in tts._ws_url()
    assert f"modelId={s.rime_model}" in tts._ws_url()
```

Those two tests kill mutants 4, 5, 6, 7, 8 and 9. **Estimate: 25 minutes.**

### F4 — The secret-scan test cannot fail when the scanner breaks, and the scanner skips a committed directory

Two defects in the gate for a stated disqualifier (*"Exposes a live credential
or other secret"*).

**F4a.** Mutant 12 made `scan()` return `[]` unconditionally; all 350 tests
passed. The only test that calls it is `tests/test_secret_scan.py:170`:

```python
def test_this_repository_is_clean() -> None:
    """The check that actually matters. Also runs in the pre-commit hook."""
    findings = scan(ROOT)
    assert findings == []
```

It asserts the scanner finds nothing — so it **passes more easily when the
scanner is broken**. The 40 tests cover `scan_text()` (the rule engine)
thoroughly; the repository *walk* has no positive test at all. This is exactly
the class the first pass named — an evidence check whose assertion does not
test the thing it claims — surviving in a second location.

**F4b.** `SKIP_DIRS` (`scripts/secret_scan.py:33`) contains `"results"`, so
`evidence/results/**` is never scanned — and that directory holds committed
artifacts (`pronunciation/pronunciation.json`, `pronunciation/report.md`, and
whatever `entrypoint._dump()` writes to `sessions/`, none of which is
gitignored). Verified:

```
rules DO flag this string      : True
scan() finds it in results/    : False   <-- gap
scan() finds it in evidence/   : True
```

**Exposure today is low** — I checked `_dump()` (`agent.py:816–840`); it writes
fence audit, metrics and heard records, no credentials. This is a coverage
hole, not a live leak. But it is the directory a future session dump lands in.

**Smallest real fix:**

```python
def test_scan_finds_a_planted_key(tmp_path):
    (tmp_path / "leak.json").write_text(
        '{"k": "rk_" + "live_" + "9f3b2c8a41de47b6a05c7e1d93f8ab24"}', encoding="utf-8")
    assert scan(tmp_path), "scan() walked the tree but found a planted key"
```

and drop `"results"` from `SKIP_DIRS` (keep `results/tmp/`, which is
gitignored, via a narrower path check). **Estimate: 10 minutes.**

### F5 — It is not a git repository

```
$ git rev-parse --is-inside-work-tree
fatal: not a git repository (or any of the parent directories): .git
```

Nothing is committed. Consequences: `.github/workflows/ci.yml` — 175 lines,
two operating systems, two Python versions, mutation job, working-tree-unchanged
guard, a markdown link checker — **has never run and cannot run**
(`on: push / pull_request`). `README.md:3`, the first visible element on the
page a judge opens, is a badge pointing at
`https://github.com/REPLACE-ME/waypoint/actions/...`; it renders broken. The
link checker that would have caught a bad link skips `http(s)://`, which is why
it survived. Lane D's *"D1. Clone fresh and verify"* has nothing to clone. The
PDF asks for claims backed by *"a transparent method, committed artifacts, or a
repeatable test"* and for *"a source repository that judges can inspect"*.

This is already written up as `WORKFLOW.md` §0d, assigned to one person,
estimated at five minutes, and correctly flagged there as *"the only thing
anyone is waiting on."* It has not been done.

**Smallest real fix:** run `WORKFLOW.md` §0d verbatim, then replace
`REPLACE-ME` in `README.md:3`. **Estimate: 5 minutes.** It also gives the
mutation harnesses a `git checkout` recovery path they currently lack.

### F6 — `build_lexicon.py` targets an endpoint that does not exist

`README.md` promises the empty phoneme column is fillable: *"`scripts/build_lexicon.py`
populates it from Rime's own API."* It cannot.

Rime's Phonemize endpoint is **`POST https://optimize.rime.ai/phonemize`**, and
its request body is **raw audio bytes** (`audio/wav` or `audio/mpeg`) — you
record or synthesise the word, then post the audio. `build_lexicon.py:58–60`
tries three other URLs (`users.rime.ai/v1/phonemize`, `users.rime.ai/phonemize`,
`api.rime.ai/v1/phonemize`) and POSTs **JSON containing text** (line 76,
`json=payload`). Wrong host, wrong path, wrong body type, wrong content type.
All three candidates fail.

This is low severity — the shipped default is `respell`, which needs no
phonemes, and the README already says the column ships empty *on purpose*. But
it is a false promise in the README and a scheduled task (`WORKFLOW.md` B3)
that cannot succeed.

**Smallest real fix:** delete `scripts/build_lexicon.py` and change the README
sentence to state the actual requirement — *"Rime's Phonemize API
(`POST optimize.rime.ai/phonemize`) takes recorded audio, not text, so
populating this column means synthesising each word first; the shipped
`respell` strategy needs no phonemes."* **Estimate: 5 minutes**, and it removes
10 minutes from Lane B. See §6.

### F7 — Four document defects a ten-minute judge will actually hit

1. **The A6 acceptance row does not render as a table row.**
   `RIME_EVIDENCE.md:74` is the last row of the scenarios table, lines 76–79
   are a prose paragraph, and line 80 is `| **A6** | Nine-turn conversation…|`.
   Separated from its table by a blank line and a paragraph, it renders as a
   literal line of pipe characters — in the section where a judge checks
   whether an acceptance test was defined. *Fix: move the paragraph below line
   80. One minute.*
2. **The bug count contradicts itself across the three documents a judge
   reads.** `evidence/mutation_test.py:22` says *"Six of them were really
   written"* (correct — 6 mutations carry `REAL BUG`). `RIME_EVIDENCE.md:131`
   says *"Five bugs this found"* (also correct — one bug has two mutated
   halves) and attributes three to the adversarial pass. `SUBMISSION.md:72`
   says *"Four real bugs… two of them by an adversarial review pass… All four
   are written up in RIME_EVIDENCE.md §3"*, where five are written up. The
   document a judge reads first **understates its own strongest evidence** and
   disagrees with its own source. In a submission whose thesis is "trust our
   numbers," this is worse than it looks. *Fix: say five, and two of the five
   halves were adversarial-pass finds; state it once, cite it elsewhere. Five
   minutes.*
3. **The README never documents the web extras.** `README.md:94` says
   `pip install -e ".[dev]"`; `README.md:147` then says `python web/server.py`.
   `fastapi`/`uvicorn`/`livekit-api` live in the `[web]` extra, so a judge
   following the README alone gets `missing dependency… install the web extras`
   on the visual console — the artifact that carries the fence board.
   `WORKFLOW.md:170` gets this right (`.[dev,web]`); the README does not.
   *Fix: one character. One minute.*
4. **`docs/MEASUREMENTS.md` and `docs/LISTENING_NOTES.md` ship as TODO
   templates** with owner blockquotes intact (*"Delete this blockquote when you
   are done"*). They are honest, well-designed worksheets and much better than
   invented numbers — but as long as F1 stands they cannot be filled, and a
   judge browsing `docs/` sees `| Gough Street | TODO | TODO | TODO |`.
   *Fix: F1, then fill them. Or move both to a `docs/worksheets/` subdirectory
   so they read as working files rather than deliverables. Two minutes.*

### F8 — *Unconfirmed.* The client barge-in stopwatch may under-sample

`web/index.html:508` only arms the stopwatch if `M.remoteActive` is true at the
moment the driver's voice crosses `SPEECH_RMS`. `M.remoteActive` is cleared
after remote RMS stays below `SILENCE_RMS = 0.004` for `SILENCE_HOLD = 120` ms
(lines 437–439, 481–495). With `segment=bySentence`, Rime returns audio per
sentence, and natural inter-sentence gaps can plausibly exceed 120 ms. If so, a
barge-in landing in a gap is **not measured at all** — and because the console
reports min–max over recorded samples, missing samples are invisible. That
would bias the reported range toward the easy cases.

I could not confirm this without a live session; it is a reasoned reading of
the code, not an observation. **What would confirm it:** run the agent, log
`M.remoteActive` transitions during one multi-sentence reply, and check whether
it drops to `false` mid-utterance. If it does, raise `SILENCE_HOLD` to ~250 ms
or gate on `agent_state === "speaking"` from the session events already being
published (`agent.py:730`) rather than on RMS alone. The instrument itself —
RMS on the *remote* track, so the stopwatch stops when audio goes silent in the
listener's own browser — is the right instrument and directly answers the PDF's
*"Measure what the user experiences, not a convenient proxy."*

### F9 — *Observed once, not reproduced.* Restore fidelity in the mutation harness

My first run of `mutation_test_ii.py`, which then used the same
`Path.read_text` / `Path.write_text` pattern as `evidence/mutation_test.py`,
ended with `!! SOURCE NOT RESTORED: ['src/waypoint/prompts.py',
'scripts/preflight.py']` and exit 2 — while the mutated text was in fact
**absent** from both files, i.e. the content had been restored and only the
SHA-256 disagreed. I could not reproduce it: all nine touched files are pure
CRLF with zero lone `\n`, a text round-trip is byte-identical, an isolated
apply-and-restore of both mutations is byte-exact, and 200 write→read cycles in
that directory were stable. After switching to `newline=""` I/O the report has
not recurred, and the original harness re-ran clean at 15/15.

**Mechanism unidentified.** I am reporting it because the original harness
shares the pattern and a false "your checkout is corrupted" alarm twenty
minutes before a deadline is expensive, and because the repository has no git
history to recover from (F5). **Hardening, one line each:** read and write with
`open(..., newline="")` and translate the table's `\n` to the file's own ending
before matching — `evidence/mutation_test_ii.py` shows the pattern in
`read_source` / `write_source` / `localise`. Also verify each restore
immediately rather than at the end of the run, so a bad restore stops the run
instead of surfacing fifteen minutes later.

### F10 — The secret scanner flags LiveKit's own exception names, and the pre-commit hook blocks on them

Listed last by severity, but it is a **deadline trap**, and it is the one
finding this audit discovered by walking into it: writing this file tripped the
scanner, and then failed `pytest`.

Throughout this section the LiveKit identifiers are written with their `API`
prefix elided — `…ConnectionError`, `…StatusError`, `…TimeoutError`,
`…ConnectOptions` — **because writing them in full makes this document fail
`tests/test_secret_scan.py::test_this_repository_is_clean`.** That is the
finding, demonstrated.

The rule at `scripts/secret_scan.py:80` is:

```python
("LiveKit API key (APIxxxxxxxxxxxx)", re.compile(r"API[A-Za-z0-9]{10,}"))
```

It matches any identifier beginning `API` with ten or more following
characters. LiveKit's public exception and option classes are exactly that
shape, so all four are reported as leaked credentials. I verified each against
`scan_text` directly; `APIError` (eight characters) is short enough to escape.

Why the repository is clean today: no *scanned* file currently contains those
identifiers. Why that will not last — six places format errors as
`f"{type(exc).__name__}: {exc}"` (`scripts/preflight.py:139,164`,
`evidence/measure_latency.py:83`, `evidence/measure_heard_accuracy.py:117`,
`evidence/measure_pronunciation.py:188`, `scripts/build_lexicon.py:90`), and for
any Rime or LiveKit failure that name **is** one of the four. Meanwhile
`docs/MEASUREMENTS.md` instructs the reader: *"TODO — anything that failed,
looked odd, or you could not explain. Write it down."* The moment someone
pastes real tool output into a document — exactly what fixing F1 and filling
Lane B require — `scripts/install_hooks.sh`'s pre-commit hook runs
`secret_scan.py --staged` and `exit 1`s on a line containing no secret. At
3 a.m. that reads as "I have leaked a key."

It is also the direct counter-example to `RIME_EVIDENCE.md`'s claim that
`test_secret_scan.py`'s 40 tests establish the scanner *"catches real keys;
does not cry wolf."* It cries wolf at the vendor's exception hierarchy.

Note `evidence/measure_pronunciation.py:188` writes that string into
`pronunciation.json`, a committed artifact — which the scanner does **not**
read, because of F4b. The two findings hide each other.

**Smallest real fix — allowlist the vendor identifiers; do not weaken the key
pattern.** My first attempt was a negative lookahead
(`API(?![A-Z][a-z])[A-Za-z0-9]{10,}`) to reject CamelCase tails. **Do not
use it.** I tested it: it silently drops real keys whose fourth character is a
capital followed by a lowercase — key shapes of the form `API` + `Rb7kQm2xLp9w`
or `API` + `Km3xyzABC123` — which is a false negative in a security control,
strictly worse than the noise it removes. Measured over seven cases (three
real-key shapes, four vendor identifiers): the current rule is wrong on 4,
the lookahead is wrong on 2 **in the dangerous direction**, and the allowlist
below is wrong on 0.

Keep the key pattern exactly as it is and subtract the known identifiers, so
the change can only ever reduce noise and never reduce detection:

```python
#: Vendor identifiers that match the LiveKit key shape but are public class
#: names. Subtracted from matches rather than excluded by pattern, so the key
#: rule itself keeps its full sensitivity.
LK_IDENTIFIERS = re.compile(
    r"API(?:ConnectionError|StatusError|TimeoutError|ConnectError"
    r"|ConnectOptions|Error)"
)
```

and in `scan_text`, skip a match when `LK_IDENTIFIERS.fullmatch(match.group(0))`.
**Estimate: 10 minutes**, plus one test per identifier and one asserting that a
key of the form `API` + `Rb7kQm2xLp9w` is *still* flagged — that last test is
the one that matters, because it is the property my first fix broke.

Two notes for whoever acts on this. First, the project already ships the right
escape hatch for prose — `secret-scan: allow` on the line or the one before it
— so this is a sharpness fix, not a correctness one. Second, once it is fixed,
this section can be rewritten with the identifiers spelled out in full; the
elision above is a workaround for the bug it describes.

---

## What is sound — do not spend your last hours here

Stated plainly, because knowing where not to look is worth as much as a bug.

- **The agent wiring is correct.** `build_session()` constructs with
  `use_tts_aligned_transcript=True`, `interruption {enabled: True, mode:
  'adaptive', min_duration: 0.4, min_words: 0, resume_false_interruption:
  True}`, `preemptive_generation {enabled: True}`, and
  `tts_text_transforms ['filter_emoji','filter_markdown']`. Every kwarg it
  passes is a real `AgentSession` parameter. Verified by construction.
- **The Rime configuration triple is current and correct.** `coda` is Rime's
  flagship (May 2026, 253 voices, nine languages) per the live catalog;
  `lyra` is its documented default voice and the pinned plugin's
  `DefaultCodaVoice`; `models.py` is `Literal["mistv2","mistv3","coda"]`;
  `eng`, PCM, 22050 Hz and `segment=bySentence` all match what `_ws_url()`
  actually sends. The code deliberately does **not** hardcode a speaker list,
  which is exactly what the PDF asks (*"Use the current catalog at submission
  time rather than copying a stale speaker list"*).
- **The web console works end to end, and every claim made about it is true.**
  I ran `web/server.py` and exercised all three endpoints: `/` → 200 (27,557
  bytes of HTML), `/api/config` → 200 with every secret redacted and no raw
  credential in the payload, `/api/token` → 200, JWT HS256-signed, TTL exactly
  3600 s, grants scoped to one room, no secret in the payload. That matches
  `RIME_EVIDENCE.md:196` word for word. Credential handling is genuinely good:
  only the signed JWT reaches the browser.
- **The acceptance harness is reproducible.** A fresh run differs from the
  committed `evidence/reference-run/acceptance.md` in six lines: the timestamp,
  and the simulated backend's jitter (409 ms vs 401 ms). Nothing structural.
- **15/15 is real** and re-ran clean. So is the seeded fuzz, whose safety
  assertion recomputes staleness from the ticket's own generation rather than
  trusting the fence's verdict — that is the right way to write it.
- **Deleting the product data is noticed loudly.** Removing
  `src/waypoint/data/manifest.json` produces six `FileNotFoundError` errors in
  `test_dispatch.py` and `run_acceptance.py` exits 1.
- **All 12 local markdown links resolve** (I ran CI's checker locally).
- **Cold/warm labelling is correct.** I traced `recordStop()`: the first sample
  publishes `warmth: "cold"`, subsequent ones `"warm"`. That satisfies *"Label
  cached and uncached measurements separately."* The boundary taxonomy
  (`client_playout` / `server_flush` / `client_first_audio`) with an explicit
  refusal to average across boundaries is the single most rubric-aware thing in
  the repository.
- **Data hygiene is right.** The manifest is labelled `SYNTHETIC DATA` in its
  first field, street names are real but every house number, recipient, gate
  code and window is invented, and `docs/DATA.md` explains it.
- **`DEMO_SCRIPT.md`'s UI claims match the actual UI.** Shot 3 says to point at
  a green `SPEECH PROVIDER: RIME` banner; `web/index.html:330` renders exactly
  that, styled green. And its closing checklist (lines 237–243) maps
  one-to-one onto the PDF's seven required demo elements. HTML is escaped
  properly throughout.

---

## 5. The score

Against the PDF's actual weights. **65/100 on the artifact — but judged today
the submission is ineligible**, because the PDF lists *"Omits the required
demo"* as a disqualifier and `demo/` contains only `.gitkeep`. The band scores
below describe what exists.

| Band | Weight | Score |
|---|---:|---:|
| Problem and necessity of voice | 25 | **23** |
| Hard voice engineering | 25 | **19** |
| Rime integration and voice experience | 20 | **12** |
| Evidence and reproducibility | 20 | **11** |
| Demo clarity | 10 | **0** |
| **Total** | **100** | **65** |

**Problem and necessity of voice — 23/25.** This is the strongest band and
close to maximal. The user is specific and the constraint is physical and
legal, not stylistic: a driver with both hands on the wheel who in most
jurisdictions may not touch a screen. *"Remove speech and there is no product
left"* is not a slogan here, it is the actual situation, and the PDF's test —
*"Removing speech would make the product materially worse"* — is met by a wide
margin. Better still, the chosen hard problem is one that **cannot exist in a
text product**: barge-in during in-flight tool work is a property of spoken,
half-duplex-in-the-user's-head interaction. The two points off are for a user
who is asserted rather than evidenced (no driver was consulted) and a dispatch
backend that is simulated, so "working product" means prototype — which the
PDF explicitly permits.

**Hard voice engineering — 19/25.** The turn fence is a genuine engineering
contribution, not a wrapper: a monotonic generation counter with a single
admission gate, turn-origin retirement so a dead turn's *second* tool call is
also fenced, an effect-boundary check placed where cancellation provably cannot
help, and re-anchoring that turns the safety mechanism into a cross-turn cache
so the common interruption gets *faster*. 757 lines, 112 tests, 70 seeded fuzz
runs with independent assertions. The README's precise accounting of what
LiveKit already does — quoting `agent_activity.py` and naming the three
remaining gaps — is the mark of someone who read the source instead of guessing,
and it means the contribution is not overclaimed. The six points off are for
the band's own words, *"solved under realistic conditions."* Every barge-in
this fence has ever seen was a Python attribute being flipped in a test
harness. It has never met real audio, real STT endpointing, real interruption
timing, or a real Rime stream; and sub-claim (c) depends on word timestamps
that have never arrived. The PDF's full-duplex example asks you to verify
*"queued Rime audio stops promptly"* — a runtime property no offline harness
can establish.

**Rime integration and voice experience — 12/20.** Rime is central and sole:
no fallback TTS, and the WebSocket transport is a *functional dependency* of a
core feature rather than a preference, which is a stronger integration story
than most submissions will have. Model, voice, language, audio format and
transport are all correct against the live catalog and the pinned plugin, and I
verified the shipped path reaches `wss://users-ws.rime.ai/ws3` and authenticates.
The coda/mistv2 bracket-control trade-off is a real product decision, resolved
in the honest direction — a model-portable respelling layer, with
`phoneme`-on-`coda` failing at startup instead of silently no-opping. The
banner and console disclosure is precisely what *"make the active speech
provider observable"* asks for. Eight points off for two things. First, the
endpoint — one of six fields the PDF names explicitly — is misstated on all
four disclosure surfaces (F2), and `build_tts`, the function that produces it,
has no test. Second, and larger: half this band is *voice experience*, and
**nothing about the voice has ever been experienced.** No clip has been
rendered, `audio_rendered` is `false`, the listening notes are `TODO`, and
there is no audio file of any kind in the repository. *"The output is clear and
appropriate"* is currently an assertion.

**Evidence and reproducibility — 11/20.** Bimodal, and worth separating.
Where no credentials are needed this is the best-evidenced hackathon submission
I have audited: 350 tests, six acceptance scenarios with 36 checks defined
before the demo, verified reproducible; a mutation suite that genuinely earns
15/15 and re-runs clean; fuzz assertions written independently of the code
under test; measurement boundaries named, separated and never averaged across;
`_unverified_` labels applied honestly rather than quietly dropped; an explicit
"what we are not claiming" section. That is most of what the band asks for and
it is why this is not a low score. Where credentials are needed there is
nothing at all, and it is not for want of trying — it is F1. Zero Rime
measurements, two of §4's four promised artifacts missing, the other two
`_unverified_`, and by the PDF's own rule (*"Unverified performance numbers
receive no credit"*) the entire latency story scores zero as it stands. Add
F5: no repository, so no *committed* artifacts in the sense the band means, and
a CI pipeline that would have produced third-party-verifiable evidence sits
unrun. Add F4a and §3: two of the suite's own guarantees are weaker than
advertised.

**Demo clarity — 0/10.** There is no demo. `demo/.gitkeep`, 0 bytes. I am
scoring what exists, and this also trips the eligibility gate. It should be
said clearly that this is *not* a planning failure: `DEMO_SCRIPT.md` is one of
the best demo scripts I have read — 4:30 shot by shot, every spoken line
written out, timings, equipment warnings (wired headset, *"the mic will hear
the agent and the barge-in detector will fire on the agent's own voice"* — that
is someone who has thought about the failure mode), a dry-run instruction, and
a closing checklist mapped to the PDF's seven required elements. Its UI claims
match the real console. A nervous person could record this in one or two takes.
They cannot start, because instruction one is `python scripts/preflight.py #
must exit 0`. Recorded as written, this band is an 8.

**Where this goes.** Record the demo from the existing script with no code
changes: **~74**. Land F1 and F2, re-run Lanes B and C to produce real cold/warm
latency numbers and saved clips, push to GitHub: **~82**.

### The single change with the best points-per-hour

**Fix F1 — `synthesize()` → transport-aware `stream()`, plus
`http_context.open()`, across the four scripts. One shared helper, four call
sites, 45–60 minutes.**

I considered recording the demo instead, since that is worth more raw points
(ineligible → eligible, +8). But F1 is *upstream of it*: `DEMO_SCRIPT.md`'s
first gate is `preflight` exiting 0, and a nervous person following the script
on one take will not skip instruction one — they will spend forty minutes
debugging a Rime API key that is fine, which is the worst possible use of the
last hour before a deadline. Fixing F1 first is what makes the demo
recordable *as scripted*.

It is also the highest-leverage single change on the scoreboard, because it is
the only thing standing between this project and every Rime-dependent number
it has already built the machinery to collect:

- `preflight.py` exits 0 → `DEMO_SCRIPT.md` gate 1 passes, and
  `SUBMISSION.md`'s last eligibility checkbox becomes tickable.
- `measure_latency.py --compare-transport` → real cold/warm time-to-first-audio
  on **both** transports, which is the evidence for the README's claim that
  *"the WebSocket path is not a preference, it is a dependency"* — currently
  unmeasurable, and the WS arm is the shipped one.
- `measure_pronunciation.py` (drop `--no-audio`) → **saved clips**, which the
  PDF requires in as many words: *"hold the model and voice constant, render at
  least two text variants, save the clips, and explain which wording or
  punctuation changed the result."* The script already renders three strategies
  × eight fixtures × two models and holds the voice constant per model. All the
  hard work is done; the synthesis call is the only broken part.
- `measure_heard_accuracy.py` → the estimator-error number, which is the only
  quantitative support for sub-claim (c).
- Lanes B and C stop being dead ends: 120 person-minutes recovered, and
  `docs/MEASUREMENTS.md` and `docs/LISTENING_NOTES.md` become fillable.

That converts roughly 13 points across the two 20% bands and unblocks the 10%
band. Nothing else available for an hour comes close.

---

## 6. What I would cut

Be willing to be unpopular. The honest one-line summary of this project is:
**it is over-engineered in the middle and empty exactly where it scores.**
9,581 lines of Python and 2,519 lines of markdown across twelve documents, and
zero seconds of audio. Every cut below buys time for §5's fix, the demo, and
`git push`.

1. **Cut `scripts/build_lexicon.py` and the phoneme lexicon entirely** (189
   lines, plus `WORKFLOW.md` B3's 10 minutes). Verified dead: Rime's Phonemize
   API is `POST optimize.rime.ai/phonemize` and takes raw audio bytes; the
   script posts JSON text to three other URLs. The shipped `respell` strategy
   needs no phonemes and the README already says the column ships empty on
   purpose. Delete the script, keep the strategy, fix the one README sentence
   (F6). Do not "fix" it — synthesise-then-phonemize is real work for a feature
   that is off by default.
2. **Cut the blind listening protocol from 25 minutes to a 3-row spot check.**
   `docs/LISTENING_TEST.md` plus `docs/LISTENING_NOTES.md` specify a
   provider-blinded, multi-listener procedure. The PDF only requires a
   benchmark-grade listening test *if the project is a benchmark*, and this is
   not one — under "How to prove the claim" it asks for two rendered variants,
   saved clips, and an explanation of what changed. Once F1 lands, render the
   clips and have one person write three honest lines about Gough, Guerrero and
   Divisadero. Ship it labelled `n=1, exploratory`, which the PDF explicitly
   permits. Saves ~40 minutes.
3. **Cut `mistv3` from the pronunciation sweep** and from the supported-model
   tuple's marketing. The demo ships `coda`; `mistv2` earns its place as the
   "before" arm that demonstrates the bracket-control trade-off. A third model
   triples render time and clip count for no rubric credit.
4. **Stop writing documentation. Now.** Twelve markdown files. A judge with ten
   minutes reads `README.md`, possibly `RIME_EVIDENCE.md`, and watches the
   video. `docs/THREAT_MODEL.md`, `docs/VERIFICATION.md`, `docs/ARCHITECTURE.md`,
   `docs/DATA.md`, `docs/LISTENING_TEST.md` and `docs/MEASUREMENTS.md` are
   well-written and earn, between them, close to nothing that the README does
   not already earn — they are the "over-engineered in the middle." Do not
   delete them; they are written and they cost nothing to leave in place. But
   the next paragraph anyone writes should be in `docs/MEASUREMENTS.md` under a
   real number, or not at all.
5. **Cut the CI file's priority until the repo is on GitHub — then it is free.**
   Right now `ci.yml` is 175 lines of dead weight and `README.md:3` renders a
   broken badge advertising it. Five minutes of `git init` and `gh repo create`
   converts the whole file into third-party-verified evidence and turns the
   badge green. Until then, no further CI work: adding a job to a pipeline that
   cannot run is the purest form of effort that earns nothing in this
   repository.

One thing I would **not** cut, against the obvious temptation: the browser
fence board. It is the only artifact that makes the central claim *visible* —
you cannot hear that a stale result was withheld, only that the agent stayed
quiet — and `DEMO_SCRIPT.md` builds two of six shots on it. It is also already
finished and verified working. Leave it alone.

---

## Reproducing this audit

```bash
pip install -e ".[dev]"

pytest                                    # 350 passed
python evidence/run_acceptance.py         # 6/6 scenarios, 36 checks
python evidence/mutation_test.py          # 15/15 caught   (~162s)
python evidence/mutation_test_ii.py       # 3/12 caught    (~161s)  <-- §3

# F1a, no credentials, no network:
RIME_API_KEY=dummy python -c "from waypoint.config import load_settings; \
from waypoint.agent import build_tts; build_tts(load_settings()).synthesize('x')"

# F1, end to end, no credentials:
RIME_API_KEY=dummy python evidence/measure_heard_accuracy.py --cuts 3; echo $?

# F2, no credentials:
RIME_API_KEY=dummy python -c "from waypoint.config import load_settings; \
from waypoint.agent import build_tts; s=load_settings(); \
print('actual :', build_tts(s)._ws_url()); \
print('claimed:', s.to_dict()['rime']['base_url'])"

# F4b — planted key in a skipped directory (cleans up after itself):
python -c "
import sys, pathlib, secrets; sys.path.insert(0,'scripts')
from secret_scan import scan
# built at runtime so this document contains no key-shaped literal of its own
k = 'RIME_API_KEY=rk_' + 'live_' + secrets.token_hex(16)
for d in ('evidence/results', 'evidence'):
    p = pathlib.Path(d)/'probe.json'; p.write_text('{\"n\": \"%s\"}' % k)
    print(f'{d:18s} found =', any('probe' in f.path for f in scan(pathlib.Path('.'))))
    p.unlink()"

# F10 — the rule versus LiveKit's own class names:
python -c "
import sys, pathlib; sys.path.insert(0,'scripts')
from secret_scan import scan_text
for n in ('ConnectionError','StatusError','TimeoutError','ConnectOptions'):
    s = 'API' + n
    print(f'  {\"FLAGGED\" if scan_text(pathlib.Path(chr(120)+chr(46)+chr(109)+chr(100)), s, chr(120)) else \"clean\":8s} {s}')"

# F5:
git rev-parse --is-inside-work-tree
```

## Findings index

| | Finding | Confirmed | Fix estimate |
|---|---|---|---|
| **F1** | No script can make a Rime API call (two bugs, four call sites) | yes, offline | 45–60 min |
| **F2** | Disclosed endpoint wrong on all four surfaces | yes, offline + live 401 | 10 min |
| **F3** | Mutation suite does not cover the wiring layer (9/12 survive) | yes, runnable | 25 min |
| **F4** | Secret-scan's repo test cannot fail; `results/` unscanned | yes, offline | 10 min |
| **F5** | Not a git repository; CI and badge dead | yes | 5 min |
| **F6** | `build_lexicon.py` targets a nonexistent endpoint shape | yes, vs Rime docs | 5 min |
| **F7** | Four document defects (A6 table, bug count, `.[web]`, TODO docs) | yes | 10 min |
| **F8** | Client barge-in stopwatch may under-sample | **unconfirmed** | 15 min |
| **F9** | Mutation-harness restore reported a false dirty tree | **not reproduced** | 5 min |
| **F10** | Scanner flags LiveKit's own exception names; hook blocks | yes, offline | 10 min |

Total for F1–F7 and F10: **a little over two hours**, and it moves two 20%
bands and the 10% band. F5 and F7 are twenty minutes between them and should
be done first because they are pure upside with no risk of breaking anything.
