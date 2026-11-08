# DJI Stock Review

Local-first pipeline for turning DJI drone footage into stock-footage candidates with AI-assisted metadata and human approval.

## What it does

1. Read GPS metadata from source video and optionally reverse-geocode coordinates using OpenStreetMap Nominatim.
2. Analyze camera motion and visual composition with OpenCV and NumPy.
3. Propose clip boundaries using motion/composition heuristics.
4. Analyze a middle frame of each candidate with Ollama `qwen3-vl:4b`.
5. Generate stock titles, descriptions, and keywords with Ollama `qwen3:4b`.
6. Review candidates in Streamlit, adjust trims/metadata, approve or reject.
7. Export approved clips and prepare stock-platform metadata.

**Original footage stays local.** AI output is advisory; approval is manual.

## Documentation

- [Architecture and dependency audit](docs/architecture.md)
- [Setup for macOS and Ubuntu](docs/setup.md)
- [Agent working instructions](AGENTS.md)

## Quick start

See [setup](docs/setup.md) for prerequisites, Ollama models, and verified vs. unverified platform support.

```bash
./scripts/start-review.sh
```

The application uses `~/workspace/DroneStock` as its data workspace and `~/workspace/DroneStock/dji-stock-review` as its Git repository. The default data root is the repository’s parent directory; set `DJI_STOCK_ROOT` to an absolute path for a separate workspace. Script execution is relative to the repository, independent of the current working directory.

## Platform status

- macOS Apple Silicon: primary development environment; no automated clean-machine verification yet.
- Ubuntu Linux x86_64: **target platform, not yet validated**. Cross-platform CI, dependency locking, and health-monitoring refactoring are planned.

No original videos, generated metadata, exports, or model weights are included in this repository.

## Local workspace layout

The Git repository is located inside the DroneStock workspace:

    ~/workspace/DroneStock/
      dji-stock-review/   Git repository and application
      originals/          Original DJI footage
      metadata/           Analysis and manual reviews
      exports/            Approved clips and stock metadata
      previews/           Generated previews
      covers/             Generated covers
      platforms/          Platform-specific data
      experiments/        Experimental exports
      reports/            Analysis reports
      logs/               Processing logs
      backups/            Local backups
      archive/            Archived files

Python environments (.venv and .venv312) currently live
in the workspace root.

Original videos, metadata, exports, and backups are not
stored in Git.
