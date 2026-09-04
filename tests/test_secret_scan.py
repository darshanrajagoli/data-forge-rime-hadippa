"""The credential scanner.

A security control with no tests is not a control. "Exposes a live credential"
is a listed disqualifier in the Rime brief, so this file checks both halves of
the scanner's job: that it catches real keys, and that it does not cry wolf.

The second half matters as much as the first. A scanner that fires on a test
fixture gets switched off by whoever is trying to commit at 2am, and a scanner
that is switched off catches nothing.

Note the shape of the fixtures below. Each fake credential is defined once as
a constant carrying a ``secret-scan: allow`` pragma, and every test builds its
sample line by interpolating that constant. That is not cosmetic: it means no
*line* in this file contains a complete credential-shaped literal, so
:func:`test_this_repository_is_clean` really does scan this file and really
does find nothing, instead of the file being excluded to make the test pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from secret_scan import check_gitignore, scan, scan_text  # noqa: E402

FAKE = Path("sample.py")

# Fake credentials, each annotated once. Nothing here is real.
RIME_K = "ak_9f3b21c7d84e5a06b1f2"          # secret-scan: allow
LIVEKIT_K = "APIabcdef1234567"              # secret-scan: allow
GH_K = "gh_A1b2C3d4E5f6G7h8I9j0K1l2"        # secret-scan: allow
PW = "hunter2hunter2hunter2"                # secret-scan: allow
OPENAI_K = "sk-proj-AAAABBBBCCCCDDDDEEEEFF" # secret-scan: allow
AWS_K = "AKIAZZZZQQQQWWWWEEE1"              # secret-scan: allow
URL_CRED = "wss://apikey:s3cr3tvalue99@host.io"  # secret-scan: allow
PEM = "-----BEGIN RSA PRIVATE KEY-----"     # secret-scan: allow
PEM_SSH = "-----BEGIN OPENSSH PRIVATE KEY-----"  # secret-scan: allow


def hits(text: str, path: Path = FAKE) -> list:
    return scan_text(path, text, str(path))


# --------------------------------------------------------------------------
# It catches real credentials
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line,rule_fragment",
    [
        (f'RIME_API_KEY = "{RIME_K}"', "Rime"),
        (f'key = "{LIVEKIT_K}"', "LiveKit"),
        (f'token = "{GH_K}"', "secret-looking"),
        (f'password = "{PW}"', "secret-looking"),
        (PEM, "private key"),
        (PEM_SSH, "private key"),
        (f'url = "{URL_CRED}"', "URL"),
        (f'aws = "{AWS_K}"', "AWS"),
        (f'k = "{OPENAI_K}"', "OpenAI"),
    ],
)
def test_catches(line: str, rule_fragment: str) -> None:
    found = hits(line + "\n")
    assert found, f"missed: {line}"
    assert rule_fragment.lower() in found[0].rule.lower(), (
        f"matched {found[0].rule!r}, expected something like {rule_fragment!r}"
    )


def test_reports_line_number_and_excerpt() -> None:
    text = f'ok = 1\n\nRIME_API_KEY = "{RIME_K}"\n'
    (f,) = hits(text)
    assert f.line == 3
    assert RIME_K[:8] in f.excerpt


def test_one_finding_per_line() -> None:
    """Two rules matching the same line is one problem, not two."""
    assert len(hits(f'secret = "{LIVEKIT_K}abc"\n')) == 1


def test_long_lines_are_skipped_not_crashed_on() -> None:
    assert hits("x = 1  # " + "y" * 3000 + "\n") == []


# --------------------------------------------------------------------------
# It does not cry wolf
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "RIME_API_KEY=your-rime-api-key",
        'key = "xxxxxxxxxxxxxxxxxxxx"',
        'key = "placeholder-value-here"',
        'key = "sk_test_abcdefghijklmnop"',
        "RIME_API_KEY=<your key here>",
        'key = "${RIME_API_KEY}"',
        'key = "{{ rime_api_key }}"',
        'url = f"wss://key:{SECRET}@demo.livekit.cloud"',
        'url = "wss://key:secret@host"',
        'url = "postgres://user:password@db"',
        'key = "%(rime_key)s"',
        "# RIME_API_KEY is read from the environment",
        'SECRET = "sk_live_FAKE_not_a_real_credential_00"',
        'aws = "AKIAIOSFODNN7EXAMPLE"',
        'note = "the key is redacted in the banner"',
    ],
)
def test_allows_obvious_non_secrets(line: str) -> None:
    assert hits(line + "\n") == [], f"false positive on: {line}"


def test_env_example_is_treated_as_a_template() -> None:
    """It exists to hold placeholder-shaped values."""
    assert hits(f"LIVEKIT_API_KEY={LIVEKIT_K}\n", Path(".env.example")) == []


def test_a_private_key_is_flagged_even_in_a_template() -> None:
    """There is no legitimate reason for one to be in .env.example."""
    assert hits(PEM + "\n", Path(".env.example"))


# --------------------------------------------------------------------------
# The pragma
# --------------------------------------------------------------------------


def _real_line() -> str:
    return f'RIME_API_KEY = "{RIME_K}"'


def test_the_bare_line_really_would_be_caught() -> None:
    """Guards the pragma tests below from passing vacuously."""
    assert hits(_real_line() + "\n")


def test_pragma_on_the_same_line_suppresses() -> None:
    assert hits(f"{_real_line()}  # secret-scan: allow\n") == []


def test_pragma_on_the_preceding_line_suppresses() -> None:
    assert hits(f"# secret-scan: allow\n{_real_line()}\n") == []


def test_pragma_does_not_suppress_two_lines_down() -> None:
    """A blanket pragma at the top of a file must not disarm the whole file."""
    assert hits(f"# secret-scan: allow\nx = 1\n{_real_line()}\n")


@pytest.mark.parametrize(
    "form", ["secret-scan: allow", "secret_scan: ignore", "secret scan:allow"]
)
def test_pragma_spellings(form: str) -> None:
    assert hits(f"{_real_line()}  # {form}\n") == []


# --------------------------------------------------------------------------
# The repository itself
# --------------------------------------------------------------------------


def test_this_repository_is_clean() -> None:
    """The check that actually matters. Also runs in the pre-commit hook."""
    findings = scan(ROOT)
    assert findings == [], "\n".join(
        f"{f.path}:{f.line} [{f.rule}] {f.excerpt}" for f in findings
    )


def test_gitignore_covers_the_env_files() -> None:
    assert check_gitignore(ROOT) == []


def test_env_example_exists_and_has_no_real_values() -> None:
    example = ROOT / ".env.example"
    assert example.exists()
    body = example.read_text(encoding="utf-8")
    assert "your-rime-api-key" in body
    assert scan_text(example, body, ".env.example") == []


def test_env_local_if_present_is_gitignored() -> None:
    if (ROOT / ".env.local").exists():
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".env.local" in gi, ".env.local exists and is not gitignored"


# --------------------------------------------------------------------------
# Vendor identifiers vs real keys
#
# The LiveKit key rule matches "API" followed by ten or more characters.
# LiveKit's own public exception classes are exactly that shape, so the scanner
# reported the vendor's error hierarchy as leaked credentials -- and the
# pre-commit hook blocked any commit containing real tool output. Six places in
# this repository format errors as f"{type(exc).__name__}: {exc}", and
# team/worksheets/MEASUREMENTS.md explicitly asks the reader to paste failures in.
#
# Every fixture below is composed at runtime so that no line in this file holds
# a complete credential-shaped literal. That is deliberate: this file is itself
# walked by test_this_repository_is_clean, and that test only means something
# if the scanner really does read it.
# --------------------------------------------------------------------------

#: Built from ordinals so no line in this file contains a bare quote or
#: newline escape that a heredoc or an editor could mangle.
NL = chr(10)
Q = chr(34)

VENDOR_NAMES = [
    "ConnectionError",
    "StatusError",
    "TimeoutError",
    "ConnectOptions",
    "ConnectError",
    "Error",
]

#: Real-key tails, prefixed with "API" at runtime.
KEY_TAILS = [
    "Rb7kQm2xLp9w",       # capital-then-lowercase: what a lookahead fix misses
    "Km3xyzABC123",
    "abcdef1234567",
    "zzzz00001111",
    "ConnectionErrorX9",  # vendor-shaped, but not a vendor name
]


@pytest.mark.parametrize("suffix", VENDOR_NAMES)
def test_livekit_exception_names_are_not_credentials(suffix: str) -> None:
    """Pasting real tool output into a document must not block a commit."""
    name = "API" + suffix
    line = "    ! " + name + ": message=" + Q + "Invalid response" + Q + ", status=401"
    assert hits(line + NL) == [], "false positive on " + name


@pytest.mark.parametrize("tail", KEY_TAILS)
def test_a_real_key_shaped_like_a_vendor_name_is_still_flagged(tail: str) -> None:
    """The property that the obvious fix breaks.

    Excluding CamelCase tails by pattern (API followed by a negative lookahead
    on [A-Z][a-z]) removes the vendor noise *and* stops detecting real keys
    whose fourth character is a capital followed by a lowercase. A false
    negative in a credential scanner is strictly worse than the noise it
    removes, so the fix subtracts an explicit allowlist from matches rather
    than narrowing the pattern.
    """
    key = "API" + tail
    assert hits("key = " + Q + key + Q + NL), "stopped detecting " + key


def test_the_allowlist_is_exact_not_a_prefix_match() -> None:
    from secret_scan import VENDOR_IDENTIFIERS

    assert "API" + "ConnectionError" in VENDOR_IDENTIFIERS
    composed = "API" + "ConnectionError" + "AAAA"
    assert hits("k = " + Q + composed + Q + NL), "a key prefixed by a vendor name is still a key"


# --------------------------------------------------------------------------
# A key hiding behind a vendor name
#
# The two tests above put the key alone on the line, and that is why they both
# passed against a scanner that could not see this:
#
#     APIStatusError: message='Invalid response status', key=API<real key>
#
# `scan_text` called `pattern.search(line)` -- the *first* match -- and on an
# allowlist hit did `continue`, which abandoned the whole rule for that line
# rather than that one match. Everything after the vendor name went unread.
#
# That is not a contrived line. It is the shape already sitting in
# evidence/results/latency.md, and team/worksheets/MEASUREMENTS.md instructs the reader to
# paste real tool output into the repository. A scanner blind to it reports
# `clean` on a committed credential, and "exposes a live credential" is a
# listed disqualifier.
#
# These tests state the property rather than the case: position on the line
# must not affect detection, in either order, for every vendor name and every
# key shape. A test written to kill one specific mutant would have passed
# against the bug it was supposed to prevent -- which is what happened.
# --------------------------------------------------------------------------


def _vendor_noise(name: str) -> str:
    """The exact prose LiveKit produces, minus any credential."""
    return name + ": message=" + Q + "Invalid response status" + Q + ", status_code=401"


@pytest.mark.parametrize("vendor", VENDOR_NAMES)
@pytest.mark.parametrize("tail", KEY_TAILS)
def test_a_key_after_a_vendor_name_on_the_same_line_is_found(
    vendor: str, tail: str
) -> None:
    """The false negative. Thirty combinations, all previously missed."""
    key = "API" + tail
    line = _vendor_noise("API" + vendor) + ", key=" + key
    assert hits(line + NL), "missed " + key + " behind API" + vendor


@pytest.mark.parametrize("vendor", VENDOR_NAMES)
@pytest.mark.parametrize("tail", KEY_TAILS)
def test_a_key_before_a_vendor_name_on_the_same_line_is_found(
    vendor: str, tail: str
) -> None:
    """The mirror case, which `search` happened to get right. Both directions
    are asserted so that a future "optimisation" back to first-match-only
    fails here too, not only in the test above."""
    key = "API" + tail
    line = "key=" + key + " raised " + _vendor_noise("API" + vendor)
    assert hits(line + NL), "missed " + key + " before API" + vendor


def test_the_exact_line_shape_already_committed_to_this_repository() -> None:
    """evidence/results/latency.md really does contain this, minus the key."""
    key = "API" + "n8Kd93mZq7Lx2Vb0Rt"
    line = (
        "  cold/websocket: API" + "StatusError: message=" + Q
        + "Invalid response status" + Q + ", status_code=401, key=" + key
    )
    assert hits(line + NL), "the scanner is blind to the shape it already ships"


@pytest.mark.parametrize("vendor", VENDOR_NAMES)
def test_several_vendor_names_do_not_exhaust_the_scanner(vendor: str) -> None:
    key = "API" + "Rb7kQm2xLp9w"
    line = (
        "except (API" + "ConnectionError, API" + "TimeoutError, API" + vendor
        + "): retry(" + key + ")"
    )
    assert hits(line + NL), "gave up before reaching the key"


def test_the_noise_property_survives_the_fix() -> None:
    """The allowlist still has to do its original job: a line of nothing but
    vendor identifiers must not block a commit. Restoring detection is only a
    fix if it does not reintroduce the false positives."""
    for vendor in VENDOR_NAMES:
        name = "API" + vendor
        assert hits("    ! " + _vendor_noise(name) + NL) == [], "cried wolf on " + name
    assert hits("except (API" + "StatusError, API" + "TimeoutError):" + NL) == []
    assert hits("raise API" + "ConnectionError(" + Q + "rime unreachable" + Q + ")" + NL) == []


# --------------------------------------------------------------------------
# JSON-shaped credentials
#
# Every committed artifact in evidence/results/ is JSON. The rule matched
# name = "value" but not "name": "value", because the closing quote sits
# between the name and the colon -- so a key in an artifact was undetectable,
# in the very directory SKIP_DIRS was excluding from the walk. The two gaps
# hid each other.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,value",
    [
        ("api_key", RIME_K),
        ("secret", "s3cr3t" + "value0123456789"),
        ("token", "tok_" + "abcdefghij0123456"),
        ("password", PW),
    ],
)
def test_json_shaped_credentials_are_caught(name: str, value: str) -> None:
    line = "{" + Q + name + Q + ": " + Q + value + Q + "}"
    assert hits(line + NL, Path("artifact.json")), "missed: " + line


@pytest.mark.parametrize(
    "value",
    [
        "your-rime-api-key",
        "your-livekit-api-secret",
        "${RIME_API_KEY}",
        "the api_key is redacted in the banner",
    ],
)
def test_json_placeholders_are_not_flagged(value: str) -> None:
    line = "{" + Q + "api_key" + Q + ": " + Q + value + Q + "}"
    assert hits(line + NL, Path("artifact.json")) == [], "false positive: " + line


# --------------------------------------------------------------------------
# The walk itself
#
# Every other test in this file exercises scan_text -- the rule engine. None
# exercised scan(), the function that walks the tree, and the only test that
# called it asserted it returns NOTHING. That test passes *more easily* when
# the scanner is broken: a mutation making scan() return [] unconditionally
# was invisible to the entire suite.
#
# These plant a key and require it to be found. Verified against that exact
# mutation, which is the whole point of a regression test.
# --------------------------------------------------------------------------


def _repo(tmp_path, rel: str, body: str):
    (tmp_path / '.gitignore').write_text('.env' + NL + '.env.local' + NL,
                                         encoding='utf-8')
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding='utf-8')
    return tmp_path


def _planted() -> str:
    return '{' + Q + 'api_key' + Q + ': ' + Q + RIME_K + Q + '}'


def test_scan_walks_the_tree_and_finds_a_planted_key(tmp_path) -> None:
    """If scan() ever stops walking, this is the test that says so."""
    root = _repo(tmp_path, 'src/leak.py', 'API_KEY = ' + Q + RIME_K + Q + NL)
    findings = scan(root)
    assert findings, 'scan() returned nothing for a tree containing a key'
    assert findings[0].path.endswith('leak.py')


def test_scan_reaches_the_committed_artifact_directory(tmp_path) -> None:
    """evidence/results/ holds committed artifacts and agent session dumps.

    It was in SKIP_DIRS as the bare word 'results', so the whole tree was
    invisible -- and every artifact in it is JSON, which the assignment rule
    could not match either. The two gaps hid each other.
    """
    root = _repo(tmp_path, 'evidence/results/session.json', _planted())
    findings = scan(root)
    assert findings, 'evidence/results is not being walked'
    assert 'results' in findings[0].path


def test_scan_reaches_a_nested_artifact_subdirectory(tmp_path) -> None:
    root = _repo(tmp_path, 'evidence/results/pronunciation/report.json', _planted())
    assert scan(root)


def test_gitignored_scratch_subdirectory_is_still_skipped(tmp_path) -> None:
    """The one path that stays excluded, and only that one."""
    root = _repo(tmp_path, 'evidence/results/tmp/scratch.json', _planted())
    assert scan(root) == []


def test_scan_returns_findings_from_several_files(tmp_path) -> None:
    """Guards against a scan() that stops at the first hit."""
    root = _repo(tmp_path, 'a/one.json', _planted())
    (root / 'b').mkdir()
    (root / 'b' / 'two.json').write_text(_planted(), encoding='utf-8')
    assert len(scan(root)) >= 2


def test_scan_of_a_clean_tree_is_empty(tmp_path) -> None:
    """The negative case, so the positives above are not vacuous."""
    root = _repo(tmp_path, 'src/ok.py', 'RIME_API_KEY = your-rime-api-key' + NL)
    assert scan(root) == []


# --------------------------------------------------------------------------
# Vendor-prefixed keys
#
# This rule exists because GitHub's push protection rejected a push from this
# repository over a key class the scanner below had no rule for. The blocked
# string was a *fake* Stripe restricted key used as an example fixture inside
# an archived audit report -- harmless in itself, and exactly the point: an
# external control found a gap in ours, on a project whose own argument is
# credential hygiene.
#
# The honest response to a miss is a rule, not an exception. These are the
# prefix conventions that actually leak in practice.
#
# Every fixture is composed at runtime so no line in this file holds a
# complete key-shaped literal -- this file is itself walked by
# test_this_repository_is_clean.
# --------------------------------------------------------------------------

VENDOR_KEYS = [
    ("Stripe restricted, live", "rk_" + "live_9f3b2c8a41de47b6a05c7e1d93f8ab24"),
    ("Stripe secret, live", "sk_" + "live_51H8xKjQm2xLp9wRb7kAAAA"),
    ("Stripe publishable, test", "pk_" + "test_51H8xKjQm2xLp9wRb7kAAAA"),
    ("Stripe webhook signing", "whsec_" + "9f3b2c8a41de47b6a05c7e1d9"),
    ("GitHub PAT, classic", "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"),
    ("GitHub PAT, fine-grained", "github_pat_" + "11ABCDEFG0aBcDeFgHiJkLmNoPqR"),
    ("GitHub OAuth", "gho_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"),
    ("Slack bot token", "xoxb-" + "123456789012-abcdefghijkl"),
    ("Google API key", "AIza" + "SyD1234567890abcdefghijklmnopqrstu"),
]


@pytest.mark.parametrize("label,key", VENDOR_KEYS, ids=[k[0] for k in VENDOR_KEYS])
def test_vendor_prefixed_keys_are_flagged(label: str, key: str) -> None:
    assert hits(key + NL), "missed " + label
    assert hits("token = " + Q + key + Q + NL), "missed " + label + " as an assignment"
    assert hits(Q + "k" + Q + ": " + Q + key + Q + NL), "missed " + label + " in JSON"


@pytest.mark.parametrize("label,key", VENDOR_KEYS, ids=[k[0] for k in VENDOR_KEYS])
def test_vendor_prefixed_keys_are_found_behind_a_vendor_name(
    label: str, key: str
) -> None:
    """The F10 property, extended to the new rule. A rule added later must
    inherit the position-independence the scan loop guarantees, not quietly
    opt out of it."""
    line = "API" + "StatusError: message=" + Q + "denied" + Q + ", key=" + key
    assert hits(line + NL), "missed " + label + " behind a vendor name"


@pytest.mark.parametrize(
    "benign",
    [
        "the sk_ prefix is used by stripe",
        "rk_live_ is a prefix, not a key",
        "the ghost_ prefix means nothing here",
        "see https://stripe.com/docs/keys for the whsec_ convention",
        "AIza is the Google prefix",
    ],
)
def test_prefixes_discussed_in_prose_are_not_credentials(benign: str) -> None:
    """Documentation talks about these prefixes. Firing on the prose is how a
    scanner gets switched off."""
    assert hits(benign + NL) == [], "cried wolf on: " + benign


def test_the_archived_audit_no_longer_carries_a_key_shaped_literal() -> None:
    """A regression guard on the specific thing GitHub rejected.

    The audit reports are shipped in full, deliberately. That means their
    example fixtures have to be inert -- an illustrative "key" in a report is
    still a string that every scanner on the internet will flag, and one that
    blocks a push is one that blocks a submission.
    """
    audits = ROOT / "docs" / "audits"
    if not audits.exists():
        pytest.skip("no archived audits")
    for f in audits.glob("*.md"):
        found = scan_text(f, f.read_text(encoding="utf-8"), str(f))
        assert not found, f"{f.name} carries {found[0].rule} on line {found[0].line}"
