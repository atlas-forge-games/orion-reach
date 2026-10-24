"""Orbital industry over the existing gas giant landscape."""

from . import gas_giants as rules
from .building_art import draw_building_art
from .planet_art import draw_planet
from .model import PLAYER, RuleError
from .ui import CYAN, GOLD, INK, MUTED, panel, paragraph, shorten, text


def draw_survey(app, game, planet):
    surface, sid = app.canvas, game.selected_system
    prop = rules.trait(game, sid, planet.id)
    name, detail = rules.TRAITS[prop]
    text(surface, 'ATMOSPHERIC SURVEY', (302, 66), 10, GOLD, 'mono', 1)
    draw_planet(surface, planet, (413, 181), 158, f'{game.seed}:{sid}:{planet.id}')
    text(surface, name, (520, 104), 24, INK, 'title')
    paragraph(surface, detail, (520, 150), 510, 14, CYAN, 22)
    text(surface, 'No surface colonies · One orbital installation', (520, 211), 13, MUTED)
    text(surface, f'Outer orbit · {planet.orbit_au:.2f} AU · {planet.gravity} gravity', (520, 239), 12, GOLD)
    text(surface, 'Stations have no population and do not extend fuel range.', (302, 279), 11, MUTED)


def draw_controls(app, game, system, planet, live):
    surface = app.canvas
    station = planet.orbital_station
    text(surface, 'ORBITAL INSTALLATION', (1090, 66), 10, GOLD, 'mono', 1)
    if station:
        spec = rules.specification(game, system.id, planet.id, station.kind)
        text(surface, spec.name, (1090, 96), 22, INK)
        text(surface, shorten(game.empire_name_for(station.owner), 306, 14), (1090, 133), 14, app.empire_color(station.owner))
        text(surface, rules.status(game, system.id, planet) if live else 'Status at last survey', (1090, 162), 12, CYAN if live else MUTED)
        text(surface, f'Hull {station.hull}/{rules.STATION_HULL} · Upkeep {spec.upkeep} CR/turn', (1090, 190), 12, INK)
        text(surface, 'Protect this unarmed station with a fleet.', (1090, 222), 11, MUTED)
    else:
        text(surface, 'Choose a specialization', (1090, 98), 20, INK)
        paragraph(surface, 'A local colony supplies construction crews. Otherwise, an idle outpost ship is consumed. Assembly takes two turns.',
                  (1090, 139), 306, 14, MUTED, 22)
    app.button('colonize_planet', 'Colonize', (1090, 257, 146, 29), app.colonize_request, enabled=False)
    app.button('establish_outpost', 'Surface outpost', (1246, 257, 154, 29), app.outpost_request, enabled=False)


def request(app, sid, pid, action, kind=None):
    game = app.game
    planet = game.planet_at(sid, pid)
    if action == 'build':
        spec = rules.specification(game, sid, pid, kind)
        reason = rules.build_error(game, sid, pid, kind)
        title, label = 'Commission '+spec.name+'?', 'Commission station'
        source = 'Local colony crews assemble it.' if game.settlements_at(sid, PLAYER) else 'One idle outpost ship is consumed.'
        body = (f'{spec.resources} Resources + {spec.credits} Credits. {source} '
                f'Two turns of assembly; {spec.upkeep} CR upkeep each turn. '
                'Only one installation fits here; replacing it requires dismantling without a refund.')
        order = lambda: rules.build(game, sid, pid, kind)
    elif action == 'dismantle':
        reason = None
        title, label = 'Dismantle orbital station?', 'Dismantle station'
        body = 'This removes the station, its output and upkeep immediately. Construction costs are not refunded.'
        order = lambda: rules.dismantle(game, sid, pid)
    else:
        capture = action == 'capture'
        reason = rules.attack_error(game, sid, pid, capture=capture)
        title, label = ('Capture station?', 'Capture station') if capture else ('Bombard station?', 'Bombard station')
        if capture:
            body = 'Consume one troop transport to install an occupation crew. Output resumes next turn if assembly is complete and the system is clear.'
        else:
            from .defenses import bombardment_attacks
            damage = min(planet.orbital_station.hull, sum(d for d, _ in bombardment_attacks(game, sid)))
            body = f'Inflict {damage} damage; {planet.orbital_station.hull-damage} hull remains. At zero hull the station is destroyed.'
        body += ' Escort ships spend their bombardment action. This starts war and ends treaties.'
        order = lambda: rules.attack(game, sid, pid, capture=capture)
    if reason:
        app.toast(reason, True)
        return
    def execute():
        try:
            result = order()
            app.save_game(autosave=True)
            app.toast(result if isinstance(result, str) else 'Orbital station commissioned · Two turns to completion')
        except RuleError as exc:
            app.toast(exc, True)
    app.confirm(title, body, label, execute)


def draw_stations(app, game, system, planet, live):
    surface, sid, pid = app.canvas, system.id, planet.id
    station = planet.orbital_station
    if station:
        draw_installation(app, game, system, planet, live)
        return
    for i, kind in enumerate(rules.STATIONS):
        spec = rules.specification(game, sid, pid, kind)
        x, y = 40+i*458, 404
        panel(surface, (x, y, 444, 414), (10, 23, 33))
        text(surface, f'0{i+1}  /  ORBITAL INDUSTRY', (x+20, y+18), 10, MUTED, 'mono')
        text(surface, spec.name, (x+20, y+44), 23, INK, 'title')
        draw_building_art(surface, spec.art, (x+16, y+93, 168, 155), habitat=True)
        text(surface, f'+{spec.output} {spec.unit}', (x+207, y+118), 30, CYAN)
        text(surface, 'per system / turn' if kind == 'energy' else 'per turn · gross', (x+207, y+162), 12, MUTED)
        text(surface, f'{spec.upkeep} CR upkeep / turn', (x+207, y+190), 12, GOLD)
        text(surface, f'{spec.resources} RES  +  {spec.credits} CR', (x+20, y+249), 18, GOLD)
        description = ('Finite power shared by your local colonies; surplus is unused.' if kind == 'energy' else
                       'Atmospheric gas exports fund your empire.' if kind == 'refinery' else
                       'Atmospheric observatories add research points to your empire.')
        paragraph(surface, description, (x+20, y+281), 400, 12, MUTED, 18)
        reason = ('Observer mode · No orders' if game.is_observer else 'Refresh this survey before building.' if not live
                  else rules.build_error(game, sid, pid, kind))
        app.button('orbital_build_'+kind, 'Commission · 2 turns', (x+20, y+337, 404, 36),
                   lambda k=kind: request(app, sid, pid, 'build', k), 'primary', enabled=reason is None)
        text(surface, shorten(reason or 'One station per giant · Defend it with a fleet', 404, 10), (x+20, y+387), 10, MUTED)


def draw_installation(app, game, system, planet, live):
    surface, sid, pid = app.canvas, system.id, planet.id
    station = planet.orbital_station
    spec = rules.specification(game, sid, pid, station.kind)
    panel(surface, (40, 404, 1358, 414), (10, 23, 33))
    draw_building_art(surface, spec.art, (68, 432, 360, 330), habitat=True)
    text(surface, spec.name, (478, 432), 32, INK, 'title')
    active = live and rules.operating(game, sid, planet)
    value = str(spec.output if active else 0) if live else '?'
    text(surface, f'+{value} {spec.unit} / turn', (478, 490), 28, CYAN if active else MUTED)
    text(surface, f'{spec.upkeep} CR upkeep / turn · Hull {station.hull}/{rules.STATION_HULL}', (478, 535), 14, GOLD)
    if station.kind == 'energy':
        description = 'Power is shared once among your colonies in this star system, in system/planet order. It fills local shortages before backup generators burn fuel. Unused capacity is not stored.'
    else:
        description = 'Output goes to the station owner. Assembly and hostile blockades suspend output; upkeep continues. This installation has no population or surface buildings.'
    paragraph(surface, description, (478, 575), 850, 15, MUTED, 24)
    if live and station.owner == PLAYER and not game.is_observer:
        app.button('orbital_dismantle', 'Dismantle station', (478, 726, 300, 40), lambda: request(app, sid, pid, 'dismantle'))
        text(surface, 'No refund · Frees this orbital slot', (478, 781), 11, MUTED)
    elif live and not game.is_observer:
        for i, (action, label) in enumerate((('attack', 'Bombard station'), ('capture', 'Capture station'))):
            x = 478+i*443
            reason = rules.attack_error(game, sid, pid, capture=action == 'capture')
            app.button('orbital_'+action, label, (x, 726, 416, 40), lambda a=action: request(app, sid, pid, a), enabled=reason is None)
            text(surface, shorten(reason or ('Occupation crew consumes one troop transport' if action == 'capture' else 'Each ship may bombard once per turn'), 416, 10), (x, 781), 10, MUTED)
    else:
        text(surface, 'OBSERVER · NO ORDERS' if game.is_observer else 'LAST SURVEY · SEND SHIPS TO REFRESH', (478, 744), 13, MUTED, 'mono')
