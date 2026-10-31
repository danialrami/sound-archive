# sound-archive

The **librarian** over your own audio: the read/serve/surface side of the sound archive.
It consumes the index that the [lufs-workchain](https://github.com/danialrami/lufs-workchain)
`archive-ingest` chain produces, and turns "a mountain of files" into **"ah, I remember that."**

Design record + rationale: `danialrami/agent-knowledge` → `docs/product/sound-archive/`.

## The CLI: `larc`

The canonical entrypoint is **`larc`** (4 chars, per the LUFS primitive CLI naming convention);
`bin/archive` is kept as a non-breaking alias that delegates to it. Both dispatch the same
subcommands: `ingest`, `query`, `serve`, `surface`, `act`, `points`, `project`, `migrate`, `export`.

```bash
larc --version                                    # larc 0.2.0 (sound-archive)
larc --help
larc query filter --role one_shot --category bass --license cc0 --json
larc migrate --db "$ARCHIVE_DB"                    # idempotent v0 -> v2 schema migration
larc export lufs-1c4541c1 --record-use --json      # lsmp handoff descriptor (+ use flywheel)
```

`./setup.sh link-cli` symlinks `bin/larc` into `~/.local/bin/larc` so `larc` is on PATH
(`first-run` calls it too).

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

## Fastest start — one script (macOS-friendly, no system pip)

`setup.sh` provisions a repo-local `.venv`, wires it through the workchain engine too, and runs
the whole first-time flow. No `pip install` into system Python (fixes the macOS PEP-668 wall).

```bash
cd sound-archive
./setup.sh --help                                  # full reference (agent-friendly)

# whole first-time flow: env → CLAP provision → smoke(1 file) → ingest → project → serve
./setup.sh first-run \
  --samples ~/Samples/Samples/sampleLibrary/lufs-recorder \
  --embedder clap --fresh --serve
# → open http://127.0.0.1:8788/   (the galaxy auto-detects the live serve and fills with your sound)
```

Composable stages (each is its own command, all venv-aware): `doctor`, `provision-clap`,
`ingest`, `project`, `serve`. See `./setup.sh --help`.

## Quick start

```bash
# (or do it by hand — setup.sh does all of this for you inside ./.venv)
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

# 3. the ADJ front door — a morning surface + the interaction log (the flywheel)
bin/archive surface --k 9 --session morning        # ~9 candidates: temporal+relevance+novelty+wildcard
bin/archive act lufs-abb199ce star                  # star / use / played / skip / more_like_this
bin/archive surface --k 9 --session morning        # now pulls "relevance:like-starred" neighbours

# 4. build the 3D galaxy projection (run after each ingest batch) + serve the read side
bin/archive project                                # PCA-3D + k-means -> persisted `projection` table
bin/archive points --scope archive                 # the galaxy point-cloud (stable cluster + x/y/z)
bin/archive serve --host 0.0.0.0 --port 8788       # serves the web/ front door at /  + the API under /api
# → open http://<klaxon>:8788/  — the galaxy auto-detects the live serve (same-origin) and fills with your real sound
```

Full first-time walkthrough: **[docs/01-first-run.md](docs/01-first-run.md)**.

## Status

v0 scaffold. The `embed` stage ships `melstats-v0` (a dependency-light stand-in behind the
CLAP **vector contract**) so the loop runs anywhere; swap in LAION-CLAP / MuQ-MuLan on klaxon
without touching the schema. `bpm`/`key` are deferred (librosa/essentia or the sononym DuckDB
warm-start). The **ADJ surface + interaction log are live** (`surface.py` / `actlog.py`) — a transparent weighted blend, no learned model yet; the log accrues from day one so a ranker/bandit can be fit later. Next: real CLAP on klaxon + the Amacher frontend over `serve`.
