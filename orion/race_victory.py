"""Civilization legacies: distinct goals, ordinary infrastructure, interruptible finales.

Read-only queries never advance a campaign or disclose hidden destinations.
"""
from dataclasses import dataclass, field
import math
from .frame_cache import cached_in_frame

FINAL_TURNS = 5
PROJECT_TECHS = 8
HARSH = frozenset(("Desert", "Tundra", "Barren", "Volcanic"))


@dataclass(frozen=True)
class Legacy:
    title: str
    building: str
    name: str
    description: str
    method: str
    ending: str


LEGACIES = {
    "terran": Legacy("The Galactic Charter", "charter_hall", "Charter Hall",
        "Unite independent civilizations through lasting friendship and peaceful ratification.",
        "Build halls in separate systems. Befriend up to two surviving diplomatic empires, remain at peace and honour your promises.",
        "Independent peoples ratify a common charter. Cooperation becomes the foundation of a new galactic order."),
    "kharuun": Legacy("The Eternal Work", "eternal_foundry", "Eternal Foundry",
        "Raise a crystalline monument through an interstellar industrial network.",
        "Each foundry needs an operating factory and mine, and two industrial workers. Each contributes up to 20 stored Resources per turn.",
        "The Eternal Work stands complete: a crystalline testament built to endure beyond the stars themselves."),
    "aelari": Legacy("The Living Archive", "living_archive", "Living Archive",
        "Preserve the galaxy's ecosystems and scientific knowledge.",
        "Personally scout-scan 40% of ordinary stars and up to six biomes. Build archives in separate systems and discover twelve technologies.",
        "The Living Archive preserves the galaxy's extraordinary diversity for civilizations yet to be born."),
    "lithar": Legacy("Awaken the Mountains", "planetary_mind", "Planetary Mind",
        "Bring the deep minds of hostile worlds into a shared consciousness.",
        "Build on Desert, Tundra, Barren or Volcanic worlds. Each mind needs twelve consecutive operating turns; interruptions reset its awakening.",
        "The mountains answer across the void. A constellation of planetary minds awakens."),
    "varkesh": Legacy("The Throne of Fear", "great_moot", "Great Moot",
        "Unite the war clans through warriors, reputation and trophies.",
        "Successful raids on different inhabited worlds earn trophies. With no other colonies left, fleet strength 120 enables a clan trial every six turns for 200 Resources.",
        "The Great Moot acknowledges one supreme warlord. The proudest clans bow before the Throne of Fear."),
    "xenonflora": Legacy("The Second Spring", "world_tree", "World Tree",
        "Grow a diverse interstellar biosphere around flourishing World Trees.",
        "Each tree needs six inhabitants, a food surplus of three and ten consecutive operating turns. Plant across different biomes and separate systems.",
        "The World Trees flower together. A living network carries a second spring from world to world."),
    "nexus": Legacy("The Final Computation", "processing_core", "Processing Core",
        "Dedicate machine population centres and knowledge to a final calculation.",
        "Each core needs six billion Nexus citizens and three scientists. Operating cores divert up to 20 RP each per turn before normal research.",
        "The distributed machine intellect resolves its final computation and opens a new horizon of existence."),
    "aetheri": Legacy("The Star That Woke", "resonance_choir", "Resonance Choir",
        "Unite different stellar resonances into a conscious star.",
        "Personally scout-scan three fifths of ordinary star systems. Establish choirs around up to three different stellar types and sustain the Convergence.",
        "The choirs converge. For the first time, a star looks back at the universe and knows itself."),
    "concord": Legacy("The Last Independent Thought", "overmind_node", "Overmind Node",
        "Assimilate population centres beneath the Dominion of One.",
        "Operating nodes convert 1 B local non-Dominion citizens per turn. Hold rival founding worlds, control half the galaxy's population and make 80% of your citizens Dominion.",
        "The Overmind synchronizes its conquered centres. Across its dominion, the last independent thought falls silent."),
    "serevan": Legacy("Many Peoples, One Future", "union_forum", "Union Forum",
        "Build a voluntary union whose member cultures survive and prosper together.",
        "Friendships allow forums to welcome 1 B settlers every three turns for 25 CR, up to 2 B per culture. Voluntary accessions qualify too. Preserve peace and promises.",
        "Many peoples retain their identities while choosing one shared future. The constitutional convention succeeds."),
    "skirr": Legacy("The Great Hatching", "queen_nest", "Queen Nest",
        "Spread mature queen broods and trigger a synchronized galactic hatching.",
        "Each nest needs eight Skirr inhabitants, a food surplus of two and eight consecutive operating turns. Power loss, starvation or blockade resets maturity.",
        "The queen broods hatch in unison. Countless swarms spill into the galaxy to replace every competing form of life."),
    "remnant": Legacy("The Throne Beyond Memory", "memory_throne", "Memory Throne",
        "Recover ancient sites and reconstruct a vanished civilization's memory.",
        "Personally scout-scan tomb systems or ancient archives. Operating thrones dedicate up to 20 RP each per turn to reconstruction; targets adapt when ruins are absent.",
        "Scattered memories become a shared past. The First Throne is restored and the forgotten civilization remembers its name."),
}
PROJECT_RACES = {spec.building: rid for rid, spec in LEGACIES.items()}


@dataclass
class Site:
    owner: str
    system_id: int
    planet_id: int
    built: int
    age: int = 0


@dataclass
class LegacyState:
    last_turn: int = 0
    sites: list[Site] = field(default_factory=list)
    final_turns: dict[str, int] = field(default_factory=dict)
    investments: dict[str, int] = field(default_factory=dict)
    trophies: dict[str, list[str]] = field(default_factory=dict)
    willing: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Requirement:
    label: str
    current: int
    target: int

    @property
    def complete(self):
        return self.current >= self.target


def race(game, owner):
    return game._empire(owner).race_id


def spec_for(game, owner="player"):
    return LEGACIES.get(race(game, owner))


def scans(game, owner):
    e = game.exploration
    return set(e.scanned_player if owner == "player" else e.scanned_rival if owner == "rival" else e.scanned_others.get(owner, []))


def ordinary(game):
    from .black_holes import KIND
    return [s for s in game.systems if s.kind != KIND]


def suitable(game, owner, planet):
    if planet.habitat:
        return False
    return planet.biome in HARSH if race(game, owner) == "lithar" else planet.biome != "Gas Giant"


@cached_in_frame
def scale(game, owner):
    if race(game, owner) == "varkesh":
        return 1
    target = {"Compact": 2, "Standard": 3, "Expansive": 5}[game.galaxy_size]
    target += race(game, owner) == "skirr"
    available = sum(any(suitable(game, owner, p) for p in s.worlds) for s in ordinary(game))
    return max(1, min(target, available))


def build_error(game, sid, planet, identifier, owner):
    if identifier not in PROJECT_RACES:
        return None
    if "race" not in game.victory_conditions:
        return "Race-specific victory is disabled for this campaign."
    if PROJECT_RACES[identifier] != race(game, owner):
        return "This legacy belongs to another civilization."
    if len(game.research_state(owner).completed) < PROJECT_TECHS:
        return f"Discover {PROJECT_TECHS} technologies to unlock your legacy installation."
    if not suitable(game, owner, planet):
        return "Planetary Minds need a Desert, Tundra, Barren or Volcanic world." if race(game, owner) == "lithar" else "Legacy installations require a planet."
    if race(game, owner) == "varkesh":
        from .raiding import home_location
        if (sid, planet.id) != home_location(game, owner):
            return "The Great Moot must stand on your original homeworld."
    return None


def strip(planet):
    """A conquered installation or queued legacy never changes allegiance."""
    keep = [i for i, b in enumerate(planet.buildings) if b not in PROJECT_RACES]
    planet.disabled_buildings = [j for j, i in enumerate(keep) if i in planet.disabled_buildings]
    planet.buildings = [planet.buildings[i] for i in keep]
    planet.construction_queue[:] = [q for q in planet.construction_queue if q.item_id not in PROJECT_RACES]


def commission(game, system, planet, identifier):
    if identifier not in PROJECT_RACES:
        return
    game.legacy.sites = [s for s in game.legacy.sites if (s.system_id, s.planet_id) != (system.id, planet.id)]
    game.legacy.sites.append(Site(planet.owner, system.id, planet.id, game.turn+1))


def normalize(game):
    retained = []
    for s in game.legacy.sites:
        p = game.planet_at(s.system_id, s.planet_id)
        spec = spec_for(game, s.owner)
        if p.owner != s.owner:
            strip(p)
        elif spec and spec.building in p.buildings:
            retained.append(s)
    game.legacy.sites = retained


def sites(game, owner):
    spec = spec_for(game, owner)
    return [(s, game.planet_at(s.system_id, s.planet_id)) for s in game.legacy.sites
            if s.owner == owner and spec and game.planet_at(s.system_id, s.planet_id).owner == owner
            and spec.building in game.planet_at(s.system_id, s.planet_id).buildings]


def site_error(game, s, p):
    owner, rid = s.owner, race(game, s.owner)
    spec = LEGACIES[rid]
    if not game.building_operational(p, spec.building):
        return "No power or manually disabled"
    if p.bombarded_turn and p.bombarded_turn >= game.turn-1:
        return "Recovering from bombardment"
    if any(ship.owner != owner and game.diplomacy_between(owner, ship.owner).at_war
           and game.military_strength(ship) > 0 for ship in game.ships if ship.system_id == s.system_id and not ship.in_transit and ship.owner in game.owners):
        return "Hostile blockade"
    pop = 8 if rid == "skirr" else 6 if rid in ("nexus", "xenonflora", "concord") else 4
    if p.population < pop:
        return f"Needs {pop} B citizens"
    from .species import composition
    if rid in ("nexus", "skirr") and composition(p, rid).get(rid, 0) < pop:
        return f"Needs {pop} B {rid.title()} citizens"
    surplus = 3 if rid == "xenonflora" else 2 if rid == "skirr" else 0
    if game.population_report(p).balance < surplus:
        return f"Needs food balance +{surplus}"
    if rid == "nexus" and p.scientists < 3:
        return "Needs three scientists"
    if rid == "kharuun":
        from .buildings import FACILITY_FAMILIES
        if p.workers < 2 or not all(any(game.building_operational(p, b) for b in FACILITY_FAMILIES[f]) for f in ("factory", "mine")):
            return "Needs operating factory, mine and two workers"
    return None


def operating(game, owner):
    return [(s, p) for s, p in sites(game, owner) if site_error(game, s, p) is None]


def mature(game, owner):
    age = {"lithar": 12, "xenonflora": 10, "skirr": 8}.get(race(game, owner), 0)
    return [(s, p) for s, p in operating(game, owner) if s.age >= age]


def population_counts(game, owner):
    from .species import composition
    result = {}
    for _, p in game.settlements(owner):
        for rid, n in composition(p, race(game, owner)).items():
            result[rid] = result.get(rid, 0)+n
    return result


def diplomatic_partners(game, owner):
    return [o for o in game.owners if o != owner and game.settlements(o) and race(game, o) not in ("concord", "skirr")]


def founding_worlds(game, owner):
    from .raiding import home_location
    result = []
    for other in game.owners:
        if other == owner or race(game, other) == "wanderers":
            continue
        sid, pid = home_location(game, other)
        p = game.planet_at(sid, pid)
        if p.colonized:
            result.append(p)
    return result


def peaceful_requirements(game, owner):
    others = [o for o in game.owners if o != owner and game.settlements(o)]
    peaceful = sum(not game.diplomacy_between(owner, o).at_war for o in others)
    breach = max((game.diplomacy_between(owner, o).last_breach.get(owner, -10) for o in game.owners if o != owner), default=-10)
    return [Requirement("Peace with surviving empires", peaceful, len(others)),
            Requirement("Turns without broken promises", min(10, game.turn-breach), 10)]


@cached_in_frame
def requirements(game, owner="player"):
    rid = race(game, owner)
    if rid not in LEGACIES:
        return ()
    ready = mature(game, owner)
    target = scale(game, owner)
    rows = [Requirement("Operating systems" if rid not in ("lithar", "xenonflora", "skirr") else "Mature installation systems", len({s.system_id for s, p in ready}), target)]
    allstars, surveyed = ordinary(game), scans(game, owner)
    if rid == "terran":
        partners = diplomatic_partners(game, owner)
        rows += [Requirement("Independent friendship treaties", sum(game.diplomacy_between(owner, o).friendship_active for o in partners), min(2, len(partners)))] + peaceful_requirements(game, owner)
    elif rid == "kharuun":
        rows += [Requirement("Resources committed to the monument", game.legacy.investments.get(owner, 0), 600*target)]
    elif rid == "aelari":
        available = {p.biome for s in allstars for p in s.worlds}
        seen = {p.biome for s in allstars if s.id in surveyed for p in s.worlds}
        rows += [Requirement("Personally surveyed star systems", len({s.id for s in allstars}&surveyed), math.ceil(.4*len(allstars))),
                 Requirement("Recorded planetary biomes", len(seen), min(6, len(available))),
                 Requirement("Discovered technologies", len(game.research_state(owner).completed), 12)]
    elif rid in ("lithar", "xenonflora"):
        available = {p.biome for s in allstars for p in s.worlds if suitable(game, owner, p)}
        rows += [Requirement("Different mature world biomes", len({p.biome for s, p in ready}), min(3, len(available)))]
    elif rid == "varkesh":
        from .raiding import homeworld
        home = homeworld(game, owner)
        rows += [Requirement("Unique raid trophies / clan trials", len(game.legacy.trophies.get(owner, [])), 3),
                 Requirement("Surviving fleet combat strength", int(sum(game.military_strength(s) for s in game.ships_owned_by(owner))), 120),
                 Requirement("Homeworld garrison", home.garrison if home else 0, 8)]
    elif rid in ("nexus", "remnant"):
        rows += [Requirement("Research dedicated to the legacy", game.legacy.investments.get(owner, 0), 500*target)]
        if rid == "remnant":
            from .exploration import discovery_at
            ancient = {s.id for s in allstars if discovery_at(game, s.id) == "ancient_archive"}
            ancient |= {t.system_id for t in game.tomb_worlds}
            rows += [Requirement("Personally surveyed ancient sites", len(ancient&surveyed), min(3, len(ancient)))]
    elif rid == "aetheri":
        rows += [Requirement("Personally surveyed star systems", len({s.id for s in allstars}&surveyed), math.ceil(.6*len(allstars))),
                 Requirement("Different stellar resonances", len({game.systems[s.system_id].kind for s, p in ready}), min(3, len({s.kind for s in allstars if any(suitable(game, owner, p) for p in s.worlds)})))]
    elif rid == "concord":
        worlds = founding_worlds(game, owner)
        counts = population_counts(game, owner)
        own = sum(counts.values())
        total = sum(p.population for _, p in game.settlements())
        rows += [Requirement("Held rival founding worlds", sum(p.owner == owner for p in worlds), min(2, len(worlds))),
                 Requirement("Share of galactic civilian population (%)", 100*own//max(1, total), 50),
                 Requirement("Dominion citizens in your empire (%)", 100*counts.get("concord", 0)//max(1, own), 80)]
    elif rid == "serevan":
        willing = set(game.legacy.willing.get(owner, [])) | {"serevan"}
        counts = population_counts(game, owner)
        available = {race(game, o) for o in diplomatic_partners(game, owner)} | {"serevan"} | (willing&counts.keys())
        rows += [Requirement("Willing cultures with at least 2 B citizens", sum(counts.get(r, 0) >= 2 for r in willing), min(3, len(available)))] + peaceful_requirements(game, owner)
    elif rid == "skirr":
        from .species import composition
        rows += [Requirement("Skirr citizens in mature nests (B)", sum(composition(p, rid).get(rid, 0) for s, p in ready), 8*target)]
    return tuple(rows)


def fraction(game, owner):
    rows = requirements(game, owner)
    if not rows:
        return 0
    base = sum(min(1, r.current/max(1, r.target)) if r.target else 1 for r in rows)/len(rows)
    final = game.legacy.final_turns.get(owner, 0)
    return min(99, int(base*80+min(FINAL_TURNS, final)*20/FINAL_TURNS)) if final < FINAL_TURNS or not all(r.complete for r in rows) else 100


def research_reservation(game, owner="player"):
    if "race" not in game.victory_conditions or race(game, owner) not in ("nexus", "remnant"):
        return 0
    return min(max(0, 500*scale(game, owner)-game.legacy.investments.get(owner, 0)), 20*len(operating(game, owner)))


def record_raid(game, owner, sid, pid):
    if race(game, owner) == "varkesh":
        records = game.legacy.trophies.setdefault(owner, [])
        token = f"world:{sid}:{pid}"
        if token not in records:
            records.append(token)


def record_accession(game, owner, planet):
    from .species import composition
    records = game.legacy.willing.setdefault(owner, [])
    for rid in composition(planet, race(game, owner)):
        if rid not in records:
            records.append(rid)


def immigrate(game, owner, ready):
    from .species import composition
    if game.turn % 3 or not ready:
        return
    empire = game._empire(owner)
    counts = population_counts(game, owner)
    for other in diplomatic_partners(game, owner):
        rid = race(game, other)
        if counts.get(rid, 0) >= 2 or empire.credits < 25 or not game.diplomacy_between(owner, other).friendship_active:
            continue
        source = next((p for _, p in game.settlements(other) if p.population >= 4 and composition(p, rid).get(rid, 0)), None)
        destination = next((p for s, p in ready if p.population < game.population_report(p).capacity), None)
        if source is None or destination is None:
            continue
        source.species = composition(source, rid)
        destination.species = composition(destination, "serevan")
        source.species[rid] -= 1
        if not source.species[rid]:
            del source.species[rid]
        source.population -= 1
        # Preserve workforce validity after the voluntary departure.
        while source.farmers+source.scientists+source.miners > source.workforce:
            for attr in ("miners", "scientists", "farmers"):
                if getattr(source, attr):
                    setattr(source, attr, getattr(source, attr)-1)
                    break
        destination.population += 1
        destination.species[rid] = destination.species.get(rid, 0)+1
        empire.credits -= 25
        counts[rid] = counts.get(rid, 0)+1
        willing = game.legacy.willing.setdefault(owner, [])
        if rid not in willing:
            willing.append(rid)


def advance(game, alerts):
    if game.legacy.last_turn >= game.turn:
        return
    game.legacy.last_turn = game.turn
    normalize(game)
    if "race" not in game.victory_conditions:
        return
    for owner in game.owners:
        spec = spec_for(game, owner)
        if spec is None:
            continue
        rid = race(game, owner)
        for s, p in sites(game, owner):
            s.age = min(1_000_000, s.age+1) if s.built < game.turn and site_error(game, s, p) is None else 0
        ready = operating(game, owner)
        empire = game._empire(owner)
        if rid in ("kharuun", "nexus", "remnant"):
            total = (600 if rid == "kharuun" else 500)*scale(game, owner)
            attribute = "resources" if rid == "kharuun" else "research"
            paid = min(max(0, total-game.legacy.investments.get(owner, 0)), 20*len(ready), max(0, getattr(empire, attribute)))
            setattr(empire, attribute, getattr(empire, attribute)-paid)
            game.legacy.investments[owner] = game.legacy.investments.get(owner, 0)+paid
        if rid == "concord":
            from .species import composition
            for s, p in ready:
                p.species = composition(p, rid)
                others = [r for r in p.species if r != rid]
                if others:
                    original = max(others, key=lambda r: (p.species[r], r))
                    p.species[original] -= 1
                    if not p.species[original]:
                        del p.species[original]
                    p.species[rid] = p.species.get(rid, 0)+1
        if rid == "serevan":
            immigrate(game, owner, ready)
        if rid == "varkesh" and ready and game.turn % 6 == 0 and not any(o != owner and game.settlements(o) for o in game.owners):
            trophies = game.legacy.trophies.setdefault(owner, [])
            if len(trophies) < 3 and empire.resources >= 200 and sum(game.military_strength(s) for s in game.ships_owned_by(owner)) >= 120:
                empire.resources -= 200
                trophies.append(f"trial:{game.turn}")
        previous = game.legacy.final_turns.get(owner, 0)
        complete = bool(game.settlements(owner)) and all(r.complete for r in requirements(game, owner))
        current = min(FINAL_TURNS, previous+1) if complete else 0
        game.legacy.final_turns[owner] = current
        if current == 1 or current == FINAL_TURNS-1 or previous and not current:
            from .first_contact import known
            message = f"{game.empire_name_for(owner)}: {spec.title} " + ("finale interrupted." if not current else f"finale {current}/{FINAL_TURNS} turns.")
            if game.is_observer or owner == "player" or known(game, "player", owner):
                alerts.append(message)
            if owner != "player":
                game.rival_event(message, owner=owner, turn=game.turn)


def migrate_ascension(game, data, version):
    """Refund retired projects in live campaigns; retain completed historical results."""
    if version >= 51 or (isinstance(data.get("result"), dict) and data["result"].get("condition") == "science"):
        return
    from .production import ASCENSION_GATE
    from .research import TECHNOLOGIES
    conditions = set(game.victory_conditions)
    if "science" in conditions:
        conditions.remove("science")
        conditions.add("race")
    from .victory import CONDITIONS
    game.victory_conditions = tuple(c for c in CONDITIONS if c in conditions)
    for owner in game.owners:
        empire, state = game._empire(owner), game.research_state(owner)
        if state.active == "ascension_theory":
            empire.research += state.progress
            state.active, state.progress, state.legacy_active = None, 0, False
        if "ascension_theory" in state.completed:
            index = state.completed.index("ascension_theory")
            state.completed.remove("ascension_theory")
            if index < state.legacy_count:
                state.legacy_count -= 1
            state.recovered = [r for r in state.recovered if r != "ascension_theory"]
            empire.research += TECHNOLOGIES["ascension_theory"].cost
        for _, p in game.settlements(owner):
            if p.ascension_gate:
                empire.resources += ASCENSION_GATE.resource_cost
            for q in p.construction_queue:
                if q.item_id == ASCENSION_GATE.id:
                    empire.resources += q.paid_resources
                    empire.credits += q.paid_credits
            p.ascension_gate, p.gate_charge = False, 0
            p.construction_queue[:] = [q for q in p.construction_queue if q.item_id != ASCENSION_GATE.id]
    for survey in game.exploration.surveys:
        for p in survey.worlds:
            p["ascension_gate"], p["gate_charge"] = False, 0
            p["construction_queue"] = [q for q in p.get("construction_queue", []) if q["item_id"] != ASCENSION_GATE.id]


def load(game, data, version):
    if version < 51:
        game.legacy = LegacyState(last_turn=game.turn)
        migrate_ascension(game, data, version)
        return
    raw = data["legacy"]
    if not isinstance(raw, dict) or set(raw) != set(LegacyState.__dataclass_fields__):
        raise ValueError("Invalid civilization legacy state")
    if type(raw["last_turn"]) is not int or not 0 <= raw["last_turn"] <= game.turn:
        raise ValueError("Invalid legacy turn")
    state = LegacyState(last_turn=raw["last_turn"])
    for key, maximum, races in (("final_turns", FINAL_TURNS, LEGACIES), ("investments", 1_000_000, ("kharuun", "nexus", "remnant"))):
        values = raw[key]
        if not isinstance(values, dict) or any(o not in game.owners or race(game, o) not in races or type(v) is not int or not 0 <= v <= maximum for o, v in values.items()):
            raise ValueError("Invalid legacy progress")
        setattr(state, key, values.copy())
    from .races import RACES
    for key, rid in (("trophies", "varkesh"), ("willing", "serevan")):
        values = raw[key]
        if not isinstance(values, dict):
            raise ValueError("Invalid legacy history")
        for o, tokens in values.items():
            if o not in game.owners or race(game, o) != rid or not isinstance(tokens, list) or len(tokens) > 2000 or any(not isinstance(t, str) or len(t) > 80 for t in tokens) or len(set(tokens)) != len(tokens):
                raise ValueError("Invalid legacy records")
            if key == "willing" and any(t not in RACES for t in tokens):
                raise ValueError("Invalid member culture")
            if key == "trophies":
                for token in tokens:
                    parts = token.split(":")
                    if parts[0] == "trial" and len(parts) == 2 and parts[1].isascii() and parts[1].isdigit() and 1 <= int(parts[1]) <= game.turn:
                        continue
                    if parts[0] != "world" or len(parts) != 3 or not all(p.isascii() and p.isdigit() for p in parts[1:]):
                        raise ValueError("Invalid raid trophy")
                    sid, pid = map(int, parts[1:])
                    if not 0 <= sid < len(game.systems) or not 0 <= pid < len(game.systems[sid].worlds):
                        raise ValueError("Invalid trophy world")
        setattr(state, key, {o: v.copy() for o, v in values.items()})
    rows, occupied = raw["sites"], set()
    if not isinstance(rows, list) or len(rows) > sum(len(s.worlds) for s in game.systems):
        raise ValueError("Invalid legacy sites")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(Site.__dataclass_fields__):
            raise ValueError("Invalid legacy site record")
        s = Site(**row)
        if (s.owner not in game.owners or race(game, s.owner) not in LEGACIES
                or type(s.system_id) is not int or not 0 <= s.system_id < len(game.systems)
                or type(s.planet_id) is not int or not 0 <= s.planet_id < len(game.systems[s.system_id].worlds)
                or type(s.built) is not int or not 1 <= s.built <= game.turn
                or type(s.age) is not int or not 0 <= s.age <= game.turn-s.built):
            raise ValueError("Invalid legacy site values")
        p = game.planet_at(s.system_id, s.planet_id)
        key = s.system_id, s.planet_id
        if key in occupied or p.owner != s.owner or LEGACIES[race(game, s.owner)].building not in p.buildings or not suitable(game, s.owner, p):
            raise ValueError("Legacy site does not match the colony")
        occupied.add(key)
        state.sites.append(s)
    for system, p in game.settlements():
        for b in p.buildings+[q.item_id for q in p.construction_queue]:
            if b in PROJECT_RACES and (PROJECT_RACES[b] != race(game, p.owner) or not suitable(game, p.owner, p) or "race" not in game.victory_conditions):
                raise ValueError("Legacy installation belongs to another race or invalid world")
        if any(b in PROJECT_RACES for b in p.buildings) and (system.id, p.id) not in occupied:
            raise ValueError("Unregistered legacy installation")
    game.legacy = state


def ai_orders(game, owner):
    """Commission a useful site through normal build, funding and power rules."""
    if "race" not in game.victory_conditions or not spec_for(game, owner) or len(game.research_state(owner).completed) < PROJECT_TECHS:
        return
    from . import ai
    spec, rid = spec_for(game, owner), race(game, owner)
    colonies = game.settlements(owner)
    planned = [(s, p) for s, p in colonies if spec.building in p.buildings or any(q.item_id == spec.building for q in p.construction_queue)]
    systems = {s.id for s, p in planned}
    biomes = {p.biome for s, p in planned}
    kinds = {s.kind for s, p in planned}
    candidates = [(s, p) for s, p in colonies if s.id not in systems and suitable(game, owner, p) and not p.construction_queue
                  and (len(systems) < scale(game, owner) or rid in ("lithar", "xenonflora") and p.biome not in biomes and len(biomes) < 3
                       or rid == "aetheri" and s.kind not in kinds and len(kinds) < 3)]
    candidates.sort(key=lambda row: (row[1].biome in biomes if rid in ("lithar", "xenonflora") else row[0].kind in kinds if rid == "aetheri" else False, -row[1].population, row[0].id))
    for system, p in candidates:
        if build_error(game, system.id, p, spec.building, owner):
            continue
        if not p.free_slots:
            protected = {"trade_center", "hydroponic_farm", "barracks", "factory", "mine", *PROJECT_RACES}
            disposable = [i for i, b in enumerate(p.buildings) if b not in protected and not ai.BUILDINGS[b].energy_output]
            if disposable:
                game.demolish_building(system.id, p.id, disposable[-1], owner=owner)
        if rid == "kharuun":
            missing = next((b for b in ("factory", "mine") if b not in p.buildings), None)
            if missing:
                ai.queue_building(game, system, p, missing, owner)
                return
        if ai.queue_building(game, system, p, spec.building, owner):
            return
