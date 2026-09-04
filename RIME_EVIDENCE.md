# RIME_EVIDENCE

The hard voice claim, the acceptance test that was written before the demo, the
procedure, the results, and what none of it establishes.

---

## 1. The claim

> **Under barge-in during in-flight tool work, Waypoint (a) never speaks a tool
> result belonging to a superseded turn, (b) never lets an irreversible
> operation commit after the turn that requested it was interrupted, and (c)
> records in the conversation history only the words that were actually played
> out of the speaker.**

Three sub-claims, because they have three different mechanisms and three
different failure modes. Each is separately falsifiable and separately tested.

| | Sub-claim | Mechanism | Falsified by |
|---|---|---|---|
| **a** | No superseded result is spoken | Generation stamp + admission gate (`TurnFence.admit`) | any spoken value traceable to a ticket whose generation is older than the current one, without a re-anchor |
| **b** | No irreversible write commits after supersession | Effect-boundary check (`TurnFence.check`) before the write | any entry in `DispatchBackend.log` written under a retired turn |
| **c** | History records what was heard | `Agent.transcription_node` collects the text and Rime's word timestamps; `WaypointAgent._reconcile_heard` cuts at the interruption and appends a playback record to the chat context | any word in the playback record whose audio never played |

### Why this is the right problem for this product

The driver is driving. They interrupt constantly — that is not rudeness, it is
what talking while operating a vehicle looks like. So barge-in is not an edge
case in this product; it is the normal case. And the cost of a stale answer is
not an awkward sentence, it is a delivery to the wrong address or a stop closed
that was never completed.

### What we are *not* claiming

- Not that LiveKit handles none of this. It handles part of it, precisely
  (§6).
- Not a barge-in stop latency figure as a service level. We report what we
  measured, with the boundary and sample size attached.
- Not that pronunciation is verified intelligible. That is a listening
  judgement and it is marked `_unverified_` until a human makes it.

---

## 2. The acceptance test

Defined before the demo was recorded. One command, no credentials, no network,
no microphone:

```bash
python evidence/run_acceptance.py
```

It drives the real `WaypointAgent` methods against the real `TurnFence` and the
real dispatch backend, injecting barge-ins at controlled points by flipping
`speech_handle.interrupted` — the same attribute the shipped code reads.

**Why offline.** Sub-claims (a), (b) and (c) are properties of the application,
not of the network. Making them depend on our API keys would make them
unreproducible by a judge. The claims that genuinely need Rime — stop latency
at the ear, pronunciation, word-timestamp accuracy — are measured separately
(§4) and clearly marked as requiring credentials.

**Pass criteria.** All six scenarios, all 36 checks. Exit code 0. Anything less
is a fail; there is no partial credit in the harness.

### Scenarios

| ID | What it does | The check that matters |
|---|---|---|
| **A1** | `eta_to("Gough")` in flight on a 400 ms backend; barge-in mid-lookup | returned string is `SUPERSEDED_RESULT`, contains no ETA value, and instructs the model not to state it *on a later turn* |
| **A2** | Turn already interrupted; call `mark_delivered`, `reschedule_stop`, `notify_recipient` | `DispatchBackend.log == []` — asserted against the backend, not against what was said |
| **A3** | `mark_delivered` past the effect check, then barge-in | the write **did** land, and the agent reports `COMMITTED_BUT_UNCONFIRMED` rather than pretending otherwise |
| **A4** | Identical `eta_to` ticket issued by the new turn after a bump | disposition `REANCHORED`, value equals a fresh lookup, one 400 ms round trip avoided |
| **A5** | Rime word timestamps at 300 ms/word; cut at 1500 ms | the unspoken gate code is absent from `to_chat_text()` |
| **A6** | Nine-turn conversation: reads, a barge-in, a refused write, a cancelled read, a committed write | `records == issued`, `in_flight == 0`, exactly one write committed and one refused |

`tests/test_agent.py` carries the matching *integration* checks —
`test_transcription_node_registers_the_real_text`,
`test_reconcile_records_what_was_heard` — which drive the agent's own pipeline
rather than the tracker directly. That distinction matters: see bug 3 below.

---

## 3. Result — offline, reproducible now

```
6/6 scenarios passed (36 checks)
```

Full output, regenerated on every run:
[`evidence/reference-run/acceptance.md`](evidence/reference-run/acceptance.md) ·
[`acceptance.json`](evidence/reference-run/acceptance.json)

### Test suite

```bash
pytest        # 573 passed in ~6s
```

| File | Tests | Covers |
|---|---|---|
| `test_fencing.py` | **112** | every fence invariant, plus 70 seeded fuzz runs |
| `test_secret_scan.py` | 66 | real keys in source *and* JSON, the vendor's own class names, and the tree walk itself |
| `test_pronounce.py` | 63 | numbers for the ear, lexicon, model-compatibility gate |
| `test_dispatch.py` | 34 | mutation log, stop resolution, synthetic-data guarantees |
| `test_config.py` | 29 | loud failures, disclosed degradations, secret redaction, endpoint derivation |
| `test_agent.py` | 28 | the `_read` / `_write` fence integration, and the heard-not-said pipeline end to end |
| `test_heard.py` | 22 | exact and estimated boundaries, chat-text truncation |
| `test_metrics.py` | 22 | cold/warm and boundary separation |
| `test_prompts.py` | 22 | that the agent is still told to speak for the ear |
| `test_wiring.py` | 16 | `build_tts` / `build_session` / `attach_observers` — whether barge-in is on at all |
| `test_preflight.py` | 11 | the gate that decides the demo may be recorded |

### The fuzz test is the load-bearing one

Hand-written tests prove the cases their author thought of. On a barge-in path
the bugs live in the orderings nobody thought of, so
`test_fuzz_random_interleavings_preserve_every_invariant` runs 40 seeded
sequences of 200 random operations (issue / retire / admit / cancel / check),
and after **every single operation** asserts:

- the accounting identity `issued == delivered + reanchored + fenced_* + in_flight`,
- that nothing was admitted whose generation was older than the current one
  *unless* it re-anchored to a live matching ticket, and
- that no `NEVER`-policy ticket ever crossed a turn boundary.

The safety assertion is written independently of the fence's own verdict — it
recomputes staleness from the ticket's own generation — so the test cannot pass
by agreeing with a bug in the code under test.

`test_fuzz_with_origins_never_leaks_a_write` adds 30 more runs where turns die
and keep issuing work.

### Ten bugs this found

Reported because "we wrote tests" is worth less than "the tests caught
something", and because the *pattern* is more useful than the list. Two
independent adversarial passes were run after this project was first declared
finished. Each found real defects. The second one found the worst.

**Found during development, by the suite itself**

1. **Fence-sync ordering.** `_read`/`_write` synced the fence *before* issuing
   the ticket, advancing the generation and then stamping the ticket with the
   new one — laundering a dead turn's request into a fresh one. Caught by
   `test_agent.py`.
2. **Turn-origin retirement.** The generation counter advances once per
   barge-in, so a *second* tool issued by an already-interrupted turn looked
   current. Caught by acceptance scenario **A2**, which committed two of three
   stale writes. Fixed by stamping each ticket with its originating
   `SpeechHandle.id`; `TurnFence._supersession_reason` now has two independent
   causes.

**Found by the first adversarial pass**

3. **Sub-claim (c) was never wired in.** `transcription_node` registered every
   utterance with an *empty string* and nothing ever called
   `HeardTracker.cut()`, so the reconciliation returned `""` and no playback
   record was ever written. All 22 module tests passed throughout, because they
   fed the tracker real text directly and never went through the agent. This is
   the exact failure mode of testing a component instead of a path.
4. **The error path bypassed the fence.** `except DispatchError` cancelled the
   ticket and returned a *speakable* string regardless of whether the turn was
   alive, so a superseded turn's error reached the driver. An error is a tool
   result; the headline claim covers it.
5. **The word-timestamp read used attributes that do not exist.**
   `ev.timed_words` / `ev.words` / `ev.alignment` are not on
   `SynthesizedAudio`. The measurement would have reported "no word timestamps
   arrived" on every run — its honest-failure path firing for a dishonest
   reason.

**Found by the second adversarial pass — the expensive ones**

6. **No script in the repository could make a Rime API call. Two bugs, four
   call sites.** `TTS.synthesize()` is the one-shot *HTTP* method and the Rime
   plugin raises unconditionally when the TTS was built for WebSocket — which
   is the shipped default. Separately, plugins need an HTTP context that only
   the agent worker opens. Together this meant `scripts/preflight.py` could
   **never exit 0**, in any configuration, with any credential — and
   `DEMO_SCRIPT.md`'s first instruction is *"do not proceed until preflight is
   clean"*. Two of four work lanes produced nothing. Not one audio sample had
   ever been rendered. Worse than the outage: preflight blamed the API key for
   a code bug, sending the reader to rotate a credential that was fine.
   Fixed by `evidence/_rime.py` — one transport-aware helper selecting on the
   public `tts.capabilities.streaming`, plus `http_context.open()` — wired into
   all four call sites. Verified against the live service: a dummy key now
   returns a real 401 over `wss://users-ws.rime.ai/ws3` instead of raising
   before any I/O. Tests: `tests/test_preflight.py` (11).
7. **The disclosed endpoint was the wrong host.** The banner, `/api/config`,
   the browser console and the README all reported `users.rime.ai` — the HTTP
   host — while the shipped WebSocket path streams from `users-ws.rime.ai`.
   `endpoint` is one of six fields the brief names explicitly, and the banner
   is printed to a terminal that gets screen-recorded. `Settings.endpoint` now
   derives from the transport, and
   `test_the_disclosed_endpoint_is_the_one_that_will_be_called` compares it
   against the URL the plugin will actually build.
8. **The wiring layer had no tests, and barge-in could be silently disabled.**
   `build_tts` / `build_session` / `attach_observers` — the code that decides
   which model speaks and *whether interruption is enabled at all* — was
   untested. 9 of the first 12 mutations written against it survived. Setting
   `interruption {"enabled": False}` left all tests, all six acceptance
   scenarios and the first mutation harness green with the product's only
   feature switched off. Fixed by `tests/test_wiring.py` (16), which asserts
   against constructed objects rather than the settings they came from.
9. **The credential scanner's own test could not fail, and it was blind to two
   things.** `test_this_repository_is_clean` asserts `scan()` returns nothing —
   so it passes *more easily* when the scanner is broken; a mutation making
   `scan()` return `[]` was invisible to all 40 tests. While fixing that, two
   more holes surfaced: `SKIP_DIRS` contained the bare word `results`, so
   `evidence/results/**` — the committed-artifact directory — was never walked;
   and the assignment rule matched `key = "..."` but not `"key": "..."`, so a
   credential in JSON was undetectable. Every artifact in that directory is
   JSON. **The two gaps hid each other.**
10. **The scanner reported the vendor's own exception classes as leaked keys.**
    The LiveKit key rule matches `API` + 10 characters, which is also the shape
    of `APIConnectionError`, `APIStatusError`, `APITimeoutError` and
    `APIConnectOptions`. Six places in this repository format errors as
    `type(exc).__name__`, and `team/worksheets/MEASUREMENTS.md` asks the reader to paste
    failures in — so the pre-commit hook would have blocked a commit and
    reported a credential leak in a line containing none. Fixed with an
    allowlist **subtracted from matches**, not by narrowing the pattern: the
    obvious narrowing (reject CamelCase tails) also stops detecting real keys
    like `API` + `Rb7kQm2xLp9w`, and a false negative in a security control is
    strictly worse than the noise it removes.
    `test_a_real_key_shaped_like_a_vendor_name_is_still_flagged` pins that.

**Found while fixing the above**

- **Order-dependent test flakiness.** The new wiring tests passed in isolation
  and failed in a full run: `AgentSession.__init__` calls
  `asyncio.get_event_loop()`, which raises once an earlier async test has
  closed the loop. Written synchronously they were green alone and red
  together — worse than a plain failure, because it reads as a fluke. All
  session-constructing tests are now `async`.

The through-line in almost all of these: **documentation and code disagreed,
and the tests agreed with neither** — and the tests that existed were tests of
*components*, not of *paths*. Both mutation harnesses now run in CI so that the
next instance of it fails a build instead of reaching a judge.

### What was verified against the installed package, not assumed

Every external behaviour this submission depends on was read out of the
installed code rather than recalled:

| Claim | Verified against |
|---|---|
| LiveKit retains interrupted tool outputs with `reply_required=False` | `livekit/agents/voice/agent_activity.py`, quoted in §6 |
| Tools are not cancellable unless flagged | `function_tool` default is `ToolFlag.NONE`; `allow_cancellation = ToolFlag.CANCELLABLE in info.flags` |
| Rime word timings reach the app via frame userdata | `livekit/plugins/rime/tts.py` (`t == "timestamps"` branch) → `livekit/agents/tts/tts.py:1103` |
| `rime.TTS` accepts the arguments `build_tts` passes | constructor signature introspected; `coda`/`mistv2`/`mistv3` are the literal model ids |
| Coda ignores bracket controls | Rime's own docs; enforced at startup by `resolve_strategy` |
| The agent, session and all 7 tools construct on 1.7.1 | constructed in-process with placeholder credentials |
| The console page, `/api/config` and `/api/token` serve correctly | server started, endpoints fetched, JWT decoded: signed, 3600 s TTL, no secret in the payload |

### Do the tests mean anything? Mutation testing

"573 tests pass" is not evidence. A suite that stays green when you break the
code it guards is worse than no suite, because it converts absence of signal
into confidence. So the claim is checked directly:

```bash
python evidence/mutation_test.py     # ~2 min, no credentials
```

It introduces 15 specific, plausible bugs one at a time — the fence admitting
stale results, the effect check skipped, gate codes read as quantities, cold and
warm runs sharing a series — runs the full suite against each, and restores the
file. **A mutant that survives is a hole in the tests, and the script exits
non-zero.** Six of the fifteen are bugs that were actually written during
development, so their regression tests are verified against the thing they exist
to catch rather than assumed to work.

Current result: **15/15 caught.**

---

## 4. Measurements that need Rime

These require credentials, so a judge cannot reproduce them without their own
keys. Each writes a committed artifact.

| What | Command | Boundary | Artifact |
|---|---|---|---|
| Rime time-to-first-audio | `python evidence/measure_latency.py` | `server_first_frame` | `results/latency.md` |
| Estimator error vs word timestamps | `python evidence/measure_heard_accuracy.py` | in-process | `results/heard_accuracy.md` |
| Pronunciation A/B with clips | `python evidence/measure_pronunciation.py` | audio saved | `results/pronunciation/` |
| Barge-in → silence, at the ear | live session, browser console | **`client_playout`** | `results/sessions/` |

### Where each stopwatch stops

This is the part that decides whether a latency number means anything.

| Boundary | Includes | Omits | Is it the driver's experience? |
|---|---|---|---|
| `client_playout` | network hop, jitter buffer, device output | nothing this side of the ear | **yes** |
| `server_flush` | agent-side processing | the last hop and the client buffer | no — flattering by roughly RTT/2 + buffer depth |
| `client_first_audio` | STT + LLM + Rime + transport + playback | nothing | **yes** |
| `server_first_frame` | Rime request, queueing, synthesis | transport and playback | no |

The browser measures `client_playout` itself with an RMS meter over the remote
track, publishes it back over a LiveKit data channel, and the agent records it
alongside its own server-side number. Both are kept. `MetricsLog` will not
aggregate across boundaries or across cold/warm — that is structural, not a
convention, and `test_metrics.py` asserts it.

**Cold vs warm.** The first call of a session carries TLS and the WebSocket
upgrade. It is labelled `cold` and reported separately. Series with n < 10
carry an explicit caution in the output: exploratory, not a service level.

### Honest note on the client-side stop measurement

The RMS detector requires 120 ms of sub-threshold audio to declare silence. The
reported figure **subtracts that hold**, so it names the moment audio actually
stopped rather than the moment we became confident about it. It remains a
threshold estimate, not a sample-exact one, and it will read slightly late on a
sentence that trails off quietly.

---

## 5. Reproducing everything

```bash
git clone <this repo> && cd waypoint
python -m venv .venv && . .venv/Scripts/activate
pip install -e ".[dev]"

# No credentials needed:
pytest
python evidence/run_acceptance.py
python scripts/secret_scan.py
python scripts/preflight.py --offline

# With credentials in .env.local:
python scripts/preflight.py
python evidence/measure_latency.py
python evidence/measure_pronunciation.py
python evidence/measure_heard_accuracy.py
```

Pinned exactly: `livekit-agents==1.7.1`, `livekit-plugins-rime==1.7.1`,
`livekit-client@2.22.2` in the browser. Fuzz tests are seeded, dispatch jitter
is seeded, `route_eta` is deterministic — a re-anchored value can therefore be
*shown* equal to a freshly computed one, which is what makes A4 falsifiable.

---

## 6. What LiveKit already does — read from the source, not recalled

Being precise here is the difference between a real contribution and an
overclaim. From `livekit/agents/voice/agent_activity.py` (1.7.1):

```python
if speech_handle.interrupted:
    await utils.aio.cancel_and_wait(exe_task)

    # commit results of tools that finished despite the interruption (#3702), so
    # the next inference doesn't run them again
    interrupted_calls: list[llm.FunctionCall] = []
    interrupted_fnc_outputs: list[llm.FunctionCallOutput] = []
    for sanitized_out in tool_output.output:
        interrupted_calls.append(sanitized_out.fnc_call)
        interrupted_fnc_outputs.append(_interrupted_tool_output(sanitized_out))
    ...
    self._agent._chat_ctx.insert(interrupted_tool_messages)
```

and `_interrupted_tool_output` sets `fnc_call_out.reply_required = False`.

**So LiveKit prevents the immediate stale utterance.** It also deliberately
*retains* the stale output, for a good reason stated in its own comment: so the
next inference does not re-run the tool.

Three consequences that retention creates, and which Waypoint addresses:

1. **The deferred utterance is not prevented.** `reply_required=False` governs
   this turn. The bare value sits in the chat context and the model can state
   it on any later turn. Waypoint's fence makes the *retained text itself*
   self-describing — the tool returns `SUPERSEDED_RESULT: ... do not state it,
   now or on any later turn` instead of a number — so retention becomes safe
   rather than being fought. Scenario A1 checks the returned string, not just
   that nothing was spoken immediately.

2. **Effects are not governed at all.** `reply_required` is about speech.
   Cancellation cannot help either: `cancel_and_wait` raises `CancelledError`
   at the tool's next await point, which is *after* the HTTP POST returned 200.
   Cancelling a coroutine does not un-send an SMS. Waypoint therefore checks
   the fence at the **effect boundary** — immediately before the irreversible
   call — and A2 asserts against the backend's mutation log rather than against
   the transcript.

3. **Tools are not cancellable by default.** `allow_cancellation` is
   `ToolFlag.CANCELLABLE in info.flags`, and `function_tool`'s default is
   `ToolFlag.NONE`. So the run-to-completion path is the default path, which is
   what makes gap 2 the common case rather than a rare race.

### Why bumping only on interruption is complete, not a shortcut

In the **non**-interrupted path the same file does `await exe_task` — tools are
awaited to completion before the turn ends. So the only way a tool result can
outlive the turn that asked for it is an interruption. Advancing the generation
on ordinary turn boundaries as well would add no safety and would risk fencing
a valid result if the bump raced ahead of the issue.

The barge-in signal is read **synchronously** from
`ctx.speech_handle.interrupted` at each boundary rather than subscribed to as
an event, so there is no window in which a tool observes a stale generation
because the event had not been dispatched yet. `bump_for()` keys on the handle
id, so the same barge-in observed from three places costs one generation.

---

## 7. Limitations

1. **A write already in flight cannot be un-written.** The effect check bounds
   the exposure to one backend call rather than the whole tool duration, but
   not to zero. When it happens the agent says
   `COMMITTED_BUT_UNCONFIRMED` and tells the driver on the next turn.
   **Scenario A3 exercises this deliberately and asserts the write landed** —
   it is a documented residual risk, not a hidden one.
   [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) has the full analysis.
2. **`ReanchorPolicy` is a human judgement.** Marking a side-effecting tool
   `REANCHOR_IF_ARGS_MATCH` would defeat the fence for that tool. The default
   is the conservative one and the three write tools are `NEVER`, but nothing
   in the code can tell whether a tool is truly side-effect-free.
3. **Barge-in *detection* is LiveKit's.** `mode="adaptive"`,
   `min_duration=0.4s`, `resume_false_interruption=true`. Road-noise-specific
   tuning has not been done, and in a real vehicle it would be needed.
4. **Sub-claim (c) is proven in two layers, and only one of them offline.**
   The offline tests prove that the reconciliation runs, that it uses Rime's
   word timestamps, that the boundary is correct, and that the resulting
   playback record excludes words that never played — observable in
   `deps.heard_log` and in the console event. What they do *not* prove is that
   the `chat_ctx.add_message` call lands in a live session: `Agent.chat_ctx`
   needs a running activity, so in the offline tests that call raises and is
   caught, by design. The append is exercised for the first time in a live run,
   and the session audit written to `evidence/results/sessions/heard-*.json` is
   how you check it did. Stated because a reader could otherwise assume the
   offline pass covers the whole path.
5. **Sub-claim (c) depends on the WebSocket path.** On HTTP, the boundary is a
   character-mass interpolation that ignores pauses and phoneme duration. It is
   labelled `duration_estimate`, `exact=False`, and the startup banner warns.
   `measure_heard_accuracy.py` quantifies the gap in words, signed, so the
   over-claiming direction is visible.
6. **Small samples.** A hackathon evidence run produces tens of measurements,
   not thousands. Percentiles are nearest-rank rather than interpolated
   precisely so they do not invent precision, and n < 10 is flagged.
7. **Synthetic data.** No real customer, address, phone number or delivery.
   Street names are real SF streets because the pronunciation corpus needs to
   be genuinely hard. [`docs/DATA.md`](docs/DATA.md).
8. **Pronunciation intelligibility is unverified without a listener.** Rows in
   `results/pronunciation/report.md` with an empty verdict column are reported
   `_unverified_`.
9. **Single language, no persistence.** `RIME_LANG=eng`; dispatch state is
   in-memory.
10. **The audible half of this submission is unmeasured, and the artifacts say
    so.** Everything in section 3 runs offline against no credential, and it is
    the part we can prove. The parts that need a Rime key — time-to-first-audio,
    the transport comparison, and whether the respelling layer actually makes
    `Gough` and `Guerrero` intelligible to a human ear — have not been run at
    the time of writing. `evidence/results/latency.md` therefore ships with an
    empty results table and the two `401`s that produced it;
    `evidence/results/pronunciation/report.md` ships with `Audio rendered:
    false` and every verdict `_unverified_`. Those files are not placeholders
    we forgot to fill. They are what this repository looks like when it has
    nothing to report, and we would rather claim nothing than a number nobody
    can reproduce. Anyone with a Rime key can close the gap with two commands,
    both in section 5.
11. **The turn fence has been proven against a simulator, not a human voice.**
    The six acceptance scenarios drive the real agent code and inject the
    barge-in themselves, which is what makes them reproducible on any machine
    with no key — and is also exactly what they cannot prove. Whether LiveKit's
    VAD fires on a real interruption at a real interruption threshold, in a
    room with real noise, is a question only a live session answers.

---

## 8. Provider disclosure

**Rime is the primary and only speech provider.** No fallback TTS is
configured. If Rime is unreachable the session errors visibly rather than
substituting another voice — a hidden substitution would violate the
requirement that the active provider be observable.

`Settings.banner()` prints the active provider, model, voice, language,
transport, audio format and endpoint at startup on every run, and the same
redacted structure is published to the browser console and shown there. Every
disclosed degradation (HTTP transport, ineffective pause brackets) appears as an
explicit `! WARNING` line. `test_config.py` asserts the banner names Rime
unconditionally and that no secret can appear in it.
