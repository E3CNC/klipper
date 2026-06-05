#!/usr/bin/env bash
# Deploy E3CNC Klipper plugins to the attic CNC machine.
# Run from repo root: bash deploy.sh
# Requires passwordless SSH key auth to be set up first (see .scratch/ssh-deploy/brief.md).
set -euo pipefail

HOST="${KLIPPER_HOST:-cnc-laptop}"
REMOTE_EXTRAS="~/klipper/klippy/extras"

# Add plugin files here as the E3CNC branch grows.
FILES=(
  "klippy/extras/work_coordinate_systems.py"
)

echo "Deploying to $HOST..."
for f in "${FILES[@]}"; do
  echo "  -> $f"
  scp "$f" "$HOST:$REMOTE_EXTRAS/$(basename "$f")"
done

echo "Restarting Klipper..."
ssh "$HOST" "sudo systemctl restart klipper"

echo ""
echo "Done."
echo "If work_coordinate_systems is new, add to printer.cfg:"
echo "  [work_coordinate_systems]"
