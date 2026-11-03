"""Readable, responsive empire economy and sortable colony directory."""

from dataclasses import dataclass
import math
import pygame as pg

from .habitat_modules import display_name
from .colony_view import turn_label
from .empire import FILTERS, colony_rows, summarize_empire
from .planet_art import draw_planet
from .races import RACES
from .treasury import BANKRUPTCY_LIMIT
from .ui import (CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED,
                 TEXT_BODY, TEXT_LABEL, TEXT_SMALL, TEXT_VALUE,
                 arrow, font, panel, paragraph, shorten, text, wrapped_lines)

MARGIN = 24
GAP = 12
SORTS = (('name', 'Colony'), ('population', 'Population'), ('food', 'Food'),
         ('industry', 'Industry'), ('income', 'Net CR'), ('research', 'Research'),
         ('slots', 'Slots'))
NAV = (('open_research', 'Research', 132),
       ('open_diplomacy', 'Diplomacy', 146), ('open_fleets', 'Fleets', 106),
       ('open_objectives', 'Objectives', 146), ('empire_rival', 'Rival report', 156),
       ('empire_specialists', 'Specialists', 146))


def flow(items, width, top, height=42, gap=8):
    x, y = MARGIN, top
    result = []
    for key, label, size in items:
        if x > MARGIN and x+size > width-MARGIN:
            x, y = MARGIN, y+height+gap
        result.append((key, label, pg.Rect(x, y, size, height)))
        x += size+gap
    return result, y+height


@dataclass(frozen=True)
class EmpireLayout:
    width: int
    height: int
    columns: int
    nav: tuple
    cards_top: int
    debt_top: int
    filters_top: int
    sorts_top: int
    rows_top: int
    row_height: int
    page_size: int
    pagination_top: int
    footer_top: int
    compact: bool


def layout_for(app, viewport):
    width, available_height = viewport
    items = NAV if app.empire_return == 'galaxy' else (('empire_back', '← Back · I', 176),)+NAV
    nav, nav_bottom = flow(items, width, 96)
    cards_top = nav_bottom+20
    columns = min(4, max(2, (width-2*MARGIN+GAP)//312))
    debt_top = cards_top+math.ceil(8/columns)*120
    summary = summarize_empire(app.game)
    note = debt_note(app.game, summary)
    note_height = max(1, len(wrapped_lines(note, width-2*MARGIN-24, TEXT_SMALL)))*22+20
    filters_top = debt_top+note_height+12
    compact = width < 1240
    sorts_top = filters_top+54
    if compact:
        _, sorts_bottom = flow([(key, label, max(90, font(17).size(label+' ↓')[0]+26))
                                for key, label in SORTS], width, sorts_top, 38)
        rows_top = sorts_bottom+12
        row_height = 220
    else:
        rows_top = sorts_top+34
        row_height = 82
    # Fewer rows at larger text sizes; an overflowing page remains scrollable.
    page_size = max(1, min(10, (available_height-rows_top-198)//row_height))
    pagination_top = rows_top+page_size*row_height+12
    footer_top = pagination_top+54
    height = max(available_height, footer_top+132)
    return EmpireLayout(width, height, columns, tuple(nav), cards_top, debt_top,
                        filters_top, sorts_top, rows_top, row_height, page_size,
                        pagination_top, height-132, compact)


def debt_note(game, summary):
    if game.credits < 0:
        return (f'Debt interest: {summary.interest:,} CR/turn (10%)  ·  '
                f'Bankruptcy at {BANKRUPTCY_LIMIT:,} CR  ·  '
                f'Next treasury: {game.credits+summary.income:,} CR')
    return f'Negative credits cost 10% interest per turn. Bankruptcy at {BANKRUPTCY_LIMIT:,} CR.'


def stats_for(game, s):
    return [
        ('Colonies', str(s.colonies), f'{s.population:,} B inhabitants'+(f' · {s.slaves} enslaved' if s.slaves else ''), INK),
        ('Treasury', f'{game.credits:,} CR', f'{s.income:+,} CR net / turn', RED if game.credits < 0 else GOLD),
        ('Industry', f'{s.industry:,} IND', 'Per turn · used locally', CYAN),
        ('Research stored', f'{game.research:,} RP', f'+{s.research:,} RP / turn', CYAN),
        ('Building slots', f'{s.used_slots} / {s.capacity}', f'{s.capacity-s.used_slots} free · includes queue', INK),
        ('Food / consumed', f'{s.food_produced} / {s.food_consumed}', f'{s.food_shortages} shortages · local supply', RED if s.food_shortages else CYAN),
        ('Resources', f'{game.resources:,} RES', f'{s.resources:+} / turn · net', GOLD),
        ('Energy', '∞' if game.bonuses_for().get('unlimited_energy') else f'{s.energy_generated} / {s.energy_demand}',
         'Dyson grid · empire-wide' if game.bonuses_for().get('unlimited_energy') else f'{s.energy_shortages} shortages · local', RED if s.energy_shortages else CYAN),
    ]


def columns(layout):
    # End positions leave clear gutters between numeric columns.
    starts = [MARGIN+16, MARGIN+246, MARGIN+372, MARGIN+490,
              MARGIN+600, MARGIN+710, MARGIN+830, MARGIN+940]
    ends = starts[1:]+[layout.width-MARGIN-20]
    return [(x, end-x-16) for x, end in zip(starts, ends)]


def draw_empire(app):
    surface, game = app.canvas, app.game
    layout = getattr(app, 'empire_layout', None)
    if app.screen != 'empire' or layout is None or layout.width != surface.get_width():
        layout = layout_for(app, surface.get_size())
    s = summarize_empire(game)
    rows = colony_rows(game, app.empire_filter, app.empire_sort, app.empire_descending)
    last_page = max(0, (len(rows)-1)//layout.page_size)
    page = min(max(0, app.empire_page), last_page)
    if app.screen == 'empire':
        app.empire_page = page
        app.empire_page_capacity = layout.page_size
    start = page*layout.page_size
    visible = rows[start:start+layout.page_size]
    right = layout.width-MARGIN

    panel(surface, (MARGIN, 16, layout.width-2*MARGIN, 66))
    text(surface, shorten(game.empire_name, layout.width-340, 30, 'title'), (MARGIN+16, 22), 30, INK, 'title')
    text(surface, f'{RACES[game.race_id].name} · Empire overview', (MARGIN+17, 59), TEXT_SMALL, MUTED)
    text(surface, f'Year {game.year} · Turn {game.turn}', (right-16, 30), TEXT_SMALL, GOLD, right=True)
    text(surface, f'{s.projects} queued · {s.idle} idle', (right-16, 57), TEXT_SMALL, MUTED, right=True)
    callbacks = {'empire_back': app.close_empire, 'open_research': app.open_research,
                 'open_diplomacy': app.open_diplomacy, 'open_fleets': app.open_fleets,
                 'open_objectives': app.open_objectives, 'empire_rival': app.open_rival,
                 'empire_specialists': app.open_specialists}
    for key, label, rect in layout.nav:
        if key == 'empire_back' and app.empire_return != 'galaxy':
            label = '← Back · I'
        app.button(key, label, rect, callbacks[key])

    width = (layout.width-2*MARGIN-(layout.columns-1)*GAP)//layout.columns
    for i, (label, value, caption, color) in enumerate(stats_for(game, s)):
        x = MARGIN+(i % layout.columns)*(width+GAP)
        y = layout.cards_top+(i//layout.columns)*120
        panel(surface, (x, y, width, 108))
        text(surface, label, (x+16, y+10), TEXT_LABEL, MUTED)
        # Extremely large late-game values can wrap onto a second line.
        value_size = TEXT_VALUE
        if font(value_size).size(value)[0] > width-32:
            value_size = TEXT_BODY
        text(surface, value, (x+16, y+34), value_size, color)
        text(surface, caption, (x+16, y+79), TEXT_SMALL, MUTED)

    warning = game.credits+s.income <= BANKRUPTCY_LIMIT
    panel(surface, (MARGIN, layout.debt_top, layout.width-2*MARGIN,
                    layout.filters_top-layout.debt_top-12), border=RED if warning else LINE)
    for i, line in enumerate(wrapped_lines(debt_note(game, s), layout.width-2*MARGIN-24, TEXT_SMALL)):
        text(surface, line, (MARGIN+12, layout.debt_top+9+i*22), TEXT_SMALL, RED if warning else MUTED)
    panel(surface, (MARGIN, layout.filters_top-4, layout.width-2*MARGIN, layout.rows_top-layout.filters_top))
    text(surface, 'Colonies', (MARGIN, layout.filters_top+7), 23, INK)
    text(surface, f'{len(rows)} / {s.colonies}', (MARGIN+118, layout.filters_top+12), TEXT_SMALL, MUTED)
    filter_width = min(112, (layout.width-2*MARGIN-205-32)//5)
    x = right-5*filter_width-32
    for i, key in enumerate(FILTERS):
        rect = pg.Rect(x+i*(filter_width+8), layout.filters_top, filter_width, 42)
        app.button('empire_filter_'+key, key.capitalize(), rect, lambda f=key: app.set_empire_filter(f))
        if app.empire_filter == key:
            pg.draw.line(surface, GOLD, (rect.x, rect.bottom-2), (rect.right, rect.bottom-2), 3)

    if layout.compact:
        sort_buttons, _ = flow([(key, label, max(90, font(17).size(label+' ↓')[0]+26))
                               for key, label in SORTS], layout.width, layout.sorts_top, 38)
        for key, label, rect in sort_buttons:
            if app.empire_sort == key:
                label += ' ↓' if app.empire_descending else ' ↑'
            app.button('empire_sort_'+key, label, rect, lambda k=key: app.sort_empire(k))
    else:
        for (key, label), (x, width) in zip(SORTS, columns(layout)):
            if app.empire_sort == key:
                label += ' ↓' if app.empire_descending else ' ↑'
            app.button('empire_sort_'+key, '', (x-4, layout.sorts_top, width+8, 30), lambda k=key: app.sort_empire(k), 'hotspot')
            text(surface, label, (x, layout.sorts_top+5), TEXT_SMALL, GOLD if app.empire_sort == key else MUTED)
        text(surface, 'Construction', (columns(layout)[7][0], layout.sorts_top+5), TEXT_SMALL, MUTED)

    for index, (system, planet) in enumerate(visible):
        y = layout.rows_top+index*layout.row_height
        draw_colony(app, layout, system, planet, y)

    if not visible:
        panel(surface, (MARGIN, layout.rows_top, layout.width-2*MARGIN, layout.row_height-8))
        text(surface, 'No colonies yet.' if not s.colonies else 'No colonies match this filter.',
             (MARGIN+16, layout.rows_top+12), TEXT_BODY, INK)
        text(surface, 'Explore the galaxy.' if not s.colonies else 'Choose All to show every colony.',
             (MARGIN+16, layout.rows_top+42), TEXT_SMALL, MUTED)
        if s.colonies:
            app.button('empire_clear_filter', 'Show all colonies', (right-240, layout.rows_top+16, 224, 42),
                       lambda: app.set_empire_filter('all'))

    text(surface, f'Page {page+1} / {last_page+1}', (MARGIN, layout.pagination_top+12), TEXT_BODY, MUTED)
    app.button('empire_previous', '← Prev', (right-260, layout.pagination_top, 122, 42), lambda: app.change_empire_page(-1), enabled=page > 0)
    app.button('empire_next', 'Next →', (right-126, layout.pagination_top, 126, 42), lambda: app.change_empire_page(1), enabled=page < last_page)
    if not layout.compact:
        text(surface, 'Click a colony to manage it; click a heading to sort.', (MARGIN+190, layout.pagination_top+13), TEXT_SMALL, MUTED)
    draw_footer(app, layout, s)


def colony_values(game, planet):
    industry, income, research = game.planet_yields(planet)
    food = game.population_report(planet)
    power = game.planet_energy(planet)
    growth = f'Growth {food.progress}%' if food.growth_rate else 'Limit reached' if planet.population >= food.capacity else 'Growth paused'
    population = f'{planet.population}+{planet.slaves} S' if planet.slaves else f'{planet.population}/{food.capacity} B'
    return [
        (population, f'Power {power.balance}' if power.balance < 0 else growth, INK, RED if power.balance < 0 else MUTED),
        (f'{food.balance:+}', f'{food.produced}/{food.consumed} used', RED if food.balance < 0 else CYAN, MUTED),
        (str(industry), 'per turn', CYAN, MUTED),
        (f'{income:+}', f'{game.planet_maintenance(planet)} upkeep', RED if income < 0 else INK, MUTED),
        (f'+{research}', 'per turn', CYAN, MUTED),
        (f'{planet.used_slots}/{planet.building_capacity}', 'Full' if not planet.free_slots else f'{planet.free_slots} free', INK, GOLD if not planet.free_slots else MUTED),
    ]


def construction(game, planet):
    if planet.trade_goods:
        return 'Trade Goods', f'+{game.trade_goods_income(planet)} CR/turn', 'Ongoing', None
    if planet.construction_queue:
        project = planet.construction_queue[0]
        waiting = len(planet.construction_queue)-1
        caption = f'{project.progress}/{project.spec.work_cost} work'+(f' · {waiting} waiting' if waiting else '')
        return display_name(project.spec, planet.habitat), turn_label(game.queue_estimates(planet)[0]), caption, project.progress/project.spec.work_cost
    return 'Idle', '', 'No free building slots' if not planet.free_slots else 'Choose a project in the colony', None


def draw_colony(app, layout, system, planet, y):
    surface, game = app.canvas, app.game
    r = pg.Rect(MARGIN, y, layout.width-2*MARGIN, layout.row_height-8)
    panel(surface, r)
    b = app.button(f'empire_colony_{system.id}_{planet.id}', '', r,
                   lambda s=system.id, p=planet.id: app.open_empire_colony(s, p), 'hotspot')
    active = app.is_active(b)
    if planet.habitat:
        from .mothership_art import draw
        draw(surface, (MARGIN+30, y+35), .5, app.empire_color(planet.owner))
    else:
        draw_planet(surface, planet, (MARGIN+30, y+35), 36, f'{game.seed}:{system.id}:{planet.id}')
    name_width = layout.width-180 if layout.compact else 170
    text(surface, shorten(planet.name, name_width, TEXT_BODY), (MARGIN+57, y+10), TEXT_BODY, GOLD if active else INK)
    text(surface, shorten(f'{system.name} · '+('Habitat' if planet.habitat else planet.size), name_width, TEXT_SMALL),
         (MARGIN+57, y+38), TEXT_SMALL, MUTED)
    values = colony_values(game, planet)
    name, eta, caption, progress = construction(game, planet)
    if layout.compact:
        cell = (layout.width-2*MARGIN-32)//3
        for i, ((_, label), (value, detail, color, secondary)) in enumerate(zip(SORTS[1:], values)):
            x = MARGIN+16+(i%3)*cell
            top = y+72+(i//3)*42
            text(surface, label+': '+value, (x, top), TEXT_SMALL, color)
            # Keep detailed economic values readable in the compact layout too.
            text(surface, detail, (x, top+20), TEXT_SMALL, secondary)
        text(surface, shorten(name, layout.width-2*MARGIN-200, TEXT_BODY), (MARGIN+16, y+160), TEXT_BODY, INK)
        text(surface, eta, (r.right-16, y+160), TEXT_SMALL, GOLD, right=True)
        text(surface, caption, (MARGIN+16, y+183), TEXT_SMALL, MUTED)
    else:
        cols = columns(layout)
        for (x, width), (value, detail, color, secondary) in zip(cols[1:7], values):
            text(surface, value, (x+width, y+10), TEXT_BODY, color, right=True)
            text(surface, detail, (x+width, y+40), TEXT_SMALL, secondary, right=True)
        x, width = cols[7]
        # Reserve the completion column before fitting a project name.
        eta_width = font(TEXT_SMALL).size(eta)[0]+18 if eta else 0
        text(surface, shorten(name, width-eta_width, TEXT_BODY), (x, y+10), TEXT_BODY, INK)
        text(surface, eta, (x+width, y+12), TEXT_SMALL, GOLD, right=True)
        text(surface, shorten(caption, width, TEXT_SMALL), (x, y+40), TEXT_SMALL, MUTED)
        if progress is not None:
            pg.draw.rect(surface, LINE, (x, y+66, width, 3))
            pg.draw.rect(surface, GOLD, (x, y+66, round(width*max(0, min(1, progress))), 3))


def draw_footer(app, layout, summary):
    from .specialists import salaries
    from .accession import upkeep
    from .gas_giants import income as station_income
    surface, game = app.canvas, app.game
    top = layout.footer_top
    panel(surface, (MARGIN, top, layout.width-2*MARGIN, 124))
    interest = f' − {summary.interest} interest' if summary.interest else ''
    caption = f'Budget: {summary.gross_income} gross − {summary.maintenance} upkeep{interest} = {summary.income:+} CR/turn'
    text(surface, caption, (MARGIN+12, top+8), TEXT_SMALL, GOLD if game.credits >= 0 else RED)
    fleet, pay, outreach = game.fleet_maintenance(), salaries(game), upkeep(game)
    orbital = station_income(game, 'player')[2]
    detail = f'Upkeep: {summary.maintenance-fleet-pay-outreach-orbital} facilities · {orbital} orbital · {fleet} ships · {pay} salaries · {outreach} outreach'
    text(surface, detail, (MARGIN+12, top+31), TEXT_SMALL, MUTED)
    app.button('empire_pause', 'Menu', (MARGIN+12, layout.height-80, 112, 54), app.pause)
    app.button('empire_save', 'Save · F5', (MARGIN+136, layout.height-80, 146, 54), app.save_game)
