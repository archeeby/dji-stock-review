"""Shared approved-clip discovery and metadata preparation.

Preserves the original exporter behavior.
No video conversion, AI analysis or metadata modification.
"""
from workspace_paths import relocated_source

import json
from pathlib import Path
from resolve_location import get_gps

def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def get_source_date(video):
    from datetime import datetime
    """Read recording date from original DJI MP4."""
    import subprocess

    if not video.is_file():
        return ''

    result = subprocess.run(
        ['exiftool', '-s3', '-CreateDate', str(video)],
        capture_output=True,
        text=True,
        check=True,
    )

    value = result.stdout.strip()
    try:
        return datetime.strptime(
            value, '%Y:%m:%d %H:%M:%S'
        ).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def load_records(root):
    base = root / 'exports' / 'approved'
    location_cache = read_json(
        root / 'metadata' / 'location_details_cache.json', {}
    )
    if not isinstance(location_cache, dict):
        location_cache = {}
    for folder in sorted(base.iterdir() if base.exists() else []):
        if not folder.is_dir():
            continue
        reviews = read_json(root / 'metadata' / 'videos' / folder.name / 'reviews.json', {})
        if not isinstance(reviews, dict):
            continue
        for filename, review in sorted(reviews.items()):
            if not isinstance(review, dict) or review.get('status') != 'approved':
                continue
            mp4 = folder / filename
            if not mp4.is_file() or mp4.stat().st_size == 0:
                print(f'SKIP missing MP4: {mp4}')
                continue
            manifest = read_json(folder / (filename + '.source.json'))
            if not isinstance(manifest, dict):
                print(f'SKIP missing source manifest: {mp4}')
                continue
            try:
                if any(abs(float(manifest[k]) - float(review[k])) > 0.02 for k in ('start', 'end')):
                    print(f'SKIP source time mismatch: {mp4}')
                    continue
            except (KeyError, TypeError, ValueError):
                print(f'SKIP invalid time values: {mp4}')
                continue
            if not all(str(review.get(k, '')).strip() for k in ('title', 'description', 'keywords')):
                print(f'SKIP incomplete metadata: {mp4}')
                continue
            source_video = relocated_source(str(manifest.get('source', '')), root)
            location = {}

            if source_video.is_file():
                try:
                    gps = get_gps(source_video)
                    if gps:
                        key = f'{gps[0]:.4f},{gps[1]:.4f}'
                        location = location_cache.get(key, {})
                except Exception as exc:
                    print(f'WARNING location lookup: {source_video.name}: {exc}')

            yield {
                'path': mp4,
                'filename': filename,
                'review': review,
                'source': source_video,
                'created': get_source_date(source_video),
                'location': location if isinstance(location, dict) else {},
            }


def clean_keywords(value):
    parts = value if isinstance(value, list) else str(value).split(',')
    out, seen = [], set()
    for part in parts:
        word = str(part).strip()
        if word and word.casefold() not in seen:
            out.append(word)
            seen.add(word.casefold())
    return out[:50]
