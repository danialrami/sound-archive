#!/usr/bin/env bash
# ingest.sh — drive + watch the sound-archive batch ingest (scan → dedup → resume → workchain).
#
# One entrypoint for starting, watching, and stopping the ingest, whether it runs in
# tmux, in a herdr pane, or in the foreground of a shell you own. All check-in paths key
# off three terminal-agnostic sources: the run log, the serve API, and the process table.
#
#   ./ingest.sh run        start/resume detached (tmux session 'ingest') — the default
#   ./ingest.sh run --herdr        same, but split a sibling pane inside a herdr session
#   ./ingest.sh run --foreground   run in the current shell (for a herdr pane you made)
#   ./ingest.sh watch [--stats]    tail the run log; optionally poll the serve count
#   ./ingest.sh status             where is it? last log lines + DB count
#   ./ingest.sh stop               Ctrl+C to the ingest (tmux send-keys, else SIGINT group)
#   ./ingest.sh preflight          /readyz + key check (fail-closed) before starting
#   ./ingest.sh help               the full check-in toolkit
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKCHAIN="${WORKCHAIN:-$(cd "$HERE/.." 2>/dev/null && pwd)/lufs-workchain}"
DB="${ARCHIVE_DB:-$HOME/.sound-archive/archive.db}"
RUNLOG_DIR="${WORKCHAIN_RUNLOG_DIR:-$HOME/.workchain/runs}"
DEFAULT_SAMPLES="$HOME/Samples/Samples/sampleLibrary"
DEFAULT_ENDPOINT="http://100.125.210.60:8770"
DEFAULT_ENV_FILE="$HOME/.config/serve-embed/client.env"
TMUX_SESSION="ingest"

if [ -x "$HERE/.venv/bin/python3" ]; then PY="$HERE/.venv/bin/python3"; else PY="python3"; fi

say(){ printf '\033[0;36m▸ %s\033[0m\n' "$*"; }
ok(){  printf '\033[0;32m✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m! %s\033[0m\n' "$*"; }
err(){ printf '\033[0;31m✗ %s\033[0m\n' "$*" >&2; }
die(){ err "$*"; exit 1; }

_ingest_pids(){ pgrep -f "archive/ingest_batch.py" || true; }

_latest_log(){
  if [ -f "$RUNLOG_DIR/latest.log" ]; then printf '%s\n' "$RUNLOG_DIR/latest.log";
  else ls -t "$RUNLOG_DIR"/*.log 2>/dev/null | head -1 || true; fi
}

_chain_for(){
  case "$1" in
    clap-remote) printf 'archive-ingest-clap-remote.yaml';;
    clap)        printf 'archive-ingest-clap.yaml';;
    melstats)    printf 'archive-ingest.yaml';;
    *)           printf 'archive-ingest.yaml';;
  esac
}

# ─────────────────────────────────────────────────────────────────────────────
cmd_preflight(){
  local env_file="${1:-$DEFAULT_ENV_FILE}" endpoint="${2:-$DEFAULT_ENDPOINT}" key=""
  [ -f "$env_file" ] && key="$(awk -F= '$1=="EMBED_API_KEY"{print $2}' "$env_file" 2>/dev/null || true)"
  if [ -n "$key" ]; then ok "API key present: $env_file"
  else warn "EMBED_API_KEY missing or empty in $env_file — /embed will 401"; fi
  local raw okf dev dim rev
  raw="$(curl -s -m 10 "$endpoint/readyz")" || { err "endpoint unreachable: $endpoint"; return 1; }
  IFS=$'\t' read -r okf dev dim rev <<<"$(printf '%s' "$raw" | "$PY" -c 'import json,sys
d=json.load(sys.stdin)
print("\t".join(["yes" if d.get("ok") else "no", str(d.get("device","")), str(d.get("dim","")), str(d.get("model_rev",""))]))')"
  if [ "$okf" = "yes" ]; then
    ok "readyz: ok=true device=$dev dim=$dim rev=$rev"
    return 0
  fi
  err "readyz not ok: ok=$okf device=$dev dim=$dim rev=$rev — fix the server before ingest"
  return 1
}

# ─────────────────────────────────────────────────────────────────────────────
cmd_run(){
  local samples="$DEFAULT_SAMPLES" embedder="clap-remote" endpoint="" env_file="$DEFAULT_ENV_FILE"
  local mode="tmux" preflight=1 limit="" force=0 dryrun=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --samples)     samples="$2"; shift 2;;
      --embedder)    embedder="$2"; shift 2;;
      --endpoint)    endpoint="$2"; shift 2;;
      --env-file)    env_file="$2"; shift 2;;
      --tmux)        mode="tmux"; shift;;
      --herdr)       mode="herdr"; shift;;
      --foreground)  mode="foreground"; shift;;
      --no-preflight) preflight=0; shift;;
      --limit)       limit="$2"; shift 2;;
      --dry-run)     dryrun=1; shift;;
      --force)       force=1; shift;;
      -h|--help)     cmd_help; exit 0;;
      *) die "unknown run flag: $1 — see 'ingest.sh help'";;
    esac
  done

  # env: EMBED_API_KEY / EMBED_CLAP_ENDPOINT come from the env file (never the CLI).
  if [ -f "$env_file" ]; then set -a; . "$env_file"; set +a; fi
  endpoint="${endpoint:-${EMBED_CLAP_ENDPOINT:-$DEFAULT_ENDPOINT}}"
  export EMBED_CLAP_ENDPOINT="$endpoint"

  [ "$preflight" = 1 ] && cmd_preflight "$env_file" "$endpoint"

  [ -d "$samples" ] || die "samples root not found: $samples"
  local chain; chain="$(_chain_for "$embedder")"
  [ -f "$WORKCHAIN/chains/$chain" ] || die "chain not found: $WORKCHAIN/chains/$chain (pull the latest lufs-workchain)"

  # Guard against double-launch (unless --force, which stops the running one first).
  local pids
  pids="$(_ingest_pids)"
  if [ -n "$pids" ]; then
    if [ "$force" = 1 ]; then warn "ingest already running (pid $pids) — stopping it first"; cmd_stop; sleep 2;
    else die "ingest already running (pid $pids) — use 'ingest.sh status'/'watch', or --force to restart"; fi
  fi

  # Re-invocation args for a fresh shell (tmux pane / herdr pane): the script re-sources
  # the env file inside that shell, so the key never appears in any command string.
  local -a reargs=(run --foreground --samples "$samples" --embedder "$embedder" --endpoint "$endpoint" --env-file "$env_file")
  [ "$preflight" = 1 ] && reargs+=(--no-preflight) || true   # already checked here; keep pane quiet
  [ -n "$limit" ] && reargs+=(--limit "$limit")
  [ "$dryrun" = 1 ] && reargs+=(--dry-run)

  # The single real launch: ingest_batch.py (same shape as setup.sh's `arch ingest`).
  # tmux/herdr modes re-invoke `run --foreground --no-preflight` in a fresh pane so the
  # env file is re-sourced there; this foreground branch then execs ingest_batch.py with
  # the env it inherited (EMBED_API_KEY / EMBED_CLAP_ENDPOINT exported above).
  local -a launch=("$samples" --workchain "$WORKCHAIN" --embedder "$embedder" --db "$DB")
  [ -n "$limit" ] && launch+=(--limit "$limit")
  [ "$dryrun" = 1 ] && launch+=(--dry-run)

  if [ "$dryrun" = 1 ]; then
    say "dry-run — would run:"
    printf '  %s\n' "$(printf '%q ' "$PY" "$HERE/archive/ingest_batch.py" "${launch[@]}")"
    return 0
  fi

  case "$mode" in
    foreground)
      say "foreground ingest: $samples (embedder=$embedder, endpoint=$endpoint, db=$DB)"
      exec "$PY" "$HERE/archive/ingest_batch.py" "${launch[@]}"
      ;;
    tmux)
      if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        [ "$force" = 1 ] && { warn "killing existing tmux session '$TMUX_SESSION'"; tmux kill-session -t "$TMUX_SESSION"; }
      fi
      local cmdstr; cmdstr="$(printf '%q ' "$HERE/ingest.sh" "${reargs[@]}")"
      tmux new-session -d -s "$TMUX_SESSION" "$cmdstr" || die "tmux launch failed"
      sleep 1
      tmux has-session -t "$TMUX_SESSION" 2>/dev/null || die "tmux session vanished immediately"
      ok "ingest launched in tmux session '$TMUX_SESSION'"
      say "watch:   ingest.sh watch --stats"
      say "attach:  tmux attach -t $TMUX_SESSION   (detach: Ctrl-b d)"
      say "stop:    ingest.sh stop"
      ;;
    herdr)
      if [ "${HERDR_ENV:-}" != "1" ]; then
        err "--herdr requires running inside a herdr pane (HERDR_ENV=1)."
        err "From your herdr TUI, create a workspace and run in its pane:"
        printf '  \033[0;36m%s\033[0m\n' "$HERE/ingest.sh run --foreground"
        die "…or use the default --tmux mode from any shell."
      fi
      local out pane_id cmdstr
      out="$(herdr pane split --current --direction right --cwd "$PWD" --no-focus)" || die "herdr pane split failed: $out"
      pane_id="$(printf '%s' "$out" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])')" \
        || die "could not parse herdr pane split response"
      cmdstr="$(printf '%q ' "$HERE/ingest.sh" "${reargs[@]}")"
      herdr pane run "$pane_id" "$cmdstr" || die "herdr pane run failed"
      ok "ingest launched in herdr pane $pane_id"
      say "check in: herdr pane read $pane_id --source recent-unwrapped --lines 80"
      say "stop:     herdr pane send-keys $pane_id ctrl+c   (or: ingest.sh stop)"
      ;;
  esac
}

# ─────────────────────────────────────────────────────────────────────────────
cmd_watch(){
  local stats=0 log=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --stats) stats=1; shift;;
      --log) log="$2"; shift 2;;
      -h|--help) cmd_help; exit 0;;
      *) die "unknown watch flag: $1";;
    esac
  done
  [ -n "$log" ] || log="$(_latest_log)"
  [ -n "$log" ] || die "no run log yet — start the ingest first (ingest.sh run)"
  if [ "$stats" = 1 ]; then
    ( while true; do
        sleep 30
        printf '\n%s  ' "$(date '+%H:%M:%S')"
        curl -s -m 5 http://127.0.0.1:8788/api/stats 2>/dev/null || printf '(serve not up — try status)'
        printf '\n'
      done ) &
    local poll=$!; trap 'kill "$poll" 2>/dev/null || true' EXIT INT
  fi
  say "tail -f $log  (Ctrl-C to stop watching; the ingest keeps running)"
  tail -f "$log"
}

# ─────────────────────────────────────────────────────────────────────────────
cmd_status(){
  local pids; pids="$(_ingest_pids)"
  if [ -n "$pids" ]; then ok "ingest: RUNNING (pid(s): $pids)"
  else warn "ingest: not running"; fi
  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then say "tmux session '$TMUX_SESSION': exists (tmux attach -t $TMUX_SESSION)"; fi
  if [ -f "$DB" ] && command -v sqlite3 >/dev/null 2>&1; then
    local n t
    IFS='|' read -r n t <<<"$(sqlite3 "$DB" "SELECT COUNT(*), COALESCE(MAX(indexed_at),'') FROM assets;")"
    say "index: $n assets  (last indexed: ${t:-never})"
    # Quarantine is the honest answer to "why is `to ingest` not going down?" — files that
    # failed before are skipped on resume instead of tarpitting the head of the queue.
    local q
    q="$(sqlite3 "$DB" "SELECT COUNT(*) FROM ingest_quarantine;" 2>/dev/null || echo 0)"
    if [ "${q:-0}" -gt 0 ]; then
      warn "quarantine: $q file(s) skipped on resume  (why: archive ingest --quarantine-report)"
      sqlite3 -noheader "$DB" "SELECT '           ' || COUNT(*) || '  step=' || COALESCE(step,'?') || '  ' || COALESCE(signature,'?') FROM ingest_quarantine GROUP BY step, signature ORDER BY COUNT(*) DESC LIMIT 5;" 2>/dev/null || true
    fi
  fi
  local log; log="$(_latest_log)"
  if [ -n "$log" ]; then
    say "run log tail ($log):"
    tail -n 15 "$log" || true
  else
    warn "no run log yet — nothing has been started"
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
cmd_stop(){
  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    warn "sending Ctrl+C to tmux session '$TMUX_SESSION'"
    tmux send-keys -t "$TMUX_SESSION" C-c
  else
    local pid pgid
    pid="$(_ingest_pids | head -1)"
    if [ -z "$pid" ]; then warn "no ingest process found — nothing to stop"; return 1; fi
    pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
    warn "sending SIGINT to process group $pgid (ingest pid $pid)"
    kill -s INT -- "-$pgid" || { err "kill failed"; return 1; }
  fi
  local i
  for i in 1 2 3 4 5; do _ingest_pids | grep -q . || break; sleep 1; done
  if _ingest_pids | grep -q .; then err "ingest still running — giving it one SIGTERM"; pkill -f "archive/ingest_batch.py" || true
  else ok "ingest stopped"; fi
}

# ─────────────────────────────────────────────────────────────────────────────
cmd_help(){
  cat <<EOF
ingest.sh — drive + watch the sound-archive batch ingest

USAGE
  ./ingest.sh <run|watch|status|stop|preflight|help> [options]

COMMANDS
  run [--samples PATH] [--embedder clap-remote|clap|melstats]
      [--endpoint URL] [--env-file PATH]
      [--tmux | --herdr | --foreground] [--no-preflight] [--limit N]
      [--dry-run] [--force]
        Start/resume the ingest. Default: detached tmux session 'ingest'.
        --herdr      only inside a herdr pane (HERDR_ENV=1); splits a sibling pane.
        --foreground run in this shell (use inside a herdr pane you created).
        --force      stop any running ingest first.
        Fail-closed: refuses to start unless <endpoint>/readyz is ok:true and the
        env file has EMBED_API_KEY.

  watch [--stats] [--log FILE]
        Tail the run log (~/.workchain/runs/latest.log). --stats also polls the
        serve count every 30s.

  status        Is it running (tmux/pane/pid)? last log lines + DB count.
  stop          Ctrl+C to the ingest (tmux send-keys C-c, else SIGINT to its group).
  preflight     Check endpoint /readyz + key. Exits non-zero if not ready.
  help          This message.

DEFAULTS
  samples    $DEFAULT_SAMPLES
  embedder   clap-remote          (chain archive-ingest-clap-remote.yaml)
  endpoint   \$EMBED_CLAP_ENDPOINT or $DEFAULT_ENDPOINT
  env-file   $DEFAULT_ENV_FILE    (sourced for EMBED_API_KEY / EMBED_CLAP_ENDPOINT)
  db         $DB

CHECK-IN TOOLKIT
  Logs (terminal-agnostic)
    ./ingest.sh watch --stats
    tail -f ~/.workchain/runs/latest.log

  Progress / index state
    curl -s http://127.0.0.1:8788/api/stats
    sqlite3 ~/.sound-archive/archive.db "SELECT COUNT(*), MAX(indexed_at) FROM assets;"

  tmux (default launch)
    tmux list-sessions
    tmux attach -t ingest            (detach: Ctrl-b d)
    tmux send-keys -t ingest C-c     (stop — same as ./ingest.sh stop)

  herdr (from inside your herdr session)
    herdr workspace list
    herdr tab list --workspace <id>
    herdr pane read <pane> --source recent-unwrapped --lines 80
    herdr pane wait-output <pane> --match "resume:" --timeout 600000
    herdr pane send-keys <pane> ctrl+c

CUTOVER GATES (Part E of the serve-embed playbook)
  [3/4] resume: N already indexed, M to ingest   → N must be >= 63,151 (the baseline)
  Fresh sidecars  (~/.sound-archive/work/<hash>/archive/*.embedding.json):
      "served_by": "remote", "device": "cuda", "elapsed_ms" in the low hundreds
  Expect throughput far above the old ~275 files/hour (no more 2 GB load per file).
EOF
}

# ─────────────────────────────────────────────────────────────────────────────
main(){
  local cmd="${1:-help}"; [ $# -gt 0 ] && shift || true
  case "$cmd" in
    run|start) cmd_run "$@";;
    watch)     cmd_watch "$@";;
    status)    cmd_status;;
    stop)      cmd_stop;;
    preflight) cmd_preflight "$@";;
    help|-h|--help) cmd_help;;
    *) err "unknown command: $cmd"; cmd_help; exit 1;;
  esac
}

main "$@"
