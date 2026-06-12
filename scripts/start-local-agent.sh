#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONUNBUFFERED=1

echo "[guarded-alpha] repo: $ROOT_DIR"
echo "[guarded-alpha] running preflight"
uv run guarded-alpha-preflight

cleanup() {
  echo
  echo "[guarded-alpha] stopping local processes"
  jobs -pr | xargs -r kill
}
trap cleanup EXIT INT TERM

echo "[guarded-alpha] starting API on http://127.0.0.1:8000"
uv run guarded-alpha-api &

echo "[guarded-alpha] starting hourly scheduler"
uv run guarded-alpha-scheduler &

echo "[guarded-alpha] starting web console on http://127.0.0.1:5173"
pnpm -C apps/web dev &

echo
echo "[guarded-alpha] local agent is running"
echo "[guarded-alpha] open http://127.0.0.1:5173"
echo "[guarded-alpha] leave this terminal open; press Ctrl-C to stop"

wait
