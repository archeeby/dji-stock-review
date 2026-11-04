"""Registry of independent stock-platform metadata adapters."""

from . import adobe, pond5, shutterstock

ADAPTERS = {
    "pond5": pond5,
    "adobe": adobe,
    "shutterstock": shutterstock,
}

PLATFORMS = tuple(ADAPTERS)


def make_row(platform, record, overrides=None):
    if platform not in ADAPTERS:
        raise ValueError(f"Unknown platform: {platform}")

    from stock.records import clean_keywords

    keywords = clean_keywords(record["review"]["keywords"])
    adapter = ADAPTERS[platform]

    if platform == "shutterstock":
        return adapter.make_row(record, keywords, overrides or {})

    return adapter.make_row(record, keywords)
