"""Candidate-scoped review identity, status, and reversible JSON updates."""
import copy
import json
from pathlib import Path


def key_for(source, clip_id):
    return f"{Path(source).stem}_{clip_id}.mp4"


def get_review(reviews, source, clip_id):
    # Legacy bare candidate IDs are local to this source folder.
    return reviews.get(key_for(source, clip_id), reviews.get(clip_id, {}))


def review_status(review):
    status = review.get("status", "pending")
    return status if status in ("approved", "rejected") else "pending"


def status_label(status):
    return {"approved": "✅ Approved", "rejected": "❌ Rejected"}.get(status, "Pending")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    temp.replace(path)


def save_review(path, source, clip_id, value):
    reviews = json.loads(path.read_text()) if path.is_file() else {}
    key = key_for(source, clip_id)
    # Snapshot the exact stored key, not a fallback record. Undo then restores
    # legacy data by removing the override, preserving the original JSON shape.
    action = {"key": key, "existed": key in reviews,
              "previous_status": review_status(get_review(reviews, source, clip_id)),
              "previous": copy.deepcopy(reviews.get(key))}
    reviews[key] = copy.deepcopy(value)
    atomic_json(path, reviews)
    return action


def undo_review(path, action, preserve_edits=False):
    reviews = json.loads(path.read_text()) if path.is_file() else {}
    if preserve_edits:
        # Undo the decision while retaining the latest candidate edits, including
        # edits saved after the decision. Other candidate keys remain untouched.
        restored = copy.deepcopy(reviews.get(action["key"], {}))
        restored["status"] = action.get("previous_status", review_status(action["previous"] or {}))
        reviews[action["key"]] = restored
    elif action["existed"]:
        reviews[action["key"]] = action["previous"]
    else:
        reviews.pop(action["key"], None)
    atomic_json(path, reviews)
    return reviews.get(action["key"], {})
