# Specification-driven development workflow

## Artifacts
- **Issue:** problem, scope, acceptance criteria and non-goals.
- **Design:** technical decisions and risks; short Issue plan is enough for a small change, `docs/design/` for substantial work.
- **Draft PR:** code, tests, evidence, review feedback, and preview instructions.

## Simple agent-led lifecycle
1. **Issue + plan.** Agent clarifies requirements and inspects code; human approves substantial/risky implementation plans.
2. **Draft PR.** Agent implements on a branch, writes tests, documents changes, and opens a Draft PR linked to the Issue.
3. **Automated checks + independent agent review.** Agent investigates failures, fixes code, reruns CI, and reports gaps. All applicable CI jobs must finish successfully on the latest PR HEAD SHA; CI green alone is not acceptance.
4. **Local acceptance.** Human opens the exact PR version with `bash scripts/preview.sh <PR-number>`, checks the relevant UI/user journeys, and reports pass/fail. For test-only or docs-only PRs, record why manual UI verification is not applicable.
5. **Human merge approval.** Only after verified green CI on the latest HEAD, independent review and applicable local acceptance does the human explicitly authorize merging this PR. Agents must not infer authorization from a green check, an approved design, or a comment that tests passed.
6. **Merge and close.** Immediately before merge, re-fetch the PR HEAD and revalidate CI for that SHA. After authorization, use **Create a merge commit** into `main` by default (not squash/rebase), check post-merge CI, and close the linked Issue only if all acceptance criteria are fulfilled. Use `Fixes #N` only when the PR fully resolves the Issue; otherwise use `Refs #N` and keep it open.

## Strict CI merge gate — no exceptions
1. Fetch the current PR HEAD commit SHA and the status of **every applicable GitHub Actions job**, including every required OS/Python matrix job. Verify checks are associated with that SHA, have completed, and all have a successful conclusion. Do not mistake a successful subset for an overall pass.
2. If any check is queued/in progress, **wait and poll again**. If a check failed, timed out, was cancelled, is missing, or its status cannot be verified, **block merge**. Tell the owner exactly which checks failed or are pending. Investigate and fix failures without weakening tests to obtain green CI; rerun on a new SHA.
3. Recheck the HEAD SHA and CI immediately before the actual merge operation. If the SHA changed, previous validation and any affected acceptance are stale: repeat them.
4. No agent may merge without the owner's **explicit authorization for this particular PR**, even with green CI and accepted UI. No auto-merge or bypass. A design approval is not merge approval.
5. After merge, verify and report post-merge CI on `main`. If it fails, report failure and investigate; never claim post-merge success while checks are running.
6. Branch protection is deferred; agents must enforce these instructions even when GitHub would technically allow merging.

## Human involvement is intentionally minimal
The agent handles Issue, branch, Draft PR, implementation, tests, review, failure resolution, preview instructions, merge after permission, and follow-up. The owner only approves substantial/risky plans, performs relevant local acceptance (or accepts a documented N/A), and explicitly authorizes each merge. Default merge strategy is **Create a merge commit** to preserve ancestry for parallel/dependent branches.

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
