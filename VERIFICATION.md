# Independent verification

**Verified by:** Rahul · **Date:** 2026-09-06
**Machine:** Windows 11 Home (10.0.26280), Python 3.14.2 — a fresh ZIP download, no prior setup
**API keys used:** none

---

## Results

| Step | Command | Result | Time taken |
|---|---|---|---|
| Clone | Downloaded ZIP from GitHub, extracted to `judge-test/` | ✅ extracted cleanly | ~30s |
| Install | `pip install -e ".[dev]"` | ✅ installed successfully | ~45s |
| Test suite | `pytest` | ✅ 628 passed in 30.85s | ~31s |
| Acceptance | `python evidence/run_acceptance.py` | ✅ 6/6 scenarios, 36 checks | ~5s |
| Mutation test (core) | `python evidence/mutation_test.py` | ✅ 15/15 mutants caught | ~299s |
| Mutation test (wiring) | `python evidence/mutation_test_ii.py` | ✅ 19/19 mutants caught | ~232s |
| Secret scan | `python scripts/secret_scan.py` | ✅ clean — "No credential found in the repository." | ~1s |
| Offline preflight | `python scripts/preflight.py --offline` | ✅ 6/6 PASS, 1 WARN (Rime shipped path skipped — expected with `--offline`) | ~35s |

**print-config (not in the table above but also run):**

`python -m waypoint.agent --print-config`

Shows the full settings banner (Rime coda/lyra, WebSocket, PCM 22050 Hz, etc.), then exits code 1 with:
`Not runnable yet — missing: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, RIME_API_KEY`

This is correct and expected: the config layer works, but you need credentials to actually connect.

---

## Did the README work as written?

No. Three problems, ranked by how much they would block a judge:

**Issue 1 — `cd waypoint` does not exist**

The "Try it in 60 seconds" section says:
`git clone <this repo> && cd waypoint`

The repo clones as `data-forge-rime-hadippa` (or `data-forge-rime-hadippa-main` from a ZIP download), not `waypoint`. A judge following this literally will get `cd: no such file or directory` on the very first step. The internal `WORKFLOW.md` had the team rename the folder to `waypoint`, but the README does not mention this.

*Fix:* change `cd waypoint` to `cd data-forge-rime-hadippa` (or tell the reader the directory name matches the repo name).

**Issue 2 — Virtual-environment activation command is ambiguous**

The next line says:
`python -m venv .venv && . .venv/Scripts/activate   # Linux/macOS: . .venv/bin/activate`

This is inside a `bash` code block yet uses a **Windows** path (`Scripts`). The `.` (dot-source) syntax works in bash and zsh but **not** in PowerShell, which is the default shell on Windows, where `Scripts/` is the correct directory. A Windows user following this in PowerShell needs `.\.venv\Scripts\Activate.ps1`. A Linux/macOS user needs `. .venv/bin/activate`.

The comment says "Linux/macOS: . .venv/bin/activate" — so the main command is implicitly Windows-bash, but most Windows users don't have bash.

*Fix:* Show both commands clearly, or default to the Unix path (the majority case) and note the Windows alternative.

**Issue 3 — Mutation test target count is inconsistent**

The README's inline bash comment says:
`python evidence/mutation_test_ii.py  # 13 targets, everything else`

But the actual output is 19/19, and the README's own prose later says "34 of 34, none surviving" (which matches 15 + 19 = 34, not 15 + 13 = 28). The "28 targets" statement in the same paragraph is also wrong. Minor, but a judge counting targets will notice the discrepancy.

*Fix:* Change "13 targets" to "19 targets" and "28 targets" to "34 targets".

---

## Steps the README does not mention but that were needed

1. Correcting the directory name after clone — see Issue 1 above. Had to figure out the actual directory name.
2. Using PowerShell activation syntax on Windows — `.\.venv\Scripts\Activate.ps1` instead of `. .venv/Scripts/activate`.

Otherwise, the setup was genuinely smooth: `pip install -e ".[dev]"` installed everything in one command with no missing system dependencies, and all verification commands ran exactly as documented.

---

## Repository check

- [x] Repo is public — TODO: check in incognito window (requires browser, not done from CLI)
- [x] `.env.local` is not in the repo — only `.env.example` is present in the file tree
- [ ] `git log -p | grep -i "api.key\|secret"` shows no real credential — cannot run: ZIP download, not a git clone
- [x] `evidence/results/` contains the committed artifacts — yes: `acceptance.json`, `acceptance.md`, `latency.json`, `latency.md`, `pronunciation/`, `sessions/`
- [ ] Demo video link works from a logged-out browser — TODO: waiting on Arrya for the YouTube link
- [ ] GitHub Actions verify workflow is green on the latest commit, and the badge URL in README.md no longer says REPLACE-ME — badge URL points to `darshanrajagoli/data-forge-rime-hadippa`, not REPLACE-ME. TODO: verify green status in browser.

## Anything I could not verify

1. Anything requiring API keys — Rime TTS synthesis, actual audio output, LiveKit connection, `measure_latency.py`, `measure_pronunciation.py`, `measure_heard_accuracy.py`. These are Lane A/B scope.
2. Demo video — no YouTube link available yet (Arrya's task).
3. Pronunciation intelligibility — requires human ears and live Rime audio. Lane B scope.
4. Barge-in timing measurements — requires a live session with a microphone. Lane A/B scope.
5. `git log` credential check — downloaded as ZIP, not a git clone, so no git history available. Should be verified from a proper clone.
6. CI green status — requires checking GitHub Actions in a browser. Badge URL in README is correctly set (not REPLACE-ME).
7. Repo public check — requires opening the URL in an incognito browser window.
---

# Resolution of the items left open above

Added 2026-09-08, after this verification was written. Rahul's report is kept
exactly as he filed it; this section records what happened to each open item so
the two can be read together.

## The three README defects are fixed

| Issue | Fix |
|---|---|
| 1 — `cd waypoint` does not exist | The clone block now names the real directory, `data-forge-rime-hadippa`, in both `README.md` and `RIME_EVIDENCE.md` §5. |
| 2 — ambiguous virtualenv activation | Split into three labelled lines: macOS/Linux, Windows PowerShell, Windows Git Bash. |
| 3 — mutation target counts | `13 targets` → `19`, `28 targets` → `34`, matching what the harnesses declare. |

**And they are now checked automatically.** Finding these by reading was the
right call, but it should not have taken a person. `scripts/check_docs.py` runs
in CI, in `preflight.py` and standalone, and fails the build on any of them
recurring — plus broken local links, unfilled `FILL:`/`REPLACE-ME`, and test
counts that drift. It is tested by `tests/test_check_docs.py` (36 tests), each
one written against a defect that actually shipped here.

## The items marked TODO or unverifiable

- **Repo is public** — confirmed. An unauthenticated GitHub API request for
  `darshanrajagoli/data-forge-rime-hadippa` returns `"private": false,
  "visibility": "public"`, which is the same check an incognito window makes.
- **`git log -p` credential check** — done, from a real clone rather than a ZIP.
  The only credential-shaped strings in the entire history are two occurrences
  of the literal `rk_dummy_key_for_audit` inside an audit document.
  `.env.local` has never appeared in any commit on any branch.
- **Demo video link works logged out** — confirmed. `https://youtu.be/EChOFjIuyNM`
  returns HTTP 303 to the watch URL, and YouTube's oEmbed endpoint returns
  `"waypoint demo final"` by Arrya Sridhar without authentication.
- **CI green on the latest commit** — it was **not**. The `docs links resolve`
  job failed on `dd357dd` and again on `e847e3d`, because `team/LISTENING_NOTES.md`
  was written from a template one directory deeper and kept its `../../` link
  prefixes. The README badge was advertising a red build. Fixed, and this is
  the first defect `check_docs.py` was written to catch.

## Things this verification could not reach, which are now measured

Lane A/B work landed after this report was filed. Rime time-to-first-audio, the
WebSocket-vs-HTTP comparison and the heard-not-said estimator error are in
[`team/MEASUREMENTS.md`](team/MEASUREMENTS.md); the listening verdicts are in
[`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md). Both carry the same
caveat, stated at the top of each: the generated report files were never
uploaded from the machine that produced them, so the numbers are hand
transcribed and `evidence/results/` still holds the earlier keyless run that
failed with two `401`s.

Barge-in timing at the ear remains unmeasured. It needs a live session with a
microphone.
