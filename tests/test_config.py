"""Configuration: nothing degrades silently, no secret escapes.

The Rime brief allows fallback behaviour but requires it to be disclosed and
observable, and requires credentials never to reach source, docs, screenshots
or client code. Both are properties of this module, so both are tested.
"""

from __future__ import annotations

import pytest

from waypoint.config import ConfigError, REQUIRED_KEYS, Settings, load_settings
from waypoint.pronounce import Strategy


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Every test starts from a known-empty environment."""
    for key in list(REQUIRED_KEYS) + [
        "RIME_MODEL", "RIME_SPEAKER", "RIME_LANG", "RIME_SAMPLE_RATE",
        "RIME_SPEED_ALPHA", "RIME_USE_WEBSOCKET", "RIME_SEGMENT", "RIME_BASE_URL",
        "WAYPOINT_PRONUNCIATION", "WAYPOINT_PAUSE_MS", "WAYPOINT_STT",
        "WAYPOINT_LLM", "WAYPOINT_DISPATCH_LATENCY_MS",
        "WAYPOINT_INTERRUPTION_MODE", "WAYPOINT_MIN_INTERRUPTION_DURATION",
    ]:
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------


def test_defaults_match_the_rime_quickstart() -> None:
    s = load_settings()
    assert s.rime_model == "coda"
    assert s.rime_speaker == "lyra"
    assert s.rime_lang == "eng"
    assert s.rime_use_websocket is True


def test_speaker_default_follows_the_model(monkeypatch) -> None:
    """coda and mist have different default voices in the plugin."""
    monkeypatch.setenv("RIME_MODEL", "mistv2")
    assert load_settings().rime_speaker == "cove"


def test_missing_credentials_are_not_fatal_at_load() -> None:
    """So --print-config and the offline test suite work with no keys."""
    s = load_settings()
    assert set(s.missing_keys()) == set(REQUIRED_KEYS)
    with pytest.raises(ConfigError, match="missing required"):
        s.require_runtime_keys()


def test_present_credentials_satisfy_the_check(monkeypatch) -> None:
    for k in REQUIRED_KEYS:
        monkeypatch.setenv(k, "x" * 24)
    load_settings().require_runtime_keys()


# --------------------------------------------------------------------------
# Loud failures
# --------------------------------------------------------------------------


def test_phonemes_on_coda_is_a_startup_error(monkeypatch) -> None:
    """The exact silent no-op this codebase exists to prevent."""
    monkeypatch.setenv("RIME_MODEL", "coda")
    monkeypatch.setenv("WAYPOINT_PRONUNCIATION", "phoneme")
    with pytest.raises(ConfigError) as exc:
        load_settings()
    assert "coda" in str(exc.value)
    assert "respell" in str(exc.value), "the error must name the fix"


def test_phonemes_on_mistv2_is_fine(monkeypatch) -> None:
    monkeypatch.setenv("RIME_MODEL", "mistv2")
    monkeypatch.setenv("WAYPOINT_PRONUNCIATION", "phoneme")
    assert load_settings().pronunciation is Strategy.PHONEME


def test_unknown_model_is_rejected_with_the_catalog_link(monkeypatch) -> None:
    monkeypatch.setenv("RIME_MODEL", "mistv9")
    with pytest.raises(ConfigError) as exc:
        load_settings()
    assert "coda, mistv2, mistv3" in str(exc.value)
    assert "catalog" in str(exc.value)


def test_unknown_pronunciation_strategy_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("WAYPOINT_PRONUNCIATION", "telepathy")
    with pytest.raises(ConfigError, match="respell, phoneme, none"):
        load_settings()


def test_non_numeric_float_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("RIME_SPEED_ALPHA", "fast")
    with pytest.raises(ConfigError, match="not a number"):
        load_settings()


def test_non_numeric_int_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("RIME_SAMPLE_RATE", "lots")
    with pytest.raises(ConfigError, match="not an integer"):
        load_settings()


# --------------------------------------------------------------------------
# Disclosed degradations
# --------------------------------------------------------------------------


def test_http_mode_warns_that_heard_tracking_degrades(monkeypatch) -> None:
    monkeypatch.setenv("RIME_USE_WEBSOCKET", "false")
    s = load_settings()
    assert any("approximate" in w for w in s.warnings)
    assert s.heard_method.startswith("duration_estimate")


def test_websocket_mode_reports_exact_heard_tracking() -> None:
    assert load_settings().heard_method.startswith("word_timestamps")


def test_pause_ms_on_coda_warns_and_zeroes(monkeypatch) -> None:
    """Coda ignores pause brackets. Say so; do not pretend they applied."""
    monkeypatch.setenv("RIME_MODEL", "coda")
    monkeypatch.setenv("WAYPOINT_PAUSE_MS", "300")
    s = load_settings()
    assert s.pause_ms == 300
    assert s.effective_pause_ms == 0
    assert any("no effect on model 'coda'" in w for w in s.warnings)


def test_pause_ms_on_mistv2_takes_effect(monkeypatch) -> None:
    monkeypatch.setenv("RIME_MODEL", "mistv2")
    monkeypatch.setenv("WAYPOINT_PAUSE_MS", "300")
    s = load_settings()
    assert s.effective_pause_ms == 300
    assert s.warnings == ()


def test_supports_brackets_by_model(monkeypatch) -> None:
    monkeypatch.setenv("RIME_MODEL", "coda")
    assert load_settings().supports_brackets is False
    monkeypatch.setenv("RIME_MODEL", "mistv2")
    assert load_settings().supports_brackets is True


def test_non_english_mistv3_loses_bracket_support(monkeypatch) -> None:
    monkeypatch.setenv("RIME_MODEL", "mistv3")
    monkeypatch.setenv("RIME_LANG", "spa")
    assert load_settings().supports_brackets is False


# --------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------


# A deliberately fake credential. Long enough to exercise redaction,
# obviously synthetic so scripts/secret_scan.py does not flag it.
SECRET = "sk_live_FAKE_not_a_real_credential_00"


CREDENTIAL_KEYS = ("LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "RIME_API_KEY")


def _set_credentials(monkeypatch) -> None:
    """Realistic env: a public URL plus three genuine secrets."""
    monkeypatch.setenv("LIVEKIT_URL", "wss://waypoint-demo.livekit.cloud")
    for k in CREDENTIAL_KEYS:
        monkeypatch.setenv(k, SECRET)


def test_banner_never_prints_a_secret(monkeypatch) -> None:
    _set_credentials(monkeypatch)
    banner = load_settings().banner()
    assert SECRET not in banner
    assert "not_a_real_credential" not in banner


def test_to_dict_never_contains_a_secret(monkeypatch) -> None:
    import json

    _set_credentials(monkeypatch)
    blob = json.dumps(load_settings().to_dict())
    assert SECRET not in blob
    assert "not_a_real_credential" not in blob


def test_livekit_url_is_shown_because_it_is_not_a_secret(monkeypatch) -> None:
    """It is public, and it is the most useful line when a demo will not connect."""
    _set_credentials(monkeypatch)
    assert "wss://waypoint-demo.livekit.cloud" in load_settings().banner()


def test_credentials_embedded_in_the_url_are_stripped(monkeypatch) -> None:
    """The banner is printed to a terminal that gets screen-recorded."""
    monkeypatch.setenv("LIVEKIT_URL", f"wss://key:{SECRET}@demo.livekit.cloud")
    d = load_settings().to_dict()
    assert SECRET not in d["livekit"]["url"]
    assert d["livekit"]["url"] == "wss://<redacted>@demo.livekit.cloud"


def test_redaction_still_confirms_presence_and_length(monkeypatch) -> None:
    """You must be able to tell 'set' from 'unset' without seeing the value."""
    monkeypatch.setenv("RIME_API_KEY", SECRET)
    d = load_settings().to_dict()
    assert d["rime"]["api_key"].startswith("set (")
    assert f"len={len(SECRET)}" in d["rime"]["api_key"]


def test_unset_key_is_reported_as_unset() -> None:
    assert load_settings().to_dict()["rime"]["api_key"] == "(unset)"


def test_short_secret_is_fully_masked(monkeypatch) -> None:
    monkeypatch.setenv("RIME_API_KEY", "abc")
    assert load_settings().to_dict()["rime"]["api_key"] == "set (***)"


def test_repr_of_settings_hides_credential_fields() -> None:
    s = Settings(rime_api_key=SECRET, livekit_api_secret=SECRET)
    assert SECRET not in repr(s)


# --------------------------------------------------------------------------
# The disclosure banner
# --------------------------------------------------------------------------


def test_banner_names_the_speech_provider_unconditionally() -> None:
    """'Make the active speech provider observable' - the Rime brief."""
    banner = load_settings().banner()
    assert "SPEECH PROVIDER : Rime" in banner


def test_banner_states_the_exact_shipped_configuration() -> None:
    banner = load_settings().banner()
    for expected in ("coda", "lyra", "eng", "22050", "WebSocket", "respell"):
        assert expected in banner


def test_banner_surfaces_warnings(monkeypatch) -> None:
    monkeypatch.setenv("RIME_USE_WEBSOCKET", "false")
    assert "! WARNING" in load_settings().banner()


def test_empty_env_var_is_treated_as_unset(monkeypatch) -> None:
    monkeypatch.setenv("RIME_SPEAKER", "   ")
    assert load_settings().rime_speaker == "lyra"


def test_bool_parsing(monkeypatch) -> None:
    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("RIME_USE_WEBSOCKET", truthy)
        assert load_settings().rime_use_websocket is True
    for falsy in ("0", "false", "no", "off"):
        monkeypatch.setenv("RIME_USE_WEBSOCKET", falsy)
        assert load_settings().rime_use_websocket is False
