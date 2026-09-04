#!/usr/bin/env python3
"""Token server and static host for the Waypoint demo console.

    python web/server.py          # http://127.0.0.1:8080

Two jobs, and one thing it deliberately does not do.

It **mints** a short-lived LiveKit access token for a browser participant, and
it **serves** ``index.html``. It does **not** ship any credential to the
browser: the API key and secret stay in this process and only the signed JWT
crosses the wire. That is the whole reason a token server exists rather than
the page connecting directly, and it is why "exposes a live credential ... in
client code" cannot happen here.

The console it serves is not decoration. The claim in ``RIME_EVIDENCE.md`` is
about behaviour a listener cannot verify by listening -- you cannot *hear* that
a stale tool result was withheld, only that the agent stayed quiet. The fence
board makes the withholding visible, and the browser measures its own audio
going silent, which is the closest thing to the driver's ear that software can
observe.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv

    for _name in (".env.local", ".env"):
        _p = ROOT / _name
        if _p.exists():
            load_dotenv(_p, override=False)
except ImportError:  # pragma: no cover
    pass

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, JSONResponse
    from livekit import api
    import uvicorn
except ImportError as exc:  # pragma: no cover
    print(
        f"missing dependency: {exc}\n"
        "install the web extras:  pip install -e \".[web]\"",
        file=sys.stderr,
    )
    raise SystemExit(2)

from waypoint.config import ConfigError, load_settings  # noqa: E402

app = FastAPI(title="Waypoint demo console")
HERE = Path(__file__).resolve().parent


@app.get("/")
def index() -> FileResponse:
    return FileResponse(HERE / "index.html")


@app.get("/api/config")
def config() -> JSONResponse:
    """The redacted, disclosed configuration the console displays.

    Every secret is redacted by ``Settings.to_dict``; this endpoint exists so
    the demo can show which speech provider is actually active, which the Rime
    brief requires to be observable.
    """
    try:
        settings = load_settings()
    except ConfigError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(settings.to_dict())


@app.get("/api/token")
def token(room: str | None = None, identity: str | None = None) -> JSONResponse:
    """Mint a short-lived join token. The API secret never leaves this process."""
    url = os.environ.get("LIVEKIT_URL")
    key = os.environ.get("LIVEKIT_API_KEY")
    secret = os.environ.get("LIVEKIT_API_SECRET")
    if not (url and key and secret):
        raise HTTPException(
            status_code=500,
            detail=(
                "LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set. "
                "Copy .env.example to .env.local and fill it in."
            ),
        )

    room_name = room or f"waypoint-{uuid.uuid4().hex[:8]}"
    who = identity or f"driver-{uuid.uuid4().hex[:6]}"

    grant = api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )
    jwt = (
        api.AccessToken(key, secret)
        .with_identity(who)
        .with_name("Driver")
        .with_grants(grant)
        .with_ttl(__import__("datetime").timedelta(minutes=60))
        .to_jwt()
    )
    return JSONResponse({"url": url, "token": jwt, "room": room_name, "identity": who})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    try:
        print(load_settings().banner())
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

    print(f"\n  Waypoint console: http://{args.host}:{args.port}\n")
    print("  Start the agent in another terminal:")
    print("      python -m waypoint.agent dev\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
