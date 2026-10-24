"""System-scale construction and effects, using the same budget as colony queues."""
from dataclasses import dataclass, field
import random

from . import economy, administration, specialists, monsters, defenses
from .research import colony_yields, TECHNOLOGIES
from .navigation import hostile

STAGES = 4
REPAIR_WORK = 2
REPAIR_RESOURCES = 3


@dataclass(frozen=True)
class MegastructureSpec:
    id: str
    name: str
    description: str
    branch: str
    tier: int
    resource_cost: int
    work_cost: int
    energy_per_stage: int = 0
    ship_speed_per_stage: int = 0
    resources_per_stage: int = 0
    discovery_chance_per_stage: int = 0
    hull: int = 200


MEGASTRUCTURES = {s.id: s for s in (
    MegastructureSpec("dyson_sphere", "Dyson Sphere", "A stellar collector shell. Completion supplies unlimited energy to every colony in your empire.",
                      "power", 4, 2000, 400, energy_per_stage=30),
    MegastructureSpec("stellar_forge", "Stellar Forge", "An immense orbital shipyard. Accelerates only ship construction in this system; buildings and Trade Goods gain no bonus.",
                      "construction", 3, 1800, 350, ship_speed_per_stage=3),
    MegastructureSpec("research_array", "Research Array", "Deep-space instruments sometimes discover an unknown technology, including a choice omitted earlier. Produces no research points.",
                      "physics", 7, 1500, 300, discovery_chance_per_stage=1),
    MegastructureSpec("asteroid_network", "Asteroid Mining Network", "Automated mines and refineries deliver large resource shipments directly to the empire each turn.",
                      "materials", 6, 1600, 320, resources_per_stage=150),
)}


@dataclass
class Megastructure:
    kind: str
    owner: str
    builder: str
    stage: int = 0
    progress: int = 0
    allocation: int = 50
    paused: bool = False
    hull: int = 200
    last_attacked: int = 0

    @property
    def spec(self):
        return MEGASTRUCTURES[self.kind]

    @property
    def max_hull(self):
        return self.spec.hull*(self.stage+1)

    @property
    def stage_work(self):
        return self.spec.work_cost*(self.stage+1) if self.stage < STAGES else 0

    @property
    def stage_resources(self):
        return self.spec.resource_cost*(self.stage+1) if self.stage < STAGES else 0

    @classmethod
    def from_dict(cls, row, owners, turn):
        from .model import _integer
        if not isinstance(row, dict) or set(row) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid megastructure")
        if not isinstance(row["kind"], str) or row["kind"] not in MEGASTRUCTURES or row["owner"] not in owners or row["builder"] not in owners:
            raise ValueError("Invalid megastructure owner or type")
        m = cls(**row)
        if (not _integer(m.stage, 0, STAGES) or not _integer(m.progress, 0, max(0, m.stage_work-1))
                or not _integer(m.allocation, 0, 100) or type(m.paused) is not bool
                or not _integer(m.hull, 1, m.max_hull) or not _integer(m.last_attacked, 0, turn)):
            raise ValueError("Invalid megastructure progress")
        return m


def settled_owners(system):
    return {p.owner for p in system.worlds if p.colonized}


def work_error(game, system, owner):
    from . import encounters
    if settled_owners(system) != {owner}:
        return "Construction requires sole control of all settlements in this system."
    if monsters.alive_at(game, system.id):
        return "Defeat the system guardian first."
    if encounters.blockade(game, system.id):
        return "Clear the pirate fleet before continuing construction."
    if any(hostile(game, s.owner, owner) and (s.damage or s.drone_bays)
           for s in game.ships if not s.in_transit and s.system_id == system.id):
        return "Hostile armed ships are blocking construction."
    return None


def start_error(game, system_id, kind, owner="player"):
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    if kind not in MEGASTRUCTURES:
        return "Unknown megastructure."
    system = game.systems[system_id]
    if system.megastructure:
        return "Only one megastructure may occupy each solar system."
    if kind in game.megastructure_history.get(owner, []):
        return "Each civilization may commission this megastructure only once per campaign."
    reason = work_error(game, system, owner)
    if reason:
        return reason
    spec = MEGASTRUCTURES[kind]
    if not any(t >= spec.tier for t in game.research_state(owner).completed_tiers(spec.branch)):
        from .research import BRANCHES
        return f"Requires tier {spec.tier} in {BRANCHES[spec.branch].name} (either choice)."
    return None


def start(game, system_id, kind, owner="player"):
    from .model import RuleError
    from .exploration import refresh
    reason = start_error(game, system_id, kind, owner)
    if reason:
        raise RuleError(reason)
    game.systems[system_id].megastructure = Megastructure(kind, owner, owner, hull=MEGASTRUCTURES[kind].hull)
    game.megastructure_history.setdefault(owner, []).append(kind)
    refresh(game)


def configure(game, system_id, *, allocation=None, paused=None, owner="player"):
    from .model import RuleError
    game._require_strategy(owner)
    m = game.systems[system_id].megastructure
    if m is None or m.owner != owner:
        raise RuleError("This is not your megastructure.")
    if allocation is not None and (type(allocation) is not int or not 0 <= allocation <= 100):
        raise RuleError("Choose an industry contribution from 0 to 100 percent.")
    if paused is not None and type(paused) is not bool:
        raise RuleError("Invalid construction setting.")
    if allocation is not None:
        m.allocation = allocation
    if paused is not None:
        m.paused = paused
    from .exploration import refresh
    refresh(game)


def normalize(game):
    """A sole new settler inherits a stranded structure, with work paused."""
    for system in game.systems:
        m = system.megastructure
        owners = settled_owners(system)
        if m and m.owner not in owners and len(owners) == 1:
            m.owner = next(iter(owners))
            m.paused = True


def _eligible(game, system, owner):
    m = system.megastructure
    return bool(m and m.owner == owner and m.stage and owner in settled_owners(system)
                and not monsters.alive_at(game, system.id)
                and not any(hostile(game, s.owner, owner) and (s.damage or s.drone_bays)
                            for s in game.ships if not s.in_transit and s.system_id == system.id))


def active(game, owner):
    """Only the strongest operational structure of each type supplies effects."""
    found = set()
    systems = sorted((s for s in game.systems if s.megastructure),
                     key=lambda s: (-s.megastructure.stage, s.id))
    for system in systems:
        m = system.megastructure
        if _eligible(game, system, owner) and m.kind not in found:
            found.add(m.kind)
            yield system


def operational(game, system, owner):
    return any(s.id == system.id for s in active(game, owner))


def operating_status(game, system):
    m = system.megastructure
    if not m.stage:
        return "Awaiting commissioning"
    if operational(game, system, m.owner):
        return "Operational"
    if _eligible(game, system, m.owner):
        return "Duplicate type: only the empire's strongest structure supplies effects"
    return "Offline / blockaded"


def empire_effects(game, owner):
    for system in active(game, owner):
        m = system.megastructure
        if m.kind == "dyson_sphere":
            return {"unlimited_energy": int(m.stage == STAGES), "colony_energy": m.stage*m.spec.energy_per_stage}
    return {}


def has_projects(game, owner):
    return any(s.megastructure and s.megastructure.owner == owner for s in game.systems)


@dataclass
class EconomicPlan:
    bonuses: object
    power: dict
    net_resources: int = 0
    resource_income: int = 0
    orders: list = field(default_factory=list)
    contributions: dict = field(default_factory=dict)
    arrays: tuple = ()


def make_plan(game, owner):
    """Preview/freeze one turn. Fuel first, then affordable megastructure work.

    No preview mutates the campaign. Only actual funded industry is diverted;
    an empty stockpile or contested site leaves colony production untouched.
    """
    base = game._base_bonuses(owner)
    colonies = [(s.id, p) for s, p in game.settlements(owner)]
    from . import gas_giants
    power = gas_giants.dispatch_power(game, owner, colonies, base, game.resources_for(owner))
    context = administration.Context(game, owner)
    from . import species
    def colony_effects(p):
        effects = {**specialists.colony_effects(game, p), **context.effects(p)}
        for key, value in species.local_effects(game, p).items():
            effects[key] = effects.get(key, 0)+value
        return effects
    local = {id(p): colony_effects(p) for _, p in colonies}
    operating = list(active(game, owner))
    for system in operating:
        m = system.megastructure
        if m.spec.ship_speed_per_stage:
            for sid, p in colonies:
                if sid == system.id:
                    local[id(p)]["ship_work_multiplier"] = 1+m.stage*m.spec.ship_speed_per_stage
    def local_effects(p):
        if id(p) in local:
            return local[id(p)]
        return colony_effects(p)
    bonuses = economy.PowerBonuses(base,
        lambda p: power[id(p)] if id(p) in power else economy.energy_report(p, base),
        local_effects)
    income = sum(s.megastructure.stage*s.megastructure.spec.resources_per_stage for s in operating)
    net = sum(economy.mining_output(p, bonuses)-power[id(p)].fuel_used for _, p in colonies)+income
    plan = EconomicPlan(bonuses, power, net, income,
                        arrays=tuple(s.id for s in operating if s.megastructure.kind == "research_array"))
    budget = max(0, game.resources_for(owner)+net)
    for system in game.systems:
        m = system.megastructure
        if not m or m.owner != owner or m.paused or not m.allocation or work_error(game, system, owner):
            continue
        worlds = [p for sid, p in colonies if sid == system.id]
        available = {id(p): colony_yields(p, bonuses)[0]*m.allocation//100 for p in worlds}
        wanted = sum(available.values())
        repair = m.hull < m.max_hull
        if repair:
            points = min(m.max_hull-m.hull, wanted//REPAIR_WORK, budget//REPAIR_RESOURCES)
            work, cost = points*REPAIR_WORK, points*REPAIR_RESOURCES
        elif m.stage < STAGES:
            paid = (m.progress*m.stage_resources+m.stage_work-1)//m.stage_work
            possible = (budget+paid)*m.stage_work//m.stage_resources-m.progress
            work = max(0, min(wanted, m.stage_work-m.progress, possible))
            cost = ((m.progress+work)*m.stage_resources+m.stage_work-1)//m.stage_work-paid
            points = work
        else:
            continue
        if work == 0:
            continue
        budget -= cost
        plan.net_resources -= cost
        plan.orders.append((system.id, points, cost, repair))
        remaining = work
        # Proportional contribution, followed by a deterministic remainder.
        shares = {id(p): available[id(p)]*work//max(1, wanted) for p in worlds}
        remainder = work-sum(shares.values())
        for p in worlds:
            if remainder and shares[id(p)] < available[id(p)]:
                shares[id(p)] += 1
                remainder -= 1
            local[id(p)]["megastructure_work"] = shares[id(p)]
            plan.contributions[(system.id, p.id)] = shares[id(p)]
            remaining -= shares[id(p)]
        assert remaining == 0
    return plan


def plan_for(game, owner):
    frozen = getattr(game, "_turn_megastructures", {})
    if owner in frozen:
        return frozen[owner]
    # UI redraws call yields many times. Include all production/ownership inputs.
    signature = (game.turn, game.resources_for(owner), repr(game._base_bonuses(owner)),
                 repr(game.systems), repr(game.ships), repr(game.guardians), repr(game.encounters), repr(game.specialists),
                 repr(game.system_integration), repr(game.diplomacy), repr(game.other_diplomacy),
                 repr(MEGASTRUCTURES), REPAIR_WORK, REPAIR_RESOURCES)
    cache = getattr(game, "_mega_cache", {})
    if owner not in cache or cache[owner][0] != signature:
        cache[owner] = (signature, make_plan(game, owner))
        game._mega_cache = cache
    return cache[owner][1]


def finish_work(game):
    messages = []
    for owner, plan in getattr(game, "_turn_megastructures", {}).items():
        for sid, points, cost, repair in plan.orders:
            m = game.systems[sid].megastructure
            if repair:
                m.hull += points
                continue
            m.progress += points
            if m.progress == m.stage_work:
                m.stage += 1
                m.progress = 0
                m.hull += m.spec.hull
                message = f"{m.spec.name} at {game.systems[sid].name}: stage {m.stage}/{STAGES} completed."
                if owner == "player":
                    messages.append(message)
                else:
                    game.rival_event(message, owner=owner)
    return messages


def discover(game):
    messages = []
    for owner, plan in getattr(game, "_turn_megastructures", {}).items():
        for sid in plan.arrays:
            m = game.systems[sid].megastructure
            # Starting-turn stage: an array finishing a section benefits next turn.
            chance = getattr(game, "_array_chances", {}).get(sid, 0)
            rng = random.Random(f"orion-array-v1:{game.seed}:{owner}:{sid}:{game.turn}")
            if rng.randrange(100) >= chance:
                continue
            state = game.research_state(owner)
            unknown = [t for t in TECHNOLOGIES if t not in state.completed
                       and (t != "ascension_theory" or "science" in game.victory_conditions)]
            if not unknown:
                continue
            identifier = rng.choice(sorted(unknown))
            empire = game._empire(owner)
            # An omitted choice can make the ongoing alternative excluded;
            # finish/refund that project cleanly so saves remain valid.
            if state.active and (state.legacy_active or state.active == identifier or
                    (TECHNOLOGIES[state.active].branch == TECHNOLOGIES[identifier].branch
                     and TECHNOLOGIES[state.active].tier == TECHNOLOGIES[identifier].tier)):
                empire.research += state.progress
                state.active, state.progress, state.legacy_active = None, 0, False
            state.completed.append(identifier)
            state.recovered.append(identifier)
            message = f"{m.spec.name} discovered {TECHNOLOGIES[identifier].name} at {game.systems[sid].name}."
            if owner == "player":
                messages.append(message)
            else:
                game.rival_event(message, turn=game.turn, owner=owner)
            from .black_holes import report_mapping
            report_mapping(game, owner)
    return messages


def load(game, data, version):
    history = data.get("megastructure_history", {}) if version >= 42 else {}
    if not isinstance(history, dict) or any(owner not in game.owners for owner in history):
        raise ValueError("Invalid megastructure history")
    for owner, kinds in history.items():
        if (not isinstance(kinds, list) or len(kinds) > len(MEGASTRUCTURES)
                or any(not isinstance(k, str) or k not in MEGASTRUCTURES for k in kinds) or len(set(kinds)) != len(kinds)):
            raise ValueError("Invalid megastructure construction history")
    built = set()
    for system in game.systems:
        if system.megastructure is not None:
            m = Megastructure.from_dict(system.megastructure, game.owners, game.turn)
            claim = (m.builder, m.kind)
            if claim in built or m.kind not in history.get(m.builder, []):
                raise ValueError("Duplicate or unrecorded megastructure")
            built.add(claim)
            system.megastructure = m
    game.megastructure_history = {o: v.copy() for o, v in history.items()}


def attack_error(game, sid, owner="player"):
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    m = game.systems[sid].megastructure
    if not m or m.owner == owner:
        return "Choose an opposing megastructure."
    if monsters.alive_at(game, sid) or game.foreign_fleet(sid, owner) or any(p.owner != owner for p in defenses.bases(game, sid)):
        return "Defeat opposing fleets, guardians and missile bases first."
    if not defenses.bombardment_fleet(game, sid, owner):
        return "Bring armed ships that have not bombarded this turn."
    return None


def attack(game, sid, owner="player"):
    from .model import RuleError
    from .victory import record_ground_hostility
    from .exploration import record_survey, refresh
    reason = attack_error(game, sid, owner)
    if reason:
        raise RuleError(reason)
    system = game.systems[sid]
    m = system.megastructure
    damage = min(m.hull, sum(d for d, _ in defenses.bombardment_attacks(game, sid, owner)))
    m.hull -= damage
    m.last_attacked = game.turn
    for ship in defenses.bombardment_fleet(game, sid, owner):
        ship.bombarded_turn = game.turn
        if ship.departure_pending:
            game._clear_course(ship)
    message = f"{m.spec.name} at {system.name}: {damage} damage, {m.hull}/{m.max_hull} hull remaining."
    if not m.hull:
        system.megastructure = None
        message = f"{m.spec.name} at {system.name} destroyed."
    record_ground_hostility(game, owner, m.owner, message)
    record_survey(game, sid, m.owner)
    refresh(game)
    return message


def ai_orders(game, owner):
    """Late-game investment from a substantial reserve, using player rules."""
    normalize(game)
    for system in game.systems:
        m = system.megastructure
        if (m and hostile(game, owner, m.owner) and game.system_visible(system.id, owner)
                and attack_error(game, system.id, owner) is None):
            attack(game, system.id, owner)
    for system in game.systems:
        m = system.megastructure
        if m and m.owner == owner:
            m.paused = game.resources_for(owner) < 300
            m.allocation = 25
    if game.resources_for(owner) < 4000 or game.empire_rates_for(owner)[0] < 0:
        return
    if any(s.megastructure and s.megastructure.owner == owner and s.megastructure.stage < STAGES for s in game.systems):
        return
    for kind in ("asteroid_network", "dyson_sphere", "stellar_forge", "research_array"):
        candidates = [s for s in game.systems if start_error(game, s.id, kind, owner) is None]
        if candidates:
            system = max(candidates, key=lambda s: sum(game.planet_yields(p)[0] for p in s.worlds if p.owner == owner))
            start(game, system.id, kind, owner)
            system.megastructure.allocation = 25
            break
