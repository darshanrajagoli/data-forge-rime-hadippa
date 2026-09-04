# Measurements

> **Worksheet — not a document for judges.** Fill every `TODO` from the reports you generate in your lane in
> `team/WORKFLOW.md`. Delete this blockquote when you are done.
>
> Report what the tools actually printed. A modest number with an honest method
> beats a good number nobody can reproduce — and the brief says unverified
> performance numbers get no credit.

**Run by:** TODO (name) · **Date:** TODO
**Machine:** TODO (OS, laptop model, roughly how old)
**Network:** TODO (wifi or ethernet, roughly where — this affects every number below)

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
| TODO paste rows from latency.md | | | | | | |

Cold and warm are reported separately and never averaged: the first call of a
process pays for connection setup that no later call pays.

## WebSocket vs HTTP transport

TODO — what `--compare-transport` showed. If the WebSocket path is faster, say
by how much. If it is not, say that: the reason we use it is word timestamps,
not speed, and the README already says so.

## Heard-not-said: estimator error

Command: `python evidence/measure_heard_accuracy.py --cuts 12`
Raw output: `evidence/results/heard_accuracy.md` (created by the command above)

Ground truth is Rime's own word timestamps. The question is how wrong the
fallback estimator is when those are unavailable.

- Comparisons: TODO
- Mean absolute error: TODO words
- Max absolute error: TODO words
- **Over-claimed** (estimator thought the driver heard more than they did):
  TODO of TODO, worst +TODO words

Over-claiming is the dangerous direction — it is how a gate code goes missing
from the transcript. The exact path has zero error by construction.

## What these numbers do not show

- TODO sample sizes. Anything under n=10 is indicative, not a service level.
- One machine, one network, one physical location, one voice, one language.
- Nothing here measures intelligibility — that is `team/worksheets/LISTENING_NOTES.md`.
- TODO — anything that failed, looked odd, or you could not explain. Write it
  down. An unexplained result reported is worth more than one quietly dropped.
