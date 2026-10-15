"""Wanderer mobile habitats. Their population travels with the actual ship."""

from dataclasses import replace
from types import SimpleNamespace

CAPACITY = 50
SPEED_FACTOR = .25
STATIONARY_BUILDINGS = frozenset({"missile_base", "planetary_shield", "interdictor", "jump_gate", "fortifications"})


def is_wanderer(game, owner="player"):
    return owner in game.owners and game._empire(owner).race_id == "wanderers"


def homes(game, owner=None):
    return [s for s in game.ships if s.habitat is not None and (owner is None or s.owner == owner)]


def ship_for(game, habitat):
    return next((s for s in game.ships if s.habitat is habitat), None)


def center(game, ship):
    from .navigation import position
    x, y = position(game, ship)
    return SimpleNamespace(id=ship.system_id, name=ship.name, kind=game.systems[ship.system_id].kind, x=x, y=y, worlds=[ship.habitat])


def create(game, system_id, owner, source=None):
    from .model import Planet, Ship
    from .population import farmers_needed, clamp_workforce
    identifier = game.next_ship_id
    if source is None:
        habitat = Planet(-identifier, f"Wayfarer {identifier:03}", "Terran", "Huge", "Average", "Normal", 1.0,
                         population=min(CAPACITY, game.starting_colonists(owner)), colonized=True, owner=owner, habitat=True)
    else:
        from .buildings import BUILDINGS
        habitat = replace(source, id=-identifier, name=f"{source.name[:30]} Ark", biome="Terran", size="Huge",
                          richness="Average", gravity="Normal", habitat=True,
                          buildings=source.buildings.copy(), construction_queue=source.construction_queue.copy(),
                          disabled_buildings=source.disabled_buildings.copy())
        habitat.population = min(CAPACITY, source.population+source.slaves)
        habitat.slaves = 0
        # Planet-specific defenses cannot be installed aboard a moving habitat.
        removed = [i for i, b in enumerate(habitat.buildings) if b in STATIONARY_BUILDINGS]
        game._empire(owner).resources += sum(BUILDINGS[habitat.buildings[i]].resource_cost for i in removed)
        habitat.disabled_buildings = [i-sum(j < i for j in removed) for i in habitat.disabled_buildings if i not in removed]
        habitat.buildings = [b for b in habitat.buildings if b not in STATIONARY_BUILDINGS]
        kept = []
        for project in habitat.construction_queue:
            if project.item_id in STATIONARY_BUILDINGS:
                game._empire(owner).resources += project.resource_refund
                game._empire(owner).credits += project.refund
            elif project.item_id == "colony_ship":
                # Preserve paid work and refund the old settlement order.
                game._empire(owner).resources += project.resource_refund
                game._empire(owner).credits += project.refund
            else:
                kept.append(project)
        habitat.construction_queue = kept
        habitat.shield_points = habitat.battery_hull = 0
        # Move people, construction and leaders; leave a real, empty planet behind.
        for person in game.specialists.people:
            if (person.system_id, person.planet_id) == (system_id, source.id):
                person.planet_id = habitat.id
        if (game.selected_system, game.selected_planet) == (system_id, source.id):
            game.selected_planet = habitat.id
        blank = Planet(source.id, source.name, source.biome, source.size, source.richness, source.gravity, source.orbit_au)
        source.__dict__.update(blank.__dict__)
    ship = Ship(identifier, "mothership", system_id, owner=owner, habitat=habitat)
    game.next_ship_id += 1
    game.ships.append(ship)
    clamp_workforce(habitat)
    if source is None:
        habitat.farmers = farmers_needed(habitat, game.bonuses_for(owner), surplus=1)
    return ship


def migrate(game):
    """Upgrade old Wanderer colonies without removing their residents or economy."""
    changed = False
    for owner in game.owners:
        if not is_wanderer(game, owner):
            continue
        for system in game.systems:
            for planet in system.worlds:
                if planet.owner == owner:
                    changed = True
                    overflow = max(0, planet.workforce-CAPACITY)
                    jobs = {role: getattr(planet, role) for role in ("farmers", "scientists", "miners")}
                    first = create(game, system.id, owner, planet)
                    for role in jobs:
                        jobs[role] -= getattr(first.habitat, role)
                    while overflow:
                        extra = create(game, system.id, owner)
                        extra.habitat.population = min(CAPACITY, overflow)
                        available = extra.habitat.population
                        for role, remaining in jobs.items():
                            assigned = min(available, remaining)
                            setattr(extra.habitat, role, assigned)
                            jobs[role] -= assigned
                            available -= assigned
                        overflow -= extra.habitat.population
        # Existing settlement ships become usable mobile homes, keeping their route.
        for old in list(game.ships):
            if old.owner != owner or old.kind != "colony_ship":
                continue
            changed = True
            new = create(game, old.system_id, owner)
            game.ships.remove(new)
            new.habitat.id = -old.id
            old.kind, old.habitat, old.hull = "mothership", new.habitat, new.max_hull
    return changed


def relocate_specialists(game):
    positions = {s.habitat.id: s.system_id for s in homes(game)}
    for person in game.specialists.people:
        if person.planet_id in positions:
            person.system_id = positions[person.planet_id]
    if game.selected_planet in positions:
        game.selected_system = positions[game.selected_planet]
    elif game.selected_planet is not None and game.selected_planet < 0:
        game.selected_planet = None


def ai_orders(game, owner):
    """Disperse new habitats to nearby surveyed, peaceful anchorages."""
    from . import monsters, black_holes
    from .production import distance_ly
    from .navigation import hostile
    fleet = homes(game, owner)
    occupied = {s.destination if s.has_course else s.system_id for s in fleet}
    for ship in fleet:
        if ship.has_course:
            continue
        crowded = sum(s.system_id == ship.system_id and not s.has_course for s in fleet) > 1
        threatened = any(hostile(game, owner, s.owner) for s in game.foreign_fleet(ship.system_id, owner))
        if not crowded and not threatened:
            continue
        candidates = [s for s in game.systems if s.id not in occupied and s.kind != black_holes.KIND
                      and game.system_explored(s.id, owner) and game.within_fuel_range(s.id, owner)
                      and monsters.known_status(game, s.id, owner) != "alive"
                      and not any(hostile(game, owner, p.owner) for p in game.known_system(s.id, owner).worlds if p.owner)
                      and not any(hostile(game, owner, f.owner) for f in game.visible_ships(owner)
                                  if not f.in_transit and f.system_id == s.id)]
        if candidates:
            target = min(candidates, key=lambda s: (distance_ly(game.systems[ship.system_id], s), s.id))
            game.send_ship(ship.id, target.id, owner=owner)
            occupied.add(target.id)
            game.rival_event(f"Relocating {ship.name} to {target.name}.", owner=owner)
