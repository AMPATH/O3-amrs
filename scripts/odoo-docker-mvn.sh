#!/usr/bin/env bash
# Run Maven for odoo-docker after SDKMAN init (same as: source ~/.sdkman/bin/sdkman-init.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"
if [[ ! -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]]; then
  echo "SDKMAN not found. Install: https://sdkman.io (expected \$SDKMAN_DIR/bin/sdkman-init.sh)" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$SDKMAN_DIR/bin/sdkman-init.sh"
cd "$ROOT"
# Optional: apply .sdkmanrc (ignore if id does not match an installed Java)
if [[ -f .sdkmanrc ]]; then
  sdk env 2>/dev/null || true
fi
cd "$ROOT/odoo-docker"
exec mvn "$@"
