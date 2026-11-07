"""Compact empire totals and a sortable, independently scrolling colony list."""

from dataclasses import dataclass
import pygame as pg

from .habitat_modules import display_name
from .colony_view import turn_label
from .empire import FILTERS, colony_rows, summarize_empire
from .empire_scroll import row_key
from .planet_art import draw_planet
from .races import RACES
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, font, panel, shorten, text

MARGIN = 24
SORTS = (('name', 'Colony'), ('population', 'Population'), ('food', 'Food'),
         ('industry', 'Industry'), ('income', 'Net CR'), ('research', 'Research'),
         ('slots', 'Slots'))
COMPACT_SORTS = ('Colony', 'Pop.', 'Food', 'Ind.', 'CR', 'RP', 'Slots')


@dataclass(frozen=True)
class EmpireLayout:
    width: int
    height: int
    header: pg.Rect
    summary: pg.Rect
    filters_top: int
    sorts_top: int
    rows_top: int
    row_height: int
    list_rect: pg.Rect
    compact: bool


def layout_for(app, viewport):
    width, available_height = viewport
    compact = width < 1240
    filters_top, sorts_top, rows_top = (164, 206, 244) if compact else (180, 226, 264)
    row_height = 168 if compact else 72
    height = max(available_height, rows_top+row_height+94)
    return EmpireLayout(width, height,
                        pg.Rect(MARGIN, 12, width-2*MARGIN, 56 if compact else 64),
                        pg.Rect(MARGIN, 78 if compact else 88, width-2*MARGIN, 76 if compact else 80),
                        filters_top, sorts_top, rows_top, row_height,
                        pg.Rect(MARGIN, rows_top, width-2*MARGIN, height-94-rows_top), compact)


def stats_for(game, s):
    return [
        ('Colonies', str(s.colonies), f'{s.population:,} B pop.'+(f' · {s.slaves} enslaved' if s.slaves else ''), INK),
        ('Treasury', f'{game.credits:,} CR', f'{s.income:+,} / turn', RED if game.credits < 0 else GOLD),
        ('Industry', f'{s.industry:,} IND', 'Per turn', CYAN),
        ('Research', f'{game.research:,} RP', f'{s.research:+,} / turn', CYAN),
        ('Slots', f'{s.used_slots} / {s.capacity}', f'{s.capacity-s.used_slots} free', INK),
        ('Food', f'{s.food_produced} / {s.food_consumed}', f'{s.food_shortages} short' if s.food_shortages else 'Local supply', RED if s.food_shortages else CYAN),
        ('Resources', f'{game.resources:,} RES', f'{s.resources:+} / turn', GOLD),
        ('Energy', '∞' if game.bonuses_for().get('unlimited_energy') else f'{s.energy_generated} / {s.energy_demand}',
         'Dyson grid' if game.bonuses_for().get('unlimited_energy') else f'{s.energy_shortages} short' if s.energy_shortages else 'Local supply', RED if s.energy_shortages else CYAN),
    ]


def columns(layout):
    starts = [MARGIN+16, MARGIN+246, MARGIN+372, MARGIN+490,
              MARGIN+600, MARGIN+710, MARGIN+830, MARGIN+940]
    ends = starts[1:]+[layout.width-MARGIN-36]
    return [(x, end-x-16) for x, end in zip(starts, ends)]


def draw_empire(app):
    surface, game = app.canvas, app.game
    layout = getattr(app, 'empire_layout', None)
    if app.screen != 'empire' or layout is None or layout.width != surface.get_width():
        layout = layout_for(app, surface.get_size())
    s = summarize_empire(game)
    rows = colony_rows(game, app.empire_filter, app.empire_sort, app.empire_descending)
    view = app.empire_scroll
    view.configure(layout.list_rect, layout.row_height, [row_key(system, planet) for system, planet in rows])
    if app.keyboard_mode:
        if app.focus != view.focus_seen:
            view.ensure_visible(app.focus)
        view.focus_seen = app.focus
    else:
        view.focus_seen = None
    right = layout.width-MARGIN

    panel(surface, layout.header)
    title_size = 24 if layout.compact else 28
    text(surface, shorten(game.empire_name, layout.width-290, title_size, 'title'),
         (MARGIN+14, layout.header.y+5), title_size, INK, 'title')
    text(surface, f'{RACES[game.race_id].name} · Empire overview',
         (MARGIN+15, layout.header.bottom-20), 12, MUTED)
    text(surface, f'Year {game.year} · Turn {game.turn}', (right-14, layout.header.y+14), 14, GOLD, right=True)

    panel(surface, layout.summary)
    stats = stats_for(game, s)
    for i, (label, value, caption, color) in enumerate(stats):
        left = layout.summary.x+round(i*layout.summary.w/len(stats))
        end = layout.summary.x+round((i+1)*layout.summary.w/len(stats))
        width, top = end-left-20, layout.summary.y
        if i:
            pg.draw.line(surface, LINE, (left, top+10), (left, layout.summary.bottom-10))
        text(surface, shorten(label, width, 12 if layout.compact else 14),
             (left+10, top+7), 12 if layout.compact else 14, MUTED)
        value_size = 22 if layout.compact else 24
        while value_size > 16 and font(value_size).size(value)[0] > width:
            value_size -= 1
        text(surface, shorten(value, width, value_size), (left+10, top+27), value_size, color)
        text(surface, shorten(caption, width, 12 if layout.compact else 13),
             (left+10, top+55), 12 if layout.compact else 13, MUTED)

    panel(surface, (MARGIN, layout.filters_top-4, layout.width-2*MARGIN, layout.rows_top-layout.filters_top-4))
    text(surface, 'Colonies', (MARGIN+10, layout.filters_top+6), 22, INK)
    count = f'{len(rows)} / {s.colonies}' if app.empire_filter != 'all' else str(s.colonies)
    text(surface, count, (MARGIN+122, layout.filters_top+12), 14, MUTED)
    filter_width = min(96 if layout.compact else 112, (layout.width-2*MARGIN-180-32)//5)
    x = right-5*filter_width-32
    for i, key in enumerate(FILTERS):
        rect = pg.Rect(x+i*(filter_width+8), layout.filters_top, filter_width, 34 if layout.compact else 38)
        label = 'Build' if layout.compact and key == 'building' else key.capitalize()
        app.button('empire_filter_'+key, label, rect, lambda f=key: app.set_empire_filter(f))
        if app.empire_filter == key:
            pg.draw.line(surface, GOLD, (rect.x, rect.bottom-2), (rect.right, rect.bottom-2), 3)

    if layout.compact:
        width = (layout.width-2*MARGIN-6*8)//7
        for i, ((key, _), label) in enumerate(zip(SORTS, COMPACT_SORTS)):
            if app.empire_sort == key:
                label += ' ↓' if app.empire_descending else ' ↑'
            app.button('empire_sort_'+key, label, (MARGIN+i*(width+8), layout.sorts_top, width, 30),
                       lambda k=key: app.sort_empire(k))
    else:
        for (key, label), (x, width) in zip(SORTS, columns(layout)):
            if app.empire_sort == key:
                label += ' ↓' if app.empire_descending else ' ↑'
            app.button('empire_sort_'+key, '', (x-4, layout.sorts_top, width+8, 30), lambda k=key: app.sort_empire(k), 'hotspot')
            text(surface, label, (x, layout.sorts_top+5), 14, GOLD if app.empire_sort == key else MUTED)
        text(surface, 'Construction', (columns(layout)[7][0], layout.sorts_top+5), 14, MUTED)

    clip = surface.get_clip()
    surface.set_clip(layout.list_rect)
    try:
        for index in view.visible_range():
            system, planet = rows[index]
            y = layout.rows_top+index*layout.row_height-round(view.offset)
            draw_colony(app, layout, system, planet, y)
        if not rows:
            panel(surface, (MARGIN, layout.rows_top, layout.width-2*MARGIN-20, 64))
            text(surface, 'No colonies yet.' if not s.colonies else 'No colonies match this filter.',
                 (MARGIN+16, layout.rows_top+20), 18, INK)
            if s.colonies:
                app.button('empire_clear_filter', 'Show all colonies', (right-260, layout.rows_top+11, 224, 42),
                           lambda: app.set_empire_filter('all'))
    finally:
        surface.set_clip(clip)
    if view.maximum:
        track, thumb = view.scrollbar()
        pg.draw.rect(surface, (18, 30, 42), track, border_radius=5)
        pg.draw.rect(surface, CYAN if view.drag else (149, 177, 195), thumb, border_radius=4)


def colony_values(game, planet):
    industry, income, research = game.planet_yields(planet)
    food = game.population_report(planet)
    power = game.planet_energy(planet)
    growth = f'Growth {food.progress}%' if food.growth_rate else 'Limit reached' if planet.population >= food.capacity else 'Growth paused'
    population = f'{planet.population}+{planet.slaves} S' if planet.slaves else f'{planet.population}/{food.capacity} B'
    return [
        (population, f'{power.efficiency_label} power' if power.efficiency < 1 else 'Gate paused' if power.balance < 0 else growth, INK, RED if power.balance < 0 else MUTED),
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
    r = pg.Rect(MARGIN, y, layout.width-2*MARGIN-20, layout.row_height-8)
    visible = r.clip(layout.list_rect)
    if not visible.w or not visible.h:
        return
    panel(surface, r)
    b = app.button(row_key(system, planet), '', visible,
                   lambda s=system.id, p=planet.id: app.open_empire_colony(s, p), 'hotspot')
    active = app.is_active(b)
    if planet.habitat:
        from .mothership_art import draw
        draw(surface, (MARGIN+30, y+35), .5, app.empire_color(planet.owner))
    else:
        draw_planet(surface, planet, (MARGIN+30, y+35), 36, f'{game.seed}:{system.id}:{planet.id}')
    name_width = layout.width-180 if layout.compact else 170
    text(surface, shorten(planet.name, name_width, 18), (MARGIN+57, y+8), 18, GOLD if active else INK)
    text(surface, shorten(f'{system.name} · '+('Habitat' if planet.habitat else planet.size), name_width, 14),
         (MARGIN+57, y+34), 14, MUTED)
    values = colony_values(game, planet)
    name, eta, caption, progress = construction(game, planet)
    if layout.compact:
        cell = (r.w-32)//6
        for i, ((_, label), (value, detail, color, secondary)) in enumerate(zip(SORTS[1:], values)):
            x = MARGIN+16+i*cell
            text(surface, shorten(label, cell-8, 11), (x, y+58), 11, MUTED)
            text(surface, shorten(value, cell-8, 17), (x, y+74), 17, color)
            text(surface, shorten(detail, cell-8, 11), (x, y+96), 11, secondary)
        text(surface, shorten(name, r.w-200, 17), (MARGIN+16, y+120), 17, INK)
        text(surface, eta, (r.right-16, y+120), 14, GOLD, right=True)
        text(surface, shorten(caption, r.w-32, 12), (MARGIN+16, y+142), 12, MUTED)
    else:
        cols = columns(layout)
        for (x, width), (value, detail, color, secondary) in zip(cols[1:7], values):
            text(surface, shorten(value, width, 18), (x+width, y+8), 18, color, right=True)
            text(surface, shorten(detail, width, 14), (x+width, y+36), 14, secondary, right=True)
        x, width = cols[7]
        # Reserve the completion column before fitting a project name.
        eta_width = font(14).size(eta)[0]+18 if eta else 0
        text(surface, shorten(name, width-eta_width, 18), (x, y+8), 18, INK)
        text(surface, eta, (x+width, y+10), 14, GOLD, right=True)
        text(surface, shorten(caption, width, 14), (x, y+36), 14, MUTED)
        if progress is not None:
            pg.draw.rect(surface, LINE, (x, y+59, width, 3))
            pg.draw.rect(surface, GOLD, (x, y+59, round(width*max(0, min(1, progress))), 3))
