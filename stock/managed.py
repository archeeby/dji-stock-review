"""Registry of files managed by the stock exporter."""

import json
import os
from pathlib import Path

REGISTRY_NAME = ".managed-files.json"
REGISTRY_VERSION = 1


def load_registry(upload_dir):
    path = Path(upload_dir) / REGISTRY_NAME

    if not path.exists():
        return set()

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Invalid managed-files registry")

    if data.get("version") != REGISTRY_VERSION:
        raise ValueError("Unsupported managed-files registry version")

    files = data.get("files")

    if not isinstance(files, list):
        raise ValueError("Invalid managed-files list")

    if not all(
        isinstance(name, str)
        and name == Path(name).name
        and name.lower().endswith(".mp4")
        and name not in (".", "..")
        for name in files
    ):
        raise ValueError("Unsafe filename in managed-files registry")

    if len(files) != len(set(files)):
        raise ValueError("Duplicate filenames in managed-files registry")

    return set(files)


def save_registry(upload_dir, names):
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    names = sorted(set(names))

    for name in names:
        if (
            not isinstance(name, str)
            or name != Path(name).name
            or not name.lower().endswith(".mp4")
            or name in (".", "..")
        ):
            raise ValueError(f"Unsafe filename: {name!r}")

    path = upload_dir / REGISTRY_NAME
    temporary = upload_dir / (REGISTRY_NAME + ".tmp")

    if temporary.exists():
        raise FileExistsError(f"Temporary registry already exists: {temporary}")

    payload = {
        "version": REGISTRY_VERSION,
        "files": names,
    }

    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def file_identity(path):
    """Return filesystem identity without following symbolic links."""
    path = Path(path)

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Not a regular file: {path}")

    stat = path.stat()

    return {
        "device": stat.st_dev,
        "inode": stat.st_ino,
    }


def load_registry_v2(upload_dir):
    """Load registry with recorded file identities.

    Version 1 registries are intentionally rejected here.
    """
    path = Path(upload_dir) / REGISTRY_NAME

    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict) or data.get("version") != 2:
        raise ValueError(
            f"Registry requires migration to version 2: {path}"
        )

    files = data.get("files")

    if not isinstance(files, dict):
        raise ValueError("Invalid version 2 registry")

    result = {}

    for name, identity in files.items():
        if (
            not isinstance(name, str)
            or name != Path(name).name
            or not name.lower().endswith(".mp4")
            or name in (".", "..")
        ):
            raise ValueError(f"Unsafe filename: {name!r}")

        if (
            not isinstance(identity, dict)
            or set(identity) != {"device", "inode"}
            or not all(
                type(identity[key]) is int and identity[key] >= 0
                for key in ("device", "inode")
            )
        ):
            raise ValueError(f"Invalid file identity: {name}")

        result[name] = identity

    return result


def save_registry_v2(upload_dir, identities):
    """Atomically save version 2 registry."""
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Validate the entire payload before writing anything.
    for name, identity in identities.items():
        if (
            not isinstance(name, str)
            or name != Path(name).name
            or not name.lower().endswith(".mp4")
            or name in (".", "..")
            or not isinstance(identity, dict)
            or set(identity) != {"device", "inode"}
            or not all(
                type(identity[key]) is int and identity[key] >= 0
                for key in ("device", "inode")
            )
        ):
            raise ValueError(f"Invalid registry entry: {name!r}")

    path = upload_dir / REGISTRY_NAME
    temporary = upload_dir / (REGISTRY_NAME + ".tmp")

    if temporary.exists():
        raise FileExistsError(f"Temporary registry exists: {temporary}")

    payload = {
        "version": 2,
        "files": dict(sorted(identities.items())),
    }

    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def remove_verified_managed_file(upload_dir, filename, identity):
    """Remove only the exact file recorded in a v2 registry.

    Returns True if removed, False if already absent.
    Raises ValueError if the file was replaced or is a symlink.
    """
    import stat

    upload_dir = Path(upload_dir)

    if (
        not isinstance(filename, str)
        or filename != Path(filename).name
        or not filename.lower().endswith(".mp4")
        or filename in (".", "..")
    ):
        raise ValueError(f"Unsafe filename: {filename!r}")

    if (
        not isinstance(identity, dict)
        or set(identity) != {"device", "inode"}
        or not all(
            type(identity[key]) is int and identity[key] >= 0
            for key in ("device", "inode")
        )
    ):
        raise ValueError("Invalid recorded file identity")

    path = upload_dir / filename

    try:
        info = path.lstat()
    except FileNotFoundError:
        return False

    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Not a regular managed file: {path}")

    current = {
        "device": info.st_dev,
        "inode": info.st_ino,
    }

    if current != identity:
        raise ValueError(
            f"Managed file identity mismatch: {path}"
        )

    # The identity is checked immediately before unlink.
    # This does not protect against concurrent filesystem changes;
    # callers must ensure no other process modifies staging.
    path.unlink()
    return True
