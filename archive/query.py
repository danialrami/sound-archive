#!/usr/bin/env python3
"""
query.py — the read side of the sound archive: query the index the batch/incremental
archive-ingest chain produced. Brute-force cosine KNN over the stored vectors (fine to
~10^5-10^6 for a single user); the production store swaps this for a sqlite-vec vec0
virtual table with the identical schema — only the ANN mechanism changes.

Subcommands:
  stats                      counts by scope + embed model
  list  [--scope] [--limit]  newest-first listing
  filter --bright-min .. --bright-max .. --dur-min .. --dur-max .. --scope ..
  like  <catalog_number> [--k 5] [--scope archive]   "more like this" (cosine NN)
  text  "<words>" [--k 5]     text->audio query (CLAP only; melstats gives an honest
                              feature-heuristic fallback and says so)
All commands take --db PATH (or $ARCHIVE_DB, or ~/.sound-archive/archive.db) and --json.
"""
import os, sys, json, sqlite3, argparse, math

def db_path(a):
    return a.db or os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db")

def connect(a):
    p = db_path(a)
    if not os.path.exists(p):
        sys.exit(f"no index at {p} — run `archive ingest <scope-root>` first")
    c = sqlite3.connect(p); c.row_factory = sqlite3.Row; return c

def _vec(row):
    v = row["vector"]
    return json.loads(v) if v else []

def cosine(a, b):
    if not a or not b or len(a) != len(b): return -1.0
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return dot/(na*nb) if na and nb else -1.0

def _emit(rows, a, extra=None):
    if a.json:
        print(json.dumps(rows, indent=2)); return
    if not rows: print("(no matches)"); return
    for i, r in enumerate(rows):
        sim = f"  sim={r['_sim']:.3f}" if "_sim" in r else ""
        print(f"{r.get('catalog_number'):<14} {(r.get('filename') or '')[:34]:<34} "
              f"{r.get('scope'):<9} {r.get('duration_s')}s  bright={r.get('brightness')}"
              f"  centroid={r.get('spectral_centroid_hz')}Hz{sim}")

def _breakdown(c, col):
    """{value: count} for a column, or {} if the column isn't present (pre-v2 index)."""
    try:
        return {r[col]: r["n"] for r in c.execute(
            "SELECT %s,COUNT(*) n FROM assets GROUP BY %s" % (col, col)).fetchall()}
    except sqlite3.OperationalError:
        return {}

def cmd_stats(a):
    c = connect(a)
    tot = c.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    byscope = c.execute("SELECT scope,COUNT(*) n FROM assets GROUP BY scope").fetchall()
    bymodel = c.execute("SELECT embed_model,COUNT(*) n FROM assets GROUP BY embed_model").fetchall()
    out = {"db": db_path(a), "total": tot,
           "by_scope": {r["scope"]: r["n"] for r in byscope},
           "by_model": {r["embed_model"]: r["n"] for r in bymodel},
           "by_role": _breakdown(c, "sample_role"),
           "by_category": _breakdown(c, "category"),
           "by_license": _breakdown(c, "license")}
    print(json.dumps(out, indent=2) if a.json else
          f"index: {out['db']}\n  total: {tot}\n  by scope: {out['by_scope']}\n  by model: {out['by_model']}\n"
          f"  by role: {out['by_role']}\n  by category: {out['by_category']}\n  by license: {out['by_license']}")

def cmd_list(a):
    c = connect(a); q = "SELECT * FROM assets"; p = []
    if a.scope: q += " WHERE scope=?"; p.append(a.scope)
    q += " ORDER BY indexed_at DESC LIMIT ?"; p.append(a.limit)
    _emit([dict(r) for r in c.execute(q, p).fetchall()], a)

def cmd_filter(a):
    c = connect(a); q = "SELECT * FROM assets WHERE 1=1"; p = []
    if a.scope: q += " AND scope=?"; p.append(a.scope)
    if a.bright_min is not None: q += " AND brightness>=?"; p.append(a.bright_min)
    if a.bright_max is not None: q += " AND brightness<=?"; p.append(a.bright_max)
    if a.dur_min is not None: q += " AND duration_s>=?"; p.append(a.dur_min)
    if a.dur_max is not None: q += " AND duration_s<=?"; p.append(a.dur_max)
    # v2 musical / provenance filters (all parameterized)
    if a.role: q += " AND sample_role=?"; p.append(a.role)
    if a.category: q += " AND category=?"; p.append(a.category)
    if a.root_note: q += " AND root_note=?"; p.append(a.root_note)
    if a.key: q += " AND key=?"; p.append(a.key)
    if a.bpm_min is not None: q += " AND bpm>=?"; p.append(a.bpm_min)
    if a.bpm_max is not None: q += " AND bpm<=?"; p.append(a.bpm_max)
    if a.pitch_conf_min is not None: q += " AND pitch_confidence>=?"; p.append(a.pitch_conf_min)
    if a.source: q += " AND source=?"; p.append(a.source)
    if a.license: q += " AND license=?"; p.append(a.license)
    q += " ORDER BY brightness LIMIT ?"; p.append(a.limit)
    _emit([dict(r) for r in c.execute(q, p).fetchall()], a)

def cmd_like(a):
    c = connect(a)
    seed = c.execute("SELECT * FROM assets WHERE catalog_number=?", (a.catalog,)).fetchone()
    if not seed: sys.exit(f"no asset {a.catalog}")
    sv = _vec(seed)
    rows = []
    for r in c.execute("SELECT * FROM assets").fetchall():
        if r["catalog_number"] == a.catalog: continue
        if a.scope and r["scope"] != a.scope: continue
        d = dict(r); d["_sim"] = cosine(sv, _vec(r)); d.pop("vector", None); rows.append(d)
    rows.sort(key=lambda x: x["_sim"], reverse=True)
    print(f"# more like {a.catalog} ({seed['filename']}):" if not a.json else "", end="" if a.json else "\n")
    _emit(rows[:a.k], a)

def cmd_text(a):
    c = connect(a)
    models = {r["embed_model"] for r in c.execute("SELECT DISTINCT embed_model FROM assets").fetchall()}
    if models and all(m and m.startswith(("laion-clap", "muq")) for m in models):
        sys.exit("text->CLAP encoding not wired in this stub; prod path: encode query with the "
                 "CLAP text tower, cosine over the vec0 index.")
    # Honest melstats fallback: map a few adjectives to the deterministic feature axes.
    words = a.query.lower()
    q = "SELECT * FROM assets WHERE 1=1"; p = []
    if "dark" in words or "low" in words: q += " AND brightness<=0.15"
    if "bright" in words or "metallic" in words or "airy" in words: q += " AND brightness>=0.4"
    if "short" in words: q += " AND duration_s<=3"
    if "long" in words or "drone" in words: q += " AND duration_s>=5"
    q += " ORDER BY brightness LIMIT ?"; p.append(a.k)
    print(f"# text query '{a.query}' — NOTE: melstats-v0 has no text tower; this is an honest "
          f"feature-heuristic fallback. Real text->audio needs the CLAP/MuQ text encoder.")
    _emit([dict(r) for r in c.execute(q, p).fetchall()], a)

def _common(sp):
    """Let --db / --json be given after the subcommand too (e.g. `query stats --json`).
    default=SUPPRESS is essential: a subparser parses into a fresh namespace and copies it
    back, so a normal default here would clobber a --db/--json given BEFORE the subcommand."""
    sp.add_argument("--db", default=argparse.SUPPRESS)
    sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return sp

def main():
    ap = argparse.ArgumentParser(prog="larc query")
    ap.add_argument("--db"); ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    _common(sub.add_parser("stats"))
    l = _common(sub.add_parser("list")); l.add_argument("--scope"); l.add_argument("--limit", type=int, default=20)
    f = _common(sub.add_parser("filter"))
    for name in ("bright-min","bright-max","dur-min","dur-max","bpm-min","bpm-max","pitch-conf-min"):
        f.add_argument("--"+name, dest=name.replace("-","_"), type=float)
    f.add_argument("--role"); f.add_argument("--category"); f.add_argument("--root-note")
    f.add_argument("--key"); f.add_argument("--source"); f.add_argument("--license")
    f.add_argument("--scope"); f.add_argument("--limit", type=int, default=20)
    lk = _common(sub.add_parser("like")); lk.add_argument("catalog"); lk.add_argument("--k", type=int, default=5); lk.add_argument("--scope")
    t = _common(sub.add_parser("text")); t.add_argument("query"); t.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    {"stats":cmd_stats,"list":cmd_list,"filter":cmd_filter,"like":cmd_like,"text":cmd_text}[a.cmd](a)

if __name__ == "__main__":
    main()
