import json
import re
import sys
import time
import urllib.request
from pathlib import Path
import argparse

ROOT = Path.home() / "DroneStock"
META = ROOT / "metadata"

parser = argparse.ArgumentParser()
parser.add_argument("candidates", type=Path)
parser.add_argument("analysis_dir", type=Path)
parser.add_argument("output_dir", type=Path)
parser.add_argument("--location", required=True)
args = parser.parse_args()

SOURCE = args.analysis_dir
OUTPUT = args.output_dir
OUTPUT.mkdir(parents=True, exist_ok=True)
DATA = json.loads(args.candidates.read_text())

LOCATION_TEXT = args.location.strip()
if not LOCATION_TEXT:
    raise ValueError("Location cannot be empty")

LOCATION_KNOWN = LOCATION_TEXT.lower() != "unknown"
LOCATION = (
    [x.strip() for x in LOCATION_TEXT.split(",") if x.strip()]
    if LOCATION_KNOWN else []
)

LOCATION_CONTEXT = (
    f"Verified location: {LOCATION_TEXT}."
    if LOCATION_KNOWN else
    "Location is unknown. Do not mention geographic names."
)

MODEL = "qwen3:4b"


def ask_ai(prompt, schema):
    payload = {
        "model": MODEL,
        "think": False,
        "stream": False,
        "format": schema,
        "messages": [{
            "role": "user",
            "content": prompt
        }],
        "options": {
            "temperature": 0,
            "num_predict": 1024,
            "num_ctx": 4096
        }
    }

    request = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)

    if result.get("done_reason") != "stop":
        raise RuntimeError(
            f"Incomplete AI response: {result.get('done_reason')}"
        )

    return json.loads(result["message"]["content"])


def clean_keywords(words, include_location=True):
    result = []
    seen = set()

    source_words = (LOCATION if include_location else []) + words

    for word in source_words:
        if not isinstance(word, str):
            continue

        word = word.strip().strip(".,; ")
        normalized = re.sub(r"\s+", " ", word).lower()

        if (
            not normalized
            or normalized in seen
            or "," in word
            or len(word) > 35
            or len(word.split()) > 4
        ):
            continue

        seen.add(normalized)
        result.append(word)

    return result


TITLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 100},
        "description": {"type": "string", "maxLength": 350}
    },
    "required": ["title", "description"],
    "additionalProperties": False
}

KEYWORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "minItems": 10,
            "maxItems": 15,
            "items": {"type": "string", "maxLength": 35}
        }
    },
    "required": ["keywords"],
    "additionalProperties": False
}


def process(clip):
    clip_id = clip["id"]
    target = OUTPUT / f"{clip_id}.json"

    if target.exists():
        try:
            saved = json.loads(target.read_text())
            metadata = saved["metadata"]
            if (
                saved["clip"] == clip
                and saved.get("location") == LOCATION_TEXT
                and metadata["title"]
                and metadata["description"]
                and len(metadata["keywords"]) >= 15
            ):
                print(f"{clip_id}: SKIPPED", flush=True)
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass

    analysis = json.loads(
        (SOURCE / f"{clip_id}.json").read_text()
    )["analysis"]

    scene = analysis["scene"]
    subjects = ", ".join(analysis["subjects"])
    composition = analysis["composition_change"]

    context = (
        f"{LOCATION_CONTEXT}\n"
        f"Scene: {scene}\n"
        f"Visible subjects: {subjects}\n"
        f"Composition: {composition}\n"
    )

    print(f"{clip_id}: Generating stock metadata...", flush=True)

    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "keywords": {
                "type": "array",
                "minItems": 15,
                "maxItems": 30,
                "items": {"type": "string", "maxLength": 35}
            }
        },
        "required": ["title", "description", "keywords"],
        "additionalProperties": False
    }

    text = ask_ai(
        "You are a professional stock footage metadata editor. "
        "Create factual English metadata for aerial drone footage. "
        "Write a natural title under 100 characters and a concise "
        "description of 120-220 characters, maximum two sentences. "
        "Generate 20-30 distinct natural stock search keywords. "
        "Include all visible objects, landscape and verified geography. "
        "Avoid commercial uses, marketing phrases, photography terms, "
        "invented landmarks, unsupported activities, camera movements "
        "not explicitly verified, and redundant synonyms. "
        "Describe only visible scenery. Do not mention docks, "
        "harbors, boat mooring, or camera direction unless "
        "explicitly verified by the input. "
        "Do not repeat the location in the description. "
        "Include verified geographic names as separate keywords. "
        "Do not claim a harbor, dock or yacht unless explicitly confirmed. "
        "Context:\n" + context,
        schema
    )

    if not LOCATION_KNOWN:
        forbidden = ("unknown", "location is not verified")
        text["keywords"] = [
            k for k in text["keywords"]
            if isinstance(k, str)
            and not any(x in k.lower() for x in forbidden)
        ]
        for field in ("title", "description"):
            if any(x in text[field].lower() for x in forbidden):
                raise RuntimeError(
                    f"Unverified location leaked into {field}"
                )

    keywords = clean_keywords(
        text["keywords"] + ["aerial view", "drone footage"]
    )
    # Remove malformed and repeated keywords without discarding
    # legitimate scene details such as harbor or docked boats.
    cleaned = []
    seen = set()

    for keyword in keywords:
        keyword = " ".join(keyword.strip().split())
        if not keyword or ":" in keyword:
            continue
        if len(keyword) > 35 or len(keyword.split()) > 4:
            continue
        key = keyword.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(keyword)

    keywords = cleaned
    suggested_keywords = []

    title = text["title"].strip()
    description = text["description"].strip()

    if not title or len(title) > 100:
        raise RuntimeError("Invalid title")

    if not description or len(description) > 350:
        print(f"Description length: {len(description)}")
        print(f"Description content: {description!r}")
        raise RuntimeError("Invalid description")

    if len(keywords) < 8:
        raise RuntimeError(
            f"Insufficient unique keywords: {len(keywords)}"
        )

    record = {
        "source": DATA["source"],
        "clip": clip,
        "location": LOCATION_TEXT,
        "model": MODEL,
        "metadata": {
            "title": title,
            "description": description,
            "keywords": keywords,
            "suggested_keywords": suggested_keywords
        }
    }

    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(record, indent=2, ensure_ascii=False)
    )
    temporary.replace(target)

    print(f"  Title: {title}")
    print(f"  Keywords: {len(keywords)}")
    print(f"  Saved: {target}", flush=True)


def main():
    selected = set()

    for clip in DATA["clips"]:
        if selected and clip["id"] not in selected:
            continue

        try:
            process(clip)
        except Exception as exc:
            print(f"{clip['id']}: ERROR: {exc}", flush=True)


if __name__ == "__main__":
    main()
