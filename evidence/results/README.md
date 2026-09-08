# What is in this directory, and what state each file is in

Read this before drawing a conclusion from anything here. Two of these files
report failure, and that is not an accident — but neither is it the whole
story, and you should not have to reconstruct that from six other documents.

Nothing in this directory has been edited by hand. Every file is exactly what
the script that produced it wrote. This README is the only hand-written file,
and it adds no numbers.

| File | State | What it means |
|---|---|---|
| `acceptance.md` · `acceptance.json` | **not in a fresh clone** | Deliberately gitignored: `team/WORKFLOW.md` has four people run the harness, and four runs would collide on a file nobody owns. Run `python evidence/run_acceptance.py` and they appear here. The committed copy is [`../reference-run/acceptance.md`](../reference-run/acceptance.md). |
| [`latency.md`](latency.md) · [`latency.json`](latency.json) | **a failed run** | Empty results table and two `401`s. See below. |
| [`pronunciation/report.md`](pronunciation/report.md) · [`pronunciation.json`](pronunciation/pronunciation.json) | **text variants only** | `Audio rendered: false`, every verdict `_unverified_`. See below. |
| `heard_accuracy.md` · `heard_accuracy.json` | **not in a fresh clone** | Written by `evidence/measure_heard_accuracy.py`, which needs a key. Same story as the latency files: the 2026-09-07 run happened, the output was never copied off the machine. The estimator-error figures it produced are transcribed in [`../../team/MEASUREMENTS.md`](../../team/MEASUREMENTS.md). |
| `sessions/` | **empty** | Live-session dumps. Nothing here: no live session was recorded to disk. |

## Why two of these report failure

These scripts need a Rime API key. They were run on **2026-09-07** by Akshat,
against a live key, and they worked — the numbers and the listening verdicts
are real. What did not happen is the upload: the regenerated `latency.md`,
`latency.json` and pronunciation report were never copied off the machine that
produced them.

So what is committed here is still the **earlier keyless run**, which failed
with two `401`s exactly as it should have. We have left it that way. The
alternative was to hand-write files that would claim to be tool output while
carrying a provenance they do not have, and the brief is explicit that
unverified performance numbers get no credit.

**The measured results are here instead:**

- Latency, transport comparison and estimator error →
  [`../../team/MEASUREMENTS.md`](../../team/MEASUREMENTS.md)
- Listening verdicts, including the two fixtures where respelling made things
  *worse* → [`../../team/LISTENING_NOTES.md`](../../team/LISTENING_NOTES.md)

Both files state at the top that their numbers are hand-transcribed from tool
output rather than committed artifacts. That is weaker evidence and it is the
correct thing to hold against this submission.

## What you can reproduce right now, with no key

```bash
python evidence/run_acceptance.py     # writes acceptance.md and .json here
```

That is the artifact carrying the central claim, and it is the one that needs
nothing from us. Because it is gitignored, a fresh clone will not have it until
you run that command — which is the point. Diff your run against our committed
copy in [`../reference-run/`](../reference-run/acceptance.md); they should agree
on every verdict, and differ only in the timestamp, the commit and the
sub-millisecond timings.

## What you would need a key for

```bash
python evidence/measure_latency.py --warm 20 --compare-transport
python evidence/measure_pronunciation.py
python evidence/measure_heard_accuracy.py --cuts 12
```

Each rewrites the corresponding file above. A free key from
[app.rime.ai/signup](https://app.rime.ai/signup) is enough.
