# Demo script — 4:30, shot by shot

Read this whole page once before recording. Then record it in order. Every line
you say out loud is written out; do not improvise, because the timing of the
interruptions is the demo.

**Target: 4 minutes 30 seconds.** The cap is 5:00. Going over is worse than
cutting the last section.

---

## Before you press record

Run these and do not proceed until all three are clean.

```bash
python scripts/preflight.py          # must exit 0
pytest                               # 425 passed
python evidence/run_acceptance.py    # 6/6 scenarios
```

Then:

- [ ] Set `WAYPOINT_DISPATCH_LATENCY_MS=1800` in `.env.local`. **This is what makes the race visible on camera.** At 300 ms the interruption lands after the lookup finishes and there is nothing to see.
- [ ] Wired headset or earbuds. **Not** laptop speakers — the mic will hear the agent and the barge-in detector will fire on the agent's own voice.
- [ ] Browser zoom at 110%, window 1600×900 or wider, so the fence board is legible after compression.
- [ ] Close Slack, mail, notifications.
- [ ] Terminal font at 16pt+. Judges watch this on a laptop.
- [ ] Two terminals side by side, or tabbed: agent in one, `web/server.py` in the other.
- [ ] Do one full dry run without recording. The interruption timing needs one rehearsal.

**Recording:** OBS, or macOS `Cmd-Shift-5`, or Windows Game Bar `Win-G`. Capture
system audio **and** microphone. Check after 10 seconds that both are in the
file.

---

## Shot 1 — the user and the problem (0:00 – 0:35)

Show: your face, or a still of a delivery van. No terminal yet.

> "This is Waypoint. The user is a delivery driver, mid-route, both hands on
> the wheel. They can't look at a screen — in most places they legally can't —
> and they won't ask twice.
>
> Take the voice away and there is no product left. That's the easy part.
>
> The hard part is this: a driver interrupts constantly. And a voice agent that
> can be interrupted can say something that is no longer true."

---

## Shot 2 — the failure, stated concretely (0:35 – 1:05)

Show: `README.md` scrolled to the blockquote, or a slide with these three lines.

> "Here's the failure. The agent starts reading a gate code for Oak Street. The
> driver cuts in and says skip Oak, go to Pine. The Oak Street lookup was
> already in flight — so it comes back, and the agent finishes the sentence
> with a gate code for a stop that's been abandoned.
>
> And it's worse than a wasted sentence. If that interrupted turn had called
> `mark_delivered`, the stop is now closed. Cancelling the task doesn't help:
> by the time the cancellation lands, the write already returned two hundred."

---

## Shot 3 — the normal flow, working (1:05 – 1:45)

Show: browser console, full screen. Agent already connected.

Point at the green **SPEECH PROVIDER: RIME** banner for two seconds.

> "Rime is the only speech provider. No fallback — if Rime is down this errors
> out loud rather than quietly swapping in another voice. Model, voice,
> transport and sample rate are all on screen."

Now speak to it:

| You say | Expect |
|---|---|
| "What's my next stop?" | "Next is stop one, **twelve forty-seven Goff Street**, unit four B…" |
| "What's the gate code?" | "…gate code **four four one seven**." |

> "Two things there. It said 'Goff', not 'Gow' — Gough Street. And it read the
> gate code as four digits, not 'four thousand four hundred seventeen', because
> the driver has to key it into a pad. Rime's Coda model doesn't support
> phoneme brackets, so that's a respelling layer that works on any model."

---

## Shot 4 — THE STRESS CASE (1:45 – 2:50)

**This is the demo. Everything else is setup.** Keep the fence board visible.

> "Now the stress case. I'm going to ask for an ETA, and interrupt while the
> lookup is still running."

| Step | You say | When |
|---|---|---|
| 1 | "How long to Guerrero?" | — |
| 2 | *(wait for the agent to start speaking, watch a row appear on the fence board marked **in flight**)* | ~1s |
| 3 | **"No — mark Gough delivered instead."** | **while it is still speaking** |

Now stop and point at the screen. Let it sit for three seconds.

> "Look at the fence board. The Guerrero lookup came back — and it's marked
> **fenced stale**. It was never spoken. The generation counter went from zero
> to one, and anything stamped with generation zero can't reach the driver.
>
> That's the whole mechanism: every tool call is stamped with the turn that
> asked for it, and one gate decides whether the answer is still allowed out."

Then the write. Ask for something irreversible and interrupt it:

| Step | You say | When |
|---|---|---|
| 4 | "Mark Haight delivered." | — |
| 5 | **"Actually stop, wrong one."** | **immediately, while it is speaking** |

> "And here — **writes blocked**. That's an irreversible operation that the
> interruption stopped from happening at all. Not cancelled after the fact.
> Refused before the call was made.
>
> The stop is still marked pending. That's checked against the dispatch
> backend's mutation log in the acceptance test, not against what the agent
> said — because what it said isn't the point. What it *did* is."

Now scroll to the **Heard, not said** panel on the left. There will be an entry
from the interruption you just did.

> "One more thing, and this is the part that's easy to miss. When I cut it off,
> it was mid-sentence. The words in red were generated but never came out of the
> speaker — and they're the ones the agent now knows the driver never heard.
>
> That matters because the alternative is the agent thinking it already gave me
> a gate code it was cut off halfway through, and never repeating it. The
> boundary comes from Rime's word-level timestamps, which is the specific reason
> this runs on Rime's WebSocket path rather than plain HTTP. The badge says
> EXACT when the timestamps are there and ESTIMATED when they aren't."

---

## Shot 5 — the number, measured at the ear (2:50 – 3:20)

Show: the "Measured, at the ear" panel.

> "This number is measured in the browser, not on the server. It's the gap
> between my voice being detected and Rime's audio actually going silent in
> this browser's output — so it includes the network hop and the jitter buffer
> that a server-side number leaves out.
>
> The server-side figure is smaller. We report both, labelled, and never
> average them. The first response of a session is a cold run and it's tagged
> as one."

Point at the `n=` count.

> "Small sample. It says so. We're not calling this a service level."

---

## Shot 6 — the receipts (3:20 – 4:10)

Show: terminal. Run these live, do not use a screenshot.

```bash
python evidence/run_acceptance.py
```

Let it scroll. Land on `6/6 scenarios passed (36 checks)`.

> "The acceptance test was written before this demo. Six scenarios, thirty-six
> checks. No API key, no network, no microphone — it drives the real agent code
> against the real fence and injects the barge-ins itself. Anyone can run this
> in one command."

```bash
pytest -q
```

> "Four hundred and twenty-five tests. A hundred and twelve of them are on the fence
> alone, and seventy of those are seeded fuzz runs — two hundred random
> orderings of issue, interrupt, resolve, cancel, checking after *every single
> operation* that nothing leaked and nothing stale got through."

Then the one that matters most:

```bash
python evidence/mutation_test.py
```

> "And this is how we know those tests mean anything. It breaks the code
> fifteen different ways — makes the fence admit stale results, skips the check
> before an irreversible write, reads gate codes as quantities — and runs the
> whole suite against each one. Fifteen out of fifteen get caught. A test suite
> that stays green when you break the thing it guards is worse than no test
> suite.
>
> Six of those fifteen are bugs we actually wrote. Four were found *after* we
> thought this was finished — including one where the transcript reconciliation
> was never wired into the agent at all, and the unit tests never noticed
> because they tested the module instead of the path. That's all written up in
> RIME_EVIDENCE."

---

## Shot 7 — close (4:10 – 4:30)

> "So: a voice-first product for someone who genuinely cannot use a screen, and
> one hard voice problem — barge-in during in-flight tool work — solved at the
> level that actually matters, which is whether an irreversible action happens,
> not just whether a sentence gets spoken.
>
> Rime for speech. LiveKit for transport and turn detection. The evidence is one
> command and it runs on your machine, not ours."

---

## If something breaks on camera

Do not restart the recording. Say what happened and keep going — the brief asks
for a deliberate stress case, and a real failure handled openly reads better
than a fourth take.

| Problem | Say this, then continue |
|---|---|
| Agent doesn't respond | "STT dropped that turn — let me repeat it." |
| Barge-in doesn't register | "That one didn't cross the interruption threshold — it's set to four hundred milliseconds to avoid firing on road noise." Then interrupt more firmly. |
| Fence board empty | Check the agent terminal for the publish error. If the data channel is down, say "the visualiser lost its data channel; the audit log is still written to `evidence/results/sessions`" and show that file. |
| Rime errors | Stop. Do not fake it. Fix it and re-record. Speaking over a broken provider is the one thing that reads as dishonest. |

## What must be in the final cut

The brief requires all seven. Tick them off before uploading.

- [ ] The target user and their problem — Shot 1
- [ ] The normal end-to-end flow — Shot 3
- [ ] The chosen hard voice problem, named — Shots 2 and 4
- [ ] One deliberate stress or failure case — Shot 4
- [ ] The result or measurement — Shots 4, 5 and 6
- [ ] Which speech provider is active — Shot 3 (on screen, and said out loud)
- [ ] Under 5:00

Editing is allowed. **Everything demonstrated must exist in the repository** —
do not cut together behaviour the code cannot produce.
