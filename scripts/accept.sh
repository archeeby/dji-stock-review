#!/usr/bin/env bash
# One-command local PR acceptance. Run with: bash scripts/accept.sh <PR-number>
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: bash scripts/accept.sh <PR-number>" >&2
  exit 2
fi
repo="$HOME/DroneStock"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for python in "$repo/.venv312/bin/python" "$repo/.venv/bin/python"; do
  if [[ -x "$python" ]]; then
    exec "$python" "$script_dir/accept.py" "$1"
  fi
done
echo "Python virtualenv not found under ~/DroneStock" >&2
exit 1
