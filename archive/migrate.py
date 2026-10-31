#!/usr/bin/env python3
"""
migrate.py — idempotent, non-destructive schema migration for the sound-archive index.

v0 -> v2 adds the musical (sample_role, category, root_note, f0_hz, pitch_confidence,
bpm_confidence, bars) and provenance (source, source_id, creator, license) columns that the
downstream sample-pack builder (`lsmp`) needs, WITHOUT touching a single existing row:

  • a fresh / empty database is created from archive/schema.sql (the canonical v2 DDL);
  • an existing database only ever gets `ALTER TABLE assets ADD COLUMN ...` — every added
    column is nullable, so no row is rewritten and no data is lost;
  • re-running is a no-op that reports `already_migrated: true`.

`PRAGMA user_version` is set to 2 so callers can detect the schema level.

  larc migrate [--db PATH] [--json]
"""
import os, re, sys, json, sqlite3, argparse

SCHEMA_VERSION = 2
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_SQL = os.path.join(HERE, "schema.sql")

# The v2 additions. `decl` is the full SQLite column definition used by ALTER TABLE; the
# CHECK clauses are byte-identical to those in archive/schema.sql so a migrated index and a
# freshly-created one enforce the same conventions.
_ROOT_NOTE_CHECK = ("CHECK (root_note IS NULL"
                    " OR root_note GLOB '[a-g][0-9]'"
                    " OR root_note GLOB '[a-g][#b][0-9]'"
                    " OR root_note GLOB '[a-g]-[0-9]'"
                    " OR root_note GLOB '[a-g][#b]-[0-9]')")
_ROLE_CHECK = ("CHECK (sample_role IS NULL"
               " OR sample_role IN ('one_shot','loop','stem','take'))")

NEW_COLUMNS = [
    ("sample_role",      "TEXT " + _ROLE_CHECK),
    ("category",         "TEXT"),
    ("root_note",        "TEXT " + _ROOT_NOTE_CHECK),
    ("f0_hz",            "REAL"),
    ("pitch_confidence", "REAL"),
    ("bpm_confidence",   "REAL"),
    ("bars",             "INTEGER"),
    ("source",           "TEXT"),
    ("source_id",        "TEXT"),
    ("creator",          "TEXT"),
    ("license",          "TEXT"),
]

# ── convention validators (used by tests / callers; the DB CHECKs enforce the same rules) ──
ROOT_NOTE_RE = re.compile(r"^[a-g](#|b)?-?[0-9]$")
VALID_ROLES = ("one_shot", "loop", "stem", "take")


def validate_root_note(note):
    """True if `note` is NULL or lowercase scientific pitch notation (e.g. e1, c4, f#3)."""
    return note is None or bool(ROOT_NOTE_RE.match(note))


def validate_sample_role(role):
    """True if `role` is NULL or one of one_shot | loop | stem | take."""
    return role is None or role in VALID_ROLES


def db_path(a):
    return getattr(a, "db", None) or os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db")


def _assets_exists(cur):
    return cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assets'").fetchone() is not None


def migrate(db, verbose=True):
    """Bring `db` to schema v2. Returns a result dict. Non-destructive + idempotent."""
    con = sqlite3.connect(db)
    try:
        cur = con.cursor()
        prior = cur.execute("PRAGMA user_version").fetchone()[0]
        added = []
        if not _assets_exists(cur):
            # fresh/empty db: create the canonical v2 schema (table + indexes + side tables)
            with open(SCHEMA_SQL) as fh:
                con.executescript(fh.read())
        else:
            # existing db: add only the columns that are missing. ALTER TABLE ADD COLUMN is
            # additive and never rewrites the table — existing rows keep every value.
            cols = {r[1] for r in cur.execute("PRAGMA table_info(assets)").fetchall()}
            for name, decl in NEW_COLUMNS:
                if name not in cols:
                    con.execute("ALTER TABLE assets ADD COLUMN %s %s" % (name, decl))
                    added.append(name)
            # now (re)apply schema.sql: CREATE ... IF NOT EXISTS creates the v2 indexes and any
            # missing side tables, and is a no-op on everything already present.
            with open(SCHEMA_SQL) as fh:
                con.executescript(fh.read())
        cur.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
        con.commit()
        already = (prior == SCHEMA_VERSION and not added)
        return {
            "db": os.path.abspath(db),
            "schema_version": SCHEMA_VERSION,
            "already_migrated": already,
            "added_columns": added,
            "prior_user_version": prior,
        }
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser(prog="larc migrate",
                                 description="Idempotent, non-destructive schema migration (v0 -> v2).")
    ap.add_argument("--db", default=None,
                    help="index sqlite db (default: $ARCHIVE_DB or ~/.sound-archive/archive.db)")
    ap.add_argument("--json", action="store_true", help="emit the migration result as JSON")
    a = ap.parse_args()
    p = db_path(a)
    if not os.path.exists(p):
        sys.exit("no index at %s — nothing to migrate (run `larc ingest` first)" % p)
    res = migrate(p)
    if a.json:
        print(json.dumps(res, indent=2))
        return
    if res["already_migrated"]:
        print("migrate: %s already at schema v%d (no changes)" % (res["db"], res["schema_version"]))
    else:
        print("migrate: %s -> schema v%d (added: %s)"
              % (res["db"], res["schema_version"], ", ".join(res["added_columns"]) or "none"))


if __name__ == "__main__":
    main()
