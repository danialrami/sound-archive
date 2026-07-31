# The ingest runner (`ingest.sh`) and the remote-embed cutover

Why this repo gained a root-level `ingest.sh`, what it does, and one change it forced in
`sound-archive`'s sibling repo `lufs-workchain`.

## 1. Why `ingest.sh` exists

The library ingest is a multi-day batch over ~244k files and ~337 GB. It is driven by
`archive/ingest_batch.py`, which:

1. scans the samples tree for standard-audio extensions,
2. hashes every byte (dedup L1 — the "resume cost"),
3. resumes against `archive.db` (skip already-indexed content),
4. runs each remaining file through the workchain (`archive-ingest-clap-remote.yaml`).

None of that is new. What is new is **where it runs and how we check in on it**. The old
flow launched the batch inside a terminal session that was tied to an interactive SSH
login; dropping the SSH connection meant the run could die with it. We also kept re-typing
the same launch flags and hand-curling status endpoints to see where a run was.

`ingest.sh` is the single entrypoint for that: start/resume the batch in a way that
survives a dropped SSH session, and watch/stop it from any shell without touching the pane.

```
./ingest.sh run        start/resume detached (default: tmux session 'ingest')
./ingest.sh run --herdr        same, but split a sibling pane inside a herdr session
./ingest.sh run --foreground   run in the current shell (for a herdr pane you made)
./ingest.sh watch [--stats]    tail the run log; optionally poll the serve count
./ingest.sh status             is it running? last log lines + DB count
./ingest.sh stop               Ctrl+C to the ingest (tmux send-keys, else SIGINT group)
./ingest.sh preflight          /readyz + key check (fail-closed) before starting
./ingest.sh help               the full check-in toolkit
```

It is deliberately thin:

- **One real launch command.** `run` execs `archive/ingest_batch.py <root> --workchain
  <workchain> --embedder <embedder> --db <db>` (the same shape as `setup.sh`'s `arch
  ingest`). The `--tmux`/`--herdr` modes re-invoke `run --foreground` in a fresh pane so
  the env file is re-sourced there and the API key never appears in any command string.
- **Env, not flags, for secrets.** `EMBED_API_KEY` is sourced from
  `~/.config/serve-embed/client.env` (0600) inside the shell; `EMBED_CLAP_ENDPOINT`
  carries the endpoint. The key is never on a command line or in `ps`.
- **Fail-closed.** `run` refuses to start unless `<endpoint>/readyz` returns `ok:true`
  and the env file contains a non-empty `EMBED_API_KEY`. `preflight` runs the same checks
  standalone.
- **Double-launch guard.** `run` refuses to start while an `ingest_batch.py` process
  exists (`--force` stops the running one first).
- **Three terminal-agnostic check-in surfaces.** The run log
  (`~/.workchain/runs/latest.log`), the serve API (`http://127.0.0.1:8788/api/stats`),
  and the process table. `watch`/`status` key off those, so they work from any shell —
  inside herdr, over a fresh SSH, or from an agent.

## 2. The remote-embed cutover (why the chain changed)

The old default embedder loaded the ~2 GB CLAP checkpoint per file locally, which capped
throughput around a few hundred files/hour. The batch now uses `--embedder clap-remote`
with chain `archive-ingest-clap-remote.yaml`, which ships decoded 48k mono PCM to a
resident-model serve-embed endpoint instead of reloading the checkpoint. The endpoint
runs on the CUDA box (carnyx, `100.125.210.60:8770`); `EMBED_CLAP_ENDPOINT` points there.
Parity was verified at cosine 1.0 on a fixture before the first remote run.

## 3. The `constants.sh` change in `lufs-workchain` (and why it was needed)

The first remote run immediately hit a wall: every `.caf` file failed with
`Input file is not a supported audio format` and `rc=1` after ~0.02 s. That was not an
audio problem — ffprobe decodes these files fine (aac-in-caf, 44.1 kHz, 9.6 s). The batch
scanner was feeding the engine files the engine's own gate rejects:

- `archive/ingest_batch.py` accepts these extensions at scan:
  `.wav .aif .aiff .aifc .flac .mp3 .ogg .oga .opus .m4a .aac .caf .wv .alac`
- `lufs-workchain/lib/constants.sh` allowed only:
  `wav mp3 aiff aif flac m4a ogg`
- `is_audio_file()` (`lufs-workchain/lib/common-utils.sh`) checks a file's extension
  against `SUPPORTED_AUDIO_EXTENSIONS`, and the engine
  (`lufs-workchain/engine/workchain-engine.sh`) exits `rc=1` with
  `Input file is not a supported audio format` when it returns false — **before any step
  runs**.

So every scanner-supported format missing from the engine list was a guaranteed failure:
`.caf`, `.aifc`, `.oga`, `.opus`, `.aac`, `.wv`, `.alac`. The library held 30,117 `.caf`
files (Apple Sound Library loops) — ~17% of the queue — all of which were failing on
every run and would have kept failing on every rerun until the lists matched.

The fix, in `lufs-workchain/lib/constants.sh`, brought the engine gate into parity with
the scanner:

```
SUPPORTED_AUDIO_EXTENSIONS=("wav" "mp3" "aiff" "aif" "flac" "m4a" "ogg" "caf" "aifc" "oga" "opus" "aac" "wv" "alac")
```

The two lists live in different languages (Python vs. bash) in different repos, so this
is maintained by hand. Keep them in lockstep: a format in one but not the other fails
loudly at ingest, not at scan. (A parity guard is a possible follow-up; it has not been
added yet.)

## 4. Cutover gates (how we know a run is healthy)

From the run log during `[4/4] ingest`:

1. **Resume count:** `[3/4] resume: 63151 already indexed, … to ingest` — the indexed
   count must be the pre-run baseline (63,151), proving we didn't re-ingest the library.
2. **Remote sidecars:** fresh files under `~/.sound-archive/work/<hash>/archive/*.embedding.json`
   show `"served_by": "remote"`, `"device": "cuda"`, and `elapsed_ms` in the low hundreds.
3. **Throughput:** well above the old ~275 files/hour — the whole point of the cutover.
