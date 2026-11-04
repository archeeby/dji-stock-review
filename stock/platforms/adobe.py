"""Adobe Stock CSV adapter. No filesystem changes."""

import hashlib
from pathlib import Path

PLATFORM = "adobe"

COLUMNS = ("Filename", "Title", "Keywords", "Category")


def destination_name(filename):
    if len(filename) <= 30:
        return filename

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:8]
    max_stem = 30 - len(suffix) - len(digest) - 1

    return stem[:max_stem] + "_" + digest + suffix


def shorten(text, limit):
    text = " ".join(str(text).replace(",", " ").split())

    if len(text) <= limit:
        return text

    prefix = text[:limit + 1].rsplit(" ", 1)[0].rstrip(" -,.")

    return prefix if prefix else text[:limit].rstrip(" -,.")


def make_row(record, keywords):
    review = record["review"]

    if len(keywords) < 7:
        return None, None, "fewer than 7 keywords"

    filename = destination_name(record["filename"])

    return {
        "Filename": filename,
        "Title": shorten(review["title"].strip(), 70),
        "Keywords": ", ".join(keywords),
        "Category": "",
    }, filename, None
