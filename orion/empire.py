"""Read-only colony reports derived from the current campaign; no save schema."""

from dataclasses import dataclass
from .model import PLAYER

FILTERS = ("all", "building", "idle", "full")
SORT_KEYS = ("name", "population", "industry", "income", "research", "slots")
COLONIES_PER_PAGE = 5


@dataclass(frozen=True)
class EmpireSummary:
    colonies: int = 0
    population: int = 0
    industry: int = 0
    income: int = 0
    research: int = 0
    used_slots: int = 0
    capacity: int = 0
    projects: int = 0
    idle: int = 0
    agreement_income: int = 0
    agreement_research: int = 0


def colony_rows(game, filter_by="all", sort_by="name", descending=False, *, owner=PLAYER):
    """Return actual system/planet pairs; sorting must never change selection IDs."""
    if filter_by not in FILTERS or sort_by not in SORT_KEYS:
        raise ValueError("Unknown colony filter or sort order.")
    rows = [(system, planet) for system in game.systems
            for planet in system.worlds if planet.colonized and planet.owner == owner]
    if filter_by == "building":
        rows = [(s, p) for s, p in rows if p.construction_queue]
    elif filter_by == "idle":
        rows = [(s, p) for s, p in rows if not p.construction_queue]
    elif filter_by == "full":
        rows = [(s, p) for s, p in rows if p.free_slots == 0]
    # Deterministic alphabetical ties, even for descending numerical sorts.
    rows.sort(key=lambda row: (row[1].name.casefold(), row[0].name.casefold(), row[0].id, row[1].id))
    keys = {
        "name": lambda row: row[1].name.casefold(),
        "population": lambda row: row[1].population,
        "industry": lambda row: row[1].yields_per_turn[0],
        "income": lambda row: row[1].yields_per_turn[1],
        "research": lambda row: row[1].yields_per_turn[2],
        "slots": lambda row: row[1].used_slots,
    }
    return sorted(rows, key=keys[sort_by], reverse=descending)


def summarize_empire(game, *, owner=PLAYER):
    colonies = [p for _, p in colony_rows(game, owner=owner)]
    outputs = [planet.yields_per_turn for planet in colonies]
    trade, research = game.diplomatic_yields(owner)
    return EmpireSummary(
        colonies=len(colonies),
        population=sum(p.population for p in colonies),
        industry=sum(output[0] for output in outputs),
        income=sum(output[1] for output in outputs)+trade,
        research=sum(output[2] for output in outputs)+research,
        used_slots=sum(p.used_slots for p in colonies),
        capacity=sum(p.building_capacity for p in colonies),
        projects=sum(len(p.construction_queue) for p in colonies),
        idle=sum(not p.construction_queue for p in colonies),
        agreement_income=trade,
        agreement_research=research,
    )
