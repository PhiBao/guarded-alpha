#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FORCE_RESTART=false
if [[ "${1:-}" == "--force" ]]; then
  FORCE_RESTART=true
fi

export PYTHONUNBUFFERED=1
export GUARDED_ALPHA_LOG_FORMAT="${GUARDED_ALPHA_LOG_FORMAT:-compact}"

echo "[guarded-alpha] repo: $ROOT_DIR"

if [[ "$FORCE_RESTART" == "true" ]]; then
  echo "[guarded-alpha] force restart requested"
  scheduler_pids="$(pgrep -f "guarded-alpha-scheduler" || true)"
  if [[ -n "$scheduler_pids" ]]; then
    printf '%s\n' "$scheduler_pids" | xargs -r kill
    sleep 1
    scheduler_pids="$(pgrep -f "guarded-alpha-scheduler" || true)"
    if [[ -n "$scheduler_pids" ]]; then
      printf '%s\n' "$scheduler_pids" | xargs -r kill -9
    fi
  fi
  rm -f data/scheduler.lock data/KILL_SWITCH
fi

echo "[guarded-alpha] running preflight"
preflight_json="$(uv run guarded-alpha-preflight)"
printf '%s\n' "$preflight_json" | python3 -c '
import json
import sys

checks = json.load(sys.stdin)
failed = [check for check in checks if not check.get("ok")]
for check in checks:
    mark = "OK" if check.get("ok") else "FAIL"
    name = check.get("name", "unknown")
    detail = check.get("detail", "")
    print(f"[guarded-alpha] {mark:<4} {name}: {detail}")
if failed:
    print("[guarded-alpha] preflight failed; refusing to start scheduler")
    sys.exit(1)
'

cleanup() {
  echo
  echo "[guarded-alpha] stopping local processes"
  jobs -pr | xargs -r kill
}
trap cleanup EXIT INT TERM

# echo "[guarded-alpha] starting API on http://127.0.0.1:8000"
# uv run guarded-alpha-api &

echo "[guarded-alpha] starting scheduled scanner"
uv run guarded-alpha-scheduler &

# echo "[guarded-alpha] starting web console on http://127.0.0.1:5173"
# pnpm -C apps/web dev &

echo
echo "[guarded-alpha] local agent is running"
# echo "[guarded-alpha] open http://127.0.0.1:5173"
# echo "[guarded-alpha] leave this terminal open; press Ctrl-C to stop"

wait
