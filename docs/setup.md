# Setup — macOS and Ubuntu

**Status:** Instructions below are a starting point based on source inspection. A clean installation has **not yet been verified** on either platform. Ubuntu is a target, not currently certified supported. Avoid running the full pipeline on valuable footage before validating the environment.

## 1. System prerequisites

Install Git, Python 3 with `venv` and `pip`, FFmpeg, and ExifTool.

macOS with Homebrew:

```bash
brew install python ffmpeg exiftool
```

Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ffmpeg libimage-exiftool-perl
```

Check availability:

```bash
python3 --version
ffmpeg -version
exiftool -ver
```

## 2. Clone and Python environment

The application currently assumes `~/DroneStock`. Clone there until configurable paths are implemented:

```bash
git clone git@github.com:archeeby/dji-stock-review.git ~/DroneStock
cd ~/DroneStock
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

**Dependency packaging is incomplete:** the repository currently has no verified dependency manifest. The audited pipeline imports `streamlit`, `cv2` and `numpy`. A provisional, **unpinned** install for exploration is:

```bash
python -m pip install streamlit opencv-python numpy pytest
```

Other scripts may require more packages; the next task is to audit all imports and add a locked dependency manifest. Do not treat the provisional command as a reproducible installation.

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
python -m pytest
```

This command has **not been executed** as part of the documentation change. Check the actual test suite and dependencies before treating a passing run as proof of full pipeline support.

## 6. Ubuntu caveats and next steps

- `run_batch.py` currently uses macOS-only health monitoring. It handles unavailable commands but does **not** monitor Linux pressure equivalently.
- Path `~/DroneStock`, Ollama endpoint and model tags are hardcoded.
- GPU acceleration is optional for functionality but may be important for practical performance; CPU-only inference may be slow.
- A full clean-machine installation, cross-platform CI and end-to-end video processing test are pending.

For details and tracked gaps, see [architecture](architecture.md).
