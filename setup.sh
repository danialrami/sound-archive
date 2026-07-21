#!/usr/bin/env bash
# setup.sh — sound-archive master provisioner + first-run orchestrator.
#
# One script for the whole first-time flow: environment (a repo-local venv), CLAP
# provisioning, ingest, projection, and serve. It solves the macOS "externally-managed
# environment" (PEP 668) wall by putting every Python dependency in ./.venv — no system
# pip installs, ever. Because the LUFS Workchain engine also calls `python3` for its
# components, this script always puts ./.venv/bin on PATH before running the engine, so
# the light-path components (probe/features/hook/embed/archive_index) find numpy too.
#
# Everything is composable (each stage is its own command) AND there's a one-shot
# `first-run` that does the whole flow. Run `./setup.sh --help` for the full reference.
set -euo pipefail

SA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SA_DIR/.venv"
PY="$VENV/bin/python3"

# ---- defaults (overridable via flags) ----------------------------------------
WORKCHAIN="$(cd "$SA_DIR/.." 2>/dev/null && pwd)/lufs-workchain"
SAMPLES=""
EMBEDDER="clap"
SCOPE_MAP=""
DB="${ARCHIVE_DB:-$HOME/.sound-archive/archive.db}"
HOST="127.0.0.1"
PORT="8788"
FRESH=0
CLAP_PYTHON=""
CHAIN_SERVE=0
LIMIT=""
HOST_SET=0

c_grn=$'\033[0;32m'; c_yel=$'\033[1;33m'; c_red=$'\033[0;31m'; c_cyn=$'\033[0;36m'; c_off=$'\033[0m'
say(){ printf "%s\n" "${c_cyn}▸ $*${c_off}"; }
ok(){  printf "%s\n" "${c_grn}✓ $*${c_off}"; }
warn(){ printf "%s\n" "${c_yel}! $*${c_off}"; }
die(){ printf "%s\n" "${c_red}✗ $*${c_off}" >&2; exit 1; }

usage(){ cat <<'EOF'
sound-archive · setup.sh — provision + first-run for the sound archive

USAGE
  ./setup.sh <command> [options]

COMMANDS
  doctor          Check deps (ffmpeg/ffprobe/python3), create ./.venv, install numpy. Idempotent.
  provision-clap  Create the workchain embed_clap venv (torch + laion-clap) for real CLAP embeddings.
  ingest          Ingest an audio root into the index (scan → dedup → workchain chain per keeper).
  project         Build the 3D galaxy projection (PCA-3D + k-means; persisted, run after each ingest).
  serve           Serve the galaxy front door + API at /  →  open http://HOST:PORT/
  first-run       The whole flow: doctor → [provision-clap if --embedder clap] → smoke(1 file)
                  → ingest → project. Add --serve to launch serve at the end.
  help            This message.  (also --help, -h)

OPTIONS
  --samples PATH      Audio root to ingest (required for ingest / first-run).
  --workchain PATH    lufs-workchain checkout (default: ../lufs-workchain).
  --embedder NAME     clap | melstats   (default: clap — real LAION-CLAP).
  --scope-map "A=reference B=reference"   Folder→scope rules (kept out of the daily surface).
  --db PATH           Index sqlite db (default: $ARCHIVE_DB or ~/.sound-archive/archive.db).
  --fresh             Wipe the db before ingest (use for a clean CLAP index — don't mix embedders).
  --limit N           Only ingest N files (smoke tests).
  --clap-python BIN   Python used to build the CLAP venv (default: auto-detect a torch-friendly one).
  --host H            serve host (default: 127.0.0.1; use 0.0.0.0 for the tailnet).
  --port N            serve port (default: 8788).
  --serve             (first-run only) chain into `serve` when the flow finishes
                      (binds 0.0.0.0 for the tailnet unless you pass --host).
  -h, --help          This message.

EXAMPLES
  # 1) whole first-time flow, real CLAP, own-recordings first, fresh index, then serve:
  ./setup.sh first-run --samples ~/Samples/Samples/sampleLibrary/lufs-recorder \
      --embedder clap --fresh --serve

  # 2) composable: set up env once, then run stages yourself
  ./setup.sh doctor
  ./setup.sh provision-clap
  ./setup.sh ingest --samples ~/Samples/Samples/sampleLibrary --embedder clap \
      --scope-map Komplete=reference Orchs=reference
  ./setup.sh project
  ./setup.sh serve --host 0.0.0.0 --port 8788

NOTES
  • Everything runs in ./.venv — no `pip install` into system Python (fixes PEP 668 on macOS).
  • CLAP is heavy: first provision downloads torch + laion-clap; first ingest pulls the ~2GB ckpt.
  • Use a FRESH --db when switching embedder (CLAP=512-d, melstats=64-d; mixing breaks cosine).
EOF
}

# ---- arg parsing -------------------------------------------------------------
[ $# -ge 1 ] || { usage; exit 1; }
CMD="$1"; shift || true
case "$CMD" in -h|--help|help) usage; exit 0;; esac
while [ $# -gt 0 ]; do
  case "$1" in
    --samples) SAMPLES="$2"; shift 2;;
    --workchain) WORKCHAIN="$2"; shift 2;;
    --embedder) EMBEDDER="$2"; shift 2;;
    --scope-map) SCOPE_MAP="$2"; shift 2;;
    --db) DB="$2"; shift 2;;
    --host) HOST="$2"; HOST_SET=1; shift 2;;
    --port) PORT="$2"; shift 2;;
    --limit) LIMIT="$2"; shift 2;;
    --clap-python) CLAP_PYTHON="$2"; shift 2;;
    --fresh) FRESH=1; shift;;
    --serve) CHAIN_SERVE=1; shift;;
    -h|--help) usage; exit 0;;
    *) die "unknown option: $1  (see ./setup.sh --help)";;
  esac
done

# ---- helpers -----------------------------------------------------------------
need(){ command -v "$1" >/dev/null 2>&1 || die "missing '$1' — install it first (macOS: brew install $2)"; }

ensure_venv(){
  need ffmpeg ffmpeg; need ffprobe ffmpeg; need python3 python
  if [ ! -x "$PY" ]; then
    say "creating venv at ./.venv"
    python3 -m venv "$VENV" || die "could not create venv (need python3 -m venv)"
  fi
  if ! "$PY" -c "import numpy" >/dev/null 2>&1; then          # idempotent: only install once
    say "installing archive deps into ./.venv (numpy)"
    "$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
    "$VENV/bin/pip" install -q -r "$SA_DIR/requirements.txt" || die "pip install failed in ./.venv"
  fi
  ok "venv ready — $("$PY" -c 'import numpy,sys;print("python",sys.version.split()[0],"· numpy",numpy.__version__)')"
  # git pushes don't always preserve the executable bit; make our entrypoints runnable.
  chmod +x "$SA_DIR/bin/archive" "$SA_DIR/setup.sh" 2>/dev/null || true
}

# Run bin/archive with the venv on PATH so the engine's python3 (features/embed/…) finds numpy.
# Invoked via `bash` so it works even if the file's +x bit didn't survive the git push.
arch(){ PATH="$VENV/bin:$PATH" ARCHIVE_DB="$DB" bash "$SA_DIR/bin/archive" "$@"; }

check_workchain(){
  [ -f "$WORKCHAIN/engine/workchain-engine.sh" ] || die "no workchain engine at $WORKCHAIN (pass --workchain PATH)"
  local chain="archive-ingest.yaml"; [ "$EMBEDDER" = clap ] && chain="archive-ingest-clap.yaml"
  [ -f "$WORKCHAIN/chains/$chain" ] || die "chain $chain missing in $WORKCHAIN/chains (pull the latest lufs-workchain)"
}

cmd_doctor(){ ensure_venv; check_workchain; ok "doctor: ffmpeg+ffprobe present, venv ready, workchain at $WORKCHAIN"; }

cmd_provision_clap(){
  check_workchain
  local cdir="$WORKCHAIN/components/embed_clap"
  [ -d "$cdir" ] || die "embed_clap component missing in $WORKCHAIN (pull latest)"
  local vpy="$cdir/.venv/bin/python" pip="$cdir/.venv/bin/pip"
  # fast path: already importable → nothing to do (this is exactly what the preflight checks)
  if [ -x "$vpy" ] && "$vpy" -c "import laion_clap, torch" >/dev/null 2>&1; then
    ok "embed_clap already provisioned + verified (import laion_clap OK)."; return
  fi
  local cpy=""
  for cand in "$CLAP_PYTHON" python3.12 python3.11 python3.13 python3; do
    [ -n "$cand" ] || continue
    command -v "$cand" >/dev/null 2>&1 && { cpy="$cand"; break; }
  done
  [ -n "$cpy" ] || die "no python found for the CLAP venv"
  say "building embed_clap venv with $cpy — torch + laion-clap + deps (heavy; several minutes, progress below)"
  rm -rf "$cdir/.venv"   # clean rebuild (a prior half-provisioned venv is why we're here)
  "$cpy" -m venv "$cdir/.venv" || die "venv create failed with $cpy"
  "$pip" install --upgrade pip >/dev/null 2>&1 || true
  # laion_clap imports torchaudio + transformers at load, and it is not numpy-2 clean — install the
  # full import-time set and pin numpy<2 in THIS venv (independent of the archive venv's numpy 2.x).
  if ! "$pip" install "numpy<2" soundfile librosa transformers torch torchaudio laion-clap; then
    warn "pip install failed under $cpy (often a too-new Python for torch/torchaudio wheels)."
    warn "remedy: brew install python@3.12 && ./setup.sh provision-clap --clap-python python3.12"
    die  "CLAP not provisioned. --embedder melstats works in the meantime (see the galaxy now, upgrade later)."
  fi
  # VERIFY the import the workchain preflight will check — never claim success we didn't earn.
  local err
  if ! err="$("$vpy" -c 'import laion_clap, torch, soundfile' 2>&1)"; then
    printf "%s\n" "$err" >&2
    warn "laion_clap installed but failed to IMPORT (real error above)."
    warn "paste that error to Ciani and I'll pin the exact versions. Meanwhile: --embedder melstats."
    die  "CLAP import verification failed — not marking provisioned."
  fi
  ok "embed_clap provisioned + verified (import laion_clap OK) with $cpy. First CLAP ingest pulls the ~2GB checkpoint."
}

cmd_ingest(){
  [ -n "$SAMPLES" ] || die "ingest needs --samples PATH"
  [ -d "$SAMPLES" ] || die "samples root not found: $SAMPLES"
  ensure_venv; check_workchain
  mkdir -p "$(dirname "$DB")"
  if [ "$FRESH" = 1 ] && [ -f "$DB" ]; then warn "fresh: removing existing $DB"; rm -f "$DB"; fi
  local args=(ingest "$SAMPLES" --workchain "$WORKCHAIN" --embedder "$EMBEDDER" --db "$DB")
  # ingest_batch's --scope-map is nargs="*": all folder=scope pairs go after ONE flag.
  if [ -n "$SCOPE_MAP" ]; then args+=(--scope-map); for kv in $SCOPE_MAP; do args+=("$kv"); done; fi
  [ -n "$LIMIT" ] && args+=(--limit "$LIMIT")
  say "ingesting $SAMPLES  (embedder=$EMBEDDER, db=$DB)"
  arch "${args[@]}"
}

cmd_project(){ ensure_venv; say "building galaxy projection"; arch project --db "$DB"; ok "projection persisted"; }

cmd_serve(){
  ensure_venv
  ok "serving the galaxy + API — open  http://$HOST:$PORT/"
  arch serve --host "$HOST" --port "$PORT" --db "$DB"
}

cmd_first_run(){
  [ -n "$SAMPLES" ] || die "first-run needs --samples PATH"
  cmd_doctor
  [ "$EMBEDDER" = clap ] && cmd_provision_clap
  say "smoke test: ingesting ONE file to validate the chain (+ download the model on first CLAP run)"
  ( LIMIT=1 cmd_ingest )
  local model
  model="$(arch query --db "$DB" stats 2>/dev/null | tr -d ' ' || true)"
  say "smoke result: $(arch query --db "$DB" stats 2>/dev/null | sed -n '3,4p' | tr '\n' ' ')"
  say "full ingest"
  FRESH=0 cmd_ingest
  cmd_project
  ok "first-run complete — index at $DB"
  arch query --db "$DB" stats || true
  if [ "$CHAIN_SERVE" = 1 ]; then
    [ "$HOST_SET" = 0 ] && HOST="0.0.0.0"   # first-run --serve binds the tailnet-reachable interface by default
    cmd_serve
  else
    echo; ok "next:  ./setup.sh serve --host 0.0.0.0 --port $PORT   →   open http://<klaxon>:$PORT/"
  fi
}

case "$CMD" in
  doctor) cmd_doctor;;
  provision-clap) cmd_provision_clap;;
  ingest) cmd_ingest;;
  project) cmd_project;;
  serve) cmd_serve;;
  first-run) cmd_first_run;;
  *) die "unknown command: $CMD  (see ./setup.sh --help)";;
esac
