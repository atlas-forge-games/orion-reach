"""Unique, empire-independent characters, Space Hub visitors and finite expeditions.

No random rolls are made while drawing or loading. A character has one record
for the entire galaxy and keeps experience when changing employers.
"""
from dataclasses import dataclass, field, fields
import random

PLAYER = "player"
XP_PER_TURN = 1
XP_PER_LEVEL = 5
MAX_LEVEL = 5
MAX_EMPLOYED = 4
MAX_VISITORS = 3
VISIT_INTERVAL = 4
VISIT_DURATION = 6
SURVEY_WORK = 12
SOCIAL_VISIT_CHANCE = 80
NORMAL_VISIT_CHANCE = 55
ISOLATED_VISIT_CHANCE = 30

SKILLS = {
    "industry": ("Engineering", "IND/turn", "colony_industry"),
    "research": ("Science", "RP/turn", "colony_research"),
    "income": ("Commerce", "CR/turn", "colony_income"),
    "food": ("Agriculture", "food/turn", "colony_food"),
    "mining": ("Geology", "RES/turn", "colony_resources"),
    "survey": ("Surveying", "survey work/turn", None),
    "hacking": ("Hacking", "recovery work/turn", None),
    "extraction": ("Salvaging", "recovery work/turn", None),
    "archaeology": ("Archaeology", "recovery work/turn", None),
}
ROLES = {"leader": "Colony leader", "explorer": "Explorer"}


@dataclass(frozen=True)
class SpecialistSpec:
    id: str
    name: str
    role: str
    description: str
    hiring_fee: int
    salary: int
    industry: int = 0
    research: int = 0
    income: int = 0
    food: int = 0
    mining: int = 0
    survey: int = 0
    hacking: int = 0
    extraction: int = 0
    archaeology: int = 0


SPECIALISTS = {s.id: s for s in (
    SpecialistSpec("mara_voss", "Mara Voss", "leader", "A shipyard engineer who turns small colonies into productive workshops.", 65, 3, industry=4, mining=1),
    SpecialistSpec("ilyra_senn", "Ilyra Senn", "leader", "An Aelari scholar who funds careful experiments through commercial partnerships.", 80, 3, research=4, income=1),
    SpecialistSpec("tarek_sol", "Tarek Sol", "leader", "A Terran merchant who builds reliable markets and food distribution networks.", 75, 3, income=5, food=1),
    SpecialistSpec("doran_kesh", "Doran Kesh", "leader", "A veteran mining foreman with an eye for neglected seams and practical machinery.", 65, 3, mining=4, industry=1),
    SpecialistSpec("veya_tal", "Veya Tal", "leader", "An ecologist who combines productive farms with patient field research.", 55, 2, food=4, research=1),
    SpecialistSpec("civic_seven", "Civic Unit Seven", "leader", "An independent synthetic planner specializing in laboratories and automated workshops.", 85, 4, industry=3, research=2),
    SpecialistSpec("orun_basalt", "Orun Basalt", "leader", "A Lithar prospector who knows both mineral deposits and their market value.", 70, 3, mining=3, income=2),
    SpecialistSpec("nera_vale", "Nera Vale", "leader", "A Concord organizer whose trading cooperatives keep isolated colonies supplied.", 60, 2, income=3, food=2),
    SpecialistSpec("silex_morrow", "Silex Morrow", "leader", "A frontier builder equally at home in a greenhouse or a machine shop.", 60, 2, industry=2, food=3),
    SpecialistSpec("ashen_archivist", "The Ashen Archivist", "leader", "A wandering Remnant custodian who reconstructs lost methods of analysis and extraction.", 90, 4, research=3, mining=2),
    SpecialistSpec("kaia_ren", "Kaia Ren", "explorer", "A fast-moving surveyor and station hacker, with some experience recovering machinery.", 65, 3, survey=3, hacking=3, extraction=1),
    SpecialistSpec("torvek", "Torvek Flint", "explorer", "A patient asteroid prospector who can also identify traces of ancient settlements.", 60, 2, survey=2, extraction=4, archaeology=1),
    SpecialistSpec("saeli_orr", "Saeli Orr", "explorer", "An Aelari archaeologist who deciphers old ruins and their security systems.", 75, 3, survey=2, archaeology=4, hacking=1),
    SpecialistSpec("juno_pike", "Juno Pike", "explorer", "A veteran pathfinder with broad, practical recovery skills.", 70, 3, survey=4, hacking=1, extraction=2),
    SpecialistSpec("echo_nine", "Echo Nine", "explorer", "An independent codebreaker built to explore abandoned networks.", 85, 4, survey=1, hacking=5, archaeology=2),
    SpecialistSpec("brakka_vein", "Brakka Vein", "explorer", "A Lithar salvage expert who can extract valuable ore from almost any wreck.", 80, 3, survey=1, extraction=5, hacking=2),
    SpecialistSpec("lysander_quill", "Lysander Quill", "explorer", "A historian whose exhaustive surveys reveal the context behind ancient discoveries.", 70, 3, survey=3, archaeology=3, extraction=1),
    SpecialistSpec("vesper_relay", "Vesper Relay", "explorer", "A Concord expedition mediator with an adaptable mix of technical skills.", 90, 4, survey=2, hacking=2, extraction=2, archaeology=2),
)}


@dataclass(frozen=True)
class SiteSpec:
    id: str
    name: str
    description: str
    skill: str
    difficulty: int
    work: int
    credits: int = 0
    resources: int = 0
    research: int = 0

    @property
    def reward(self):
        return " + ".join(f"{n} {unit}" for n, unit in
                          ((self.credits, "CR"), (self.resources, "RES"), (self.research, "RP")) if n) or "No resources"


SITES = {s.id: s for s in (
    SiteSpec("sealed_station", "Sealed trading station", "Bypass an abandoned station's security to recover its credit reserves.", "hacking", 2, 18, credits=120),
    SiteSpec("rare_asteroid", "Rare mineral asteroid", "Recover a small, unusually rich deposit before its unstable rock breaks apart.", "extraction", 2, 20, resources=80),
    SiteSpec("ancient_observatory", "Ancient observatory", "Reconstruct the instruments and translate their surviving research records.", "archaeology", 2, 18, research=80),
)}


@dataclass
class Specialist:
    id: str
    owner: str | None = None
    visitor: str | None = None
    system_id: int | None = None
    planet_id: int | None = None
    expires: int = 0
    available_after: int = 0
    xp: int = 0

    @property
    def spec(self):
        return SPECIALISTS[self.id]

    @property
    def level(self):
        return max(n for n in range(1, MAX_LEVEL+1) if self.xp >= level_xp(n))

    def skill(self, key):
        base = getattr(self.spec, key)
        return base+self.level-1 if base else 0

    @property
    def skills(self):
        return {key: self.skill(key) for key in SKILLS if getattr(self.spec, key)}


def level_xp(level):
    return XP_PER_LEVEL*level*(level-1)//2


@dataclass
class Site:
    system_id: int
    kind: str
    surveyed: int = 0
    progress: int = 0
    recovered_by: str | None = None
    known_by: list[str] = field(default_factory=list)

    @property
    def spec(self):
        return SITES[self.kind]


@dataclass
class SpecialistEvent:
    turn: int
    owner: str
    message: str


@dataclass
class SpecialistState:
    people: list[Specialist] = field(default_factory=lambda: [Specialist(k) for k in SPECIALISTS])
    sites: list[Site] = field(default_factory=list)
    next_visit: dict[str, int] = field(default_factory=dict)
    welcomed: list[str] = field(default_factory=list)
    events: list[SpecialistEvent] = field(default_factory=list)
    news_read: int = 0


def person(game, identifier):
    return next((p for p in game.specialists.people if p.id == identifier), None)


def employed(game, owner=PLAYER):
    return [p for p in game.specialists.people if p.owner == owner]


def hubs(game, owner=PLAYER):
    return [(s.id, p.id) for s in game.systems for p in s.worlds
            if p.owner == owner and "space_hub" in p.buildings and game.building_operational(p, "space_hub")]


def visitors(game, owner=PLAYER):
    available = set(hubs(game, owner))
    return [p for p in game.specialists.people if p.visitor == owner and p.expires > game.turn
            and (p.system_id, p.planet_id) in available]


def salaries(game, owner=PLAYER):
    return sum(p.spec.salary for p in employed(game, owner))


def colony_effects(game, planet, turns=0):
    if not planet.colonized:
        return {}
    leader = next((p for p in employed(game, planet.owner) if p.spec.role == "leader"
                   and p.system_id is not None and p.planet_id == planet.id
                   and game.systems[p.system_id].worlds[p.planet_id] is planet), None)
    if leader is None:
        return {}
    level = max(n for n in range(1, MAX_LEVEL+1) if leader.xp+turns*XP_PER_TURN >= level_xp(n))
    return {SKILLS[key][2]: getattr(leader.spec, key)+level-1
            for key in SKILLS if SKILLS[key][2] and getattr(leader.spec, key)}


def eligible_system(game, sid, owner):
    if type(sid) is not int or not 0 <= sid < len(game.systems):
        return False
    worlds = game.systems[sid].worlds
    return any(p.owner == owner for p in worlds) and not any(p.colonized and p.owner != owner for p in worlds)


def record(game, owner, message):
    game.specialists.events.append(SpecialistEvent(game.turn, owner, message))
    if owner != PLAYER:
        game.rival_event(message, owner=owner)


def hire_error(game, identifier, owner=PLAYER):
    if owner not in game.owners:
        return "Choose an existing empire."
    if error := game.strategy_error(owner):
        return error
    p = person(game, identifier)
    if p is None or p not in visitors(game, owner):
        return "This specialist is not visiting one of your operational Space Hubs."
    if len(employed(game, owner)) >= MAX_EMPLOYED:
        return f"You can employ up to {MAX_EMPLOYED} specialists. Dismiss someone first."
    if game._empire(owner).credits < p.spec.hiring_fee:
        return f"Hiring requires {p.spec.hiring_fee} CR."
    return None


def hire(game, identifier, owner=PLAYER):
    from .model import RuleError
    if error := hire_error(game, identifier, owner):
        raise RuleError(error)
    p = person(game, identifier)
    game._empire(owner).credits -= p.spec.hiring_fee
    p.owner, p.visitor, p.expires = owner, None, 0
    p.system_id = p.planet_id = None
    record(game, owner, f"Hired {p.spec.name}: {p.spec.hiring_fee} CR fee; {p.spec.salary} CR/turn salary.")
    return p


def assignment_error(game, identifier, sid, pid=None, owner=PLAYER):
    if owner not in game.owners:
        return "Choose an existing empire."
    if error := game.strategy_error(owner):
        return error
    p = person(game, identifier)
    if p is None or p.owner != owner:
        return "Choose one of your hired specialists."
    if type(sid) is not int or not 0 <= sid < len(game.systems):
        return "Choose one of your colonies or systems."
    if p.spec.role == "leader":
        worlds = game.systems[sid].worlds
        if type(pid) is not int or not 0 <= pid < len(worlds) or worlds[pid].owner != owner:
            return "Leaders can only govern your own colonies."
        if any(other.id != p.id and other.spec.role == "leader" and (other.system_id, other.planet_id) == (sid, pid)
               for other in employed(game, owner)):
            return "This colony already has a leader."
    else:
        if pid is not None or not eligible_system(game, sid, owner):
            return "Explorers need a system with your colony and no foreign colonies."
        if any(other.id != p.id and other.spec.role == "explorer" and other.system_id == sid
               for other in employed(game, owner)):
            return "An explorer is already assigned to this system."
        site = site_at(game, sid)
        if site and site.recovered_by:
            return "This system's expedition site has already been recovered."
    return None


def assign(game, identifier, sid, pid=None, owner=PLAYER):
    from .model import RuleError
    if error := assignment_error(game, identifier, sid, pid, owner):
        raise RuleError(error)
    p = person(game, identifier)
    p.system_id, p.planet_id = sid, pid
    if p.spec.role == "explorer":
        site = site_at(game, sid)
        if site is None:
            kind = random.Random(f"site:{game.seed}:{sid}").choice(tuple(SITES))
            site = Site(sid, kind)
            game.specialists.sites.append(site)
        if owner not in site.known_by:
            site.known_by.append(owner)


def unassign(game, identifier, owner=PLAYER):
    from .model import RuleError
    game._require_strategy(owner)
    p = person(game, identifier)
    if owner not in game.owners or p is None or p.owner != owner:
        raise RuleError("Choose one of your hired specialists.")
    p.system_id = p.planet_id = None


def dismiss(game, identifier, owner=PLAYER):
    unassign(game, identifier, owner)
    p = person(game, identifier)
    p.owner = None
    p.available_after = game.turn+VISIT_INTERVAL
    record(game, owner, f"Dismissed {p.spec.name}. Salary ends immediately; experience is retained.")


def site_at(game, sid):
    return next((s for s in game.specialists.sites if s.system_id == sid), None)


def normalize(game):
    """Conquest, destruction and shutdown never transfer characters to an enemy."""
    active_hubs = {owner: set(hubs(game, owner)) for owner in game.owners}
    for p in game.specialists.people:
        if p.visitor and (p.expires <= game.turn or (p.system_id, p.planet_id) not in active_hubs.get(p.visitor, ())):
            p.visitor, p.system_id, p.planet_id, p.expires = None, None, None, 0
            p.available_after = game.turn+VISIT_INTERVAL
        if p.owner and not game.colony_systems(p.owner):
            p.owner, p.system_id, p.planet_id = None, None, None
            p.available_after = game.turn+VISIT_INTERVAL
        if p.owner and p.system_id is not None:
            valid = (game.planet_at(p.system_id, p.planet_id).owner == p.owner if p.spec.role == "leader"
                     else eligible_system(game, p.system_id, p.owner))
            if not valid:
                record(game, p.owner, f"{p.spec.name} returned to reserve after losing their assignment.")
                p.system_id = p.planet_id = None


def visit_chance(game, owner):
    race = game._empire(owner).race_id
    return SOCIAL_VISIT_CHANCE if race in ("terran", "concord") else ISOLATED_VISIT_CHANCE if race in ("remnant", "nexus", "varkesh") else NORMAL_VISIT_CHANCE


def advance_visitors(game):
    normalize(game)
    # Rotate empire order so the player does not always claim the last candidate.
    owners = list(game.owners)
    rng = random.Random(f"visitors:{game.seed}:{game.turn}")
    rng.shuffle(owners)
    for owner in owners:
        locations = hubs(game, owner)
        if not locations:
            continue
        first = owner not in game.specialists.welcomed
        if not first and game.turn < game.specialists.next_visit.get(owner, 0):
            continue
        game.specialists.next_visit[owner] = game.turn+VISIT_INTERVAL
        if first:
            game.specialists.welcomed.append(owner)
        for role in (("leader", "explorer") if first else (None,)):
            if len(visitors(game, owner)) >= MAX_VISITORS:
                break
            if not first and rng.randrange(100) >= visit_chance(game, owner):
                continue
            choices = [p for p in game.specialists.people if p.owner is None and p.visitor is None
                       and p.available_after <= game.turn and (role is None or p.spec.role == role)]
            if not choices:
                continue
            p = rng.choice(choices)
            p.visitor, p.expires = owner, game.turn+VISIT_DURATION
            p.system_id, p.planet_id = rng.choice(locations)
            record(game, owner, f"{p.spec.name} is visiting the Space Hub on {game.planet_at(p.system_id, p.planet_id).name} until turn {p.expires}.")


def expedition_status(game, p):
    if p.system_id is None:
        return "In reserve · choose a system to explore"
    site = site_at(game, p.system_id)
    if not eligible_system(game, p.system_id, p.owner):
        return "Assignment lost · returns to reserve next turn"
    if game.foreign_fleet(p.system_id, p.owner):
        return "Paused · foreign fleet in system"
    if site.surveyed < SURVEY_WORK:
        return f"Surveying · {site.surveyed}/{SURVEY_WORK} work"
    if site.recovered_by:
        return "Site recovered"
    skill = p.skill(site.spec.skill)
    if skill < site.spec.difficulty:
        return f"Blocked · needs {SKILLS[site.spec.skill][0]} {site.spec.difficulty} (has {skill})"
    return f"Recovering · {site.progress}/{site.spec.work} work"


def advance_employed(game):
    """Use starting skills for expeditions; new levels affect the following turn.

    Salaries are already included in empire_rates_for and banked by the model,
    exactly like building maintenance. Debt follows the ordinary treasury rules.
    """
    normalize(game)
    for p in game.specialists.people:
        if p.owner is None:
            continue
        if p.spec.role == "explorer" and p.system_id is not None and not game.foreign_fleet(p.system_id, p.owner):
            site = site_at(game, p.system_id)
            if site.recovered_by:
                p.system_id = None
            elif site.surveyed < SURVEY_WORK:
                site.surveyed = min(SURVEY_WORK, site.surveyed+p.skill("survey"))
                if site.surveyed == SURVEY_WORK:
                    record(game, p.owner, f"{p.spec.name} found {site.spec.name} in {game.systems[p.system_id].name}. Needs {SKILLS[site.spec.skill][0]} {site.spec.difficulty}; reward {site.spec.reward}.")
            elif p.skill(site.spec.skill) >= site.spec.difficulty:
                site.progress = min(site.spec.work, site.progress+p.skill(site.spec.skill))
                if site.progress == site.spec.work:
                    empire = game._empire(p.owner)
                    empire.credits += site.spec.credits
                    empire.resources += site.spec.resources
                    empire.research += site.spec.research
                    site.recovered_by = p.owner
                    record(game, p.owner, f"{p.spec.name} recovered {site.spec.name} in {game.systems[p.system_id].name}: +{site.spec.reward}. Expedition complete.")
                    p.system_id = None
        previous = p.level
        p.xp = min(level_xp(MAX_LEVEL), p.xp+XP_PER_TURN)
        if p.level > previous:
            record(game, p.owner, f"{p.spec.name} reached level {p.level}. Each starting skill improves by one.")


def ai_orders(game, owner):
    """The AI pays the same fees and salaries and uses only its own Hub visitors."""
    normalize(game)
    empire = game._empire(owner)
    for p in list(employed(game, owner)):
        if empire.credits < 0 and game.empire_rates_for(owner)[0] < 0:
            dismiss(game, p.id, owner)
    for p in visitors(game, owner):
        if (len(employed(game, owner)) < min(2, MAX_EMPLOYED) and empire.credits >= p.spec.hiring_fee+40
                and game.empire_rates_for(owner)[0] >= p.spec.salary+2 and hire_error(game, p.id, owner) is None):
            hire(game, p.id, owner)
    for p in employed(game, owner):
        if p.system_id is not None:
            site = site_at(game, p.system_id) if p.spec.role == "explorer" else None
            if site and site.surveyed >= SURVEY_WORK and p.skill(site.spec.skill) < site.spec.difficulty:
                unassign(game, p.id, owner)
            else:
                continue
        for system in game.systems:
            choices = [(world.id if p.spec.role == "leader" else None) for world in system.worlds if world.owner == owner]
            for pid in choices:
                site = site_at(game, system.id)
                if p.spec.role == "explorer" and site and site.surveyed >= SURVEY_WORK and p.skill(site.spec.skill) < site.spec.difficulty:
                    continue
                if assignment_error(game, p.id, system.id, pid, owner) is None:
                    assign(game, p.id, system.id, pid, owner)
                    break
            if p.system_id is not None:
                break
    if game.turn < 8 or empire.credits < 100 or game.empire_rates_for(owner)[0] < 5:
        return
    # Recruitment must not consume the resources saved for a first expansion.
    colonies = [(system, world) for system in game.systems for world in system.worlds if world.owner == owner]
    if (len(colonies) < 2 and empire.race_id != "varkesh"
            and not any(ship.kind == "colony_ship" for ship in game.ships_owned_by(owner))):
        return
    if any("space_hub" in world.buildings or any(q.item_id == "space_hub" for q in world.construction_queue)
           for system in game.systems for world in system.worlds if world.owner == owner):
        return
    from .ai import queue_building
    from .buildings import facility_family
    for system, world in colonies:
        if (not world.construction_queue and world.free_slots >= 2
                and any(facility_family(b) == "factory" for b in world.buildings)
                and game.population_report(world).balance >= 0):
            if game.build_error(system.id, world.id, "space_hub", owner=owner) is None and queue_building(game, system, world, "space_hub", owner):
                return


def load(game, data, version):
    if version < 39:
        return
    from .model import _integer
    raw = data["specialists"]
    if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(SpecialistState)}:
        raise ValueError("Invalid specialist state")
    rows = raw["people"]
    if not isinstance(rows, list) or len(rows) != len(SPECIALISTS):
        raise ValueError("Invalid specialist roster")
    people, ids, assignments = [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {f.name for f in fields(Specialist)}:
            raise ValueError("Invalid specialist record")
        p = Specialist(**row)
        if not isinstance(p.id, str) or p.id not in SPECIALISTS or p.id in ids:
            raise ValueError("Duplicate or unknown specialist")
        ids.add(p.id)
        if any(o is not None and (not isinstance(o, str) or o not in game.owners) for o in (p.owner, p.visitor)) or (p.owner and p.visitor):
            raise ValueError("Invalid specialist owner")
        if not _integer(p.xp, 0, level_xp(MAX_LEVEL)) or not _integer(p.available_after, 0, game.turn+VISIT_INTERVAL):
            raise ValueError("Invalid experience or availability")
        if p.system_id is not None and not _integer(p.system_id, 0, len(game.systems)-1):
            raise ValueError("Invalid specialist system")
        if p.planet_id is not None and (p.system_id is None or not _integer(p.planet_id, 0, len(game.systems[p.system_id].worlds)-1)):
            raise ValueError("Invalid specialist colony")
        if p.visitor:
            if p.planet_id is None or not _integer(p.expires, 1, game.turn+VISIT_DURATION):
                raise ValueError("Invalid visitor")
        elif p.expires != 0 or type(p.expires) is not int:
            raise ValueError("Expiry without a visit")
        if not (p.owner or p.visitor) and (p.system_id is not None or p.planet_id is not None):
            raise ValueError("Unemployed specialist with an assignment")
        if p.owner and p.system_id is not None:
            if (p.spec.role == "leader") != (p.planet_id is not None):
                raise ValueError("Invalid specialist role assignment")
            key = (p.owner, p.spec.role, p.system_id, p.planet_id)
            if key in assignments:
                raise ValueError("Duplicate specialist assignment")
            assignments.add(key)
        people.append(p)
    for owner in game.owners:
        if sum(p.owner == owner for p in people) > MAX_EMPLOYED or sum(p.visitor == owner for p in people) > MAX_VISITORS:
            raise ValueError("Specialist capacity exceeded")
    site_rows = raw["sites"]
    if not isinstance(site_rows, list) or len(site_rows) > len(game.systems):
        raise ValueError("Invalid expedition sites")
    sites, systems = [], set()
    for row in site_rows:
        if not isinstance(row, dict) or set(row) != {f.name for f in fields(Site)}:
            raise ValueError("Invalid expedition site")
        s = Site(**row)
        if not _integer(s.system_id, 0, len(game.systems)-1) or s.system_id in systems or not isinstance(s.kind, str) or s.kind not in SITES:
            raise ValueError("Invalid or duplicate site")
        systems.add(s.system_id)
        if not _integer(s.surveyed, 0, SURVEY_WORK) or not _integer(s.progress, 0, s.spec.work) or (s.progress and s.surveyed < SURVEY_WORK):
            raise ValueError("Invalid expedition progress")
        if s.recovered_by is not None and (not isinstance(s.recovered_by, str) or s.recovered_by not in game.owners):
            raise ValueError("Invalid reward owner")
        if (s.progress == s.spec.work) != (s.recovered_by is not None):
            raise ValueError("Invalid expedition reward")
        known = s.known_by
        if not isinstance(known, list) or any(not isinstance(o, str) or o not in game.owners for o in known) or len(set(known)) != len(known) or not known:
            raise ValueError("Invalid expedition observers")
        if s.recovered_by and s.recovered_by not in known:
            raise ValueError("Reward without discovery")
        sites.append(s)
    for p in people:
        if p.owner and p.spec.role == "explorer" and p.system_id is not None and not any(s.system_id == p.system_id and p.owner in s.known_by for s in sites):
            raise ValueError("Assignment without expedition")
    schedule, welcomed = raw["next_visit"], raw["welcomed"]
    if not isinstance(schedule, dict) or any(o not in game.owners or not _integer(t, 1, game.turn+VISIT_INTERVAL) for o, t in schedule.items()):
        raise ValueError("Invalid visitor schedule")
    if not isinstance(welcomed, list) or any(not isinstance(o, str) or o not in game.owners for o in welcomed) or len(set(welcomed)) != len(welcomed) or set(welcomed) != set(schedule):
        raise ValueError("Invalid Hub introductions")
    event_rows = raw["events"]
    if not isinstance(event_rows, list) or len(event_rows) > 50000:
        raise ValueError("Invalid specialist dispatches")
    events = []
    for row in event_rows:
        if not isinstance(row, dict) or set(row) != {f.name for f in fields(SpecialistEvent)}:
            raise ValueError("Invalid specialist dispatch")
        e = SpecialistEvent(**row)
        if not _integer(e.turn, 1, game.turn) or not isinstance(e.owner, str) or e.owner not in game.owners or not isinstance(e.message, str) or not 1 <= len(e.message) <= 500 or not e.message.isprintable():
            raise ValueError("Invalid specialist dispatch")
        if events and events[-1].turn > e.turn:
            raise ValueError("Invalid specialist dispatch order")
        events.append(e)
    if not _integer(raw["news_read"], 0, len(events)):
        raise ValueError("Invalid specialist news marker")
    game.specialists = SpecialistState(people, sites, dict(schedule), list(welcomed), events, raw["news_read"])
