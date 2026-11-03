"""Render every game screen and representative dialogs using temporary campaigns.

Run python tools/preview_all_screens.py --output /tmp/orion-screens.
The fixtures are also used by the UI smoke tests; player saves are never opened.
"""
import argparse
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg
from orion.app import App, GAME_SCREENS
from orion.model import new_game


def campaign(race='terran'):
    return new_game(seed=12, random_starts=False, with_ai=False, rival_count=3,
                    with_guardians=False, with_black_holes=False, with_tombs=False,
                    with_encounters=False, fog_of_war=False, race_id=race)


def screen_states(app):
    """Yield a name after preparing one real screen, without rendering it."""
    app.game = campaign()
    app.game.selected_system, app.game.selected_planet = 0, 2
    app.settings['animated_background'] = app.settings['autosave'] = False
    app.notice, app.mouse = '', (-1, -1)
    app.screen = 'galaxy'
    app.open_specialists()
    app.open_research()
    app.open_designer()
    app.fleet_anchor_id = app.game.ships[0].id
    for screen in GAME_SCREENS:
        if screen in ('combat', 'ground', 'result', 'contact', 'observer', 'hyperlane'):
            continue
        app.screen = screen
        yield screen
    for screen in ('splash', 'menu', 'setup', 'race_select', 'load', 'pause', 'info', 'about'):
        app.screen = screen
        yield screen
    for section in (None, 'graphics', 'sound', 'gameplay', 'interface'):
        app.screen, app.settings_section = 'settings', section
        yield 'settings_'+(section or 'overview')
    app.screen = 'galaxy'
    app.open_research()
    app.research_overview = False
    yield 'research_detail'
    from orion.research import choices
    app.show_technology_info(choices(app.research_branch, 1)[0].id)
    yield 'technology_info'
    app.dialog = None
    app.contact_owner, app.screen = 'rival', 'contact'
    yield 'contact'
    system, planet = app.game.headquarters('rival')
    app.ground_target, app.screen = (system.id, planet.id), 'ground'
    yield 'ground'
    app.ground_target = None

    home = app.game.planet_at(0, 2)
    home.buildings = ['space_hub', 'factory', 'research_lab', 'mine']
    app.game.credits = app.game.resources = 10000
    for _ in range(3):
        app.game.advance_turn()
    app.open_specialists()
    yield 'specialists_visitors'
    from orion import specialists
    for person in specialists.visitors(app.game)[:2]:
        app.specialist_select(person.id)
        yield 'specialist_'+person.spec.role
    app.game.selected_system, app.game.selected_planet = 0, 2
    app.game.queue_building(0, 2, 'barracks')
    for screen in ('planet', 'colony', 'production', 'shipyard'):
        app.screen = screen
        yield screen+'_populated'
    app.screen = 'planet'
    for name, show in (
        ('population_info', app.show_population_info),
        ('building_info', lambda: app.show_building_info('surface_factory')),
        ('output_breakdown', lambda: app.show_output_breakdown('industry')),
        ('alignment', app.show_alignment),
        ('diplomatic_affairs', app.show_diplomatic_affairs),
    ):
        app.dialog = None
        show()
        yield name
    app.dialog = None
    app.screen = 'designer'
    app.show_design_requirements()
    yield 'designer_info'
    app.dialog = None
    app.screen = 'galaxy'
    app.open_map_fleet(app.game.ships_owned_by()[0].id)
    yield 'galaxy_fleet'
    app.close_fleet_popup()
    app.dialog = dict(title='Return to the main menu?', body='Your campaign stays available through Continue. Save first if you want to keep this turn on disk.',
                      label='Return to menu', action=lambda: None)
    yield 'confirmation'
    app.dialog = None

    from orion.victory import CampaignResult
    app.game.result, app.screen = CampaignResult('player', 'conquest', app.game.turn), 'result'
    yield 'result'
    app.game = campaign('observer')
    for tab in ('empires', 'diplomacy', 'research', 'fleets', 'objectives'):
        app.observer_tab, app.screen = tab, 'observer'
        yield 'observer_'+tab
    app.game = campaign('wanderers')
    from orion import motherships, hyperlanes
    app.open_mothership(motherships.homes(app.game)[0].id)
    yield 'mothership'
    app.screen = 'hyperlane'
    yield 'hyperlane'
    hyperlanes.start(app.game, app.game.selected_system)
    yield 'hyperlane_project'

    app.game = new_game(seed=2408, with_ai=False, fog_of_war=False)
    system, giant = next((s, p) for s in app.game.systems for p in s.worlds if p.is_gas_giant)
    app.game.selected_system, app.game.selected_planet = system.id, giant.id
    app.screen = 'planet'
    yield 'gas_giant'
    site = app.game.black_holes.sites[0]
    app.game.selected_system, app.game.selected_planet = site.system_id, None
    for screen in ('galaxy', 'system'):
        app.screen = screen
        yield 'black_hole_'+screen

    from tools.preview_council import campaign as council_campaign
    from orion import council
    app.game = council_campaign((2, 7, 2, 1, 1, 1))
    council.schedule(app.game)
    app.game.check_victory()
    app.screen = 'council'
    yield 'council_vote'

    from orion.combat_sandbox import build_game, Scenario, FleetSetup
    app.game = build_game(Scenario(player=FleetSetup(ships={'frigate': 2}), rival=FleetSetup(ships={'destroyer': 2})))
    app.reset_combat_view()
    app.sync_combat_selection()
    app.screen = 'combat'
    yield 'combat'
    ship, target = app.game.combat.ship(app.combat_ship_id), app.game.combat.ship(app.combat_target_id)
    ship.x, ship.y, target.x, target.y = 4, 4, 6, 4
    yield 'combat_in_range'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'screenshots'/'readability_v0860')
    parser.add_argument('--width', type=int, default=1440)
    parser.add_argument('--height', type=int, default=900)
    parser.add_argument('--scale', type=int, choices=(100, 125, 150, 175), default=100)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.window = pg.display.set_mode((args.width, args.height))
            app.settings['ui_scale'] = args.scale
            names = []
            for name in screen_states(app):
                app.render()
                app.present()
                pg.image.save(app.window, str(args.output/(name+'.png')))
                names.append(name)
            print(f'Rendered {len(names)} screen states to {args.output}')
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    main()
