import base64
import cv2
import json
import sys
import urllib.request
from pathlib import Path
import argparse

ROOT = Path.home() / "DroneStock"
META = ROOT / "metadata"
parser = argparse.ArgumentParser()
parser.add_argument("candidates", type=Path)
parser.add_argument("output_dir", type=Path)
parser.add_argument("clip_id")
parser.add_argument("--video", type=Path, required=True)
args = parser.parse_args()

DATA = json.loads(args.candidates.read_text())
OUTPUT = args.output_dir
OUTPUT.mkdir(parents=True, exist_ok=True)
clip_id = args.clip_id
clip = next(c for c in DATA["clips"] if c["id"] == clip_id)
video = args.video.resolve()

target = OUTPUT / f"{clip_id}.json"
if target.exists():
    try:
        saved = json.loads(target.read_text())
        if (
            saved.get("analysis")
            and saved.get("clip") == clip
            and saved.get("source") == DATA["source"]
        ):
            print(f"{clip_id}: SKIPPED (already analyzed)")
            sys.exit(0)
    except (OSError, ValueError):
        pass
cap = cv2.VideoCapture(str(video))
if not cap.isOpened():
    raise RuntimeError(f"Cannot open {video}")

images = []

try:
    for fraction in (0.5,):
        timestamp = clip["start"] + clip["duration"] * fraction
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = cap.read()

        if not ok:
            raise RuntimeError(f"Cannot read frame at {timestamp}")

        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (960, round(h * 960 / w)))

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("JPEG encoding failed")

        images.append(
            base64.b64encode(encoded.tobytes()).decode()
        )
finally:
    cap.release()

prompt = """
Analyze the single middle frame from ONE drone stock footage clip.

Return JSON containing:
- subjects: array of clearly visible objects
- scene: factual description of the landscape
- composition_change: "unknown from one frame"
- commercial_uses: array of potential stock footage uses
- quality_concerns: only concerns actually visible in these images

Rules:
- Write in English.
- Do not guess the geographic location.
- Do not invent objects, activities or landmarks.
- Do not evaluate camera smoothness from still images.
- Keep descriptions specific and concise.
"""

payload = {
    "model": "qwen3-vl:4b",
    "think": False,
    "stream": False,
    "format": "json",
    "messages": [{
        "role": "user",
        "content": prompt,
        "images": images
    }],
    "options": {
        "temperature": 0.2,
        "num_ctx": 8192,
        "num_predict": 8192
    }
}

request = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"}
)

print(f"Analyzing {clip_id}...", flush=True)

with urllib.request.urlopen(request, timeout=600) as response:
    result = json.load(response)

if result.get("done_reason") != "stop":
    raise RuntimeError(
        f"Incomplete response: {result.get('done_reason')}"
    )

analysis = json.loads(result["message"]["content"])

required = (
    "subjects", "scene", "composition_change",
    "commercial_uses", "quality_concerns"
)
missing = [key for key in required if key not in analysis]
if missing:
    raise RuntimeError(f"Missing fields: {missing}")

record = {
    "source": DATA["source"],
    "clip": clip,
    "model": "qwen3-vl:4b",
    "analysis": analysis,
    "processing_seconds": round(
        result.get("total_duration", 0) / 1e9, 1
    )
}

target = OUTPUT / f"{clip_id}.json"
target.write_text(
    json.dumps(record, indent=2, ensure_ascii=False)
)

print(json.dumps(analysis, indent=2, ensure_ascii=False))
print(f"\nProcessing: {record['processing_seconds']}s")
print(f"Saved: {target}")
