"""Shutterstock CSV adapter. Categories are unverified suggestions."""

import re

PLATFORM = "shutterstock"

COLUMNS = (
    "Filename", "Description", "Keywords", "Categories",
    "Illustration", "Mature Content", "Editorial",
)

CATEGORY_RULES = (
    ("Nature", ("nature", "forest", "mountain", "waterfall", "river",
                "landscape", "sea", "ocean", "beach", "coast",
                "sunset", "lake", "island", "sky")),
    ("Buildings/Landmarks", ("building", "architecture", "town",
                             "city", "village", "harbor", "harbour",
                             "street", "castle", "bridge")),
    ("Travel", ("travel", "tourism", "destination", "resort",
                "vacation", "holiday", "albania", "croatia", "greece")),
    ("Transportation", ("boat", "ship", "road", "car",
                        "vehicle", "traffic", "port")),
    ("Parks/Outdoor", ("park", "outdoor", "hiking",
                       "trail", "recreation")),
)


def suggest_categories(record, overrides):
    name = record["filename"]

    if name in overrides:
        values = overrides[name]

        if isinstance(values, str):
            values = [values]

        if (
            not isinstance(values, list)
            or not 1 <= len(values) <= 2
            or not all(isinstance(x, str) and x.strip() for x in values)
        ):
            return [], "invalid category override"

        return [x.strip() for x in values], None

    review = record["review"]
    text = " ".join([
        str(review["title"]),
        str(review["description"]),
        str(review["keywords"]),
    ]).casefold()

    ranked = []

    for category, terms in CATEGORY_RULES:
        hits = sum(
            bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text))
            for term in terms
        )

        if hits:
            ranked.append((hits, category))

    ranked.sort(key=lambda item: (-item[0], item[1]))

    return [category for _, category in ranked[:2]], None


def make_row(record, keywords, overrides):
    review = record["review"]

    if len(keywords) < 7:
        return None, None, "fewer than 7 keywords"

    categories, reason = suggest_categories(record, overrides)

    if reason:
        return None, None, reason

    if not categories:
        return None, None, "no category suggestion; add manual override"

    filename = record["filename"]

    return {
        "Filename": filename,
        "Description": str(review["description"]).strip(),
        "Keywords": ", ".join(keywords),
        "Categories": ", ".join(categories),
        "Illustration": "No",
        "Mature Content": "No",
        "Editorial": "No",
    }, filename, None
