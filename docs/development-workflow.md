# Specification-driven development workflow

## Artifacts
- **Issue:** problem, scope, acceptance criteria and non-goals.
- **Design:** technical decisions and risks; short Issue plan is enough for a small change, `docs/design/` for substantial work.
- **Draft PR:** code, tests, evidence, review feedback, and preview instructions.

## Simple agent-led lifecycle
1. **Issue + plan.** Agent clarifies requirements and inspects code; human approves substantial/risky implementation plans.
2. **Draft PR.** Agent implements on a branch, writes tests, documents changes, and opens a Draft PR linked to the Issue.
3. **Automated checks + independent agent review.** Agent investigates failures, fixes code, reruns CI, and reports gaps. All applicable CI jobs must finish successfully on the latest PR HEAD SHA; CI green alone is not acceptance.
4. **Local acceptance (one human touchpoint).** Agent selects required local integration/E2E checks for the PR. Human runs them and the relevant Streamlit preview in one acceptance session, checks user journeys, and reports pass/fail. Use `bash scripts/accept.sh <PR-number>` for one-command local acceptance. It runs the applicable local tests and opens the Streamlit preview only after tests pass. The user must still explicitly confirm UI acceptance and authorize merge. For docs-only/test-only PRs, record N/A for inapplicable checks and UI verification.
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

## Local integration/E2E acceptance policy
- CI should automatically run unit and feasible lightweight real-media integration checks. The agent chooses additional local tests based on affected behavior: FFmpeg/OpenCV/ExifTool and representative real footage for video-processing changes; Ollama E2E for AI/pipeline changes; no heavyweight Ollama for unrelated docs/UI PRs.
- `scripts/accept.sh <PR-number>` fetches the PR HEAD into a detached worktree, selects a conservative docs/unit/media/ai profile from changed paths, checks prerequisites, executes the local unittest suite and required AI E2E where available, records SHA/results/logs under `~/.dji-stock-acceptance/`, and starts Streamlit preview **only after required tests pass**. Media acceptance requires `tests/test_real_dji_tools.py`; AI acceptance requires `tests/test_ollama_e2e.py`. Missing suites fail closed rather than falsely passing. Current Streamlit preview still shares real runtime data. Tests must use temporary directories.
- Local tests must not mutate originals, existing AI metadata, or user review/export data. Existing preview is not isolated and shares real runtime directories; avoid destructive acceptance actions and disclose that limitation.
- Required local tests are a merge gate alongside CI, independent review, applicable manual acceptance, and explicit owner approval. Failed, missing, or unverified required local tests block merge. Altering the required test scope requires explicit owner agreement. New PR commits invalidate affected acceptance/test evidence.
- Record the applicable test matrix and any N/A rationale in the PR. UI acceptance can be N/A for docs/test-only PRs.

## One-command local PR acceptance (macOS)
Run from the main checkout after updating `main`:

```bash
cd ~/workspace/DroneStock/dji-stock-review
bash scripts/accept.sh 9
```

The command fetches the current PR, runs applicable local tests, writes `~/.dji-stock-acceptance/pr-9/<SHA>/result.json` and `tests.log`, then starts the PR's Streamlit preview if tests pass. It does **not** record manual UI approval; tell the agent whether the UI was accepted. Docs-only PRs mark local checks N/A. If required real-tool or Ollama E2E suites are absent, acceptance blocks until implemented. Check the result SHA against the PR before merge; CI remains a separate mandatory gate.

## Local PR preview (macOS)
Run from the main checkout at `~/workspace/DroneStock/dji-stock-review`:

```bash
cd ~/workspace/DroneStock/dji-stock-review
bash scripts/preview.sh 3
```

Open **http://localhost:8503**. PR #4 uses port 8504, etc. The script fetches the PR's latest commit into a detached Git worktree at `~/.dji-stock-previews/pr-<number>`, leaves the main checkout untouched, reuses the existing `.venv312` or `.venv` Python environment and local Ollama, and runs Streamlit in the foreground. Press **Ctrl+C** to stop. Repeat the command to refresh the PR version. If the preview worktree has uncommitted changes, the script refuses to overwrite them.

**Important:** preview instances share the existing `~/workspace/DroneStock/originals`, `metadata`, `exports`, and other runtime data through the explicit `DJI_STOCK_ROOT` inherited by the preview worktree. UI decisions (approve/reject/undo/export) can modify real review data. Do not perform destructive actions on valuable records during acceptance; no isolation or automatic cleanup is provided. The script itself never runs batch processing or exports. Local URLs are accessible only on the Mac and only while the process runs.

**Prerequisites:** Git, Python >=3.11 in `.venv312` or `.venv`, `pip install -e .`, FFmpeg for video previews, and existing candidate metadata for meaningful UI review. Ollama models are only required for AI processing, not opening the review UI. See `docs/setup.md` and `docs/testing.md`.

**Port conflicts:** only one process can use a given port; stop the previous preview instance before restarting the same PR. The URL uses a stable port per PR, but is not an internet deployment. PR numbers above the available TCP port range are rejected.

## Review evidence
For each PR, record the tested commit SHA, CI outcome, agent review outcome, whether local acceptance was run (and on what OS), and any known limitations. A later code change requires rechecking affected acceptance criteria.

## Design document template
Status (Draft / Approved / Superseded); linked Issue; problem and use cases; acceptance criteria; observed behavior; assumptions and non-goals; alternatives and decision; affected modules; implementation plan; test matrix; data safety; rollback; open questions.
