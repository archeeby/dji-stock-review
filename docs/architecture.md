# Architecture and dependency audit

This document describes behavior observed in source code, not a claim that all stages have been end-to-end tested.

## Processing flow

```text
originals/*.MP4
  ├─ ExifTool GPS / telemetry → metadata/source_enrichment/
  ├─ GPS → Nominatim reverse geocoding → location cache
  └─ run_pipeline.py
       ├─ analyze_camera_motion_batch.py → camera_motion.json
       ├─ analyze_composition_batch.py → composition_analysis.json
       ├─ detect_scenes_v4_batch.py → clip_candidates.json
       ├─ analyze_auto_single_frame_batch.py → ai/<clip_id>.json
       └─ generate_stock_metadata_batch.py → stock_metadata/<clip_id>.json
                ↓
         review_app.py (manual approve/reject, trim, metadata)
                ↓
         export_approved.py / export_stock_platforms.py
```

`run_batch.py` discovers videos under `originals/`, skips completed processing, and runs `run_pipeline.py` for each remaining video. Exports are deferred until manual approval.

## AI models (confirmed in code)

| Purpose | Model | Runtime | Source |
| --- | --- | --- | --- |
| Visual scene understanding of a candidate's middle frame | `qwen3-vl:4b` | Ollama local HTTP `/api/chat` | `analyze_auto_single_frame_batch.py` |
| Stock title, description, keywords | `qwen3:4b` | Ollama local HTTP `/api/chat` | `generate_stock_metadata_batch.py` |

Both currently use `http://localhost:11434/api/chat` hardcoded. The vision model receives a JPEG frame extracted using OpenCV. Metadata generation uses structured JSON responses and includes a location context. Exact model digests are **not pinned** in the repository.

**Not AI models:** `analyze_camera_motion_batch.py` uses optical flow, feature tracking, affine transforms and jerk estimates with OpenCV/NumPy. `analyze_composition_batch.py` uses histogram and grayscale changes. `detect_scenes_v4_batch.py` uses deterministic heuristics to identify usable segments and candidate boundaries (5–30 seconds; target 22 seconds).

## Location and data integrity

`resolve_location.py` extracts GPS via ExifTool or cached source enrichment and queries the public OpenStreetMap Nominatim reverse-geocoding endpoint. A missing location becomes `Unknown`; the metadata prompt forbids invented geographic names when location is unknown. Network access is required for uncached reverse geocoding, and service usage policies must be respected.

`metadata_enrichment.py` uses ExifTool to read DJI embedded telemetry and caches results. Review and export code must never delete or modify source videos or source AI analyses.

Runtime data lives in `~/workspace/DroneStock/originals`, `metadata`, and `exports`; these directories are excluded from Git. Intermediate outputs are cached and processing skips existing results under code-specific checks. Do not force regeneration of historical AI analyses without explicit permission.

## Dependencies observed

- Python: `streamlit`, `cv2` (OpenCV), `numpy`; all tracked Python imports were audited; the project declares these in `pyproject.toml` (version ranges, not a lockfile).
- CLI: `ffmpeg`, `exiftool`.
- Local service: Ollama with `qwen3-vl:4b` and `qwen3:4b`.
- External service: OpenStreetMap Nominatim for uncached location resolution.

## Current portability and reproducibility gaps

1. Workspace paths use `workspace_paths.py`: checkout parent by default, absolute `DJI_STOCK_ROOT` override for separate data and isolated tests. Historical metadata folders are reused by source name; ambiguous matches stop processing. Export manifests are resolved in memory after relocation without rewriting historical metadata.
2. `run_batch.py` uses macOS-specific `sysctl kern.thermal_pressure` and `memory_pressure` checks. Their failures are handled, but Ubuntu has no equivalent monitoring and logs may misleadingly imply a health check occurred.
3. A `pyproject.toml` now declares the three external Python dependencies, but versions are not locked and model digests are not pinned. Installation still needs validation.
4. The Ollama endpoint and model tags are hardcoded.
5. The full pipeline requires real or representative video, sufficient RAM/storage, and local Ollama models. Automated integration tests are not established.
6. Ubuntu support and cross-platform CI are planned, not yet proven.

## Cross-platform implementation plan

- Centralize project/data root and Ollama endpoint in configuration; preserve existing defaults.
- Validate and lock Python dependencies and the new installable development setup.
- Separate optional health monitoring from batch processing, with macOS and Linux implementations or explicit opt-out.
- Add lightweight fixture-based unit tests and GitHub Actions on Ubuntu and macOS; avoid downloading model weights in ordinary CI.
- Add opt-in end-to-end smoke tests using a small permitted sample clip and locally installed Ollama models.
- Verify clean Ubuntu x86_64 and macOS ARM64 installs, then update support status.
