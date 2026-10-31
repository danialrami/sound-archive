# Unit 02 — `schema-v1-pitch-role-provenance-migration`

## Objective
Extend `archive/schema.sql` and provide an idempotent migration script (`archive/migrate.py`) that adds the musical (`sample_role`, `category`, `root_note`, `f0_hz`, `pitch_confidence`, `bpm_confidence`, `bars`) and provenance (`source`, `source_id`, `creator`, `license`) columns required by `lsmp` without losing existing rows in `~/.sound-archive/archive.db`.

## Context
- Repo files: `archive/schema.sql`, new `archive/migrate.py`.
- Phase spec: `docs/specs/2026-10-31T1514Z_larc-cli-and-lsmp-handoff-schema/SPEC.md`.
- Depends on: —.
- The live `assets` table + `interaction_log` already exist and are append-only in production; the migration must be **non-destructive** (only `ALTER TABLE ... ADD COLUMN`, every new column nullable) and **idempotent**.

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

## Output
- **Files changed:** `archive/schema.sql` (new v2 columns + indexes + `PRAGMA user_version` comment), `archive/migrate.py` (new — idempotent, non-destructive migrator + `root_note`/`sample_role` validators).
- **Where tests live:** `tests/test_units.py` — `Unit02MigrationTests` (fresh/empty db → v2, v0→v2 `ALTER TABLE` only, idempotent `already_migrated`, non-destructive row preservation, validators, index presence). The unit's own verification command is run verbatim too.
- **Commit-message style:** `feat(schema): add pitch/role/provenance columns + idempotent v2 migration (Unit 02)`

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
