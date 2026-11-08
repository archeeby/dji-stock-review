from workspace_paths import data_root, video_work_dir
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = data_root()
ORIGINALS = ROOT / "originals"
VIDEOS = ROOT / "metadata" / "videos"

def duration(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def snapshot():
    total = 0
    ai_done = 0
    stock_done = 0
    ai_seconds = []

    for video in sorted(ORIGINALS.rglob("*")):
        if not video.is_file() or video.suffix.lower() not in {".mp4", ".mov", ".m4v"}:
            continue

        work = video_work_dir(video, ROOT)
        candidates = work / "clip_candidates.json"

        if not candidates.exists():
            continue

        try:
            clips = json.loads(candidates.read_text())["clips"]
        except (OSError, ValueError, KeyError):
            continue

        for clip in clips:
            total += 1
            clip_id = clip["id"]

            ai_file = work / "ai" / f"{clip_id}.json"
            stock_file = work / "stock_metadata" / f"{clip_id}.json"

            try:
                ai = json.loads(ai_file.read_text())
                if ai.get("clip") == clip and ai.get("analysis"):
                    ai_done += 1
                    seconds = ai.get("processing_seconds", 0)
                    if isinstance(seconds, (int, float)) and seconds > 0:
                        ai_seconds.append(seconds)
            except (OSError, ValueError, TypeError):
                pass

            try:
                stock = json.loads(stock_file.read_text())
                metadata = stock.get("metadata", {})
                if (
                    stock.get("clip") == clip
                    and metadata.get("title")
                    and metadata.get("description")
                    and len(metadata.get("keywords", [])) >= 15
                ):
                    stock_done += 1
            except (OSError, ValueError, TypeError):
                pass

    average = sum(ai_seconds) / len(ai_seconds) if ai_seconds else 30
    remaining_ai = total - ai_done
    remaining_stock = total - stock_done

    # Stock metadata generation time is estimated conservatively.
    eta = remaining_ai * average + remaining_stock * 15

    return total, ai_done, stock_done, eta

def show():
    total, ai_done, stock_done, eta = snapshot()
    finish = datetime.now() + timedelta(seconds=eta)

    print(
        f"\nAI progress: {ai_done}/{total} clips | "
        f"Stock metadata: {stock_done}/{total}",
        flush=True
    )
    print(
        f"ETA: ~{duration(eta)} | "
        f"Estimated finish: {finish:%H:%M:%S}",
        flush=True
    )

if __name__ == "__main__":
    if "--watch" in sys.argv:
        previous = None
        try:
            while True:
                state = snapshot()
                if state[:3] != previous:
                    show()
                    previous = state[:3]
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
    else:
        show()
