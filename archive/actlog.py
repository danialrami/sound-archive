#!/usr/bin/env python3
"""
actlog.py — the interaction log: the flywheel's irreplaceable asset. Every typed action
(star/use/played/skip/more_like_this) is an append-only row in interaction_log. In v0 the
log just retunes the transparent surface weights (down-rank surfaced-and-skipped; up-weight
starred clusters). A learned ranker comes later — the LOG is what makes that possible, so it
accrues from day one. Back it up religiously (KB 05-scope-tagging-and-backup); nothing
regenerates it.

  archive act <catalog_number> <star|use|played|skip|more_like_this> [--session S]
"""
import os, sys, json, sqlite3, argparse, datetime

WEIGHTS = {"star": 3.0, "use": 5.0, "played": 1.0, "skip": -1.0, "more_like_this": 0.0, "surfaced": 0.0}

def db_path(a):
    return getattr(a, "db", None) or os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db")

def _ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS interaction_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, action TEXT,
      content_sha256 TEXT, session TEXT, weight REAL)""")

def log_event(con, action, sha, session="default"):
    _ensure(con)
    con.execute("INSERT INTO interaction_log(ts,action,content_sha256,session,weight) VALUES(?,?,?,?,?)",
                (datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), action, sha, session,
                 WEIGHTS.get(action, 0.0)))
    con.commit()

def sha_for_catalog(con, cat):
    r = con.execute("SELECT content_sha256 FROM assets WHERE catalog_number=?", (cat,)).fetchone()
    return r[0] if r else None

def recent_stars(con, limit=5):
    _ensure(con)
    return [r[0] for r in con.execute(
        "SELECT content_sha256 FROM interaction_log WHERE action IN ('star','use','more_like_this') "
        "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

def recently_surfaced(con, limit=200):
    _ensure(con)
    return {r[0] for r in con.execute(
        "SELECT content_sha256 FROM interaction_log WHERE action='surfaced' ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()}

def skip_counts(con):
    _ensure(con)
    return {r[0]: r[1] for r in con.execute(
        "SELECT content_sha256, COUNT(*) FROM interaction_log WHERE action='skip' GROUP BY content_sha256").fetchall()}

def main():
    ap = argparse.ArgumentParser(prog="archive act")
    ap.add_argument("catalog"); ap.add_argument("action", choices=list(WEIGHTS))
    ap.add_argument("--session", default="default"); ap.add_argument("--db")
    a = ap.parse_args()
    con = sqlite3.connect(db_path(a))
    sha = sha_for_catalog(con, a.catalog)
    if not sha: sys.exit(f"no asset {a.catalog}")
    log_event(con, a.action, sha, a.session)
    print(f"logged {a.action} ({WEIGHTS[a.action]:+g}) for {a.catalog}")

if __name__ == "__main__": main()
