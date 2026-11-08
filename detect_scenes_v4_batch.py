from workspace_paths import data_root
import json
import math
import statistics
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("composition", type=Path)
parser.add_argument("motion", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()

ROOT = data_root()
META = ROOT / "metadata"

composition = json.loads(
    args.composition.read_text()
)
motion = json.loads(
    args.motion.read_text()
)

duration = float(composition["duration"])
MIN_LENGTH = 5.0
TARGET_LENGTH = 22.0
MAX_LENGTH = 30.0

samples = motion["measurements"]

warnings = []
spikes = []

for i, m in enumerate(samples):
    if m.get("dx") is None or m.get("dy") is None:
        continue

    speed = math.hypot(m["dx"], m["dy"])

    neighbors = [
        math.hypot(x["dx"], x["dy"])
        for x in samples[max(0, i-15):min(len(samples), i+16)]
        if x.get("dx") is not None and x.get("dy") is not None
    ]

    baseline = statistics.median(neighbors)

    speed_spike = speed > max(4.0, baseline * 2.5)

    if m.get("jerk_warning"):
        warnings.append(float(m["time"]))

    if speed_spike:
        spikes.append(float(m["time"]))

for t in spikes:
    if any(0 < abs(t - other) <= 1.0 for other in spikes):
        warnings.append(t)

warnings = sorted(set(warnings))

# Group nearby camera-motion warnings into excluded intervals.
excluded = []
for t in warnings:
    start = max(0.0, t - 0.4)
    end = min(duration, t + 0.8)

    if excluded and start <= excluded[-1]["end"] + 0.6:
        excluded[-1]["end"] = max(excluded[-1]["end"], end)
    else:
        excluded.append({"start": start, "end": end})

# Find remaining usable time intervals.
usable = []
cursor = 0.0

for interval in excluded:
    if interval["start"] - cursor >= MIN_LENGTH:
        usable.append((cursor, interval["start"]))
    cursor = max(cursor, interval["end"])

if duration - cursor >= MIN_LENGTH:
    usable.append((cursor, duration))

measurements = [
    m for m in composition["measurements"]
    if m.get("visual_change") is not None
]

def boundary_score(time):
    if not measurements:
        return 0.0

    nearest = min(
        measurements,
        key=lambda m: abs(float(m["time"]) - time)
    )

    if abs(float(nearest["time"]) - time) > 1.5:
        return 0.0

    return float(nearest["visual_change"])


def motion_change_score(time):
    before = [
        m for m in samples
        if time - 4.0 <= m["time"] < time - 1.0
        and not m.get("jerk_warning")
        and m.get("dx") is not None
        and m.get("dy") is not None
    ]
    after = [
        m for m in samples
        if time + 1.0 < m["time"] <= time + 4.0
        and not m.get("jerk_warning")
        and m.get("dx") is not None
        and m.get("dy") is not None
    ]

    if len(before) < 5 or len(after) < 5:
        return 0.0

    bx = statistics.median(m["dx"] for m in before)
    by = statistics.median(m["dy"] for m in before)
    ax = statistics.median(m["dx"] for m in after)
    ay = statistics.median(m["dy"] for m in after)

    change = math.hypot(ax - bx, ay - by)
    return min(change / 2.0, 1.0)

clips = []

for segment_start, segment_end in usable:
    start = segment_start

    while segment_end - start >= MIN_LENGTH:
        remaining = segment_end - start

        if remaining <= MAX_LENGTH:
            end = segment_end
        else:
            low = start + MIN_LENGTH
            high = min(start + MAX_LENGTH, segment_end - MIN_LENGTH)
            # Balance the remaining interval into as few clips
            # as possible, each no longer than MAX_LENGTH.
            parts = math.ceil(remaining / MAX_LENGTH)
            preferred = min(
                max(start + remaining / parts, low),
                high
            )

            candidates = [
                float(m["time"])
                for m in measurements
                if low <= float(m["time"]) <= high
            ]

            if candidates:
                end = max(
                    candidates,
                    key=lambda t: (
                        0.65 * motion_change_score(t)
                        + 0.35 * boundary_score(t)
                        - 0.004 * abs(t - preferred)
                    )
                )
            else:
                end = preferred

        clips.append({
            "id": f"auto_{len(clips) + 1:02d}",
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(end - start, 2),
            "status": "auto_candidate"
        })

        start = end

result = {
    "source": composition["filename"],
    "method": "motion_phase_heuristic_v4",
    "duration": duration,
    "clips": clips,
    "excluded": excluded
}

output = args.output
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2))

print("Automatic scene candidates:")
for clip in clips:
    print(
        f"  {clip['id']}: "
        f"{clip['start']:.2f}–{clip['end']:.2f}s "
        f"({clip['duration']:.2f}s)"
    )

print(f"\nExcluded intervals: {len(excluded)}")
print(f"Candidates: {len(clips)}")
print(f"Saved: {output}")
