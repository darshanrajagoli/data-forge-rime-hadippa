# Pronunciation experiment

- Run at: `2026-09-04T03:04:21+0530`
- Models: coda, mistv2  (voice held constant per model: {'coda': 'lyra', 'mistv2': 'cove', 'mistv3': 'cove'})
- Strategies: none, respell, phoneme
- Audio rendered: False

**Limitation.** Intelligibility is a listening judgement. This script renders and saves the variants; docs/LISTENING_TEST.md says how to score them. Rows with an empty listening_verdict are unverified and must be reported as such.

## Text variants

| fixture | model | requested | effective | sent to Rime | clip | verdict |
|---|---|---|---|---|---|---|
| `addr-gough` | coda | none | none | 1247 Gough Street, unit 4B | - | _unverified_ |
| `addr-haight` | coda | none | none | 836 Haight Street | - | _unverified_ |
| `addr-guerrero` | coda | none | none | 2190 Guerrero Street, unit 2 | - | _unverified_ |
| `addr-divisadero` | coda | none | none | 3401 Divisadero Street, unit 11C | - | _unverified_ |
| `code-4417` | coda | none | none | gate code 4417 | - | _unverified_ |
| `code-0921` | coda | none | none | gate code 0921 | - | _unverified_ |
| `num-1207` | coda | none | none | 1207 Noe Street | - | _unverified_ |
| `mixed` | coda | none | none | Next stop 660 Vallejo Street, unit A. Gate code 1150. Then Kearny and Taraval. | - | _unverified_ |
| `addr-gough` | coda | respell | respell | twelve forty-seven Goff Street, unit four B | - | _unverified_ |
| `addr-haight` | coda | respell | respell | eight thirty-six Hate Street | - | _unverified_ |
| `addr-guerrero` | coda | respell | respell | twenty-one ninety Ger-RARE-oh Street, unit two | - | _unverified_ |
| `addr-divisadero` | coda | respell | respell | thirty-four oh one Di-viss-a-DARE-oh Street, unit eleven C | - | _unverified_ |
| `code-4417` | coda | respell | respell | gate code four four one seven | - | _unverified_ |
| `code-0921` | coda | respell | respell | gate code zero nine two one | - | _unverified_ |
| `num-1207` | coda | respell | respell | twelve oh seven NO-ee Street | - | _unverified_ |
| `mixed` | coda | respell | respell | Next stop 660 Va-LAY-ho Street, unit A. Gate code 1150. Then KAR-nee and TARA-val. | - | _unverified_ |
| `addr-gough` | coda | phoneme | respell *(downgraded)* | twelve forty-seven Goff Street, unit four B | - | _unverified_ |
| `addr-haight` | coda | phoneme | respell *(downgraded)* | eight thirty-six Hate Street | - | _unverified_ |
| `addr-guerrero` | coda | phoneme | respell *(downgraded)* | twenty-one ninety Ger-RARE-oh Street, unit two | - | _unverified_ |
| `addr-divisadero` | coda | phoneme | respell *(downgraded)* | thirty-four oh one Di-viss-a-DARE-oh Street, unit eleven C | - | _unverified_ |
| `code-4417` | coda | phoneme | respell *(downgraded)* | gate code four four one seven | - | _unverified_ |
| `code-0921` | coda | phoneme | respell *(downgraded)* | gate code zero nine two one | - | _unverified_ |
| `num-1207` | coda | phoneme | respell *(downgraded)* | twelve oh seven NO-ee Street | - | _unverified_ |
| `mixed` | coda | phoneme | respell *(downgraded)* | Next stop 660 Va-LAY-ho Street, unit A. Gate code 1150. Then KAR-nee and TARA-val. | - | _unverified_ |
| `addr-gough` | mistv2 | none | none | 1247 Gough Street, unit 4B | - | _unverified_ |
| `addr-haight` | mistv2 | none | none | 836 Haight Street | - | _unverified_ |
| `addr-guerrero` | mistv2 | none | none | 2190 Guerrero Street, unit 2 | - | _unverified_ |
| `addr-divisadero` | mistv2 | none | none | 3401 Divisadero Street, unit 11C | - | _unverified_ |
| `code-4417` | mistv2 | none | none | gate code 4417 | - | _unverified_ |
| `code-0921` | mistv2 | none | none | gate code 0921 | - | _unverified_ |
| `num-1207` | mistv2 | none | none | 1207 Noe Street | - | _unverified_ |
| `mixed` | mistv2 | none | none | Next stop 660 Vallejo Street, unit A. Gate code 1150. Then Kearny and Taraval. | - | _unverified_ |
| `addr-gough` | mistv2 | respell | respell | twelve forty-seven Goff Street, unit four B | - | _unverified_ |
| `addr-haight` | mistv2 | respell | respell | eight thirty-six Hate Street | - | _unverified_ |
| `addr-guerrero` | mistv2 | respell | respell | twenty-one ninety Ger-RARE-oh Street, unit two | - | _unverified_ |
| `addr-divisadero` | mistv2 | respell | respell | thirty-four oh one Di-viss-a-DARE-oh Street, unit eleven C | - | _unverified_ |
| `code-4417` | mistv2 | respell | respell | gate code four four one seven | - | _unverified_ |
| `code-0921` | mistv2 | respell | respell | gate code zero nine two one | - | _unverified_ |
| `num-1207` | mistv2 | respell | respell | twelve oh seven NO-ee Street | - | _unverified_ |
| `mixed` | mistv2 | respell | respell | Next stop 660 Va-LAY-ho Street, unit A. Gate code 1150. Then KAR-nee and TARA-val. | - | _unverified_ |
| `addr-gough` | mistv2 | phoneme | phoneme | twelve forty-seven Goff Street, unit four B | - | _unverified_ |
| `addr-haight` | mistv2 | phoneme | phoneme | eight thirty-six Hate Street | - | _unverified_ |
| `addr-guerrero` | mistv2 | phoneme | phoneme | twenty-one ninety Ger-RARE-oh Street, unit two | - | _unverified_ |
| `addr-divisadero` | mistv2 | phoneme | phoneme | thirty-four oh one Di-viss-a-DARE-oh Street, unit eleven C | - | _unverified_ |
| `code-4417` | mistv2 | phoneme | phoneme | gate code four four one seven | - | _unverified_ |
| `code-0921` | mistv2 | phoneme | phoneme | gate code zero nine two one | - | _unverified_ |
| `num-1207` | mistv2 | phoneme | phoneme | twelve oh seven NO-ee Street | - | _unverified_ |
| `mixed` | mistv2 | phoneme | phoneme | Next stop 660 Va-LAY-ho Street, unit A. Gate code 1150. Then KAR-nee and TARA-val. | - | _unverified_ |

## Why each fixture is in the corpus

- **`addr-gough`** (address) - Gough is the standard example of English orthography giving TTS nothing usable. 'Gow' or 'Go' sends the driver to a street that is not on their route.
- **`addr-haight`** (address) - One syllable, rhymes with gate. Commonly read as two.
- **`addr-guerrero`** (address) - Spanish origin; stress on the second syllable.
- **`addr-divisadero`** (address) - Four syllables before the stress. Easy to garble at speed.
- **`code-4417`** (gate code) - Read as a quantity ('four thousand four hundred seventeen') it cannot be keyed into a pad.
- **`code-0921`** (gate code) - Leading zero. Must survive as a digit, not be dropped.
- **`num-1207`** (house number) - 'Twelve oh seven', not 'one thousand two hundred seven'.
- **`mixed`** (full utterance) - Everything at once, which is what an actual turn sounds like.

## Note on `coda`

Rime documents `coda` as ignoring `phonemize_between_brackets`, `pause_between_brackets` and `reduce_latency`. Rows above where `requested = phoneme` and `model = coda` are marked *(downgraded)*: the run used respelling instead. That is why respelling is the shipped default -- it is the only strategy that survives a model change without silently becoming a no-op.
