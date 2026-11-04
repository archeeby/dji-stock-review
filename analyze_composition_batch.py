import cv2
import json
import numpy as np
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("video", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()

ROOT = Path.home() / "DroneStock"
VIDEO = args.video.resolve()
OUTPUT = args.output.resolve()

SAMPLE_SECONDS = 1.0
WIDTH = 320

cap = cv2.VideoCapture(str(VIDEO))

if not cap.isOpened():
    raise RuntimeError(f"Cannot open: {VIDEO}")

fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
duration = frame_count / fps

measurements = []
previous_hist = None
previous_gray = None

for second in np.arange(0, duration, SAMPLE_SECONDS):
    cap.set(cv2.CAP_PROP_POS_MSEC, float(second * 1000))
    ok, frame = cap.read()

    if not ok:
        continue

    height = round(frame.shape[0] * WIDTH / frame.shape[1])
    frame = cv2.resize(frame, (WIDTH, height))

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    hist = cv2.calcHist(
        [hsv], [0, 1], None, [24, 24], [0, 180, 0, 256]
    )
    cv2.normalize(hist, hist, alpha=1, norm_type=cv2.NORM_L1)

    color_change = None
    visual_change = None

    if previous_hist is not None:
        color_change = float(
            cv2.compareHist(
                previous_hist, hist, cv2.HISTCMP_BHATTACHARYYA
            )
        )
        visual_change = float(
            np.mean(cv2.absdiff(previous_gray, gray)) / 255
        )

    measurements.append({
        "time": round(float(second), 2),
        "color_change": (
            round(color_change, 5)
            if color_change is not None else None
        ),
        "visual_change": (
            round(visual_change, 5)
            if visual_change is not None else None
        )
    })

    previous_hist = hist
    previous_gray = gray

cap.release()

result = {
    "filename": VIDEO.name,
    "duration": round(duration, 3),
    "sample_seconds": SAMPLE_SECONDS,
    "measurements": measurements
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(result, indent=2))

print(f"Analyzed: {VIDEO.name}")
print(f"Samples: {len(measurements)}")

for key in ("color_change", "visual_change"):
    values = [
        m[key] for m in measurements if m[key] is not None
    ]
    print(
        f"{key}: mean={np.mean(values):.4f}, "
        f"max={np.max(values):.4f}"
    )

print(f"Saved: {OUTPUT}")
