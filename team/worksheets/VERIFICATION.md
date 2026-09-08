# Independent verification

> **Worksheet — not a document for judges.** Fill every `TODO` after doing your lane in `team/WORKFLOW.md`.
> Delete this blockquote when you are done.
>
> You are standing in for a judge. Behave like someone who has never seen this
> project: follow the README exactly as written, and write down every place it
> was wrong, unclear, or assumed something it did not say.

**Verified by:** TODO (name) · **Date:** TODO
**Machine:** TODO (OS, laptop) — a fresh clone, no prior setup
**API keys used:** none

---

## Results

| Step | Command | Result | Time taken |
|---|---|---|---|
| Clone | `git clone <repo>` | TODO | TODO |
| Install | `pip install -e ".[dev]"` | TODO | TODO |
| Test suite | `pytest` | TODO (expect: 620 passed) | TODO |
| Acceptance | `python evidence/run_acceptance.py` | TODO (expect: 6/6, 36 checks) | TODO |
| Mutation test (core) | `python evidence/mutation_test.py` | TODO (expect: 15/15) | TODO |
| Mutation test (wiring) | `python evidence/mutation_test_ii.py` | TODO (expect: 19/19) | TODO |
| Secret scan | `python scripts/secret_scan.py` | TODO (expect: clean) | TODO |
| Offline preflight | `python scripts/preflight.py --offline` | TODO | TODO |

## Did the README work as written?

TODO — yes or no, and be specific. Every command that did not work, every step
that assumed something not stated, every place you had to guess.

**This is the single most useful thing in this file.** A judge will hit exactly
the same things you did.

## Steps the README does not mention but that were needed

TODO — list them. If the answer is genuinely none, write "none" explicitly
rather than leaving it blank; a blank reads as unchecked.

## Repository check

- [ ] Repo is **public** — checked in a private/incognito window while logged out
- [ ] `.env.local` is **not** in the repo (`git ls-files | grep env` shows only `.env.example`)
- [ ] `git log -p | grep -i "api.key\|secret"` shows no real credential
- [ ] `evidence/results/` contains the committed artifacts
- [ ] Demo video link works from a logged-out browser
- [ ] GitHub Actions `verify` workflow is **green** on the latest commit, and the badge URL in `README.md` no longer says `REPLACE-ME`

## Anything I could not verify

TODO — everything needing API keys, a microphone or human ears is out of scope
for this file and belongs to Lanes A, B and C. Name what you skipped, so the
gap is visible rather than assumed covered.
