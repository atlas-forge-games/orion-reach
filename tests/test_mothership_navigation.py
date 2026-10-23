"""Mothership range, live system ownership and clickable orbital habitats."""

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from test_motherships import campaign, target, advance
from orion import combat, exploration, motherships
from orion.model import GameState, RuleError, Ship, generate_planets
from scenarios import research_to


class MothershipRangeTests(unittest.TestCase):
    def test_twenty_five_ly_convoy_boundary_and_independent_escorts(self):
        game = campaign()
        home = motherships.homes(game)[0]
        escorts = [s for s in game.ships if s.habitat is None]
        dest = target(game, 25)
        self.assertEqual(game.fuel_range(ships=[home]), 25)
        self.assertEqual(game.fuel_range(ships=escorts), 20)
        self.assertFalse(game.within_fuel_range(dest.id, ships=escorts))
        with self.assertRaisesRegex(RuleError, 'fuel range'):
            game.send_ships([s.id for s in escorts], dest.id)
        game.send_ships([s.id for s in game.ships], dest.id)
        self.assertEqual({s.travel_total for s in game.ships}, {50})
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        target(game, 25.001)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, 'range 25 ly'):
            game.send_ships([s.id for s in game.ships], dest.id)
        self.assertEqual(game.to_dict(), before)

    def test_reserves_do_not_stack_and_research_still_increases_range(self):
        game = campaign()
        motherships.create(game, 0, 'player')
        homes = motherships.homes(game)
        self.assertEqual(game.fuel_range(ships=homes), 25)
        research_to(game, 'cryogenic_fuel_tanks')
        self.assertGreater(game.fuel_range(ships=homes), 25)
        self.assertEqual(game.fuel_range(ships=homes), game.fuel_range()+15)

    def test_ai_relocation_uses_mothership_range(self):
        game = campaign(race_id='terran', with_ai=True, rival_race_id='wanderers')
        home = motherships.homes(game, 'rival')[0]
        origin = game.systems[home.system_id]
        dest = next(s for s in game.systems if s.id not in (0, origin.id))
        dest.x, dest.y = origin.x+20/140, origin.y
        exploration.record_survey(game, dest.id, 'rival')
        motherships.create(game, origin.id, 'rival')
        self.assertFalse(game.within_fuel_range(dest.id, 'rival'))
        motherships.ai_orders(game, 'rival')
        self.assertTrue(any(s.destination == dest.id for s in motherships.homes(game, 'rival')))

    def test_retreat_uses_reserves_only_while_a_mothership_survives(self):
        game = campaign(with_ai=True, rival_race_id='terran')
        dest = target(game, 23)
        for system in game.systems[2:]:
            system.x, system.y = game.systems[0].x+.5, game.systems[0].y
        enemy = Ship(game.next_ship_id, 'frigate', 0, owner='rival')
        game.next_ship_id += 1
        game.ships.append(enemy)
        game.start_combat(0, owner='rival', target='player')
        self.assertEqual(combat.retreat_destination(game).id, dest.id)
        home = motherships.homes(game, 'player')[0]
        game.combat.ship(home.id).hull = 0
        self.assertIsNone(combat.retreat_destination(game))


class MothershipSystemTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign()
        self.home = motherships.homes(self.app.game)[0]
        self.home.habitat.trade_goods = True
        self.app.go('galaxy')
        self.app.present()

    def click(self, key):
        import pygame as pg
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        v = self.app.viewport
        x, y = button.rect.center
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def drawn_text(self):
        from orion.ui import text_image
        with patch('orion.ui.text_image', wraps=text_image) as drawn:
            self.app.render()
        return '\n'.join(str(c.args[0]) for c in drawn.call_args_list)

    def test_system_home_is_clickable_and_returns_to_system_with_population(self):
        self.app.open_system(0)
        drawn = self.drawn_text()
        self.assertIn('HABITATS', drawn)
        self.assertIn('8 B', drawn)
        self.click(f'system_mothership_{self.home.id}')
        self.assertEqual(self.app.screen, 'planet')
        self.assertEqual(self.app.game.selected_planet, self.home.habitat.id)
        self.click('planet_return')
        self.assertEqual(self.app.screen, 'system')

    def test_sidebar_pages_include_homes_and_preserve_planet_return(self):
        self.click(f'galaxy_mothership_{self.home.id}')
        self.click('planet_return')
        self.assertEqual(self.app.screen, 'galaxy')
        self.assertEqual(self.app.focus, f'galaxy_mothership_{self.home.id}')
        self.click('galaxy_planets_next')
        self.click('galaxy_world_3')
        self.click('planet_return')
        self.assertEqual(self.app.galaxy_planet_page, 1)
        self.assertEqual(self.app.focus, 'galaxy_world_3')

    def test_crowded_system_has_separate_planet_and_home_targets_and_home_pages(self):
        game = self.app.game
        system = game.systems[0]
        system.planets = 8
        system.worlds = generate_planets(system, game.seed)
        for _ in range(5):
            motherships.create(game, 0, 'player')
        self.app.open_system(0)
        self.app.render()
        buttons = [b for b in self.app.buttons if b.key.startswith(('world_', 'system_mothership_'))]
        self.assertEqual(len(buttons), 12)
        for i, button in enumerate(buttons):
            self.assertEqual(button.rect.collidelist([b.rect for b in buttons[i+1:]]), -1)
        self.click('system_motherships_next')
        homes = [b for b in self.app.buttons if b.key.startswith('system_mothership_')]
        self.assertEqual(len(homes), 2)
        self.click(homes[-1].key)
        self.assertEqual(game.selected_planet, game.ships[-1].habitat.id)

    def test_ownership_moves_on_departure_and_arrival_and_preserves_shared_colors(self):
        from orion.galaxy_labels import known_owners, label_bands
        game = self.app.game
        origin, dest = game.systems[0], target(game)
        self.app.render()
        self.assertEqual(known_owners(game, origin), ('player',))
        self.assertEqual(label_bands(game, origin)[1][0][2], self.app.empire_color('player'))
        x, y = map(int, self.app.star_pos(origin))
        self.assertEqual(tuple(self.app.canvas.get_at((x+10, y)))[:3], self.app.empire_color('player'))
        game.send_ships([s.id for s in game.ships], dest.id)
        self.assertEqual(known_owners(game, origin), ('player',))
        advance(game)
        self.assertEqual(known_owners(game, origin), ())
        self.assertEqual(known_owners(game, dest), ())
        for _ in range(self.home.turns_remaining):
            advance(game)
        self.assertEqual(known_owners(game, dest), ('player',))

    def test_unknown_foreign_homes_stay_hidden_and_shared_systems_keep_both_owners(self):
        from orion.galaxy_labels import known_owners
        game = self.app.game = campaign(race_id='terran', with_ai=True, rival_race_id='wanderers')
        home = motherships.homes(game, 'rival')[0]
        remote = game.systems[home.system_id]
        self.assertEqual(known_owners(game, remote), ())
        scout = game.ships_owned_by()[0]
        scout.system_id = remote.id
        exploration.refresh(game)
        self.assertEqual(known_owners(game, remote), ('rival',))
        scout.system_id = 0
        self.assertEqual(known_owners(game, remote), ())
        home.system_id = 0
        self.assertEqual(known_owners(game, game.systems[0]), ('player', 'rival'))

    def test_route_display_tracks_selection_and_map_badge_omits_population(self):
        from orion.galaxy_fleet_view import draw_map_fleets
        from orion.app import MAP
        with patch('orion.galaxy_fleet_view.text') as drawn:
            draw_map_fleets(self.app, MAP)
        labels = [str(c.args[1]) for c in drawn.call_args_list]
        self.assertTrue(labels)
        self.assertFalse(any('/50' in s or s.endswith(' B') for s in labels))
        dest = target(self.app.game, 22)
        self.app.open_map_fleet(self.home.id)
        self.app.game.selected_system = dest.id
        self.assertIn('RANGE 25 LY', self.drawn_text())
        self.click(f'fleet_select_{self.home.id}')
        self.assertIn('RANGE 20 LY', self.drawn_text())
        self.assertIn('Out of range', self.drawn_text())
        self.app.open_mothership(self.home.id)
        self.click('mothership_course')
        self.app.select_star(dest.id)
        self.app.render()
        self.assertTrue(next(b for b in self.app.buttons if b.key == 'send_course').enabled)
        self.assertIn('RANGE 25 LY', self.drawn_text())


if __name__ == '__main__':
    unittest.main()
