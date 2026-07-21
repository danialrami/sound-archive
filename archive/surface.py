#!/usr/bin/env python3
"""
surface.py — the ADJ front door: assemble ~9 candidates for a morning session by a
TRANSPARENT weighted blend (no learned model in v0):

  • temporal   — a couple most-recent, plus one "on-this-week, past years"
  • relevance  — nearest neighbours (cosine) of what you starred/used last session
  • novelty    — from a cluster/folder you haven't touched lately (cold storage)
  • wildcard   — pure random, for serendipity

Every returned item is logged as `surfaced` so novelty can avoid repeats, and the blend is
retuned by the interaction log (down-rank things surfaced-and-skipped 3+ times). Scope is
gated to `archive` by default — `reference` never enters the inspiration stream unless asked.

  archive surface [--k 9] [--session S] [--scope archive] [--json]
"""
import os, sys, json, sqlite3, argparse, math, random, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actlog
import points as _points

def db_path(a): return a.db or os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db")
def cosine(a,b):
    if not a or not b or len(a)!=len(b): return -1.0
    d=sum(x*y for x,y in zip(a,b)); na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(y*y for y in b))
    return d/(na*nb) if na and nb else -1.0

def surface(con, k=9, session="default", scope="archive"):
    con.row_factory=sqlite3.Row
    pool=[dict(r) for r in con.execute("SELECT * FROM assets WHERE scope=?", (scope,)).fetchall()]
    if not pool: return []
    by_sha={r["content_sha256"]: r for r in pool}
    cmap=_points.cluster_map(con)
    seen=actlog.recently_surfaced(con, 200)
    skips=actlog.skip_counts(con)
    stars=actlog.recent_stars(con, 5)
    picked, reasons = [], {}
    def take(sha, why):
        if sha and sha in by_sha and sha not in reasons:
            reasons[sha]=why; picked.append(sha)
    # cold-first ordering: penalize recently-surfaced and repeatedly-skipped
    def cold_key(r):
        s=r["content_sha256"]
        return (s in seen, skips.get(s,0), random.random())
    cold=sorted(pool, key=cold_key)
    # 1) temporal — most recent by indexed_at
    for r in sorted(pool, key=lambda r: r["indexed_at"] or "", reverse=True)[:2]:
        take(r["content_sha256"], "temporal:recent")
    # 2) temporal — on-this-week, past years (same ISO week, older year)
    now=datetime.datetime.utcnow(); wk=now.isocalendar()[1]
    for r in pool:
        ia=r.get("indexed_at") or ""
        try: d=datetime.datetime.strptime(ia[:10], "%Y-%m-%d")
        except Exception: continue
        if d.isocalendar()[1]==wk and d.year<now.year:
            take(r["content_sha256"], "temporal:on-this-week"); break
    # 3) relevance — neighbours of recent stars
    for seed in stars:
        sv=json.loads(by_sha[seed]["vector"]) if seed in by_sha and by_sha[seed]["vector"] else None
        if not sv: continue
        nbrs=sorted((r for r in pool if r["content_sha256"]!=seed),
                    key=lambda r: cosine(sv, json.loads(r["vector"] or "[]")), reverse=True)
        for r in nbrs[:2]: take(r["content_sha256"], "relevance:like-starred")
        if len([1 for w in reasons.values() if w.startswith("relevance")])>=2: break
    # 4) novelty — coldest clusters
    for r in cold:
        if len(picked)>=k-1: break
        take(r["content_sha256"], "novelty:cold")
    # 5) wildcard — pure random to fill
    rest=[r["content_sha256"] for r in pool if r["content_sha256"] not in reasons]
    random.shuffle(rest)
    for s in rest:
        if len(picked)>=k: break
        take(s, "wildcard")
    out=[]
    for s in picked[:k]:
        r=by_sha[s]
        out.append({"catalog_number":r["catalog_number"],"filename":r["filename"],
                    "scope":r["scope"],"duration_s":r["duration_s"],"brightness":r["brightness"],
                    "spectral_centroid_hz":r["spectral_centroid_hz"],"cluster":cmap.get(s),
                    "hook":"/hook/%s"%r["catalog_number"],"waveform":"/waveform/%s"%r["catalog_number"],
                    "hook_path":r["hook_path"],"waveform_path":r["waveform_path"],"why":reasons[s]})
        actlog.log_event(con, "surfaced", s, session)
    return out

def main():
    ap=argparse.ArgumentParser(prog="archive surface")
    ap.add_argument("--k", type=int, default=9); ap.add_argument("--session", default="default")
    ap.add_argument("--scope", default="archive"); ap.add_argument("--db"); ap.add_argument("--json", action="store_true")
    a=ap.parse_args()
    p=db_path(a)
    if not os.path.exists(p): sys.exit(f"no index at {p} — ingest first")
    con=sqlite3.connect(p)
    rows=surface(con, a.k, a.session, a.scope)
    if a.json: print(json.dumps(rows, indent=2)); return
    print(f"# morning surface — {len(rows)} candidates (session={a.session}, scope={a.scope})")
    for r in rows:
        print(f"  {r['catalog_number']:<14} {(r['filename'] or '')[:30]:<30} {r['duration_s']}s "
              f"bright={r['brightness']:<7} [{r['why']}]")
    print("\n# audition hooks, then: archive act <catalog> <star|use|played|skip|more_like_this>")

if __name__ == "__main__": main()
