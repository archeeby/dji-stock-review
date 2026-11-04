"""Safe, read-only staging planner.

Never deletes files. Never modifies MP4, CSV or metadata.
"""

from pathlib import Path


def plan_sync(upload_dir, expected, managed_names=()):
    """Compare expected clips with existing staged files.

    expected: mapping destination filename -> approved source Path
    managed_names: filenames previously registered by this exporter
    """
    upload_dir = Path(upload_dir)
    managed = set(managed_names)

    actual = {
        p.name: p
        for p in upload_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".mp4"
    } if upload_dir.is_dir() else {}

    expected_names = set(expected)
    actual_names = set(actual)

    missing = sorted(expected_names - actual_names)
    stale_managed = sorted((actual_names - expected_names) & managed)
    unknown = sorted((actual_names - expected_names) - managed)

    mismatched = []
    for name in sorted(expected_names & actual_names):
        source = Path(expected[name])
        if not source.samefile(actual[name]):
            mismatched.append(name)

    return {
        "create": missing,
        "remove_managed": stale_managed,
        "unknown_preserved": unknown,
        "conflicts": mismatched,
        "unchanged": sorted(
            (expected_names & actual_names) - set(mismatched)
        ),
    }



def apply_sync(upload_dir, expected):
    """Synchronize verified hardlinks using the v2 ownership registry.

    Requires exclusive access to the staging directory.
    Refuses legacy v1 registries and conflicting files.
    """
    import os
    from stock.managed import (
        file_identity,
        load_registry_v2,
        save_registry_v2,
        remove_verified_managed_file,
    )

    upload_dir = Path(upload_dir)

    # Load v2 first. Legacy registries must fail before any changes.
    managed = load_registry_v2(upload_dir)

    for name, approved in expected.items():
        if (
            not isinstance(name, str)
            or name != Path(name).name
            or not name.lower().endswith(".mp4")
            or name in (".", "..")
        ):
            raise ValueError(f"Unsafe destination: {name!r}")

        if not Path(approved).is_file():
            raise FileNotFoundError(f"Approved source missing: {approved}")

    plan = plan_sync(upload_dir, expected, set(managed))

    if plan["conflicts"]:
        raise FileExistsError(
            f"Conflicting staged files: {plan['conflicts']}"
        )

    # Verify all existing registered files before modifying anything.
    for name in sorted(set(managed) & set(plan["unchanged"])):
        destination = upload_dir / name

        if file_identity(destination) != managed[name]:
            raise ValueError(f"Managed file replaced: {destination}")

    for name in plan["remove_managed"]:
        destination = upload_dir / name

        if destination.exists() or destination.is_symlink():
            if file_identity(destination) != managed[name]:
                raise ValueError(
                    f"Refusing to delete replaced file: {destination}"
                )

    created = []

    try:
        for name in plan["create"]:
            upload_dir.mkdir(parents=True, exist_ok=True)
            destination = upload_dir / name
            os.link(Path(expected[name]), destination)
            created.append(name)

        # Register new links before attempting any removal.
        updated = dict(managed)

        for name in created:
            updated[name] = file_identity(upload_dir / name)

        save_registry_v2(upload_dir, updated)

    except Exception:
        # Roll back only newly created, still-matching hardlinks.
        for name in reversed(created):
            destination = upload_dir / name
            approved = Path(expected[name])

            if (
                not destination.is_symlink()
                and destination.is_file()
                and approved.is_file()
                and os.path.samefile(destination, approved)
            ):
                destination.unlink()

        raise

    removed = []

    for name in plan["remove_managed"]:
        if remove_verified_managed_file(
            upload_dir, name, managed[name]
        ):
            removed.append(name)

    # Rebuild the registry from verified current exports.
    remaining = {}

    for name, approved in expected.items():
        destination = upload_dir / name

        if (
            destination.is_symlink()
            or not destination.is_file()
            or not os.path.samefile(destination, Path(approved))
        ):
            raise RuntimeError(
                f"Staging changed during sync: {destination}"
            )

        remaining[name] = file_identity(destination)

    save_registry_v2(upload_dir, remaining)

    return {
        "created": created,
        "removed": removed,
        "unchanged": plan["unchanged"],
        "unknown_preserved": plan["unknown_preserved"],
    }
