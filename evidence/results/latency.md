# Rime time-to-first-audio

- Run at: `2026-09-04T05:08:02+0530`
- Model / voice: `coda` / `lyra`, lang `eng`
- Sample rate: 22050 Hz
- Command: `python evidence/measure_latency.py --warm 1`

## Where the stopwatch stops

| boundary | what it includes | what it omits |
|---|---|---|
| `server_first_frame` (this file) | Rime request, queueing, synthesis; plus TLS and WebSocket upgrade on the cold run | the LiveKit hop, the client jitter buffer, the speaker |
| `client_first_audio` (browser console) | all of the above, end to end | nothing this side of the driver's ear |

**This file's numbers are not the driver's experience.** They are the provider-side component of it. The end-to-end figure is measured in the browser, where the audio actually plays.

## Results

| series | warmth | n | p50 | p95 | min | max |
|---|---|---|---|---|---|---|

Percentiles are nearest-rank (`ceil(p/100 * n)`), not interpolated.

## Errors

- `cold/websocket: APIStatusError: message='Invalid response status', status_code=401, retryable=False`
- `warm[0]/websocket: APIStatusError: message='Invalid response status', status_code=401, retryable=False`
