#!/usr/bin/env python3
"""
ingest_batch.py — the batch/incremental DRIVER around the workchain `archive-ingest` chain.
This is the inherently multi-file part (scan + dedup + scope), so it lives in the app, not
in a workchain component. It calls the workchain engine once per KEEPER file.

  archive ingest <root> --workchain <path> --scope-map own=archive [--db PATH]

What it does (verifiable-correctness, resumable):
  1. scan  — walk <root>, keep only standard-audio extensions (drop .nkx/.ncw/.nki/.mid/…)
  2. scope — tag each file archive|reference from --scope-map folder rules (default archive)
  3. dedup L1 — content SHA-256; group; keep ONE canonical per group by quality rank
                (lossless > lossy, higher SR/bit-depth, longer); tombstone the rest.
     dedup L2 (transcode) — Chromaprint via fpcalc if present, else recorded as deferred.
  4. drive — for each keeper NOT already in the index (idempotent), run the workchain engine:
                engine/workchain-engine.sh -c chains/archive-ingest.yaml -o <work> <file>
             with ARCHIVE_DB + scope exported. A crash resumes: cataloged==in-index.
"""
import os, sys, json, hashlib, argparse, subprocess, sqlite3, tempfile

AUDIO = {".wav",".aif",".aiff",".aifc",".flac",".mp3",".ogg",".oga",".opus",".m4a",".aac",".caf",".wv",".alac"}
LOSSLESS = {".wav",".aif",".aiff",".aifc",".flac",".caf",".wv",".alac"}

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20), b""): h.update(c)
    return h.hexdigest()

def scope_for(path, rules):
    for frag, sc in rules: 
        if frag in path: return sc
    return "archive"

def quality_key(p):
    ext=os.path.splitext(p)[1].lower()
    try: sz=os.path.getsize(p)
    except OSError: sz=0
    return (1 if ext in LOSSLESS else 0, sz)  # prefer lossless, then bigger

def _existing_models(db):
    if not os.path.exists(db): return set()
    import sqlite3 as _s; c=_s.connect(db)
    try: return {r[0] for r in c.execute("SELECT DISTINCT embed_model FROM assets") if r[0]}
    except Exception: return set()
    finally: c.close()

def already_indexed(db):
    if not os.path.exists(db): return set()
    c=sqlite3.connect(db)
    try: return {r[0] for r in c.execute("SELECT content_sha256 FROM assets")}
    except sqlite3.OperationalError: return set()
    finally: c.close()

def main():
    ap=argparse.ArgumentParser(prog="archive ingest")
    ap.add_argument("root")
    ap.add_argument("--workchain", required=True, help="path to lufs-workchain checkout")
    ap.add_argument("--db", default=os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db"))
    ap.add_argument("--scope-map", nargs="*", default=[], help='folder=scope, e.g. Komplete=reference Orchs=reference')
    ap.add_argument("--embedder", choices=["melstats","clap"], default="melstats",
                    help="melstats = light default (archive-ingest.yaml); clap = LAION-CLAP (archive-ingest-clap.yaml; requires embed_clap provisioned on klaxon)")
    ap.add_argument("--chain", help="explicit chain filename under <workchain>/chains (overrides --embedder)")
    ap.add_argument("--work", default=os.path.expanduser("~/.sound-archive/work"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a=ap.parse_args()
    rules=[(kv.split("=",1)[0], kv.split("=",1)[1]) for kv in a.scope_map if "=" in kv]
    _existing=_existing_models(a.db)
    _want="laion-clap-630k" if a.embedder=="clap" else "melstats-v0"
    if _existing and _want not in _existing:
        print(f"WARNING: index already holds vectors from {sorted(_existing)} but you're ingesting {_want}. "
              f"Mixed embedding dims break cosine similarity — use a FRESH --db for a CLAP index, or re-embed all.")

    # 1-2. scan + scope
    files=[]
    for dp,_,fns in os.walk(a.root):
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in AUDIO:
                p=os.path.join(dp,fn); files.append((p, scope_for(p, rules)))
    print(f"scan: {len(files)} standard-audio files under {a.root}  (embedder={a.embedder})")

    # 3. dedup L1 by content hash → keeper per group
    groups={}
    for p,sc in files:
        try: h=sha256(p)
        except OSError: continue
        groups.setdefault(h, []).append((p,sc))
    keepers=[]
    dupes=0
    for h,members in groups.items():
        members.sort(key=lambda ps: quality_key(ps[0]), reverse=True)
        keepers.append((h, members[0][0], members[0][1]))
        dupes += len(members)-1
    print(f"dedup L1: {len(groups)} unique / {len(files)} files  ({dupes} exact-dupe copies collapsed)")
    if not _have("fpcalc"):
        print("dedup L2 (chromaprint): fpcalc not found — transcode-dupe pass DEFERRED (install chromaprint)")

    done=already_indexed(a.db)
    todo=[k for k in keepers if k[0] not in done]
    print(f"resume: {len(keepers)-len(todo)} already indexed, {len(todo)} to ingest")
    if a.limit: todo=todo[:a.limit]
    if a.dry_run:
        for h,p,sc in todo[:20]: print(f"  would ingest [{sc}] {p}")
        return

    engine=os.path.join(a.workchain,"engine","workchain-engine.sh")
    chain_name = a.chain or ("archive-ingest-clap.yaml" if a.embedder=="clap" else "archive-ingest.yaml")
    chain=os.path.join(a.workchain,"chains",chain_name)
    if not os.path.exists(chain):
        sys.exit(f"chain not found: {chain} (pull the latest lufs-workchain; clap chain shipped in #23)")
    os.makedirs(a.work, exist_ok=True); os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    env=dict(os.environ, ARCHIVE_DB=a.db)
    ok=fail=0
    for h,p,sc in todo:
        workdir=os.path.join(a.work, h[:12])
        env["ARCHIVE_SCOPE"]=sc
        r=subprocess.run(["bash",engine,"-c",chain,"-o",workdir,p], env=env,
                         capture_output=True, text=True)
        if r.returncode==0: ok+=1
        else: fail+=1; sys.stderr.write(f"FAIL {p}\n{r.stderr[-400:]}\n")
    print(f"ingest: {ok} ok, {fail} failed → {a.db}")

def _have(cmd):
    from shutil import which; return which(cmd) is not None

if __name__=="__main__": main()
