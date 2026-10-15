"""Reuse read-only queries during one drawing pass, never across game actions.

Cached queries take hashable arguments. Drawing code must treat their returned
collections as read-only. The scope is deliberately short: a new frame sees all
orders, arrivals, ownership changes, research and diplomacy without an invalidation
list. No cache is kept during simulation or written into a campaign save.
"""
from contextlib import contextmanager
from functools import wraps


@contextmanager
def frame_queries(game):
    if game is None:
        yield
        return
    previous = getattr(game, '_frame_queries', None)
    game._frame_queries = {}
    try:
        yield
    finally:
        if previous is None:
            del game._frame_queries
        else:
            game._frame_queries = previous


def cached_in_frame(query):
    @wraps(query)
    def lookup(game, *args, **kwargs):
        cache = getattr(game, '_frame_queries', None)
        if cache is None:
            return query(game, *args, **kwargs)
        key = (query, args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = query(game, *args, **kwargs)
        return cache[key]
    return lookup
