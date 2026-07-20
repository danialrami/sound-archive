# First-time usage — the honest walkthrough

What actually happens the first time, end to end, with no hand-waving. Everything below
was exercised in a sandbox against generated audio before shipping; the numbers are real.

## 0. Prerequisites
- `ffmpeg` + `ffprobe` on PATH (probe/hook/decode).
- `python3` with `numpy` (`pip install numpy`). v0 is otherwise stdlib-only.
- A checkout of `lufs-workchain` next to this repo.
- (prod, later, on klaxon) a `uv` venv adds sqlite-vec / laion-clap / librosa / duckdb / pyacoustid.

## 1. Point it at your own recordings first
Ingest is scoped on purpose. Start with the smallest, highest-signal set — the material
the ADJ loop should surface — not the whole 2.6 TB:

```bash
export ARCHIVE_DB=~/.sound-archive/archive.db
bin/archive ingest ~/Samples/Samples/sampleLibrary \
  --workchain ../lufs-workchain \
  --scope-map Komplete=reference Orchs=reference \
  --dry-run
```

`--dry-run` prints the plan without touching anything:

```
scan: 259320 standard-audio files under ~/Samples/Samples/sampleLibrary
dedup L1: <unique> / 259320 files  (<n> exact-dupe copies collapsed)
dedup L2 (chromaprint): fpcalc not found — transcode-dupe pass DEFERRED
resume: 0 already indexed, <unique> to ingest
  would ingest [archive] .../lufs-recorder/2026-01-07/take-0003.wav
  would ingest [reference] .../Komplete/.../horn_Db4.wav
```

Non-standard-audio filetypes (`.nkx/.ncw/.nki/.nksn/.mid/.sdir/.xpak/…`) are dropped at scan.
Nothing is excluded from the *index* except those — the `Komplete`/`Orchs` libraries are
tagged `reference` (queryable, but kept out of the daily inspiration stream), never dropped.

## 2. Run it for real
Drop `--dry-run`. The driver computes a content hash per file (exact-dedup Layer 1), keeps one
canonical per dupe group (lossless > lossy > higher SR/bit-depth > longer), and runs the
workchain `archive-ingest` chain once per keeper. It is **resumable**: re-running skips anything
already in the index (a file is "cataloged" only when it's *verified* in the index, not when a
script exited 0).

```bash
bin/archive ingest ~/Samples/Samples/sampleLibrary --workchain ../lufs-workchain \
  --scope-map Komplete=reference Orchs=reference
# → ingest: <ok> ok, <fail> failed → ~/.sound-archive/archive.db
```

Each file flows through five verified stages: **probe** (hash + facts + loudness) →
**features** (centroid/rms/brightness; bpm/key deferred) → **hook** (3 s loudest-window clip +
waveform PNG) → **embed** (L2-normed vector) → **archive_index** (sqlite upsert). Every stage's
output is checked by the workchain verifier against its `step.yaml` `verify:` contract before the
next stage runs.

## 3. Query it over the CLI
Yes — once your own-recordings scope is ingested, you query it immediately, no UI:

```bash
bin/archive query stats
#   total: 90   by scope: {'archive': 88, 'reference': 2}   by model: {'melstats-v0': 90}

bin/archive query filter --bright-max 0.15 --scope archive        # dark things I recorded
bin/archive query filter --dur-min 30 --scope archive             # long takes
bin/archive query like lufs-1c4541c1 --k 5                         # "more like this one" (cosine NN)
bin/archive query text "dark drone" --k 5                          # text (see note below)
bin/archive query <any> --json                                     # machine-readable for agents
```

**Honest note on `text`:** real text→audio retrieval needs the CLAP/MuQ *text* encoder, which
ships in the prod embedder on klaxon. On the `melstats-v0` placeholder there is no text tower, so
`text` falls back to a feature heuristic (dark→low brightness, etc.) and **says so** in its output.
`like` (audio→audio similarity) is fully real on melstats today.

## 4. Serve the read side (optional, for the front door)
```bash
bin/archive serve --host 0.0.0.0 --port 8788     # on klaxon, over the tailnet
curl localhost:8788/api/stats
curl "localhost:8788/api/query?scope=archive&bright_max=0.15&limit=9"
curl localhost:8788/api/like/lufs-1c4541c1?k=5
curl localhost:8788/hook/lufs-1c4541c1 -o hook.wav      # the 3s preview
```
This is the surface the ADJ front door (and Amacher's "galaxy") build on. The typed
`interaction_log` (star/use/skip) is the flywheel — back it up religiously; nothing regenerates it.

## What's real today vs deferred
- **Real & verified:** the chain, per-stage contracts + the verifier gate, exact-dedup, scope
  tagging, hooks + waveforms, the index, and CLI `stats/list/filter/like`.
- **Placeholder (contract-stable):** `embed` = `melstats-v0`; swap to LAION-CLAP/MuQ on klaxon.
- **Deferred:** bpm/key (librosa/essentia or sononym warm-start); chromaprint transcode-dedup
  (needs `fpcalc`); the sqlite-vec vec0 table; the ADJ surface + learned ranker.
