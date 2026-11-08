# Setup — macOS and Ubuntu

**Status:** Local Python 3.12 / OpenCV installation and the real-video integration test have been verified on macOS ARM64. A clean installation on Ubuntu is not yet verified. Avoid running the full pipeline on valuable footage before validating the environment.

## 1. System prerequisites

Install Git, **Python 3.12** with `venv` and `pip`, FFmpeg, and ExifTool. Python 3.12 is the recommended local development version; CI also tests 3.11. Python 3.15 is not currently verified for this project.

macOS with Homebrew:

```bash
brew install python@3.12 ffmpeg exiftool
```

Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ffmpeg libimage-exiftool-perl
```

Check availability:

```bash
/opt/homebrew/bin/python3.12 --version
ffmpeg -version
exiftool -ver
```

## 2. Clone and Python environment

Choose a workspace anywhere. Keep the checkout inside it (or set `DJI_STOCK_ROOT` to an absolute data directory):

```bash
mkdir -p ~/workspace/DroneStock
git clone git@github.com:archeeby/dji-stock-review.git ~/workspace/DroneStock/dji-stock-review
cd ~/workspace/DroneStock/dji-stock-review
/opt/homebrew/bin/python3.12 -m venv ../.venv
source ../.venv/bin/activate
python --version  # expect Python 3.12.x
python -m pip install --upgrade pip
```

The project has a `pyproject.toml` declaring `streamlit`, `opencv-python` and `numpy`, but dependency versions are not locked and a clean-machine installation is not yet verified. Install with:

```bash
python -m pip install -e .
```

Check the active interpreter and OpenCV before running media tests:

```bash
python -c 'import sys, cv2, numpy; print(sys.version); print("OpenCV:", cv2.__version__)'
```

If `.venv` was created with the wrong interpreter, **do not overwrite or delete it without checking its contents**. Use a separate environment instead:

```bash
/opt/homebrew/bin/python3.12 -m venv ../.venv312
source ../.venv312/bin/activate
python -m pip install -e .
```

Repository-local `.venv312/` is excluded by `.gitignore`; workspace environments are outside this checkout. Launch and acceptance tools search workspace, checkout, then a separate `DJI_STOCK_ROOT` for `.venv312` or `.venv`. Acceptance requires Python 3.12 and Streamlit. Do not delete project data or originals.

## 3. Ollama (required for full AI processing)

Install Ollama for your platform using its official installation instructions: https://ollama.com/download

Ensure the local server is running and pull the exact model tags referenced in code:

```bash
ollama pull qwen3-vl:4b
ollama pull qwen3:4b
ollama list
```

The Python scripts call `http://localhost:11434/api/chat`. Ollama is **not required** to read the code, run isolated non-AI tests, or inspect the Streamlit interface; it is required for full AI processing. Model download sizes and RAM requirements depend on platform/model variants and are not yet benchmarked here.

## 4. Local data and first run

The repository excludes the personal video library and generated output. One explicitly approved, immutable DJI fixture is versioned at `tests/fixtures/dji/354022_DJI_0408.MP4` (original MP4 including GPS/telemetry); do not change it. For full pipeline exploration, place a **copy** of a separate test video under `~/workspace/DroneStock/originals/`; never move or alter your only original. For an initial safe check:

```bash
mkdir -p ~/workspace/DroneStock/originals
python run_batch.py --dry-run
```

Process a single video only after prerequisites are ready:

```bash
python run_batch.py --limit 1
```

Then launch the review UI:

```bash
python -m streamlit run review_app.py
```

The UI requires generated candidate metadata. GPS reverse-geocoding may make network requests to Nominatim; without valid GPS the location may be `Unknown`.

## 5. Tests

For the three testing levels (unit/component, lightweight real-video integration, and heavy AI/manual E2E), prerequisites, CI coverage, and safe local commands, see **[Testing strategy and execution](testing.md)**.

```bash
python -m unittest discover -s tests -v
```

The test suite uses Python's standard-library `unittest`. The real DJI motion/candidate integration test is **enabled by default** using the versioned, immutable fixture at `tests/fixtures/dji/354022_DJI_0408.MP4`. It exercises the production analysis scripts with actual OpenCV and checks the production 5–30 second clip limits, exclusion intervals, and SHA-256 source integrity. It does not require Ollama.

```bash
python -m unittest tests.test_real_dji_motion -v
python -m unittest discover -s tests -v
```

Optionally use another local video without changing the fixture:

```bash
DJI_TEST_VIDEO="/absolute/path/to/other.MP4" python -m unittest tests.test_real_dji_motion -v
```

The approved fixture has SHA-256 `43ff72ef1f3b7167b71b6672b3694d50e3fc339f38e3a905f5a40ada0b7773e5`. It was verified on the user's Mac (Python 3.12.16, OpenCV 4.14) and produced a 0.00–7.41s candidate from the 13s original. CI results on Ubuntu and macOS must be checked separately. Other originals and GPS data remain excluded; do not commit new original files without explicit approval.

## 6. Ubuntu caveats and next steps

- `run_batch.py` currently uses macOS-only health monitoring. It handles unavailable commands but does **not** monitor Linux pressure equivalently.
- The Ollama endpoint and model tags are hardcoded.
- GPU acceleration is optional for functionality but may be important for practical performance; CPU-only inference may be slow.
- A full clean-machine installation, cross-platform CI and end-to-end video processing test are pending.

For details and tracked gaps, see [architecture](architecture.md).
