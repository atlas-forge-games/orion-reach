"""Deterministic fleet combat. Tactical damage commits to the campaign on resolution."""

from dataclasses import dataclass, field

from .production import SHIP_TYPES

OWNERS = ("player", "rival")
HOSTILE_BELOW = -30
RESULTS = ("active", "player_victory", "rival_victory", "player_retreat", "rival_retreat")


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

    @property
    def name(self):
        return f"{SHIP_TYPES[self.kind].name} {self.id:03}"

    @property
    def max_hull(self):
        return SHIP_TYPES[self.kind].hull

    @property
    def damage(self):
        return SHIP_TYPES[self.kind].damage


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

    def fleet(self, owner, *, alive=True):
        return [s for s in self.ships if s.owner == owner and (s.hull > 0 or not alive)]

    def ready(self, owner):
        return [s for s in self.fleet(owner) if s.id not in self.acted]

    def ship(self, identifier):
        return next((s for s in self.ships if type(identifier) is int and s.id == identifier), None)

    def record(self, message):
        self.log.append(message)
        self.log = self.log[-8:]

    @classmethod
    def from_dict(cls, data, game):
        from .model import _integer, _name
        if not isinstance(data, dict) or set(data) != {
                "system_id", "initiator", "ships", "round", "active_owner", "acted",
                "log", "status", "retreat_destination"}:
            raise ValueError("Invalid combat state")
        if (not _integer(data["system_id"], 0, len(game.systems)-1) or
                data["initiator"] not in OWNERS or game.opponent is None or
                not _integer(data["round"], 1, 1_000_000) or data["status"] not in RESULTS):
            raise ValueError("Invalid combat location or status")
        if (game.diplomacy.relations != -100 or game.diplomacy.trade_active
                or game.diplomacy.research_active):
            raise ValueError("Combat does not match diplomatic state")
        rows = data["ships"]
        if not isinstance(rows, list) or not 2 <= len(rows) <= 10000:
            raise ValueError("Invalid battle fleet")
        ships = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"id", "kind", "owner", "hull", "initial_hull"}:
                raise ValueError("Invalid combat ship")
            if (not _integer(row["id"], 1, game.next_ship_id-1) or row["owner"] not in OWNERS or
                    not isinstance(row["kind"], str) or row["kind"] not in SHIP_TYPES or
                    not _integer(row["initial_hull"], 1, SHIP_TYPES[row["kind"]].hull) or
                    not _integer(row["hull"], 0, row["initial_hull"])):
                raise ValueError("Invalid combat ship health")
            ships.append(CombatShip(**row))
        identifiers = {s.id for s in ships}
        if len(identifiers) != len(ships) or {s.owner for s in ships} != set(OWNERS):
            raise ValueError("Invalid combat participants")
        if not any(s.owner == data["initiator"] and s.damage for s in ships):
            raise ValueError("An unarmed fleet cannot initiate combat")
        acted = data["acted"]
        if (not isinstance(acted, list) or any(type(i) is not int or i not in identifiers for i in acted)
                or len(set(acted)) != len(acted)):
            raise ValueError("Invalid activations")
        if (not isinstance(data["log"], list) or len(data["log"]) > 8
                or any(not _name(message, 180) for message in data["log"])):
            raise ValueError("Invalid combat log")
        state = cls(**{**data, "ships": ships})
        retreating = state.status.split("_")[0] if state.status.endswith("_retreat") else None
        if retreating:
            if (not _integer(state.retreat_destination, 0, len(game.systems)-1)
                    or state.retreat_destination == state.system_id
                    or any(not state.fleet(owner) for owner in OWNERS)):
                raise ValueError("Invalid retreat")
        elif state.retreat_destination is not None:
            raise ValueError("Unexpected retreat destination")
        if state.status == "active":
            if (state.active_owner not in OWNERS or not state.ready(state.active_owner)
                    or any(not state.fleet(owner) for owner in OWNERS)):
                raise ValueError("Invalid side to act")
        elif state.active_owner is not None:
            raise ValueError("Resolved battle still has an active side")
        if state.status.endswith("_victory"):
            winner = state.status.split("_")[0]
            if not state.fleet(winner) or state.fleet(other(winner)):
                raise ValueError("Invalid victory")
        campaign = {s.id: s for s in game.ships}
        for ship in ships:
            original = campaign.get(ship.id)
            if state.status != "active" and ship.hull == 0:
                if original is not None:
                    raise ValueError("Destroyed ship survived in the campaign")
                continue
            if (original is None or original.owner != ship.owner or original.kind != ship.kind
                    or original.system_id != state.system_id
                    or original.hull != (ship.initial_hull if state.status == "active" else ship.hull)):
                raise ValueError("Battle does not match the campaign fleet")
            if ship.owner == retreating:
                expected = game.travel_turns(game.systems[state.system_id], game.systems[state.retreat_destination], ship.owner)
                if (original.destination != state.retreat_destination or original.turns_remaining != expected
                        or original.travel_total != expected
                        or original.speed_bonus != game.bonuses_for(ship.owner).get("ship_speed", 0)):
                    raise ValueError("Invalid retreat voyage")
            elif original.in_transit:
                raise ValueError("Travelling ship in battle")
        orbiting = {s.id for s in game.ships if not s.in_transit and s.system_id == state.system_id}
        expected_orbit = {s.id for s in ships if (state.status == "active" or s.hull > 0)
                          and s.owner != retreating}
        if orbiting != expected_orbit:
            raise ValueError("Battle omitted orbiting ships")
        return state


def engagement_error(game, system_id, owner="player"):
    if game.strategy_error():
        return game.strategy_error()
    if type(system_id) is not int or not 0 <= system_id < len(game.systems):
        return "Unknown solar system."
    if owner not in OWNERS or game.opponent is None:
        return "No opposing empire is available."
    own, enemy = game.fleet_at(system_id, owner), game.fleet_at(system_id, other(owner))
    if not own or not enemy:
        return "Both empires need ships in orbit in this system."
    if not any(s.damage for s in own):
        return "Bring a frigate to engage. Scouts and transports are unarmed."
    return None


def begin_combat(game, system_id, owner="player"):
    error = engagement_error(game, system_id, owner)
    require(error is None, error)
    fleet = sorted(game.fleet_at(system_id, "player")+game.fleet_at(system_id, "rival"), key=lambda s: s.id)
    state = CombatState(system_id, owner, [CombatShip(s.id, s.kind, s.owner, s.hull, s.hull) for s in fleet], active_owner=owner)
    state.record(f"{game.empire_name_for(owner)} initiated combat at {game.systems[system_id].name}.")
    game.combat = state
    game.diplomacy.trade_active = game.diplomacy.research_active = False
    game.diplomacy.relations = -100
    game.diplomacy.offer_ready_turn = game.turn+3
    game.diplomacy.record(game.turn, f"Combat at {game.systems[system_id].name}. Agreements ended; relations are now -100.")
    game.rival_event(f"Battle began at {game.systems[system_id].name}.", turn=game.turn)
    return state


def action_error(game, owner, ship_id=None, target_id=None):
    state = game.combat
    if state is None or state.status != "active":
        return "There is no active battle."
    if owner not in OWNERS or state.active_owner != owner:
        return "Wait for your side's next activation."
    if ship_id is not None:
        ship = state.ship(ship_id)
        if ship is None or ship.owner != owner or ship.hull <= 0 or ship.id in state.acted:
            return "Choose one of your ships that has not acted this round."
        if target_id is not None:
            target = state.ship(target_id)
            if ship.damage == 0:
                return "Transports are unarmed. Hold or retreat."
            if target is None or target.owner == owner or target.hull <= 0:
                return "Choose a surviving enemy ship."
    return None


def resolve(game, status, destination=None):
    state = game.combat
    require(state is not None and state.status == "active", "This battle is already resolved.")
    state.status, state.active_owner, state.retreat_destination = status, None, destination
    rows = {s.id: s for s in state.ships}
    retreating = status.split("_")[0] if status.endswith("_retreat") else None
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
        message = f"{game.empire_name_for(status.split('_')[0])} won the battle."
    state.record(message)
    game.rival_event(message, turn=game.turn)


def next_activation(game, owner):
    state = game.combat
    for side in OWNERS:
        if not state.fleet(side):
            resolve(game, other(side)+"_victory")
            return
    opponent = other(owner)
    if state.ready(opponent):
        state.active_owner = opponent
    elif state.ready(owner):
        state.active_owner = owner
    else:
        state.round += 1
        state.acted.clear()
        state.active_owner = other(owner)
        state.record(f"Round {state.round}. Every surviving ship can act again.")


def fire(game, ship_id, target_id, owner="player"):
    error = action_error(game, owner, ship_id, target_id)
    require(error is None, error)
    state = game.combat
    attacker, target = state.ship(ship_id), state.ship(target_id)
    require(attacker is not None and target is not None, "Choose an attacker and target.")
    damage = min(attacker.damage, target.hull)
    target.hull -= damage
    state.acted.append(attacker.id)
    suffix = " Destroyed." if target.hull == 0 else f" {target.hull}/{target.max_hull} hull remains."
    state.record(f"{attacker.name} hit {target.name} for {damage}.{suffix}")
    next_activation(game, owner)
    return damage


def hold(game, ship_id, owner="player"):
    error = action_error(game, owner, ship_id)
    require(error is None, error)
    ship = game.combat.ship(ship_id)
    require(ship is not None, "Choose a ship first.")
    game.combat.acted.append(ship.id)
    game.combat.record(f"{ship.name} held position.")
    next_activation(game, owner)


def retreat_destination(game, owner="player"):
    if game.combat is None or owner not in OWNERS:
        return None
    origin = game.systems[game.combat.system_id]
    safe = [s for s in game.systems if s.id != origin.id and
            not (game.system_visible(s.id, owner) and game.fleet_at(s.id, other(owner)))]
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


def ai_action(game):
    error = action_error(game, "rival")
    require(error is None, error)
    state = game.combat
    fleet = state.fleet("rival")
    if not any(s.damage for s in fleet) and retreat_destination(game, "rival"):
        retreat(game, "rival")
        return None
    ship = min(state.ready("rival"), key=lambda s: (-s.damage, s.hull, s.id))
    if not ship.damage:
        hold(game, ship.id, "rival")
        return None
    target = min(state.fleet("player"), key=lambda s: (s.hull > ship.damage, -s.damage, s.hull, s.id))
    fire(game, ship.id, target.id, "rival")
    return ship.id, target.id


def hostile_encounter(game):
    if game.opponent is None or game.diplomacy.relations >= HOSTILE_BELOW:
        return None
    return next((s.id for s in game.systems if engagement_error(game, s.id, "rival") is None), None)
