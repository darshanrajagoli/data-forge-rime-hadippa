# Waypoint acceptance run

- Run at: `2026-09-08T23:44:38+0530`
- Commit: `d5c6b18`
- Python: `3.12.0`
- Command: `python evidence/run_acceptance.py`
- Requires network: **no**. Requires credentials: **no**.

- Harness self-audit: **intact** (6 scenarios, 36 checks, as declared).

| Scenario | Claim | Checks | Result |
|---|---|---|---|
| **A1** A superseded lookup is never spoken | When the driver barges in while a route lookup is in flight, the result of that lookup is never turned into speech, and never becomes a value the model can state on a later turn. | 7/7 | PASS |
| **A2** A superseded irreversible write never reaches the backend | When the driver barges in before an irreversible operation has been carried out, the operation does not happen at all. | 6/6 | PASS |
| **A3** A write already in flight is reported, not hidden | If the driver interrupts after an irreversible write has already started, the write lands. | 5/5 | PASS |
| **A4** Refining a request re-uses the in-flight lookup | When the driver interrupts to add to a request rather than replace it, the in-flight read is handed to the new turn instead of being discarded and re-issued. | 7/7 | PASS |
| **A5** The transcript records what was heard, not what was generated | When Rime's audio is cut mid-sentence, the assistant turn written into the chat context contains only the words that were played, marked as truncated. | 5/5 | PASS |
| **A6** Bookkeeping holds across a realistic interrupted conversation | Over a conversation with several barge-ins, mixed reads and writes and a cancellation, every issued ticket resolves exactly once and nothing leaks. | 6/6 | PASS |

## Detail

### A1 - A superseded lookup is never spoken

**Claim.** When the driver barges in while a route lookup is in flight, the result of that lookup is never turned into speech, and never becomes a value the model can state on a later turn.

**Procedure.** Issue eta_to('Gough') with a 400ms backend. Flip the speech handle to interrupted while it is in flight. Await the tool and inspect the returned string and the fence audit log.

- [x] tool returned the superseded marker
- [x] no ETA value appears in the returned text
  - returned: SUPERSEDED_RESULT: the driver interrupted before hearing this, and it answers a request th...
- [x] the marker instructs the model not to state it later
  - LiveKit retains interrupted tool outputs in the chat context, so the returned string is what the model reads next turn. It has to be self-describing.
- [x] exactly one fence record was written
- [x] disposition is fenced_stale
  - got fenced_stale
- [x] generation advanced exactly once
- [x] fence accounting balances

### A2 - A superseded irreversible write never reaches the backend

**Claim.** When the driver barges in before an irreversible operation has been carried out, the operation does not happen at all. This is checked against the backend's mutation log, not against what was said.

**Procedure.** Mark the speech handle interrupted, then call mark_delivered, reschedule_stop and notify_recipient. Inspect the backend mutation log and the stop statuses.

- [x] no mutation reached the dispatch backend
  - mutation log: []
- [x] all three tools reported a refusal
- [x] the refusal states that nothing changed
- [x] stop statuses are untouched
- [x] all three are recorded as fenced_terminal, not merely stale
  - fenced_terminal is the disposition reserved for NEVER-policy tools, so an irreversible refusal is distinguishable in the audit log.
- [x] fence accounting balances

### A3 - A write already in flight is reported, not hidden

**Claim.** If the driver interrupts after an irreversible write has already started, the write lands. The agent says so on the next turn instead of pretending it did not happen or doing it twice.

**Procedure.** Start mark_delivered against a 300ms backend, wait past the effect-boundary check, then flip the handle to interrupted.

- [x] the write did land
- [x] the agent reports it as committed but unconfirmed
  - returned: COMMITTED_BUT_UNCONFIRMED: this was carried out, but the driver interrupted before hearing...
- [x] the agent is told not to repeat the action
- [x] this is the documented residual risk, not a silent failure
  - Cancellation cannot protect a write that already committed. The window is bounded by one backend call and is stated in docs/THREAT_MODEL.md.
- [x] fence accounting balances

### A4 - Refining a request re-uses the in-flight lookup

**Claim.** When the driver interrupts to add to a request rather than replace it, the in-flight read is handed to the new turn instead of being discarded and re-issued. The safety mechanism pays for itself in latency.

**Procedure.** Issue an eta_to ticket, bump the generation, issue an identical ticket for the new turn, then admit the first.

- [x] disposition is reanchored
  - got reanchored
- [x] the result is speakable
- [x] it is attributed to the new turn's ticket
- [x] the value handed over equals a fresh lookup
  - route_eta is deterministic precisely so this is checkable.
- [x] satisfying the new turn cost zero extra backend calls
  - backend call count unchanged at 2; the alternative is a second lookup costing about 411ms.
- [x] the re-anchor decision itself is effectively free
  - 0.004ms in-process, against a 411ms round trip.
- [x] fence accounting balances

### A5 - The transcript records what was heard, not what was generated

**Claim.** When Rime's audio is cut mid-sentence, the assistant turn written into the chat context contains only the words that were played, marked as truncated. A gate code that was never spoken never appears in history.

**Procedure.** Register an utterance, attach synthetic Rime word timestamps at 300ms per word, cut at 1500ms, and inspect the chat text.

- [x] boundary is exact, from Rime word timestamps
  - This is why the shipped config uses the Rime WebSocket path: use_websocket=True plus use_tts_aligned_transcript=True.
- [x] five words were heard
- [x] the unheard gate code is absent from the chat context
  - chat text: 'Your next stop is twelve [cut off here - the driver interrupted and did not hear the rest]'
- [x] the turn is marked as truncated
- [x] the generated text is preserved separately for audit

### A6 - Bookkeeping holds across a realistic interrupted conversation

**Claim.** Over a conversation with several barge-ins, mixed reads and writes and a cancellation, every issued ticket resolves exactly once and nothing leaks.

**Procedure.** Nine turns: reads, a barge-in, a refused write, a cancelled read, a committed write, more reads. Assert the accounting identity after each.

- [x] no ticket left in flight
- [x] one record per issued ticket
  - 7 records, 7 issued
- [x] exactly one write committed
- [x] exactly one write was refused
- [x] exactly one read was cancelled
- [x] the generation advanced once, for one barge-in
