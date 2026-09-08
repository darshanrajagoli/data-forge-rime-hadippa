# Listening notes

Scored by ear. The method is in [`docs/LISTENING_TEST.md`](../docs/LISTENING_TEST.md);
the text variants that were sent to Rime are committed in
[`evidence/results/pronunciation/report.md`](../evidence/results/pronunciation/report.md).

**Listener:** Akshat · **Date:** 2026-09-07
**Playback device:** earbuds

**The audio clips are not in the repository.** They were rendered locally by
`python evidence/measure_pronunciation.py` against a live Rime key and
listened to on that machine; the `.wav` files were never committed. What is
committed is the text-variant table every clip was generated from, so the
experiment is repeatable by anyone with a Rime key, but the exact audio these
verdicts were scored against is not recoverable. Treat the table below as one
listener's report of a run you would have to reproduce, not as an artifact you
can re-listen to.

## Method

Blind A/B where possible: played the `none` and `respell` clips in a random
order without looking at the filename, then scored each one.

Scale: `correct` (I would have driven to the right street, or keyed the right
code) · `usable` (slightly off, unambiguous in context) · `wrong` (I would have
gone to the wrong place, or could not key the code) · `unclear`.

## Results — model `coda`, voice `lyra`

| fixture | `none` | `respell` | what it actually sounded like |
|---|---|---|---|
| Gough Street | correct | correct | `none` said "guff" |
| Haight Street | correct | correct | `none` said "hay-t" |
| Guerrero Street | correct | **unclear** | `respell` said "juh-rey-ro street" |
| Divisadero Street | correct | correct | `none` said "Di-vih-zah-de-roh" |
| Noe Street | correct | **unclear** | `none` said "No-ey"; `respell` said "Now-uh street" |
| gate code 4417 | correct | correct | not written down |
| gate code 0921 | correct | correct | not written down |
| house number 1207 | correct | *not scored* | "twelve oh seven" |

`phoneme` is not scored for `coda`: the model ignores
`phonemize_between_brackets`, so the run downgrades the request to `respell` and
records it as such. That downgrade is visible in
[`evidence/results/pronunciation/report.md`](../evidence/results/pronunciation/report.md)
as `phoneme → respell *(downgraded)*`.

## Results — model `mistv2`, voice `cove`

`mistv2` is the model that supports phoneme brackets, so the `phoneme` arm is
only meaningful here.

| fixture | `none` | `respell` | `phoneme` | what it actually sounded like |
|---|---|---|---|---|
| gate code 4417 | **unclear** | correct | correct | `none` said "four thousand four hundred and seventeen" |
| Guerrero Street | not scored | not scored | unclear | `phoneme` said "ger-wear-oh" |
| 1207 Noe Street | correct | correct | correct | |
| Gough Street | correct | correct | correct | |
| Haight Street | correct | correct | correct | |
| Divisadero Street | correct | correct | correct | |
| Noe Street | correct | correct | correct | |
| gate code 0921 | correct | correct | correct | |

The two "not scored" cells are blanks in the original score sheet, not passes.
The `none` and `respell` arms for Guerrero on `mistv2` were not listened to.

## What this actually shows

Two findings, and they point in opposite directions. Both are reported because
the trade-off is the honest result.

**1. Respelling is load-bearing for numeric codes, and only on some models.**
The single worst result in this table is `mistv2` reading `gate code 4417` with
no respelling: it said *"four thousand four hundred and seventeen."* A driver
cannot key that into a keypad. Respelling fixes it. This is the case the layer
exists for, and it is a genuine correctness failure rather than a cosmetic one.

**2. Respelling makes some street names worse on `coda`.**
`coda` with no respelling read every one of the five street fixtures correctly,
including the three that motivated the layer (Gough, Haight, Divisadero). Two of
them got *worse* when respelled: Guerrero became "juh-rey-ro" and Noe became
"Now-uh". On this model the respelling layer is a net negative for street names.

The conservative reading is that respelling should stay on for digit strings and
should not be assumed to help street names on every model. We are not shipping a
per-model respelling policy on the strength of one listener — see the caveats —
but the measurement says one is worth building.

## Outside listener

None. We could not get a second listener, so every verdict above is one person's.

## Honest caveats

- One listener, one playback device, one session.
- The listener knew what each clip was supposed to say, which biases toward
  scoring `correct`. The two `unclear` verdicts are the ones to trust most,
  because they were reached in spite of that bias.
- "Correct" here means intelligible to one person in a quiet room with earbuds.
  It is not a road test, and a cab at speed is a much worse listening
  environment.
- The `mistv2` Guerrero row is incomplete, so the `phoneme`-vs-`respell`
  comparison for that fixture rests on a single cell.
