from workspace_paths import REPO_ROOT, data_root, video_work_dir
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = data_root()
ORIGINALS = ROOT / "originals"
LOG = ROOT / "metadata" / "batch_results.json"

parser = argparse.ArgumentParser()
parser.add_argument("--location", default=None)
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--limit", type=int, default=0)
args = parser.parse_args()

videos = sorted(
    p for p in ORIGINALS.rglob("*")
    if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".m4v"}
)
if args.limit:
    videos = videos[:args.limit]

print(f"Found {len(videos)} videos", flush=True)

if args.dry_run:
    for video in videos:
        print(video.relative_to(ORIGINALS))
    sys.exit(0)


def work_folder(video):
    return video_work_dir(video, ROOT)


def is_complete(video):
    work = work_folder(video)
    candidates = work / "clip_candidates.json"

    if not candidates.is_file():
        return False

    try:
        data = json.loads(candidates.read_text())
        clips = data["clips"]

        if not (work / "camera_motion.json").is_file():
            return False
        if not (work / "composition_analysis.json").is_file():
            return False

        for clip in clips:
            clip_id = clip["id"]

            ai = json.loads(
                (work / "ai" / f"{clip_id}.json").read_text()
            )
            stock = json.loads(
                (work / "stock_metadata" / f"{clip_id}.json").read_text()
            )

            if ai.get("clip") != clip or not ai.get("analysis"):
                return False

            metadata = stock.get("metadata", {})
            if stock.get("clip") != clip:
                return False
            if not metadata.get("title"):
                return False
            if not metadata.get("description"):
                return False
            if len(metadata.get("keywords", [])) < 15:
                return False

            if args.location and stock.get("location") != args.location.strip():
                return False

        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def mac_health():
    warnings = []

    try:
        result = subprocess.run(
            ["sysctl", "-n", "kern.thermal_pressure"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            value = result.stdout.strip()
            if value.isdigit() and int(value) >= 2:
                warnings.append(f"thermal pressure={value}")
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["memory_pressure", "-Q"],
            capture_output=True, text=True, timeout=10
        )
        match = re.search(
            r"System-wide free percentage:\s*(\d+)",
            result.stdout
        )
        if match and int(match.group(1)) < 10:
            warnings.append(f"free memory={match.group(1)}%")
    except (OSError, subprocess.TimeoutExpired):
        pass

    return warnings


def wait_for_healthy_mac():
    while True:
        warnings = mac_health()

        if not warnings:
            print("Memory check: OK (thermal monitoring unavailable)", flush=True)
            return

        print(
            "PAUSED: " + ", ".join(warnings) +
            ". Rechecking in 120 seconds...",
            flush=True
        )
        time.sleep(120)


def fmt_duration(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


LOG.parent.mkdir(parents=True, exist_ok=True)

try:
    previous = json.loads(LOG.read_text()) if LOG.exists() else []
    if not isinstance(previous, list):
        previous = []
except (OSError, ValueError):
    previous = []

history = {
    item["video"]: item
    for item in previous
    if isinstance(item, dict) and "video" in item
}

total = len(videos)
batch_start = time.monotonic()
processed_times = []
completed = 0
failed = 0

for index, video in enumerate(videos, 1):
    print(f"\n[{index}/{total}] {video.name}", flush=True)

    if is_complete(video):
        print("SKIPPED: already processed", flush=True)
        completed += 1
        continue

    wait_for_healthy_mac()

    command = [
        sys.executable,
        str(REPO_ROOT / "run_pipeline.py"),
        str(video)
    ]
    if args.location:
        command.extend(["--location", args.location])

    started = datetime.now()
    start_clock = time.monotonic()

    result = subprocess.run(command)

    elapsed = time.monotonic() - start_clock
    processed_times.append(elapsed)

    status = "success" if result.returncode == 0 else "failed"

    if status == "success" and is_complete(video):
        completed += 1
    else:
        failed += 1
        status = "failed"

    history[str(video)] = {
        "video": str(video),
        "status": status,
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(elapsed, 1),
        "return_code": result.returncode
    }

    temporary = LOG.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(
        list(history.values()), indent=2, ensure_ascii=False
    ))
    temporary.replace(LOG)

    remaining = sum(
        not is_complete(v) for v in videos[index:]
    )

    average = sum(processed_times) / len(processed_times)
    eta_seconds = remaining * average
    finish = datetime.now() + timedelta(seconds=eta_seconds)

    print(f"\nResult: {status}", flush=True)
    print(f"Progress: {completed}/{total} completed, {failed} failed")
    print(f"Current video: {fmt_duration(elapsed)}")
    print(f"Batch elapsed: {fmt_duration(time.monotonic() - batch_start)}")
    print(f"ETA: ~{fmt_duration(eta_seconds)}")
    print(f"Estimated finish: {finish:%Y-%m-%d %H:%M:%S}", flush=True)

print(
    f"\nCompleted: {completed} successful, {failed} failed",
    flush=True
)
print(f"Log: {LOG}")
