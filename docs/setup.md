# Setup — macOS and Ubuntu

**Status:** Instructions below are a starting point based on source inspection. A clean installation has **not yet been verified** on either platform. Ubuntu is a target, not currently certified supported. Avoid running the full pipeline on valuable footage before validating the environment.

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

The application currently assumes `~/DroneStock`. Clone there until configurable paths are implemented:

```bash
git clone git@github.com:archeeby/dji-stock-review.git ~/DroneStock
cd ~/DroneStock
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
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

If `.venv` was created with the wrong interpreter, deactivate it and recreate it **only after confirming it contains no personal files**. Do not delete project data or originals.

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

The repository excludes personal footage and generated output. Place a **copy** of a test video under `~/DroneStock/originals/`; never move or alter your only original. For an initial safe check:

```bash
mkdir -p ~/DroneStock/originals
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

```bash
python -m unittest discover -s tests -v
```

The test suite uses Python's standard-library `unittest`. A passing unit suite is not proof of full video pipeline support. For the opt-in real DJI motion integration test on the test branch (production 5-second minimum), run:

```bash
DJI_TEST_VIDEO="$HOME/DroneStock/originals/354022_DJI_0408.MP4" \
  python -m unittest tests.test_real_dji_motion -v
```

The real-video test is skipped when `DJI_TEST_VIDEO` is unset. Never commit the original video or GPS data without explicit approval. The real-video integration test has not yet been verified on the user's Mac.

## 6. Ubuntu caveats and next steps

- `run_batch.py` currently uses macOS-only health monitoring. It handles unavailable commands but does **not** monitor Linux pressure equivalently.
- Path `~/DroneStock`, Ollama endpoint and model tags are hardcoded.
- GPU acceleration is optional for functionality but may be important for practical performance; CPU-only inference may be slow.
- A full clean-machine installation, cross-platform CI and end-to-end video processing test are pending.

For details and tracked gaps, see [architecture](architecture.md).
