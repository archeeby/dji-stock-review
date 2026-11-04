"""Pond5 metadata adapter.

Transforms a normalized approved clip record into a Pond5 CSV row.
Does not access the filesystem or modify video files.
"""

PLATFORM = "pond5"

COLUMNS = (
    "OriginalFilename",
    "name",
    "Description",
    "Keywords",
    "City",
    "Region",
    "Country",
    "Created",
)


def make_row(record, keywords):
    review = record["review"]
    filename = record["filename"]

    title = str(review["title"]).strip()
    description = str(review["description"]).strip()

    if len(keywords) < 7:
        return None, None, "fewer than 7 keywords"

    if len(title) > 80 or len(description) > 500:
        return (
            None,
            None,
            "Pond5 title/description exceeds conservative limits",
        )

    location = record.get("location") or {}

    row = {
        "OriginalFilename": filename,
        "name": title,
        "Description": description,
        "Keywords": ", ".join(keywords),
        "City": location.get("city") or "",
        "Region": location.get("region") or "",
        "Country": location.get("country") or "",
        "Created": record.get("created") or "",
    }

    return row, filename, None
