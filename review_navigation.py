"""Deterministic candidate ordering and navigation after a review decision."""
import re


def candidate_order(clip):
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower())
                 for part in re.split(r'(\d+)', clip['id']))


def next_after_decision(queue, statuses, current, status_filter):
    """Use post-decision statuses; retain the selected filter in the caller."""
    following = list(range(current + 1, len(queue))) + list(range(current))
    if status_filter in ('Pending', 'All'):
        source = queue[current][2]
        same_source = [i for i in following if queue[i][2] == source]
        other_sources = [i for i in following if queue[i][2] != source]
        for i in same_source + other_sources:
            if statuses[i] == 'pending':
                return i
        return current if status_filter == 'All' else None
    for i in following + [current]:
        if statuses[i] == status_filter.lower():
            return i
    return None
