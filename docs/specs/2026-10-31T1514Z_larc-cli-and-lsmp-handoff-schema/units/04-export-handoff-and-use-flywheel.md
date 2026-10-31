# Unit 04 — `export-handoff-and-use-flywheel`

## Objective
Add `larc export <catalog_number...> [--record-use] [--session <name>] --json` to emit a deterministic handoff manifest for `lsmp` and automatically record `action = 'use'` (`weight = +5.0`) in `interaction_log` when `--record-use` is set.

## Context
- Depends on: `docs/specs/2026-10-31T1514Z_larc-cli-and-lsmp-handoff-schema/units/01-larc-cli-alias-and-packaging.md`, `docs/specs/2026-10-31T1514Z_larc-cli-and-lsmp-handoff-schema/units/02-schema-v1-pitch-role-provenance-migration.md`.
- Repo files: new `archive/export.py`, `archive/actlog.py`.
- Phase spec: `docs/specs/2026-10-31T1514Z_larc-cli-and-lsmp-handoff-schema/SPEC.md`.
- Downstream consumer `lsmp` (`src/pack.rs::resolve_larc_source`) shells out to `larc export <catalog_number> --record-use --json` and reads a **top-level** `path`/`audio`/`file` string from stdout. The handoff payload therefore carries the `assets[]` envelope **and** a top-level `path` (first asset) so the built consumer resolves the file without a change to `lsmp`.

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
- **Note (spec conflict, resolved):** the decomposition table says "wired into `bin/larc` and `POST /api/export`", but the Boundaries list explicitly forbids touching `archive/serve.py`. Boundaries win: `export` is wired into `bin/larc` only; no `/api/export` route is added.

## Output
- **Files changed:** `archive/export.py` (new — the handoff descriptor emitter), `archive/actlog.py` (`log_event(..., commit=...)` so a multi-asset `use` commits once).
- **Where tests live:** `tests/test_units.py` — `Unit04ExportTests` (payload field set incl. no `vector`; lookup by catalog + by sha; `--record-use` appends `use`/`+5.0` rows; missing asset / missing path → exit 4 structured error).
- **Commit-message style:** `feat(export): lsmp handoff descriptor + use flywheel (Unit 04)`

## Verification
```bash
./bin/larc export lufs-01234567 --record-use --session strudel-pack --json
```
