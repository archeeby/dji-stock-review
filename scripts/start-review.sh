#!/bin/bash
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export DJI_STOCK_ROOT="${DJI_STOCK_ROOT:-$(dirname -- "$repo")}"
cd "$repo"
repo_workspace="$(dirname -- "$repo")"
for python in "$repo_workspace/.venv312/bin/python" "$repo_workspace/.venv/bin/python" "$repo/.venv312/bin/python" "$repo/.venv/bin/python" "$DJI_STOCK_ROOT/.venv312/bin/python" "$DJI_STOCK_ROOT/.venv/bin/python"; do
  if [[ -x "$python" ]] && "$python" -c 'import sys, streamlit; assert sys.version_info >= (3, 11)' >/dev/null 2>&1; then
    exec "$python" -m streamlit run review_app.py "$@"
  fi
done
echo "No working Python + Streamlit environment found; see docs/setup.md" >&2
exit 1
