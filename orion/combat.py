"""Deterministic, grid-based fleet combat; campaign losses commit on resolution."""

from collections import deque
from dataclasses import dataclass, field
import math

from .production import SHIP_TYPES
from .designs import HULLS, ShipDesign
from .empires import EMPIRE_IDS
from .monsters import MONSTER, MONSTERS, alive_at, at as guardian_at, observe, known_status, commit_battle_result

COMBAT_TYPES = {**SHIP_TYPES, **MONSTERS}

OWNERS = EMPIRE_IDS
HOSTILE_BELOW = -30
RESULTS = ("active", "monster_victory", *(owner+suffix for owner in OWNERS for suffix in ("_victory", "_retreat")))
BOARD_COLUMNS = 18
MIN_ROWS = 10
MOVEMENT = {"frigate": 3, "scout": 5, "colony_ship": 2, "troop_transport": 2}
MOVEMENT.update({kind: spec.movement for kind, spec in MONSTERS.items()})


@dataclass(frozen=True)
class Beam:
    name: str
    damage: int
    range: int
    color: tuple[int, int, int]


BEAMS = {
    "none": Beam("Unarmed", 0, 0, (133, 151, 160)),
    "laser": Beam("Laser", 5, 6, (255, 80, 76)),
    "quantum": Beam("Quantum beam", 7, 7, (187, 113, 255)),
    "torpedo": Beam("Torpedo", 10, 8, (255, 188, 79)),
    "plasma_breath": Beam("Plasma breath", 8, 4, (104, 255, 144)),
    "crystal_ray": Beam("Crystal ray", 10, 7, (102, 220, 255)),
    "ancient_lance": Beam("Ancient lance", 12, 8, (255, 198, 104)),
    "void_ray": Beam("Void ray", 15, 5, (196, 143, 255)),
}


def weapon_for(game, kind, owner):
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

    @property
    def name(self):
        return MONSTERS[self.kind].name if self.kind in MONSTERS else f"{self.design.name if self.design else SHIP_TYPES[self.kind].name} {self.id:03}"

    @property
    def max_hull(self):
        return self.design.hull if self.design else COMBAT_TYPES[self.kind].hull

    @property
    def damage(self):
        return self.design.damage if self.design else BEAMS[self.weapon].damage

    @property
    def weapon_range(self):
        return self.design.weapon_range if self.design else BEAMS[self.weapon].range

    @property
    def movement(self):
        return self.design.movement if self.design else MOVEMENT[self.kind]

    def volley(self, target):
        if self.design:
            return tuple((m.weapon, m.damage) for m in self.design.volley(math.dist(self.position, target.position)))
        return ((self.weapon, self.damage),)

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
        return ship.hull > 0 and ship.id not in self.moved

    def can_fire(self, ship):
        return ship.hull > 0 and ship.damage > 0 and ship.id not in self.acted

    def fleet(self, owner, *, alive=True):
        return [s for s in self.ships if s.owner == owner and (s.hull > 0 or not alive)]

    def ready(self, owner):
        return [s for s in self.fleet(owner) if self.can_move(s) or self.can_fire(s)]

    def ship(self, identifier):
        return next((s for s in self.ships if type(identifier) is int and s.id == identifier), None)

    def record(self, message):
        self.log.append(message)
        self.log = self.log[-8:]

    @classmethod
    def from_dict(cls, data, game, *, version=18):
        from .model import _integer, _name
        # Migrate copies so reading a save never mutates its source payload.
        if version < 13 and isinstance(data, dict):
            data = {**data, "moved": list(data.get("acted", []))}
            if isinstance(data.get("ships"), list):
                data["ships"] = [{k: v for k, v in row.items() if k not in ("x", "y", "weapon")}
                                 if isinstance(row, dict) else row for row in data["ships"]]
        if not isinstance(data, dict) or set(data) != {
                "system_id", "initiator", "ships", "round", "active_owner", "acted",
                "log", "status", "retreat_destination", "moved"}:
            raise ValueError("Invalid combat state")
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
            if diplomacy.relations != -100 or diplomacy.trade_active or diplomacy.research_active:
                raise ValueError("Combat does not match diplomatic state")
        ships = []
        for row in rows:
            fields = {"id", "kind", "owner", "hull", "initial_hull"}
            if version >= 13:
                fields |= {"x", "y", "weapon"}
            if version >= 18:
                fields |= {"design", "shields"}
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError("Invalid combat ship")
            monster = row["owner"] == MONSTER
            design = ShipDesign.from_dict(row["design"]) if version >= 18 and row["design"] is not None else None
            if design and (monster or design.kind != row["kind"]):
                raise ValueError("Invalid battle blueprint")
            if ((not guardian or row["id"] != guardian.combat_id or type(row["id"]) is not int) if monster
                    else not _integer(row["id"], 1, game.next_ship_id-1)):
                raise ValueError("Invalid combat identifier")
            if (row["owner"] not in sides or
                    not isinstance(row["kind"], str) or row["kind"] not in (MONSTERS if monster else HULLS if design else SHIP_TYPES) or
                    not _integer(row["initial_hull"], 1, design.hull if design else COMBAT_TYPES[row["kind"]].hull) or
                    not _integer(row["hull"], 0, row["initial_hull"])):
                raise ValueError("Invalid combat ship health")
            if version < 13:
                row = {**row, "weapon": weapon_for(game, row["kind"], row["owner"])}
            elif (not isinstance(row["weapon"], str) or row["weapon"] not in BEAMS
                  or row["weapon"] != (design.weapon if design else weapon_for(game, row["kind"], row["owner"]))):
                raise ValueError("Invalid combat weapon")
            shields = row["shields"] if version >= 18 else 0
            if not _integer(shields, 0, design.shields if design else 0) or (row["hull"] == 0 and shields):
                raise ValueError("Invalid shields")
            row = {**row, "design": design, "shields": shields}
            ships.append(CombatShip(**row))
        identifiers = {s.id for s in ships}
        if len(identifiers) != len(ships) or {s.owner for s in ships} != set(sides):
            raise ValueError("Invalid combat participants")
        if not guarded and not any(s.owner == data["initiator"] and s.damage for s in ships):
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
                          and s.owner != retreating and s.owner != MONSTER}
        if orbiting != expected_orbit:
            raise ValueError("Battle omitted orbiting ships")
        return state


def deploy(state):
    rows = state.rows
    lanes = sorted(range(rows), key=lambda y: (abs(y-(rows-1)/2), y))
    for owner in state.sides:
        for index, ship in enumerate(sorted(state.fleet(owner, alive=False), key=lambda s: s.id)):
            depth, lane = divmod(index, rows)
            ship.x = 4-depth if owner == state.sides[0] else 13+depth
            ship.y = lanes[lane]


def in_range(ship, target):
    return (ship.x-target.x)**2+(ship.y-target.y)**2 <= ship.weapon_range**2


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
    if game.strategy_error():
        return game.strategy_error()
    if type(system_id) is not int or not 0 <= system_id < len(game.systems):
        return "Unknown solar system."
    if alive_at(game, system_id) and owner in OWNERS and game.fleet_at(system_id, owner):
        return None
    if owner not in game.owners or not game.opponents:
        return "No opposing empire is available."
    target = engagement_target(game, system_id, owner, target)
    if target == owner or target not in game.owners:
        return "Both empires need ships in orbit in this system."
    own, enemy = game.fleet_at(system_id, owner), game.fleet_at(system_id, target)
    if not own or not enemy:
        return "Both empires need ships in orbit in this system."
    if not any(s.damage for s in own):
        return "Bring a frigate to engage. Scouts and transports are unarmed."
    return None


def battle_ship(game, ship):
    return CombatShip(ship.id, ship.kind, ship.owner, ship.hull, ship.hull,
                      weapon=ship.design.weapon if ship.design else weapon_for(game, ship.kind, ship.owner),
                      design=ship.design, shields=ship.design.shields if ship.design else 0)


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
    state = CombatState(system_id, owner, [battle_ship(game, s) for s in fleet], active_owner=owner)
    deploy(state)
    state.record(f"{game.empire_name_for(owner)} initiated combat at {game.systems[system_id].name}.")
    game.combat = state
    diplomacy = game.diplomacy_between(owner, target)
    diplomacy.trade_active = diplomacy.research_active = False
    diplomacy.relations = -100
    diplomacy.offer_ready_turn = game.turn+3
    diplomacy.record(game.turn, f"Combat at {game.systems[system_id].name}. Agreements ended; relations are now -100.")
    for participant in (owner, target):
        if participant != "player":
            game.rival_event(f"Battle began at {game.systems[system_id].name}.", turn=game.turn, owner=participant)
    return state


def begin_guardian_combat(game, system_id, owner="player"):
    require(game.strategy_error() is None, game.strategy_error())
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
            if target is None or target.owner == owner or target.hull <= 0:
                return "Choose a surviving enemy ship."
            if not in_range(ship, target):
                return f"Target out of range. {BEAMS[ship.weapon].name} range: {ship.weapon_range} cells."
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
            state.record(f"{guardian.spec.name} destroyed. Protected worlds are open for colonization.")
        if reward:
            state.record(reward)
            if state.sides[0] in game.opponents:
                game.rival_event(reward, turn=game.turn, owner=state.sides[0])


def check_losses(game):
    state = game.combat
    for side in state.sides:
        if not state.fleet(side):
            resolve(game, state.enemy(side)+"_victory")
            return
def end_turn(game, owner="player"):
    error = action_error(game, owner)
    require(error is None, error)
    state = game.combat
    state.active_owner = state.enemy(owner)
    if state.active_owner == state.initiator:
        state.round += 1
        state.acted.clear()
        state.moved.clear()
        state.record(f"Round {state.round}. Every surviving ship can move and fire again.")


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


def fire(game, ship_id, target_id, owner="player"):
    error = action_error(game, owner, ship_id, target_id)
    require(error is None, error)
    state = game.combat
    attacker, target = state.ship(ship_id), state.ship(target_id)
    require(attacker is not None and target is not None, "Choose an attacker and target.")
    damage, absorbed = 0, 0
    for weapon, strength in attacker.volley(target):
        if weapon == "torpedo" and target.design:
            strength = max(1, math.ceil(strength*(100-target.design.interception)/100))
        blocked = min(strength, target.shields)
        target.shields -= blocked
        absorbed += blocked
        hit = min(strength-blocked, target.hull)
        target.hull -= hit
        damage += hit
    state.acted.append(attacker.id)
    suffix = " Destroyed." if target.hull == 0 else f" {target.hull}/{target.max_hull} hull remains."
    protection = f" Shields absorbed {absorbed}." if absorbed else ""
    state.record(f"{attacker.name} hit {target.name} for {damage}.{protection}{suffix}")
    check_losses(game)
    return damage


def hold(game, ship_id, owner="player"):
    error = action_error(game, owner, ship_id)
    require(error is None, error)
    ship = game.combat.ship(ship_id)
    require(ship is not None, "Choose a ship first.")
    require(game.combat.can_move(ship) or game.combat.can_fire(ship), "This ship has finished its turn.")
    if ship.id not in game.combat.acted:
        game.combat.acted.append(ship.id)
    if ship.id not in game.combat.moved:
        game.combat.moved.append(ship.id)
    game.combat.record(f"{ship.name} held position.")


def retreat_destination(game, owner="player"):
    if game.combat is None or owner not in OWNERS:
        return None
    origin = game.systems[game.combat.system_id]
    safe = [s for s in game.systems if s.id != origin.id and
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
    if not any(s.damage for s in fleet) and retreat_destination(game, owner):
        retreat(game, owner)
        return {"kind": "retreat"}
    ready = state.ready(owner)
    if not ready:
        end_turn(game, owner)
        return {"kind": "end_turn"}
    ship = min(ready, key=lambda s: (-s.damage, s.hull, s.id))
    enemies = state.fleet(state.enemy(owner))
    targets = [s for s in enemies if in_range(ship, s)] if state.can_fire(ship) else []
    if targets:
        target = min(targets, key=lambda s: (s.hull > ship.damage, -s.damage, s.hull, s.id))
        damage = fire(game, ship.id, target.id, owner)
        return {"kind": "fire", "ship_id": ship.id, "target_id": target.id, "damage": damage}
    paths = reachable(state, ship)
    if paths and (not ship.damage or state.can_fire(ship)):
        if ship.damage:
            target = min(enemies, key=lambda s: (math.dist(ship.position, s.position), -s.damage, s.hull, s.id))
            # Close only as far as necessary; prefer a firing lane over a short blocked route.
            def score(cell):
                distance = math.dist(cell, target.position)
                return (max(0, distance-ship.weapon_range), len(paths[cell]), distance, cell)
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
        if retreat_destination(game, owner):
            retreat(game, owner)
            return
        end_turn(game, owner)
    # A trapped, immobile stalemate is disengaged with its current damage.
    for ship in game.combat.ships:
        if ship.owner != MONSTER and ship.hull > 0:
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
