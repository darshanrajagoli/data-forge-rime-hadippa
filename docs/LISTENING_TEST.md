# Listening test — how to score the pronunciation clips

`evidence/measure_pronunciation.py` renders the fixture corpus under every
strategy and saves the clips. It does **not** score them, because whether a
driver hears the right street is a judgement a person has to make. Rows with an
empty verdict are reported `_unverified_`, never as passes.

This page is how to fill that column in. It takes about ten minutes.

## Protocol

1. Render the clips:

   ```bash
   python evidence/measure_pronunciation.py --models coda mistv2
   ```

2. Open `evidence/results/pronunciation/report.md`. Each fixture appears once
   per (model, strategy) pair, with a link to its `.wav`.

3. **Listen blind where you can.** For each fixture, play the `none` and
   `respell` clips in a random order without looking at which is which. The
   effect is obvious enough that knowing the answer contaminates the judgement.

4. For each clip, write one of:

   | Verdict | Means |
   |---|---|
   | `correct` | You would have driven to the right street / keyed the right code. |
   | `usable` | Slightly off but unambiguous in context. |
   | `wrong` | You would have gone to the wrong place, or could not key the code. |
   | `unclear` | You could not tell. |

5. Put the verdict in the `listening_verdict` field of the matching row in
   `pronunciation.json`, then re-render the report:

   ```bash
   python -c "import json,sys; sys.path.insert(0,'evidence'); \
     from measure_pronunciation import to_markdown; \
     p=json.load(open('evidence/results/pronunciation/pronunciation.json')); \
     open('evidence/results/pronunciation/report.md','w').write(to_markdown(p))"
   ```

6. Record **who** listened and **on what** (headphones, laptop speakers, phone
   speaker) at the top of the report. A verdict from laptop speakers is a
   different measurement from one on earbuds, and a driver is on neither.

## What counts as a result

A fair statement looks like:

> Two listeners, wired earbuds. On `coda/lyra`, 4 of 4 hard street fixtures
> were scored `wrong` under `none` and `correct` under `respell`. Gate codes
> were `wrong` under `none` (read as quantities) and `correct` under `respell`
> in 2 of 2. n=8 per arm, one voice, one language — indicative, not a
> benchmark.

What is not fair: reporting a pass rate without saying how many listeners,
which device, or that it was your own project you were listening to. Say those
things and the number is worth something.

## Known bias

You built this and you know what the clips are supposed to say, which makes you
the worst available listener. If you can get one person who has not seen the
lexicon to score the `none` arm, that single outside verdict is worth more than
all of yours.
