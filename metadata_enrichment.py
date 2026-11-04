#!/usr/bin/env python3
"""Read-only DJI original metadata extraction and cached per-source telemetry."""
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
FIELDS = ('$SampleTime,$GPSLatitude,$GPSLongitude,$GPSAltitude,$GPSSpeed,$VerticalSpeed')


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout


def number(value):
    try:
        value = value.strip()
        if not value or value == '-':
            return None
        return float(value)
    except (ValueError, AttributeError):
        return None


def first_tag(data, *names):
    for name in names:
        if name in data:
            return data[name]
    return None


def extract(video):
    raw = json.loads(command(['exiftool', '-j', '-n', '-G1', '-s', str(video)]))[0]
    # ExifTool -p expands one row per embedded telemetry sample. It can emit a
    # header record with missing tags; only keep rows with numeric sample times.
    telemetry_text = command(['exiftool', '-ee', '-n', '-p', FIELDS, str(video)])
    samples = []
    for line in telemetry_text.splitlines():
        parts = line.strip().split(',')
        if len(parts) != 6:
            continue
        values = [number(part) for part in parts]
        if values[0] is None:
            continue
        samples.append(dict(zip(('time_s', 'latitude', 'longitude', 'altitude_m_dji', 'horizontal_speed_kmh', 'vertical_speed_mps'), values)))
    samples.sort(key=lambda row: row['time_s'])
    gps_lat = first_tag(raw, 'Composite:GPSLatitude', 'UserData:GPSLatitude')
    gps_lon = first_tag(raw, 'Composite:GPSLongitude', 'UserData:GPSLongitude')
    if gps_lat is None or gps_lon is None:
        gps = first_tag(raw, 'UserData:GPSCoordinates')
        if isinstance(gps, str):
            match = re.match(r'^\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)', gps)
            if match:
                gps_lat, gps_lon = map(float, match.groups())
    return {
        'schema_version': SCHEMA_VERSION,
        'source': {'filename': video.name, 'size_bytes': video.stat().st_size,
                   'mtime_ns': video.stat().st_mtime_ns},
        'capture_datetime_raw': first_tag(raw, 'QuickTime:CreateDate'),
        'capture_timezone': None,
        'camera_model': first_tag(raw, 'UserData:Model'),
        'video': {
            'width': first_tag(raw, 'Track1:ImageWidth'),
            'height': first_tag(raw, 'Track1:ImageHeight'),
            'fps': first_tag(raw, 'Track1:VideoFrameRate'),
            'duration_s': first_tag(raw, 'QuickTime:Duration'),
            'bitrate_bps': first_tag(raw, 'Composite:AvgBitrate'),
            'compressor': first_tag(raw, 'Track1:CompressorID'),
        },
        'source_gps': {'latitude': gps_lat, 'longitude': gps_lon},
        'telemetry': {
            'source': 'DJI embedded subtitle track via ExifTool -ee -p',
            'altitude_reference': 'DJI H; datum not verified',
            'samples': samples,
            'sample_count': len(samples),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    video = args.video.expanduser().resolve()
    if not video.is_file():
        parser.error('Video does not exist: ' + str(video))
    output = args.output or (Path.home() / 'DroneStock' / 'metadata' / 'source_enrichment' / (video.stem + '.json'))
    if output.exists() and not args.force:
        try:
            cached = json.loads(output.read_text(encoding='utf-8'))
            source = cached.get('source', {})
            if cached.get('schema_version') == SCHEMA_VERSION and source.get('size_bytes') == video.stat().st_size and source.get('mtime_ns') == video.stat().st_mtime_ns and source.get('filename') == video.name:
                print('CACHED:', output)
                print('Samples:', cached.get('telemetry', {}).get('sample_count'))
                return
        except (OSError, ValueError):
            pass
    data = extract(video)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(output)
    print('SAVED:', output)
    print('GPS:', data['source_gps'])
    print('Samples:', data['telemetry']['sample_count'])
    print('Video:', data['video'])


if __name__ == '__main__':
    main()
