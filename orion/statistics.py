"""Per-turn empire totals, recorded independently of diplomatic visibility."""

from dataclasses import dataclass

from . import economy, first_contact
from .empires import PLAYER


@dataclass(frozen=True)
class Metric:
    title: str
    unit: str
    description: str


# Save rows: turn, followed by these six metrics in this fixed order.
METRICS = {
    "population": Metric("Population", "B inhabitants", "Total population across colonies, including enslaved population."),
    "industry": Metric("Industry", "production / turn", "Total industry available for construction and Trade Goods."),
    "food": Metric("Food production", "food / turn", "Gross food produced across colonies, before consumption."),
    "mining": Metric("Mining production", "resources / turn", "Gross extraction from colonies, mines and miners, before power-plant fuel use."),
    "energy": Metric("Energy", "energy / turn", "Actual generation across local colony grids, including fueled backup power."),
    "credits": Metric("Credits per turn", "credits / turn", "Net income after maintenance and specialist salaries, including agreements and Trade Goods."),
}


def sample(game, owner):
    colonies = [p for s in game.systems for p in s.worlds if p.colonized and p.owner == owner]
    bonuses = game.bonuses_for(owner)
    yields = [game.planet_yields(p) for p in colonies]
    trade, _ = game.diplomatic_yields(owner)
    return [game.turn, sum(p.workforce for p in colonies), sum(y[0] for y in yields),
            sum(game.population_report(p).produced for p in colonies),
            sum(economy.mining_output(p, bonuses) for p in colonies),
            sum(game.planet_energy(p).generated for p in colonies), game.empire_rates_for(owner)[0]]


def record(game):
    """Refresh this turn only. Past observations never change or get discarded."""
    for owner in game.owners:
        rows = game.statistics.setdefault(owner, [])
        row = sample(game, owner)
        if rows and rows[-1][0] == game.turn:
            rows[-1] = row
        else:
            rows.append(row)


def visible_owners(game):
    return list(game.owners) if game.is_observer else [PLAYER, *first_contact.known_opponents(game)]


def visible_series(game, metric):
    """Reveal the full recorded history on contact; the current point is live.

    Rendering must neither persist state nor expose even the names or existence
    of uncontacted civilizations. Late empires and migrated saves have gaps.
    """
    index = tuple(METRICS).index(metric)+1
    result = {}
    for owner in visible_owners(game):
        rows = game.statistics.get(owner, [])
        result[owner] = [(r[0], r[index]) for r in rows if r[0] < game.turn]
        result[owner].append((game.turn, sample(game, owner)[index]))
    return result


def load(game, data, version):
    if version < 38:
        # Earlier versions never stored these totals; do not invent a past.
        record(game)
        return
    history = data["statistics"]
    if not isinstance(history, dict) or set(history)-set(game.owners):
        raise ValueError("Invalid statistics empires")
    parsed = {}
    for owner, rows in history.items():
        if not isinstance(rows, list) or len(rows) > game.turn:
            raise ValueError("Invalid statistics history")
        previous = 0
        parsed[owner] = []
        for row in rows:
            if (not isinstance(row, list) or len(row) != 7
                    or any(type(v) is not int for v in row)
                    or not previous < row[0] <= game.turn
                    or any(not 0 <= v <= 10**15 for v in row[1:6])
                    or not -10**15 <= row[6] <= 10**15):
                raise ValueError("Invalid statistics sample")
            parsed[owner].append(row.copy())
            previous = row[0]
    game.statistics = parsed
