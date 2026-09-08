# Submission — Waypoint

## Deliverables

| | Link |
|---|---|
| **Demo video** (4:30, unlisted) | https://youtu.be/EChOFjIuyNM |
| **Repository** | https://github.com/darshanrajagoli/data-forge-rime-hadippa |
| **CI, green on every push** | [verify workflow](https://github.com/darshanrajagoli/data-forge-rime-hadippa/actions/workflows/ci.yml) |
| **Evidence** | [`RIME_EVIDENCE.md`](RIME_EVIDENCE.md) |
| **Full project explainer** | [`HANDOFF.md`](HANDOFF.md) |
| **Independent fresh-clone verification** | [`VERIFICATION.md`](VERIFICATION.md) |
| **Adversarial audits, kept in full** | [`docs/audits/`](docs/audits/) |

## One-liner

**Waypoint is a hands-free dispatch copilot for delivery drivers that never speaks a stale answer.**

## The user and the problem

A delivery driver mid-route. Both hands on the wheel, eyes on the road, and in most jurisdictions legally barred from touching a screen. Remove speech and there is no product left.

But a driver interrupts constantly — that is what talking while operating a vehicle looks like. And a voice agent that can be interrupted can finish a sentence that is no longer true: reading out a gate code for a stop the driver abandoned two seconds ago, or closing a delivery they just cancelled.

## The hard voice problem we chose

**Barge-in and recovery during in-flight tool work**, taken to the level that actually matters:

1. A superseded tool result is never spoken — *and never becomes a value the model can state on a later turn*.
2. An irreversible write never commits after the turn that requested it was interrupted. Checked at the **effect boundary**, because cancellation cannot help: by the time `CancelledError` arrives the POST returned 200.
3. The transcript records the words that actually left the speaker, using Rime's word-level timestamps — so the agent never believes it gave the driver a gate code it was cut off mid-way through.

Mechanism: a **turn fence** — a monotonic generation counter with one admission gate, plus turn-origin retirement. `src/waypoint/fencing.py`.

## Why Rime is central

- Rime is the **only** speech provider. No fallback TTS. If Rime is unreachable the session errors visibly rather than quietly substituting another voice.
- Rime's **WebSocket word timestamps** are what make claim 3 exact rather than estimated. Turning that transport off degrades the feature and the startup banner says so.
- Rime's model capabilities shaped a real product decision: `coda` ignores `phonemize_between_brackets` and `pause_between_brackets`, which are mistv2-only. Since street-name pronunciation is a correctness requirement for a driver ("Gow Street" is not on their route), we built a model-portable respelling layer and made asking for phonemes on `coda` **fail at startup** instead of silently no-opping.

## Evidence, in one command

```bash
pytest                                # 686 tests, ~25s, no credentials
python evidence/run_acceptance.py     # 6/6 scenarios, 36 checks, no credentials
python evidence/mutation_test.py      # 15/15 deliberate bugs caught
python evidence/mutation_test_ii.py   # 19/19 more: wiring, gates, evidence
python scripts/secret_scan.py         # clean
python scripts/check_docs.py          # the docs still match the repository
```

None of these need a key of ours. That is the point: the central claim is checkable without trusting us.

<!-- check-docs: allow -- the recorded narration really does say 573 -->
**One discrepancy, flagged rather than hidden.** The demo video was recorded on 2026-09-08, when the suite was 573 tests, and the narration says so out loud.
The repository reports 686 passing here, and the 113 in `tests/test_check_docs.py` were added after the fresh-clone verification found documentation defects that nothing was checking for; they guard against exactly that recurring. The video was not re-cut. Both numbers are real, and the "112 on the fence" figure the narration also quotes is unchanged.

## What we measured with Rime, and what we did not

Run on 2026-09-07 against a live Rime key, on Windows over a mobile hotspot. Full method and caveats in [`team/MEASUREMENTS.md`](team/MEASUREMENTS.md) and [`team/LISTENING_NOTES.md`](team/LISTENING_NOTES.md).

| | result |
|---|---|
| Rime time-to-first-audio, WebSocket, **warm**, n=20 | p50 **394.35 ms**, p95 429.93 ms |
| Rime time-to-first-audio, WebSocket, **cold**, n=1 | 1346.12 ms |
| WebSocket vs HTTP, warm | 14.5 ms faster at p50, and a 52 ms spread against 175 ms |
| Heard-not-said estimator error, 48 comparisons | mean 2.96 words; over-claimed in **1 of 48** |

Boundary is `server_first_frame` — the Rime request, queueing and synthesis. **It is not the driver's ear**: it excludes the LiveKit hop, the jitter buffer and the speaker. Cold and warm are reported separately and never averaged.

**Two honest weaknesses, stated rather than buried.**

1. The generated report files were never uploaded from the machine that ran them, so `evidence/results/` still holds an earlier keyless run that failed with two `401`s. The numbers above are hand-transcribed from tool output. That is weaker than a committed artifact and we have not manufactured one to cover it.
2. The pronunciation result is **mixed**, and both halves are reported. On `mistv2`, `gate code 4417` without respelling came out as *"four thousand four hundred and seventeen"* — unusable at a keypad — and respelling fixes it. But on `coda`, all five street fixtures were already correct without respelling and two got *worse* with it. One listener, one device, who knew what the clips were supposed to say.

Not measured at all: barge-in to silence at the driver's ear. That needs a live session with a microphone.

## Links

| | |
|---|---|
| Repository | https://github.com/darshanrajagoli/data-forge-rime-hadippa |
| Demo video | https://youtu.be/EChOFjIuyNM (4:30, under the 5:00 cap) |
| CI, green on every push | [verify workflow](https://github.com/darshanrajagoli/data-forge-rime-hadippa/actions/workflows/ci.yml) |
| Project explainer, one file | [`HANDOFF.md`](HANDOFF.md) |
| Evidence | [`RIME_EVIDENCE.md`](RIME_EVIDENCE.md) |
| Independent verification | [`VERIFICATION.md`](VERIFICATION.md) |
| Acceptance run | [`evidence/reference-run/acceptance.md`](evidence/reference-run/acceptance.md) |
| Architecture | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Threat model | [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) |
| Data provenance | [`docs/DATA.md`](docs/DATA.md) |
| Adversarial audits, kept in full | [`docs/audits/`](docs/audits/) |

## Team

| | Role |
|---|---|
| **Darshan Rajagoli** | Product, the turn fence, the test and evidence apparatus |
| **Arrya Sridhar** | Live run and the demo video |
| **Akshat Marathe** | Rime latency and transport measurements; the listening test |
| **Rahul Sudarshan** | Independent fresh-clone verification, acting as a judge; submission |

No mentor involvement.

## AI assistance

Built with AI assistance (Claude) for code, tests and documentation, and used
throughout rather than for a single pass.

What did **not** come from a model's recall: the turn-fence design, the
Coda/Mist trade-off, and the measurement-boundary discipline came from reading
primary sources — the LiveKit Agents 1.7.1 source for interruption handling, and
Rime's own documentation for model capabilities. The `agent_activity.py`
behaviour quoted in `RIME_EVIDENCE.md` §6 was read out of the installed package,
not remembered.

Five adversarial passes were run with AI as the red team, each one told to
attack the previous result; the three that were written up as reports are kept
in full in `docs/audits/` alongside the fixes, including the findings that were
embarrassing. All measurements
and every listening verdict were produced by a person running the committed
scripts.

---

## How this maps to the judging criteria

| Criterion | Where to look |
|---|---|
| **Problem and necessity of voice — 25%** | A driver legally cannot use a screen. `README.md` opening; Shot 1 of the demo. |
| **Hard voice engineering — 25%** | `src/waypoint/fencing.py`, and the `_read`/`_write` integration in `agent.py`. `RIME_EVIDENCE.md` §6 states exactly what LiveKit already does, so the contribution is not overclaimed. |
| **Rime integration and voice experience — 20%** | `build_tts()`; the WebSocket word-timestamp dependency; `pronounce.py` and the Coda/Mist trade-off; exact config table in `README.md`; measured transport comparison in `RIME_EVIDENCE.md` §4. |
| **Evidence and reproducibility — 20%** | `evidence/run_acceptance.py` (no credentials), 686 tests, and **two** mutation harnesses proving the tests would fail if the code broke — 34 targets, 34 caught, 0 survived. Pinned versions, seeded fuzz, measurement boundaries labelled and never averaged, archived adversarial audits with every finding mapped to its fix, and an independent fresh-clone verification in `VERIFICATION.md` whose findings are fixed and now guarded by `scripts/check_docs.py`. GitHub Actions re-runs it all on every push across Linux and Windows × Python 3.10/3.12, with **no secrets block**. |
| **Demo clarity — 10%** | `DEMO_SCRIPT.md`; the browser fence board makes the withholding visible, which listening alone cannot. |

## Eligibility self-check

Every disqualifier in the brief, and where it is ruled out.

- [x] **Verifiable Rime integration in the submitted code** — `build_tts()` in `src/waypoint/agent.py`; `livekit-plugins-rime==1.7.1` pinned in `pyproject.toml`.
- [x] **Rime is not incidental** — it is the only speech provider, and its word timestamps are a functional dependency of a core feature, not decoration.
- [x] **A working product path, not static screens** — `python -m waypoint.agent console` runs the whole loop with no browser.
- [x] **Demo included** — https://youtu.be/EChOFjIuyNM, 4:30, under the 5:00 cap.
- [x] **No live credential exposed** — `.env.example` holds placeholders only; `scripts/secret_scan.py` (158 of the 686 tests) runs standalone, in preflight and in a pre-commit hook; the browser never receives a key.
- [x] **No unverified performance number claimed as verified** — every figure in this document carries its boundary, its sample size, its cold/warm label, and the fact that it was hand-transcribed rather than committed as an artifact.
- [x] **Model / voice / language passes the event preflight** — `coda`/`lyra`/`eng` and `mistv2`/`cove`/`eng` both synthesised successfully against live Rime on 2026-09-07 during the latency and pronunciation runs. `python scripts/preflight.py --offline` passes with the single expected warning; the credentialed run of `preflight.py` itself was not separately recorded.

## Pre-submit checklist

- [x] `pytest` → 686 passed
- [x] `python evidence/run_acceptance.py` → 6/6 scenarios, 36 checks
- [x] `python scripts/secret_scan.py` → clean
- [x] `python scripts/check_docs.py` → clean
- [x] `python scripts/preflight.py --offline` → passes, 1 expected warning
- [x] Demo is under 5:00 and the link resolves — the link was checked programmatically (HTTP 303, oEmbed returns "waypoint demo final"); the content was confirmed by Arrya, who recorded it to `DEMO_SCRIPT.md`
- [x] No unfilled placeholder left anywhere in this file — enforced by `scripts/check_docs.py`
- [x] Every number here is one somebody actually measured
- [x] `.env.local` is not in the repository — only `.env.example` is
- [x] `python evidence/mutation_test.py` → **15/15 caught** (454s), and `mutation_test_ii.py` → **19/19 caught** (335s). 34 of 34, none surviving
- [x] GitHub Actions `verify` is green — it was **red** on `dd357dd` and `e847e3d` from two broken links in `team/LISTENING_NOTES.md`; fixed, and `scripts/check_docs.py` now fails the build if it recurs
- [x] Repo is public — an unauthenticated GitHub API request returns `"private": false`
- [x] Full git history holds no credential, and `.env.local` has never been committed on any branch
