# Measurements

> **Worksheet — not a document for judges.** Fill every `TODO` from the reports you generate in your lane in
> `team/WORKFLOW.md`. Delete this blockquote when you are done.
>
> Report what the tools actually printed. A modest number with an honest method
> beats a good number nobody can reproduce — and the brief says unverified
> performance numbers get no credit.

**Run by:** Akshat (name) · **Date:** 7/09/2026
**Machine:** Windwos, ASUS Vivobook 16X, 2 yrs old (OS, laptop model, roughly how old)
**Network:** Hotspot (wifi or ethernet, roughly where — this affects every number below)

---

## Rime time-to-first-audio

Command: `python evidence/measure_latency.py --warm 20 --compare-transport`
Raw output: `evidence/results/latency.md` (created by the command above)

**Boundary: `server_first_frame`.** This is **not** the driver's experience. It
covers the Rime request, queueing and synthesis, and on the cold run also TLS
and the WebSocket upgrade. It excludes the LiveKit hop, the client jitter
buffer and the speaker. The end-to-end number is measured in the browser
(`client_first_audio`) — see the demo console.

| series | warmth | n | p50 (ms) | p95 (ms) | min | max |
|---|---|---|---|---|---|---|
| `rime.first_frame.http` | cold | 1 | 1225.632 | 1225.632 | 1225.63 | 1225.63 |
| `rime.first_frame.http` | warm | 20 | 408.86 | 477.189 | 395.04 | 569.72 |
| `rime.first_frame.websocket` | cold | 1 | 1346.12 | 1346.12 | 1346.12 | 1346.12 |
| `rime.first_frame.websocket` | warm | 20 | 394.35 | 429.933 | 379.99 | 432.17 |

Cold and warm are reported separately and never averaged: the first call of a
process pays for connection setup that no later call pays.

## WebSocket vs HTTP transport

The WebSocket path is slightly faster on warm runs (median 394.35ms vs HTTP's 408.86ms, a difference of ~14.5ms). However, the reason we use it is word timestamps, not speed, and the README already says so.

## Heard-not-said: estimator error

Command: `python evidence/measure_heard_accuracy.py --cuts 12`
Raw output: `evidence/results/heard_accuracy.md` (created by the command above)

Ground truth is Rime's own word timestamps. The question is how wrong the
fallback estimator is when those are unavailable.

- Comparisons: 48
- Mean absolute error: 2.96 words
- Max absolute error: TODO words
- **Over-claimed** (estimator thought the driver heard more than they did):
  over-claimed in 1 of 48 

Over-claiming is the dangerous direction — it is how a gate code goes missing
from the transcript. The exact path has zero error by construction.

## What these numbers do not show

- Sample sizes are n=20 for warm runs, and n=1 for cold runs. Anything under n=10 is indicative, not a service level.
- One machine, one network, one physical location, one voice, one language.
- Nothing here measures intelligibility — that is `team/worksheets/LISTENING_NOTES.md`.
- Cold start for WebSocket was slower (1346.12ms) compared to HTTP (1225.63ms), though WebSocket became faster once warmed up.
