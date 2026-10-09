"""A common view of private tomb-world and raid dispatches."""

from dataclasses import dataclass
from . import raiding, tomb_worlds


@dataclass(frozen=True)
class NewsEntry:
    turn: int
    system_id: int
    planet_id: int
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
    return sorted(rows, key=lambda n: (n.turn, n.order, n.system_id, n.planet_id), reverse=True)


def unread_count(game):
    return tomb_worlds.unread_count(game)+sum(r.id > game.raid_news_read for r in raiding.news(game))


def mark_read(game):
    game.news_read_turn = game.turn
    game.raid_news_read = game.next_raid_id-1
