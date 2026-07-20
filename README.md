# sound-archive

The **librarian** over your own audio: the read/serve/surface side of the sound archive.
It consumes the index that the [lufs-workchain](https://github.com/danialrami/lufs-workchain)
`archive-ingest` chain produces, and turns "a mountain of files" into **"ah, I remember that."**

Design record + rationale: `danialrami/agent-knowledge` → `docs/product/sound-archive/`.

## The split (why two repos)

```
lufs-workchain  ──►  archive-ingest chain (per file):  probe → features → hook → embed → archive_index
                     • Workchain components; inherit the verifier ("proven, not exited-0")
                     • writes the shared index (sqlite; sqlite-vec in prod)
                                   │  the directory contract + the index file = the seam
                                   ▼
sound-archive   ──►  the librarian app (this repo):
                     • ingest_batch.py  scan + dedup + scope → drives the chain per keeper
                     • query.py         CLI: stats / list / filter / like / text
                     • serve.py         read-only HTTP/JSON for the front door (tailnet, on klaxon)
                     • schema.sql       canonical index schema (+ the interaction_log flywheel)
```

Ingest **stages are Workchain components** (they inherit the verifier). The librarian —
the store as system-of-record, the serve API, the ADJ surface, and the *irreplaceable*
interaction log — is this app. See `docs/product/sound-archive/07-ciani-engineering-addendum` (KB).

## Quick start

```bash
pip install numpy                       # v0 core is stdlib + numpy
export ARCHIVE_DB=~/.sound-archive/archive.db

# 1. ingest ONLY your own recordings first (scope=archive); tag the libraries reference
bin/archive ingest ~/Samples \
  --workchain ../lufs-workchain \
  --scope-map Komplete=reference Orchs=reference

# 2. query it over the CLI
bin/archive query stats
bin/archive query filter --bright-max 0.15 --scope archive     # dark things I recorded
bin/archive query like lufs-1c4541c1 --k 5                      # more like this one
bin/archive query text "dark metallic drone"                   # (CLAP in prod; heuristic on melstats-v0)

# 3. serve the read side on the tailnet (front door for the ADJ surface / Amacher)
bin/archive serve --host 0.0.0.0 --port 8788
```

Full first-time walkthrough: **[docs/01-first-run.md](docs/01-first-run.md)**.

## Status

v0 scaffold. The `embed` stage ships `melstats-v0` (a dependency-light stand-in behind the
CLAP **vector contract**) so the loop runs anywhere; swap in LAION-CLAP / MuQ-MuLan on klaxon
without touching the schema. `bpm`/`key` are deferred (librosa/essentia or the sononym DuckDB
warm-start). The ADJ surface + learned ranker are the next build on top of `serve` + `interaction_log`.
