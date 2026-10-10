"""Spectator identity and a bounded, saved journal of computer empire activity."""

from dataclasses import dataclass

MAX_EVENTS = 240
READ_ONLY = "The Observer can inspect the galaxy but cannot issue empire orders."


@dataclass(frozen=True)
class Observation:
    id: int
    turn: int
    owner: str
    message: str


def record(game, owner, message, turn):
    if not game.is_observer:
        return
    game.observer_events.append(Observation(game.next_observer_event_id, turn, owner, message))
    game.next_observer_event_id += 1
    game.observer_events[:] = game.observer_events[-MAX_EVENTS:]


def load(game, data, version):
    from .model import _integer, _name
    if version < 30:
        return
    rows = data["observer_events"]
    next_id, read = data["next_observer_event_id"], data["observer_news_read"]
    if (not isinstance(rows, list) or len(rows) > MAX_EVENTS
            or not _integer(next_id, 1, 1_000_000_000)
            or not _integer(read, 0, next_id-1)):
        raise ValueError("Invalid observer journal")
    events = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"id", "turn", "owner", "message"}
                or not _integer(row["id"], 1, next_id-1)
                or not _integer(row["turn"], 1, game.turn)
                or row["owner"] not in game.opponents or not _name(row["message"], 400)):
            raise ValueError("Invalid observation")
        events.append(Observation(**row))
    if [e.id for e in events] != list(range(max(1, next_id-MAX_EVENTS), next_id)):
        raise ValueError("Invalid observation sequence")
    if not game.is_observer and (events or next_id != 1 or read):
        raise ValueError("Only observer campaigns have an observer journal")
    game.observer_events, game.next_observer_event_id, game.observer_news_read = events, next_id, read
    if game.is_observer:
        if (not game.opponents or game.diplomacy is not None or game.credits or game.resources
                or game.research or game.designs or game.technology.completed or game.technology.active):
            raise ValueError("The observer cannot own an economy or research")
        if game.combat is not None:
            raise ValueError("Observer battles must resolve within the turn")
