# Threat model — what the fence does and does not protect

The fence is a safety mechanism, so it deserves the same scepticism as any
other one: what exactly is guaranteed, under what assumptions, and what is left
exposed. Guarantees are stated with the test that holds them up. Residual risks
are stated without mitigation where none exists.

---

## The asset

**Correctness of what the driver hears, and of what gets written to dispatch
records.** The driver is operating a vehicle and cannot cross-check anything.
A wrong address costs a delivery; a wrongly closed stop costs a delivery *and*
hides the error.

## The adversary

There isn't one. This is a concurrency threat model, not a security one. The
"adversary" is the interleaving of a human interrupting, a network call
returning, and an event loop scheduling — and the fact that a human's change of
mind is not atomic with respect to in-flight I/O.

That framing matters, because it rules out one class of defence: nothing here
can be secured by asking the model nicely. The `SUPERSEDED_RESULT` marker is
for conversational coherence. **A model that ignored every marker still could
not commit a stale write**, because `TurnFence.check()` refuses it before the
call is made.

---

## Guarantees

### G1 — A superseded read is never spoken

**Holds because** `admit()` is the only path by which a tool result becomes a
return value, and it refuses any ticket whose generation is older than the
current one or whose originating turn has been retired.

**Assumes** every tool goes through `_read` or `_write`. A new tool that calls
the backend directly is outside the fence — see R5.

**Tested by** `test_result_superseded_by_barge_in_is_never_spoken`, acceptance
**A1**, and 70 seeded fuzz runs that re-derive staleness independently of the
fence's own verdict.

### G2 — A `NEVER`-policy write never commits after supersession

**Holds because** the fence is checked at the **effect boundary** —
immediately before the irreversible call — not merely after the result returns.

**Assumes** the tool is correctly declared `ReanchorPolicy.NEVER`. See R1.

**Tested by** acceptance **A2**, which asserts against
`DispatchBackend.log` rather than against the transcript, and
`test_stale_write_is_refused_before_it_happens`.

### G3 — Exactly-once resolution

Every issued ticket reaches exactly one terminal disposition. No leaks, no
double-delivery. `admit()` raises on a second call rather than speaking twice.

**Tested by** `assert_accounting()`, called after every operation in the fuzz
tests, and `test_concurrent_admit_only_one_wins` under eight racing threads.

### G4 — History records only what was played

**Holds because** `Agent.transcription_node` collects the utterance text and
Rime's word timestamps together, and `WaypointAgent._reconcile_heard` cuts at
the interruption and appends a playback record to the chat context.
`HeardTracker.cut()` counts a word as heard only if its audio *finished* before
the cut.

**Assumes** the WebSocket transport, which is what carries the timestamps.
Degrades to an estimate on HTTP — see R3. Also assumes `t0` is close to the
start of playout — see R6.

**Tested by** acceptance **A5** for the boundary logic, and
`test_transcription_node_registers_the_real_text` /
`test_reconcile_records_what_was_heard` for the pipeline. Both layers are
needed: this guarantee was **false in a shipped version** while `test_heard.py`
was entirely green, because the module was tested and the path was not.

**Not covered offline.** `Agent.chat_ctx` requires a running activity, so the
final `add_message` is the one step the offline tests cannot execute — they
assert the record was computed correctly and logged, and the append raises and
is caught. It runs for real only in a live session; `evidence/results/sessions/
heard-*.json` is the artifact that shows it did.

### G5 — No credential reaches the repository or the browser

`.gitignore`, `secret_scan.py` (with its own 40-test suite), a pre-commit hook,
redaction in `banner()` / `to_dict()`, and a token server that keeps the API
secret server-side.

---

## Residual risks

### R1 — A mis-declared policy defeats the fence for that tool  *(unmitigated)*

`ReanchorPolicy` is a human judgement. Marking a side-effecting tool
`REANCHOR_IF_ARGS_MATCH` would let its result cross a turn boundary, and
nothing in the code can detect that a tool is not really a pure read.

Reduced, not solved, by: the default being `DISCARD`; all three write tools
being `NEVER`; and the policy being a property of the tool rather than of the
call site, so it is declared once, in one visible place.

**A type system cannot fix this** — "side-effect-free" is a claim about the
world, not about a signature.

### R2 — A write in flight when the barge-in lands still commits  *(bounded, disclosed)*

This is the important one, and it is **not fixable by cancellation**.
`cancel_and_wait` raises `CancelledError` at the tool's next await point, which
is after the HTTP POST returned 200. Cancelling a coroutine does not un-send an
SMS or un-close a stop.

What the fence buys: the exposure window shrinks from *the whole tool duration*
to *one backend call*, because the check sits immediately before the effect
rather than after the result.

What it does not buy: zero. When it happens, the agent returns
`COMMITTED_BUT_UNCONFIRMED`, the driver is told plainly on the next turn, and
the action is not repeated. **Acceptance scenario A3 exercises this on purpose
and asserts the write landed** — so the residual risk is demonstrated, not
hidden.

Real fixes, out of scope here: idempotency keys on the dispatch API so a
retry is safe, or a compensating-transaction path so the write can be reversed.
Both are properties of the backend, which is synthetic in this repository.

### R3 — Heard-not-said degrades on the HTTP path  *(disclosed at runtime)*

Without word timestamps the boundary is a character-mass interpolation that
ignores pauses and per-phoneme duration. Typically ±1 word near a clause
boundary; the over-claiming direction is the dangerous one.

Mitigated by: WebSocket being the default; `exact=False` and a plain-language
note on every such result; a startup `! WARNING`; and
`measure_heard_accuracy.py`, which quantifies the error in signed words against
real Rime timings.

### R4 — Barge-in detection is upstream of the fence  *(inherited)*

The fence is only as good as the signal that a barge-in happened. That signal
is LiveKit's adaptive interruption classifier at `min_duration=0.4s`. A missed
barge-in means the generation never advances and a stale result is delivered
legitimately, because as far as the system knows the turn was never
interrupted.

Not tuned for a vehicle. Road noise, wipers and a passenger talking are all
real, and `resume_false_interruption=true` is a blunt instrument against them.

### R5 — A tool added outside `_read`/`_write` is unfenced  *(structural)*

The choke point only chokes what flows through it.

Reduced by: `_read` and `_write` being the only two paths in `agent.py`, both
short; every existing tool being a three-line wrapper over one of them; and the
accounting identity failing loudly if a ticket is issued and never resolved.
A tool that never issues a ticket at all, though, is simply invisible to the
fence.

### R6 — Two timing proxies, both biased the same way  *(disclosed)*

**Client-side stop measurement.** The RMS silence detector needs 120 ms below
threshold to declare silence. The reported figure subtracts the hold, but it
remains an estimate and reads late on an utterance that trails off quietly.

**The heard-not-said cut position.** `_reconcile_heard` measures from `t0`, the
arrival of the first transcription delta, which stands in for the start of
playout. It omits the transport hop and the client jitter buffer, so elapsed
time reads slightly *short* of true playout position — which means the cut lands
slightly early and the record under-claims what the driver heard.

Under-claiming is the safe direction for both: the cost is the agent repeating
a word, against a cost of a gate code the driver never received. Neither is
sample-exact and neither is presented as such.

### R7 — The visualiser is not a source of truth  *(by design)*

Fence events are published over a LiveKit data channel with every failure
swallowed, because observability must never be able to break a session
(`test_broken_record_sink_cannot_break_the_fence`). If the channel drops, the
board goes stale while the fence keeps working. The authoritative record is
`TurnFence.audit_json()`, written to `evidence/results/sessions/` on shutdown.

---

## Explicitly out of scope

- **Authentication and authorisation.** Anyone who can reach the token server
  can join. Fine for a local demo; not a deployment posture.
- **Prompt injection via dispatch data.** The synthetic manifest is trusted
  input. A real one is attacker-influenced (a customer-supplied delivery note
  is untrusted text) and would need handling.
- **Multi-driver isolation.** One session, one manifest, in memory.
- **PII.** There is none. `docs/DATA.md`.
- **Denial of service, rate limiting, cost control.**
