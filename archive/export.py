#!/usr/bin/env python3
"""
export.py — the `lsmp` handoff descriptor + the use flywheel.

  larc export <catalog_number|content_sha256>... [--record-use] [--session NAME] --json

Emits a deterministic JSON manifest for the downstream sample-pack builder (`lsmp`): the full
asset + musical metadata for each requested keeper, EXCLUDING the raw 512-float `vector`. When
`--record-use` is set it also appends `action='use'` (weight `+5.0`) to `interaction_log` for
every exported asset — closing the ADJ flywheel whenever `lsmp` pulls an archive keeper into a
sample pack.

DOWNSTREAM CONTRACT (verified against the built `lsmp`, `src/pack.rs::resolve_larc_source`):
`lsmp add --from-larc <catalog_number>` shells out to
    `larc export <catalog_number> --record-use --json`
and reads a **top-level `path`** string from stdout (falling back to `audio`, then `file`). The
spec's Unit-04 envelope nests `path` inside `assets[]`, which that consumer would not find — so
this emitter carries BOTH: the full `assets[]` envelope AND the top-level `path`/`audio`/`file`
aliases (the first asset's path). No change is required in the built consumer.

Exit codes:
  0  success
  4  a requested reference is missing (`not_in_assets`) or its `path` is gone from disk
     (`path_missing_on_disk`) — a structured JSON error naming the missing asset(s) on stderr.
"""
import os, sys, json, sqlite3, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import actlog

SCHEMA_VERSION = 2

# Fields emitted per asset, in the Unit-04 contract's order. The raw `vector` (512-float JSON
# text) is deliberately excluded.
ASSET_FIELDS = [
    "content_sha256", "catalog_number", "path", "filename", "scope",
    "sample_role", "category", "duration_s", "samplerate", "channels",
    "peak_dbfs", "rms_dbfs", "root_note", "f0_hz", "pitch_confidence",
    "bpm", "bpm_confidence", "bars", "key",
    "source", "source_id", "creator", "license",
]


def db_path(a):
    return getattr(a, "db", None) or os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db")


def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _fail(missing, db):
    """Structured JSON error (stderr) + exit 4, naming every asset that could not be resolved."""
    err = {
        "error": "missing_asset",
        "exit_code": 4,
        "db": os.path.abspath(db),
        "message": "export aborted: %d requested asset(s) could not be resolved" % len(missing),
        "missing": missing,
    }
    sys.stderr.write(json.dumps(err, indent=2) + "\n")
    sys.exit(4)


def _asset_dict(row):
    keys = row.keys()
    return {k: (row[k] if k in keys else None) for k in ASSET_FIELDS}


def main():
    ap = argparse.ArgumentParser(prog="larc export",
                                 description="Emit the lsmp handoff descriptor for catalog number(s) / content hashes.")
    ap.add_argument("references", nargs="+",
                    help="catalog_number (lufs-<8hex>) or full content_sha256")
    ap.add_argument("--record-use", action="store_true",
                    help="append action='use' (+5.0) to interaction_log for each exported asset")
    ap.add_argument("--session", default="default")
    ap.add_argument("--db")
    ap.add_argument("--json", action="store_true", help="emit JSON (export is JSON-only)")
    a = ap.parse_args()

    p = db_path(a)
    if not os.path.exists(p):
        sys.exit("no index at %s — run `larc ingest` first" % p)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row

    assets, missing = [], []
    for ref in a.references:
        row = con.execute("SELECT * FROM assets WHERE catalog_number=? OR content_sha256=? LIMIT 1",
                          (ref, ref)).fetchone()
        if row is None:
            missing.append({"reference": ref, "reason": "not_in_assets"})
            continue
        path = row["path"]
        if not path or not os.path.exists(path):
            missing.append({"reference": ref, "catalog_number": row["catalog_number"],
                            "reason": "path_missing_on_disk", "path": path})
            continue
        assets.append(row)
    if missing:
        _fail(missing, p)

    # Record the flywheel write BEFORE emitting: one transaction for the whole batch, so a
    # crash mid-write never emits a manifest whose `use` was never logged.
    recorded = False
    if a.record_use:
        for row in assets:
            actlog.log_event(con, "use", row["content_sha256"], a.session, commit=False)
        con.commit()
        recorded = True

    out = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": _now(),
        "recorded_use": recorded,
        "assets": [_asset_dict(row) for row in assets],
    }
    # Top-level aliases the built `lsmp` reads (path, then audio, then file).
    out["path"] = out["assets"][0]["path"]
    out["audio"] = out["assets"][0]["path"]
    out["file"] = out["assets"][0]["path"]

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
