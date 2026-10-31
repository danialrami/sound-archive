# Unit 03 — `query-filter-by-role-pitch-bpm-and-license`

## Objective
Extend `archive/query.py` (`larc query filter`) and `archive/serve.py` (`GET /api/query`) so users and agents can filter by musical role, category, root note, scale key, BPM range, source, and license.

## Context
- Depends on: `docs/specs/2026-10-31T1514Z_larc-cli-and-lsmp-handoff-schema/units/02-schema-v1-pitch-role-provenance-migration.md`.
- Repo files: `archive/query.py`, `archive/serve.py`.
- Phase spec: `docs/specs/2026-10-31T1514Z_larc-cli-and-lsmp-handoff-schema/SPEC.md`.

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

## Output
- **Files changed:** `archive/query.py` (new `filter` flags + `by_role`/`by_category`/`by_license` in `stats`), `archive/serve.py` (`/api/query` parses + parameterizes `role`, `category`, `root_note`, `key`, `bpm_min`, `bpm_max`, `license`, `source`).
- **Where tests live:** `tests/test_units.py` — `Unit03QueryTests` (filter by each axis via the CLI against a temp db; `stats --json` breakdowns; `/api/query` param filtering via the `serve` handler in-process).
- **Commit-message style:** `feat(query): filter by role/category/pitch/bpm/source/license + stats breakdowns (Unit 03)`

## Verification
```bash
./bin/larc query filter --role one_shot --category bass --license cc0 --json
```
