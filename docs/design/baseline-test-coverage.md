# Baseline behavior and test coverage

**Status: Implemented and accepted — 2026-11-05.** Issue #2; implementation and acceptance in [PR #17](https://github.com/archeeby/dji-stock-review/pull/17), squash-merged into `main` as `e32c0958`.

## Goal and scope

Establish reproducible regression evidence for DJI video processing, AI-assisted metadata, review decisions, export lifecycle and platform metadata. Original video, historic AI output and personal review data must remain untouched by automated tests.

## Traceability matrix

| Journey / risk | Evidence in `tests/` | Dependency / execution | Status / limit |
| --- | --- | --- | --- |
| DJI original, GPS and metadata extraction | `test_real_dji_tools.py`, `test_real_dji_motion.py` | Checked-in DJI MP4, real ExifTool/OpenCV; local and hosted CI | Automated; fixture checksum protects source |
| Motion/composition and clip candidates | `test_real_dji_motion.py`, `test_trim_boundary_contracts.py`, `test_trim_duration_controls.py` | Real OpenCV plus deterministic boundary tests | Automated; includes clip constraints |
| AI frame analysis and stock metadata | `test_ollama_e2e.py` | Real local `qwen3-vl:4b` and `qwen3:4b`; opt-in local only | Real-model E2E passed; nondeterministic wording is not asserted |
| Review, approval/rejection and persistence | `test_candidate_reviews.py`, `test_records.py`, `test_approved_record_contracts.py`, `test_export_lifecycle_regressions.py` | Isolated filesystem tests; human Streamlit preview | Automated contracts plus manual UI acceptance |
| Trimming, approved export and media verification | `test_real_dji_tools.py`, `test_export_lifecycle_regressions.py`, `test_ollama_e2e.py` | Real FFmpeg/FFprobe, temporary copied media | Automated, including real-model-to-export path |
| Interrupted exports, reruns and recovery | `test_interrupted_export_recovery.py`, `test_batch_resume_integration.py`, `test_staging_failures.py` | Controlled fixtures and failure injection | Automated |
| Stock platform contracts and CLI | `test_platform_adapters.py`, `test_stock_platform_contracts.py`, `test_batch_and_platform_cli.py` | Synthetic/contract tests; no live platform uploads | Automated; external platform upload not validated |
| Acceptance reporting and SHA-bound preview | `test_accept.py`, `scripts/structured_tests.py`, `scripts/accept.py` | Structured unittest JSON and local Mac preview | Zero unaccounted skips required; preview shares live runtime data |

The matrix identifies representative test modules, **not** a claim that every possible edge case is covered. Live stock-platform upload, human judgement of AI wording and destructive UI actions on personal data are outside automated acceptance.

## Verified acceptance evidence

- PR #17 tested at exact head SHA `922de7e3a51d21991250f057fd044ebc5c9206c2` on macOS Apple Silicon with profile `ai`.
- **103 passed, 0 failed, 0 skipped**: 102 unit/real DJI integration tests and one real Ollama + FFmpeg E2E. Real Ollama stage took 48.5 seconds.
- GitHub Actions Python 3.12 checks passed on **Ubuntu and macOS** for that SHA (workflow run `42029386800`).
- Human confirmed all five Streamlit UI acceptance checks passed on the same SHA.
- Acceptance evidence lives locally under `~/.dji-stock-acceptance/pr-17/<sha>/` and includes structured JSON, logs and summary; personal runtime data and models are not committed.
- PR #17 was squash-merged as `e32c0958ca11b315c3dec7ed5c463809f29fae79`.

## Execution and safety

Run local PR acceptance with `DJI_ACCEPT_PROFILE=ai bash scripts/accept.sh <PR-number>` for an open PR; after merge, see [testing instructions](../testing.md) for direct test commands. The runner executes discovery and the separate real Ollama suite; an unexpected skip or inconsistent structured count blocks acceptance. No heavyweight models are downloaded by GitHub-hosted CI.

Automated tests use temporary directories and copied media; the checked-in original fixture is hash-checked. The Streamlit preview **shares** `~/DroneStock` runtime data, so manual acceptance must not change valuable existing records. Filesystem redirection is not a hardened sandbox.

## Remaining risks and follow-up

- No hosted real-Ollama CI: intentional due to model/runner cost and isolation constraints. Local real-model acceptance is required when AI/pipeline changes.
- No end-to-end upload to Adobe, Pond5 or Shutterstock; adapters have contract tests, not live marketplace certification.
- Coverage is behavioral, not a guarantee of 100% statement/branch coverage.
- Optimize GitHub Actions minute consumption separately; do not reduce required validation silently.
