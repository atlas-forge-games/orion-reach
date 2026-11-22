"""Physical mounting positions for new blueprints; legacy snapshots stay intact."""

from dataclasses import dataclass

from .designs import DRONE_BAYS, HULLS, MODULES, SUPPORT_HULLS


@dataclass(frozen=True)
class Mount:
    id: str
    category: str
    name: str


def mounts_for(kind):
    hull = HULLS[kind]
    return tuple(
        [Mount(f"weapon_{i+1}", "weapon", f"Weapon mount {i+1}") for i in range(hull.external_mounts)]
        + [Mount(f"core_{i+1}", "core", "Internal bay" if hull.internal_bays == 1 else f"Internal bay {i+1}")
           for i in range(hull.internal_bays)]
        + [Mount(f"hangar_{i+1}", "hangar", f"Hangar {i+1}") for i in range(hull.hangar_bays)]
        + [Mount("engine", "engine", "Engine"), Mount("armor", "armor", "Hull plating")]
    )


def category(identifier):
    if identifier in DRONE_BAYS:
        return "hangar"
    if identifier in ("armor", "reinforced_armor"):
        return "armor"
    if identifier == "engine":
        return "engine"
    module = MODULES[identifier]
    if module.category == "weapon" or identifier in ("point_defense", "flak"):
        return "weapon"
    return "core"


def hull_allows(kind, identifier):
    # A command frigate is a valid role; the stronger flag bridge stays Titan-only.
    hulls = SUPPORT_HULLS.get(identifier)
    return identifier == "command_relay" or hulls is None or kind in hulls


def arrange(kind, modules, preferred=()):
    """Preserve positions when possible. Return excess equipment without deleting it."""
    slots = mounts_for(kind)
    by_id = {slot.id: slot for slot in slots}
    remaining, fitted = list(modules), {}
    for slot_id, identifier in preferred:
        slot = by_id.get(slot_id)
        if (slot is not None and slot_id not in fitted and identifier in remaining
                and category(identifier) == slot.category and hull_allows(kind, identifier)):
            fitted[slot_id] = identifier
            remaining.remove(identifier)
    overflow = []
    for identifier in remaining:
        slot = next((s for s in slots if s.id not in fitted and s.category == category(identifier)
                     and hull_allows(kind, identifier)), None)
        if slot is None:
            overflow.append(identifier)
        else:
            fitted[slot.id] = identifier
    return ordered(kind, fitted), overflow


def ordered(kind, fitted):
    return tuple((slot.id, fitted[slot.id]) for slot in mounts_for(kind) if slot.id in fitted)


def capacity_error(kind, modules):
    hull = HULLS[kind]
    limits = {"weapon": hull.external_mounts, "core": hull.internal_bays,
              "hangar": hull.hangar_bays, "engine": 1, "armor": 1}
    labels = {"weapon": "external weapon mounts", "core": "shared internal bays",
              "hangar": "drone hangars", "engine": "engine slot", "armor": "hull plating selection"}
    for group, limit in limits.items():
        if sum(category(m) == group for m in modules) > limit:
            return f"This hull has {limit} {labels[group]}."
    return None


def placement_error(kind, modules, mounts):
    """Validate saved positions as well as the aggregate equipment list."""
    if not isinstance(mounts, (tuple, list)) or len(mounts) > len(mounts_for(kind)):
        return "Invalid mounting positions."
    slots = {s.id: s for s in mounts_for(kind)}
    fitted = {}
    for pair in mounts:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            return "Invalid mounting position."
        slot_id, identifier = pair
        if (not isinstance(slot_id, str) or slot_id not in slots or slot_id in fitted
                or not isinstance(identifier, str) or identifier not in MODULES):
            return "Unknown or duplicate mounting position."
        if category(identifier) != slots[slot_id].category or not hull_allows(kind, identifier):
            return "That equipment cannot fit in this mounting position."
        fitted[slot_id] = identifier
    canonical = ordered(kind, fitted)
    if tuple(tuple(p) for p in mounts) != canonical or tuple(m for _, m in canonical) != tuple(modules):
        return "Equipment does not match its mounting positions."
    return None


def options(kind, slot_id):
    slot = next(s for s in mounts_for(kind) if s.id == slot_id)
    # The three principal internal roles lead the list, followed by research variants.
    core_order = ("shield", "damage_control", "command_relay", "regenerative_shield", "hardened_shield",
                  "scanner", "escort_array", "ecm_projector", "flag_bridge")
    identifiers = core_order if slot.category == "core" else MODULES
    return tuple(m for m in identifiers if m in MODULES and category(m) == slot.category and hull_allows(kind, m))


def design_mounts(design):
    """Read old designs without changing their equipment, stats or saved snapshots."""
    return arrange(design.kind, design.modules, design.mounts)


def build_design(identifier, name, kind, modules, mounts=None):
    from .designs import ShipDesign, loadout_error
    error = loadout_error(kind, modules, fit_version=3)
    if error:
        raise ValueError(error)
    if mounts is None:
        mounts, overflow = arrange(kind, modules)
        if overflow:
            raise ValueError("Equipment does not fit this hull.")
        modules = tuple(m for _, m in mounts)
    error = placement_error(kind, modules, mounts)
    if error:
        raise ValueError(error)
    return ShipDesign(identifier, name, kind, tuple(modules), 3, tuple(tuple(p) for p in mounts))
