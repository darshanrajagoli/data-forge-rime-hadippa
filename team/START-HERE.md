# START HERE — what this project is, in plain English

**Everyone reads this once. It takes eight minutes. Then go to
[`WORKFLOW.md`](WORKFLOW.md) and do your lane.**

You do not need to know Python. You do not need to know maths, machine
learning, or what a "turn fence" is. You need to know enough to talk about it
for five minutes and to not accidentally break it. That is what this page is
for.

---

## What we built

**Waypoint is a voice assistant for delivery drivers.**

Picture someone driving a delivery van. Both hands on the wheel. Eyes on the
road. They cannot look at a phone — in most places it is actually illegal — but
they need to know things: what is my next stop, what is the gate code, how long
to get there, mark this one as delivered.

So they talk to it, and it talks back. That is the product.

**Why does it have to be voice?** Because if you take the voice away, there is
nothing left. It is not an app with a speaker bolted on. A driver cannot use a
screen. That is the test the judges apply, and we pass it cleanly.

---

## The clever bit — this is the part you need to be able to explain

Here is a thing that goes wrong with every voice assistant, and almost nobody
handles it.

**People interrupt.** Constantly. That is just what talking to something while
you are driving looks like.

Now watch what happens:

1. You ask: *"How long to Guerrero Street?"*
2. It starts looking that up. Takes about two seconds.
3. It starts talking: *"Guerrero is about..."*
4. **You interrupt:** *"No, forget that — mark Gough Street delivered instead."*
5. The Guerrero lookup finishes and comes back.

**What most systems do at step 5:** read out the Guerrero answer anyway. You
asked about a stop you already abandoned, and you get told about it. Annoying.

**But here is the bad version.** Suppose step 2 was not a lookup. Suppose it was
*"mark this delivery complete."* You interrupted, you changed your mind — but
the instruction was already sent. **A stop just got closed that shouldn't have
been.** And you cannot undo it, because by the time your interruption registers,
it already happened.

**Our fix:** every single request the assistant makes gets **stamped with which
part of the conversation asked for it**. When you interrupt, that part of the
conversation is marked dead. Then there is one gate that every answer has to
pass through, and it asks one question: *is the conversation that asked for this
still alive?*

- If yes → the answer gets spoken.
- If no → the answer is thrown away, silently, and never reaches you.
- And if it was something irreversible → **it is refused before it happens at
  all**, not cancelled afterwards.

We call it the **turn fence**. If someone asks you what the project does, that
paragraph above is your answer.

---

## The second clever bit

When you cut it off mid-sentence, some words came out of the speaker and some
did not.

That matters. Say it was halfway through reading you a gate code when you
interrupted. If the assistant *thinks* it already told you the code, it will
never repeat it — and you never get the code.

So we use a feature of **Rime** (the company whose voice technology this is
built on): Rime tells us the exact timestamp of every single word it speaks.
From that we work out precisely where the audio got cut, and the assistant
records *"the driver heard up to here, and not past it."*

**This is why we use Rime specifically**, and specifically their live streaming
connection rather than the simpler one. It is a real reason, not a
box-ticking exercise, and it is worth saying out loud in the demo.

---

## How we prove it works

This is where most hackathon projects lose points, and where we are strongest.

- **609 automated tests.**
- **Six "acceptance scenarios"** — one command, no API keys needed, that runs
  the whole interruption scenario and checks 36 separate things about it.
- **34 "mutation tests."** This one is the good one. We deliberately *break the
  code* in 34 different ways — make it speak stale answers, turn off
  interruption handling entirely, and so on — and check that the tests
  **notice**. All 34 times, they do.

Why does that last one matter? Because "all our tests pass" means nothing on its
own. Tests that stay green when you break the thing they are guarding are worse
than useless. So we proved ours actually bite.

- **It runs automatically on GitHub** every time we push, on Windows and Linux,
  on two versions of Python, **using none of our API keys.** Anyone can check our
  main claim without asking us for anything.

- **We got the project torn apart three times** by independent reviewers told to
  be as harsh as possible. All three found real problems. All three reports are
  in `docs/audits/`, including everything they found, and every code problem
  they found is now fixed. Keeping those reports in the submission looks risky
  and is not — it is the strongest evidence we have that we actually checked our
  own work.

---

## What was NOT done — and what happened to each

All four are now done. Kept here with their outcomes, because what came back is
more interesting than the list was.

1. ~~There is no demo video.~~ **Recorded** by Arrya —
   [youtu.be/EChOFjIuyNM](https://youtu.be/EChOFjIuyNM), 4:30.
2. ~~The code has never actually spoken out loud.~~ **It has.** Akshat ran it
   against a live Rime key on 2026-09-07. Warm time-to-first-audio was 394 ms at
   p50 over WebSocket. See [`MEASUREMENTS.md`](MEASUREMENTS.md) — including the
   part where the generated report never got uploaded, so the numbers are
   hand-transcribed and say so.
3. ~~Nobody has listened to the pronunciation.~~ **Akshat did, and what we had
   predicted turned out half right.** We expected it to say "Gough Street" as
   *"Goff"* and to read a gate code as *"four four one seven"* rather than
   *"four thousand four hundred and seventeen"*. "Gough" does come out as
   "Goff". And the gate-code worry was exactly right — on `mistv2`, `gate code
   4417` really was read as *"four thousand four hundred and seventeen"*, which
   a driver cannot key. Respelling fixes that. But it also made *Guerrero* and
   *Noe* **worse** on `coda`, where plain text was already correct. Both halves
   are reported in [`LISTENING_NOTES.md`](LISTENING_NOTES.md).
4. ~~Nobody has tried following our own setup instructions from scratch.~~
   **Rahul did**, from a fresh ZIP on a clean machine, and found three real
   defects — starting with `cd waypoint`, a directory that does not exist. All
   three are fixed, and `scripts/check_docs.py` now fails the build if any of
   them comes back. See [`../VERIFICATION.md`](../VERIFICATION.md).

**The golden rule:** if nobody measured it, we do not claim it. Anywhere you see
`TODO` or `_unverified_` in this project, that is deliberate and honest. Fill it
in with what actually happened, or leave it. **Never make a number up.** A
boring true number beats an impressive invented one, and the competition rules
say so in writing.

---

## The rules — short version

1. **Never put an API key in a file that gets uploaded.** Keys go in one file
   called `.env.local`, which is set up to never leave your laptop. There is an
   automatic scanner that blocks it if you get this wrong.
2. **Only touch the files your lane says you own.** They do not overlap, so
   nobody can break anybody else's work. This is deliberate.
3. **Never invent a result.** See above.
4. **If something breaks, say so in the group chat.** A real failure handled
   openly reads better than a fake success, on camera and in the report.

---

## What happens now

Three people, three lanes, running at the same time. **Nobody waits for anybody
—** the lanes were designed that way on purpose.

| Lane | Person | What it is |
|---|---|---|
| **A** | **Arrya** | Get it running for real, and **record the demo video.** This is the one that decides whether we are eligible. |
| **B** | **Akshay** | Get the real numbers and the real audio. Listen to it. Write down what you actually heard. |
| **C** | **Rahul** | Be the judge. Follow our own instructions from scratch, catch what is wrong, then write and file the submission. |

Full copy-paste instructions are in **[`WORKFLOW.md`](WORKFLOW.md)**.

Every step there can be pasted into ChatGPT, Gemini, or Claude if you get stuck
— the workflow document tells you exactly what to upload and what to say.

**Go.**
