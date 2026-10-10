"""A common view of private tomb-world and raid dispatches."""

from dataclasses import dataclass
from . import raiding, tomb_worlds


@dataclass(frozen=True)
class NewsEntry:
    turn: int
    system_id: int | None
    planet_id: int | None
    category: str
    headline: str
    detail: str
    order: int = 0


def entries(game):
    rows = [NewsEntry(t.awakened_turn, t.system_id, t.planet_id, "REMNANT AWAKENING",
                      tomb_worlds.headline(game, t), tomb_worlds.outcome_text(game, t))
            for t in tomb_worlds.news(game)]
    rows += [NewsEntry(r.turn, r.system_id, r.planet_id, "VARKESH RAID",
                       raiding.headline(game, r), raiding.outcome_text(game, r), r.id)
             for r in raiding.news(game)]
    rows += [NewsEntry(r.turn, r.system_id, None, "HOSTILE SENSOR CONTACT",
                      f"Hostile fleet detected near {game.systems[r.system_id].name}.",
                      f"{game.empire_name_for(r.owner)} · "+(f"{r.count} ships" if r.count is not None else "Ship count unknown")+
                      ". Open the galaxy sensor overlay for the latest contact positions.", r.id)
             for r in game.sensor_reports if r.observer == "player"]
    rows += [NewsEntry(e.turn, None, None, "EMPIRE ACTIVITY", game.empire_name_for(e.owner), e.message, e.id)
             for e in game.observer_events]
    return sorted(rows, key=lambda n: (n.turn, n.order, n.system_id if n.system_id is not None else -1,
                                      n.planet_id if n.planet_id is not None else -1), reverse=True)


def unread_count(game):
    return (tomb_worlds.unread_count(game)+sum(r.id > game.raid_news_read for r in raiding.news(game))+
            sum(r.observer == "player" and r.id > game.sensor_news_read for r in game.sensor_reports)+
            sum(e.id > game.observer_news_read for e in game.observer_events))


def mark_read(game):
    game.news_read_turn = game.turn
    game.raid_news_read = game.next_raid_id-1
    game.sensor_news_read = game.next_sensor_report_id-1
    game.observer_news_read = game.next_observer_event_id-1
