import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from candidate_reviews import key_for, get_review, review_status
from trim_bounds import valid_trim

ROOT = Path.home() / "DroneStock"
WORK = ROOT / "metadata" / "videos"
ORIGINALS = ROOT / "originals"
DEST = ROOT / "exports" / "approved"

def export(folder):
    work = WORK / folder
    candidates = json.loads((work / "clip_candidates.json").read_text())
    reviews_path = work / "reviews.json"
    reviews = json.loads(reviews_path.read_text()) if reviews_path.exists() else {}

    source_name = candidates["source"]
    matches = list(ORIGINALS.rglob(source_name))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one original for {source_name}, found {len(matches)}")
    source = matches[0]
    source_stat = source.stat()

    output = DEST / folder
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    total_clips = len(candidates["clips"])
    completed_clips = 0

    def report_progress(clip_id):
        nonlocal completed_clips
        completed_clips += 1
        print(
            f"PROGRESS|{completed_clips}|{total_clips}|{clip_id}",
            flush=True,
        )

    for clip in candidates["clips"]:
        clip_id = clip["id"]
        key = key_for(source_name, clip_id)
        review = get_review(reviews, source_name, clip_id)
        if review_status(review) != "approved":
            for path in (
                output / key,
                output / (key + ".source.json"),
            ):
                if path.is_file():
                    path.unlink()
                    print(f"REMOVED inactive export: {path.name}")
            report_progress(clip_id)
            continue

        start = float(review.get("start", clip["start"]))
        end = float(review.get("end", clip["end"]))
        if not valid_trim(start, end, float(candidates["duration"])):
            raise ValueError(f"Invalid boundaries for {clip_id}: {start}–{end}")

        metadata_file = work / "stock_metadata" / f"{clip_id}.json"
        record = json.loads(metadata_file.read_text())
        metadata = record["metadata"]

        title = review.get("title", metadata.get("title", "")).strip()
        description = review.get("description", metadata.get("description", "")).strip()
        keywords = review.get("keywords", ", ".join(metadata.get("keywords", [])))
        if isinstance(keywords, list):
            keywords = ", ".join(keywords)
        keywords = keywords.strip()

        if not title or not description or not keywords:
            raise ValueError(f"Missing metadata for {clip_id}")

        filename = key
        target = output / filename
        manifest = output / (filename + ".source.json")
        spec = {
            "source": str(source.resolve()),
            "source_size": source_stat.st_size,
            "source_mtime_ns": source_stat.st_mtime_ns,
            "start": start,
            "end": end,
        }

        existing = json.loads(manifest.read_text()) if manifest.exists() else None
        if target.exists() and existing == spec:
            print(f"SKIP unchanged: {filename}", flush=True)
        else:
            if target.exists() and existing is None:
                raise RuntimeError(f"Existing MP4 without manifest: {target}")

            temporary = output / (filename + ".partial.mp4")
            temporary.unlink(missing_ok=True)
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source),
                "-ss", str(start),
                "-t", str(end - start),
                "-map", "0:v:0", "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                "-pix_fmt", "yuv420p",
                str(temporary),
            ]
            try:
                subprocess.run(command, check=True)
                subprocess.run([
                    "ffprobe", "-v", "error", "-show_entries",
                    "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                    str(temporary)
                ], check=True, capture_output=True)
                temporary.replace(target)
                tmp_manifest = manifest.with_suffix(manifest.suffix + ".tmp")
                tmp_manifest.write_text(json.dumps(spec, indent=2))
                tmp_manifest.replace(manifest)
            finally:
                temporary.unlink(missing_ok=True)
            print(f"EXPORTED: {filename}", flush=True)

        report_progress(clip_id)

        rows.append({
            "Filename": filename,
            "Title": title,
            "Description": description,
            "Keywords": keywords,
        })

    csv_file = output / "approved_metadata.csv"
    temporary_csv = output / "approved_metadata.csv.tmp"
    with temporary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Filename", "Title", "Description", "Keywords"]
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary_csv.replace(csv_file)

    print(f"Approved clips: {len(rows)}")
    print(f"Output: {output}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python export_approved.py <video_folder>")
    export(sys.argv[1])
