"""Two-decimal editor bounds that never exceed the actual source duration."""
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
import math

MIN_CLIP_SECONDS = 5.0


def editor_duration(duration):
    # Round inward: rounding 116.817 up to 116.82 would exceed the footage.
    return int(Decimal(str(duration)).scaleb(2).to_integral_value(rounding=ROUND_FLOOR)) / 100


def normalize_trim(start, end, duration, changed=None):
    limit = int(Decimal(str(duration)).scaleb(2).to_integral_value(rounding=ROUND_FLOOR))
    if limit < 500:
        raise ValueError("Source video must be at least 5 seconds long")
    a = int(Decimal(str(start)).scaleb(2).to_integral_value(rounding=ROUND_HALF_UP))
    b = int(Decimal(str(end)).scaleb(2).to_integral_value(rounding=ROUND_HALF_UP))
    a = max(0, min(a, limit - 500))
    b = max(500, min(b, limit))
    if changed == "start":
        a = min(a, b - 500)
    else:
        b = max(b, a + 500)
    return a / 100, b / 100


def valid_trim(start, end, duration):
    return (all(math.isfinite(v) for v in (start, end, duration))
            and 0 <= start and end <= duration
            and end - start >= MIN_CLIP_SECONDS - 1e-9)


def adjust_trim_end(start, end, duration, delta):
    """Move only the End boundary, clamping to 5s minimum and source duration."""
    a, b = normalize_trim(start, end, duration)
    maximum = editor_duration(duration)
    desired = max(a + MIN_CLIP_SECONDS, min(maximum, b + delta))
    return normalize_trim(a, desired, duration, changed="end")[1]
