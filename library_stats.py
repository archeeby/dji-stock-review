from workspace_paths import data_root
import csv
import json
from pathlib import Path
from candidate_reviews import key_for, get_review, review_status

ROOT = data_root()
WORK = ROOT / "metadata" / "videos"
EXPORTS = ROOT / "exports" / "approved"


def load_json(path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def get_library_stats():
    videos = []
    totals = {
        "videos": 0,
        "candidates": 0,
        "approved": 0,
        "rejected": 0,
        "pending": 0,
        "exported": 0,
        "needs_export": 0,
        "outdated": 0,
    }

    folders_by_source = {}

    for folder in sorted(WORK.iterdir()) if WORK.exists() else []:
        candidates_file = folder / "clip_candidates.json"
        if not candidates_file.is_file():
            continue

        data = load_json(candidates_file, {})
        source_name = data.get("source", folder.name)
        reviews = load_json(folder / "reviews.json", {})

        score = (
            bool(reviews),
            sum(1 for r in reviews.values()
                if r.get("status") in ("approved", "rejected")),
            len(list((EXPORTS / folder.name).glob("*.mp4")))
            if (EXPORTS / folder.name).exists() else 0
        )

        previous = folders_by_source.get(source_name)
        if previous is None or score > previous[0]:
            folders_by_source[source_name] = (score, folder)

    # Decision counts select duplicate folders but must never reorder the queue.
    for folder in sorted(entry[1] for entry in folders_by_source.values()):
        data = load_json(folder / "clip_candidates.json", {})
        reviews = load_json(folder / "reviews.json", {})
        source_name = data.get("source", folder.name)

        video = {
            "folder": folder.name,
            "source": source_name,
            "candidates": 0,
            "approved": 0,
            "rejected": 0,
            "pending": 0,
            "exported": 0,
            "needs_export": 0,
            "outdated": 0,
        }

        csv_path = EXPORTS / folder.name / "approved_metadata.csv"
        exported_metadata = {}
        if csv_path.is_file():
            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                exported_metadata = {row["Filename"]: row for row in csv.DictReader(csv_file)}

        for clip in data.get("clips", []):
            clip_id = clip["id"]
            filename = key_for(source_name, clip_id)
            review = get_review(reviews, source_name, clip_id)
            status = review_status(review)

            video["candidates"] += 1

            if status not in ("approved", "rejected"):
                status = "pending"

            video[status] += 1

            if status != "approved":
                continue

            target = EXPORTS / folder.name / filename
            manifest = Path(str(target) + ".source.json")

            if not target.is_file() or not manifest.is_file():
                video["needs_export"] += 1
                continue

            spec = load_json(manifest, {})
            start = float(review.get("start", clip["start"]))
            end = float(review.get("end", clip["end"]))

            record = load_json(folder / "stock_metadata" / f"{clip_id}.json", {})
            metadata = record.get("metadata", {})
            keywords = review.get("keywords", ", ".join(metadata.get("keywords", [])))
            if isinstance(keywords, list):
                keywords = ", ".join(keywords)
            expected_metadata = {
                "Filename": filename,
                "Title": review.get("title", metadata.get("title", "")).strip(),
                "Description": review.get("description", metadata.get("description", "")).strip(),
                "Keywords": keywords.strip(),
            }
            if (
                exported_metadata.get(filename) == expected_metadata
                and abs(float(spec.get("start", -1)) - start) < 0.001
                and abs(float(spec.get("end", -1)) - end) < 0.001
            ):
                video["exported"] += 1
            else:
                video["outdated"] += 1

        videos.append(video)
        totals["videos"] += 1

        for key in totals:
            if key != "videos":
                totals[key] += video[key]

    return totals, videos


if __name__ == "__main__":
    totals, videos = get_library_stats()

    print("\nLIBRARY OVERVIEW")
    for key, value in totals.items():
        print(f"{key:15} {value}")

    print("\nVIDEOS")
    for video in videos:
        print(
            f"{video['source']}: "
            f"{video['exported']}/{video['approved']} exported, "
            f"{video['needs_export']} missing, "
            f"{video['outdated']} outdated"
        )
