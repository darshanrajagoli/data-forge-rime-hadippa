# Waypoint

[![verify](https://github.com/darshanrajagoli/data-forge-rime-hadippa/actions/workflows/ci.yml/badge.svg)](https://github.com/darshanrajagoli/data-forge-rime-hadippa/actions/workflows/ci.yml)

**A hands-free dispatch copilot for delivery drivers, built on LiveKit Agents with Rime as the primary spoken output.**

## Deliverables

| | Link |
|---|---|
| **Demo video** (4:30, unlisted) | https://youtu.be/EChOFjIuyNM |
| **Repository** | https://github.com/darshanrajagoli/data-forge-rime-hadippa |
| **CI — every claim below, re-run on hardware we do not control** | [verify workflow](https://github.com/darshanrajagoli/data-forge-rime-hadippa/actions/workflows/ci.yml) · Linux + Windows × Python 3.10/3.12 · **no secrets block** |
| **Start here (whole project in one file)** | [`HANDOFF.md`](HANDOFF.md) |
| **Evidence, claim by claim** | [`RIME_EVIDENCE.md`](RIME_EVIDENCE.md) |
| **The submission** | [`SUBMISSION.md`](SUBMISSION.md) |
| **Acceptance run** (no credentials, one command) | [`evidence/reference-run/acceptance.md`](evidence/reference-run/acceptance.md) |
| **Adversarial audits, kept in full** | [`docs/audits/`](docs/audits/) |

Reproduce the whole offline half on your own machine, with no keys of ours:

```bash
pip install -e ".[dev]"
pytest                               # 686 passed
python evidence/run_acceptance.py    # 6/6 scenarios, 36 checks
python evidence/mutation_test.py     # 15/15 deliberate bugs caught
python evidence/mutation_test_ii.py  # 19/19 more
```

The driver has both hands on the wheel and their eyes on the road. They cannot
look at a screen — in most jurisdictions they legally must not — and they will
not ask twice. Removing speech from this product does not degrade it; it
deletes it.

---

## The hard voice problem

**A voice agent that supports barge-in can speak a stale answer.**

When the driver interrupts mid-sentence, three things are already in flight:
Rime is streaming audio for a sentence that will never finish playing, one or
more tool calls issued for the superseded turn are still running, and the chat
context is about to record an assistant turn claiming the driver heard the
whole thing.

For a driver, the consequence is not cosmetic:

> **Agent:** "Fourteen minutes to Oak Street, and the gate code is—"
> **Driver:** "No, skip Oak, go to Pine first."
> **Agent:** *(the Oak Street lookup returns)* "…four four one seven."

That is a gate code for a stop the driver has abandoned, and on the next turn
the agent will not repeat the Pine Street code because as far as it knows, it
already gave one. Worse, if the interrupted turn had called
`mark_delivered(Oak Street)`, the stop is now closed.

Waypoint's contribution is a **turn fence**: a monotonic generation counter
with a single admission gate that every tool result must pass before it can be
spoken or committed, plus **heard-not-said reconciliation** so the transcript
records the words that actually came out of the speaker
(`transcription_node` → `_reconcile_heard`, see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)).

### What LiveKit already does, precisely

This matters, because the rest is what Waypoint adds. On a barge-in,
`AgentActivity` cancels the tool executor task and then does this
(`livekit/agents/voice/agent_activity.py`):

```python
if speech_handle.interrupted:
    await utils.aio.cancel_and_wait(exe_task)

    # commit results of tools that finished despite the interruption (#3702), so
    # the next inference doesn't run them again
    ...
    self._agent._chat_ctx.insert(interrupted_tool_messages)
```

with each output rewritten by `_interrupted_tool_output` to carry
`reply_required = False`.

That is a sound design and it solves half the problem: it stops the
*immediate* stale utterance, and it keeps the result so the model does not pay
to re-run the lookup. Three gaps remain.

| Gap | Why it survives LiveKit's handling |
|---|---|
| **Deferred staleness** | The raw stale value stays in the chat context with nothing marking it superseded. `reply_required=False` suppresses this turn's reply, not the next one. The model reads `route_eta(Oak) -> 14 minutes` and states it as current. |
| **Committed side effects** | `reply_required` governs speech, not effects. Cancellation cannot protect a write: by the time `CancelledError` arrives, the POST that marked the delivery has returned 200. |
| **No re-anchoring** | The choices are run-to-completion-then-suppress, or cancel. There is no path for "this in-flight read is exactly what the new turn wants". A driver refining a request pays the lookup twice. |

Waypoint adds a generation stamp and admission gate for the first, an
**effect-boundary check** for the second, and **re-anchoring** for the third.
See [`src/waypoint/fencing.py`](src/waypoint/fencing.py) and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### The safety mechanism pays for itself

A fence that only discarded work would cost latency. Re-anchoring makes it a
cross-turn deduplicating cache: when the driver interrupts to *add* to a
request rather than replace it, the in-flight lookup is handed to the new turn
instead of being thrown away and re-issued. The common interruption gets
faster, not slower.

---

## Try it in 60 seconds, with no credentials

The claims about fencing are properties of the application, not of the
network, so they are verifiable offline:

```bash
git clone https://github.com/darshanrajagoli/data-forge-rime-hadippa
cd data-forge-rime-hadippa

python -m venv .venv
. .venv/bin/activate           # macOS/Linux
# .venv\Scripts\Activate.ps1  # Windows PowerShell
# . .venv/Scripts/activate     # Windows Git Bash

pip install -e ".[dev]"

pytest                                  # 686 tests, ~25s, no network
python evidence/run_acceptance.py        # the 6 acceptance scenarios
```

`run_acceptance.py` drives the real agent methods against the real fence,
injecting barge-ins at controlled points, and prints a pass/fail per claim.
Its output is committed at
[`evidence/reference-run/acceptance.md`](evidence/reference-run/acceptance.md).

---

## Run the real thing

### 1. Credentials

```bash
cp .env.example .env.local     # then fill it in
```

| Variable | Where to get it | Free tier? |
|---|---|---|
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | [cloud.livekit.io](https://cloud.livekit.io) | yes |
| `RIME_API_KEY` | [app.rime.ai/signup](https://app.rime.ai/signup) | yes |

STT and LLM run through **LiveKit Inference**, which uses the LiveKit
credentials above — no separate OpenAI or Deepgram key is required. To bring
your own, set the provider key and change `WAYPOINT_STT` / `WAYPOINT_LLM`.

### 2. Preflight

```bash
python scripts/preflight.py
```

This does not check a plausible configuration; it builds the real
`rime.TTS` from the real settings and synthesises real audio through it, so
the exact model, voice, language, endpoint, audio format and transport used in
the demo are the ones that were tested. It also runs the secret scan, the test
suite and the acceptance scenarios. **Exit code 0 means the demo can be
recorded.**

### 3. Run

```bash
python -m waypoint.agent console      # talk to it in the terminal, no browser
```

or, for the visual console:

```bash
pip install -e ".[dev,web]"           # the console needs the web extra
python -m waypoint.agent dev          # terminal 1
python web/server.py                  # terminal 2 -> http://127.0.0.1:8080
```

Also useful:

```bash
python -m waypoint.agent --print-config   # the exact shipped config, secrets redacted
bash scripts/install_hooks.sh             # pre-commit hook that blocks credentials
```

---

## Exact Rime configuration

Required disclosure, and the values `Settings.banner()` prints at startup on
every run:

| Setting | Value | Notes |
|---|---|---|
| **Provider** | **Rime** — primary spoken output | No fallback provider is configured. If one were, the banner would say so. |
| Model ID | `coda` | `RIME_MODEL`; also supports `mistv2`, `mistv3` |
| Speaker | `lyra` | `RIME_SPEAKER`. Default follows the model (`cove` for mist) |
| Language | `eng` | `RIME_LANG` |
| Endpoint | **`wss://users-ws.rime.ai/ws3`** | The WebSocket host. On the HTTP path it is `https://users.rime.ai/v1/rime-tts` — a *different host*, not another path. Overridable via `RIME_BASE_URL`. |
| Transport | **WebSocket** (`wss`), `segment=bySentence` | `RIME_USE_WEBSOCKET=true` |
| Audio format | PCM, 16-bit mono @ **22050 Hz** | `RIME_SAMPLE_RATE` |
| `speed_alpha` | `1.0` | `RIME_SPEED_ALPHA` |
| Plugin | `livekit-plugins-rime==1.7.1` | `rime.TTS(...)`, see `build_tts()` |

**The WebSocket path is not a preference, it is a dependency.** It carries
word-level timestamps, which is what routes through
`use_tts_aligned_transcript=True` into `Agent.transcription_node` and makes the
heard/unheard boundary exact rather than estimated. Setting
`RIME_USE_WEBSOCKET=false` still works, but heard-not-said degrades to the
approximate estimator and **the startup banner says so**.

### The Coda / Mist trade-off, and why respelling ships

Rime exposes two text-level controls and both are **mistv2-only**:
`phonemize_between_brackets` (`{h'El.o}`) and `pause_between_brackets`
(`<200>`). Coda — Rime's newest model, and the one their own LiveKit
quickstart recommends — **ignores both**.

For this product street-name pronunciation is a correctness requirement, not
polish: "Gow Street" sends the driver to a street that is not on their route.
So there are two strategies:

| `WAYPOINT_PRONUNCIATION` | Works on | Trade-off |
|---|---|---|
| `respell` **(default)** | every model | Portable; survives a model swap. Coarser than phonemes, and **measured as a net negative for street names on `coda`** — see below. |
| `phoneme` | mistv2, English mistv3 | Exact, but locks the product to mistv2 and silently no-ops elsewhere. |
| `none` | — | The "before" arm of the pronunciation experiment. |

Respelling ships because a voice product that breaks silently when the
provider ships a better model has a latent outage in it. `phoneme` is fully
implemented, and **pairing it with `coda` fails at startup** rather than
degrading quietly — a silent no-op is the exact failure this layer exists to
prevent.

**What the listening test says we should do next, and why we did not do it.**
The measured result is not "respelling works." It splits by token class, in
opposite directions, and the split is sharp. Respelling is *load-bearing* for
digit strings: `mistv2` with no respelling read `gate code 4417` as "four
thousand four hundred and seventeen", which a driver cannot key into a keypad.
Respelling is a *net negative* for street names on `coda`: that model read all
five street fixtures correctly on its own, and respelling made two of them
worse — Guerrero became "juh-rey-ro", Noe became "Now-uh". Shipping one global
strategy means one of those two results is being ignored, and right now it is
the second one.

The policy the data actually argues for is per-model and per-token-class:
**normalise digit strings on every model, and apply the street-name lexicon
only where plain text is known to fail.** That is a small change rather than a
rewrite — `render()` already runs the two as separate steps
([`src/waypoint/pronounce.py`](src/waypoint/pronounce.py)),
`normalize_numbers_for_ear()` for the numeric path and `apply_lexicon()` for
the street names, so the change is a model predicate on the second call and a
matrix row per model.

We scoped it and did not ship it, for one reason we think is the right one:
**the evidence is a single listener**, who built the lexicon and knew what each
clip was supposed to say ([`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md),
"Outside listener: None"). Turning n=1 into a shipped per-model behaviour would
be over-fitting a product to one person's ear, and it would replace a strategy
that is wrong in one known way with one that is wrong in ways nobody has
listened for. The honest state is that we measured our own default, found it
half-wrong, wrote down which half, and left the change to a second listener.
That listener is the highest-value work outstanding on this project.

The phoneme column of the lexicon **ships empty on purpose**. Rime's phoneme
alphabet is its own notation, and writing strings in it from memory would be
guessing dressed as precision.

We previously shipped a `scripts/build_lexicon.py` that claimed to populate it
from Rime's API. It has been deleted: it POSTed JSON text to three guessed
URLs, none of which is Rime's phonemize endpoint, so the promise was never
keepable. Populating that column properly means synthesising each word and
submitting the *audio* — real work, on a path the shipped `respell` strategy
does not need. Saying so is better than shipping a script that fails.

---

## Architecture

```
  browser (web/index.html)                    agent process
  ┌───────────────────────────┐              ┌──────────────────────────────────┐
  │ mic ──────────────────────┼──LiveKit────▶│ Deepgram nova-3 (STT)            │
  │                           │   WebRTC     │            │                     │
  │ speaker ◀─────────────────┼──────────────│            ▼                     │
  │   │                       │              │ gpt-4.1-mini (LLM)               │
  │   ├─ RMS meter            │              │            │                     │
  │   │  (client_playout)     │              │            ▼                     │
  │   │                       │              │  ┌──── TurnFence ─────────┐      │
  │ fence board ◀─────data────┼──────────────│  │ issue → check → admit  │      │
  │ config disclosure         │  waypoint.   │  └────────────┬───────────┘      │
  │ measurements ─────data────┼──▶ fence     │               ▼                  │
  └───────────────────────────┘  waypoint.   │  dispatch backend (synthetic)    │
                                  client     │               │                  │
                                             │               ▼                  │
                                             │  pronounce.render()              │
                                             │               │                  │
                                             │               ▼                  │
                                             │  Rime coda/lyra, wss, PCM 22k    │
                                             │      │                           │
                                             │      └─ word timestamps ──▶      │
                                             │         HeardTracker             │
                                             └──────────────────────────────────┘
```

| Module | Role |
|---|---|
| [`fencing.py`](src/waypoint/fencing.py) | The turn fence. Pure, no dependencies, 112 of the 686 tests. |
| [`heard.py`](src/waypoint/heard.py) | Heard-not-said reconciliation from Rime word timestamps. |
| [`pronounce.py`](src/waypoint/pronounce.py) | Lexicon, number-for-the-ear, model-compatibility gate. |
| [`agent.py`](src/waypoint/agent.py) | LiveKit wiring. `_read` / `_write` are the fence integration. |
| [`dispatch.py`](src/waypoint/dispatch.py) | Synthetic backend with configurable latency and a mutation log. |
| [`config.py`](src/waypoint/config.py) | Validation, disclosure banner, secret redaction. |
| [`metrics.py`](src/waypoint/metrics.py) | Measurement with the boundary stated on every number. |
| [`prompts.py`](src/waypoint/prompts.py) | System instructions, written for the ear. |

**Safety lives in code, not in the prompt.** The `SUPERSEDED_RESULT` marker
returned to the model is for conversational coherence only. A model that
ignored every marker still could not commit a stale write, because
`TurnFence.check()` refuses it before it executes.

---

## Evidence

| What | Command | Needs a key? | Output |
|---|---|---|---|
| The six acceptance scenarios | `python evidence/run_acceptance.py` | no | [`reference-run/acceptance.md`](evidence/reference-run/acceptance.md) |
| Test suite | `pytest` | no | 686 passing |
| The docs still match the repository | `python scripts/check_docs.py` | no | 8 checks |
| Rime time-to-first-audio, cold vs warm | `python evidence/measure_latency.py` | yes | **run 2026-09-07** — [`team/MEASUREMENTS.md`](team/MEASUREMENTS.md) |
| Pronunciation A/B, clips saved | `python evidence/measure_pronunciation.py` | yes | **run 2026-09-07** — [`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md) |
| Estimator error vs word timestamps | `python evidence/measure_heard_accuracy.py` | yes | **run 2026-09-07** — [`team/MEASUREMENTS.md`](team/MEASUREMENTS.md) |
| Barge-in to silence, at the ear | browser console, during a live session | yes | **not measured** |

The three credentialed runs happened on 2026-09-07. Their *generated* reports
were never uploaded from the machine that produced them, so `evidence/results/`
still holds an earlier keyless run that failed with two `401`s, and the numbers
live hand-transcribed in the two `team/` files above with that gap stated at the
top of each. Headline: **394 ms p50 warm time-to-first-audio** over WebSocket at
the `server_first_frame` boundary — which is not the driver's ear.

The full claim, acceptance test, procedure and limitations are in
**[`RIME_EVIDENCE.md`](RIME_EVIDENCE.md)**.

### The tests are checked too

`pytest` reporting 686 passing is not evidence on its own — a suite that stays
green when you break the code it guards converts absence of signal into
confidence. So there are two mutation harnesses, and between them 34 targets:

```bash
python evidence/mutation_test.py       # 15 targets, the tested core
python evidence/mutation_test_ii.py    # 19 targets, everything else
```

Each introduces one specific, plausible bug at a time, runs the whole suite
against it, restores the file, and **exits non-zero if any mutant survives**.
Both take an exclusive lock, refuse to start on an already-mutated tree, verify
every restore, and ship a `--repair` mode.

The second harness exists because the first one had a shape. All fifteen of its
targets land in code a unit test calls directly, and **9 of the first 12
mutations written against the wiring layer survived** — including
`interruption {"enabled": False}`, which disables the only feature this product
has. The whole suite as it stood then, all six acceptance scenarios and the
first harness's 15/15 stayed green with barge-in switched off.
`tests/test_wiring.py` and `tests/test_preflight.py` were written to close
that, and they did: mutant **B** of the second harness is that exact flag,
and it is caught today.

Current result: **15/15 and 19/19 — 34 of 34, none surviving.** Both run in CI.

### Verified continuously, on hardware we do not control

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the test suite, the
acceptance scenarios, the secret scan, the offline preflight and a
markdown-link check on **every push**, across `ubuntu-latest` and
`windows-latest` × Python 3.10 and 3.12.

The workflow has **no `secrets:` block and needs none** — which is the argument
rather than an incidental fact. If the central claim required our API keys,
neither GitHub nor a judge could check it. It doesn't, so both can. Each run
uploads its `acceptance.json` as a build artifact, so the evidence is dated and
attributable to a specific commit rather than to a screenshot.

### Measurement boundaries

Every number carries where its stopwatch stopped, and numbers from different
boundaries are never averaged:

- **`client_playout`** — the browser's own audio output going silent. Includes
  the network hop, the jitter buffer and the device. **This is what the driver
  experiences.**
- **`server_flush`** — the agent stopped handing frames to the transport.
  Earlier than the ear, and therefore flattering.
- **`client_first_audio`** / **`server_first_frame`** — the same distinction for
  response time.

Cold runs (first call of a session, carrying TLS and the WebSocket upgrade) are
labelled and reported separately from warm ones. Series with fewer than ten
samples carry an explicit caution: they are exploratory, not a service level.

---

## Known limitations

Stated because they are real, not because they are exhaustively mitigated.
The full analysis is in [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

1. **A write already in flight cannot be un-written.** The effect-boundary
   check runs immediately before the irreversible operation, so the exposure
   window is one backend call rather than the whole tool duration — but it is
   not zero. When it happens, the agent reports
   `COMMITTED_BUT_UNCONFIRMED` and tells the driver on the next turn. It does
   not pretend the write did not land. Acceptance scenario **A3** exercises
   this deliberately.
2. **The dispatch backend is synthetic.** No real customer, address, phone
   number or delivery exists in this repository and none is fetched at runtime.
   Street names are real San Francisco streets because the pronunciation work
   needs a genuinely hard corpus; house numbers, recipients, gate codes and
   windows are invented. See [`docs/DATA.md`](docs/DATA.md).
3. **The phoneme lexicon is empty and there is no script to fill it.** Under
   `WAYPOINT_PRONUNCIATION=phoneme`, every token falls back to its respelling
   and `Rendered.notes` says so. Filling it means synthesising each word and
   submitting the audio to Rime's phonemize endpoint — work the shipped
   `respell` strategy does not require, so it has not been done.
4. **Pronunciation intelligibility is not automatically verified, and the one
   human pass came back mixed.** `measure_pronunciation.py` renders and saves
   the variants; whether a driver hears the right street is a listening
   judgement. One listener scored the corpus on 2026-09-07
   ([`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md)): respelling was
   load-bearing for gate codes on `mistv2`, which read `4417` as "four thousand
   four hundred and seventeen" without it — and a **net negative** for street
   names on `coda`, where plain text was already correct and Guerrero and Noe
   got worse. The committed `results/pronunciation/report.md` is an earlier
   keyless run, so its rows still read `_unverified_`, never as passes.
5. **Barge-in detection quality is LiveKit's, not ours.** We use
   `interruption.mode="adaptive"` with `min_duration=0.4s`. False-positive
   interruptions from road noise are handled by
   `resume_false_interruption=true`, which is LiveKit's mechanism. In a real
   vehicle this would need road-noise-specific tuning we have not done.
6. **The client-side RMS silence detector has a 120 ms confirmation hold.** The
   reported barge-in time subtracts the hold, so it names the moment audio
   actually stopped rather than the moment we became confident — but it is
   still a threshold-based estimate, not a sample-exact one.
7. **Single language.** `RIME_LANG=eng`. Code-switching is not implemented.
8. **No persistence.** Dispatch state is in-memory and resets per session.

## Failure behaviour

| Failure | What happens |
|---|---|
| Rime unreachable | The session errors visibly and the console shows it. No silent fallback to another TTS — the brief requires the active provider be observable, and a hidden substitution would violate that. |
| A tool raises | The ticket is resolved as cancelled, the fence's accounting stays balanced, and the driver hears "That did not work" plus the reason. |
| A tool is cancelled by the framework | `CancelledError` resolves the ticket as `fenced_cancelled`. Nothing leaks. |
| Barge-in during a write | `COMMITTED_BUT_UNCONFIRMED` — see limitation 1. |
| An unknown street | A domain error, spoken plainly. Not an exception. |
| Config that would run but lie | Refused at startup (`ConfigError`) with the fix named. |
| Missing credentials | `--print-config` and the offline tests still work; connecting raises with the list of what is missing. |
| The visualiser dies | Observability is not allowed to break the session. Every publish is wrapped and swallowed; the fence audit log remains the source of truth. |

---

## Third-party services and licences

| Service | Role | Notes |
|---|---|---|
| **Rime** | Text-to-speech — the primary spoken output | `coda` / `lyra` / `eng` |
| **LiveKit Cloud** | WebRTC transport, rooms, turn detection | free tier |
| **LiveKit Inference** | STT (`deepgram/nova-3`) and LLM (`openai/gpt-4.1-mini`) | billed through LiveKit |

| Dependency | Version | Licence |
|---|---|---|
| `livekit-agents` (+ `rime`, `silero`, `deepgram`, `openai` extras) | 1.7.1 | Apache-2.0 |
| `livekit-client` (browser, via jsDelivr) | 2.22.2 | Apache-2.0 |
| `python-dotenv` | ≥1.1 | BSD-3-Clause |
| `aiohttp` | ≥3.10 | Apache-2.0 |
| `fastapi`, `uvicorn` (web extra) | ≥0.115, ≥0.30 | MIT, BSD-3-Clause |
| `pytest`, `pytest-asyncio` (dev extra) | ≥8.0, ≥1.0 | MIT, Apache-2.0 |

Waypoint itself is MIT — see [`LICENSE`](LICENSE). No model weights, datasets,
fonts or graphics are vendored. The synthetic manifest is original to this
repository.

## Configuration hygiene

- [`.env.example`](.env.example) contains placeholders only. No credential is
  committed.
- `.gitignore` covers `.env`, `.env.local`, `*.pem`, `*.key`.
- `scripts/secret_scan.py` runs standalone, from `preflight.py`, and from the
  pre-commit hook installed by `scripts/install_hooks.sh`. It has [its own
  test suite](tests/test_secret_scan.py) — a security control with no tests is
  not a control — covering both catching real keys and not crying wolf.
- No credential reaches the browser: `web/server.py` mints a 60-minute JWT and
  keeps the API secret in the server process.
- `Settings.banner()` and `Settings.to_dict()` redact every key, and a
  credential embedded in `LIVEKIT_URL`'s userinfo is stripped — the banner is
  printed to a terminal that gets screen-recorded.

## AI assistance disclosure

This project was built with AI assistance (Claude) for code, tests and
documentation. The turn-fence design, the Coda/Mist pronunciation trade-off and
the measurement-boundary discipline were arrived at by reading the primary
sources — the LiveKit Agents 1.7.1 source for interruption handling, and Rime's
documentation for model capabilities — and the specific `agent_activity.py`
behaviour quoted above was verified by reading that file, not recalled. Two
design bugs (fence-sync ordering, and turn-origin retirement) were found by the
test suite and the acceptance harness during development and are documented at
their fix sites.

## Repository map

| Path | What it is |
|---|---|
| **[`HANDOFF.md`](HANDOFF.md)** | **Start here.** The whole project in one file — what it is, what is proven, what is not, and how to run everything. Written to be the only file a new reader (or a language model) needs. |
| [`RIME_EVIDENCE.md`](RIME_EVIDENCE.md) | Every claim, with the command that checks it. Section 7 is the limitations, and it is honest. |
| [`SUBMISSION.md`](SUBMISSION.md) | The submission itself, mapped to the brief's rubric. |
| [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) | The demo, shot by shot, with every line written out. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the pieces fit, and why. |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | What the fence does not cover, analysed rather than asserted. |
| [`docs/DATA.md`](docs/DATA.md) | Where the synthetic manifest comes from. |
| [`docs/LISTENING_TEST.md`](docs/LISTENING_TEST.md) | The protocol for judging pronunciation by ear. |
| **[`docs/audits/`](docs/audits/)** | **Independent adversarial reviews, kept in full.** Each has a header mapping every finding to its fix. See below. |
| [`team/`](team/) | Internal working documents and worksheets. Not written for judges. |

### The audits

This repository ships every review that was written up, complete, including
everything they found. That is deliberate. A submission claiming to be
adversarially tested should be able to show the adversary's report.

- [`AUDIT-2.md`](docs/audits/AUDIT-2.md) — found ten defects, every one *outside*
  the tested modules. Headline: no script in the repository could make a single
  Rime API call in any configuration, so the preflight everyone was told to run
  before recording could never have passed.
- [`AUDIT-3.md`](docs/audits/AUDIT-3.md) — asked who tests the code that
  manufactures the proof. Nobody did: one token made all 36 acceptance checks
  vacuous while the whole suite stayed green. It also defeated two of the fixes
  AUDIT-2 had prompted, including a credential scanner blind to a key sharing a
  line with an error-class name.
- [`AUDIT-5.md`](docs/audits/AUDIT-5.md) — the pre-submission pass, run cold
  against the finished tree. It confirmed the measurements, the mixed
  pronunciation result and all six eligibility rules, and found that the
  documentation gate's own auto-fixer had been silently rewriting a sentence
  about a fixed moment in the past into a false claim about the present. Its
  verdict, its DO-NOT-FIX list and the reasoning behind each are kept whole.
- [`RED-TEAM-PROMPT-3.md`](docs/audits/RED-TEAM-PROMPT-3.md) — the prompt used
  for the third pass.
- [`RED-TEAM-PROMPT-4.md`](docs/audits/RED-TEAM-PROMPT-4.md) — aimed a fourth
  pass at the evidence-integrity layer added after audit 3, including
  `scripts/check_docs.py` itself. It was run by the author against their own
  work, which is the weak form, and it still found three fail-open holes in
  that gate plus a mixed measurement that had flattened into a success in three
  documents. All fixed.
- [`RED-TEAM-PROMPT-5.md`](docs/audits/RED-TEAM-PROMPT-5.md) — the prompt that
  produced `AUDIT-5.md`. It is written for convergence: it fixes a green-state regression contract up front,
  requires every finding to carry its own blast radius and verification
  command, and asks the reviewer to classify findings as FIX NOW / FIX IF TIME
  / DO NOT FIX so that a marginal improvement cannot break a green build the
  night before a deadline.

Every code finding from every pass is fixed. The two that were left open needed
a person and an API key, and both have now been done: the demo video is
recorded, and the Rime scripts were run against a live key on 2026-09-07. What
did *not* survive that run is the paperwork — the generated reports were never
uploaded, so `evidence/results/` still holds the earlier keyless run that failed
with two `401`s, and the measured numbers live hand-transcribed in
[`team/MEASUREMENTS.md`](team/MEASUREMENTS.md) and
[`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md) instead. That is weaker
evidence than a committed artifact and is labelled as such in both files and in
limitation 10 of `RIME_EVIDENCE.md`, rather than glossed.
