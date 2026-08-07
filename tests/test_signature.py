"""Tests for the quarantine failure-signature extractor.

`_signature()` is the entire diagnostic surface of a library-scale ingest: it reduces a
failed workchain run's captured stdout+stderr to ONE groupable line, so that "295 failed"
becomes "which bugs, how many, go look here". On the first complete archive index
(112,401 ok / 295 failed of 112,696) it produced almost nothing usable, and finding that
out cost two days of manual sqlite spelunking.

Every blob below is a REAL capture from `ingest_quarantine.stderr_tail` on that run, not a
fabrication. Each assertion was checked against the pre-fix implementation and goes red
there — per the house rule that a test is only accepted when it can be proven to fail.

`archive/` is a package but these tests are run from the repo root without installation,
so the module is loaded by path rather than imported by name.
"""
import importlib.util
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE_PATH = os.path.join(os.path.dirname(_HERE), "archive", "ingest_batch.py")

_spec = importlib.util.spec_from_file_location("_ingest_batch_under_test", _MODULE_PATH)
_ib = importlib.util.module_from_spec(_spec)
sys.modules["_ingest_batch_under_test"] = _ib
_spec.loader.exec_module(_ib)

_signature = _ib._signature
_failing_step = _ib._failing_step

E = "\x1b[0;31m"
R = "\x1b[0m"


# ── the real blobs ───────────────────────────────────────────────────────────────────

VERIFIER_VIOLATION = "\n".join([
    "Registered output: probe.probe -> /Users/d/.sound-archive/work/e69f/archive/64104005.probe.json (type: json)",
    E + "[00:21:47] ERROR:" + R + " /Users/d/repos/lufs-workchain/lib/workchain_verify.py:848: "
    "DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal "
    "in a future version. Use timezone-aware objects to represent datetimes in UTC: "
    "datetime.datetime.now(datetime.UTC).",
    E + "[00:21:47] ERROR:" + R + '   "verified_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),',
    E + "[00:21:47] ERROR:" + R + " ✗ probe — verification FAILED (1 of 5 checks)",
    E + "[00:21:47] ERROR:" + R + "     probe_facts_plausible: samplerate: 1280 >= 2000  <- VIOLATED",
    E + "[00:21:47] ERROR:" + R + " Step failed verification: probe",
    E + "[00:21:47] ERROR:" + R + " Chain halted: step 'probe' failed",
])

SALVAGE_FAILURE = "\n".join([
    "probe: ffmpeg refused /Users/d/Samples/Pole Position/Porsche Carrera GT.wav "
    "(Error opening input files: Invalid data found when processing input) "
    "and salvage failed (no plausible fmt chunk found)",
    E + "[06:02:09] ERROR:" + R + " probe failed to produce /Users/d/.sound-archive/work/8b86/archive/Porsche.probe.json",
    E + "[06:02:09] ERROR:" + R + " Step failed: probe",
    E + "[06:02:09] ERROR:" + R + " Chain halted: step 'probe' failed",
])

SHOWWAVESPIC = "\n".join([
    "[Parsed_showwavespic_1 @ 0x7f8b2c904d40] Too few samples",
    E + "[03:11:02] ERROR:" + R + " hook failed (clip or waveform missing; decoder=ffmpeg)",
    E + "[03:11:02] ERROR:" + R + " Chain halted: step 'hook' failed",
])

EMBED_413 = "\n".join([
    "Registered output: hook.waveform -> /Users/d/.sound-archive/work/db1b/archive/Working.waveform.png (type: file)",
    'clap_remote: server rejected the request: HTTP 413 {"detail":"clip is 4244.3 s; '
    'EMBED_MAX_SECONDS=1800. Refusing to truncate silently."} — not retrying '
    "(a contract error is not transient)",
    E + "[00:27:46] ERROR:" + R + " embed_clap failed to produce /Users/d/.sound-archive/work/db1b/archive/Working.embedding.json (backend=remote)",
    E + "[00:27:46] ERROR:" + R + " Step failed: embed_clap",
    E + "[00:27:46] ERROR:" + R + " Chain halted: step 'embed_clap' failed",
])

UNICODE_CRASH = "\n".join([
    '  File "/Users/d/repos/lufs-workchain/lib/workchain_decode.py", line 91, in run',
    "    return subprocess.run(cmd, capture_output=True, text=True, errors=None, **kw)",
    "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf6 in position 4211: invalid start byte",
])

ALL_BLOBS = [VERIFIER_VIOLATION, SALVAGE_FAILURE, SHOWWAVESPIC, EMBED_413, UNICODE_CRASH]


# ── what the signature must say ──────────────────────────────────────────────────────

@pytest.mark.parametrize("blob,must_contain,must_not_contain", [
    # The 67-file case. Pre-fix this returned the DeprecationWarning, because it was the
    # first line matching the generic `ERROR:` pattern.
    (VERIFIER_VIOLATION, ["samplerate: 1280 >= 2000", "VIOLATED"], ["DeprecationWarning"]),
    # The salvage case. Pre-fix the informative line was dropped by the substring blacklist
    # on "Error opening input files", leaving the contentless fallback.
    (SALVAGE_FAILURE, ["ffmpeg refused", "salvage failed"], ["probe failed to produce"]),
    # Regression guard on behaviour that already worked — the bracketed ffmpeg line wins and
    # the heap address is normalised so 156 distinct files collapse to one row.
    (SHOWWAVESPIC, ["Parsed_showwavespic_1 @ 0xADDR", "Too few samples"], []),
    # The server's own refusal is the cause; "failed to produce" is the consequence.
    (EMBED_413, ["413"], ["embed_clap failed to produce"]),
    # The warning filter must not swallow real exceptions. This is the case the original
    # preference-order comment was written for and it must keep working.
    (UNICODE_CRASH, ["UnicodeDecodeError"], []),
])
def test_signature_names_the_cause(blob, must_contain, must_not_contain):
    sig = _signature(blob)
    for frag in must_contain:
        assert frag in sig, "expected %r in %r" % (frag, sig)
    for frag in must_not_contain:
        assert frag not in sig, "did not expect %r in %r" % (frag, sig)


@pytest.mark.parametrize("blob", ALL_BLOBS)
def test_signature_is_free_of_ansi(blob):
    """Raw escapes shatter GROUP BY: identical failures stop grouping, and the report is
    unreadable (`^[[0;31mERROR:`). Pre-fix, every engine-logged signature carried them."""
    sig = _signature(blob)
    assert "\x1b" not in sig
    assert not re.search(r"\[\d;\d\dm", sig)


@pytest.mark.parametrize("blob", ALL_BLOBS)
def test_signature_is_bounded_and_nonempty(blob):
    sig = _signature(blob)
    assert 0 < len(sig) <= 140
    assert sig == sig.strip()


def test_signature_of_nothing():
    assert _signature("") == "(no output)"
    assert _signature(None) == "(no output)"


def test_signature_groups_across_filenames():
    """The point of the function: two different files failing the same way must produce ONE
    row. Paths are normalised to <path>, so only the bug remains."""
    a = SALVAGE_FAILURE.replace("Porsche Carrera GT", "Morris Oxford 1969")
    assert _signature(a) == _signature(SALVAGE_FAILURE)


@pytest.mark.parametrize("blob,step", [
    (VERIFIER_VIOLATION, "probe"),
    (SALVAGE_FAILURE, "probe"),
    (SHOWWAVESPIC, "hook"),
    (EMBED_413, "embed_clap"),
])
def test_failing_step(blob, step):
    assert _failing_step(blob) == step


def test_failing_step_unknown():
    assert _failing_step("nothing useful here") == "unknown"
