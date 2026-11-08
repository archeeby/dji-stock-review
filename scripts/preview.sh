#!/usr/bin/env bash
# Run a pull request's Streamlit UI on localhost without switching the main checkout.
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: bash scripts/preview.sh <PR-number> (e.g. 3)" >&2
  exit 2
fi

pr="$1"
port=$((8500 + pr))
if (( port > 65535 )); then
  echo "PR number too large for a local TCP port" >&2
  exit 2
fi

repo="${DJI_STOCK_REPO:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
export DJI_STOCK_REPO="$repo"
export DJI_STOCK_ROOT="${DJI_STOCK_ROOT:-$(dirname -- "$repo")}"
if [[ ! -e "$repo/.git" ]]; then
  echo "Main checkout not found at $repo." >&2
  exit 1
fi

python=""
repo_workspace="$(dirname -- "$repo")"
for candidate in "$repo_workspace/.venv312/bin/python" "$repo_workspace/.venv/bin/python" "$repo/.venv312/bin/python" "$repo/.venv/bin/python" "$DJI_STOCK_ROOT/.venv312/bin/python" "$DJI_STOCK_ROOT/.venv/bin/python"; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import sys, streamlit; assert sys.version_info >= (3, 11)' >/dev/null 2>&1; then
    python="$candidate"
    break
  fi
done
if [[ -z "$python" ]]; then
  echo "No working Python >=3.11 + Streamlit found in .venv312 or .venv." >&2
  echo "See docs/setup.md; on macOS: /opt/homebrew/bin/python3.12 -m venv .venv312 && .venv312/bin/python -m pip install -e ." >&2
  exit 1
fi

preview_root="$HOME/.dji-stock-previews"
worktree="$preview_root/pr-$pr"
mkdir -p "$preview_root"

echo "Fetching current head of PR #$pr..."
git -C "$repo" fetch --no-tags origin "pull/$pr/head"
sha="$(git -C "$repo" rev-parse --verify FETCH_HEAD^{commit})"
if [[ -n "${DJI_EXPECTED_PR_SHA:-}" && "$sha" != "$DJI_EXPECTED_PR_SHA" ]]; then
  echo "PR HEAD changed: expected $DJI_EXPECTED_PR_SHA, got $sha. Refusing preview." >&2
  exit 1
fi

if [[ -e "$worktree" ]]; then
  if [[ ! -f "$worktree/.git" ]]; then
    echo "Refusing to use existing non-worktree directory: $worktree" >&2
    exit 1
  fi
  if [[ -n "$(git -C "$worktree" status --porcelain)" ]]; then
    echo "Preview worktree has local changes; refusing to overwrite: $worktree" >&2
    exit 1
  fi
  git -C "$worktree" -c advice.detachedHead=false checkout --detach "$sha"
else
  git -C "$repo" worktree add --detach "$worktree" "$sha"
fi

echo "PR #$pr at $sha"
echo "Preview: http://localhost:$port"
echo "Press Ctrl+C to stop. The existing $DJI_STOCK_ROOT data is SHARED and UI actions can modify it."
cd "$worktree"
exec "$python" -m streamlit run review_app.py --server.address 127.0.0.1 --server.port "$port" --server.headless true
