# Specification-driven development workflow

## Artifacts
- **Issue:** problem, scope, acceptance criteria and non-goals.
- **Design:** technical decisions and risks; short Issue plan is enough for a small change, `docs/design/` for substantial work.
- **Draft PR:** code, tests, evidence, review feedback, and preview instructions.

## Simple agent-led lifecycle
1. **Issue + plan.** Agent clarifies requirements and inspects code; human approves substantial/risky implementation plans.
2. **Draft PR.** Agent implements on a branch, writes tests, documents changes, and opens a Draft PR linked to the Issue.
3. **Automated checks + independent agent review.** Agent investigates failures, fixes code, reruns CI, and reports gaps. CI green alone is not acceptance.
4. **Local acceptance.** Human opens the exact PR version with `bash scripts/preview.sh <PR-number>`, checks the relevant UI/user journeys, and reports pass/fail. For test-only or docs-only PRs, record why manual UI verification is not applicable.
5. **Human merge approval.** Only after CI, review and acceptance does the human explicitly authorize merging. Agents must not infer authorization from a green check, an approved design, or a comment that tests passed.
6. **Merge and close.** After authorization, squash-merge into `main`, check post-merge CI, and close the linked Issue only if all acceptance criteria are fulfilled. Use `Fixes #N` only when the PR fully resolves the Issue; otherwise use `Refs #N` and keep it open.

**Close without merge** rejects a PR's changes; it is not the normal completion path.

## Local PR preview (macOS)
Run from the main checkout at `~/DroneStock`:

```bash
cd ~/DroneStock
bash scripts/preview.sh 3
```

Open **http://localhost:8503**. PR #4 uses port 8504, etc. The script fetches the PR's latest commit into a detached Git worktree at `~/.dji-stock-previews/pr-<number>`, leaves the main checkout untouched, reuses the existing `.venv312` or `.venv` Python environment and local Ollama, and runs Streamlit in the foreground. Press **Ctrl+C** to stop. Repeat the command to refresh the PR version. If the preview worktree has uncommitted changes, the script refuses to overwrite them.

**Important:** preview instances share the existing `~/DroneStock/originals`, `metadata`, `exports`, and other runtime data because application paths are hardcoded. UI decisions (approve/reject/undo/export) can modify real review data. Do not perform destructive actions on valuable records during acceptance; no isolation or automatic cleanup is provided. The script itself never runs batch processing or exports. Local URLs are accessible only on the Mac and only while the process runs.

**Prerequisites:** Git, Python >=3.11 in `.venv312` or `.venv`, `pip install -e .`, FFmpeg for video previews, and existing candidate metadata for meaningful UI review. Ollama models are only required for AI processing, not opening the review UI. See `docs/setup.md` and `docs/testing.md`.

**Port conflicts:** only one process can use a given port; stop the previous preview instance before restarting the same PR. The URL uses a stable port per PR, but is not an internet deployment. PR numbers above the available TCP port range are rejected.

## Review evidence
For each PR, record the tested commit SHA, CI outcome, agent review outcome, whether local acceptance was run (and on what OS), and any known limitations. A later code change requires rechecking affected acceptance criteria.

## Design document template
Status (Draft / Approved / Superseded); linked Issue; problem and use cases; acceptance criteria; observed behavior; assumptions and non-goals; alternatives and decision; affected modules; implementation plan; test matrix; data safety; rollback; open questions.
