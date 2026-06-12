#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UV_BIN="$(command -v uv)"
TEMPLATE_DIR="$ROOT_DIR/ops/systemd"

mkdir -p "$SYSTEMD_DIR"

render_unit() {
  local template="$1"
  local output="$2"
  sed \
    -e "s|{{PROJECT_DIR}}|$ROOT_DIR|g" \
    -e "s|{{UV_BIN}}|$UV_BIN|g" \
    -e "s|{{PATH}}|$PATH|g" \
    "$template" > "$output"
}

render_unit "$TEMPLATE_DIR/guarded-alpha-api.service.template" "$SYSTEMD_DIR/guarded-alpha-api.service"
render_unit "$TEMPLATE_DIR/guarded-alpha-scheduler.service.template" "$SYSTEMD_DIR/guarded-alpha-scheduler.service"

systemctl --user daemon-reload
systemctl --user enable --now guarded-alpha-api.service
systemctl --user enable --now guarded-alpha-scheduler.service

echo "[guarded-alpha] installed user services"
echo "[guarded-alpha] api:       systemctl --user status guarded-alpha-api.service"
echo "[guarded-alpha] scheduler: systemctl --user status guarded-alpha-scheduler.service"
echo "[guarded-alpha] keep running after logout: loginctl enable-linger \"$USER\""
