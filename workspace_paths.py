"""Repository-relative runtime paths; importing this module never creates data."""
import hashlib
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def data_root() -> Path:
    """Use an explicit workspace override, otherwise the checkout's parent."""
    value = os.environ.get("DJI_STOCK_ROOT")
    if value is not None:
        path = Path(value).expanduser()
        if not value.strip() or not path.is_absolute():
            raise ValueError("DJI_STOCK_ROOT must be a nonempty absolute path")
        return path.resolve()
    return REPO_ROOT.parent


def video_work_dir(video: Path, root: Path) -> Path:
    """Reuse historical metadata after relocation; never rename or regenerate it."""
    video = video.resolve()
    work = root / "metadata" / "videos"
    expected = work / (video.stem + "_" + hashlib.sha256(str(video).encode()).hexdigest()[:10])
    matches = []
    for folder in work.iterdir() if work.exists() else []:
        if not folder.is_dir():
            continue
        candidates = folder / "clip_candidates.json"
        identities = set()
        if candidates.exists():
            owner = json.loads(candidates.read_text()).get("source")
            if owner != video.name and folder != expected:
                continue
        records = (
            (candidates, "source"),
            (folder / "camera_motion.json", "filename"),
            (folder / "composition_analysis.json", "filename"),
        )
        for record, key in records:
            if record.exists():
                data = json.loads(record.read_text())
                identity = data.get(key)
                if not isinstance(identity, str) or not identity:
                    raise RuntimeError(f"Missing source identity in {record}")
                identities.add(identity)
        if video.name in identities:
            if len(identities) != 1:
                raise RuntimeError(f"Conflicting source identities in {folder}")
            matches.append(folder)
        elif folder == expected and identities:
            raise RuntimeError(f"Conflicting source identity in {folder}")
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous existing metadata for {video.name}; select explicitly before processing")
    if matches and matches[0] != expected:
        sources = [p for p in (root / "originals").rglob("*")
                   if p.is_file() and p.name == video.name]
        if len(sources) > 1:
            raise RuntimeError(f"Ambiguous original filename: {video.name}")
        if (not video.is_relative_to((root / "originals").resolve())
                or sources and sources[0].resolve() != video):
            raise RuntimeError(f"Cannot reuse workspace metadata for external source: {video}")
    return matches[0] if matches else expected


def relocated_source(source: str, root: Path) -> Path:
    """Resolve a historical manifest path only within this workspace's originals."""
    old = Path(source)
    if old.is_file():
        return old
    if "originals" not in old.parts:
        return old
    relative = Path(*old.parts[old.parts.index("originals") + 1:])
    candidate = (root / "originals" / relative).resolve()
    if candidate.is_relative_to((root / "originals").resolve()) and candidate.is_file():
        return candidate
    return old


def same_export(existing: dict | None, expected: dict, root: Path) -> bool:
    """A workspace move alone must not trigger re-encoding an existing export."""
    if existing is None:
        return False
    actual = dict(existing)
    actual["source"] = str(relocated_source(str(actual.get("source", "")), root))
    return actual == expected
