from workspace_paths import REPO_ROOT, data_root, video_work_dir
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = data_root()

parser = argparse.ArgumentParser()
parser.add_argument("video", type=Path)
parser.add_argument("--location", default=None)
args = parser.parse_args()

video = args.video.resolve()
if not video.is_file():
    raise FileNotFoundError(video)
work = video_work_dir(video, ROOT)
from resolve_location import resolve_details

try:
    location_details = resolve_details(video)
    if location_details and not args.location:
        args.location = location_details.get("location")
except Exception as exc:
    print(f"GPS location lookup failed: {exc}", flush=True)

if not args.location:
    args.location = "Unknown"

print(f"Location: {args.location}", flush=True)

work.mkdir(parents=True, exist_ok=True)

motion = work / "camera_motion.json"
composition = work / "composition_analysis.json"
candidates = work / "clip_candidates.json"
ai_dir = work / "ai"
stock_dir = work / "stock_metadata"

def run(script, *arguments):
    command = [sys.executable, str(REPO_ROOT / script), *map(str, arguments)]
    print(f"\nRunning {script}", flush=True)
    subprocess.run(command, check=True)

if not motion.exists():
    run("analyze_camera_motion_batch.py", video, motion)

if not composition.exists():
    run("analyze_composition_batch.py", video, composition)

if not candidates.exists():
    run("detect_scenes_v4_batch.py", composition, motion, candidates)

data = json.loads(candidates.read_text())
if not data["clips"]:
    print("No suitable clips found")
    sys.exit(0)

for clip in data["clips"]:
    run(
        "analyze_auto_single_frame_batch.py",
        candidates, ai_dir, clip["id"],
        "--video", video
    )

run(
    "generate_stock_metadata_batch.py",
    candidates, ai_dir, stock_dir,
    "--location", args.location
)

# Verify every clip has current AI analysis and stock metadata.
for clip in data["clips"]:
    clip_id = clip["id"]

    ai_file = ai_dir / f"{clip_id}.json"
    metadata_file = stock_dir / f"{clip_id}.json"

    if not ai_file.is_file():
        raise RuntimeError(f"Missing AI analysis: {clip_id}")

    ai_record = json.loads(ai_file.read_text())
    if ai_record.get("clip") != clip or not ai_record.get("analysis"):
        raise RuntimeError(f"Outdated AI analysis: {clip_id}")

    if not metadata_file.is_file():
        raise RuntimeError(f"Missing stock metadata: {clip_id}")

    record = json.loads(metadata_file.read_text())
    if (
        record.get("clip") != clip
        or record.get("location") != args.location.strip()
        or not record.get("metadata", {}).get("title")
        or not record.get("metadata", {}).get("keywords")
    ):
        raise RuntimeError(f"Invalid stock metadata: {clip_id}")

print(f"\nPipeline completed: {video.name}")
print("MP4 export deferred until manual approval.")
print(f"Metadata: {stock_dir}")
