# WORKFLOW — from here to submitted

**Read [`START-HERE.md`](START-HERE.md) first. Then find your name below and do
only that lane.**

---

## The deal

- **Three lanes. Three people. All running at the same time.**
- **Nobody waits for anybody.** Every lane is designed so you can finish it
  without needing anything from the other two.
- **Nobody touches anybody else's files.** The file lists below do not overlap.
  You literally cannot break someone else's work.
- **You do not need to know Python, git, or anything technical.** Every command
  is written out. Copy it, paste it, press Enter.

| Lane | Person | Job | Time |
|---|---|---|---|
| **A** | **Arya** | Get it running for real, **record the demo video** | ~90 min |
| **B** | **Akshat** | Real numbers, real audio, listen to it | ~75 min |
| **C** | **Darshan** | Be the judge, then write and file the submission | ~75 min |

**Lane A is the one that decides whether we are eligible at all.** If Arya gets
blocked, Akshat drops Lane B and takes over Lane A. Say so in the group chat.

**Files each person owns — nobody else edits these:**

| | Owns |
|---|---|
| **Arya** | `demo/` (the video) |
| **Akshat** | `evidence/results/latency.*`, `evidence/results/pronunciation/`, `team/worksheets/MEASUREMENTS.md`, `team/worksheets/LISTENING_NOTES.md` |
| **Darshan** | `team/worksheets/VERIFICATION.md`, `SUBMISSION.md` |

---

## Before anything else — everyone does this (10 minutes)

You each do this once, on your own laptop. It is the same for all three of you.

### Step 0.1 — Get the project onto your laptop

Go to: **https://github.com/darshanrajagoli/data-forge-rime-hadippa**

Click the green **`< > Code`** button → **Download ZIP**.

Unzip it somewhere you can find again — your Desktop is fine. You will get a
folder called `data-forge-rime-hadippa-main`. **Rename it to `waypoint`** so
these instructions match what you see.

### Step 0.2 — Open a terminal in that folder

- **Windows:** open the folder in File Explorer, click the address bar at the
  top, type `powershell`, press Enter.
- **Mac:** right-click the folder → Services → **New Terminal at Folder**.

A black or blue window opens. That is the terminal. Every command below gets
typed (or pasted) there, one at a time, pressing Enter after each.

> **Pasting into a terminal:** on Windows use **right-click**, on Mac use
> **Cmd+V**. Ctrl+V often does not work in a terminal.

### Step 0.3 — Install Python if you do not have it

Type this and press Enter:

```
python --version
```

If it prints something like `Python 3.12.0`, you are fine — skip to 0.4.

If it says "not recognised" or opens the Microsoft Store, go to
**https://www.python.org/downloads/** and install it. **On Windows, tick "Add
Python to PATH" on the first screen** — this is the one thing people miss. Then
close the terminal, open a new one (step 0.2 again), and try `python --version`
again.

### Step 0.4 — Set the project up

Paste these **one at a time**, waiting for each to finish:

```
python -m venv .venv
```

Then, **Windows:**
```
.venv\Scripts\activate
```
**Mac:**
```
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`. That means it worked.

```
pip install -e ".[dev]"
```

That one takes 2–3 minutes and prints a lot. Ignore it all unless it ends with
the word `ERROR`.

### Step 0.5 — Check it works

```
pytest
```

**You should see `549 passed`.** If you do, everything is set up correctly and
you can start your lane.

> **Every time you open a new terminal from now on**, you must run the
> `activate` command from step 0.4 again first. If a command suddenly says
> "module not found", that is why.

📱 **Send to the group:** `Setup done, 549 passed. Starting Lane <A/B/C>.`

---

## 🅰️ LANE A — ARYA — the demo video

**You have Claude Pro. You are on the critical path. This lane is why we are
eligible.**

### A1 — Get two free API keys (15 min)

**LiveKit** (this is the phone line — it carries the audio):

1. Go to **https://cloud.livekit.io** → sign up (Google login is fine)
2. Create a project — call it `waypoint`
3. Go to **Settings → Keys** → **Create key**
4. Copy three things: the **URL** (starts `wss://`), the **API Key** (starts
   `API`), and the **API Secret**

**Rime** (this is the voice):

1. Go to **https://rime.ai** → sign up → find **API Keys** in the dashboard
2. Copy the key

> ⚠️ **These are passwords. Never paste them into a chat, a document, or an AI
> chatbot.** They go in exactly one file, in the next step. There is an
> automatic scanner in this project that will block you if you get this wrong —
> but do not rely on it.

### A2 — Put the keys in the right place (5 min)

In your `waypoint` folder there is a file called **`.env.example`**.

Make a copy of it. Name the copy **`.env.local`** — exactly that, starting with
a dot. Open `.env.local` in Notepad (Windows) or TextEdit (Mac) and replace the
four placeholder values with your real ones:

```
LIVEKIT_URL=wss://waypoint-xxxxx.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RIME_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

Leave every other line in the file exactly as it is. Save.

> `.env.local` is already configured to never be uploaded anywhere. That is why
> it has to be named exactly that.

### A3 — Check everything is live (5 min)

```
python scripts/preflight.py
```

**This must finish with `Ready` and no red text. Do not go further until it
does.** It actually calls Rime and checks the voice comes back, so if this
passes, the hard part is over.

If it fails, jump to **"When you are stuck"** at the bottom of this page. This
is the step most likely to need an LLM's help.

📱 **Send to the group:** `Preflight is green. Rime is answering. Recording next.`

### A4 — Make the demo dramatic (2 min)

Open `.env.local` again and find this line:

```
WAYPOINT_DISPATCH_LATENCY_MS=1800
```

Make sure it says **1800**. This makes the lookups take 1.8 seconds, which is
what makes the interruption visible on camera. At the default speed it happens
too fast to see. Save.

### A5 — Do a practice run (15 min)

Open **two** terminals, both in the `waypoint` folder, both with `activate` run.

**Terminal 1:**
```
python web/server.py
```

**Terminal 2:**
```
python -m waypoint.agent dev
```

Open **http://localhost:8080** in Chrome. Allow microphone access.

**Use wired headphones or earbuds. Not laptop speakers** — the microphone will
hear the assistant's own voice and interrupt itself constantly.

Now talk to it. Try:
- *"What's my next stop?"*
- *"What's the gate code?"*
- Then the important one: ask *"How long to Guerrero?"*, wait until it **starts
  talking**, and cut in with **"No — mark Gough delivered instead."**

Watch the fence board on screen. You should see a row appear and get marked
**fenced stale**. That is the whole project working.

**Do this practice run at least twice before recording.** The timing of the
interruption is the entire demo and it takes one rehearsal to get right.

### A6 — Record (45 min including retakes)

Open **`DEMO_SCRIPT.md`** in the main project folder. It is written shot by
shot, with every word you say written out and every interruption timed.

**Follow it exactly.** Do not improvise — the timing is the demo.

**Recording software:**
- **Windows:** press `Win + G` (Game Bar) → record
- **Mac:** press `Cmd + Shift + 5` → Record Entire Screen

**Critical:** capture **system audio AND microphone**. Record ten seconds, stop,
play it back, and confirm you can hear both your voice and the assistant's
voice. People lose an hour to this.

**Target 4 minutes 30 seconds. Hard cap is 5:00.** Going over is worse than
cutting the last section.

**If something breaks on camera, do not restart.** Say what happened and keep
going. The brief specifically asks for a stress case, and a real failure handled
openly reads better than a fourth take. `DEMO_SCRIPT.md` has a table of exactly
what to say for each kind of failure.

### A7 — Save the video

Put the finished file in the `demo/` folder inside the project. Name it
`waypoint-demo.mp4`.

**Also upload it to YouTube as "Unlisted"** and copy the link — Darshan needs
that link for the submission form.

📱 **Send to the group:** `🎬 DEMO IS RECORDED. Length <mm:ss>. Link: <youtube link>. @Darshan it's yours.`

Then go to **"Uploading your work"** at the bottom.

---

## 🅱️ LANE B — AKSHAT — the real numbers and the real audio

**Right now this project has never made a sound. Your job is to change that and
write down honestly what happened.**

### B1 — Get a Rime key (10 min)

Go to **https://rime.ai** → sign up → **API Keys** in the dashboard → copy it.

You only need this one key. You do not need LiveKit for this lane.

> ⚠️ **This is a password. Never paste it into a chat, a document, or an AI
> chatbot.**

### B2 — Put it in the right place (5 min)

In your `waypoint` folder, copy the file **`.env.example`** and name the copy
**`.env.local`** — exactly that, starting with a dot.

Open it in Notepad/TextEdit and set this one line to your real key:

```
RIME_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

Leave everything else alone. Save.

### B3 — Measure how fast Rime is (15 min)

```
python evidence/measure_latency.py --warm 20 --compare-transport
```

This calls Rime about 40 times and times how long until the first audio comes
back. It takes a few minutes. It will write a report to
`evidence/results/latency.md`.

**Open that file and read it.** Then open **`team/worksheets/MEASUREMENTS.md`**
— that file is yours — and fill in every `TODO`.

**Write down exactly what the tool printed.** Not what you think it should have
said. If a run failed, write that it failed. If a number looks bad, write the
bad number. An honest modest number scores; an invented good one disqualifies.

The worksheet asks for your machine and your network too — fill those in, they
matter, because a number without them means nothing.

### B4 — Make the audio (15 min)

```
python evidence/measure_pronunciation.py --render
```

This makes Rime actually say the hard street names, twice each — once plainly,
once through our respelling layer. The audio files land in
`evidence/results/pronunciation/`.

### B5 — Actually listen to it (25 min) ← **this is the valuable one**

Nobody on this team has ever heard this project speak. You are about to be the
first.

Read **`docs/LISTENING_TEST.md`** for the method — it is short. The short
version: play each pair of clips **without looking at the filenames first**,
and score each one:

- **correct** — I would have driven to the right street / keyed the right code
- **usable** — slightly off, but obvious in context
- **wrong** — I would have gone to the wrong place
- **unclear** — could not tell

The words that matter most: **Gough** (should sound like *"Goff"*, not *"Gow"*),
**Guerrero**, **Divisadero**, and the gate codes (should be *"four four one
seven"*, **not** *"four thousand four hundred seventeen"*).

Now open **`team/worksheets/LISTENING_NOTES.md`** — yours — and fill in every
`TODO` with what you actually heard. **Say what you listened on** (earbuds,
headphones, laptop speakers — they are three different measurements).

**If the respelling makes it worse, write that down.** A finding that our own
feature does not help is a genuinely valuable result and it costs us nothing to
report it honestly. Making one up costs us everything.

📱 **Send to the group:** `📊 Numbers + listening test done. Time-to-first-audio: <number>ms. Gough came out as "<what you heard>". Both worksheets filled.`

Then go to **"Uploading your work"** at the bottom.

---

## 🅲 LANE C — DARSHAN — be the judge, then submit

**Two jobs. First you try to break our own instructions. Then you write the
submission.**

### C1 — Pretend you have never seen this project (30 min)

You are standing in for a judge who has ten minutes and no patience.

**Start completely fresh.** Download the ZIP again into a *different* folder
than the one you set up in step 0. Do not reuse anything. Do not fix anything as
you go — you are testing the instructions, not the project.

Now open the main **`README.md`** and follow it **exactly as written**, from the
top. Not what you know it means. What it literally says.

Open **`team/worksheets/VERIFICATION.md`** — that file is yours — and fill in
every `TODO` as you go. For each step: did it work, how long did it take, and
**what was wrong, unclear, or assumed something it did not say?**

Run each of these and record what actually happened:

```
pytest
```
```
python evidence/run_acceptance.py
```
```
python scripts/secret_scan.py
```
```
python -m waypoint.agent --print-config
```

> The last one is *supposed* to say credentials are missing and exit with an
> error. That is correct behaviour on a machine with no keys, not a bug — but
> note whether the README made that clear enough.

**Be harsh.** Every confusing sentence you find here is one a judge would have
hit instead. This is genuinely useful work, and finding nothing is a worse
outcome than finding five things.

📱 **Send to the group:** `Fresh-clone check done. Found <n> problems with our own README. VERIFICATION.md filled.`

### C2 — Write the submission (25 min)

Open **`SUBMISSION.md`** — that file is yours. Search it for `FILL:` and fill in
each one.

Everything you need is in **`HANDOFF.md`** in the main folder — it has the
one-liner, the problem statement, the technical claims, and an honest list of
what is and is not proven. Copy from there; do not invent anything.

**You will need from the others:**
- The YouTube link (from Arya)
- The measured numbers (from Akshat's `MEASUREMENTS.md`)

If either has not arrived yet, do everything else first and leave those two
blanks until last. Do not wait around.

### C3 — Final check before submitting (20 min)

Go through this list. Every box must be genuinely ticked.

- [ ] The demo video exists, is **under 5:00**, and you have watched it end to end
- [ ] You can hear **both** the person and the assistant in the video
- [ ] The video says out loud **which speech provider is being used** (it must
      say Rime) and shows it on screen
- [ ] The video shows **one deliberate failure or stress case** (the interruption)
- [ ] `pytest` → `549 passed`
- [ ] `python evidence/run_acceptance.py` → `6/6 scenarios passed (36 checks)`
- [ ] `python scripts/secret_scan.py` → **`clean`**
- [ ] Nobody's real API key is in any file that got uploaded — **check
      `.env.local` is NOT in the GitHub repo**
- [ ] Every number in `SUBMISSION.md` is one somebody actually measured
- [ ] No `FILL:` or `TODO` left in `SUBMISSION.md`

**The one that will disqualify us:** a real API key uploaded by accident. Run
`secret_scan.py` one final time after everything is uploaded and confirm it says
`clean`.

### C4 — Submit

Submit through the DataForge portal with the YouTube link and the GitHub link:
`https://github.com/darshanrajagoli/data-forge-rime-hadippa`

📱 **Send to the group:** `✅ SUBMITTED. We're done.`

---

## 📤 Uploading your work back to GitHub

**You do not need to install git or know how it works.** Do this in the browser.

1. Go to **https://github.com/darshanrajagoli/data-forge-rime-hadippa**
2. Click into the folder your file belongs in (e.g. click `team`, then
   `worksheets`)
3. Click **`Add file`** → **`Upload files`**
4. Drag your finished file in from your computer
5. In the box at the bottom, type what you did — e.g. `Akshat: filled in
   measurements and listening notes`
6. Click **`Commit changes`**

That is it. Because everyone owns different files, **nobody can overwrite anybody
else's work.** You cannot break anything here.

> ⚠️ **Before you upload anything, check it does not contain an API key.** If in
> doubt, open the file, press Ctrl+F, and search for your key. The only file
> that should ever contain one is `.env.local`, and **that file must never be
> uploaded.**

> **The video is too big for the drag-and-drop upload.** That is fine — the
> YouTube unlisted link is what actually gets submitted. Just paste the link in
> the group chat.

---

## 🤖 When you are stuck — using an AI to get through this

**This is expected. Use it early rather than burning 40 minutes.**

Any of ChatGPT, Gemini, or Claude will work. Arya has Claude Pro, which handles
long documents best — send the genuinely hard problems there.

### What to upload

Upload these **three files** at the start of your chat:

1. **`HANDOFF.md`** — from the main project folder. This explains the whole
   project to an AI.
2. **`team/WORKFLOW.md`** — this file.
3. **Whichever file you are actually working on** (your worksheet, or the file
   the error mentions).

### Then paste this exactly, filling in the blanks

```
I'm working on a hackathon project called Waypoint. I've uploaded three files:
HANDOFF.md explains the whole project, WORKFLOW.md is my task list, and the
third is the file I'm working on.

I'm doing Lane <A / B / C>, at step <A3 / B4 / C1 ...>.

I am not a programmer. Please give me exact commands to copy and paste, and
tell me what I should see when it works.

I'm on <Windows / Mac>.

What I did: <exactly what you typed>
What I expected: <what the workflow said would happen>
What actually happened: <paste the ENTIRE error message, all of it>

Please give me one step at a time and wait for me to tell you what happened
before giving me the next one.
```

### Rules for using the AI

- **Paste the whole error message.** All of it, including the boring parts. The
  useful line is usually the last one, but AIs need the rest to find it.
- **Never paste your API key.** If an error message contains your key, replace
  it with `<MY KEY>` before pasting. Seriously — this is a disqualifier.
- **Ask for one step at a time.** If it gives you ten commands at once, reply:
  *"Just give me the first one and wait for my result."*
- **If it suggests changing project files, stop and ask the group first.** You
  almost certainly do not need to. Nearly every problem at this stage is
  setup-related, not a bug in the project.
- **If it goes in circles twice, ask it to start over:** *"That didn't work.
  Forget your previous suggestions and think about this differently — what else
  could cause this?"*

### The three problems you are most likely to hit

| It says | It means | Fix |
|---|---|---|
| `'python' is not recognized` | Python isn't installed, or wasn't added to PATH | Reinstall Python and **tick "Add to PATH"** |
| `ModuleNotFoundError` | You forgot to activate the environment in this terminal | Run the `activate` command from step 0.4 |
| `401` or `Unauthorized` | The API key is wrong, or `.env.local` is misnamed | Check the file is called exactly `.env.local` and re-copy the key |

---

## 📱 WhatsApp messages — copy these

**When you start:**
```
Starting Lane <A/B/C>. Setup done, 549 tests passing.
```

**When you finish:**
```
Lane <A/B/C> done ✅ — <one line on what you produced>. Uploaded to GitHub.
```

**When you're stuck (say this early):**
```
Stuck on Lane <A/B/C> step <number>. Error: <first line of the error>.
Trying with AI now, will update in 15 min.
```

**When you're properly blocked:**
```
🚨 Blocked on <step>. Tried <what you tried>. Need help.
```

**Arya only, the one everyone is waiting for:**
```
🎬 DEMO IS RECORDED. Length <mm:ss>. Link: <youtube link>. @Darshan it's yours.
```

**Darshan only, the last one:**
```
✅ SUBMITTED. We're done. 🎉
```

---

## If time runs short

Cut in this order — **the top item is never cut**:

1. 🔒 **The demo video.** Without it we are not eligible. It is worth more than
   everything below combined.
2. 🔒 **The submission form.** Obviously.
3. Fresh-clone verification (Lane C1) — nice to have, not scored directly
4. The listening test (Lane B5)
5. The latency measurements (Lane B3)

**If you have to submit with worksheets unfilled, that is fine.** They are
internal notes and they live in `team/`, away from what judges read. An empty
`TODO` is honest. An invented number is a disqualification.

**A submitted project with an honest gap beats a perfect one that missed the
deadline.**

Good luck. 🚚
