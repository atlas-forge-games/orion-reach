"""Read-only population figures and explanations of the existing growth rules."""

from dataclasses import dataclass

from . import economy, environments, population
from .buildings import BUILDINGS
from .habitat_modules import display_name
from .races import RACES
from .species import composition

POPULATION_RECT = (302, 58, 742, 26)


def millions(points):
    return points * 1000 / population.GROWTH_THRESHOLD


def growth_millions(report):
    # Swarm starvation precedes both growth and the capacity check in advance().
    if report.colonized and report.swarm and report.balance < 0:
        return -1000 if report.population > 1 else 0
    return millions(report.growth_rate)


def summary(planet, report=None):
    if report is None:
        return f"{planet.population} billion (growth unknown) / max unknown"
    return (f"{planet.population} billion ({growth_millions(report):+,g} mil / turn)"
            f" / {report.capacity} billion max")


@dataclass(frozen=True)
class PopulationInfo:
    title: str
    lines: tuple[str, ...]
    live: bool
    rate_millions: float | None = None


def describe(game, planet, *, live):
    title = "Population growth — " + planet.name
    if not live:
        lines = [f"Last observed population: {planet.population} billion.",
                 "Stored survey: current growth, food supply and population limit are unknown.",
                 "Revisit this system to see a current population calculation."]
        if planet.slaves:
            lines.append(f"Also last observed: {planet.slaves} billion slaves, counted separately.")
        return PopulationInfo(title, tuple(lines), False)

    report = game.population_report(planet)
    b = economy.local_bonuses(planet, game.bonuses_for(planet.owner or 'player'))
    rate = growth_millions(report)
    lines = [f"TOTAL GROWTH: {rate:+,g} million / turn",
             f"Population: {planet.population} billion / {report.capacity} billion maximum · {report.status}"]
    if planet.slaves:
        from .raiding import MORTALITY_CHANCE
        lines += [f"Native population is shown above; {planet.slaves} billion slaves are additional workers.",
                  f"Slaves consume food but do not grow; each slave unit has a {100/MORTALITY_CHANCE:g}% mortality chance per turn."]
    if not planet.colonized:
        lines.append("Establish a colony to begin population growth; this world has no inhabitants yet.")
        return PopulationInfo(title, tuple(lines), True, rate)
    elif report.swarm and report.balance < 0:
        lines.append("Swarm starvation: lose 1 billion per turn, down to a minimum of 1 billion; growth progress resets.")
    elif planet.population >= report.capacity:
        lines.append("Population limit reached: growth stops and accumulated growth progress resets.")
    else:
        turns = report.turns_to_growth
        forecast = f"next +1 billion in {turns} {'turn' if turns == 1 else 'turns'}" if turns else "growth is paused"
        lines.append(f"Growth progress: {millions(report.progress):g} / 1,000 million · {forecast}.")
        lines.append("Growth accumulates between turns; each full billion becomes one additional worker.")

    if report.assembly:
        from .research import gross_colony_yields
        industry = gross_colony_yields(planet, b)[0]
        lines += [f"Assembly: {b.get('assembly_percent', 0):g}% of {industry} gross industry; {report.assembly_industry} industry reserved.",
                  "The reservation rounds up, keeps at least 1 industry for construction and stops at capacity.",
                  f"Each reserved industry adds {millions(population.GROWTH_PER_INDUSTRY):g} million; base cap {millions(population.ASSEMBLY_GROWTH_LIMIT):g} million / turn.",
                  "Assembly replaces food-based growth; ordinary growth-speed traits do not multiply it."]
    elif report.passive_growth:
        lines += [f"Passive growth: {millions(report.passive_growth):g} million / turn before the environment and population limit.",
                  "Passive growth is independent of food surplus and industry; ordinary growth-speed traits do not multiply it."]
    else:
        base = max(0, min(report.growth_limit, population.GROWTH_PER_FOOD * report.balance))
        lush = b.get('lush_growth_percent', 0) if planet.biome in population.LUSH_BIOMES else 0
        lines += [f"Food surplus: {report.produced} produced − {report.consumed} consumed = {report.balance:+} / turn.",
                  f"Each surplus food adds {millions(population.GROWTH_PER_FOOD):g} million; base cap {millions(report.growth_limit):g} million / turn.",
                  f"Potential base growth: {millions(base):g} million / turn before traits, environment and capacity.",
                  f"Growth-speed traits: {b.get('growth_percent', 0):+g}% general; {lush:+g}% lush-world bonus → {report.growth_percent:g}% of base."]
        if report.balance <= 0 and not report.swarm:
            lines.append("Without a food surplus, food-based growth pauses; existing inhabitants and progress are retained.")

    lines.append(f"Before environment (after capacity check): {millions(report.base_growth_rate):g} million / turn.")
    if report.facility_growth:
        lines.append(f"Powered population facilities: +{report.facility_growth}% growth; applies to biological, assembly and passive growth before environment.")
    if report.adaptation:
        lines.append(f"Powered habitat facilities remove {report.adaptation}% of the environmental penalty (combined cap 80%).")
    if planet.habitat:
        lines.append("Habitat environment: 100%; the planet below does not affect growth.")
    else:
        lines.append(f"{planet.biome} environment: {report.environment_percent}% of growth, weighted by resident species.")
        for rid, count in sorted(composition(planet).items()):
            lines.append(f"  {RACES[rid].name}: {count} billion at {environments.PREFERENCES[rid][planet.biome]}% suitability.")
    if planet.habitat:
        lines.append(f"Population capacity: fixed at {report.capacity} billion aboard a mothership.")
    else:
        base_capacity = population.POPULATION_LIMITS[planet.size]
        gaia = population.GAIA_CAPACITY if planet.biome == 'Gaia' else 0
        lines.append(f"Capacity: {planet.size} {base_capacity} billion + {gaia} Gaia bonus; {b.get('capacity_percent', 0):+g}% traits and {b.get('facility_capacity', 0):+g}% powered facilities → {report.capacity} billion.")
    lines.append(f"Growth rounds down in {millions(1):g}-million steps after each multiplier; positive growth has a one-step minimum.")
    if b.get('food_use_percent', 0) <= -100:
        lines.append("Food is not required by this population.")
    else:
        active = economy.active_buildings(planet, b)
        natural = population.BASE_FOOD[planet.biome] + environments.native_food(planet)
        farms = sum(BUILDINGS[key].food for key in active)
        farmer_food = planet.farmers * population.farmer_output(planet, b)
        other = b.get('colony_food', 0) + (b.get('lush_food', 0) if planet.biome in population.LUSH_BIOMES else 0)
        lines += [f"Food sources before strain: {natural} natural + {farmer_food} farmers + {farms} facilities + {other} bonuses.",
                  f"Food use: {100+b.get('food_use_percent', 0):g}% × {planet.workforce} billion workers, rounded up = {report.consumed}.",
                  f"Food lost to local strain: {natural+farmer_food+farms+other-report.produced} / turn."]
        power = economy.energy_report(planet, b)
        inactive = [display_name(BUILDINGS[key], planet.habitat) for index, key in enumerate(planet.buildings)
                    if BUILDINGS[key].food and (index in planet.disabled_buildings or index in power.offline)]
        if inactive:
            lines.append("Disabled or unpowered food facilities: " + ', '.join(inactive) + ".")
        lines.append("Farmers, active farms, research and strain affect the surplus. Right-click Food for details.")
    lines.append("This rate uses current conditions. Completed buildings and new research affect later turns.")
    return PopulationInfo(title, tuple(lines), True, rate)


def draw(app):
    from .production_breakdown import draw as draw_breakdown
    info = app.dialog['population_info']
    draw_breakdown(app, data=info, caption=("CURRENT POPULATION · growth and limits" if info.live
                                          else "STORED SURVEY · last-observed population only"))
