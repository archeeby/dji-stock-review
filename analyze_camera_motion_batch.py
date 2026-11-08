from workspace_paths import data_root
import cv2
import json
import numpy as np
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("video", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()

ROOT = data_root()
VIDEO = args.video.resolve()
OUTPUT = args.output.resolve()

SAMPLE_FPS = 5
WIDTH = 640

cap = cv2.VideoCapture(str(VIDEO))
if not cap.isOpened():
    raise RuntimeError(f"Cannot open video: {VIDEO}")

fps = cap.get(cv2.CAP_PROP_FPS)
if fps <= 0:
    raise RuntimeError("Invalid video FPS")

step = max(1, round(fps / SAMPLE_FPS))
previous = None
previous_motion = None
measurements = []
frame_index = 0

while True:
    ok, frame = cap.read()
    if not ok:
        break

    if frame_index % step != 0:
        frame_index += 1
        continue

    timestamp = frame_index / fps
    height = round(frame.shape[0] * WIDTH / frame.shape[1])
    gray = cv2.resize(
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
        (WIDTH, height)
    )

    record = {
        "time": round(timestamp, 2),
        "dx": None,
        "dy": None,
        "rotation": None,
        "zoom": None,
        "jerk": None,
        "tracked_points": 0
    }

    current_motion = None

    if previous is not None:
        points = cv2.goodFeaturesToTrack(
            previous,
            maxCorners=350,
            qualityLevel=0.01,
            minDistance=8
        )

        if points is not None and len(points) >= 12:
            tracked, status, _ = cv2.calcOpticalFlowPyrLK(
                previous, gray, points, None
            )

            if tracked is not None and status is not None:
                mask = status.ravel() == 1
                src = points.reshape(-1, 2)[mask]
                dst = tracked.reshape(-1, 2)[mask]

                record["tracked_points"] = len(src)

                if len(src) >= 12:
                    matrix, inliers = cv2.estimateAffinePartial2D(
                        src, dst,
                        method=cv2.RANSAC,
                        ransacReprojThreshold=3
                    )

                    if matrix is not None:
                        dx = float(matrix[0, 2])
                        dy = float(matrix[1, 2])
                        rotation = float(
                            np.degrees(
                                np.arctan2(matrix[1, 0], matrix[0, 0])
                            )
                        )
                        zoom = float(
                            np.hypot(matrix[0, 0], matrix[1, 0])
                        )

                        current_motion = np.array(
                            [dx, dy, rotation * 5],
                            dtype=float
                        )

                        record["dx"] = round(dx, 3)
                        record["dy"] = round(dy, 3)
                        record["rotation"] = round(rotation, 4)
                        record["zoom"] = round(zoom, 5)

                        if previous_motion is not None:
                            jerk = float(np.linalg.norm(
                                current_motion - previous_motion
                            ))
                            record["jerk"] = round(jerk, 3)

    measurements.append(record)
    previous = gray
    previous_motion = current_motion
    frame_index += 1

cap.release()

jerks = np.array([
    m["jerk"] for m in measurements
    if m["jerk"] is not None
])

threshold = (
    float(np.percentile(jerks, 95))
    if len(jerks) else None
)

for m in measurements:
    m["jerk_warning"] = (
        m["jerk"] > threshold
        if threshold is not None and m["jerk"] is not None
        else False
    )

result = {
    "filename": VIDEO.name,
    "sample_fps": SAMPLE_FPS,
    "jerk_threshold": round(threshold, 3)
        if threshold is not None else None,
    "measurements": measurements
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(result, indent=2))

warnings = [m for m in measurements if m["jerk_warning"]]

print(f"Analyzed: {VIDEO.name}")
print(f"Samples: {len(measurements)}")
print(f"Jerk threshold: {result['jerk_threshold']}")
print(f"Potential abrupt movements: {len(warnings)}")
print("Strongest changes:")

for m in sorted(
    warnings, key=lambda x: x["jerk"], reverse=True
)[:10]:
    print(f"  {m['time']:6.1f}s | change: {m['jerk']:.2f}")

print(f"Saved: {OUTPUT}")
