# Data

**Everything in this repository is synthetic. No real person, address, phone
number, delivery or account exists here, and none is fetched at runtime.**

## The manifest

`src/waypoint/data/manifest.json` — eight delivery stops for one fictional
driver on one fictional shift.

| Field | Source | Real? |
|---|---|---|
| `street` | Real San Francisco street names | **yes, deliberately** |
| `house_number` | Invented | no |
| `recipient` | `Recipient A` … `Recipient H` | no |
| `gate_code` | Invented four-digit numbers | no |
| `unit`, `access_note`, `window_*` | Invented | no |
| `lat` / `lon` | Approximate coordinates for the street, not a building | no |
| `driver_id`, `vehicle` | Invented | no |

### Why the street names are real

The pronunciation work is only worth anything against a corpus that is
genuinely hard. "Gough" and "Haight" are the standard examples of English
orthography giving a TTS engine no usable signal; "Guerrero", "Vallejo" and
"Divisadero" are Spanish-origin names that general-purpose models
mis-stress. Inventing street names would have produced a corpus that was
easy for the wrong reason, and the pronunciation evidence would have proved
nothing.

A street name is a public geographic fact. It is not personal data, and it is
not attached to any real resident: the house numbers paired with it are made
up, and several do not exist on those streets.

### Verified by tests

- `test_manifest_is_labelled_synthetic` — the file carries a `SYNTHETIC`
  header comment.
- `test_no_real_looking_personal_data` — no `@`, and every recipient matches
  `Recipient <letter>`.
- `test_manifest_covers_the_hard_street_names` — at least six stops sit on a
  street in the pronunciation lexicon, so the corpus stays hard on purpose.

## What the Rime brief asks for

> "use synthetic or de-identified data for healthcare, finance, identity,
> safety, and other sensitive workflows."

Delivery routing touches location, which is sensitive. So the data is synthetic
rather than de-identified — there was never a real record to de-identify.

## Data that leaves the machine at runtime

| Destination | What is sent | Contains synthetic data? |
|---|---|---|
| Rime | The text to speak | yes — addresses and gate codes from the manifest |
| LiveKit Inference (STT) | Microphone audio | whatever you say into it |
| LiveKit Inference (LLM) | Transcript + tool results | yes |
| LiveKit Cloud | WebRTC media and data channels | yes |

Nothing else. There is no analytics endpoint, no telemetry and no external
database. Evidence artifacts are written locally to `evidence/results/`.

**One thing to know before recording:** anything you say into the microphone
goes to the STT provider. Do not read out a real address during the demo — use
the manifest.
