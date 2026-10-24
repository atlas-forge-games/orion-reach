"""Read-only descriptions for the structures shown in planetary overviews."""

from collections import Counter
from dataclasses import dataclass

from .buildings import BUILDINGS
from .building_art import draw_building_art
from .colony_scene import scene_buildings
from .economy import building_status
from .habitat_modules import display_name
from .ui import CYAN, GOLD, INK, MUTED, PANEL, panel, shorten, text, wrapped_lines


@dataclass(frozen=True)
class BuildingInfo:
    identifier: str
    title: str
    location: str
    sections: tuple[tuple[str, str], ...]
    habitat: bool = False


def describe(game, system_id, planet, key, *, live):
    """Resolve only a displayed structure, using the visible survey's contents."""
    if key.startswith('surface_'):
        identifier = key.removeprefix('surface_')
        item = next((item for item in scene_buildings(game, system_id, planet)
                     if item.asset_id == identifier), None)
        if item is None:
            return None
        slots = [i for i, value in enumerate(planet.buildings) if value == identifier]
        built, queued = item.completed, item.queued
    elif key.startswith('mothership_module_') and planet.habitat:
        index = int(key.removeprefix('mothership_module_'))
        if not 0 <= index < planet.used_slots:
            return None
        built, queued = int(index < len(planet.buildings)), int(index >= len(planet.buildings))
        identifier = (planet.buildings[index] if built else
                      planet.building_projects[index-len(planet.buildings)][1].item_id)
        slots = [index] if built else []
    else:
        return None

    if identifier == 'headquarters':
        title = 'Headquarters palace'
        sections = (
            ('PURPOSE', "This civilization's administrative centre. Its location is the reference for distance-related administration strain."),
            ('UPKEEP & SPACE', 'No separate upkeep or building slot. This landmark marks the headquarters colony.'),
            ('LEFT-CLICK', 'Open the empire overview or the rival report.'),
        )
    elif identifier == 'shipyard':
        title = 'Shipyard'
        sections = (
            ('PURPOSE', "Construct ships through this colony's production queue, using local industry and the empire's shared Resources."),
            ('UPKEEP & SPACE', 'No separate upkeep or building slot. Completed ships pay their own maintenance.'),
            ('CONSTRUCTION', f'{queued} ship projects queued. Ship projects share the production queue with buildings.'),
            ('LEFT-CLICK', 'Open the shipyard to review available designs and ship construction.'),
        )
    else:
        spec = BUILDINGS[identifier]
        title = display_name(spec, planet.habitat)
        if live:
            statuses = Counter(building_status(planet, i, game.bonuses_for(planet.owner)) for i in slots)
            status = ' · '.join(f'{count} {label.lower()}' for label, count in statuses.items())
        else:
            status = 'Last observed; current operating status unknown.'
        if queued:
            status += (' · ' if status else '')+f'{queued} queued (no effects until completed)'
        sections = [
            ('PURPOSE', spec.description),
            ('BASE EFFECTS PER BUILDING', spec.effect_text(planet.richness)),
        ]
        if bonus := spec.workforce_text(planet.richness):
            sections.append(('WORKFORCE BONUS', bonus))
        sections += [
            ('BASE UPKEEP & POWER', f'{spec.maintenance} Credits / turn · {spec.energy_use} energy demand'),
            ('STATUS', status or f'{built} built'),
            ('VALUES', f'{planet.richness} mineral richness, before empire bonuses and administration. Benefits require the building to operate.'),
        ]
    location = planet.name+(' · Last survey' if not live else ' · Onboard module' if planet.habitat else ' · Colony structure')
    return BuildingInfo(identifier, title, location, tuple(sections), planet.habitat)


def draw(app):
    info, surface = app.dialog['building_info'], app.canvas
    panel(surface, (260, 100, 920, 700), PANEL, GOLD)
    text(surface, 'MODULE INFORMATION' if info.habitat else 'BUILDING INFORMATION', (294, 125), 11, GOLD, 'mono', 1)
    text(surface, shorten(info.title, 660, 30, 'title'), (294, 154), 30, INK, 'title')
    text(surface, shorten(info.location, 660, 13), (294, 199), 13, CYAN)
    draw_building_art(surface, info.identifier, (982, 127, 158, 112), habitat=info.habitat)
    rows = []
    for heading, body in info.sections:
        rows.append((heading, GOLD))
        rows.extend((line, INK) for line in wrapped_lines(body, 842, 15))
        rows.append(('', MUTED))
    per_page = 19
    last = max(0, (len(rows)-1)//per_page)
    page = min(last, max(0, app.dialog.get('info_page', 0)))
    for i, (line, color) in enumerate(rows[page*per_page:(page+1)*per_page]):
        text(surface, line, (294, 258+i*23), 15, color)
    if last:
        app.button('dialog_building_previous', '←', (294, 733, 52, 40),
                   lambda: app.dialog.update(info_page=page-1), enabled=page > 0)
        text(surface, f'{page+1} / {last+1}', (361, 746), 12, MUTED)
        app.button('dialog_building_next', '→', (418, 733, 52, 40),
                   lambda: app.dialog.update(info_page=page+1), enabled=page < last)
    text(surface, 'Right-click or Esc to close', (500, 746), 12, MUTED)
    app.button('dialog_close', 'Close · Esc', (944, 731, 202, 44), app.cancel_dialog, 'primary')
