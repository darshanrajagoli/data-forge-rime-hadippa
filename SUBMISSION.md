# Submission — Waypoint

> **Owner: Akshay.** Fill the four `FILL:` blanks and tick the checklist. Do not
> edit any other file in the repo — see `WORKFLOW.md`.

---

## One-liner

**Waypoint is a hands-free dispatch copilot for delivery drivers that never
speaks a stale answer.**

## The user and the problem

A delivery driver mid-route. Both hands on the wheel, eyes on the road, and in
most jurisdictions legally barred from touching a screen. Remove speech and
there is no product left.

But a driver interrupts constantly — that is what talking while operating a
vehicle looks like. And a voice agent that can be interrupted can finish a
sentence that is no longer true: reading out a gate code for a stop the driver
abandoned two seconds ago, or closing a delivery they just cancelled.

## The hard voice problem we chose

**Barge-in and recovery during in-flight tool work**, taken to the level that
actually matters:

1. A superseded tool result is never spoken — *and never becomes a value the
   model can state on a later turn*.
2. An irreversible write never commits after the turn that requested it was
   interrupted. Checked at the **effect boundary**, because cancellation cannot
   help: by the time `CancelledError` arrives the POST returned 200.
3. The transcript records the words that actually left the speaker, using
   Rime's word-level timestamps — so the agent never believes it gave the
   driver a gate code it was cut off mid-way through.

Mechanism: a **turn fence** — a monotonic generation counter with one admission
gate, plus turn-origin retirement. `src/waypoint/fencing.py`.

## Why Rime is central

- Rime is the **only** speech provider. No fallback TTS. If Rime is
  unreachable the session errors visibly rather than quietly substituting
  another voice.
- Rime's **WebSocket word timestamps** are what make claim 3 exact rather than
  estimated. Turning that transport off degrades the feature and the startup
  banner says so.
- Rime's model capabilities shaped a real product decision: `coda` ignores
  `phonemize_between_brackets` and `pause_between_brackets`, which are
  mistv2-only. Since street-name pronunciation is a correctness requirement for
  a driver ("Gow Street" is not on their route), we built a model-portable
  respelling layer and made asking for phonemes on `coda` **fail at startup**
  instead of silently no-opping.

## Evidence, in one command

```bash
pytest                                # 350 tests, ~6s, no credentials
python evidence/run_acceptance.py     # 6/6 scenarios, 36 checks, no credentials
python evidence/mutation_test.py      # 15/15 deliberate bugs caught by the suite
```

The acceptance test was written before the demo. It drives the real agent code
against the real fence and injects the barge-ins itself, so a judge can verify
the central claim on their own machine without our keys.

The third command is the one we would point a sceptical judge at first. It
breaks the code fifteen different ways and checks that a test notices each time
— because "350 tests pass" says nothing until you know the tests would fail.

**Five** real bugs were found and fixed this way. Three came from adversarial
review passes run *after* the project was declared finished — one of them a
headline claim that had never been wired into the agent at all while its module
tests stayed green, and one a family of measurement scripts that could not make
a single Rime API call in any configuration. All five are written up in
`RIME_EVIDENCE.md` §3, including what the tests missed and why.

Full claim, procedure, results and limitations: **`RIME_EVIDENCE.md`**.

## Links

| | |
|---|---|
| Repository | FILL: github URL |
| Demo video | FILL: video URL (4:30, under the 5:00 cap) |
| Evidence | [`RIME_EVIDENCE.md`](RIME_EVIDENCE.md) |
| Threat model | [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) |

## Team

FILL: names, and who did what. Disclose any mentor involvement.

## AI assistance

Built with AI assistance (Claude) for code, tests and documentation. The
turn-fence design, the Coda/Mist trade-off and the measurement-boundary
discipline came from reading primary sources — the LiveKit Agents 1.7.1 source
for interruption handling, Rime's docs for model capabilities. The
`agent_activity.py` behaviour quoted in `RIME_EVIDENCE.md` §6 was read from the
installed package, not recalled. FILL: add anything else the team used.

---

## How this maps to the judging criteria

| Criterion | Where to look |
|---|---|
| **Problem and necessity of voice — 25%** | A driver legally cannot use a screen. `README.md` opening; Shot 1 of the demo. |
| **Hard voice engineering — 25%** | `src/waypoint/fencing.py`, and the `_read`/`_write` integration in `agent.py`. `RIME_EVIDENCE.md` §6 states exactly what LiveKit already does, so the contribution is not overclaimed. |
| **Rime integration and voice experience — 20%** | `build_tts()`; the WebSocket word-timestamp dependency; `pronounce.py` and the Coda/Mist trade-off; exact config table in `README.md`. |
| **Evidence and reproducibility — 20%** | `evidence/run_acceptance.py` (no credentials), 350 tests, and `evidence/mutation_test.py` which proves the tests would fail if the code broke (15/15). Pinned versions, seeded fuzz, measurement boundaries labelled and never averaged. GitHub Actions re-runs it all on every push across Linux and Windows × Python 3.10/3.12, with **no secrets block** — the central claim is checkable without our keys. |
| **Demo clarity — 10%** | `DEMO_SCRIPT.md`; the browser fence board makes the withholding visible, which listening alone cannot. |

## Eligibility self-check

Every disqualifier in the brief, and where it is ruled out.

- [x] **Verifiable Rime integration in the submitted code** — `build_tts()` in `src/waypoint/agent.py`; `livekit-plugins-rime==1.7.1` pinned in `pyproject.toml`.
- [x] **Rime is not incidental** — it is the only speech provider, and its word timestamps are a functional dependency of a core feature, not decoration.
- [x] **A working product path, not static screens** — `python -m waypoint.agent console` runs the whole loop with no browser.
- [ ] **Demo included** — FILL after upload.
- [x] **No live credential exposed** — `.env.example` holds placeholders only; `scripts/secret_scan.py` (40 tests) runs standalone, in preflight and in a pre-commit hook; the browser never receives a key.
- [ ] **Model / voice / language passes the event preflight** — `python scripts/preflight.py` must exit 0 on the machine that records the demo. FILL: date run and result.

## Pre-submit checklist

- [ ] GitHub Actions `verify` is green on the submitted commit
- [ ] `python scripts/preflight.py` exits 0 on the recording machine
- [ ] `pytest` → 350 passed
- [ ] `python evidence/run_acceptance.py` → 6/6
- [ ] `python evidence/mutation_test.py` → 15/15 caught
- [ ] `python scripts/secret_scan.py` → clean
- [ ] `git log -p | grep -i "api.key\|secret"` shows nothing real
- [ ] Demo is under 5:00 and shows all seven required elements (`DEMO_SCRIPT.md`)
- [ ] Repo is public and clones clean on a machine that never had the project
- [ ] `evidence/results/` contains the committed artifacts
- [ ] Every `FILL:` above is replaced
