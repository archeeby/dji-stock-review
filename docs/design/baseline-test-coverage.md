# Baseline behavior and test coverage

**Status: Draft — discussion and approval required before implementation.**

## Goal
Before refactoring, establish trustworthy regression coverage for meaningful user journeys from DJI source-video ingestion to stock-platform export. Measure code coverage but prioritize behavior over a numeric 100% target. Do not change production behavior to make tests pass.

## Baseline
Existing unittest and Streamlit AppTest checks exercise some review and export behavior with temporary files and mocks. Current GitHub-hosted CI tests do not verify real video processing or Ollama inference. Models `qwen3-vl:4b` and `qwen3:4b` may require multi-GB downloads and substantial compute; hosted-runner feasibility is unverified.

## Phase 1: inventory
Inspect implementation and tests; create a matrix: real user journey, expected outcome, modules, existing tests, missing tests, fixtures, external dependencies, execution environment and status. Include video discovery and GPS/ExifTool; OpenCV motion/composition and candidate detection; Ollama vision and metadata; review, edit, trim, approve/reject, undo and persistence; FFmpeg export; Adobe/Pond5/Shutterstock adapters; retries, resumes, corrupt inputs and protection of originals/previous analysis.

## Phase 2: characterization and coverage
Add missing unit/component tests for expected behavior and edge cases. Use mocks only at explicit external boundaries. Produce per-module coverage metrics and a scenario coverage matrix; report gaps. If observed behavior is questionable, discuss it rather than encoding it as an unquestioned specification.

## Phase 3: real-video integration
Use small licensed representative MP4 fixtures, including a sanitized DJI/GPS sample where possible. Execute actual FFmpeg, ExifTool and OpenCV in temporary isolated directories. Assert media validity, duration, candidate boundaries, metadata, idempotency, source checksums and expected exports. Verify installation, runtime and resource limits on GitHub-hosted Ubuntu and macOS before making tests required on every PR.

## Phase 4: real Ollama end-to-end
Run a representative clip through actual Ollama vision and text models and export, validating schema and stable quality invariants rather than exact nondeterministic wording. Compare a manually triggered GitHub-hosted workflow (model downloads/caching, compute, timeouts) with an isolated self-hosted runner with preinstalled models. Never assume GitHub-hosted capacity is sufficient. A personal Mac runner must not run untrusted PR code or access private footage. Record model version/digest, environment and real results; do not claim E2E success until executed.

## Acceptance criteria
- A traceable use-case matrix and honest list of coverage gaps.
- Deterministic fast tests plus meaningful real-tool integration tests where runner feasibility is proven.
- Documented, reproducible full-model E2E strategy and actual results once executed.
- No changes to originals, historical AI analyses or intended product behavior.
- Test failures receive root-cause analysis and a discussed fix decision, never assertion weakening for green CI.

## Open decisions
- Source and licensing of representative video fixture with DJI metadata.
- Whether full Ollama inference can run on hosted GitHub Actions or requires a dedicated runner.
- Whether to split implementation into multiple small PRs after inventory.
