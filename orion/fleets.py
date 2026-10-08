"""Fleet membership derived from existing ship positions, without extra save state."""


def fleet_key(ship):
    # Flights with different departure times or speeds remain separate on the map.
    return (ship.owner, ship.system_id, ship.destination,
            ship.travel_total, ship.turns_remaining, ship.speed_bonus, ship.departure_pending, ship.cruise_speed)


def group_fleets(ships):
    """Ships of one empire sharing an orbit or the same voyage form a fleet."""
    groups = {}
    for ship in sorted(ships, key=lambda s: s.id):
        groups.setdefault(fleet_key(ship), []).append(ship)
    return list(groups.values())


def fleet_containing(ships, ship_id):
    anchor = next((ship for ship in ships if ship.id == ship_id), None)
    if anchor is None:
        return []
    key = fleet_key(anchor)
    return sorted((ship for ship in ships if fleet_key(ship) == key), key=lambda s: s.id)
