# HANDOFF — everything you need to know about this project

**Read this first. It is written to be the only file you need.**

If you are a person who just inherited this repository, or a language model
that has been handed it with no other context, this document gives you the
whole thing: what it is, why it was built this way, what is proven, what is
not, what is left to do, and how to run every part of it. Everything else in
the repository is detail underneath one of the headings below.

It is deliberately long. Skimming the headings takes two minutes; reading it
properly takes twenty and replaces a day of archaeology.

---

## Table of contents

1. [The thirty-second version](#1-the-thirty-second-version)
2. [What the competition asks for](#2-what-the-competition-asks-for)
3. [The product, and why it has to talk](#3-the-product-and-why-it-has-to-talk)
4. [The hard problem we chose](#4-the-hard-problem-we-chose)
5. [How the solution works](#5-how-the-solution-works)
6. [The code, file by file](#6-the-code-file-by-file)
7. [How to run everything](#7-how-to-run-everything)
8. [What is proven, and how](#8-what-is-proven-and-how)
9. [What is NOT proven — read this before claiming anything](#9-what-is-not-proven--read-this-before-claiming-anything)
10. [The three adversarial audits](#10-the-three-adversarial-audits)
11. [What is left to do](#11-what-is-left-to-do)
12. [Conventions, rules and traps](#12-conventions-rules-and-traps)
13. [If you are a language model working on this](#13-if-you-are-a-language-model-working-on-this)

---

## 1. The thirty-second version

**Waypoint** is a hands-free voice assistant for delivery drivers. You talk to
it, it talks back. It reads out your next stop, gate codes, ETAs, and marks
deliveries done.

The interesting part is not that it talks. It is what happens when you
**interrupt** it.

A driver interrupts constantly — that is what talking while driving looks like.
And a voice agent that can be interrupted can end up saying something that is no
longer true: it starts looking up the gate code for Oak Street, you cut in and
say "skip Oak, go to Pine", and the Oak Street lookup — already in flight —
comes back and gets read aloud anyway. Worse, if the interrupted turn had
called "mark this delivered", the stop is *closed*, and cancelling the task does
not help because the write already happened.

Waypoint fixes this with a thing called the **turn fence**. Every tool call is
stamped with the conversational turn that asked for it, and one gate decides
whether its answer is still allowed to reach the driver. If the turn is dead,
the answer is discarded before it can be spoken, and an irreversible action is
refused before the call is made.

That is the contribution. Everything else in the repository exists to prove it
works, or to make it demonstrable.

**Stack:** Python · LiveKit Agents 1.7.1 (transport, turn detection) · **Rime**
(all spoken output) · Deepgram nova-3 (speech-to-text) · GPT-4.1-mini (the
reasoning).

---

## 2. What the competition asks for

DataForge 2026, Rime track. The brief (`Rime PS.pdf`, kept outside this repo)
scores five bands:

| Band | Weight | What it means |
|---|---|---|
| Problem and necessity of voice | 25% | Is this genuinely a voice product, or a chatbot with a speaker bolted on? |
| Hard voice engineering | 25% | Did you pick a real voice-specific problem and solve it? |
| Rime integration and voice experience | 20% | Is Rime used properly and does it sound right? |
| Evidence and reproducibility | 20% | Can someone else check your claims? |
| Demo clarity | 10% | Can a judge see it work in five minutes? |

And it lists **eligibility failures** — things that disqualify you outright
regardless of score:

- Omitting the required demo video
- Exposing a live credential or other secret
- A model/voice/language combination that fails the event preflight
- Unverified performance numbers claimed as verified

Those four constraints explain most of the odd-looking decisions in this
repository. There is a credential scanner wired into a git hook. There is a
preflight script. Every number is labelled with the boundary it was measured
at, and anything unmeasured says `_unverified_` rather than guessing.

**The demo video is recorded** — [youtu.be/EChOFjIuyNM](https://youtu.be/EChOFjIuyNM).
That was the one eligibility failure standing, and it is closed.

---

## 3. The product, and why it has to talk

The user is a delivery driver, mid-route, both hands on the wheel.

- They **cannot look at a screen** — in most jurisdictions they legally must not.
- They **will not ask twice.** If the answer is slow or wrong they give up and
  guess.
- They are **interrupting constantly**, because that is what a conversation
  looks like when you are doing something else with your attention.

Take the voice away and there is no product left. That is the test the brief
actually applies: not "does it use speech" but "would removing speech degrade
this, or delete it?" For a driver with both hands occupied, it deletes it.

The dispatch data (stops, addresses, gate codes) is synthetic and lives in
`src/waypoint/data/manifest.json`. Street names are real San Francisco streets
on purpose — *Gough*, *Guerrero*, *Divisadero* — because the pronunciation
problem is only interesting if the words are genuinely hard.

---

## 4. The hard problem we chose

**Barge-in during in-flight tool work.**

Here is the failure, concretely:

1. Driver: *"How long to Guerrero?"*
2. Agent starts an ETA lookup. It takes about two seconds.
3. Agent starts speaking: *"Guerrero is about..."*
4. Driver interrupts: **"No — mark Gough delivered instead."**
5. The Guerrero lookup finishes and returns.

Without a fence, step 5's answer gets spoken into a conversation that has moved
on. The driver hears an ETA for a stop they just abandoned. If step 2 had been
`mark_delivered` instead of a lookup, a real stop is now closed and nobody knows.

**What LiveKit already does, stated honestly.** We read the framework source
rather than guessing. `agent_activity.py` deliberately *retains* the outputs of
tools that were interrupted, adding them to the chat context with
`reply_required=False`. That is a reasonable default — the information might
still be useful next turn — but it means the framework does not solve this, and
it means an interrupted tool result is still sitting in the model's context on
the following turn. The fence is what makes that safe.

**Why cancellation is not enough.** By the time a cancellation reaches the
dispatch backend, the write has already returned 200. You cannot un-write it.
So the fence checks *before* the effect, not after — and for the narrow window
where a write is genuinely already in flight, it reports
`COMMITTED_BUT_UNCONFIRMED` and tells the driver, rather than pretending.

---

## 5. How the solution works

Three sub-claims, all in `src/waypoint/fencing.py` (which is pure Python with
no dependencies, and is the file to read first).

### (a) A stale *read* is never spoken

Every tool call gets a **ticket** stamped with the current generation counter
and the id of the speech turn that requested it:

```python
ticket = fence.issue(name, args, policy, origin=speech_handle.id)
```

When the driver barges in, `fence.bump_for(cause, reason)` advances the
generation **and retires that turn's origin**. When the tool result comes back:

```python
decision = fence.admit(ticket)   # terminal, at-most-once
```

If either the generation moved on *or* the ticket's origin turn was retired,
the result is `FENCED_STALE` and the agent returns a marker string instead of
speakable text.

Two independent supersession causes matter, and the second was a real bug found
in testing: the generation advances *once* per barge-in, so a *second* tool
call from the same dead turn still looked fresh. Retiring the origin closes it.

### (b) A stale *write* never commits

Writes use two gates, not one:

- `fence.check(ticket)` — non-terminal, called at the **effect boundary**, right
  before the backend call.
- `fence.admit(ticket)` — terminal, called at the **speech boundary**, when the
  result is about to be spoken.

So an interruption that lands while the tool is thinking stops the write from
happening at all. This is checked in the acceptance suite against the dispatch
backend's **mutation log** — what the system actually did — not against what
the agent said.

`ReanchorPolicy` controls whether a superseded call may be re-attached to the
new turn: `DISCARD` (default), `REANCHOR_IF_ARGS_MATCH` (a repeated identical
read is a free win), or `NEVER`. **All three write tools are `NEVER`.**

### (c) The agent knows what the driver actually heard

When speech is cut off mid-sentence, the words after the cut were *generated*
but never came out of the speaker. If the agent believes it said them, it will
never repeat them — so the driver never gets the gate code.

Rime's WebSocket path returns **word-level timestamps**. `heard.py` uses them to
compute the exact boundary between spoken and unspoken words, and writes a
`[playback record]` system message so the model's next turn knows the truth.
Badged `EXACT` when timestamps are present and `ESTIMATED` when they are not.

**This is the specific reason the project runs on Rime's WebSocket path rather
than plain HTTP.** It is a real integration argument, not a checkbox.

---

## 6. The code, file by file

```
src/waypoint/
  fencing.py      THE CORE. Pure, no dependencies, ~760 lines. Read this first.
  agent.py        LiveKit wiring. Tools, transcription_node, observers, entrypoint.
  heard.py        Heard-not-said reconciliation from word timestamps.
  pronounce.py    Respelling layer: "Gough" -> "Goff", codes digit-by-digit.
  dispatch.py     Fake dispatch backend with a mutation log and injectable latency.
  config.py       Settings, env loading, the disclosure banner.
  metrics.py      Latency samples, labelled by measurement boundary.
  prompts.py      The system prompt. Written-for-the-ear rules live here.
  data/manifest.json   Synthetic stops.

evidence/
  run_acceptance.py       6 scenarios, 36 checks, no keys, no network. THE artifact.
  mutation_test.py        15 deliberate bugs in src/. Proves the tests bite.
  mutation_test_ii.py     19 more: wiring, gates, prompts, and the harness itself.
  _rime.py                Transport-aware Rime helper. Everything that calls Rime uses it.
  measure_latency.py      Time-to-first-audio. NEEDS A RIME KEY.
  measure_pronunciation.py Renders the corpus for listening. NEEDS A RIME KEY.
  measure_heard_accuracy.py Quantifies the exact-vs-estimated gap. NEEDS A RIME KEY.
  results/                Committed artifacts. Currently honest about being empty.

scripts/
  preflight.py    Run before recording. Certifies the shipped path end to end.
  secret_scan.py  Credential scanner. Wired into the pre-commit hook.
  save.sh / save.ps1   One-command "commit and push my work" for non-git people.

web/
  server.py       Serves the browser console and mints LiveKit JWTs.
  console.html    The demo UI: fence board, heard-not-said panel, latency panel.

tests/            628 tests.
docs/             Architecture, threat model, data, listening-test method, audits.
team/             Internal. Workflow and worksheets. Not for judges.
```

**If you read only one file, read `src/waypoint/fencing.py`.** It is
self-contained, heavily commented, and every design decision is explained where
it was made.

---

## 7. How to run everything

### Setup (once, five minutes, no credentials needed)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

### The offline half — works on any laptop, no API keys at all

```bash
pytest                               # 628 tests, ~25s
python evidence/run_acceptance.py    # 6/6 scenarios, 36 checks
python evidence/mutation_test.py     # 15/15 deliberate bugs caught  (~6 min)
python evidence/mutation_test_ii.py  # 19/19 more                    (~4 min)
python scripts/secret_scan.py        # must say "clean"
python -m waypoint.agent --print-config   # the disclosure banner
```

**Everything above requires no credentials and no network.** That is the whole
design of the evidence: a judge can check the central claim on their own
machine without our keys.

### The live half — needs credentials

Copy `.env.example` to `.env.local` and fill in four values:

```
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET   # livekit.io, free tier
RIME_API_KEY                                        # rime.ai, free tier
```

`.env.local` is gitignored and the secret scanner blocks a commit that contains
a key. **Never put a real key in any other file.**

Then:

```bash
python scripts/preflight.py     # must exit 0 before you record anything
python web/server.py            # terminal 1 - open http://localhost:8080
python -m waypoint.agent dev    # terminal 2
```

---

## 8. What is proven, and how

This section is the honest inventory. It matters more than it looks, because
the brief gives 20% to evidence and gives no credit for unverified claims.

**628 tests.** 112 of them are on the fence alone, and 70 of those are seeded
fuzz runs — random orderings of issue / interrupt / resolve / cancel, checking
after *every single operation* that nothing stale got through. The safety
assertion is computed independently of the code under test, so it cannot agree
with a bug by construction.

**Six acceptance scenarios, 36 checks, offline.** These drive the real agent
code against the real fence and inject the barge-ins themselves. A1 proves a
stale read is never spoken. A2 proves a stale write never commits — checked
against the backend's mutation log. A3 proves the in-flight write case is
reported honestly rather than hidden.

**Two mutation harnesses, 34 targets, 34 caught.** This is the part worth
understanding. "628 tests pass" is not evidence — a suite that stays green when
you break the thing it guards is worse than no suite. So both harnesses
deliberately break the code (make the fence admit stale results, skip the check
before an irreversible write, disable barge-in entirely, read gate codes as
quantities) and require the suite to go red for every one. It does, 34 times out
of 34.

**Six of those 34 are bugs we actually wrote and shipped**, later found and
turned into permanent tests.

**CI on hardware nobody on this team controls.** GitHub Actions runs all of the
above on every push, across Linux and Windows, on Python 3.10 and 3.12, with
**no secrets block in the workflow** — which is the argument, not an oversight.

---

## 9. What is NOT proven — read this before claiming anything

**This is the most important section in this document.** Overclaiming is a
listed disqualifier, and it is also just wrong.

1. **The committed Rime artifacts are still the failed keyless run.** Audio
   *has* now been synthesised — Akshat ran the latency and pronunciation
   scripts against a live key on 2026-09-07 — but the generated reports were
   never uploaded from that machine. So `evidence/results/latency.md` still
   ships with an empty results table and the two `401`s that produced it, and
   `evidence/results/pronunciation/report.md` still ships with `Audio rendered:
   false` and every verdict `_unverified_`. The real numbers are transcribed by
   hand in [`team/MEASUREMENTS.md`](team/MEASUREMENTS.md) and
   [`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md), with that provenance
   gap stated at the top of both. Hand-transcribed numbers are weaker evidence
   than a committed artifact. Do not present them as the artifact.

2. **No human has ever spoken to this agent.** Every barge-in claim is proved
   against a Python attribute flipped in a test harness. Whether LiveKit's VAD
   fires correctly on a real interruption, in a real room, is a question only a
   live session answers. The demo video shows the product working; it is not a
   measurement of VAD behaviour under load.

3. **The pronunciation verdicts are one listener, and they are mixed.** Akshat
   listened on 2026-09-07. "Gough" does come out as "Goff". But respelling made
   *Guerrero* and *Noe* worse on `coda`, and the strongest result for the layer
   is on `mistv2`, which read `gate code 4417` as "four thousand four hundred
   and seventeen" without it. One listener, one device, and he knew what each
   clip was supposed to say. The clips themselves were not committed.

4. ~~There is no demo video.~~ **Recorded** —
   [youtu.be/EChOFjIuyNM](https://youtu.be/EChOFjIuyNM).

If you are writing anything user-facing about this project — a README, a
submission form, a pitch — **do not claim any of the four above until someone
has actually done them.** A modest verified number beats an impressive one
nobody can reproduce, and the brief says so explicitly.

---

## 10. The three adversarial audits

The project was reviewed three times by independent adversarial passes, each
told to tear it apart. All three found real defects. The reports are kept in
`docs/audits/` **including everything they found**, which looks reckless and
is not: they are the best evidence in the repository that the claims elsewhere
were actually tested.

- **AUDIT-2** (`docs/audits/AUDIT-2.md`) — found ten defects, all *outside* the
  tested modules. Its headline: no script in the repository could make a single
  Rime API call in any configuration, so the preflight everyone was told to run
  before recording could never have passed. Every finding is mapped to its fix
  in a header table.

- **AUDIT-3** (`docs/audits/AUDIT-3.md`) — asked the better question: *who tests
  the thing that manufactures the proof?* Nobody did. `evidence/` sat at 0%
  coverage with zero mutation targets, and one token change made all 36
  acceptance checks vacuous while the entire test suite stayed green. It also
  **defeated two of the fixes AUDIT-2 had prompted** — including a credential
  scanner that could not see a key sitting on the same line as an error class
  name, which is the exact shape of output this repository already ships.

- The prompt used for the third pass is kept at
  `docs/audits/RED-TEAM-PROMPT-3.md`, if you want to run a fourth.

**The pattern across all three is worth internalising:** each pass found things
in the region the previous one had no reason to look at. Pass 1 looked at tested
code, pass 2 at untested code beside it, pass 3 at the code that decides whether
the tests passed. If you are looking for what is still wrong, ask what region
nobody has named yet.

---

## 11. What is left to do

Every code finding from every audit is fixed. The four tasks that needed a
human, a microphone and a free API key have now been done.

| # | Task | Done? | By |
|---|---|---|---|
| 1 | **Record the 4:30 demo video** following `DEMO_SCRIPT.md` | ✅ [youtu.be/EChOFjIuyNM](https://youtu.be/EChOFjIuyNM) | Arrya |
| 2 | Get a Rime key, run `measure_latency.py`, record the numbers | ✅ [`team/MEASUREMENTS.md`](team/MEASUREMENTS.md) | Akshat |
| 3 | Render the pronunciation corpus and actually listen to it | ✅ [`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md) | Akshat |
| 4 | Fresh-clone verification — behave like a judge, write down every place the README lies | ✅ [`VERIFICATION.md`](VERIFICATION.md) | Rahul |
| 5 | Fix what #4 found, and submit | ✅ fixed; see below | — |

**What #4 found, and where it went.** The fresh-clone verification found three
README defects: `cd waypoint` (the repository does not clone under that name),
a Windows-pathed virtualenv activation inside a `bash` fence, and mutation
target counts of 13 and 28 against harnesses that declare 19 and 34. All three
are fixed, and `scripts/check_docs.py` now fails the build on each of them
rather than trusting the next reader to notice.

**Two things remain unrecoverable rather than undone**, and the documents say
so where they are relevant: the generated `latency.md`/`latency.json` from
Akshat's run were never uploaded, so `evidence/results/` still holds the
earlier keyless run that failed with two `401`s; and the pronunciation `.wav`
clips were listened to locally and never committed. The numbers and verdicts
are recorded with their method and their provenance gap stated plainly in
`team/MEASUREMENTS.md` and `team/LISTENING_NOTES.md`.

`team/WORKFLOW.md` splits these across three people with copy-paste
instructions. `team/START-HERE.md` is the plain-English explainer for that team.

---

## 12. Conventions, rules and traps

**Rules that are not negotiable**

- **Never commit a credential.** `.env.local` is gitignored; `.env.example`
  holds placeholders only; `scripts/secret_scan.py` runs in the pre-commit hook.
  The browser never receives an API secret — only a short-lived signed JWT from
  `web/server.py`.
- **Never claim a number nobody measured.** If it is not measured, write
  `_unverified_`. This is a disqualifier, and it is also the single most
  credible thing about this repository.
- **Never say "it works" without the command and its output.**

**Traps that have already bitten someone**

- `TTS.synthesize()` is the *HTTP* one-shot method. On a WebSocket-configured
  TTS it raises before any I/O. Use `evidence/_rime.py::synth()`, which selects
  on `tts.capabilities.streaming` — the public capability the framework itself
  dispatches on.
- Rime's two endpoints are **different hosts**: `https://users.rime.ai/...` for
  HTTP and `wss://users-ws.rime.ai/ws3` for WebSocket. Do not assume one is a
  path on the other.
- The plugin **upgrades** the transport from the URL scheme: a `wss://` base URL
  turns on WebSocket even with `RIME_USE_WEBSOCKET=false`. Always read
  `Settings.effective_use_websocket`, never the raw flag.
- Word timings ride on `frame.userdata[USERDATA_TIMED_TRANSCRIPT]`, not on the
  event object.
- Rime plugins need `livekit.agents.utils.http_context.open()` when used outside
  the agent worker.
- Coda **does not support** phoneme brackets. That is why the pronunciation
  layer respells rather than using IPA — it *runs* on every model. That is a
  portability claim, not an efficacy one: the one listening pass found it
  load-bearing for gate codes on `mistv2` and a net negative for street names
  on `coda`. See [`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md).
- `AgentSession.__init__` calls `asyncio.get_event_loop()`, so tests touching it
  must be `async def` or they pass alone and fail in a full run.
- The mutation harnesses edit source in place. **Never run two at once** — there
  is a lock, and a `--repair` flag if you ever see one report a dirty tree.

---

## 13. If you are a language model working on this

Some direct guidance, because this repository has specific failure modes.

**Verify before you assert.** Every claim in this project is meant to be backed
by a command and its output. Three audits found things precisely because they
ran the code instead of reading about it. If you are about to say "this works",
run it first. If you cannot run it, say that you could not.

**Do not trust the documentation over the code.** It has been wrong before —
that was pass 1's entire finding. When they disagree, the code is the truth and
the documentation is a bug.

**Do not trust a green test suite.** That is what the mutation harnesses are
for. If you add a behaviour, add a mutation target that breaks it and confirm
the suite goes red. A test written to kill one specific mutant is not the same
as a test that specifies behaviour — AUDIT-3 defeated two fixes precisely
because their tests pinned the example instead of the property.

**Check the installed package, not your memory of the API.** LiveKit Agents
1.7.1 and `livekit-plugins-rime` 1.7.1 are pinned exactly. Read the installed
source with `inspect.getsource`. Several bugs here came from a plausible-looking
API that does not exist in this version.

**Watch out for `\n` in shell heredocs.** Writing Python through a bash heredoc
mangles escape sequences and produces `SyntaxError: unterminated string
literal`. Use a file-writing tool instead, or `chr(10)`.

**The honest answer is usually the right one.** If something is unverified, the
correct move is to label it unverified and move on — not to soften it, and not
to quietly drop it. That instinct is worth more points here than another
hundred tests.

**Where to start reading:** this file, then `src/waypoint/fencing.py`, then
`evidence/run_acceptance.py`, then `docs/audits/AUDIT-3.md` for what nearly went
wrong.
