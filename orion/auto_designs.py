"""Deterministic, ordinary blueprints for AI fleets and the designer's auto-fit."""

from functools import lru_cache

from .designs import HULLS, ShipDesign, loadout_error
from .production import HULL_TECHNOLOGIES


@lru_cache(maxsize=512)
def auto_design(kind, completed, legacy_hulls=False, *, planning=False):
    if kind not in HULLS:
        return None
    if planning:
        # Preview this hull and its native equipment; other choices still use
        # known technologies. AI callers never opt into blueprint planning.
        completed = (*completed, HULL_TECHNOLOGIES[kind])
    modules = []

    def add(identifier):
        if loadout_error(kind, [*modules, identifier], completed, require_weapon=False,
                         legacy_hulls=legacy_hulls) is None:
            modules.append(identifier)
            return True
        return False

    def first(options):
        return next((m for m in options if add(m)), None)

    if kind == "carrier":
        first(("bomber_bay", "interceptor_bay", "drone_bay"))
        first(("interceptor_bay", "bomber_bay", "drone_bay"))
    first(("hardened_shield", "regenerative_shield", "shield", "reinforced_armor", "armor"))
    first(("damage_control", "scanner", "engine"))
    if kind in ("frigate", "carrier"):
        preferred = ("phased", "plasma", "pulse", "graviton", "ion", "quantum", "laser")
    elif kind == "destroyer":
        preferred = ("antimatter", "mirv", "fusion_torpedo", "torpedo", "pulse", "laser")
    else:
        preferred = ("heavy_beam", "particle", "disruptor", "phased", "graviton", "plasma",
                     "fusion_torpedo", "mirv", "antimatter", "quantum", "pulse", "torpedo", "laser")
    first(preferred)
    first(("flak", "reinforced_armor", "point_defense"))
    if kind not in ("frigate", "carrier", "destroyer"):
        first(("ion", "graviton"))
    while first(preferred) is not None:
        pass
    while first(("hardened_shield", "regenerative_shield", "shield", "flak", "reinforced_armor", "armor")) is not None:
        pass
    if loadout_error(kind, modules, completed, legacy_hulls=legacy_hulls):
        return None
    return ShipDesign("design_24", f"{HULLS[kind].name} Mk II", kind, tuple(modules))
