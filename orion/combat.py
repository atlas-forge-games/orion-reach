from .economy import remove_building
"""Deterministic, grid-based fleet combat; campaign losses commit on resolution."""

from collections import deque
from dataclasses import dataclass, field
import math
import hashlib

from .production import SHIP_TYPES, ShipSpec
from . import defenses
from .designs import HULLS, MODULE_SIZES, ShipDesign
from .weapons import Beam, BEAMS, DRONE_ROLES, CAPITAL_TARGETS
from .empires import EMPIRE_IDS
from .monsters import MONSTER, MONSTERS, alive_at, at as guardian_at, observe, known_status, commit_battle_result

BASE_SPEC = ShipSpec("missile_base", "Missile base", 100, 60, hull=40, damage=10)
DRONE_HULL = 6
DRONE_SPEC = ShipSpec("combat_drone", "Combat drone", 0, 0, hull=DRONE_HULL, damage=3)
DRONE_ID_BASE = -1_000_000
DRONES_PER_BAY = 2
LAUNCHES_PER_BAY = 4
COMBAT_TYPES = {**SHIP_TYPES, **MONSTERS, "missile_base": BASE_SPEC, "combat_drone": DRONE_SPEC}

OWNERS = EMPIRE_IDS
HOSTILE_BELOW = -30
RESULTS = ("active", "monster_victory", *(owner+suffix for owner in OWNERS for suffix in ("_victory", "_retreat")))
BOARD_COLUMNS = 18
MIN_ROWS = 10
MOVEMENT = {"frigate": 3, "scout": 5, "colony_ship": 2, "outpost_ship": 2, "troop_transport": 2}
MOVEMENT.update({kind: hull.movement for kind, hull in HULLS.items() if kind != "frigate"})
MOVEMENT.update({kind: spec.movement for kind, spec in MONSTERS.items()})
MOVEMENT["missile_base"] = 0
MOVEMENT["combat_drone"] = 5


def weapon_for(game, kind, owner):
    if kind in ("destroyer", "cruiser", "battleship", "titan", "combat_drone"):
        return {"destroyer": "torpedo", "cruiser": "cruiser_battery", "battleship": "battleship_battery",
                "titan": "titan_battery", "combat_drone": "drone_beam"}[kind]
    if kind == "missile_base":
        return "missile"
    if kind in MONSTERS:
        return MONSTERS[kind].weapon
    if not SHIP_TYPES[kind].damage:
        return "none"
    return "quantum" if game.bonuses_for(owner).get("beam_level", 0) else "laser"


def other(owner):
    return "rival" if owner == "player" else "player"


def require(condition, message):
    if not condition:
        from .model import RuleError
        raise RuleError(message)


@dataclass
class CombatShip:
    id: int
    kind: str
    owner: str
    hull: int
    initial_hull: int
    x: int = 0
    y: int = 0
    weapon: str = "none"
    design: ShipDesign | None = None
    shields: int = 0
    carrier_id: int | None = None
    launched_drones: int = 0
    cooldowns: dict[str, int] = field(default_factory=dict)
    graviton_slow: bool = False
    repair_remaining: int = 0
    drone_role: str | None = None

    @property
    def name(self):
        if self.kind == "combat_drone":
            return f"{DRONE_ROLES[self.drone_role or 'assault'][0]} {DRONE_ID_BASE-self.id+1}"
        if self.kind == "missile_base":
            return f"Missile base {(-self.id-10_000)%8+1}"
        return MONSTERS[self.kind].name if self.kind in MONSTERS else f"{self.design.name if self.design else SHIP_TYPES[self.kind].name} {self.id:03}"

    @property
    def max_hull(self):
        return self.design.hull if self.design else COMBAT_TYPES[self.kind].hull

    @property
    def damage(self):
        return self.design.damage if self.design else BEAMS[self.weapon].damage

    @property
    def drone_bays(self):
        return self.design.drone_bays if self.design else (SHIP_TYPES[self.kind].drone_bays if self.kind in SHIP_TYPES else 0)

    @property
    def drone_bay_counts(self):
        return self.design.drone_bay_counts if self.design else ({"assault": self.drone_bays} if self.drone_bays else {})

    @property
    def drone_reserve(self):
        return self.drone_bays*LAUNCHES_PER_BAY-self.launched_drones

    @property
    def weapon_range(self):
        return self.design.weapon_range if self.design else BEAMS[self.weapon].range

    @property
    def movement(self):
        movement = (DRONE_ROLES[self.drone_role or "assault"][2] if self.kind == "combat_drone"
                    else self.design.movement if self.design else MOVEMENT[self.kind])
        return max(1, movement-int(self.graviton_slow)) if movement else 0

    @property
    def ready_damage(self):
        return sum(strength for _, strength, _ in self.ready_weapons)

    @property
    def ready_range(self):
        return max((distance for _, _, distance in self.ready_weapons), default=0)

    @property
    def ready_weapons(self):
        if self.design:
            scanner = sum(m.range_bonus for m in self.design.specs)
            return tuple((m.weapon, m.damage, m.range+scanner) for m in self.design.specs
                         if m.damage and m.weapon not in self.cooldowns)
        return ((self.weapon, self.damage, self.weapon_range),) if self.damage and self.weapon not in self.cooldowns else ()

    def volley(self, target):
        distance = math.dist(self.position, target.position)
        return tuple((weapon, strength) for weapon, strength, reach in self.ready_weapons if distance <= reach)

    @property
    def position(self):
        return self.x, self.y


@dataclass
class CombatState:
    system_id: int
    initiator: str
    ships: list[CombatShip]
    round: int = 1
    active_owner: str | None = "player"
    acted: list[int] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    status: str = "active"
    retreat_destination: int | None = None
    moved: list[int] = field(default_factory=list)
    accuracy: bool = True
    shots_fired: int = 0

    @property
    def guardian(self):
        return next((s for s in self.ships if s.owner == MONSTER), None)

    @property
    def sides(self):
        return tuple(owner for owner in (*OWNERS, MONSTER) if any(s.owner == owner for s in self.ships))

    def enemy(self, owner):
        return next(side for side in self.sides if side != owner)

    @property
    def rows(self):
        # Four deployment columns per side; large fleets extend the map vertically.
        return max(MIN_ROWS, (max(sum(s.owner == o for s in self.ships) for o in self.sides)+3)//4)

    def can_move(self, ship):
        return ship.hull > 0 and ship.movement > 0 and ship.id not in self.moved

    def can_fire(self, ship):
        return ship.hull > 0 and ship.ready_damage > 0 and ship.id not in self.acted

    def drones(self, carrier, *, alive=True):
        return [s for s in self.ships if s.carrier_id == carrier.id and (s.hull > 0 or not alive)]

    def launch_cells(self, carrier):
        occupied = {s.position for s in self.ships if s.hull > 0}
        forward = 1 if carrier.owner == self.sides[0] else -1
        offsets = ((forward, 0), (forward, -1), (forward, 1), (0, -1), (0, 1),
                   (-forward, 0), (-forward, -1), (-forward, 1))
        return [(carrier.x+dx, carrier.y+dy) for dx, dy in offsets
                if 0 <= carrier.x+dx < BOARD_COLUMNS and 0 <= carrier.y+dy < self.rows
                and (carrier.x+dx, carrier.y+dy) not in occupied]

    def available_drone_roles(self, ship):
        return tuple(role for role, bays in ship.drone_bay_counts.items()
                     if sum(s.drone_role == role for s in self.drones(ship)) < bays*DRONES_PER_BAY
                     and sum(s.drone_role == role for s in self.drones(ship, alive=False)) < bays*LAUNCHES_PER_BAY)

    def can_launch(self, ship, role=None):
        return (ship.hull > 0 and ship.id not in self.acted and ship.drone_reserve > 0
                and len(self.drones(ship)) < ship.drone_bays*DRONES_PER_BAY
                and bool(self.available_drone_roles(ship))
                and (role is None or role in self.available_drone_roles(ship))
                and len(self.ships) < 10000 and bool(self.launch_cells(ship)))

    def fleet(self, owner, *, alive=True):
        return [s for s in self.ships if s.owner == owner and (s.hull > 0 or not alive)]

    def ready(self, owner):
        return [s for s in self.fleet(owner) if self.can_move(s) or self.can_fire(s) or self.can_launch(s)]

    def ship(self, identifier):
        return next((s for s in self.ships if type(identifier) is int and s.id == identifier), None)

    def record(self, message):
        self.log.append(message if len(message) <= 180 else message[:179]+"…")
        self.log = self.log[-8:]

    @classmethod
    def from_dict(cls, data, game, *, version=37):
        from .model import _integer, _name
        if version < 25 and isinstance(data, dict):
            data = {**data, "accuracy": False, "shots_fired": 0}
        # Migrate copies so reading a save never mutates its source payload.
        if version < 13 and isinstance(data, dict):
            data = {**data, "moved": list(data.get("acted", []))}
            if isinstance(data.get("ships"), list):
                data["ships"] = [{k: v for k, v in row.items() if k not in ("x", "y", "weapon")}
                                 if isinstance(row, dict) else row for row in data["ships"]]
        if not isinstance(data, dict) or set(data) != {
                "system_id", "initiator", "ships", "round", "active_owner", "acted",
                "log", "status", "retreat_destination", "moved", "accuracy", "shots_fired"}:
            raise ValueError("Invalid combat state")
        if type(data["accuracy"]) is not bool or not _integer(data["shots_fired"], 0, 100_000_000):
            raise ValueError("Invalid combat random sequence")
        if (not _integer(data["system_id"], 0, len(game.systems)-1) or
                data["initiator"] not in game.owners or
                not _integer(data["round"], 1, 1_000_000) or data["status"] not in RESULTS):
            raise ValueError("Invalid combat location or status")
        rows = data["ships"]
        if not isinstance(rows, list) or not 2 <= len(rows) <= 10000:
            raise ValueError("Invalid battle fleet")
        guarded = any(isinstance(row, dict) and row.get("owner") == MONSTER for row in rows)
        participants = {row.get("owner") for row in rows if isinstance(row, dict)}
        sides = tuple(owner for owner in (*game.owners, MONSTER) if owner in participants)
        if len(sides) != 2 or participants != set(sides) or data["initiator"] not in sides:
            raise ValueError("Invalid combat participants")
        guardian = guardian_at(game, data["system_id"]) if guarded else None
        if guarded:
            if guardian is None:
                raise ValueError("Missing guardian or empire")
        else:
            diplomacy = game.diplomacy_between(*sides)
            if diplomacy.relations != -100 or diplomacy.trade_active or diplomacy.research_active or diplomacy.non_aggression_active:
                raise ValueError("Combat does not match diplomatic state")
        ships = []
        for row in rows:
            fields = {"id", "kind", "owner", "hull", "initial_hull"}
            if version >= 13:
                fields |= {"x", "y", "weapon"}
            if version >= 18:
                fields |= {"design", "shields"}
            if version >= 29:
                fields |= {"carrier_id", "launched_drones"}
            if version >= 31:
                fields |= {"cooldowns", "graviton_slow", "repair_remaining", "drone_role"}
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError("Invalid combat ship")
            monster = row["owner"] == MONSTER
            station = row["kind"] == "missile_base"
            drone = row["kind"] == "combat_drone"
            role = row.get("drone_role") if version >= 31 else "assault" if drone else None
            if ((drone and (not isinstance(role, str) or role not in DRONE_ROLES))
                    or (not drone and role is not None)):
                raise ValueError("Invalid drone role")
            planet = defenses.base_planet(game, row["id"]) if station else None
            design = ShipDesign.from_dict(row["design"], version=version) if version >= 18 and row["design"] is not None else None
            if design and (monster or station or drone or design.kind != row["kind"]):
                raise ValueError("Invalid battle blueprint")
            if ((not planet or (-row["id"]-10_000)//8 != data["system_id"]) if station else
                    (not guardian or row["id"] != guardian.combat_id or type(row["id"]) is not int) if monster
                    else not _integer(row["id"], -1_000_000_000, DRONE_ID_BASE) if drone
                    else not _integer(row["id"], 1, game.next_ship_id-1)):
                raise ValueError("Invalid combat identifier")
            if (row["owner"] not in sides or
                    not isinstance(row["kind"], str) or row["kind"] not in (("missile_base",) if station else MONSTERS if monster else ("combat_drone",) if drone else HULLS if design else SHIP_TYPES) or
                    not _integer(row["initial_hull"], 1, design.hull if design else COMBAT_TYPES[row["kind"]].hull) or
                    not _integer(row["hull"], 0, row["initial_hull"])):
                raise ValueError("Invalid combat ship health")
            if version < 13:
                row = {**row, "weapon": weapon_for(game, row["kind"], row["owner"])}
            elif (not isinstance(row["weapon"], str) or row["weapon"] not in BEAMS
                  or row["weapon"] != (design.weapon if design else DRONE_ROLES[role][1] if drone
                                       else weapon_for(game, row["kind"], row["owner"]))):
                raise ValueError("Invalid combat weapon")
            shields = row["shields"] if version >= 18 else 0
            if not _integer(shields, 0, design.shields if design else 0) or (row["hull"] == 0 and shields):
                raise ValueError("Invalid shields")
            row = {**row, "design": design, "shields": shields}
            if version < 31:
                row.update(cooldowns={}, graviton_slow=False, repair_remaining=0, drone_role=role)
            cooldowns = row["cooldowns"]
            weapons = {m.weapon for m in design.specs if m.damage} if design else {row["weapon"]}
            if (not isinstance(cooldowns, dict) or any(
                    key not in weapons or not BEAMS[key].reload or not _integer(value, 1, BEAMS[key].reload+1)
                    for key, value in cooldowns.items())):
                raise ValueError("Invalid weapon recharge")
            if (type(row["graviton_slow"]) is not bool or (station and row["graviton_slow"])
                    or not _integer(row["repair_remaining"], 0, design.repair_capacity if design else 0)):
                raise ValueError("Invalid combat support state")
            if version < 29:
                row.update(carrier_id=None, launched_drones=0)
            if (not _integer(row["launched_drones"], 0, 10000)
                    or (not drone and row["carrier_id"] is not None)
                    or (drone and (not _integer(row["carrier_id"], 1, game.next_ship_id-1)
                                   or row["initial_hull"] != DRONE_SPEC.hull or row["launched_drones"]))):
                raise ValueError("Invalid drone deployment")
            ships.append(CombatShip(**row))
        identifiers = {s.id for s in ships}
        if len(identifiers) != len(ships) or {s.owner for s in ships} != set(sides):
            raise ValueError("Invalid combat participants")
        if not guarded and not any(s.owner == data["initiator"] and (s.damage or s.drone_bays) for s in ships):
            raise ValueError("An unarmed fleet cannot initiate combat")
        for key in ("acted", "moved"):
            used = data[key]
            if (not isinstance(used, list) or any(type(i) is not int or i not in identifiers for i in used)
                    or len(set(used)) != len(used)):
                raise ValueError("Invalid tactical actions")
        if (not isinstance(data["log"], list) or len(data["log"]) > 8
                or any(not _name(message, 180) for message in data["log"])):
            raise ValueError("Invalid combat log")
        state = cls(**{**data, "ships": ships})
        drone_ids = {s.id for s in ships if s.kind == "combat_drone"}
        if drone_ids != set(range(DRONE_ID_BASE, DRONE_ID_BASE-len(drone_ids), -1)):
            raise ValueError("Invalid drone identifiers")
        for ship in ships:
            if ship.kind == "combat_drone":
                carrier = state.ship(ship.carrier_id)
                if (carrier is None or not carrier.drone_bays or carrier.owner != ship.owner
                        or ship.drone_role not in carrier.drone_bay_counts
                        or (ship.hull > 0 and carrier.hull == 0)):
                    raise ValueError("Drone without an operational carrier")
            if (ship.launched_drones != len(state.drones(ship, alive=False))
                    or ship.launched_drones > ship.drone_bays*LAUNCHES_PER_BAY
                    or len(state.drones(ship)) > ship.drone_bays*DRONES_PER_BAY):
                raise ValueError("Invalid carrier reserve or active drones")
            for role, bays in ship.drone_bay_counts.items():
                if (sum(s.drone_role == role for s in state.drones(ship, alive=False)) > bays*LAUNCHES_PER_BAY
                        or sum(s.drone_role == role for s in state.drones(ship)) > bays*DRONES_PER_BAY):
                    raise ValueError("Invalid drone role capacity")
        if version < 13:
            deploy(state)
        battle_rows = state.rows
        if any(not _integer(s.x, 0, BOARD_COLUMNS-1) or not _integer(s.y, 0, battle_rows-1) for s in ships):
            raise ValueError("Ship outside the battlefield")
        living = [s.position for s in ships if s.hull > 0]
        if len(set(living)) != len(living):
            raise ValueError("Ships occupy the same position")
        retreating = state.status.rsplit("_", 1)[0] if state.status.endswith("_retreat") else None
        if retreating:
            if (not _integer(state.retreat_destination, 0, len(game.systems)-1)
                    or state.retreat_destination == state.system_id
                    or retreating not in sides or retreating == MONSTER
                    or any(not state.fleet(owner) for owner in sides)):
                raise ValueError("Invalid retreat")
        elif state.retreat_destination is not None:
            raise ValueError("Unexpected retreat destination")
        if state.status == "active":
            if (state.active_owner not in sides
                    or any(not state.fleet(owner) for owner in sides)):
                raise ValueError("Invalid side to act")
        elif state.active_owner is not None:
            raise ValueError("Resolved battle still has an active side")
        if state.status.endswith("_victory"):
            winner = state.status.rsplit("_", 1)[0]
            if winner not in sides or not state.fleet(winner) or state.fleet(state.enemy(winner)):
                raise ValueError("Invalid victory")
        campaign = {s.id: s for s in game.ships}
        for ship in ships:
            if ship.kind == "combat_drone":
                continue
            if ship.kind == "missile_base":
                planet = defenses.base_planet(game, ship.id)
                expected = ship.initial_hull if state.status == "active" else ship.hull
                if expected:
                    if (planet.owner != ship.owner or "missile_base" not in planet.buildings
                            or (planet.battery_hull or defenses.BASE_HULL) != expected):
                        raise ValueError("Missile base does not match the colony")
                elif "missile_base" in planet.buildings:
                    raise ValueError("Destroyed missile base survived")
                continue
            if ship.owner == MONSTER:
                expected_hull = ship.initial_hull if state.status == "active" else ship.hull
                if ship.kind != guardian.kind or guardian.hull != expected_hull:
                    raise ValueError("Guardian does not match the battle")
                continue
            original = campaign.get(ship.id)
            if state.status != "active" and ship.hull == 0:
                if original is not None:
                    raise ValueError("Destroyed ship survived in the campaign")
                continue
            if (original is None or original.owner != ship.owner or original.kind != ship.kind
                    or original.design != ship.design
                    or original.system_id != state.system_id
                    or original.hull != (ship.initial_hull if state.status == "active" else ship.hull)):
                raise ValueError("Battle does not match the campaign fleet")
            if ship.owner == retreating:
                # Ship validation already checked its saved speed and complete voyage length.
                expected = original.travel_total
                if (original.departure_pending or original.destination != state.retreat_destination or original.turns_remaining != expected
                        or original.travel_total != expected
                        or original.speed_bonus not in (game.bonuses_for(ship.owner).get("ship_speed", 0),
                                                        game.ship_speed_bonus(ship.owner))):
                    raise ValueError("Invalid retreat voyage")
            elif original.in_transit or original.departure_pending:
                raise ValueError("Travelling ship in battle")
        orbiting = {s.id for s in game.ships if s.owner in sides and not s.in_transit and s.system_id == state.system_id}
        expected_orbit = {s.id for s in ships if (state.status == "active" or s.hull > 0)
                          and s.owner != retreating and s.owner != MONSTER and s.kind not in ("missile_base", "combat_drone")}
        if orbiting != expected_orbit:
            raise ValueError("Battle omitted orbiting ships")
        expected_bases = {defenses.base_id(state.system_id, p.id) for p in defenses.bases(game, state.system_id)
                          if p.owner in sides} if not guarded else set()
        battle_bases = {s.id for s in ships if s.kind == "missile_base" and (state.status == "active" or s.hull > 0)}
        if expected_bases != battle_bases:
            raise ValueError("Battle omitted planetary defenses")
        return state


def deploy(state):
    rows = state.rows
    lanes = sorted(range(rows), key=lambda y: (abs(y-(rows-1)/2), y))
    for owner in state.sides:
        for index, ship in enumerate(sorted(state.fleet(owner, alive=False), key=lambda s: s.id)):
            depth, lane = divmod(index, rows)
            ship.x = 4-depth if owner == state.sides[0] else 13+depth
            if ship.kind == "missile_base":
                ship.x = 5 if owner == state.sides[0] else 12
            ship.y = lanes[lane]


def in_range(ship, target):
    return bool(ship.volley(target))


def reachable(state, ship):
    """Shortest eight-direction paths; ships block cells and diagonal corners."""
    if not state.can_move(ship):
        return {}
    occupied = {s.position for s in state.ships if s.hull > 0 and s.id != ship.id}
    rows = state.rows
    paths = {ship.position: (ship.position,)}
    queue = deque([ship.position])
    while queue:
        x, y = queue.popleft()
        path = paths[(x, y)]
        if len(path) > ship.movement:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            cell = x+dx, y+dy
            if (not 0 <= cell[0] < BOARD_COLUMNS or not 0 <= cell[1] < rows
                    or cell in occupied or cell in paths):
                continue
            if dx and dy and ((x+dx, y) in occupied or (x, y+dy) in occupied):
                continue
            paths[cell] = path+(cell,)
            queue.append(cell)
    paths.pop(ship.position)
    return paths


def engagement_target(game, system_id, owner="player", target=None):
    candidates = game.opponents_at(system_id, owner)
    return target if target is not None else (candidates[0] if candidates else None)


def engagement_error(game, system_id, owner="player", target=None):
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    if type(system_id) is not int or not 0 <= system_id < len(game.systems):
        return "Unknown solar system."
    if alive_at(game, system_id) and owner in OWNERS and game.fleet_at(system_id, owner):
        return None
    if owner not in game.owners or not game.opponents:
        return "No opposing empire is available."
    target = engagement_target(game, system_id, owner, target)
    if target == owner or target not in game.owners:
        return "Both empires need ships in orbit in this system."
    from .diplomacy import aggression_error
    if aggression_error(game, owner, target):
        return aggression_error(game, owner, target)
    own, enemy = game.fleet_at(system_id, owner), game.fleet_at(system_id, target)
    own_bases, enemy_bases = defenses.bases(game, system_id, owner), defenses.bases(game, system_id, target)
    if not (own or own_bases) or not (enemy or enemy_bases):
        return "Both empires need ships in orbit in this system."
    if not own_bases and not any(s.damage or s.drone_bays for s in own):
        return "Bring an armed ship or carrier to engage. Scouts and transports are unarmed."
    return None


def battle_ship(game, ship):
    return CombatShip(ship.id, ship.kind, ship.owner, ship.hull, ship.hull,
                      weapon=ship.design.weapon if ship.design else weapon_for(game, ship.kind, ship.owner),
                      design=ship.design, shields=ship.design.shields if ship.design else 0,
                      repair_remaining=ship.design.repair_capacity if ship.design else 0)


def battle_bases(game, system_id, owner):
    return [CombatShip(defenses.base_id(system_id, p.id), "missile_base", owner,
                       p.battery_hull or defenses.BASE_HULL, p.battery_hull or defenses.BASE_HULL, weapon="missile")
            for p in defenses.bases(game, system_id, owner)]


def begin_combat(game, system_id, owner="player", target=None):
    error = engagement_error(game, system_id, owner, target)
    require(error is None, error)
    if alive_at(game, system_id):
        return begin_guardian_combat(game, system_id, owner)
    target = engagement_target(game, system_id, owner, target)
    fleet = sorted(game.fleet_at(system_id, owner)+game.fleet_at(system_id, target), key=lambda s: s.id)
    # An engagement happens before departure. Orders cannot survive the battle unnoticed.
    for ship in fleet:
        if ship.departure_pending:
            game._clear_course(ship)
    units = [battle_ship(game, s) for s in fleet]+battle_bases(game, system_id, owner)+battle_bases(game, system_id, target)
    state = CombatState(system_id, owner, units, active_owner=owner)
    deploy(state)
    state.record(f"{game.empire_name_for(owner)} initiated combat at {game.systems[system_id].name}.")
    game.combat = state
    from .first_contact import establish
    establish(game, owner, target)
    diplomacy = game.diplomacy_between(owner, target)
    from .diplomacy import start_war
    start_war(game, owner, target)
    diplomacy.record(game.turn, f"Combat at {game.systems[system_id].name}. Agreements ended; relations are now -100.")
    for participant in (owner, target):
        if participant != "player":
            game.rival_event(f"Battle began at {game.systems[system_id].name}.", turn=game.turn, owner=participant)
    return state


def begin_guardian_combat(game, system_id, owner="player"):
    from . import black_holes
    require(game.strategy_error(owner) is None, game.strategy_error(owner))
    require(not black_holes.at(game, system_id) or black_holes.can_explore(game, owner),
            "Event Horizon Navigation is required to approach this guardian.")
    guardian = alive_at(game, system_id)
    fleet = game.fleet_at(system_id, owner) if owner in game.owners else []
    require(guardian is not None and bool(fleet), "A guardian and an arriving fleet are required.")
    for ship in fleet:
        if ship.departure_pending:
            game._clear_course(ship)
    ships = [battle_ship(game, s) for s in fleet]
    ships.append(CombatShip(guardian.combat_id, guardian.kind, MONSTER, guardian.hull, guardian.hull, weapon=guardian.spec.weapon))
    state = CombatState(system_id, owner, ships, active_owner=owner)
    deploy(state)
    state.record(f"{guardian.spec.name} blocks entry to {game.systems[system_id].name}.")
    state.record(f"Prize: {guardian.spec.reward}. Your fleet has the first turn to fight or retreat.")
    game.combat = state
    observe(game, system_id, owner)
    return state


def action_error(game, owner, ship_id=None, target_id=None):
    state = game.combat
    if state is None or state.status != "active":
        return "There is no active battle."
    if owner not in state.sides or state.active_owner != owner:
        return "Wait for your fleet's turn."
    if ship_id is not None:
        ship = state.ship(ship_id)
        if ship is None or ship.owner != owner or ship.hull <= 0:
            return "Choose one of your surviving ships."
        if target_id is not None:
            target = state.ship(target_id)
            if ship.damage == 0:
                return "This ship is unarmed. Move, hold or retreat."
            if ship.id in state.acted:
                return "This ship has already fired this turn."
            if not ship.ready_damage:
                return "Weapons are recharging. Move, hold or end the turn."
            if target is None or target.owner == owner or target.hull <= 0:
                return "Choose a surviving enemy ship."
            if not in_range(ship, target):
                return f"Target out of range. Ready weapon range: {ship.ready_range} cells."
    return None


def resolve(game, status, destination=None):
    state = game.combat
    require(state is not None and state.status == "active", "This battle is already resolved.")
    state.status, state.active_owner, state.retreat_destination = status, None, destination
    rows = {s.id: s for s in state.ships}
    retreating = status.rsplit("_", 1)[0] if status.endswith("_retreat") else None
    game.ships[:] = [s for s in game.ships if s.id not in rows or rows[s.id].hull > 0]
    for ship in game.ships:
        if ship.id not in rows:
            continue
        ship.hull = rows[ship.id].hull
        if ship.owner == retreating:
            game._dispatch_ship(ship, destination)
    for unit in state.ships:
        if unit.kind == "missile_base":
            planet = defenses.base_planet(game, unit.id)
            planet.battery_hull = 0 if unit.owner == retreating else unit.hull
            if not planet.battery_hull:
                unit.hull = 0
                if "missile_base" in planet.buildings:
                    remove_building(planet, planet.buildings.index("missile_base"))
    if retreating:
        message = f"{game.empire_name_for(retreating)} retreated toward {game.systems[destination].name}."
    else:
        message = f"{game.empire_name_for(status.rsplit('_', 1)[0])} won the battle."
    state.record(message)
    for participant in state.sides:
        if participant in game.opponents:
            game.rival_event(message, turn=game.turn, owner=participant)
    if state.guardian:
        guardian = guardian_at(game, state.system_id)
        reward = commit_battle_result(game, guardian, state.guardian.hull, state.sides[0])
        observe(game, state.system_id, state.sides[0])
        from .exploration import refresh
        refresh(game)
        if not guardian.alive:
            from .black_holes import at as black_hole_at
            outcome = "The relic site is secured." if black_hole_at(game, guardian.system_id) else "Protected worlds are open for colonization."
            state.record(f"{guardian.spec.name} destroyed. {outcome}")
        if reward:
            state.record(reward)
            if state.sides[0] in game.opponents:
                game.rival_event(reward, turn=game.turn, owner=state.sides[0])
    if not state.guardian:
        from .exploration import refresh
        refresh(game)


def check_losses(game):
    state = game.combat
    for ship in state.ships:
        if ship.kind == "combat_drone" and ship.hull > 0 and state.ship(ship.carrier_id).hull == 0:
            ship.hull = 0
            state.record(f"{ship.name} lost its carrier control link and shut down.")
        if ship.hull == 0:
            ship.shields = 0
            ship.graviton_slow = False
    for side in state.sides:
        if not state.fleet(side):
            resolve(game, state.enemy(side)+"_victory")
            return


def launch_drones(game, ship_id, owner="player", role=None):
    error = action_error(game, owner, ship_id)
    require(error is None, error)
    state, carrier = game.combat, game.combat.ship(ship_id)
    require(carrier is not None and carrier.drone_bays > 0, "Choose a carrier fitted with drone bays.")
    require(carrier.id not in state.acted, "This carrier has already fired or launched this turn.")
    require(carrier.drone_reserve > 0, "This carrier has exhausted its drone reserve for this battle.")
    require(len(state.drones(carrier)) < carrier.drone_bays*DRONES_PER_BAY,
            "This carrier already controls its maximum number of drones.")
    roles = state.available_drone_roles(carrier)
    role = role or next(iter(roles), None)
    require(role in roles, "No launch capacity or reserve remains for this drone type.")
    bays = carrier.drone_bay_counts[role]
    slots = bays*DRONES_PER_BAY-sum(s.drone_role == role for s in state.drones(carrier))
    require(slots > 0, "This carrier already controls its maximum number of drones.")
    cells = state.launch_cells(carrier)
    require(bool(cells) and len(state.ships) < 10000, "No space is available to launch drones.")
    reserve = bays*LAUNCHES_PER_BAY-sum(s.drone_role == role for s in state.drones(carrier, alive=False))
    count = min(slots, reserve, len(cells), 10000-len(state.ships))
    identifier = min([DRONE_ID_BASE+1]+[s.id for s in state.ships if s.kind == "combat_drone"])-1
    drones = [CombatShip(identifier-i, "combat_drone", owner, DRONE_SPEC.hull, DRONE_SPEC.hull,
                         *cell, weapon=DRONE_ROLES[role][1], carrier_id=carrier.id, drone_role=role)
              for i, cell in enumerate(cells[:count])]
    state.ships.extend(drones)
    carrier.launched_drones += count
    state.acted.append(carrier.id)
    state.record(f"{carrier.name} launched {count} {DRONE_ROLES[role][0].lower()}s. {carrier.drone_reserve} in reserve.")
    return [s.id for s in drones]


def end_turn(game, owner="player"):
    error = action_error(game, owner)
    require(error is None, error)
    state = game.combat
    for ship in state.fleet(owner):
        ship.graviton_slow = False
    state.active_owner = state.enemy(owner)
    if state.active_owner == state.initiator:
        state.round += 1
        state.acted.clear()
        state.moved.clear()
        state.record(f"Round {state.round}. Movement and weapon actions refreshed.")
    for ship in state.fleet(state.active_owner):
        ship.cooldowns = {weapon: turns-1 for weapon, turns in ship.cooldowns.items() if turns > 1}
        if ship.design:
            regained = min(ship.design.shield_regeneration, ship.design.shields-ship.shields)
            repair = min(ship.design.repair_rate, ship.repair_remaining, ship.initial_hull-ship.hull)
            ship.shields += regained
            ship.hull += repair
            ship.repair_remaining -= repair
            if regained or repair:
                state.record(f"{ship.name} restored {regained} shields and repaired {repair} hull.")


def move(game, ship_id, x, y, owner="player"):
    error = action_error(game, owner, ship_id)
    require(error is None, error)
    state = game.combat
    ship = state.ship(ship_id)
    require(ship is not None, "Choose a ship first.")
    require(type(x) is int and type(y) is int and 0 <= x < BOARD_COLUMNS and 0 <= y < state.rows,
            "Choose a cell on the battlefield.")
    require(state.can_move(ship), "This ship has already moved this turn.")
    path = reachable(state, ship).get((x, y))
    require(path is not None, "Choose a highlighted empty cell within movement range.")
    ship.x, ship.y = x, y
    state.moved.append(ship.id)
    state.record(f"{ship.name} moved {len(path)-1} cells.")
    return path


def accuracy_breakdown(game, attacker, target, weapon):
    if game.combat is not None and not game.combat.accuracy:
        return {"base": 100, "targeting": 0, "range": 0, "evasion": 0, "tracking": 0, "chance": 100}
    bonuses = game.bonuses_for(attacker.owner) if attacker.owner in game.owners else {}
    defense = game.bonuses_for(target.owner) if target.owner in game.owners else {}
    spec = BEAMS[weapon]
    base = spec.accuracy
    distance = math.dist(attacker.position, target.position)
    penalty = max(0, math.ceil(distance-2))*3
    if bonuses.get("beam_precision") and not spec.projectile and weapon != "siege":
        penalty //= 2
    evasion = {"scout": 15, "frigate": 10, "destroyer": 8, "cruiser": 5, "carrier": 3, "combat_drone": 25}.get(target.kind, 0)
    if target.kind != "missile_base":
        evasion += defense.get("evasion", 0)
        if target.design:
            evasion = max(0, evasion+3*(target.movement-HULLS[target.kind].movement))
    if spec.projectile and bonuses.get("torpedo_guidance"):
        evasion //= 2
    targeting = bonuses.get("accuracy", 0)
    tracking = 0
    if attacker.kind in HULLS and (attacker.design is None or attacker.design.fit_version == 2):
        hull = HULLS[attacker.kind]
        target_size = (MODULE_SIZES[HULLS[target.kind].module_size] if target.kind in HULLS
                       else 3 if target.kind == "missile_base" or target.kind in MONSTERS
                       else 0 if target.kind in ("scout", "combat_drone") else 1)
        tracking = max(0, MODULE_SIZES[hull.module_size]-target_size)*hull.tracking_penalty
    return {"base": base, "targeting": targeting, "range": penalty, "evasion": evasion,
            "tracking": tracking,
            "chance": max(5 if tracking else 10, min(95, base+targeting-penalty-evasion-tracking))}


def shot_strengths(weapon, strength):
    """Split a battery's total damage into independently rolled projectiles."""
    count = BEAMS[weapon].shots
    return tuple(strength//count+(index < strength % count) for index in range(count))


def interception(state, target):
    local = target.design.interception if target.design else 0
    escorts = (sum(s.drone_role == "interceptor" and s.id != target.id
                   and math.dist(s.position, target.position) <= 2
                   for s in state.fleet(target.owner)) if state else 0)
    return min(90, local+min(40, 20*escorts))


def hit_damage(state, target, weapon, strength, *, shields=None, hull=None):
    """Pure damage forecast shared by AI and real fire; no state changes here."""
    spec = BEAMS[weapon]
    shields = target.shields if shields is None else shields
    hull = target.hull if hull is None else hull
    if weapon == "siege" and target.kind == "missile_base":
        strength *= 3
    if target.kind == "combat_drone":
        strength *= spec.versus_drones
    if target.kind in CAPITAL_TARGETS or target.kind in MONSTERS:
        strength *= spec.versus_capitals
    if spec.projectile or spec.drone:
        reduction = interception(state, target)*(100-spec.interception_piercing)/100
        strength = max(1, (round if spec.drone else math.ceil)(strength*(100-reduction)/100))
    hardening = target.design.shield_hardening if shields and target.design else 0
    bypass = strength*spec.shield_bypass*(100-hardening)//10_000
    blocked = min((strength-bypass)*spec.shield_multiplier, shields)
    # Ion amplification is spent on shields only; fractional shield absorption
    # consumes the corresponding point of ordinary hull damage.
    hit = min(hull, strength-math.ceil(blocked/spec.shield_multiplier))
    return hit, blocked


def expected_volley(game, attacker, target):
    shields, hull, score = target.shields, target.hull, 0.0
    for weapon, strength in attacker.volley(target):
        chance = accuracy_breakdown(game, attacker, target, weapon)["chance"]/100
        for shot in shot_strengths(weapon, strength):
            hit, blocked = hit_damage(game.combat, target, weapon, shot, shields=shields, hull=hull)
            score += (hit+.65*blocked)*chance
            shields -= blocked*chance
            hull -= hit*chance
    return score


def fire(game, ship_id, target_id, owner="player"):
    error = action_error(game, owner, ship_id, target_id)
    require(error is None, error)
    state = game.combat
    attacker, target = state.ship(ship_id), state.ship(target_id)
    require(attacker is not None and target is not None, "Choose an attacker and target.")
    damage, absorbed, hits, shots = 0, 0, 0, 0
    volley = attacker.volley(target)
    slowed = False
    for weapon, total in volley:
        spec = BEAMS[weapon]
        if spec.reload:
            attacker.cooldowns[weapon] = spec.reload+1
        chance = accuracy_breakdown(game, attacker, target, weapon)["chance"]
        for strength in shot_strengths(weapon, total):
            token = f"orion-shot-v1:{game.seed}:{game.turn}:{state.system_id}:{state.round}:{ship_id}:{target_id}:{state.shots_fired}"
            roll = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")%100
            state.shots_fired += 1
            shots += 1
            if roll >= chance:
                continue
            hits += 1
            hit, blocked = hit_damage(state, target, weapon, strength)
            target.shields -= blocked
            absorbed += blocked
            target.hull -= hit
            damage += hit
            if target.hull == 0:
                target.shields = 0
            if spec.slows and target.hull and target.movement:
                target.graviton_slow = True
                slowed = True
    state.acted.append(attacker.id)
    suffix = " Destroyed." if target.hull == 0 else f" {target.hull}/{target.max_hull} hull remains."
    protection = f" Shields absorbed {absorbed}." if absorbed else ""
    effect = " Target slowed." if slowed else ""
    state.record(f"{attacker.name} → {target.name}: {hits}/{shots} hits, {damage} hull damage.{protection}{effect}{suffix}")
    check_losses(game)
    return damage


def hold(game, ship_id, owner="player"):
    error = action_error(game, owner, ship_id)
    require(error is None, error)
    ship = game.combat.ship(ship_id)
    require(ship is not None, "Choose a ship first.")
    require(game.combat.can_move(ship) or game.combat.can_fire(ship) or game.combat.can_launch(ship), "This ship has finished its turn.")
    if ship.id not in game.combat.acted:
        game.combat.acted.append(ship.id)
    if ship.id not in game.combat.moved:
        game.combat.moved.append(ship.id)
    game.combat.record(f"{ship.name} held position.")


def retreat_destination(game, owner="player"):
    from . import black_holes
    if game.combat is None or owner not in OWNERS:
        return None
    if not any(s.kind not in ("missile_base", "combat_drone") for s in game.combat.fleet(owner)):
        return None
    origin = game.systems[game.combat.system_id]
    safe = [s for s in game.systems if s.id != origin.id and s.kind != black_holes.KIND and
            game.within_fuel_range(s.id, owner) and
            known_status(game, s.id, owner) != "alive" and
            not (game.system_visible(s.id, owner) and game.foreign_fleet(s.id, owner))]
    friendly = [s for s in safe if any(p.owner == owner for p in s.worlds)]
    return min(friendly or safe, key=lambda s: (game.travel_turns(origin, s, owner),
               (1.4*(s.x-origin.x))**2+(s.y-origin.y)**2, s.id), default=None)


def retreat(game, owner="player"):
    error = action_error(game, owner)
    require(error is None, error)
    destination = retreat_destination(game, owner)
    require(destination is not None, "No safe retreat destination is available.")
    resolve(game, owner+"_retreat", destination.id)
    return destination.id


def ai_action(game, owner="rival"):
    """Take one visible action so the UI can animate it before the next order."""
    error = action_error(game, owner)
    require(error is None, error)
    state = game.combat
    fleet = state.fleet(owner)
    if not any(s.damage or s.drone_reserve for s in fleet) and retreat_destination(game, owner) is not None:
        retreat(game, owner)
        return {"kind": "retreat"}
    ready = state.ready(owner)
    if not ready:
        end_turn(game, owner)
        return {"kind": "end_turn"}
    carrier = next((s for s in ready if state.can_launch(s)), None)
    if carrier:
        enemy_drones = any(s.kind == "combat_drone" for s in state.fleet(state.enemy(owner)))
        preference = ("interceptor", "bomber", "assault") if enemy_drones else ("bomber", "assault", "interceptor")
        role = next(r for r in preference if r in state.available_drone_roles(carrier))
        return {"kind": "launch", "ship_id": carrier.id, "drone_ids": launch_drones(game, carrier.id, owner, role)}
    ship = min(ready, key=lambda s: (-s.damage, s.hull, s.id))
    enemies = state.fleet(state.enemy(owner))
    targets = [s for s in enemies if in_range(ship, s)] if state.can_fire(ship) else []
    if targets:
        target = min(targets, key=lambda s: (s.hull > expected_volley(game, ship, s),
                                            -expected_volley(game, ship, s), -s.damage, s.hull, s.id))
        shield_before = target.shields
        weapons = tuple(dict.fromkeys(w for w, _ in ship.volley(target)))
        damage = fire(game, ship.id, target.id, owner)
        return {"kind": "fire", "ship_id": ship.id, "target_id": target.id, "damage": damage,
                "weapons": weapons,
                "missed": damage == 0 and target.shields == shield_before}
    paths = reachable(state, ship)
    if paths and (not ship.damage or state.can_fire(ship)):
        if ship.damage:
            target = min(enemies, key=lambda s: (math.dist(ship.position, s.position), -s.damage, s.hull, s.id))
            # Close only as far as necessary; prefer a firing lane over a short blocked route.
            def score(cell):
                distance = math.dist(cell, target.position)
                return (max(0, distance-ship.ready_range), len(paths[cell]), distance, cell)
            destination = min(paths, key=score)
            improve = math.dist(destination, target.position) < math.dist(ship.position, target.position)
        else:
            distance = lambda cell: min(math.dist(cell, s.position) for s in enemies)
            destination = min(paths, key=lambda cell: (-distance(cell), len(paths[cell]), cell))
            improve = distance(destination) > distance(ship.position)
        if improve:
            path = move(game, ship.id, *destination, owner)
            return {"kind": "move", "ship_id": ship.id, "path": path}
    hold(game, ship.id, owner)
    return {"kind": "hold", "ship_id": ship.id}


def hostile_encounter(game):
    encounter = next(hostile_pairs(game), None)
    return encounter[0] if encounter else None


def hostile_pairs(game):
    for system in game.systems:
        if alive_at(game, system.id):
            continue
        for attacker in game.opponents:
            for defender in game.opponents_at(system.id, attacker):
                if (game.diplomacy_between(attacker, defender).relations < HOSTILE_BELOW
                        and engagement_error(game, system.id, attacker, defender) is None):
                    yield system.id, attacker, defender


def autoresolve(game):
    """Use the same tactical rules for encounters with no human participant."""
    for _ in range(20000):
        if game.combat.status != "active":
            return
        ai_action(game, game.combat.active_owner)
    # Avoid blocking strategic turns forever in a pathological formation.
    for _ in range(2):
        owner = game.combat.active_owner
        if retreat_destination(game, owner) is not None:
            retreat(game, owner)
            return
        end_turn(game, owner)
    # A trapped, immobile stalemate is disengaged with its current damage.
    for ship in game.combat.ships:
        if ship.kind == "missile_base":
            planet = defenses.base_planet(game, ship.id)
            planet.battery_hull = ship.hull
            if not ship.hull and "missile_base" in planet.buildings:
                remove_building(planet, planet.buildings.index("missile_base"))
        elif ship.owner != MONSTER and ship.kind != "combat_drone" and ship.hull > 0:
            game.ship_at(ship.id, owner=ship.owner).hull = ship.hull
    game.ships[:] = [s for s in game.ships if not game.combat.ship(s.id) or game.combat.ship(s.id).hull > 0]
    if game.combat.guardian:
        guardian_at(game, game.combat.system_id).hull = game.combat.guardian.hull
    game.combat = None


def intercept(game):
    if game.combat or game.result:
        return False
    # Each pair at each location is processed at most once in this phase.
    encounters = list(hostile_pairs(game))
    for system_id, attacker, defender in encounters:
        if engagement_error(game, system_id, attacker, defender) is not None:
            continue
        begin_combat(game, system_id, attacker, defender)
        if "player" in game.combat.sides:
            return True
        autoresolve(game)
        if game.combat:
            game.finish_combat()
    return False
