# 🚚 WAYPOINT — THE DO-THIS-NEXT LIST

> ✅ **All three lanes are complete.** Arrya recorded the demo, Akshat ran the
> measurements and the listening test, Rahul did the fresh-clone verification
> and everything he found is fixed. Nothing below needs doing again — it is
> kept as the record of how the work was split.

**You do not need to understand anything. Just do the steps in order.**

Every step tells you three things:

> **DO** — exactly what to type or click
> **YOU SHOULD SEE** — what appears if it worked
> **IF NOT** — exactly what to do instead

If what you see does not match, **stop and do the IF NOT.** Do not continue and
hope. Do not skip a step. Do not do steps out of order.

---

## 🗺️ WHO DOES WHAT

| Lane | Who | What | How long |
|---|---|---|---|
| 🅰️ | **Arrya** | Record the demo video | ~90 min |
| 🅱️ | **Akshay** | Get the real numbers + listen to the voice | ~75 min |
| 🅲 | **Rahul** | Test our instructions, then write the submission | ~75 min |

**Arrya has Claude Pro.** Akshay and Rahul have normal Claude / Gemini /
ChatGPT — that is plenty for these lanes.

**Start now. Do not wait for anybody.** All three lanes are independent by
design. Nobody is blocked on anybody.

**Your files — nobody else touches these, so you cannot break each other's
work:**

| Who | Files |
|---|---|
| **Arrya** | `demo/` |
| **Akshay** | `team/worksheets/MEASUREMENTS.md`, `team/worksheets/LISTENING_NOTES.md` |
| **Rahul** | `team/worksheets/VERIFICATION.md`, `SUBMISSION.md` |

---

## ⛔ THE THREE RULES

**1. Your API key goes in ONE file called `.env.local` and nowhere else.**
Never in a chat. Never in a document. Never pasted into ChatGPT, Gemini or
Claude. *Leaking a key disqualifies the whole team instantly.*

**2. Never type a number you did not see on your own screen.**
If something did not run, write "did not run". A blank is fine. A made-up
number disqualifies us.

**3. Only edit the files your lane says you own.**

---
---

# 📦 PART 0 — SETUP

**All three of you do this. About 15 minutes.**

---

### STEP 1 — Download the project

**DO:** Open this link in Chrome:

```
https://github.com/darshanrajagoli/data-forge-rime-hadippa
```

Click the green button that says **`< > Code`**.
Then click **`Download ZIP`**.

**YOU SHOULD SEE:** A file downloading called
`data-forge-rime-hadippa-main.zip`

---

### STEP 2 — Unzip it

**DO:** Go to your **Downloads** folder. Right-click the zip file.

- 🪟 Windows → click **Extract All** → click **Extract**
- 🍎 Mac → double-click it

**DO:** Drag the folder that appears onto your **Desktop**.

**YOU SHOULD SEE:** A folder on your Desktop called
`data-forge-rime-hadippa-main`

---

### STEP 3 — Rename the folder

**DO:** Right-click that folder → **Rename** → type `waypoint` → press Enter.

**YOU SHOULD SEE:** A folder on your Desktop called `waypoint`

> This is only so the rest of this document matches what you see on screen.

---

### STEP 4 — Open the black window (the "terminal")

The terminal is just a window where you type commands. That is all it is.

**🪟 IF YOU ARE ON WINDOWS:**

**DO:** Double-click the `waypoint` folder to open it.
Click once on the **address bar** at the top (where the folder path is shown).
Type `powershell` and press **Enter**.

**🍎 IF YOU ARE ON MAC:**

**DO:** Right-click the `waypoint` folder → **Services** → **New Terminal at
Folder**.

*(If that option is missing: open **Terminal** from Applications → Utilities,
type `cd ` — with a space after it — then drag the `waypoint` folder into the
Terminal window, then press Enter.)*

**YOU SHOULD SEE:** A window with a blinking cursor.

> 📋 **How to paste into this window:** Windows → **right-click**.
> Mac → **Cmd+V**. Ctrl+V usually does not work here.

---

### STEP 5 — Check if Python is installed

**DO:** Copy this, paste it into the black window, press **Enter**:

```
python --version
```

**YOU SHOULD SEE:** Something like `Python 3.12.0` → **skip to STEP 7.**

**IF YOU SEE** `not recognized`, `command not found`, or the Microsoft Store
opens → **go to STEP 6.**

---

### STEP 6 — Install Python (only if STEP 5 failed)

**DO:** Go to **https://www.python.org/downloads/** and click the big yellow
download button. Run the file that downloads.

> 🚨 **WINDOWS — DO NOT MISS THIS.** On the very first screen there is a
> checkbox at the bottom saying **"Add python.exe to PATH"**. **TICK IT.**
> Then click Install.
> If you miss it, nothing else in this document will work.

**DO:** When it finishes, **close the black window completely**, then do
**STEP 4** again, then **STEP 5** again.

**YOU SHOULD SEE:** `Python 3.12.0` or similar.

**IF NOT:** Go to the **🤖 STUCK?** section near the bottom of this page.

---

### STEP 7 — Create the workspace

**DO:** Paste this and press Enter:

```
python -m venv .venv
```

**YOU SHOULD SEE:** Nothing at all. It goes quiet for about 20 seconds and then
gives you a fresh cursor. **Silence means it worked.**

---

### STEP 8 — Turn the workspace on

**🪟 WINDOWS — DO:**

```
.venv\Scripts\activate
```

**🍎 MAC — DO:**

```
source .venv/bin/activate
```

**YOU SHOULD SEE:** The start of your line now says `(.venv)` — like
`(.venv) PS C:\Users\you\Desktop\waypoint>`

**IF NOT:** Go to the **🤖 STUCK?** section.

> 🔁 **REMEMBER THIS FOREVER.** Every time you open a NEW black window you must
> do STEP 8 again first. If a command ever says `ModuleNotFoundError` — that is
> why. Do STEP 8, then try again.

---

### STEP 9 — Install the project

**DO:** Paste this and press Enter:

```
pip install -e ".[dev]"
```

**YOU SHOULD SEE:** A lot of scrolling text for 2–3 minutes, ending with a line
starting `Successfully installed`.

**IF NOT:** If the last lines say `ERROR`, go to the **🤖 STUCK?** section.

> Yellow `WARNING` lines are completely fine. Ignore them.

---

### STEP 10 — Check everything works

**DO:** Paste this and press Enter:

```
pytest
```

**YOU SHOULD SEE:** About 30 seconds of dots, then:

```
626 passed
```

**IF NOT:** Go to the **🤖 STUCK?** section.

---

### ✅ STEP 11 — Tell the group

**DO:** Send to WhatsApp:

```
Setup done ✅ 626 passed. Starting Lane <A / B / C>.
```

**Now go to your lane below. Ignore the other two lanes completely.**

---
---

# 🅰️ LANE A — ARRYA — THE DEMO VIDEO

**This is the most important job on the team.** Without this video we are not
allowed to be judged at all. Everything else is worth less than this.

Set aside about 90 minutes.

---

### STEP A1 — Get the LiveKit keys

**DO:** Go to **https://cloud.livekit.io** → **Sign up** → use your Google
account.

**DO:** It asks you to create a project. Call it `waypoint`. Click through.

**DO:** On the left, click **Settings** → **Keys** → **Create key** →
**Create**.

**DO:** A box appears with three values. **Copy all three into Notepad** and
leave it open.

**YOU SHOULD SEE:** Three values —
- a **URL** starting `wss://`
- an **API Key** starting `API`
- an **API Secret** (long random string)

> 🚨 **These are passwords.** Never paste them into any chat, document,
> ChatGPT, Gemini or Claude.

---

### STEP A2 — Get the Rime key

**DO:** Go to **https://rime.ai** → **Sign up**.

**DO:** In the dashboard find **API Keys**. Copy it into your Notepad with the
others.

**YOU SHOULD SEE:** A fourth long random string.

---

### STEP A3 — Make the keys file

**DO:** Open the `waypoint` folder on your Desktop.

**DO:** Find the file called **`.env.example`**. Copy it and paste it back into
the same folder. *(Windows: Ctrl+C then Ctrl+V. Mac: Cmd+C then Cmd+V.)*

**DO:** Rename the copy to exactly:

```
.env.local
```

Including the dot at the front. Nothing else.

> 🪟 **Windows may hide the `.env` part.** If so: File Explorer → **View** menu
> → tick **File name extensions**. Now you can see it.

**YOU SHOULD SEE:** Two files side by side — `.env.example` and `.env.local`

---

### STEP A4 — Put your keys in that file

**DO:** Right-click `.env.local` → **Open with** → **Notepad** (Mac:
**TextEdit**).

**DO:** Find these four lines near the top. Replace the fake values after each
`=` with your real ones:

```
LIVEKIT_URL=wss://waypoint-xxxxx.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RIME_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

> ⚠️ No spaces around the `=`. No quote marks. Just `NAME=value`.

**DO:** Change nothing else in the file. Save it. (Ctrl+S / Cmd+S.)

---

### STEP A5 — Test that the keys work

**DO:** Back in your black window, paste:

```
python scripts/preflight.py
```

**YOU SHOULD SEE:** After about 20 seconds, near the bottom, the word:

```
Ready
```

**IF YOU SEE `401` or `Unauthorized`:** Your Rime key is wrong, or `.env.local`
is misnamed. Redo **STEP A3** and **STEP A4** carefully.

**IF YOU SEE ANYTHING ELSE RED:** Go to the **🤖 STUCK?** section. This is the
step most likely to need help.

> 🚨 **Do not go to STEP A6 until this says `Ready`.** This step actually calls
> Rime and checks the voice comes back. Once it passes, the hard part is over.

---

### ✅ STEP A6 — Tell the group

```
Preflight green ✅ Rime is answering. Recording next.
```

---

### STEP A7 — Make the demo dramatic

**DO:** Open `.env.local` in Notepad again.

**DO:** Find this line and make sure it says **1800**:

```
WAYPOINT_DISPATCH_LATENCY_MS=1800
```

**DO:** Save and close.

> This makes the assistant take 1.8 seconds to look things up, so the
> interruption is actually visible on camera. Any faster and there is nothing
> to film.

---

### STEP A8 — Get your headphones

**DO:** Plug in **wired headphones or earbuds**.

> 🚨 **Not laptop speakers.** The microphone will hear the assistant's own
> voice and interrupt it constantly, and the whole demo falls apart. This is
> not optional.

---

### STEP A9 — Start it up (two windows)

**DO:** In your existing black window, paste:

```
python web/server.py
```

**YOU SHOULD SEE:** A line mentioning `8080`.
**Leave this window open and alone.** Do not type anything else in it.

**DO:** Open a **SECOND** black window: do **STEP 4** again, then **STEP 8**
again (the `activate` one).

**DO:** In that second window, paste:

```
python -m waypoint.agent dev
```

**YOU SHOULD SEE:** Startup text that stops scrolling and waits.

**IF NOT:** Go to the **🤖 STUCK?** section.

---

### STEP A10 — Practice (at least twice)

**DO:** Open Chrome and go to:

```
http://localhost:8080
```

**DO:** Click **Allow** when it asks for your microphone.

**DO:** Say out loud: *"What's my next stop?"*

**YOU SHOULD SEE + HEAR:** A voice answers with an address.

**IF NOTHING HAPPENS:** Check your headphones are the selected microphone in
your computer's sound settings, then refresh the page.

**DO:** Now the important one. Say:

> *"How long to Guerrero?"*

**WAIT** until the voice **starts talking**. Then immediately cut in with:

> *"No — mark Gough delivered instead."*

**YOU SHOULD SEE:** On the screen, a row appears and turns into
**`fenced stale`**.

**That is the entire project working. That is what you are filming.**

**DO:** Repeat this **at least twice more** until the timing feels natural.
The timing IS the demo.

---

### STEP A11 — Record

**DO:** Open the file **`DEMO_SCRIPT.md`** in the main `waypoint` folder —
either in Notepad, or just read it on the GitHub website.

**It contains every single word you say, in order, with timings.** Follow it
exactly. Do not improvise.

**DO — start recording:**
- 🪟 Windows: press **`Win` + `G`** → click the record button
- 🍎 Mac: press **`Cmd` + `Shift` + `5`** → **Record Entire Screen** → Record

> 🚨 **BEFORE THE REAL TAKE:** record 10 seconds, stop, play it back.
> **You must hear BOTH your voice AND the assistant's voice.** If you only hear
> one, fix it now. People lose an hour to this.

**Target: 4 minutes 30 seconds. Hard limit: 5 minutes.**

**IF SOMETHING BREAKS ON CAMERA: do not restart.** Say what happened out loud
and keep going. The competition specifically asks for a stress case, and a real
failure handled openly scores better than a fourth take. `DEMO_SCRIPT.md` has a
table of exactly what to say for each kind of failure.

---

### STEP A12 — Save it and post the link

**DO:** Put the finished video into the `demo/` folder inside `waypoint`. Name
it `waypoint-demo.mp4`.

**DO:** Go to **https://youtube.com** → **Create** → **Upload video** → drag
your file in.

**DO:** On the visibility screen choose **Unlisted**.
*(Not Private — judges must be able to open it.)*

**DO:** Copy the link.

**DO:** Now put that link in two places, on the GitHub website:

1. Go to `https://github.com/darshanrajagoli/data-forge-rime-hadippa`
2. Click **`README.md`**
3. Click the **pencil icon** (top right)
4. Find the line saying `FILL: unlisted YouTube link`
5. Replace just that text with your link
6. Scroll down → click **Commit changes**
7. **Now do exactly the same for `SUBMISSION.md`**

**IF YOU'D RATHER NOT:** paste the link in the group and say **"Rahul please
add the link"**. But say which one you did, so it does not get done twice or
not at all.

---

### ✅ STEP A13 — Tell the group

```
🎬 DEMO IS RECORDED. Length <mm:ss>. Link: <paste link>
README + SUBMISSION updated: <yes / no, Rahul please do it>
```

**🎉 Lane A done. You just saved the submission.**

---
---

# 🅱️ LANE B — AKSHAY — THE REAL NUMBERS AND THE REAL VOICE

**Right now this project has never made a single sound. You are about to be the
first person on Earth to hear it talk.**

Set aside about 75 minutes.

---

### STEP B1 — Get a Rime key

**DO:** Go to **https://rime.ai** → **Sign up** (Google login is fine).

**DO:** In the dashboard find **API Keys**. Copy the key into Notepad.

**YOU SHOULD SEE:** A long random string.

> 🚨 **This is a password.** Never paste it into any chat, document, ChatGPT,
> Gemini or Claude.

> You do **not** need LiveKit for this lane. Only Rime.

---

### STEP B2 — Make the keys file

**DO:** Open the `waypoint` folder on your Desktop.

**DO:** Find **`.env.example`**. Copy it, paste it back into the same folder.

**DO:** Rename the copy to exactly:

```
.env.local
```

Including the dot at the front.

> 🪟 **Windows hiding the `.env` part?** File Explorer → **View** menu → tick
> **File name extensions**.

---

### STEP B3 — Put your key in it

**DO:** Right-click `.env.local` → **Open with** → **Notepad** (Mac:
**TextEdit**).

**DO:** Find this line and replace the fake value with your real key:

```
RIME_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

**DO:** Change **nothing else**. Save.

> No spaces around the `=`. No quote marks.

---

### STEP B4 — Measure how fast Rime is

**DO:** In your black window, paste:

```
python evidence/measure_latency.py --warm 20 --compare-transport
```

**YOU SHOULD SEE:** It runs for 3–5 minutes printing progress, then says it
wrote a file.

**IF YOU SEE `401`:** Your key is wrong or the file is misnamed. Redo
**STEP B2** and **STEP B3**.

**IF ANYTHING ELSE GOES RED:** Go to the **🤖 STUCK?** section.

---

### STEP B5 — Read the results

**DO:** Open this file (double-click it, or open in Notepad):

```
waypoint / evidence / results / latency.md
```

**YOU SHOULD SEE:** A table with numbers in milliseconds.

---

### STEP B6 — Write the numbers down

**DO:** Open this file — **this file is yours:**

```
waypoint / team / worksheets / MEASUREMENTS.md
```

**DO:** Every place it says `TODO`, replace it with the real answer.

> 🚨 **Copy the numbers exactly as they appear on your screen.** Not what you
> think they should be. If a run failed, write "run failed". If a number looks
> bad, write the bad number. **An honest bad number scores points. An invented
> good one disqualifies us.**

It also asks which laptop and which wifi you are on. Fill those in — a speed
number without them means nothing.

**DO:** Save the file.

---

### STEP B7 — Make the audio

**DO:** In your black window, paste:

```
python evidence/measure_pronunciation.py --render
```

**YOU SHOULD SEE:** It runs for 2–3 minutes and says it wrote files.

---

### STEP B8 — 🎧 LISTEN TO IT — this is the valuable bit

**DO:** Open this folder:

```
waypoint / evidence / results / pronunciation /
```

**YOU SHOULD SEE:** A pile of audio files. Each street name has **two**
versions — one plain, one through our pronunciation fixer.

**DO:** Put headphones on. Play them.

**DO — the trick that makes this real:** play each pair **without looking at
the filename first.** Guess which is which, then check. That way you are
judging the sound, not your expectation.

**Listen for these four specifically:**

| Word | Should sound like | Wrong sounds like |
|---|---|---|
| **Gough** | "Goff" | "Gow" / "Goo" |
| **Guerrero** | "Ge-rare-oh" | anything else |
| **Divisadero** | "Div-iss-a-dare-oh" | anything else |
| Gate code **4417** | "four four one seven" | "four thousand four hundred seventeen" |

**Score each one:**

- ✅ **correct** — I'd have driven to the right street / keyed the right code
- 🟡 **usable** — a bit off, but obvious in context
- ❌ **wrong** — I'd have gone to the wrong place
- ❓ **unclear** — couldn't tell

---

### STEP B9 — Write down what you heard

**DO:** Open this file — **this file is yours:**

```
waypoint / team / worksheets / LISTENING_NOTES.md
```

**DO:** Fill in every `TODO` with what you **actually heard**.

**DO:** Say what you listened on — earbuds, over-ear headphones, or laptop
speakers. Those are three different measurements.

> 🚨 **If our pronunciation fixer makes it WORSE, write that down.** That is a
> genuinely valuable finding and it costs us nothing to report honestly.
> Pretending otherwise costs us everything.

**DO:** Save the file.

---

### ✅ STEP B10 — Tell the group

```
📊 Numbers + listening done ✅
Time to first audio: <number> ms
"Gough" came out as: "<what you actually heard>"
Both worksheets filled. Uploading now.
```

**DO:** Now go to **📤 UPLOAD YOUR WORK** near the bottom of this page.

---
---

# 🅲 LANE C — RAHUL — BE THE JUDGE, THEN SUBMIT

**Two jobs. First you try to break our own instructions. Then you write the
submission.**

**You need ZERO API keys for this lane — you can start right now.**

Set aside about 75 minutes.

---

### STEP C1 — Start completely fresh

You are pretending to be a judge who has never seen this project and has no
patience.

**DO:** Download the ZIP again (**STEP 1**), but this time put it in a
**different folder** — e.g. `Desktop/judge-test`.

**DO NOT** reuse the folder you set up in Part 0. A clean start is the point.

---

### STEP C2 — Follow our README like a stranger

**DO:** Open **`README.md`** in that new folder.

**DO:** Follow it **exactly as written, from the top.** Not what you know it
means — what it literally says.

> 🚨 **Do not fix anything as you go.** You are testing the instructions, not
> the project. Every confusing sentence you find is one a judge would have hit
> instead.

**DO:** Keep this file open beside you — **this file is yours:**

```
waypoint / team / worksheets / VERIFICATION.md
```

Write in it as you go: did each step work, how long it took, and **what was
wrong, unclear, or assumed something it did not say.**

> Finding nothing is a worse result than finding five things. Be harsh.

---

### STEP C3 — Run the four checks

**DO:** Run each of these and write down exactly what happened.

**Check 1:**
```
pytest
```
**YOU SHOULD SEE:** `626 passed`

**Check 2:**
```
python evidence/run_acceptance.py
```
**YOU SHOULD SEE:** `6/6 scenarios passed (36 checks)`

**Check 3:**
```
python scripts/secret_scan.py
```
**YOU SHOULD SEE:** the word `clean`

**Check 4:**
```
python -m waypoint.agent --print-config
```
**YOU SHOULD SEE:** A settings box, then an error saying credentials are
missing.

> ⚠️ **Check 4 is SUPPOSED to error.** You have no API keys, so that is correct
> behaviour, not a bug. But write down whether the README made that clear
> enough — if it confused you, it will confuse a judge.

---

### ✅ STEP C4 — Tell the group

```
Fresh-clone test done ✅
Found <n> problems with our own README.
VERIFICATION.md filled in.
```

---

### STEP C5 — Write the submission

**DO:** Open this file — **this file is yours:**

```
waypoint / SUBMISSION.md
```

**DO:** Press **Ctrl+F**, search for `FILL:`, and fill in each one.

**DO:** Everything you need is already written in **`HANDOFF.md`** in the main
folder — the one-line description, the problem, what is proven, and an honest
list of what is not. **Copy from there. Invent nothing.**

**You will need from the others:**
- 🎬 The YouTube link (from Arrya)
- 📊 The measured numbers (from Akshay)

**If they have not arrived yet, do everything else first and leave those two
blank until last. Do not sit and wait.**

---

### STEP C6 — Check the demo link is in the READMEs

**DO:** Go to `https://github.com/darshanrajagoli/data-forge-rime-hadippa`

**DO:** Open **`README.md`** and look at the **Deliverables** table at the very
top. Check whether the first row still says `FILL: unlisted YouTube link`.

**DO:** Do the same for **`SUBMISSION.md`**.

**IF THEY STILL SAY `FILL:`** — check the group chat; Arrya may have done it.
If not, do it yourself: click the file → **pencil icon** → replace the text →
**Commit changes**.

> 🚨 A submission whose own README does not link the demo is one a judge may
> never find the demo in.

---

### STEP C7 — Final check before submitting

**DO:** Tick every box. Every one must be genuinely true.

- [ ] The demo video exists and you have watched it all the way through
- [ ] It is **under 5:00**
- [ ] You can hear **both** the person and the assistant in it
- [ ] It says out loud **"Rime"** and shows it on screen
- [ ] It shows the interruption / stress case
- [ ] `pytest` → `626 passed`
- [ ] `python evidence/run_acceptance.py` → `6/6 scenarios passed`
- [ ] `python scripts/secret_scan.py` → **`clean`**
- [ ] No `FILL:` left anywhere in `SUBMISSION.md`
- [ ] Every number in `SUBMISSION.md` is one somebody actually measured
- [ ] **`.env.local` is NOT on GitHub** — go look at the file list and confirm

> 🚨 **The one that disqualifies us:** an API key uploaded by accident. Run
> `secret_scan.py` one last time after everything is uploaded. It must say
> `clean`.

---

### STEP C8 — Submit

**DO:** Go to the DataForge submission portal.

**DO:** Submit with:
- The YouTube link
- `https://github.com/darshanrajagoli/data-forge-rime-hadippa`

**IF THE PORTAL LOGIN IS NOT YOURS:** post both links in the group and say
**"ready to submit"**. Do not assume somebody else is doing it.

---

### ✅ STEP C9 — Tell the group

```
✅ SUBMITTED. We're done. 🎉
```

---
---

# 📤 UPLOAD YOUR WORK

**You do not need git. You do not need to install anything. Do it in Chrome.**

---

**STEP U1 — DO:** Go to
`https://github.com/darshanrajagoli/data-forge-rime-hadippa`

**STEP U2 — DO:** Click into the folder your file belongs in.
*Example for Akshay: click **`team`** → click **`worksheets`***

**STEP U3 — DO:** Click **`Add file`** (top right) → **`Upload files`**

**STEP U4 — DO:** Drag your finished file from your computer into the box.

**STEP U5 — DO:** In the text box at the bottom, type what you did. For example:

```
Akshay: filled in measurements and listening notes
```

**STEP U6 — DO:** Click the green **`Commit changes`** button.

**YOU SHOULD SEE:** Your file now in the list, with your message beside it.

---

> 🚨 **BEFORE YOU UPLOAD ANYTHING:** open the file and press Ctrl+F. Search for
> your API key. If it is in there, take it out. The only file that should ever
> contain a key is `.env.local`, and **that file must never be uploaded.**

> 🎬 **The video is too big to upload this way.** That is fine — the YouTube
> link is what actually gets submitted.

> ✅ **You cannot break anybody else's work.** Everyone owns different files.

---
---

# 🤖 STUCK? USE AN AI

**This is expected. Do this after 10 minutes of being stuck, not 40.**

ChatGPT, Gemini or Claude all work. **Arrya has Claude Pro** — send the really
hard ones there.

---

### STEP S1 — Upload three files into the chat

1. **`HANDOFF.md`** — from the main `waypoint` folder
   *(this single file teaches the AI the entire project)*
2. **`team/WORKFLOW.md`** — this file
3. **The file you are stuck on** — your worksheet, or whatever the error
   mentions

> Just drag them into the chat box. ChatGPT, Gemini and Claude all accept file
> uploads.

---

### STEP S2 — Copy this, fill in the blanks, send it

```
I'm working on a hackathon project called Waypoint. I've uploaded three files:
HANDOFF.md explains the whole project, WORKFLOW.md is my step-by-step task
list, and the third is the file I'm stuck on.

I am doing Lane <A / B / C>, at STEP <A5 / B4 / C3 ...>.

I am NOT a programmer. Please give me exact commands to copy and paste, and
tell me what I should see on screen when it works.

I am on <Windows / Mac>.

WHAT I TYPED:
<paste exactly what you typed>

WHAT THE WORKFLOW SAID I'D SEE:
<copy the "YOU SHOULD SEE" line from that step>

WHAT ACTUALLY HAPPENED:
<paste the ENTIRE error message — all of it, including the boring parts>

Please give me ONE step at a time and wait for me to tell you what happened
before giving me the next one.
```

---

### STEP S3 — Rules for talking to the AI

| ✅ Do this | ❌ Not this |
|---|---|
| Paste the **whole** error, all of it | Paste just the last line |
| Ask for **one step at a time** | Let it dump 10 commands on you |
| Replace your key with `<MY KEY>` before pasting | 🚨 Ever paste a real key |
| After 2 failed attempts say: *"That didn't work. Forget your previous suggestions and think about this differently."* | Keep going round in circles |

> 🚨 **If it tells you to change project files, stop and ask the group first.**
> You almost certainly do not need to. At this stage nearly every problem is
> setup, not a bug in the project.

---

### The three problems you will probably hit

| Message on screen | What it means | Fix |
|---|---|---|
| `'python' is not recognized` / `command not found` | Python not installed, or the PATH box was not ticked | Redo **STEP 6**, tick "Add python.exe to PATH" |
| `ModuleNotFoundError` | You opened a new black window and forgot to turn the workspace on | Do **STEP 8**, then try again |
| `401` / `Unauthorized` | Key is wrong, or `.env.local` is misnamed | Recheck the file is named exactly `.env.local`, re-copy the key |

---
---

# 📱 WHATSAPP MESSAGES — COPY THESE

**When you start:**
```
Starting Lane <A/B/C>. Setup done, 626 passed ✅
```

**When you finish:**
```
Lane <A/B/C> done ✅ — <one line on what you produced>. Uploaded to GitHub.
```

**When you're stuck (send this EARLY):**
```
Stuck on Lane <A/B/C> STEP <number>.
Error says: <first line of the error>
Trying with AI now, will update in 15 min.
```

**When you're properly blocked:**
```
🚨 Blocked on STEP <number>. Tried <what you tried>. Need help.
```

**Arrya — the one everyone is waiting for:**
```
🎬 DEMO IS RECORDED. Length <mm:ss>. Link: <youtube link>
README + SUBMISSION updated: <yes / no, Rahul please do it>
```

**Rahul — the last one:**
```
✅ SUBMITTED. We're done. 🎉
```

---
---

# ⏰ IF TIME RUNS OUT

**Cut from the bottom. Never cut the top two.**

| | Task | |
|---|---|---|
| 1 | 🔒 **The demo video** | Without it we are not eligible. Worth more than everything below combined. |
| 2 | 🔒 **Actually submitting** | Obviously. |
| 3 | The fresh-clone test (Lane C1–C4) | Nice to have |
| 4 | The listening test (Lane B8–B9) | Nice to have |
| 5 | The speed measurements (Lane B4–B6) | Nice to have |

**Submitting with worksheets half-empty is completely fine.** They are internal
notes, they live in `team/`, and judges do not read them. A blank `TODO` is
honest.

**A submitted project with an honest gap beats a perfect one that missed the
deadline.**

---

**Go. 🚚**
