# Measurements

The Rime measurements that need a live key. Everything here was produced by the
committed scripts; the numbers are transcribed from what those scripts printed.

**Run by:** Akshat · **Date:** 2026-09-07
**Machine:** Windows, ASUS Vivobook 16X, roughly two years old
**Network:** mobile hotspot

**The generated report files are not committed.** `measure_latency.py` writes
`evidence/results/latency.md` and `latency.json`, but those were not uploaded
from the machine that ran them, so what is in `evidence/results/` is still the
earlier keyless run that failed with two `401`s and an empty results table. The
tables below are the record of the real run. They were read off the tool output
by hand, which is weaker provenance than a committed artifact, and that is
stated here rather than papered over. Anyone with a Rime key can regenerate the
artifact with the exact command shown under each table.

---

## Rime time-to-first-audio

```
python evidence/measure_latency.py --warm 20 --compare-transport
```

**Boundary: `server_first_frame`.** This is **not** the driver's experience. It
covers the Rime request, queueing and synthesis, and on the cold run also TLS
and the WebSocket upgrade. It excludes the LiveKit hop, the client jitter
buffer and the speaker. The end-to-end number is measured in the browser
(`client_first_audio`) and was not captured in this run.

| series | warmth | n | p50 (ms) | p95 (ms) | min (ms) | max (ms) |
|---|---|---|---|---|---|---|
| `rime.first_frame.http` | cold | 1 | 1225.63 | 1225.63 | 1225.63 | 1225.63 |
| `rime.first_frame.http` | warm | 20 | 408.86 | 477.19 | 395.04 | 569.72 |
| `rime.first_frame.websocket` | cold | 1 | 1346.12 | 1346.12 | 1346.12 | 1346.12 |
| `rime.first_frame.websocket` | warm | 20 | 394.35 | 429.93 | 379.99 | 432.17 |

Cold and warm are reported separately and never averaged: the first call of a
process pays for connection setup that no later call pays. The cold rows are
n=1 — a single observation each, not a distribution. Their p50, p95, min and max
are the same number because there is only one number.

## WebSocket vs HTTP transport

Warm, the WebSocket path is **14.5 ms faster at p50** (394.35 vs 408.86) and
**47.3 ms faster at p95** (429.93 vs 477.19). It is also markedly steadier: the
WebSocket warm spread is 52 ms end to end (379.99–432.17) against HTTP's 175 ms
(395.04–569.72).

Cold, the WebSocket path is **120.5 ms slower** (1346.12 vs 1225.63), which is
the WebSocket upgrade being paid for once.

**None of this is why we use it.** The WebSocket transport is selected for word
timestamps, which is what makes the heard-not-said transcript exact rather than
estimated. The latency result is a small bonus and would not on its own justify
the choice. n=20 warm on one machine and one network is indicative, not a
service level, and n=1 cold is a single sample.

## Heard-not-said: estimator error

```
python evidence/measure_heard_accuracy.py --cuts 12
```

Ground truth is Rime's own word timestamps. The question this answers is how
wrong the fallback estimator is when those are unavailable — that is, on the
HTTP path.

- Comparisons: **48**
- Mean absolute error: **2.96 words**
- Max absolute error: *not written down* — the run was not saved, and this
  figure is not recoverable without re-running
- **Over-claimed** (estimator thought the driver heard more than they actually
  did): **1 of 48**

Over-claiming is the dangerous direction. It is how a gate code goes missing
from the transcript: the agent believes it finished saying a code it was cut off
partway through, and never repeats it. One case in 48 is the number that matters
here, and it is the argument for the WebSocket path being the default rather
than an option — on the exact path the error is zero by construction, not small.

## What these numbers do not show

- One machine, one network, one physical location, one voice, one language.
- n=20 for warm runs and n=1 for cold. Anything under n=10 is exploratory.
- A mobile hotspot is a high-variance network. The HTTP warm max of 569.72 ms
  against a 395.04 ms min is more likely the network than Rime.
- Nothing here measures intelligibility. That is
  [`LISTENING_NOTES.md`](LISTENING_NOTES.md).
- Nothing here measures what the driver hears. Every figure stops at
  `server_first_frame`, before the LiveKit hop, the jitter buffer and the
  speaker.
- The max absolute error for the estimator is missing, so the tail of that
  distribution is unknown. A 2.96-word mean says nothing about the worst case.
