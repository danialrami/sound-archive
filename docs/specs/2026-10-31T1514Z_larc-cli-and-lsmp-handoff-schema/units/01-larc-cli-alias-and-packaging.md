# Unit 01 — `larc-cli-alias-and-packaging`

## Objective
Expose **`larc`** as the canonical 4-character LUFS CLI entrypoint for `sound-archive` (with `bin/archive` retained as a backwards-compatible alias) and add a `--version` / `--json` top-level help surface.

## Context
- Repo files: `bin/archive`, `setup.sh`, `README.md`.
- Phase spec: `docs/specs/2026-10-31T1514Z_larc-cli-and-lsmp-handoff-schema/SPEC.md`.
- Depends on: —.

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

## Output
- **Files changed:** `bin/larc` (new, mode `0755`), `bin/archive` (rewritten as a delegating alias), `setup.sh` (`link-cli` stage + first-run hook + usage), `README.md` (documents `larc` + `link-cli`).
- **Where tests live:** `tests/test_units.py` — `Unit01CliTests` (version string/exit code, `--help`, dispatcher coverage, alias delegation, executable bits, `setup.sh link-cli` symlink).
- **Commit-message style:** `feat(cli): add larc entrypoint + link-cli stage; keep archive as compat alias (Unit 01)`

## Verification
```bash
./bin/larc --version
./bin/larc --help
./bin/archive --version
```
