"""Read-only explanations of the colony economy, using its live local bonuses."""
from dataclasses import dataclass
from . import economy, population, research, administration
from .buildings import BUILDINGS, MINERAL_FACTORS, facility_family, workforce_bonuses
from .habitat_modules import display_name

KINDS = ('credits', 'food', 'industry', 'research', 'mining', 'energy')
ROLES = dict(farmers='food', workers='industry', scientists='research', miners='mining')
TITLES = dict(credits='Credits', food='Food', industry='Industry', research='Research', mining='Mining / resources', energy='Energy')


@dataclass(frozen=True)
class Breakdown:
    title: str
    lines: tuple[str, ...]
    total: float


def describe(game, planet, kind):
    """Explain exactly the production value displayed in the planet overview."""
    if kind not in KINDS or not planet.colonized:
        raise ValueError('Choose a colonized planet and a valid output.')
    b = economy.local_bonuses(planet, game.bonuses_for(planet.owner))
    staff = workforce_bonuses(planet, b)
    active = economy.active_buildings(planet, b)
    lines = []
    def add(label, value):
        lines.append(f'{label}: {value:g}')
        return value
    def buildings(field, factor=1):
        total = 0
        for identifier in active:
            value = getattr(BUILDINGS[identifier], field)*factor
            if value:
                total += add(display_name(BUILDINGS[identifier], planet.habitat), value)
        return total
    def strain(value):
        r = game.strain_report(planet)
        lines.append(f'Strain: empire {r.empire:g}% + integration {r.integration:g}% + distance {r.distance:.2f}%')
        lines.append(f'Combined {r.total:.2f}% (cap {administration.MAX_STRAIN:g}%) × {administration.sensitivity(kind):g}% sensitivity')
        result = administration.reduced_output(value, b, kind)
        lines.append(f'After strain: floor({value:g} × {1-r.loss(kind)/100:.4f}) = {result:g}')
        return result
    if kind in ('industry', 'research', 'credits'):
        if kind == 'industry':
            raw = add(f'{planet.workers} workers × {research.WORKER_INDUSTRY:g} (minimum 1)', max(1, research.WORKER_INDUSTRY*planet.workers))
            raw += add(f'Worker facility bonus: floor({planet.workers} × {staff.industry:g})', int(planet.workers*staff.industry))
            raw += add('Colony bonuses (race, research, leader)', b.get('colony_industry', 0))
            percent = b.get('industry_percent', 0)+(b.get('harsh_industry_percent', 0) if planet.biome not in population.LUSH_BIOMES else 0)
            index = 0
        elif kind == 'research':
            raw = add(f'{planet.scientists} scientists × ({research.SCIENTIST_RESEARCH:g} base + {staff.research:g} facilities)', planet.scientists*(research.SCIENTIST_RESEARCH+staff.research))
            raw += add('Colony bonuses (race, research, leader)', b.get('colony_research', 0))
            percent, index = b.get('research_percent', 0), 2
        else:
            raw = add(f'{planet.workforce} population × {research.POPULATION_INCOME:g}', planet.workforce*research.POPULATION_INCOME)
            raw += add(f'Facility income: floor({planet.workforce} × {staff.income:g})', int(planet.workforce*staff.income))
            raw += add('Colony bonuses (race, research, leader)', b.get('colony_income', 0))
            raw += add('Population / terrain bonuses', (planet.workforce//2)*b.get('income_per_two_pop', 0)+(b.get('rough_income', 0) if planet.biome in ('Desert','Tundra') else 0))
            percent, index = b.get('income_percent', 0), 1
        for identifier in active:
            value = research.building_yields(BUILDINGS[identifier], planet.richness, b)[index]
            if value:
                raw += add(display_name(BUILDINGS[identifier], planet.habitat)+' (incl. upgrades)', value)
        scaled = research.scaled_output(raw, percent)
        lines.append(f'Subtotal {raw:g} × {1+percent/100:g} = {scaled:g} (whole-unit rounding)')
        adjusted = strain(scaled)
        if kind == 'industry':
            adjusted = max(1, adjusted)
            add('Gross industry (minimum 1)', adjusted)
            add('Reserved for population assembly', population.assembly_work(planet, adjusted, b))
            add('Reserved for megastructure construction', b.get('megastructure_work', 0))
            lines.append('Available = max(0, gross − assembly − megastructure work).')
        if kind == 'credits':
            add('Trade Goods income after strain', game.trade_goods_income(planet) if planet.trade_goods else 0)
            add('Subtract building / gate upkeep', research.colony_maintenance(planet, b))
            lines.append('Fleet upkeep and specialist salaries are empire costs.')
        total = game.planet_yields(planet)[index]
    elif kind == 'food':
        if b.get('food_use_percent', 0) <= -100:
            lines.append('This civilization does not require food; food production is 0.')
        else:
            raw = add('Habitat life support' if planet.habitat else 'Natural food ('+planet.biome+')', population.BASE_FOOD[planet.biome])
            raw += add('Colony / terrain bonuses', b.get('colony_food', 0)+(b.get('lush_food', 0) if planet.biome in population.LUSH_BIOMES else 0))
            raw += add(f'{planet.farmers} farmers × ({population.FARMER_OUTPUT[planet.biome]:g} base + {staff.food:g} facilities)', planet.farmers*population.farmer_output(planet,b))
            raw += buildings('food')
            add('Subtotal', raw)
            strain(raw)
        food = game.population_report(planet)
        total = food.produced
        add('Food consumed by population', food.consumed)
        add('Surplus / deficit', food.balance)
    elif kind == 'mining':
        factor = MINERAL_FACTORS[planet.richness]
        add('Mineral multiplier ('+planet.richness+')', factor)
        base = buildings('resources',factor)
        extra = sum(BUILDINGS[x].resources_per_miner for x in active)
        workers = add(f'{planet.miners} miners × ({economy.MINER_RESOURCES:g} base + {extra:g} facilities) × {factor:g}', planet.miners*economy.miner_output(planet,b))
        raw = add('Base extraction', economy.BASE_EXTRACTION)
        raw += add('Colony bonuses (race, research, leader)', b.get('colony_resources',0))
        raw += add('Mine research bonuses', sum(facility_family(x)=='mine' for x in active)*b.get('mine_resources',0))
        raw += add('Facilities + miners, rounded down together', int(base+workers))
        strain(raw)
        add('Subtract resources burned for energy', game.planet_energy(planet).fuel_used)
        total = game.planet_resources(planet)
    else:
        power = game.planet_energy(planet)
        if power.unlimited:
            lines.append('Completed Dyson Sphere: unlimited empire-wide energy.')
            total = float('inf')
        else:
            add('Base energy', economy.BASE_ENERGY)
            add('Colony energy bonuses', b.get('colony_energy',0))
            for i,identifier in enumerate(planet.buildings):
                spec = BUILDINGS[identifier]
                if i not in planet.disabled_buildings and spec.energy_output and not spec.energy_per_resource:
                    add(display_name(spec, planet.habitat),spec.energy_output)
            add('Actual backup generation',power.backup_generated)
            add('Resources burned by backup plants',power.fuel_used)
            total = power.generated
        add('Total demand',power.demand)
        add('Actually supplied to loads',power.used)
        lines.append('Energy is local and is not reduced by administrative strain.')
    unavailable = len(planet.buildings)-len(active)
    if unavailable:
        lines.append(f"{unavailable} disabled/unpowered {'module(s)' if planet.habitat else 'building(s)'} excluded from output; upkeep still applies.")
    lines.append('TOTAL '+TITLES[kind].upper()+f': {total:g} per turn')
    return Breakdown(TITLES[kind]+' — '+planet.name, tuple(lines), total)


def draw(app):
    import pygame as pg
    from .ui import panel, text, wrapped_lines, INK, MUTED, GOLD, PANEL
    data = app.dialog['output_breakdown']
    lines = [part for line in data.lines for part in wrapped_lines(line, 890, 16)]
    per_page = 18
    pages = max(1,(len(lines)+per_page-1)//per_page)
    page = min(app.dialog.get('info_page',0), pages-1)
    panel(app.canvas,(240,110,960,690),PANEL,GOLD)
    text(app.canvas,data.title,(272,137),28,INK,'title')
    caption = ('LIVE HABITAT CALCULATION · only operational modules contribute' if app.selected_habitat()
               else 'LIVE COLONY CALCULATION · only operational buildings contribute')
    text(app.canvas,caption,(272,184),12,MUTED)
    for i,line in enumerate(lines[page*per_page:(page+1)*per_page]):
        text(app.canvas,line,(272,217+i*26),16,GOLD if line.startswith('TOTAL ') else INK)
    text(app.canvas,f'{page+1} / {pages} · Right-click or Esc to close',(272,747),12,MUTED)
    if pages>1:
        app.button('dialog_output_previous','←',(720,731,64,40),lambda:app.dialog.update(info_page=page-1),enabled=page>0)
        app.button('dialog_output_next','→',(794,731,64,40),lambda:app.dialog.update(info_page=page+1),enabled=page+1<pages)
    app.button('dialog_cancel','Close',(920,731,240,40),app.cancel_dialog,'primary')
