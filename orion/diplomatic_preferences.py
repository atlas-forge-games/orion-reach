"""Public racial priorities and assessments made from an empire's own intelligence."""
from dataclasses import dataclass
from . import first_contact, sensors
from .production import distance_ly


@dataclass(frozen=True)
class Priorities:
    summary: str
    interest: str
    frontier: int = 2
    goal: int = 2
    pragmatism: int = 5
    loyalty: int = 2
    memory: int = 2
    resolve: int = 0
    trade: int = 2
    research: int = 2
    friendship: int = 2


PROFILES = {
    'terran': Priorities('Flexible alliances around shared goals.', 'security', pragmatism=12),
    'kharuun': Priorities('Profitable trade and economic influence.', 'commerce', trade=5, resolve=-5, goal=3),
    'aelari': Priorities('Research partners and shared discoveries.', 'science', research=5, friendship=3, goal=4),
    'lithar': Priorities('Lasting alliances; broken promises are never forgotten.', 'security',
                        frontier=3, loyalty=5, memory=8, resolve=10, friendship=4),
    'varkesh': Priorities('Intimidation, tribute and opportunities for conquest.', 'power',
                         pragmatism=10, loyalty=0, memory=1, resolve=15, friendship=0),
    'wanderers': Priorities('Safe routes, secure anchorages and dependable partners.', 'routes',
                           frontier=3, loyalty=1, trade=3, friendship=4),
    'xenonflora': Priorities('Protect ecosystems and living worlds.', 'ecology', goal=5, memory=5, friendship=3),
    'nexus': Priorities('Industrial security and practical research cooperation.', 'industry',
                        goal=4, pragmatism=10, loyalty=0, memory=1, research=4),
    'aetheri': Priorities('Protect access to energy-rich stars and energy sources.', 'energy', goal=5, research=3),
    'concord': Priorities('Cooperation across species and protection of peaceful partners.', 'cooperation',
                         pragmatism=8, loyalty=3, friendship=5),
    'remnant': Priorities('Ancient sites and historical claims.', 'heritage', goal=5, memory=5, resolve=10),
}
INTERESTS = ('security', 'commerce', 'science', 'power', 'routes', 'ecology', 'industry', 'energy', 'cooperation', 'heritage')


def profile(game, owner):
    return PROFILES[game._empire(owner).race_id]


@dataclass(frozen=True)
class Assessment:
    score: int
    reasons: tuple[tuple[str, int], ...]


def known_worlds(game, observer, target):
    return [(s, p) for actual in game.systems if (s := game.known_system(actual.id, observer))
            for p in s.worlds if p.owner == target]


def ship_power(game, ship):
    damage = game.military_strength(ship)
    return (damage+ship.max_hull*.3)*ship.hull/max(1, ship.max_hull) if damage else 0


def observed_forces(game, observer, target):
    """Exact visible ships plus conservative estimates for unidentified scanner fleets.

    Scanner contacts never reveal hidden equipment, hit points or destinations.
    """
    from .navigation import position
    from .production import SHIP_TYPES
    visible = [s for s in game.visible_ships(observer) if s.owner == target]
    ids = {s.id for s in visible}
    rows = [(ship_power(game, s), *position(game, s)) for s in visible if ship_power(game, s)]
    contacts = [c for c in sensors.contacts(game, observer) if c.active and c.owner == target and c.anchor not in ids]
    for contact in contacts:
        strength = 8*(contact.count or 1)
        if contact.level >= 3:
            strength = 0
            for entry in contact.classes:
                name, count = entry.rsplit(' × ', 1)
                spec = SHIP_TYPES.get(name.lower().replace(' ', '_'))
                if spec and (spec.damage or spec.drone_bays):
                    strength += int(count)*(spec.damage+.3*spec.hull+spec.drone_bays*10)
        if strength:
            rows.append((strength, contact.x, contact.y))
    return rows


def observed_power(game, observer, target):
    return sum(power for power, _, _ in observed_forces(game, observer, target))


def fear(game, observer, target):
    """How afraid observer is of target, independent of affinity."""
    if not first_contact.known(game, observer, target) or not game.colony_systems(observer):
        return Assessment(0, (('No confirmed threat', 0),))
    own = sum(ship_power(game, s) for s in game.ships_owned_by(observer))
    own += 20*sum('missile_base' in p.buildings for s in game.colony_systems(observer) for p in s.worlds if p.owner == observer)
    forces = observed_forces(game, observer, target)
    enemy = sum(power for power, _, _ in forces)
    ratio = enemy/max(10, own)
    superiority = round(90*max(0, (ratio-1)/(ratio+1)))
    homes = game.colony_systems(observer)
    distances = [(power, min(sensors.distance(x, y, s) for s in homes)) for power, x, y in forces]
    nearest = min((distance for _, distance in distances), default=1000)
    # Distant strength is less coercive; fleets already nearby prove their reach.
    reach = sum(power*max(0., min(1., (45-distance)/30)) for power, distance in distances)/max(1, enemy)
    proximity = 15 if nearest <= 12 and enemy else 0
    support = 0
    for ally in game.owners:
        if ally in (observer, target) or not game.colony_systems(ally) or not first_contact.known(game, observer, ally):
            continue
        state = game.diplomacy_between(observer, ally)
        if state.friendship_active or state.coalition_target == target:
            support += 8+min(12, round(observed_power(game, observer, ally)/10))
    state = game.diplomacy_between(observer, target)
    last = state.last_defeat.get(observer, 0)
    setback = max(0, 15-(game.turn-last)) if last else 0
    resolve = profile(game, observer).resolve
    reasons = (('Observed military superiority', round(superiority*reach)), ('Fleets near your colonies', proximity),
               ('Recent military defeat', setback), ('Allied protection', -min(35, support)), ('Racial resolve', -resolve))
    value = max(0, min(100, sum(v for _, v in reasons))) if enemy else 0
    return Assessment(value, reasons)


def threat(game, observer, target):
    if not first_contact.known(game, observer, target):
        return Assessment(0, (('No contact', 0),))
    nature = profile(game, observer)
    homes = game.colony_systems(observer)
    worlds = known_worlds(game, observer, target)
    nearby = [(s, p) for s, p in worlds if any(distance_ly(s, h) <= 30 for h in homes)]
    state = game.diplomacy_between(observer, target)
    war = 40 if state.at_war else 0
    pressure = min(30, len({s.id for s, _ in nearby})*5*nature.frontier)
    interest = nature.interest
    if interest == 'ecology':
        contested = sum(p.biome in ('Terran', 'Ocean', 'Gaia') for _, p in nearby)
    elif interest == 'energy':
        contested = sum(s.kind in ('Blue star', 'White star') for s, _ in nearby)
    elif interest == 'industry':
        contested = sum(p.richness in ('Rich', 'Ultra-rich') or 'factory' in p.buildings for _, p in nearby)
    elif interest == 'science':
        contested = sum('research_lab' in p.buildings or p.ascension_gate for _, p in nearby)
    elif interest == 'commerce':
        contested = sum('trade_center' in p.buildings or p.population >= 5 for _, p in nearby)
    elif interest == 'heritage':
        # Only public awakenings reported to this observer; dormant tombs remain secret.
        sites = {t.system_id for t in game.tomb_worlds if t.awakened_turn and observer in t.notified_owners}
        sites.update(s.system_id for s in game.specialists.sites if observer in s.known_by and s.spec.skill == 'archaeology')
        contested = sum(s.id in sites for s, _ in nearby)
    elif interest == 'cooperation':
        contested = sum(1 for ally in game.owners if ally not in (observer, target)
                        and first_contact.known(game, observer, ally)
                        and game.diplomacy_between(observer, ally).friendship_active
                        and first_contact.known(game, ally, target)
                        and game.diplomacy_between(ally, target).at_war)
    else:
        contested = len({s.id for s, _ in nearby})
    goals = min(25, contested*3*nature.goal)
    intimidation = min(25, state.coercion.get(target, 0)*10)
    danger = fear(game, observer, target).score//4
    race = 25 if any(p.ascension_gate for _, p in worlds) and 'ascension' in game.victory_conditions else 0
    reasons = (('Shared war', war), ('Nearby territorial pressure', pressure),
               (f'Competing interests: {interest}', goals), ('Intimidation remembered', intimidation),
               ('Military danger', danger), ('Known ascension project', race))
    return Assessment(min(100, sum(value for _, value in reasons)), reasons)
