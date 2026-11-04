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

## Working agreement
1. Read the task, acceptance criteria, and affected code before editing.
2. For nontrivial changes, briefly state a plan and identify data-loss or regression risks.
3. Keep the change minimal and focused. Avoid unrelated refactoring and new dependencies without justification.
4. Add or update tests for changed behavior, especially candidate isolation, undo, trimming, and export deletion.
5. Run the relevant tests; use `python -m pytest` when pytest is available. Report exactly what ran and any failures or environment limitations.
6. Review the diff for accidental changes, secrets, generated files, and destructive behavior.
7. Deliver a concise summary, test evidence, and any unresolved risks. Prefer a feature branch and pull request; do not merge to `main` without human approval.

## Agent roles
- **Implementer** (Codex or Claude Code): change code and tests in a scoped branch.
- **Independent reviewer** (preferably the other model): review the issue, diff, and test evidence; prioritize correctness, data safety, regressions, and missing test cases. Do not silently modify the implementer's branch during review.
- **Human owner**: decides whether to merge and authorizes any destructive or irreversible action.

AI review is advisory; tests and explicit human approval remain required. Do not claim tests passed unless they actually ran.

## Project onboarding and portability
- Read `README.md`, `docs/architecture.md`, and `docs/setup.md` before changing pipeline, model, dependency, or deployment behavior.
- The full pipeline uses Ollama `qwen3-vl:4b` for middle-frame vision analysis and `qwen3:4b` for stock metadata. Motion and composition use OpenCV/NumPy heuristics; GPS comes from ExifTool and optional Nominatim reverse geocoding.
- macOS ARM64 is the primary development environment. Ubuntu x86_64 is a **target**, not yet verified. Do not claim portability without testing.
- Prioritize configurable project/data paths, cross-platform resource monitoring, pinned dependencies, CI on both operating systems, and small non-destructive integration fixtures.
- Do not assume the agent's cloud environment has access to original videos, Ollama models, or a running Ollama server.
