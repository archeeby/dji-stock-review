#!/bin/bash
set -euo pipefail
WORKSPACE="$HOME/DroneStock"
cd "$WORKSPACE/dji-stock-review"
exec "$WORKSPACE/.venv312/bin/python" -m streamlit run review_app.py "$@"
