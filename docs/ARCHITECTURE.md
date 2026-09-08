# Architecture

Reading order for someone who has ten minutes: `fencing.py`, then the `_read`
and `_write` methods in `agent.py`, then `tests/test_fencing.py`. Everything
else is support.

---

## The one idea

Every tool result must pass through **one** function before it can be spoken or
committed.

```python
ticket = fence.issue(name, args, policy, origin=speech_handle.id)
result = await do_the_work()
decision = fence.admit(ticket)
if not decision.speak:
    return SUPERSEDED_MARKER
```

That is the whole design. The value of a single choke point is that the
invariant can be tested exhaustively in one place rather than argued about at
every call site — which is why 112 of the 620 tests live on this module and 70
of them are fuzz runs.

## Two independent supersession causes

`TurnFence._supersession_reason` returns non-`None` if **either** holds:

| Cause | Question it answers |
|---|---|
| `ticket.generation < current` | Was this issued before the latest barge-in? |
| `ticket.origin in retired` | Is the turn that issued it dead? |

Both are needed, and the second was added because of a bug the acceptance
harness found. The generation counter advances *once* per barge-in. A *second*
tool issued by an already-interrupted turn therefore gets stamped with the new
generation and looks fresh. Scenario A2 committed two of three stale writes
until origins were stamped. See `RIME_EVIDENCE.md` §3.

## Two boundaries, not one

```
  issue ──────── check ──────── [ the irreversible thing ] ──────── admit
                   │                                                  │
          effect boundary                                     speech boundary
     non-terminal; refuses a                          terminal; decides whether
     write before it happens                          the result may be spoken
```

`check()` exists because cancellation is not a safety mechanism for a write. By
the time `CancelledError` arrives, the POST returned 200. The only way to not
do a thing is to not do it, so the fence is consulted *before* the effect.

`admit()` is terminal and at-most-once: a second call raises rather than
speaking twice.

## Three dispositions that are not "fenced"

| Disposition | When | Speak? |
|---|---|---|
| `DELIVERED` | Same turn that asked. | yes |
| `REANCHORED` | Superseded, but a live turn wants this exact lookup. | yes |
| `FENCED_STALE` | Superseded read, nobody wants it. | no |
| `FENCED_TERMINAL` | Superseded `NEVER`-policy write. | no |
| `FENCED_CANCELLED` | Resolved before completing. | no |

`FENCED_TERMINAL` is deliberately distinct from `FENCED_STALE`. Both withhold
the result, but only one represents an irreversible action that was prevented,
and that distinction is what you want visible in an audit log at 3am.

### Re-anchoring, and why it makes the fence cheap

A driver who says *"ETA to Gough — and the traffic"* has not abandoned the ETA
lookup; they have added to it. The new turn issues its own ticket for the same
tool with the same argument fingerprint, and the in-flight result is handed
over instead of being discarded and re-issued.

So the fence is not purely a tax. On the most common interruption it acts as a
cross-turn deduplicating cache and saves a full round trip — 400 ms in
acceptance scenario A4. A safety mechanism that makes the common path faster is
a safety mechanism people leave switched on.

Re-anchoring requires `REANCHOR_IF_ARGS_MATCH`, which is only ever correct for
a side-effect-free read. A retired *origin* does not block it — the turn is
dead but the data is still what a live turn is asking for — though the target
must itself be from a live turn, so two dead turns cannot validate each other.

## Where LiveKit ends and Waypoint begins

| Concern | Owner |
|---|---|
| WebRTC transport, rooms, audio I/O | LiveKit |
| Barge-in *detection* (adaptive classifier, VAD) | LiveKit |
| Stopping TTS playout on interruption | LiveKit |
| Cancelling the tool executor task | LiveKit |
| Suppressing the *immediate* reply from a stale result | LiveKit (`reply_required=False`) |
| Retaining stale outputs in the chat context | LiveKit (deliberate — see its comment) |
| **Labelling those retained outputs as superseded** | **Waypoint** |
| **Refusing an irreversible write across a turn boundary** | **Waypoint** |
| **Re-anchoring in-flight reads** | **Waypoint** |
| **Audit trail and accounting** | **Waypoint** |
| **Heard-not-said reconciliation** | **Waypoint** |
| Speech synthesis | Rime |
| Pronunciation of street names and codes | **Waypoint** (`pronounce.py`) |

`RIME_EVIDENCE.md` §6 quotes the exact LiveKit source this table is based on.

## Data flow for one interrupted turn

```
driver: "how long to Guerrero?"
  │
  ├─ STT final ─▶ LLM ─▶ tool call eta_to(destination="Guerrero")
  │                        │
  │                        ├─ fence.issue(gen=0, origin="speech-7")   ──▶ console: in flight
  │                        └─ backend.route_eta()  ... 1800 ms ...
  │
driver: "no, mark Gough delivered"   ◀── barge-in at ~600 ms
  │
  ├─ LiveKit: stops Rime playout, cancels exe_task
  ├─ speech_handle.interrupted = True
  │
  │   (agent reads it synchronously at the next boundary, not via an event,
  │    so there is no window where a tool sees a stale generation)
  │
  ├─ fence.bump_for("speech-7")  ──▶ gen 1, "speech-7" retired
  │
  └─ eta_to returns ─▶ fence.admit(ticket)
                         │  gen 0 < 1 AND origin retired
                         └─▶ FENCED_STALE ──▶ SUPERSEDED_MARKER    ──▶ console: fenced stale
                                                    │
                                                    └─ retained in chat_ctx by LiveKit,
                                                       but as an instruction, not a number
```

## The second path: heard, not said

The fence governs *tool results*. A separate, shorter path governs the
*utterance itself*, and it is where sub-claim (c) lives.

```
Rime (WebSocket) ──word timestamps──▶ Agent.transcription_node
                                          │  collects the text AND the marks,
                                          │  registers both together at stream end,
                                          │  records t0 = first delta
                                          ▼
                                  HeardTracker (utterance registered)
                                          │
SpeechHandle done ──▶ _on_speech_done ──▶ _reconcile_heard
                                          │  cut() if interrupted, else complete()
                                          ├─▶ deps.heard_log        (audit, written on shutdown)
                                          ├─▶ console "heard" event (visible in the demo)
                                          └─▶ chat_ctx: "[playback record] the driver heard only …"
```

Two things about this are worth knowing, because both were wrong once.

**The text and the marks must be registered together.** An earlier version
registered the utterance with an empty string and attached marks afterwards, so
every reconciliation returned `""` — silently, and with the module's own tests
passing throughout, because they fed the tracker real text directly and never
went through this node. Testing a component is not testing a path.

**`t0` is a proxy.** It is the moment the first transcription delta arrived,
which stands in for the start of playout. It omits the transport hop, so it
reads slightly *late* and therefore biases towards believing the driver heard
more than they did. Rime's word timestamps place the boundary exactly within
that window; the residual is one network hop and it is stated in
`docs/THREAT_MODEL.md` (R6) rather than rounded away.

## Why bumping only on interruption is complete

In the non-interrupted path LiveKit does `await exe_task` — tools are awaited to
completion before the turn ends. So the only way a tool result can outlive its
turn is an interruption. Advancing the generation on ordinary turn boundaries
would add no safety and would risk fencing a valid result if the bump raced
ahead of the issue. This is a claim about LiveKit's actual control flow, not a
simplification.

## Module dependency order

```
fencing.py      (no internal deps — pure, importable alone)
heard.py        (no internal deps)
pronounce.py    (no internal deps)
    ▲
config.py ──────┘   (validates a strategy against a model)
dispatch.py
metrics.py
prompts.py ─────▶ config.py
agent.py   ─────▶ everything + livekit
```

`fencing.py`, `heard.py` and `pronounce.py` import nothing from the rest of the
package and nothing from LiveKit. That is why the bulk of the test suite needs
no network, no credentials and no audio device — and why a judge can verify the
central claim in about six seconds.
