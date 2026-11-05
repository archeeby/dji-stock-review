# Testing strategy and local execution

This document distinguishes tests that **exist today** from planned checks. It applies to macOS ARM64 (locally exercised with Python 3.12) and the GitHub Actions Ubuntu/macOS matrix (Python 3.12). See [setup](setup.md) for installation details.

## Three test levels

| Level | Scope | Dependencies | Where | Current status |
| --- | --- | --- | --- | --- |
| **Unit / component** | Domain logic, state, validation, adapters, and isolated UI behavior; mocks/synthetic inputs where appropriate | Python 3.12, `pip install -e .` | Local and hosted GitHub Actions | Automated under `tests/` |
| **Lightweight real-tool integration** | Actual original DJI MP4 → OpenCV motion/composition analysis → deterministic clip candidates; SHA-256 and clip constraints | Same Python dependencies, checked-in MP4; **no Ollama** | Local and hosted GitHub Actions | Automated in `tests/test_real_dji_motion.py` |
| **Heavy AI / end-to-end** | Actual Ollama vision analysis and stock metadata; ultimately review, export, playable media and metadata verification | Python, OpenCV, Ollama server, `qwen3-vl:4b`, `qwen3:4b`; FFmpeg/ExifTool for full pipeline and GPS; network for uncached geocoding | Local controlled environment only | **Automated real Ollama vision + metadata + FFmpeg export E2E exists (`tests/test_ollama_e2e.py`); runs locally only** |

The word *integration* does not imply AI. The current video integration test exercises real OpenCV and deterministic scripts, not Ollama.

## Prerequisites for unit and lightweight integration

1. Clone the repository and install **Python 3.12**.
2. Use a Python 3.12 virtual environment; install project dependencies.
3. No GPU, Ollama models, external network service or local personal footage is needed after the repository and dependencies are available. The explicitly approved fixture is versioned in Git.

macOS ARM64, including machines with an existing older `.venv`:

```bash
cd ~/DroneStock
brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv .venv312
source .venv312/bin/activate
python -m pip install -e .
python --version
python -c 'import cv2; print(cv2.__version__)'
```

Do **not** overwrite an existing virtual environment or delete personal files to resolve an interpreter mismatch. See [setup](setup.md) for Ubuntu prerequisites.

## Run locally

All automated tests (unit/component **plus** lightweight real-video integration):

```bash
cd ~/DroneStock
source .venv312/bin/activate
python -m unittest discover -s tests -v
```

Run only the real-video integration:

```bash
python -m unittest tests.test_real_dji_motion -v
```

To run a particular unit test module, use `python -m unittest tests.<module_name> -v` (replace the module name with an existing test file, without `.py`).

The checked-in fixture is `tests/fixtures/dji/354022_DJI_0408.MP4`. It is an **immutable original** containing embedded GPS/telemetry. Expected SHA-256:

```text
43ff72ef1f3b7167b71b6672b3694d50e3fc339f38e3a905f5a40ada0b7773e5
```

The test verifies the fixture hash before processing and checks the source hash afterward. Analysis JSON goes to a temporary directory, not alongside the fixture. It asserts production clip limits (minimum 5 seconds, maximum 30 seconds), excludes motion-warning intervals, and requires at least one usable candidate. On the verified local macOS run it produced a candidate from 0.00 to 7.41 seconds.

To run the same test against a **different** local video, without changing the committed fixture:

```bash
DJI_TEST_VIDEO="/absolute/path/to/other.MP4" \
  python -m unittest tests.test_real_dji_motion -v
```

The override still checks that the video is not modified, but does not assert the committed fixture's hash. Do not weaken production clip thresholds just to make a fixture pass.

## GitHub Actions

Workflow: `.github/workflows/tests.yml`.

- Triggers: pull requests and pushes to `main`.
- Matrix: `ubuntu-latest` and `macos-latest`, each with Python 3.12 (two jobs).
- Steps: checkout (includes the MP4 fixture), `pip install -e .`, `compileall`, and `python -m unittest discover -s tests -v`.
- **Both** unit/component and lightweight integration tests run in each job. The job's historical name `unit-tests` does not mean it runs only unit tests.
- **No** Ollama installation, model download, AI inference or full export E2E is configured.
- A local passing run is not proof of CI success: inspect the actual checks in the pull request, including macOS and Ubuntu results.

## Heavy AI pipeline: automated opt-in contract test and manual smoke test

Additional prerequisites:

- Ollama installed, running locally at `http://localhost:11434` and enough free RAM/disk for the two models.
- `ollama pull qwen3-vl:4b` and `ollama pull qwen3:4b`; confirm with `ollama list`.
- FFmpeg and ExifTool installed (`brew install ffmpeg exiftool` on macOS).
- A dedicated test video that you have permission to process. Prefer a disposable **copy** of the checked-in fixture, not your only personal original.
- For GPS resolution, `resolve_location.py` may contact Nominatim; provide a known `--location` to control metadata text, but note that location resolution is attempted before that argument is used.

Example **manual smoke test** in the existing `~/DroneStock` installation:

```bash
cd ~/DroneStock
source .venv312/bin/activate
ollama list
ollama pull qwen3-vl:4b
ollama pull qwen3:4b
mkdir -p originals/ai-smoke
cp -n tests/fixtures/dji/354022_DJI_0408.MP4 originals/ai-smoke/354022_DJI_0408.MP4
python run_pipeline.py originals/ai-smoke/354022_DJI_0408.MP4 --location "Unknown"
```

**Safety / limitations:** `run_pipeline.py` hardcodes `~/DroneStock` as its data root, creates or reuses output in `metadata/videos/`, and can call Nominatim. This is **not an isolated automated test**; inspect existing outputs and available storage before running it, and never delete or overwrite previous metadata to force a pass. The example uses a separate copy to avoid writing against the committed fixture or personal originals. `cp -n` avoids replacing an existing copy; if one exists, check it before proceeding. No stock MP4 export is performed by `run_pipeline.py`—the program deliberately defers export until manual approval.

Manual smoke-test acceptance checks: successful process exit; candidate JSON and AI JSON generated for each candidate; stock metadata JSON with title and keywords; source file SHA-256 unchanged. This does **not** establish AI content quality, export correctness, or full end-to-end coverage. Model outputs may vary; validate contracts and quality constraints, not exact generated prose.

## Real-model E2E coverage and remaining limits

The opt-in `tests/test_ollama_e2e.py` exercises actual Ollama vision and metadata, then an approved export through real FFmpeg using disposable copies and temporary paths. It verifies generated contracts rather than exact nondeterministic prose. It does not certify external stock-platform uploads or replace manual UI review. See [Issue #2 coverage matrix](design/baseline-test-coverage.md).

Do not enable heavy AI E2E on ordinary hosted PR CI or silently download multi-GB models. A future manually triggered/self-hosted runner must be isolated from personal data and must not execute untrusted pull-request code.

## Failure triage

- Unit failure: inspect the failing assertion and fixture/mocks.
- Lightweight integration failure: inspect captured script stdout/stderr, OpenCV/platform differences, candidate/excluded JSON, and fixture SHA-256. Do not change 5–30 second production limits to obtain a green build.
- Heavy AI failure: check Ollama availability, model tags, RAM, network/GPS resolution, cached metadata and actual JSON contracts before changing production behavior.

Never merge solely because one local test passed. Review all required CI checks and obtain explicit human approval to merge.


## Issue #8: one-command SHA-bound PR acceptance

Run from the main checkout on macOS with the Python 3.12 virtualenv, FFmpeg, FFprobe, and ExifTool installed:

```bash
bash scripts/accept.sh 12
```

The runner fetches the exact PR head into a separate Git worktree, chooses the most demanding applicable profile, and records the SHA, changed paths, environment, per-check results, failure details and test log in `~/.dji-stock-acceptance/pr-<number>/<sha>/`. Its normal test run includes the real DJI/OpenCV/FFmpeg/ExifTool suite. `docs` is explicitly N/A; non-AI PRs record Ollama as N/A, not passed. Missing dependencies and test failures block the preview. The Streamlit preview is **not isolated** and can access real runtime data; do not modify existing review decisions or metadata.

For an explicit **stricter** local AI acceptance run (including for this PR, whose ordinary changed-file profile is `unit`):

```bash
DJI_ACCEPT_PROFILE=ai bash scripts/accept.sh 12
```

This runs `tests/test_ollama_e2e.py` against a running local Ollama with both **already installed** `qwen3-vl:4b` and `qwen3:4b`. The test extracts a real video frame, performs both model calls and validates their output contracts, all under temporary HOME and output paths. It never downloads models, modifies the committed DJI fixture, or uses the personal video library. Model responses are nondeterministic: assertions cover schema and basic constraints, not exact prose. A missing model, Ollama failure, or missing output blocks acceptance. **No heavy AI model test runs on hosted GitHub CI.** The opt-in test is skipped there by design, and that skip must never be presented as a passed AI E2E.

A passing automated report is not human UI approval or permission to merge. Local tests run with filesystem path redirection, not a hardened OS sandbox; inspect third-party code before execution. The runner rechecks PR SHA before launching the preview; new commits require new evidence. Explicit human merge approval and green CI on the exact current SHA remain mandatory.


## Issue #2 completion — PR #17 (2026-11-05)

The accepted PR head was `922de7e3`; local AI-profile acceptance reported **102/102** unit and DJI integration tests plus **1/1** real Ollama/FFmpeg E2E, with **0 failures and 0 skips**. Both Ubuntu and macOS CI jobs succeeded, and five manual UI checks were confirmed. PR #17 was merged into `main` as `e32c0958`.

For a new open PR, use:

```bash
cd ~/DroneStock
DJI_ACCEPT_PROFILE=ai bash scripts/accept.sh <PR-number>
```

The SHA-bound acceptance runner writes `tests.json`, `ollama-e2e.json`, logs, `summary.txt` and `result.json` to `~/.dji-stock-acceptance/pr-<number>/<sha>/`. Ollama is intentionally excluded from discovery and run separately; **any unexpected skip, inconsistent count or failed required suite blocks acceptance**. The Streamlit preview is not data-isolated.

For direct testing on updated `main`, the ordinary `unittest discover` command above may still report the opt-in Ollama class as skipped; use the structured runner's distinct suites to avoid counting it as unverified:

```bash
python scripts/structured_tests.py --suite discovery --json /tmp/dji-tests.json
DJI_RUN_OLLAMA_E2E=1 python scripts/structured_tests.py --suite ollama --json /tmp/dji-ollama.json
```

The second command requires a running local Ollama and both installed models.
