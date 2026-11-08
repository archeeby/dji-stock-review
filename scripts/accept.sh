#!/usr/bin/env bash
# Bootstrap the PR's acceptance runner, never the stale runner from main.
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: bash scripts/accept.sh <PR-number>" >&2
  exit 2
fi
pr="$1"
repo="${DJI_STOCK_REPO:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
export DJI_STOCK_REPO="$repo"
export DJI_STOCK_ROOT="${DJI_STOCK_ROOT:-$(dirname -- "$repo")}"
target="$HOME/.dji-stock-previews/pr-$pr"
[[ -e "$repo/.git" ]] || { echo "Missing repository: $repo" >&2; exit 1; }
git -C "$repo" fetch --no-tags origin "pull/$pr/head"
sha="$(git -C "$repo" rev-parse FETCH_HEAD)"
mkdir -p "$(dirname "$target")"
if [[ -e "$target" ]]; then
  [[ -f "$target/.git" ]] || { echo "Refusing non-worktree path: $target" >&2; exit 1; }
  [[ -z "$(git -C "$target" status --porcelain)" ]] || { echo "Worktree has local changes: $target" >&2; exit 1; }
  git -C "$target" checkout --detach "$sha"
else
  git -C "$repo" worktree add --detach "$target" "$sha"
fi
[[ -f "$target/scripts/accept.py" ]] || { echo "PR runner missing" >&2; exit 1; }
repo_workspace="$(dirname -- "$repo")"
for python in "$repo_workspace/.venv312/bin/python" "$repo_workspace/.venv/bin/python" "$repo/.venv312/bin/python" "$repo/.venv/bin/python" "$DJI_STOCK_ROOT/.venv312/bin/python" "$DJI_STOCK_ROOT/.venv/bin/python"; do
  if [[ -x "$python" ]] && "$python" -c 'import sys, streamlit; assert sys.version_info[:2] == (3, 12)' >/dev/null 2>&1; then
    echo "Bootstrapped PR #$pr at $sha; running PR-owned acceptance runner"
    exec "$python" "$target/scripts/accept.py" "$pr"
  fi
done
echo "Python virtualenv not found under $DJI_STOCK_ROOT" >&2
exit 1
