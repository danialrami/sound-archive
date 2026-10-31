# Spec: `2026-10-31T1515Z_larc-cli-and-lsmp-handoff-schema`

> Self-contained specification and unit-of-work contracts for upgrading `danialrami/sound-archive` to the **`larc`** LUFS CLI primitive convention and extending its SQLite schema, query filters, and export handoff to feed downstream sample-pack builders (`lsmp`).

---

## 1. Problem & Goal

`sound-archive` indexes ~259k audio files into `~/.sound-archive/archive.db` for discovery and daily surfacing. We now have a downstream LUFS primitive, **`lsmp`** (`lufs-sampler`), which pulls curated keepers from the archive (or from `flufs`, `pd-query`, and `lrex` takes) to assemble normalized 48 kHz `.wav` sample packs and pitch-mapped `strudel.json` manifests for livecoding in Strudel.

Right now, four gaps prevent `sound-archive` from feeding `lsmp` cleanly:

1. **CLI Naming (LUFS Unit 07 convention)**: The current CLI entrypoint is `bin/archive` (7 chars, generic). Per the LUFS Primitive CLI naming convention (3–6 lowercase chars: `lrex`, `lsbx`, `lsmp`), `sound-archive` should expose **`larc`** as its primary CLI invocation name while keeping `bin/archive` as a non-breaking compatibility alias.
2. **Monophonic `root_note` (`e1`, `c4`) vs. Polyphonic `key` (`D:minor`)**: `archive/schema.sql` currently defines only `key TEXT` (null in v0). Strudel's `strudel.json` pitch-mapping format (`"bass": { "e1": "bass/bass.wav" }`) requires the **scientific pitch root note with octave** (`root_note TEXT`, `f0_hz REAL`, `pitch_confidence REAL`) for monophonic one-shots, distinct from harmonic scale `key` (`"D:minor"`) for loops.
3. **Missing `sample_role` & `category` columns**: Although KB `07-ciani-engineering-addendum` (Knob 3) resolved to keep `Loop/OneShot` and category classification from the Sononym warm-start and native DSP, `archive/schema.sql` omitted `sample_role` (`one_shot` | `loop` | `stem` | `take`) and `category` (`bd`, `sd`, `hh`, `cp`, `perc`, `bass`, `pad`, `lead`, `fx`, `vox`). `lsmp` needs `sample_role` + `pitch_confidence` to decide whether to emit a `strudel.json` entry as a pitch-mapped object (`{ "e1": "..." }`), an unpitched variation array (`["..."]`), or a tempo-tagged loop.
4. **Missing Provenance/License columns & Handoff Flywheel**: `assets` tracks `scope` (`archive` | `reference`) but not `source` (`own` | `freesound` | `openverse` | `pack`), `source_id`, `creator`, or `license` (`own` | `cc0` | `cc-by` | `reference`). Furthermore, when `lsmp` pulls an asset by `catalog_number` (`lufs-<8hex>`), `larc` needs a single machine-readable `larc export <catalog_number> --json` (or `--use`) subcommand that returns the full asset + musical metadata and automatically logs `action = 'use'` (`weight = +5.0`) in `interaction_log`.

---

## 2. Ecosystem References

- **Downstream Consumer (`lsmp` / `lufs-sampler`)**: Reads `larc export <catalog_number> --json` (or queries `~/.sound-archive/archive.db` read-only) to build `~/repos/samples/<pack-slug>/pack.json` and `strudel.json`.
- **Upstream Sibling Primitives**:
  - `lrex` (`danialrami/lufs-recorder`) — verified hardware/PipeWire audio capture (`take.json`).
  - `flufs` (`danialrami/freesound-lufs`) — Freesound CLI (`*_metadata.json`).
  - `pd-query` (`danialrami/public-domain`) — Openverse/CC0 public domain query CLI.
  - `lufs-workchain` (`danialrami/lufs-workchain`) — runs the `archive-ingest` chain (`probe -> features -> hook -> embed -> archive_index`).
- **KB Design Records**:
  - `danialrami/agent-knowledge` → `docs/product/sound-archive/03-architecture-and-workchain.md`
  - `danialrami/agent-knowledge` → `docs/product/sound-archive/07-ciani-engineering-addendum.md`
  - `danialrami/agent-knowledge` → `docs/product/bplate/10-naming-kernel-and-backport.md` (Unit 07 3–6 char CLI naming rule).

---

## 3. Unit Decomposition

| Unit | Slug | Summary | Depends On |
|---|---|---|---|
| **01** | `larc-cli-alias-and-packaging` | Add `bin/larc` dispatcher + `setup.sh` install symlink (`~/.local/bin/larc`) while preserving `bin/archive`. | — |
| **02** | `schema-v1-pitch-role-provenance-migration` | Add idempotent schema migration in `archive/schema.sql` + `archive/migrate.py` for `sample_role`, `category`, `root_note`, `f0_hz`, `pitch_confidence`, `bpm_confidence`, `bars`, `source`, `source_id`, `creator`, `license`. | — |
| **03** | `query-filter-by-role-pitch-bpm-and-license` | Extend `archive/query.py` and `archive/serve.py` (`GET /api/query`) to filter by `--role`, `--category`, `--root-note`, `--key`, `--bpm-min`, `--bpm-max`, `--license`, and `--source`. | 02 |
| **04** | `export-handoff-and-use-flywheel` | Add `larc export <catalog_number...> [--record-use] --json` in `archive/export.py` (wired into `bin/larc` and `POST /api/export`) to emit the `lsmp`-compatible handoff descriptor and append `action='use'` (+5.0) to `interaction_log`. | 01, 02 |

---

# Unit 01 — `larc-cli-alias-and-packaging`

## Objective
Expose **`larc`** as the canonical 4-character LUFS CLI entrypoint for `sound-archive` (with `bin/archive` retained as a backwards-compatible alias) and add a `--version` / `--json` top-level help surface.

## Context
- Repo files: `bin/archive`, `setup.sh`, `README.md`.

## Acceptance criteria
- [ ] `bin/larc` exists, is executable (`0755`), and dispatches all subcommands (`ingest`, `query`, `serve`, `surface`, `act`, `points`, `project`, `migrate`, `export`).
- [ ] `bin/archive` remains executable and delegates to `bin/larc` so existing scripts do not break.
- [ ] `bin/larc --version` prints `larc 0.2.0 (sound-archive)` and exits `0`.
- [ ] `setup.sh` includes a `link-cli` stage (also called by `first-run`) that symlinks `bin/larc` to `~/.local/bin/larc`.

## Interface contract
```bash
larc <ingest|query|serve|surface|act|points|project|migrate|export> [ARGS...]
larc --version
larc --help
```

## Boundaries
- **Touches:** `bin/larc`, `bin/archive`, `setup.sh`, `README.md`
- **Does NOT touch:** `archive/*.py`, `archive/schema.sql`

## Verification
```bash
./bin/larc --version
./bin/larc --help
./bin/archive --version
```

---

# Unit 02 — `schema-v1-pitch-role-provenance-migration`

## Objective
Extend `archive/schema.sql` and provide an idempotent migration script (`archive/migrate.py`) that adds the musical (`sample_role`, `category`, `root_note`, `f0_hz`, `pitch_confidence`, `bpm_confidence`, `bars`) and provenance (`source`, `source_id`, `creator`, `license`) columns required by `lsmp` without losing existing rows in `~/.sound-archive/archive.db`.

## Context
- Repo files: `archive/schema.sql`, new `archive/migrate.py`.

## Acceptance criteria
- [ ] `archive/schema.sql` defines all new columns on `assets` plus indexes on `sample_role`, `category`, `root_note`, `key`, `bpm`, and `license`.
- [ ] Running `python3 archive/migrate.py --db <path> --json` on an existing v0 database adds any missing columns via `ALTER TABLE assets ADD COLUMN ...`, sets `PRAGMA user_version = 2`, and is idempotent on re-runs (`already_migrated: true`).
- [ ] `root_note` is constrained by convention/validation to lowercase scientific pitch notation (`^[a-g](#|b)?-?[0-9]$`, e.g. `e1`, `c4`, `f#3`) or `NULL`.
- [ ] `sample_role` is constrained to `one_shot | loop | stem | take` or `NULL`.

## Interface contract
```sql
-- Added columns on `assets` in archive/schema.sql (schema version 2):
  sample_role          TEXT,     -- 'one_shot' | 'loop' | 'stem' | 'take'
  category             TEXT,     -- 'bd' | 'sd' | 'hh' | 'oh' | 'cp' | 'rim' | 'perc' | 'bass' | 'pad' | 'lead' | 'chord' | 'fx' | 'vox' | 'atmo'
  root_note            TEXT,     -- scientific pitch for monophonic one-shots, e.g. 'e1', 'c4', 'g4' (feeds strudel.json pitch map)
  f0_hz                REAL,     -- detected fundamental frequency in Hz
  pitch_confidence     REAL,     -- [0.0, 1.0] confidence of fundamental pitch estimate
  bpm_confidence       REAL,     -- [0.0, 1.0] confidence of BPM estimate
  bars                 INTEGER,  -- estimated bar count for loops (e.g. 1, 2, 4, 8)
  source               TEXT,     -- 'own' | 'freesound' | 'openverse' | 'pack'
  source_id            TEXT,     -- upstream ID (e.g. Freesound numeric ID, Openverse UUID, lrex take_id)
  creator              TEXT,     -- upstream creator / artist handle
  license              TEXT      -- 'own' | 'cc0' | 'cc-by' | 'cc-by-sa' | 'reference'
```

## Boundaries
- **Touches:** `archive/schema.sql`, `archive/migrate.py`
- **Does NOT touch:** `archive/query.py`, `archive/serve.py`, `archive/actlog.py`

## Verification
```bash
python3 -c '
import tempfile, sqlite3, subprocess, json
with tempfile.NamedTemporaryFile(suffix=".db") as f:
    out = subprocess.check_output(["python3", "archive/migrate.py", "--db", f.name, "--json"])
    data = json.loads(out)
    assert data["schema_version"] == 2
    out2 = subprocess.check_output(["python3", "archive/migrate.py", "--db", f.name, "--json"])
    assert json.loads(out2)["already_migrated"] is True
'
```

---

# Unit 03 — `query-filter-by-role-pitch-bpm-and-license`

## Objective
Extend `archive/query.py` (`larc query filter`) and `archive/serve.py` (`GET /api/query`) so users and agents can filter by musical role, category, root note, scale key, BPM range, source, and license.

## Context
- Depends on: `Unit 02` (`schema-v1-pitch-role-provenance-migration`).
- Repo files: `archive/query.py`, `archive/serve.py`.

## Acceptance criteria
- [ ] `larc query filter` accepts `--role`, `--category`, `--root-note`, `--key`, `--bpm-min`, `--bpm-max`, `--pitch-conf-min`, `--source`, and `--license`.
- [ ] `GET /api/query` in `archive/serve.py` accepts the corresponding query parameters (`role`, `category`, `root_note`, `key`, `bpm_min`, `bpm_max`, `license`, `source`) and filters SQL results with parameterized queries.
- [ ] `larc query stats --json` includes breakdowns `by_role`, `by_category`, and `by_license`.

## Interface contract
```bash
larc query filter \
  [--scope archive|reference] \
  [--role one_shot|loop|stem|take] \
  [--category bd|sd|hh|oh|cp|rim|perc|bass|pad|lead|chord|fx|vox|atmo] \
  [--root-note <note>] \
  [--key <key>] \
  [--bpm-min <float>] [--bpm-max <float>] \
  [--pitch-conf-min <float>] \
  [--source own|freesound|openverse|pack] \
  [--license own|cc0|cc-by|reference] \
  [--bright-min <float>] [--bright-max <float>] \
  [--dur-min <float>] [--dur-max <float>] \
  [--limit <int>] [--json]
```

## Boundaries
- **Touches:** `archive/query.py`, `archive/serve.py`
- **Does NOT touch:** `archive/actlog.py`, `archive/surface.py`, `archive/points.py`

## Verification
```bash
./bin/larc query filter --role one_shot --category bass --license cc0 --json
```

---

# Unit 04 — `export-handoff-and-use-flywheel`

## Objective
Add `larc export <catalog_number...> [--record-use] [--session <name>] --json` to emit a deterministic handoff manifest for `lsmp` and automatically record `action = 'use'` (`weight = +5.0`) in `interaction_log` when `--record-use` is set.

## Context
- Depends on: `Unit 01`, `Unit 02`.
- Repo files: new `archive/export.py`, `archive/actlog.py`.

## Acceptance criteria
- [ ] `larc export <catalog_number...> --json` looks up each asset by `catalog_number` (`lufs-<8hex>`) or full `content_sha256` and emits the JSON handoff payload below (excluding the raw 512-float `vector` text).
- [ ] If any requested `catalog_number` is missing from `assets` or its `path` does not exist on disk, `larc export` exits non-zero (`exit 4`) with a structured JSON error naming the missing asset.
- [ ] When `--record-use` is passed, `larc export` calls `actlog.log_event(con, "use", content_sha256, session)` for each exported asset within the same transaction, closing the ADJ flywheel whenever `lsmp` pulls an archive keeper into a sample pack.

## Interface contract
```json
{
  "schema_version": 2,
  "exported_at": "2026-10-31T15:15:00Z",
  "recorded_use": true,
  "assets": [
    {
      "content_sha256": "0123456789abcdef...",
      "catalog_number": "lufs-01234567",
      "path": "/Users/danielramirez/Samples/...",
      "filename": "bass_stab.wav",
      "scope": "archive",
      "sample_role": "one_shot",
      "category": "bass",
      "duration_s": 1.85,
      "samplerate": 48000,
      "channels": 2,
      "peak_dbfs": -1.2,
      "rms_dbfs": -14.8,
      "root_note": "e1",
      "f0_hz": 41.2,
      "pitch_confidence": 0.94,
      "bpm": null,
      "bpm_confidence": null,
      "bars": null,
      "key": null,
      "source": "own",
      "source_id": "rec-70ac952a",
      "creator": "danielramirez",
      "license": "own"
    }
  ]
}
```

## Boundaries
- **Touches:** `archive/export.py`, `archive/actlog.py`
- **Does NOT touch:** `archive/query.py`, `archive/serve.py`, `archive/surface.py`

## Verification
```bash
./bin/larc export lufs-01234567 --record-use --session strudel-pack --json
```
