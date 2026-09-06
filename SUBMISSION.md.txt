# Submission — Waypoint

## Deliverables

| | Link |
|---|---|
| **Demo video** (4:30, unlisted) | `FILL: YouTube link` |
| **Repository** | https://github.com/darshanrajagoli/data-forge-rime-hadippa |
| **CI, green on every push** | [verify workflow](https://github.com/darshanrajagoli/data-forge-rime-hadippa/actions/workflows/ci.yml) |
| **Evidence** | [`RIME_EVIDENCE.md`](RIME_EVIDENCE.md) |
| **Full project explainer** | [`HANDOFF.md`](HANDOFF.md) |
| **Adversarial audits (3, kept in full)** | [`docs/audits/`](docs/audits/) |

## One-liner

**Waypoint is a hands-free dispatch copilot for delivery drivers that never speaks a stale answer.**

## The user and the problem

A delivery driver mid-route. Both hands on the wheel, eyes on the road, and in most jurisdictions legally barred from touching a screen. Remove speech and there is no product left.

But a driver interrupts constantly — that is what talking while operating a vehicle looks like. And a voice agent that can be interrupted can finish a sentence that is no longer true: reading out a gate code for a stop the driver abandoned two seconds ago, or closing a delivery they just cancelled.

## The hard voice problem we chose

**Barge-in and recovery during in-flight tool work**, taken to the level that actually matters:

1. A superseded tool result is never spoken — *and never becomes a value the model can state on a later turn*.
2. An irreversible write never commits after the turn that requested it was interrupted. Checked at the **effect boundary**, because cancellation cannot help: by the time `CancelledError` arrives the POST returned 200.
3. The transcript records the words that actually left the speaker, using Rime's word-level timestamps — so the agent never believes it gave the driver a gate code it was cut off mid-way through.

Mechanism: a **turn fence** — a monotonic generation counter with one admission gate, plus turn-origin retirement. `src/waypoint/fencing.py`.

## Why Rime is central

- Rime is the **only** speech provider. No fallback TTS. If Rime is unreachable the session errors visibly rather than quietly substituting another voice.
- Rime's **WebSocket word timestamps** are what make claim 3 exact rather than estimated. Turning that transport off degrades the feature and the startup banner says so.
- Rime's model capabilities shaped a real product decision: `coda` ignores `phonemize_between_brackets` and `pause_between_brackets`, which are mistv2-only. Since street-name pronunciation is a correctness requirement for a driver ("Gow Street" is not on their route), we built a model-portable respelling layer and made asking for phonemes on `coda` **fail at startup** instead of silently no-opping.

## Evidence, in one command

```bash
pytest                                # 573 tests, ~20s, no credentials
python evidence/run_acceptance.py     # 6/6 scenarios, 36 checks, no credentials
python evidence/mutation_test.py      # 15/15 deliberate bugs caught
python evidence/mutation_test_ii.py   # 19/19 more: wiring, gates, evidence