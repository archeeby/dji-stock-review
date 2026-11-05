# Agent instructions — DJI Stock Review

## Purpose
This repository contains a Python/Streamlit application for reviewing DJI drone footage, selecting candidate clips, editing trims and metadata, and preparing exports for stock marketplaces.

Treat this document as shared guidance for coding agents. The assigned issue and its acceptance criteria define the scope of each task. If instructions conflict or a destructive operation is unclear, stop and ask.

## Code map
- `review_app.py`: Streamlit review interface and preview flow.
- `candidate_reviews.py`: candidate-specific review identity, persisted decisions, and undo.
- `review_navigation.py`: deterministic navigation after review decisions.
- `trim_bounds.py`: trim validation and minimum clip duration.
- `export_approved.py`: approved-video export.
- `export_stock_platforms.py` and `stock/platforms/`: stock marketplace outputs.
- `run_pipeline.py`, `run_batch.py`, and `metadata_enrichment.py`: processing and enrichment.
- `tests/` and `test_*.py`: automated tests (inspect actual test locations before running).

Read relevant implementation and tests before changing behavior; this map is not exhaustive.

## Non-negotiable data safety
- Never modify, overwrite, move, or delete original footage in `originals/`.
- Never delete or rewrite existing AI analysis or source metadata under `metadata/` unless the user explicitly authorizes a specific migration.
- Treat `exports/`, `previews/`, `covers/`, and `platforms/` as local generated data, not source code. Do not commit videos, user data, secrets, or generated upload CSVs.
- Revoking approval may remove only the matching generated approved export and its sidecar; it must not affect source footage, metadata, or other candidates.
- Do not run broad cleanup commands or destructive batch processing against the user's local library. Prefer isolated temporary fixtures for tests.
- Respect `.gitignore`; do not bypass it to stage local assets.

## Review behavior to preserve
- Candidate identity and status are scoped to the original source and candidate ID; actions on one candidate must not change another.
- Approve/Reject and Undo must preserve intended candidate edits and the active filter; Undo returns the decision to its previous state as implemented.
- After a decision, navigation should prefer the next pending candidate from the same original video when applicable.
- Clip trim validation must enforce the project's minimum duration (currently 5 seconds); use existing validation helpers instead of duplicating rules.
- Preserve preview stability and existing Streamlit interaction semantics when changing UI behavior.

## Collaborative task discovery and architecture-first workflow
Follow `docs/development-workflow.md` for the Issue → design/implementation plan → PR process. The proposed test-coverage work is documented as a **draft** in `docs/design/baseline-test-coverage.md`; implementation requires design approval.

The human owner may describe tasks conversationally or by voice. A spoken request is the **start of discovery**, not automatic authorization to implement.

1. **Discuss the problem first.** The planning assistant clarifies the goal, user-visible behavior, constraints, edge cases, and success criteria. Ask focused questions rather than turning an incomplete request directly into code.
2. **Inspect the existing system.** For changes beyond a trivial fix, review the relevant code, tests, data flow, module boundaries, dependencies, and established patterns before proposing a solution. Distinguish verified facts about the repository from assumptions.
3. **Design proportionately.** For a small, low-risk change, use a short implementation plan. For complex, architectural, cross-module, data-sensitive, or high-risk work, discuss options, trade-offs, compatibility, failure handling, performance, security, test strategy, and best practices. Explicitly identify the modules and interfaces expected to change.
4. **Agree on a plan before coding.** Present the recommended approach, alternatives where meaningful, ordered implementation steps, acceptance criteria, validation strategy, and outstanding risks. For complex changes, **obtain explicit human approval of the implementation plan** before delegating or editing code. Record substantial decisions as a concise RFC under `docs/design/` when useful; avoid unnecessary documentation for simple fixes.
5. **Delegate a bounded task.** After approval, create or update a GitHub Issue (when available) containing the agreed scope, technical decisions, acceptance criteria, test expectations, and non-goals. The implementer works on a feature branch and opens a pull request. Do not treat a draft plan or issue as permission to start implementation when approval is required.
6. **Validate and independently review.** Run appropriate automated tests and CI; add integration or end-to-end tests when the change warrants them. An independent reviewer checks the diff against the agreed plan, architecture, correctness, security, data safety, and regressions. Report which checks were real versus mocked and which environments were not tested.
7. **Resolve feedback, then request merge approval.** Address review and CI findings, repeat validation, summarize results and residual risks, and leave the final merge decision to the human owner.

**Change control:** An implementer must not silently diverge from an approved architecture or expand the scope. If implementation reveals a material design problem, stop, document the finding and options, and return to the planning discussion for a decision. Routine implementation details within the approved scope do not require repeated approval.

**Roles:** The planning assistant acts as technical discussion partner and coordinates design and review; the implementer writes code; an independent agent reviews; the human owner approves significant plans and merges. Voice is an input method, not a shortcut around design or human approval.

## Mandatory agent delivery and merge gate (MUST FOLLOW)
- Minimize human effort: agent owns Issue creation, scoped implementation branch, Draft PR, tests, independent review, failure triage, preview instructions, merge execution after approval, post-merge checks and Issue closure when fully complete. Human involvement is limited to significant design approval, relevant acceptance, and explicit final merge authorization.
- Every implementation must be tracked in a GitHub Issue and developed via a separate branch and Draft PR. Discuss and obtain approval before substantial or risky implementation; routine in-scope implementation and CI fixes do not require repeated human confirmation.
- Before asking for merge permission AND immediately before merging, fetch the latest PR HEAD SHA and verify all applicable GitHub Actions jobs/checks for that exact SHA are completed successfully. Do not rely on a previous commit, a green badge on another branch, or a partial success. Check all required matrix jobs, not just the workflow's existence.
- If checks are queued or running, wait and recheck. If any check fails, times out, is cancelled, is missing, or its status cannot be verified, **DO NOT MERGE**. Tell the human which check failed or is unavailable, investigate and fix when possible, push changes, and wait for fresh green CI.
- If the PR HEAD changes after validation, invalidate previous evidence and recheck CI, review, and affected acceptance for the new SHA.
- A green CI is necessary but insufficient. Independent review and relevant human local acceptance must be recorded; docs/test-only changes may mark UI acceptance N/A with a reason.
- **NEVER MERGE WITHOUT EXPLICIT HUMAN APPROVAL FOR THAT PR.** Approval of a plan, successful tests, or an earlier PR is not merge authorization. Never use auto-merge as a workaround.
- Default to GitHub **Create a merge commit** (not squash or rebase) to preserve branch ancestry. Deviations require explicit human agreement.
- After merging, inspect post-merge main CI and report any failures; close the linked Issue only if its full acceptance criteria are met. Do not claim a successful post-merge CI before it finishes.
- GitHub branch protection is not currently configured; these rules remain mandatory for all agents regardless.

## Test integrity and failure triage
Tests exist to verify **real, agreed user behavior**, not to make CI green. Never weaken, delete, skip, rewrite assertions, alter fixtures, or increase mocks solely to make a failing test pass.

- Derive tests from explicit user journeys, requirements, regressions, and realistic edge cases. Unit tests and synthetic fixtures are useful for deterministic logic, but they do not replace representative real-media integration and end-to-end tests where actual FFmpeg, ExifTool, OpenCV, Ollama models, and filesystem behavior matter. Label mocked tests clearly and never present them as proof that the full pipeline works.
- Prefer small, legally usable, representative MP4 fixtures and real tool invocations for integration coverage; keep private originals and generated data out of Git. External services and large AI models may require a separate opt-in/local or dedicated-runner workflow. Document test coverage gaps honestly.
- On any failure, **investigate before changing anything**: reproduce it, inspect the error and relevant diff, identify the expected use case, and determine whether the failure reflects a product regression, an intentional behavior change, an invalid or brittle test, an environment/dependency issue, or a flaky test.
- Explain what broke, its user impact, and the viable fixes. If the intended behavior changed, update the specification and test **only after agreement**; if the existing use case remains valid, fix the production code. If the test itself is incorrect, fix it while preserving meaningful assertions. For significant or ambiguous failures, discuss the diagnosis and options with the human owner before choosing a fix.
- Do not silently change a test to match current implementation, mask failures with mocks, suppress exceptions, or bypass CI. Every test change accompanying a failure must include a rationale tied to expected behavior and evidence that the corrected test still detects the regression.
- Rerun affected tests and relevant regression suites after the fix. Report which cases passed, what was mocked, what was tested with real tools/media/models, and any unverified scenarios.

## Working agreement
1. Read the task, acceptance criteria, and affected code before editing.
2. For nontrivial changes, briefly state a plan and identify data-loss or regression risks.
3. Keep the change minimal and focused. Avoid unrelated refactoring and new dependencies without justification.
4. Add or update tests for changed behavior, especially candidate isolation, undo, trimming, and export deletion.
5. Run the relevant tests; use `python -m unittest discover -s tests -v` for the existing unittest suite. Report exactly what ran and any failures or environment limitations.
6. Review the diff for accidental changes, secrets, generated files, and destructive behavior.
7. Deliver a concise summary, test evidence, and any unresolved risks. Prefer a feature branch and pull request; do not merge to `main` without human approval.

## Agent roles
- **Implementer** (Codex or Claude Code): change code and tests in a scoped branch.
- **Independent reviewer** (preferably the other model): review the issue, diff, and test evidence; prioritize correctness, data safety, regressions, and missing test cases. Do not silently modify the implementer's branch during review.
- **Human owner**: decides whether to merge and authorizes any destructive or irreversible action.

AI review is advisory; tests and explicit human approval remain required. Do not claim tests passed unless they actually ran.

## Engineering standards
- Read and follow `docs/development-guidelines.md` for new and materially changed code. Treat existing deviations as technical debt to address through approved, behavior-preserving refactoring, not as permission to broaden an unrelated task.
- Establish meaningful behavior and real-video integration coverage before substantial refactoring; do not confuse mocked tests with full pipeline validation.

## Project onboarding and portability
- Read `README.md`, `docs/architecture.md`, and `docs/setup.md` before changing pipeline, model, dependency, or deployment behavior.
- The full pipeline uses Ollama `qwen3-vl:4b` for middle-frame vision analysis and `qwen3:4b` for stock metadata. Motion and composition use OpenCV/NumPy heuristics; GPS comes from ExifTool and optional Nominatim reverse geocoding.
- macOS ARM64 is the primary development environment. Ubuntu x86_64 is a **target**, not yet verified. Do not claim portability without testing.
- Prioritize configurable project/data paths, cross-platform resource monitoring, pinned dependencies, CI on both operating systems, and small non-destructive integration fixtures.
- Do not assume the agent's cloud environment has access to original videos, Ollama models, or a running Ollama server.
