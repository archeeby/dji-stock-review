#!/usr/bin/env bash
# Bootstrap the PR's acceptance runner, never the stale runner from main.
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: bash scripts/accept.sh <PR-number>" >&2
  exit 2
fi
pr="$1"
repo="$HOME/DroneStock"
target="$HOME/.dji-stock-previews/pr-$pr"
[[ -d "$repo/.git" ]] || { echo "Missing repository: $repo" >&2; exit 1; }
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
for python in "$repo/.venv312/bin/python" "$repo/.venv/bin/python"; do
  if [[ -x "$python" ]]; then
    echo "Bootstrapped PR #$pr at $sha; running PR-owned acceptance runner"
    exec "$python" "$target/scripts/accept.py" "$pr"
  fi
done
echo "Python virtualenv not found under ~/DroneStock" >&2
exit 1
