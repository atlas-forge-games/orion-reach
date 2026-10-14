"""Read-only colony reports derived from the current campaign; no save schema."""

from dataclasses import dataclass
from .model import PLAYER

FILTERS = ("all", "building", "idle", "full", "power")
SORT_KEYS = ("name", "population", "food", "industry", "income", "research", "slots")
COLONIES_PER_PAGE = 5


@dataclass(frozen=True)
class EmpireSummary:
    colonies: int = 0
    population: int = 0
    slaves: int = 0
    industry: int = 0
    income: int = 0
    gross_income: int = 0
    maintenance: int = 0
    research: int = 0
    used_slots: int = 0
    capacity: int = 0
    projects: int = 0
    idle: int = 0
    agreement_income: int = 0
    agreement_research: int = 0
    food_produced: int = 0
    food_consumed: int = 0
    food_shortages: int = 0
    resources: int = 0
    energy_generated: int = 0
    energy_demand: int = 0
    energy_shortages: int = 0


def colony_rows(game, filter_by="all", sort_by="name", descending=False, *, owner=PLAYER):
    """Return actual system/planet pairs; sorting must never change selection IDs."""
    if filter_by not in FILTERS or sort_by not in SORT_KEYS:
        raise ValueError("Unknown colony filter or sort order.")
    rows = [(system, planet) for system in game.systems
            for planet in system.worlds if planet.colonized and planet.owner == owner]
    if filter_by == "building":
        rows = [(s, p) for s, p in rows if p.construction_queue and not p.trade_goods]
    elif filter_by == "idle":
        rows = [(s, p) for s, p in rows if p.production_idle]
    elif filter_by == "full":
        rows = [(s, p) for s, p in rows if p.free_slots == 0]
    elif filter_by == "power":
        rows = [(s, p) for s, p in rows if game.planet_energy(p).balance < 0]
    # Deterministic alphabetical ties, even for descending numerical sorts.
    rows.sort(key=lambda row: (row[1].name.casefold(), row[0].name.casefold(), row[0].id, row[1].id))
    keys = {
        "name": lambda row: row[1].name.casefold(),
        "population": lambda row: row[1].workforce,
        "food": lambda row: game.population_report(row[1]).balance,
        "industry": lambda row: game.planet_yields(row[1])[0],
        "income": lambda row: game.planet_yields(row[1])[1],
        "research": lambda row: game.planet_yields(row[1])[2],
        "slots": lambda row: row[1].used_slots,
    }
    return sorted(rows, key=keys[sort_by], reverse=descending)


def summarize_empire(game, *, owner=PLAYER):
    from .specialists import salaries
    colonies = [p for _, p in colony_rows(game, owner=owner)]
    outputs = [game.planet_yields(planet) for planet in colonies]
    trade, research = game.diplomatic_yields(owner)
    food = [game.population_report(planet) for planet in colonies]
    return EmpireSummary(
        colonies=len(colonies),
        population=sum(p.workforce for p in colonies),
        slaves=sum(p.slaves for p in colonies),
        industry=sum(output[0] for output in outputs),
        income=game.empire_rates_for(owner)[0],
        gross_income=sum(output[1]+game.planet_maintenance(p) for output, p in zip(outputs, colonies))+trade,
        maintenance=sum(game.planet_maintenance(p) for p in colonies)+salaries(game, owner),
        research=sum(output[2] for output in outputs)+research,
        used_slots=sum(p.used_slots for p in colonies),
        capacity=sum(p.building_capacity for p in colonies),
        projects=sum(len(p.construction_queue) for p in colonies),
        idle=sum(p.production_idle for p in colonies),
        agreement_income=trade,
        agreement_research=research,
        food_produced=sum(r.produced for r in food),
        food_consumed=sum(r.consumed for r in food),
        food_shortages=sum(r.balance < 0 for r in food),
        resources=game.resource_rate(owner),
        energy_generated=sum(game.planet_energy(p).generated for p in colonies),
        energy_demand=sum(game.planet_energy(p).demand for p in colonies),
        energy_shortages=sum(game.planet_energy(p).balance < 0 for p in colonies),
    )
