"""Prepare platform metadata and synchronize approved uploads.

No video conversion or modification of originals/reviews.
Verify platform CSV schemas before uploading.
"""

import argparse
import csv
from pathlib import Path

ROOT = Path.home() / "DroneStock"


def main():
    from stock.records import (
        load_records as load_stock_records,
        read_json,
    )
    from stock.platforms import (
        PLATFORMS as STOCK_PLATFORMS,
        make_row as make_stock_row,
    )
    from stock.staging import apply_sync

    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument(
        '--platform',
        choices=STOCK_PLATFORMS + ('all',),
        default='all',
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    records = list(load_stock_records(root))

    overrides = read_json(
        root / 'metadata' / 'platform_category_overrides.json',
        {},
    )
    if not isinstance(overrides, dict):
        raise ValueError(
            'platform_category_overrides.json must be a JSON object'
        )

    print(
        f'Approved existing MP4 with matching manifests: '
        f'{len(records)}'
    )

    selected = (
        STOCK_PLATFORMS
        if args.platform == 'all'
        else (args.platform,)
    )

    for platform in selected:
        target = root / 'platforms' / platform
        upload = target / 'upload'

        rows = []
        expected = {}
        used_names = set()

        for record in records:
            row, filename, reason = make_stock_row(
                platform, record, overrides
            )

            if reason:
                print(
                    f'SKIP {platform}: '
                    f'{record["filename"]}: {reason}'
                )
                continue

            if filename in used_names:
                print(
                    f'SKIP {platform}: '
                    f'duplicate staging name: {filename}'
                )
                continue

            used_names.add(filename)
            expected[filename] = record['path']
            rows.append(row)

        # Synchronization must succeed before publishing metadata.
        result = apply_sync(upload, expected)

        target.mkdir(parents=True, exist_ok=True)
        csv_path = target / (platform + '.csv')

        if rows:
            tmp = csv_path.with_suffix('.csv.tmp')

            with tmp.open(
                'w', encoding='utf-8', newline=''
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=list(rows[0]),
                )
                writer.writeheader()
                writer.writerows(rows)

            tmp.replace(csv_path)

        elif csv_path.exists():
            csv_path.unlink()

        print(
            f'{platform}: '
            f'{len(result["created"])} created, '
            f'{len(result["removed"])} removed, '
            f'{len(result["unchanged"])} unchanged, '
            f'{len(result["unknown_preserved"])} '
            f'unknown preserved; '
            f'{len(rows)} metadata rows'
        )

    print(
        'No videos converted. Existing exports, '
        'reviews and originals were not modified.'
    )
    print(
        'CAUTION: Adobe Category is blank; '
        'Shutterstock categories are suggestions.'
    )
    print(
        'Verify current platform CSV schemas/categories '
        'and video resolution before upload.'
    )

if __name__ == '__main__':
    main()
