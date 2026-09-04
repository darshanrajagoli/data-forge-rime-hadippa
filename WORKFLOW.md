# WORKFLOW — from here to submitted

**The code is finished.** 350 tests pass, the acceptance harness passes 6/6,
the docs are written. What is left is the part software cannot do: getting API
keys, listening to audio with human ears, talking into a microphone, and
pressing submit.

This page is the whole plan. Follow your lane top to bottom. **Nobody in this
plan ever waits for anybody else after the first five minutes.**

| Person | Lane | Claude | Needs API keys? |
|---|---|---|---|
| **Darshan** | A — repo, live agent, demo video | Pro | yes |
| **Arya** | B — measured evidence | Pro | yes |
| **Rahul** | C — pronunciation + listening test | free | yes (Rime only) |
| **Akshay** | D — verification + submission | free | no |

Rough timing: **2.5 to 3 hours** if you all start at once.

---

## THE ONE RULE

> **You only ever create or change files inside your own list. You never touch
> a file on someone else's list.**

That single rule is why nobody will ever get a git conflict.

| Person | Files you own — the only ones you may change |
|---|---|
| **Darshan** | `evidence/results/sessions/**`, `demo/**`, plus any real code fix |
| **Arya** | `evidence/results/latency.*`, `evidence/results/heard_accuracy.*`, `docs/MEASUREMENTS.md` |
| **Rahul** | `evidence/results/pronunciation/**`, `docs/LISTENING_NOTES.md` |
| **Akshay** | `SUBMISSION.md`, `docs/VERIFICATION.md` |

Nobody owns `README.md`, `RIME_EVIDENCE.md` or anything in `src/`. If you think
one of those is wrong, **post it in the group chat and let Darshan change it.**
Do not fix it yourself, even if the fix is obvious. Two people editing one file
is the only way this goes wrong.

### Saving your work — one command, always the same

```bash
# Mac / Linux
bash scripts/save.sh "what you just did"

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\save.ps1 "what you just did"
```

That script scans for leaked API keys, commits, pulls your teammates' work,
stacks yours on top, and pushes. Run it whenever you finish a step. If it ever
says "run this same command again", just run it again.

**Never run `git push --force`.** Never. If something looks broken, paste the
error into the group chat.

---

## STEP 0 — everybody, right now, at the same time (15 min)

Do all four of these in parallel. Do not wait for Darshan.

### 0a. Check you have Python 3.10 or newer

```bash
python --version
```

If that says 3.9 or lower, or "command not found":

- **Windows:** install from <https://www.python.org/downloads/> and **tick
  "Add python.exe to PATH"** on the first screen.
- **Mac:** `brew install python@3.12`  (if `brew` is missing, get it from
  <https://brew.sh>)

If `python` doesn't work but `python3` does, use `python3` everywhere below.

### 0b. Check you have git

```bash
git --version
```

If missing: **Windows** <https://git-scm.com/download/win> · **Mac**
`xcode-select --install`

Then set your name once (skip if you have used git before):

```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

### 0c. Get your own API keys — everyone gets their own

**Do not share keys over chat.** Each of you signs up separately. Both are
free.

1. **Rime** — <https://app.rime.ai/signup> → sign up → find your API key in the
   dashboard. *(If the organisers gave the team a Rime key, use that one
   instead.)*
2. **LiveKit Cloud** — <https://cloud.livekit.io> → sign up → create a project
   → **Settings → Keys** → copy the **URL**, **API Key** and **API Secret**.
   Akshay can skip this one.

Paste them into a note on your own machine. You will need them in step 1.

### 0d. Darshan only — put the repo on GitHub (5 min)

Everyone else: keep doing 0a–0c, this does not block you.

```bash
cd "C:/Users/darsh/OneDrive/Desktop/DataForge/waypoint"

git init
git add -A
git commit -m "Waypoint: turn-fenced voice agent on LiveKit + Rime"
```

Then create the repo. Easiest way, if you have the GitHub CLI:

```bash
gh auth login
gh repo create waypoint --public --source=. --remote=origin --push
```

If you don't have `gh`: go to <https://github.com/new>, name it `waypoint`,
make it **Public**, do **not** add a README or .gitignore, click Create, then:

```bash
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/waypoint.git
git push -u origin main
```

**Then post the repo URL in the group chat.** That is the only thing anyone is
waiting on, and it takes five minutes.

Two last things:

```bash
bash scripts/install_hooks.sh      # blocks any commit containing a credential
```

And fix the CI badge at the top of `README.md` — replace `REPLACE-ME` with your
GitHub username, then push again. GitHub Actions starts running the whole test
suite on Linux and Windows automatically; a green badge is evidence a judge can
click, produced on hardware none of us controls.

---

## STEP 1 — everybody (10 min)

### 1a. Get the code

Darshan: skip, you already have it. Everyone else:

```bash
git clone https://github.com/DARSHANS-USERNAME/waypoint.git
cd waypoint
```

### 1b. Install

```bash
# Mac / Linux
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,web]"

# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,web]"
```

> If PowerShell refuses with "running scripts is disabled", run this once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Every time you open a new terminal you must activate the venv again**
(`source .venv/bin/activate` or `.venv\Scripts\Activate.ps1`). If a command
says "module not found", this is why, 95% of the time.

### 1c. Prove it works before you add any keys

```bash
pytest
python evidence/run_acceptance.py
```

You should see **350 passed** and **6/6 scenarios passed**. This needs no keys
and no internet.

**If you see anything else, stop and post the output in the group chat.** Four
people getting this to pass on four different laptops *is* our
reproducibility evidence — a failure here is a real finding, not your mistake.

> Running these rewrites `evidence/results/acceptance.*` on your machine. Those
> two files are gitignored precisely so four people re-running the harness do
> not collide on a file nobody owns. The citable copy lives in
> `evidence/reference-run/` and only Darshan regenerates it. You do not need to
> do anything about this — it is here so the ignored file does not confuse you.

### 1d. Add your keys

```bash
# Mac / Linux
cp .env.example .env.local

# Windows PowerShell
Copy-Item .env.example .env.local
```

Open `.env.local` in any text editor and fill in the four values from step 0c.
Change nothing else.

`.env.local` is gitignored. It will never be committed. Do not paste its
contents anywhere.

### 1e. Preflight

```bash
python scripts/preflight.py
```

This makes a real Rime request with the real settings. **You want exit 0 and
all green.** Akshay: run `python scripts/preflight.py --offline` instead.

If Rime fails here, the model/voice pair is wrong — check
<https://docs.rime.ai/api-reference/voices> and post in the chat.

Now go to your lane. **From here on, nobody waits for anybody.**

---

## LANE A — Darshan: live session + demo video (90 min)

### A1. Run the agent and talk to it (15 min)

Simplest possible check, no browser:

```bash
python -m waypoint.agent console
```

Talk to it. Try: *"what's my next stop?"* then *"what's the gate code?"*
Listen for **"Goff Street"** (not "Gow") and **"four four one seven"** (not
"four thousand four hundred seventeen"). Press Ctrl-C to stop.

### A2. The visual console (15 min)

Two terminals, both with the venv activated:

```bash
# terminal 1
python -m waypoint.agent dev

# terminal 2
python web/server.py
```

Open <http://127.0.0.1:8080> and click **Connect**. Allow microphone access.

**Use a wired headset.** On laptop speakers the mic hears the agent and the
interruption detector fires on the agent's own voice.

Now practise the money shot until you can do it reliably:

1. Say *"How long to Guerrero?"*
2. Wait about one second — a row appears on the fence board marked **in flight**
3. **While it is still talking**, say *"No — mark Gough delivered instead."*
4. The Guerrero row flips to **fenced stale**, and the generation counter goes
   0 → 1

Then the write:

5. Say *"Mark Haight delivered."*
6. **Immediately**, while it speaks: *"Actually stop, wrong one."*
7. The counter under **writes blocked** goes up

If step 3 doesn't register the interruption, speak louder and more definitely.
The threshold is 400 ms on purpose so road noise doesn't trigger it.

Then commit whatever the session wrote:

```bash
bash scripts/save.sh "live session evidence"
```

### A3. Record the demo (45 min including retakes)

Open **`DEMO_SCRIPT.md`** and follow it shot by shot. Every line you say is
written out. Do one full dry run without recording first — the interruption
timing needs one rehearsal.

Before you record, confirm `WAYPOINT_DISPATCH_LATENCY_MS=1800` in `.env.local`.
**This is what makes the race visible on camera.** At 300 ms the lookup
finishes before you can interrupt and there is nothing to show.

Recording: OBS, or **Mac** `Cmd-Shift-5`, or **Windows** `Win-G`. Capture
system audio **and** microphone — check 10 seconds in that both are in the
file.

Target **4:30**. The hard cap is 5:00.

Then upload it (YouTube unlisted, or Drive with link sharing on) and **post the
link in the chat for Akshay**. Put the file in `demo/` if it is under 100 MB;
otherwise the link is enough.

### A4. You are the only person who edits shared files

If Rahul or Akshay reports that something in `README.md` or `RIME_EVIDENCE.md`
doesn't match reality, you make the change. Then:

```bash
bash scripts/save.sh "fix: <what they found>"
```

### A5. Final merge and check (15 min, at the end)

```bash
git pull --rebase
pytest
python evidence/run_acceptance.py
python scripts/secret_scan.py
git log --oneline | head -20
```

Then tell Akshay it is ready to submit.

---

## LANE B — Arya: measured evidence (60 min)

You are producing the numbers that go in the evidence file. **Your job is to
report what the tools actually print, not what we hope they print.** A slow
number reported honestly is worth more than a fast one that isn't real.

### B1. Latency (15 min)

```bash
python evidence/measure_latency.py --warm 20 --compare-transport
```

This creates `evidence/results/latency.md` and `latency.json`. Read the report.
It separates **cold** (first call, includes TLS setup) from **warm** — those
are never mixed, on purpose.

```bash
bash scripts/save.sh "latency measurements"
```

### B2. Heard-not-said accuracy (15 min)

```bash
python evidence/measure_heard_accuracy.py --cuts 12
```

This asks: when we don't have Rime's word timestamps, how wrong is our
estimate? Ground truth is Rime's real timings.

**If it says no word timestamps arrived, that is important — post it in the
chat immediately.** It would mean a claim in `RIME_EVIDENCE.md` needs
softening, and that is Darshan's edit to make.

```bash
bash scripts/save.sh "heard-not-said accuracy"
```

### B3 &nbsp;(removed &mdash; 10 minutes back)

There was a step here that ran `scripts/build_lexicon.py` to fetch Rime
phonemes. **That script has been deleted.** It posted JSON text to three
guessed URLs, none of them Rime's phonemize endpoint, so it could never have
worked. The shipped `respell` pronunciation strategy needs no phonemes at all.
Spend the ten minutes on B4 instead.

### B4. Write up the numbers (20 min)

Open **`docs/MEASUREMENTS.md`** — **you own this file.** It already exists as a
template with every blank marked `TODO`. You are filling in blanks, not writing
a document from scratch.

Paste the tables straight out of `evidence/results/latency.md` and
`heard_accuracy.md`. Keep the boundary notes that are already in the template —
they are what make the numbers mean something.

Then:

```bash
bash scripts/save.sh "measurements writeup"
```

---

## LANE C — Rahul: pronunciation + listening test (60 min)

You are the ears. You do not need Claude Pro for any of this.

### C1. Render the clips (10 min)

```bash
python evidence/measure_pronunciation.py --models coda mistv2
```

This writes `.wav` files and a report into
`evidence/results/pronunciation/`. It renders the same street names three
ways: untouched, respelled, and with phonemes.

### C2. Listen (25 min)

Open **`docs/LISTENING_TEST.md`** and follow it. Short version:

1. Use earbuds or headphones, not laptop speakers.
2. For each street, play the `none` clip and the `respell` clip **without
   looking at which is which**.
3. Score each: `correct` / `usable` / `wrong` / `unclear`.

The ones to focus on: **Gough** (should sound like "Goff"), **Haight** ("Hate"),
**Guerrero**, **Divisadero**, and the two gate codes (must be digits — "four
four one seven", not "four thousand...").

### C3. Write it down (15 min)

Open **`docs/LISTENING_NOTES.md`** — **you own this file.** It already exists as
a template with every blank marked `TODO`, including the results table with the
right fixtures already listed. Fill in your verdicts.

**If you can get one person outside the team to score the `none` clips, that
single outside verdict is worth more than all of ours.** Ask anyone nearby —
it takes them two minutes and there is a section for it in the template.

And if the respelling makes something sound *worse*, write that down. That is a
real finding and we would rather ship it than hide it.

### C4. Read the docs against reality (10 min)

Read `README.md` and `RIME_EVIDENCE.md`. You are looking for **anything that
claims something we did not actually do.** Overclaiming is the fastest way to
lose points with judges who check.

Do **not** edit those files. Post what you find in the chat and Darshan
changes it.

```bash
bash scripts/save.sh "listening test notes"
```

---

## LANE D — Akshay: verification + submission (60 min)

You are the judge's stand-in. **Behave like someone who has never seen this
project.** You do not need API keys and you do not need Claude Pro.

### D1. Clone fresh and verify (20 min)

Do this in a brand-new folder, not one that already has the project:

```bash
cd ~/Desktop          # or wherever
git clone https://github.com/DARSHANS-USERNAME/waypoint.git waypoint-check
cd waypoint-check
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

pytest
python evidence/run_acceptance.py
python scripts/secret_scan.py
python scripts/preflight.py --offline
```

**Write down exactly what each one printed**, including how long it took.

### D2. Record the verification (15 min)

Open **`docs/VERIFICATION.md`** — **you own this file.** It already exists as a
template with every blank marked `TODO`, including the results table and the
repository checklist.

The most valuable section is *"Did the README work as written?"*. Be blunt
there. A judge will hit exactly the same things you did, and we would much
rather find them now.

Anything wrong goes in the chat for Darshan to fix. Then re-verify.

### D3. Fill the submission (15 min)

Open `SUBMISSION.md` — **you own this file.** Replace every `FILL:`:

- repo URL
- demo video URL (from Darshan)
- team names and who did what
- the preflight date/result from Darshan

### D4. Final checklist and submit (10 min)

Work down the checklist at the bottom of `SUBMISSION.md`. Every box must be
ticked. In particular, check the repo really is **public** — open it in a
private/incognito window while logged out.

Then submit on the hackathon platform, and **post confirmation in the chat.**

```bash
bash scripts/save.sh "submission details and verification"
```

---

## If something goes wrong

Try these in order.

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | Your venv isn't active. `source .venv/bin/activate` (Windows: `.venv\Scripts\Activate.ps1`) |
| `python: command not found` | Use `python3` instead, everywhere |
| PowerShell "running scripts is disabled" | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `pytest` fails | Post the last 30 lines in the chat. Do not "fix" it — a real failure is information |
| Rime errors in preflight | Check `RIME_API_KEY` in `.env.local` has no quotes and no trailing space |
| Agent connects but says nothing | `LIVEKIT_URL` must start with `wss://` |
| Agent complains about a missing model file | `python -m waypoint.agent download-files` — not normally needed, the VAD model ships in the wheel, but this fixes it if it ever is |
| Browser: no microphone | Site must be `127.0.0.1`, not a LAN IP. Browsers block mic on insecure non-localhost origins |
| Barge-in doesn't register | Use a wired headset. Laptop speakers make the mic hear the agent |
| Agent hears itself, loops | Same fix: headset |
| `git push` rejected | Run the same `save.sh` command again |
| Rebase stopped / conflict | You edited someone else's file. `git rebase --abort`, then post in the chat |

### Asking Claude for help

When stuck, paste this into Claude (any tier) — it gives Claude what it needs
in one shot:

```
I'm working on a Python voice-agent project called Waypoint.
It uses livekit-agents 1.7.1 with the Rime TTS plugin.

I ran:      <the exact command>
I expected: <what should have happened>
I got:      <paste the FULL error, all of it>

My OS is <Windows 11 / macOS>, Python <output of python --version>.
I am on Lane <A/B/C/D> of WORKFLOW.md, step <number>.
```

**Two rules.** Never paste your API keys into a chat window — replace them with
`REDACTED`. And if Claude suggests editing a file you do not own, don't; post
the suggestion in the group chat instead.

---

## Definition of done

- [ ] Repo public on GitHub, clones clean *(Akshay verified)*
- [ ] GitHub Actions badge is green and the `REPLACE-ME` in its URL is fixed *(Darshan)*
- [ ] `pytest` → 350 passed, on at least three different laptops
- [ ] `python evidence/run_acceptance.py` → 6/6
- [ ] `python scripts/preflight.py` → exit 0 on the recording machine *(Darshan)*
- [ ] `python scripts/secret_scan.py` → clean
- [ ] Demo video under 5:00, uploaded, link in `SUBMISSION.md` *(Darshan)*
- [ ] `docs/MEASUREMENTS.md` filled *(Arya)*
- [ ] `docs/LISTENING_NOTES.md` filled *(Rahul)*
- [ ] `docs/VERIFICATION.md` filled *(Akshay)*
- [ ] Every `FILL:` in `SUBMISSION.md` replaced *(Akshay)*
- [ ] Submitted, confirmation posted in the chat *(Akshay)*

## The one thing that actually matters

If you are short on time, **the demo video and the public repo are the
submission.** Everything else strengthens it. Do those two properly before
polishing anything.

And if a measurement comes out worse than we hoped, **report it as it is.** The
brief says unverified performance numbers get no credit, and judges check.
A modest number with an honest method beats a good number nobody can reproduce
— and we have a fence, a fuzzer and 350 tests to stand on regardless.
