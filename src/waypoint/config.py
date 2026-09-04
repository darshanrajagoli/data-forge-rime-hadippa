"""Configuration, validated at startup and printed in full.

Two rules drive this module.

**Nothing degrades silently.** Every setting that could quietly stop working --
a pronunciation strategy the model ignores, a speaker that is not in the live
catalog, a WebSocket path that fell back to HTTP -- is either rejected at
startup or reported in the banner. The Rime brief is explicit that fallback
behaviour is allowed but must be disclosed and observable, so
:meth:`Settings.banner` is the disclosure and it is printed on every run and
published to the demo UI.

**Secrets never leave the process.** :meth:`Settings.banner` and
:meth:`Settings.to_dict` redact every key. ``scripts/secret_scan.py`` enforces
that no key reaches the repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

from .pronounce import Strategy, resolve_strategy, PronunciationError

__all__ = ["Settings", "ConfigError", "load_settings", "REQUIRED_KEYS"]

#: Environment variables that must be present for the agent to run for real.
#: The offline test suite needs none of them.
REQUIRED_KEYS = (
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "RIME_API_KEY",
)

#: Rime's two endpoints. These are *different hosts*, not two paths on one
#: host, and which one is used is decided entirely by the transport.
#:
#: Mirrored from ``livekit.plugins.rime.tts`` (``RIME_WS_BASE_URL`` +
#: ``"/ws3"``, and ``RIME_BASE_URL``). They are duplicated here rather than
#: imported so that this module stays free of the LiveKit dependency -- and
#: ``test_config.py::test_endpoint_constants_match_the_plugin`` asserts they
#: are still equal, so if Rime moves a host the suite fails instead of the
#: disclosure quietly going stale.
#:
#: This matters more than it looks. The brief names ``endpoint`` as one of six
#: fields the README must state exactly, the startup banner is printed to a
#: terminal that gets screen-recorded, and the browser console renders it two
#: lines under the speech-provider badge. Disclosing the HTTP host while
#: streaming over the WebSocket one is a wrong answer on camera.
RIME_WS_ENDPOINT = "wss://users-ws.rime.ai/ws3"
RIME_HTTP_ENDPOINT = "https://users.rime.ai/v1/rime-tts"


class ConfigError(RuntimeError):
    """Configuration that cannot produce a working, honest demo."""


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


def _env_bool(name: str, default: bool) -> bool:
    v = _env(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    v = _env(name)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        raise ConfigError(f"{name}={v!r} is not a number") from None


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        raise ConfigError(f"{name}={v!r} is not an integer") from None


def _redact(value: str | None) -> str:
    if not value:
        return "(unset)"
    if len(value) <= 8:
        return "set (" + "*" * len(value) + ")"
    return f"set ({value[:3]}...{value[-2:]}, len={len(value)})"


def _redact_url(value: str | None) -> str:
    """Show the LiveKit URL, but never any credentials embedded in it.

    ``LIVEKIT_URL`` is not itself a secret -- it is a public endpoint that
    every browser client already knows, and seeing which project you are
    pointed at is the single most useful line in the banner when a demo will
    not connect. So it is shown.

    But a URL *can* carry credentials in its userinfo component
    (``wss://key:secret@host``), and this banner is printed to a terminal that
    will be screen-recorded for the demo video. So if there is a ``@`` before
    the host, everything before it is stripped.
    """
    if not value:
        return "(unset)"
    if "@" not in value:
        return value
    scheme, _, rest = value.partition("://")
    if not rest:
        return "(redacted: credentials embedded in URL)"
    _userinfo, _, host = rest.rpartition("@")
    return f"{scheme}://<redacted>@{host}"


@dataclass(frozen=True)
class Settings:
    """The exact configuration the demo runs on."""

    # -- Rime (the primary spoken output) --------------------------------
    rime_model: Literal["coda", "mistv2", "mistv3"] = "coda"
    rime_speaker: str = "lyra"
    rime_lang: str = "eng"
    rime_sample_rate: int = 22050
    rime_speed_alpha: float = 1.0
    rime_use_websocket: bool = True
    rime_segment: str = "bySentence"
    rime_base_url: str | None = None

    # -- pronunciation ---------------------------------------------------
    pronunciation: Strategy = Strategy.RESPELL
    pause_ms: int = 0

    # -- other providers (Rime owns speech; we own the rest) -------------
    stt_model: str = "deepgram/nova-3"
    stt_language: str = "multi"
    llm_model: str = "openai/gpt-4.1-mini"

    # -- turn handling ---------------------------------------------------
    interruption_mode: Literal["adaptive", "vad"] = "adaptive"
    min_interruption_duration: float = 0.4
    min_interruption_words: int = 0
    resume_false_interruption: bool = True
    false_interruption_timeout: float = 1.0
    preemptive_generation: bool = True

    # -- demo behaviour --------------------------------------------------
    dispatch_latency_ms: float = 1800.0
    dispatch_jitter_ms: float = 200.0
    publish_fence_events: bool = True

    # -- credentials (redacted everywhere) -------------------------------
    livekit_url: str | None = None
    livekit_api_key: str | None = field(default=None, repr=False)
    livekit_api_secret: str | None = field(default=None, repr=False)
    rime_api_key: str | None = field(default=None, repr=False)

    # -- derived ----------------------------------------------------------
    warnings: tuple[str, ...] = ()

    # ------------------------------------------------------------------

    @property
    def supports_brackets(self) -> bool:
        """Whether the configured model honours ``{...}`` and ``<...>``."""
        from .pronounce import MODEL_SUPPORTS_BRACKETS

        if self.rime_model == "mistv3" and self.rime_lang not in ("eng", "en", "en-US"):
            return False
        return MODEL_SUPPORTS_BRACKETS.get(self.rime_model, False)

    @property
    def effective_pause_ms(self) -> int:
        """Pause brackets are silently ignored off mistv2, so we zero them."""
        return self.pause_ms if self.supports_brackets else 0

    @property
    def effective_use_websocket(self) -> bool:
        """The transport the plugin will *actually* use.

        ``rime_use_websocket`` is a request, not an outcome. The plugin
        upgrades it from the URL scheme
        (``livekit.plugins.rime.tts.TTS.__init__``, v1.7.1)::

            if is_given(base_url):
                use_websocket = use_websocket or base_url.startswith(("ws://", "wss://"))

        so ``RIME_USE_WEBSOCKET=false`` with ``RIME_BASE_URL=wss://...`` --
        both documented variables -- streams over a WebSocket while every
        field derived from the raw flag says HTTP.

        That was not only a disclosure bug. ``build_session`` passes
        ``use_tts_aligned_transcript=`` this value, so Waypoint would have
        *declined* word timestamps that were already on the wire and dropped
        the heard-not-said boundary from exact to estimated -- silently, and
        while the banner explained the degradation as if it were the operator's
        choice. Every transport-derived field now keys off this one property.

        ``test_config.py`` asserts this agrees with the installed plugin for
        the whole cross-product of flag and override, so if Rime changes the
        rule the suite fails instead of the banner going quietly wrong.
        """
        if self.rime_base_url:
            return self.rime_use_websocket or self.rime_base_url.startswith(
                ("ws://", "wss://")
            )
        return self.rime_use_websocket

    @property
    def transport(self) -> str:
        return "WebSocket (wss)" if self.effective_use_websocket else "HTTP"

    @property
    def endpoint(self) -> str:
        """The URL audio will actually be fetched from.

        Derived from the effective transport, not from whether an override
        happens to be set. An earlier version disclosed "default
        (users.rime.ai)" whenever ``RIME_BASE_URL`` was unset -- the HTTP host,
        and therefore wrong on the shipped WebSocket path on every single run.

        The ``/ws3`` suffix is the plugin's, not ours: on the WebSocket path it
        builds ``f"{base_url}/ws3?{params}"``. Appending it here means an
        override discloses the same URL the socket is opened against, rather
        than the bare host the operator typed.
        """
        if self.rime_base_url:
            base = self.rime_base_url.rstrip("/")
            if self.effective_use_websocket and not base.endswith("/ws3"):
                return base + "/ws3"
            return base
        return RIME_WS_ENDPOINT if self.effective_use_websocket else RIME_HTTP_ENDPOINT

    @property
    def heard_method(self) -> str:
        """Which heard-not-said method this configuration can actually achieve."""
        return (
            "word_timestamps (exact)"
            if self.effective_use_websocket
            else "duration_estimate (approximate)"
        )

    def missing_keys(self) -> list[str]:
        present = {
            "LIVEKIT_URL": self.livekit_url,
            "LIVEKIT_API_KEY": self.livekit_api_key,
            "LIVEKIT_API_SECRET": self.livekit_api_secret,
            "RIME_API_KEY": self.rime_api_key,
        }
        return [k for k in REQUIRED_KEYS if not present.get(k)]

    def require_runtime_keys(self) -> None:
        missing = self.missing_keys()
        if missing:
            raise ConfigError(
                "missing required environment variables: "
                + ", ".join(missing)
                + ". Copy .env.example to .env.local and fill it in, then run "
                "`python scripts/preflight.py`."
            )

    def to_dict(self) -> dict[str, Any]:
        """Full config with every secret redacted. Safe to log and publish."""
        return {
            "rime": {
                "model": self.rime_model,
                "speaker": self.rime_speaker,
                "lang": self.rime_lang,
                "sample_rate": self.rime_sample_rate,
                "speed_alpha": self.rime_speed_alpha,
                "transport": self.transport,
                "segment": self.rime_segment if self.effective_use_websocket else None,
                "base_url": self.endpoint,
                "base_url_source": (
                    "RIME_BASE_URL override" if self.rime_base_url
                    else "plugin default for this transport"
                ),
                "supports_bracket_controls": self.supports_brackets,
                "api_key": _redact(self.rime_api_key),
            },
            "pronunciation": {
                "strategy": self.pronunciation.value,
                "pause_ms_requested": self.pause_ms,
                "pause_ms_effective": self.effective_pause_ms,
            },
            "pipeline": {
                "stt": self.stt_model,
                "stt_language": self.stt_language,
                "llm": self.llm_model,
                "tts": f"rime/{self.rime_model}:{self.rime_speaker}",
            },
            "turn_handling": {
                "interruption_mode": self.interruption_mode,
                "min_interruption_duration": self.min_interruption_duration,
                "min_interruption_words": self.min_interruption_words,
                "resume_false_interruption": self.resume_false_interruption,
                "false_interruption_timeout": self.false_interruption_timeout,
                "preemptive_generation": self.preemptive_generation,
            },
            "heard_not_said": {"method": self.heard_method},
            "demo": {
                "dispatch_latency_ms": self.dispatch_latency_ms,
                "dispatch_jitter_ms": self.dispatch_jitter_ms,
                "publish_fence_events": self.publish_fence_events,
            },
            "livekit": {
                "url": _redact_url(self.livekit_url),
                "api_key": _redact(self.livekit_api_key),
                "api_secret": _redact(self.livekit_api_secret),
            },
            "warnings": list(self.warnings),
        }

    def banner(self) -> str:
        """Human-readable disclosure, printed at startup and shown in the UI.

        The Rime brief requires that the active speech provider be observable
        and that fallbacks be disclosed. This is that disclosure. It names the
        provider unconditionally, so a run using anything other than Rime for
        primary output would say so here.
        """
        d = self.to_dict()
        lines = [
            "=" * 68,
            " Waypoint - active configuration",
            "=" * 68,
            f"  SPEECH PROVIDER : Rime (primary, no fallback configured)",
            f"  model / speaker : {d['rime']['model']} / {d['rime']['speaker']}",
            f"  language        : {d['rime']['lang']}",
            f"  transport       : {d['rime']['transport']}"
            + (f"  segment={d['rime']['segment']}" if self.effective_use_websocket else ""),
            f"  audio           : PCM @ {d['rime']['sample_rate']} Hz"
            f"   speed_alpha={d['rime']['speed_alpha']}",
            f"  endpoint        : {d['rime']['base_url']}",
            "-" * 68,
            f"  STT             : {d['pipeline']['stt']} ({d['pipeline']['stt_language']})",
            f"  LLM             : {d['pipeline']['llm']}",
            "-" * 68,
            f"  pronunciation   : {d['pronunciation']['strategy']}"
            f"   (bracket controls supported: {d['rime']['supports_bracket_controls']})",
            f"  pause brackets  : requested {d['pronunciation']['pause_ms_requested']}ms"
            f" -> effective {d['pronunciation']['pause_ms_effective']}ms",
            f"  heard-not-said  : {d['heard_not_said']['method']}",
            "-" * 68,
            f"  interruption    : mode={d['turn_handling']['interruption_mode']}"
            f" min_duration={d['turn_handling']['min_interruption_duration']}s"
            f" min_words={d['turn_handling']['min_interruption_words']}",
            f"  false-interrupt : resume={d['turn_handling']['resume_false_interruption']}"
            f" timeout={d['turn_handling']['false_interruption_timeout']}s",
            f"  preemptive gen  : {d['turn_handling']['preemptive_generation']}",
            f"  dispatch latency: {d['demo']['dispatch_latency_ms']}ms"
            f" +/- {d['demo']['dispatch_jitter_ms']}ms",
            "-" * 68,
            f"  LIVEKIT_URL     : {d['livekit']['url']}",
            f"  LIVEKIT_API_KEY : {d['livekit']['api_key']}",
            f"  RIME_API_KEY    : {d['rime']['api_key']}",
        ]
        for w in self.warnings:
            lines.append(f"  ! WARNING       : {w}")
        lines.append("=" * 68)
        return "\n".join(lines)


def load_settings(*, strict_pronunciation: bool = True) -> Settings:
    """Read the environment, validate it, and return frozen settings.

    Raises :class:`ConfigError` for a configuration that would run but lie --
    principally a pronunciation strategy the chosen Rime model ignores.
    Missing credentials are *not* fatal here, so that ``--print-config`` and
    the offline test suite work on a laptop with no keys; call
    :meth:`Settings.require_runtime_keys` before actually connecting.
    """
    warnings: list[str] = []

    model = (_env("RIME_MODEL", "coda") or "coda").lower()
    if model not in ("coda", "mistv2", "mistv3"):
        raise ConfigError(
            f"RIME_MODEL={model!r} is not a Rime model id. "
            "Valid: coda, mistv2, mistv3. Check the live catalog at "
            "https://docs.rime.ai/api-reference/voices before the demo."
        )

    default_speaker = "lyra" if model == "coda" else "cove"
    speaker = _env("RIME_SPEAKER", default_speaker) or default_speaker

    strategy_raw = (_env("WAYPOINT_PRONUNCIATION", "respell") or "respell").lower()
    try:
        strategy = Strategy(strategy_raw)
    except ValueError:
        raise ConfigError(
            f"WAYPOINT_PRONUNCIATION={strategy_raw!r} is not valid. "
            "Use one of: respell, phoneme, none."
        ) from None

    lang = _env("RIME_LANG", "eng") or "eng"
    try:
        resolve_strategy(strategy, model, lang, strict=strict_pronunciation)
    except PronunciationError as exc:
        raise ConfigError(str(exc)) from None

    use_ws = _env_bool("RIME_USE_WEBSOCKET", True)
    base_url = _env("RIME_BASE_URL")

    # Warn about the transport that will actually be used, not the one that
    # was asked for. The plugin upgrades a `false` flag to WebSocket when the
    # override carries a `ws`/`wss` scheme, and an earlier revision warned
    # here about a degradation that was not happening -- on the banner, in the
    # terminal, on camera. See `Settings.effective_use_websocket`.
    effective_ws = use_ws or bool(base_url and base_url.startswith(("ws://", "wss://")))

    if not effective_ws:
        warnings.append(
            "RIME_USE_WEBSOCKET=false: heard-not-said falls back to the "
            "approximate duration estimator, and word timestamps are "
            "unavailable. This is disclosed in the transcript."
        )
    elif not use_ws:
        warnings.append(
            f"RIME_USE_WEBSOCKET=false is overridden by RIME_BASE_URL={base_url!r}: "
            "the plugin infers the transport from the URL scheme, so this run "
            "streams over a WebSocket. Word timestamps remain available."
        )

    if use_ws and base_url and base_url.startswith(("http://", "https://")):
        # `use_websocket=True` wins over the scheme, so the plugin opens a
        # WebSocket against an HTTP path. This configuration cannot work, and
        # failing loudly beats failing at the first spoken word.
        warnings.append(
            f"RIME_BASE_URL={base_url!r} is an HTTP URL but RIME_USE_WEBSOCKET "
            "is true, so the plugin will attempt a WebSocket handshake against "
            f"{base_url.rstrip('/')}/ws3. Set RIME_USE_WEBSOCKET=false, or "
            "point RIME_BASE_URL at a wss:// host."
        )

    pause_ms = _env_int("WAYPOINT_PAUSE_MS", 0)
    if pause_ms and model == "coda":
        warnings.append(
            f"WAYPOINT_PAUSE_MS={pause_ms} has no effect on model 'coda', "
            "which ignores pause brackets. Effective value is 0."
        )

    settings = Settings(
        rime_model=model,  # type: ignore[arg-type]
        rime_speaker=speaker,
        rime_lang=lang,
        rime_sample_rate=_env_int("RIME_SAMPLE_RATE", 22050),
        rime_speed_alpha=_env_float("RIME_SPEED_ALPHA", 1.0),
        rime_use_websocket=use_ws,
        rime_segment=_env("RIME_SEGMENT", "bySentence") or "bySentence",
        rime_base_url=base_url,
        pronunciation=strategy,
        pause_ms=pause_ms,
        stt_model=_env("WAYPOINT_STT", "deepgram/nova-3") or "deepgram/nova-3",
        stt_language=_env("WAYPOINT_STT_LANGUAGE", "multi") or "multi",
        llm_model=_env("WAYPOINT_LLM", "openai/gpt-4.1-mini") or "openai/gpt-4.1-mini",
        interruption_mode=(
            _env("WAYPOINT_INTERRUPTION_MODE", "adaptive") or "adaptive"
        ),  # type: ignore[arg-type]
        min_interruption_duration=_env_float("WAYPOINT_MIN_INTERRUPTION_DURATION", 0.4),
        min_interruption_words=_env_int("WAYPOINT_MIN_INTERRUPTION_WORDS", 0),
        resume_false_interruption=_env_bool("WAYPOINT_RESUME_FALSE_INTERRUPTION", True),
        false_interruption_timeout=_env_float("WAYPOINT_FALSE_INTERRUPTION_TIMEOUT", 1.0),
        preemptive_generation=_env_bool("WAYPOINT_PREEMPTIVE_GENERATION", True),
        dispatch_latency_ms=_env_float("WAYPOINT_DISPATCH_LATENCY_MS", 1800.0),
        dispatch_jitter_ms=_env_float("WAYPOINT_DISPATCH_JITTER_MS", 200.0),
        publish_fence_events=_env_bool("WAYPOINT_PUBLISH_FENCE_EVENTS", True),
        livekit_url=_env("LIVEKIT_URL"),
        livekit_api_key=_env("LIVEKIT_API_KEY"),
        livekit_api_secret=_env("LIVEKIT_API_SECRET"),
        rime_api_key=_env("RIME_API_KEY"),
        warnings=tuple(warnings),
    )
    return settings
