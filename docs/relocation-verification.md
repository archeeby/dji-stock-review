# Workspace relocation verification — 2026-11-08

**Status: relocation accepted on 2026-11-08.** Final structured discovery passed (116/116, no skips), and the real Ollama E2E passed on the host Mac after final review (1/1, no errors or skips). The agent sandbox's localhost restriction affected only its own attempts; those failures are retained below as historical evidence.

Root cause: runtime modules used `Path.home() / "DroneStock"`, while data moved to the parent of the nested checkout. Subprocesses also incorrectly looked for Python scripts in the workspace root. Absolute source paths were embedded in metadata folder hashes and export sidecars.

`workspace_paths.py` now defaults to the checkout parent and accepts an absolute `DJI_STOCK_ROOT`. Code execution uses `REPO_ROOT`. Launch/preview/acceptance scripts derive their checkout location; preview worktrees inherit the explicit data root. Tests explicitly redirect their data root into temporary directories. Historical metadata folders are reused by source name; ambiguous historical matches stop processing. Historical export sidecars resolve relocated originals in memory while preserving source size, modification time and trim comparisons. No migration or metadata rewrite was performed.

Audit covered tracked Python modules, shell scripts, packaging configuration, GitHub workflows, tests and Markdown documentation. Home-relative PR worktree/report directories are intentional user caches. Homebrew paths in setup examples and the macOS system notification sound are platform-specific tool/resource paths, independent of the workspace. No operational `~/DroneStock` data-root assumptions remain.

Read-only checks against the existing workspace:

- 496 original MP4s, 202,336,130,702 bytes across all files in originals.
- 5,574 metadata files, 51,188,582 bytes logical size.
- 179 approved MP4s, 14,310,151,922 bytes across all files in exports/approved.
- Library: 490 source videos, 2,013 candidates; 179 approved, 88 rejected, 1,746 pending.
- All 2,013 stock metadata JSON records parsed. All 179 approved exports are current; zero missing or outdated. All 179 historical source manifests match the relocated source size/mtime and approved trims.
- Streamlit AppTest loaded the real library and selected metadata without exceptions; the pending dropdown contains 1,746 candidates. Only FFmpeg preview bytes were stubbed; no review/export actions were clicked against live data.
- Six originals lack candidate records: 265320_DJI_0177.MP4, 269446_DJI_0329.MP4, 354661_DJI_0453.MP4, 354740_DJI_0495.MP4, 354653_DJI_0482.MP4, 264533_DJI_0086.MP4. Their processing history was not changed or regenerated.

macOS ARM64 / Python 3.12.16 validation:

- `../.venv312/bin/python -m unittest discover -s tests -v`: 107 tests run; OK, with one opt-in Ollama class skipped (15.236 seconds).
- Real fixture tests exercised OpenCV analysis, ExifTool, playable FFmpeg export and repeat-export idempotency. The relocated-sidecar regression verified that export invokes no encoding and preserves MP4 hash/mtime and sidecar bytes.
- Candidate review tests exercised approve/reject/undo, candidate isolation and matching-export removal using disposable data. Batch retry/resume used a fake pipeline in a copied temporary checkout. These mocked tests are not full AI E2E evidence.
- Shell syntax and `git diff --check` passed. Final source/test/doc diff reviewed, including independent agent review.
- Before/after inventories matched for all protected originals, metadata and approved exports: file names, sizes and nanosecond modification times; additionally SHA-256 for metadata and sidecars. Large production MP4s were not fully hashed.

A live HTTP launch check reached Streamlit but socket binding was blocked by the agent sandbox (`PermissionError: Operation not permitted`). Browser playback remains unverified here; AppTest covers app loading, with preview bytes stubbed. Ollama E2E could not run in the agent sandbox; it subsequently passed on the host Mac as documented below. PR fetching/acceptance was not run against live data. Preview UI actions still act on the configured workspace. No commit was created.

Temporary evidence: `/tmp/drone-tests-final.log`, `/tmp/drone-relocation-tests.log`, `/tmp/drone-readonly.log`, `/tmp/drone-streamlit.log`, `/tmp/drone-inventory-before.json`, `/tmp/drone-inventory-after.json`.

## Real AI acceptance — completed on host Mac

The original committed acceptance configuration (`git show HEAD:scripts/accept.py` and `git show HEAD:tests/test_ollama_e2e.py`) selected the `ai` profile for AI/pipeline changes, or through `DJI_ACCEPT_PROFILE=ai bash scripts/accept.sh <PR-number>`. The runner ran structured discovery first, then set `DJI_RUN_OLLAMA_E2E=1` and executed `scripts/structured_tests.py --suite ollama`. That suite requires exactly one named successful, unskipped test. Hosted CI intentionally does not enable real Ollama.

Required models are `qwen3-vl:4b` (frame vision) and `qwen3:4b` (stock metadata). `/opt/homebrew/bin/ollama` is installed. Both local manifests and all referenced blobs exist with the expected file sizes under `~/.ollama/models`; this is disk evidence, not confirmation that the server can load them. Model files were not changed or downloaded.

Additional fixes:

- Shared path configuration and acceptance/preview runner changes now require the AI profile, preventing them from silently selecting media-only acceptance.
- Test environments explicitly replace inherited live data paths, and enable real AI only for the separate AI suite. Preview environments explicitly carry the main checkout and workspace into detached PR worktrees.
- The real AI E2E uses a copied fixture in a temporary workspace containing spaces and executes vision, metadata and export CLIs from outside the repository. No model or FFmpeg calls are mocked. Export idempotence requires `SKIP unchanged`, unchanged mtime, sidecar bytes and MP4 bytes.
- The real-media integration now also executes the exporter CLI and the real Streamlit app with actual FFmpeg preview generation in temporary data, from a different current directory.

Commands executed from `~/workspace/DroneStock/dji-stock-review`:

```bash
command -v ollama
ollama list
curl --max-time 15 -sS http://127.0.0.1:11434/api/tags

# Initial real AI attempt; failed in setUpClass before inference.
DJI_RUN_OLLAMA_E2E=1 ../.venv312/bin/python scripts/structured_tests.py --suite ollama --json /tmp/drone-ollama-attempt.json > /tmp/drone-ollama-attempt.log 2>&1

../.venv312/bin/python -m unittest tests.test_accept -v > /tmp/drone-accept-regression.log 2>&1
../.venv312/bin/python -m unittest tests.test_real_dji_tools -v > /tmp/drone-real-cli-preview.log 2>&1

# Complete structured unit/integration suite, explicitly isolated.
task_sandbox="$(mktemp -d /tmp/drone-ai-acceptance.XXXXXX)"
env -u DJI_RUN_OLLAMA_E2E HOME="$task_sandbox" TMPDIR="$task_sandbox" DJI_STOCK_ROOT="$task_sandbox" ../.venv312/bin/python scripts/structured_tests.py --suite discovery --json /tmp/drone-ai-discovery.json > /tmp/drone-ai-discovery.log 2>&1

# Final real AI attempt against updated working-tree code.
task_sandbox="$(mktemp -d /tmp/drone-real-ai.XXXXXX)"
env HOME="$task_sandbox" TMPDIR="$task_sandbox" DJI_STOCK_ROOT="$task_sandbox" DJI_RUN_OLLAMA_E2E=1 ../.venv312/bin/python scripts/structured_tests.py --suite ollama --json /tmp/drone-ai-final.json > /tmp/drone-ai-final.log 2>&1

bash scripts/start-review.sh --server.headless true --server.address 127.0.0.1 --server.port 18519 --browser.gatherUsageStats false
bash -n scripts/accept.sh scripts/preview.sh scripts/start-review.sh
git diff --check
```

The server command was launched and monitored by Python `subprocess.Popen`, with output in `/tmp/drone-preview-final.log`; the process exited itself with status 1. Additional Python checks called `find_python(repo)` and `prerequisites('ai', repo)` successfully, inspected model blob sizes, and compared the protected-data inventory with the original baseline.

| Check | Result |
| --- | --- |
| Acceptance regression tests | 23 passed, 0 failed, 0 skipped |
| Real media / CLI / AppTest preview tests | 2 passed, 0 failed, 0 skipped; 6.237 seconds |
| Structured discovery (includes both rows above) | 110 passed, 0 failed, 0 skipped; 16.001 seconds |
| Initial real Ollama suite | Exit 1; 0 tests executed, 1 setup error, 0 skipped |
| Final real Ollama suite | Exit 1; 0 tests executed, 1 setup error, 0 skipped |
| Live Streamlit HTTP server | Exit 1; socket bind denied by sandbox |
| Shell syntax / diff whitespace | Passed |
| Protected production data inventory | Unchanged: 496 original MP4s, all metadata, 179 approved MP4s |

`ollama list` and real E2E setup fail when connecting to `127.0.0.1:11434` with `Operation not permitted`. Streamlit fails with the same sandbox restriction when binding its socket. This session's permission profile cannot grant shell/network escalation. No mock was substituted to turn these failures into passes. Independent review found no material data-safety blocker; the sandbox's AI acceptance attempt remained blocked; the later host Mac run passed.

The PR-fetch/worktree wrapper was not executed: it would validate committed remote PR code rather than these uncommitted working-tree changes. No commit or PR was created. The required real-AI test was subsequently executed successfully on the host Mac (see final verification below). Browser HTTP access also remains unverified here. The AI test covers the individual vision, metadata and export CLIs; it does not claim a real-model `run_pipeline.py`/`run_batch.py` orchestration run. Batch resume/orchestration regression coverage uses the existing explicitly fake pipeline.

## Final uncommitted code review

Reviewed every modified source/configuration/test/documentation file and the untracked path module, regression tests and this report. `.idea/` is now ignored, confirmed with `git check-ignore .idea/workspace.xml`; no IDE files were staged, removed or changed.

Findings fixed during review:

1. A new current-path folder could bypass historical metadata ambiguity checks. Historical ownership is now evaluated before folder selection; an empty new folder cannot hide historical records.
2. Historical motion/composition-only folders were missed. Their producer `filename` fields now allow reuse without regeneration. Candidate, motion and composition identities are checked together, and conflicts stop processing.
3. Duplicate original filenames or an unrelated external video with the same basename could claim historical workspace metadata. Ambiguous and external fallback ownership now stops processing.
4. Interpreter lookup differed between the Python acceptance runner, its bootstrap, preview and normal launcher. All search workspace-parent, checkout-local, then separate data-root environments in that order. Acceptance validates Python 3.12 and Streamlit before execution.
5. Pipeline source/metadata ownership checks now precede GPS lookup, preventing location-cache writes before an ownership failure. The documented manual AI smoke command now uses a temporary data workspace.

Added regression coverage for historical/current folder collisions, partial analyses, conflicting identities, duplicate filenames, external basename collisions, corrupted records and interpreter fallback. The stricter identity validation initially exposed one invalid fake batch fixture: its analysis objects were `{}` whereas both real producers include `filename`. Corrected those fake records to match the producer schema; all existing retry/resume and source-integrity assertions were preserved. This was a fixture correction, not a relaxation of production validation.

Final structured discovery command:

```bash
task_sandbox="$(mktemp -d /tmp/drone-final-pass.XXXXXX)"
env -u DJI_RUN_OLLAMA_E2E HOME="$task_sandbox" TMPDIR="$task_sandbox" DJI_STOCK_ROOT="$task_sandbox" ../.venv312/bin/python scripts/structured_tests.py --suite discovery --json /tmp/drone-final-pass.json > /tmp/drone-final-pass.log 2>&1
```

Result: **116 passed, 0 failed, 0 skipped**, 15.859 seconds. This includes real OpenCV, ExifTool, FFmpeg export, relocated-sidecar reuse and FFmpeg-backed Streamlit AppTest preview checks. An intermediate run had 115 passed and the one fake-fixture failure described above; the final run resolves it. Shell syntax, whitespace diff checks and independent review passed.

A fresh real-AI attempt during final review used the same isolated environment with `DJI_RUN_OLLAMA_E2E=1` and `--suite ollama --json /tmp/drone-final-review-ai.json`; it returned exit 1, zero executed tests, one setup error and zero skips because localhost access is denied. No real model inference is claimed. This was a sandbox-only blocker, subsequently resolved by running the real test on the host Mac.

Read-only production validation still reports 490 videos / 2,013 candidates and all 179 approved exports current. Five of the six originals without candidate records have historical partial analysis folders, now resolved correctly without writing them; the sixth has no existing folder. Final inventory `/tmp/drone-inventory-reviewed.json` exactly matches `/tmp/drone-inventory-before.json`: all original and approved MP4 names/sizes/mtime values, all metadata files and SHA-256 values, and all sidecars. Large production MP4s were not fully hashed. No production media or metadata was modified.

Code review found no known material code blocker. The host Mac subsequently passed the required real Ollama E2E test, and the relocation changes were committed and pushed to `main`. The no-commit/no-push statement above describes the earlier agent review session only. Historical lookup still scans metadata folders; batch/monitor performance on substantially larger libraries has not been benchmarked.

## Final host-Mac verification and publication — 2026-11-08

After the final review fixes, the user ran the real, unmocked Ollama E2E in a normal macOS terminal with access to the local Ollama service:

```bash
cd ~/workspace/DroneStock/dji-stock-review
DJI_RUN_OLLAMA_E2E=1 ../.venv312/bin/python \
  scripts/structured_tests.py --suite ollama \
  --json /tmp/drone-local-ai-final.json
```

Result: **1 test passed, 0 failures, 0 errors, 0 skips**, in **43.168 seconds** (`test_real_frame_vision_and_stock_metadata`). Installed models included `qwen3-vl:4b` and `qwen3:4b`. The same real E2E had also passed earlier in 41.994 seconds, before the final review fixes. The post-review run is the acceptance evidence for the final code.

Combined final evidence: **116/116 structured discovery tests passed** in the agent environment; **1/1 real Ollama E2E passed** on the host Mac. These are separate test executions, not a claim that a single end-to-end acceptance wrapper ran. The live browser/HTTP Streamlit check was blocked in the agent sandbox and was not independently verified by this host-Mac E2E run; Streamlit AppTest with real FFmpeg preview did pass. A full real-model `run_pipeline.py` / `run_batch.py` orchestration run was not claimed.

The relocation changes were committed and pushed to GitHub `main`; the repository's subsequent published head was verified as `a625b298b6e793c65ef6d96bda7518434a249375` before this documentation update. The historical inventory checks found no production-media or metadata changes. **Relocation acceptance is complete within the tested scope.**
