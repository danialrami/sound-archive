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

OBSERVABILITY (this used to be the weak point, badly):
  The per-file loop ran the engine with capture_output=True and DISCARDED the result unless
  the step failed. So a multi-day run over 259k files printed four summary lines and then
  went completely silent — every per-step log the engine already emits was captured and
  thrown away. The hashing pass was worse: a full 337 GB read with no output at all.

  Now: every phase reports progress with a rate and an ETA, every file gets a line saying
  what is being done to it and how long it took, and the whole run is mirrored to a run log
  under ~/.workchain/runs (newest 25 kept, older ones autocleaned).

  The run log is opened HERE and exported as $WORKCHAIN_RUNLOG, so all N engine invocations
  append to that ONE file instead of opening N logs that would evict each other instantly.
  The engine's own log_* lines land in it directly — we do not re-print captured stdout,
  which would double every line.
"""
import os, sys, json, hashlib, argparse, subprocess, sqlite3, tempfile, time, datetime

AUDIO = {".wav",".aif",".aiff",".aifc",".flac",".mp3",".ogg",".oga",".opus",".m4a",".aac",".caf",".wv",".alac"}
LOSSLESS = {".wav",".aif",".aiff",".aifc",".flac",".caf",".wv",".alac"}

QUIET = False
_RUNLOG = None


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────

def _iso():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def say(msg, level="INFO", console=True):
    """Print to the console and mirror to the run log, in the SAME line format the bash
    side uses (`ISO LEVEL message`) so one run log reads as a single coherent stream."""
    if console and not (QUIET and level == "INFO"):
        print(msg, flush=True)
    if _RUNLOG:
        try:
            with open(_RUNLOG, "a") as f:
                f.write("%s %-5s %s\n" % (_iso(), level, msg))
        except OSError:
            pass


def warn(msg):
    say(msg, "WARN")


def err(msg):
    if not QUIET:
        sys.stderr.write(msg + "\n")
    if _RUNLOG:
        try:
            with open(_RUNLOG, "a") as f:
                f.write("%s %-5s %s\n" % (_iso(), "ERROR", msg))
        except OSError:
            pass


def human_bytes(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return "%.1f%s" % (n, u)
        n /= 1024.0


def human_dur(s):
    s = int(max(0, s))
    if s < 60:
        return "%ds" % s
    if s < 3600:
        return "%dm%02ds" % (s // 60, s % 60)
    return "%dh%02dm" % (s // 3600, (s % 3600) // 60)


class Progress:
    """Rate + ETA reporter. Emits at most every `every_s` seconds or `every_n` items, so
    a 259k-file pass is legible without becoming its own bottleneck."""

    def __init__(self, total, label, every_n=2000, every_s=5.0, unit="files"):
        self.total, self.label = total, label
        self.every_n, self.every_s, self.unit = every_n, every_s, unit
        self.t0 = self.last_t = time.time()
        self.n = self.last_n = 0
        self.bytes = 0

    def tick(self, inc=1, nbytes=0):
        self.n += inc
        self.bytes += nbytes
        now = time.time()
        if (self.n - self.last_n) >= self.every_n or (now - self.last_t) >= self.every_s:
            self.emit()
            self.last_n, self.last_t = self.n, now

    def emit(self, final=False):
        el = max(1e-9, time.time() - self.t0)
        rate = self.n / el
        pct = (100.0 * self.n / self.total) if self.total else 0.0
        eta = ((self.total - self.n) / rate) if (rate > 0 and self.total) else 0
        extra = ""
        if self.bytes:
            extra = "  %s at %s/s" % (human_bytes(self.bytes), human_bytes(self.bytes / el))
        tail = "elapsed %s" % human_dur(el) if final else "eta %s" % human_dur(eta)
        say("  %s: %d/%d %s (%.1f%%)  %.0f %s/s%s  %s"
            % (self.label, self.n, self.total, self.unit, pct, rate, self.unit, extra, tail))


# ─────────────────────────────────────────────────────────────────────────────
# Core (unchanged logic)
# ─────────────────────────────────────────────────────────────────────────────

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

def _have(cmd):
    from shutil import which; return which(cmd) is not None


def open_runlog(workchain, label, meta):
    """Open the batch run log via the workchain's single implementation and export it so
    every engine invocation appends to it. Fail-soft and loud: an older workchain checkout
    without lib/workchain_runlog.py must not stop an ingest."""
    global _RUNLOG
    try:
        libdir = os.path.join(workchain, "lib")
        if libdir not in sys.path:
            sys.path.insert(0, libdir)
        import workchain_runlog as rl
        path, pruned = rl.open_run(label, meta=meta)
        _RUNLOG = path
        os.environ["WORKCHAIN_RUNLOG"] = path
        return path, pruned, rl.default_keep()
    except Exception as e:
        sys.stderr.write("NOTE: run logging unavailable (%s) — continuing without it. "
                         "Update the lufs-workchain checkout for run logs.\n" % e)
        return None, [], 0


# ─────────────────────────────────────────────────────────────────────────────

def main():
    global QUIET
    ap=argparse.ArgumentParser(prog="archive ingest")
    ap.add_argument("root")
    ap.add_argument("--workchain", required=True, help="path to lufs-workchain checkout")
    ap.add_argument("--db", default=os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db"))
    ap.add_argument("--scope-map", nargs="*", default=[], help='folder=scope, e.g. Komplete=reference Orchs=reference')
    ap.add_argument("--embedder", choices=["melstats","clap","clap-remote"], default="melstats",
                    help="melstats = light default (archive-ingest.yaml); clap = LAION-CLAP in-process, reloads the ~2GB checkpoint PER FILE (archive-ingest-clap.yaml); clap-remote = LAION-CLAP on a resident-model serve-embed endpoint, no local venv needed (archive-ingest-clap-remote.yaml) — use this one at library scale")
    ap.add_argument("--chain", help="explicit chain filename under <workchain>/chains (overrides --embedder)")
    ap.add_argument("--work", default=os.path.expanduser("~/.sound-archive/work"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress per-file console lines (the run log still records everything)")
    ap.add_argument("--progress-every", type=int, default=2000,
                    help="emit a scan/hash progress line every N files (default 2000)")
    a=ap.parse_args()
    QUIET = a.quiet
    rules=[(kv.split("=",1)[0], kv.split("=",1)[1]) for kv in a.scope_map if "=" in kv]

    chain_name = a.chain or {"clap":"archive-ingest-clap.yaml",
                             "clap-remote":"archive-ingest-clap-remote.yaml"}.get(a.embedder,
                                                                                  "archive-ingest.yaml")
    endpoint = os.environ.get("EMBED_CLAP_ENDPOINT", "")
    meta = {"root": a.root, "db": a.db, "chain": chain_name, "embedder": a.embedder,
            "work": a.work, "scope_map": " ".join(a.scope_map) or "(none)"}
    if a.embedder == "clap-remote":
        meta["endpoint"] = endpoint or "(unset — $EMBED_CLAP_ENDPOINT)"
    t_run0 = time.time()
    logpath, pruned, keep = open_runlog(a.workchain, "archive-ingest", meta)

    say("=== archive ingest ===  %s" % _iso())
    say("  root     : %s" % a.root)
    say("  chain    : %s  (embedder=%s)" % (chain_name, a.embedder))
    say("  db       : %s" % a.db)
    if a.embedder == "clap-remote":
        say("  endpoint : %s" % (endpoint or "(unset — set $EMBED_CLAP_ENDPOINT)"))
    if logpath:
        say("  run log  : %s" % logpath)
        if pruned:
            say("  autoclean: removed %d old run log(s), keeping newest %d" % (len(pruned), keep))

    if a.embedder == "clap-remote" and not endpoint:
        warn("clap-remote selected but $EMBED_CLAP_ENDPOINT is not set — the chain will fail "
             "honestly on the first file rather than silently taking the slow local path. "
             "Export it (e.g. http://127.0.0.1:8770) and re-run.")

    _existing=_existing_models(a.db)
    _want="laion-clap-630k" if a.embedder in ("clap","clap-remote") else "melstats-v0"
    if _existing and _want not in _existing:
        warn(f"WARNING: index already holds vectors from {sorted(_existing)} but you're ingesting {_want}. "
             f"Mixed embedding dims break cosine similarity — use a FRESH --db for a CLAP index, or re-embed all.")

    # 1-2. scan + scope
    say("[1/4] scan: walking %s" % a.root)
    files=[]
    t0=time.time()
    seen=0
    for dp,_,fns in os.walk(a.root):
        for fn in fns:
            seen+=1
            if os.path.splitext(fn)[1].lower() in AUDIO:
                p=os.path.join(dp,fn); files.append((p, scope_for(p, rules)))
        if seen and seen % (a.progress_every*5) == 0:
            say("  scan: %d entries seen, %d audio files so far (%s)"
                % (seen, len(files), human_dur(time.time()-t0)))
    say("scan: %d standard-audio files under %s  (from %d entries, %s)"
        % (len(files), a.root, seen, human_dur(time.time()-t0)))
    if not files:
        say("nothing to do — no standard-audio files found")
        return

    # 3. dedup L1 by content hash → keeper per group
    #    This is the slow, previously-silent phase: it reads every byte of the library.
    say("[2/4] dedup L1: hashing %d files (reads every byte — this is the resume cost)" % len(files))
    groups={}
    prog=Progress(len(files), "hash", every_n=a.progress_every)
    skipped=0
    for p,sc in files:
        try:
            sz=os.path.getsize(p)
        except OSError:
            sz=0
        try:
            h=sha256(p)
        except OSError as e:
            skipped+=1
            err("SKIP unreadable: %s (%s)" % (p, e))
            continue
        groups.setdefault(h, []).append((p,sc))
        prog.tick(1, sz)
    prog.emit(final=True)
    keepers=[]
    dupes=0
    for h,members in groups.items():
        members.sort(key=lambda ps: quality_key(ps[0]), reverse=True)
        keepers.append((h, members[0][0], members[0][1]))
        dupes += len(members)-1
    say("dedup L1: %d unique / %d files  (%d exact-dupe copies collapsed%s)"
        % (len(groups), len(files), dupes, ", %d unreadable skipped" % skipped if skipped else ""))
    if not _have("fpcalc"):
        say("dedup L2 (chromaprint): fpcalc not found — transcode-dupe pass DEFERRED (install chromaprint)")

    done=already_indexed(a.db)
    todo=[k for k in keepers if k[0] not in done]
    say("[3/4] resume: %d already indexed, %d to ingest" % (len(keepers)-len(todo), len(todo)))
    if a.limit:
        todo=todo[:a.limit]
        say("  --limit %d applied → %d this run" % (a.limit, len(todo)))
    if a.dry_run:
        say("dry run — would ingest:")
        for h,p,sc in todo[:20]: say(f"  would ingest [{sc}] {p}")
        if len(todo)>20: say("  … and %d more" % (len(todo)-20))
        return
    if not todo:
        say("nothing to ingest — the index is already current for this root")
        return

    engine=os.path.join(a.workchain,"engine","workchain-engine.sh")
    chain=os.path.join(a.workchain,"chains",chain_name)
    if not os.path.exists(chain):
        sys.exit(f"chain not found: {chain} (pull the latest lufs-workchain; the clap-remote chain shipped in #27)")
    os.makedirs(a.work, exist_ok=True); os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    env=dict(os.environ, ARCHIVE_DB=a.db)
    if _RUNLOG:
        env["WORKCHAIN_RUNLOG"] = _RUNLOG      # every engine run appends to THIS log
    ok=fail=0
    total=len(todo)
    say("[4/4] ingest: %d files via %s" % (total, chain_name))
    t_ing0=time.time()
    for i,(h,p,sc) in enumerate(todo, 1):
        workdir=os.path.join(a.work, h[:12])
        env["ARCHIVE_SCOPE"]=sc
        t0=time.time()
        # Per-file line BEFORE the work, so a stall is attributable to a specific file
        # rather than showing up as an unexplained gap.
        say("[%d/%d] %s  [%s]  %s" % (i, total, h[:8], sc, p))
        r=subprocess.run(["bash",engine,"-c",chain,"-o",workdir,p], env=env,
                         capture_output=True, text=True)
        dt=time.time()-t0
        if r.returncode==0:
            ok+=1
            rate=i/max(1e-9,(time.time()-t_ing0))
            eta=(total-i)/rate if rate>0 else 0
            say("        ok %s  (%d/%d, %.2f files/s, eta %s)" % (human_dur(dt) if dt>=1 else "%.2fs"%dt,
                                                                  i, total, rate, human_dur(eta)))
        else:
            fail+=1
            err("[%d/%d] FAIL rc=%d after %s: %s" % (i, total, r.returncode,
                                                     "%.2fs"%dt, p))
            tail=(r.stderr or r.stdout or "").strip().splitlines()[-12:]
            for line in tail:
                err("        | %s" % line)
    el=time.time()-t_ing0
    say("ingest: %d ok, %d failed → %s  (%s, %.2f files/s)"
        % (ok, fail, a.db, human_dur(el), ok/max(1e-9,el)))
    say("=== done in %s ===" % human_dur(time.time()-t_run0))
    if logpath:
        say("run log: %s" % logpath)
    if fail:
        sys.exit(1)   # honest exit code: a partial ingest is not a success


if __name__=="__main__": main()
