"""Rectangular space, a small initial range, and fully random surroundings."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.model import GALAXY_SIZES, GameState, new_game
from orion.production import distance_ly
from orion.races import RACES


class RectangularGalaxyTests(unittest.TestCase):
    def test_each_races_initial_range_is_divided_by_five_and_research_still_adds_range(self):
        for race in RACES:
            game = new_game(seed=2408, race_id=race, rival_count=0)
            old_range = 50 if race == "wanderers" else 35
            multiplier = 1.5 if race == "varkesh" else 1
            self.assertEqual(game.fuel_range(), old_range/5*multiplier)
            game.research += 140
            game.choose_research("lightweight_alloys")
            self.assertEqual(game.fuel_range(), (old_range/5+10)*multiplier)
            game.choose_research("composite_structures")
            self.assertEqual(game.fuel_range(), (old_range/5+25)*multiplier)

    def test_starting_empires_do_not_relocate_or_terraform_surrounding_systems(self):
        for size in GALAXY_SIZES:
            for seed in (0, 2408, 116545103):
                with self.subTest(size=size, seed=seed):
                    solo = new_game(seed=seed, galaxy_size=size, rival_count=0, with_guardians=False)
                    crowded = new_game(seed=seed, galaxy_size=size, rival_count=5, with_guardians=False)
                    self.assertEqual([(s.x, s.y) for s in solo.systems],
                                     [(s.x, s.y) for s in crowded.systems])
                    homes = {crowded.headquarters(owner)[0].id for owner in crowded.owners}
                    for before, after in zip(solo.systems, crowded.systems):
                        if before.id not in homes:
                            self.assertEqual(before, after)
                    self.assertGreaterEqual(min(distance_ly(a, b) for i, a in enumerate(crowded.systems)
                                                for b in crowded.systems[i+1:]), 6-1e-9)
                    self.assertEqual(GameState.from_dict(crowded.to_dict()), crowded)

    def test_both_player_and_rivals_can_start_isolated(self):
        game = new_game(seed=0, galaxy_size="Compact", rival_count=5)
        for owner in game.owners:
            home = game.headquarters(owner)[0]
            self.assertFalse(any(game.within_fuel_range(s.id, owner)
                                 for s in game.systems if s.id != home.id), owner)

    def test_seed_changes_neighbor_count_and_does_not_guarantee_a_colonizable_world(self):
        counts, habitable = [], []
        for seed in (0, 2, 6, 8):
            game = new_game(seed=seed, rival_count=5)
            neighbors = [s for s in game.systems[1:] if game.within_fuel_range(s.id)]
            counts.append(len(neighbors))
            habitable.append(any(game.can_settle(p) for s in neighbors for p in s.worlds))
        self.assertEqual(counts, [0, 1, 1, 2])
        self.assertEqual(habitable, [False, False, True, True])

    def test_isolated_empires_can_research_tanks_without_moving_the_map(self):
        from orion.ai import research_choice, scouting_orders
        game = new_game(seed=0, rival_count=5)
        positions = [(s.x, s.y) for s in game.systems]
        for owner in game.opponents:
            scouting_orders(game, owner)
            self.assertTrue(all(not s.has_course for s in game.ships_owned_by(owner)))
            game.opponents[owner].research += 40
            research_choice(game, owner)
            self.assertIn("lightweight_alloys", game.research_state(owner).completed)
        game.research += 140
        game.choose_research("lightweight_alloys")
        game.choose_research("composite_structures")
        target = next(s for s in game.systems[1:] if game.within_fuel_range(s.id))
        game.send_ship(1, target.id)
        game.advance_turn()
        self.assertTrue(game.ship_at(1).in_transit)
        self.assertEqual([(s.x, s.y) for s in game.systems], positions)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_stars_and_player_homes_can_use_all_four_outer_corners(self):
        corners, home_corners = set(), set()
        for seed in range(32):
            game = new_game(seed=seed, galaxy_size="Compact", rival_count=0)
            for star in game.systems:
                self.assertTrue(0 < star.x < 1 and 0 < star.y < 1)
                if (star.x < .2 or star.x > .8) and (star.y < .2 or star.y > .8):
                    corner = (star.x > .5, star.y > .5)
                    corners.add(corner)
                    if star.id == 0:
                        home_corners.add(corner)
        self.assertEqual(corners, {(False, False), (False, True), (True, False), (True, True)})
        self.assertGreaterEqual(len(home_corners), 2)

    def test_same_seed_reproduces_the_complete_new_layout(self):
        a = new_game(seed=116545103, rival_count=5, galaxy_size="Expansive")
        b = new_game(seed=116545103, rival_count=5, galaxy_size="Expansive")
        first, second = a.to_dict(), b.to_dict()
        first.pop("campaign_id")
        second.pop("campaign_id")
        self.assertEqual(first, second)

    def test_starting_colony_ship_can_reach_and_settle_a_neighbour(self):
        game = new_game(seed=6, rival_count=5)  # A naturally colonizable neighbor.
        target, world = next((s, p) for s in game.systems[1:] if game.supply_distance(s.id) <= 7
                             for p in s.worlds if p.owner is None and game.can_settle(p))
        duration = game.send_ship(3, target.id)
        self.assertIn(duration, (3, 4))
        for _ in range(duration):
            game.advance_turn()
            self.assertIsNone(game.combat)
        self.assertEqual(game.ship_at(3).system_id, target.id)
        game.colonize(3, target.id, world.id)
        self.assertEqual(world.owner, "player")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class RectangularMapInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = new_game(seed=116545103, galaxy_size="Expansive", rival_count=5, fog_of_war=False)
        self.app.go("galaxy")
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def test_rectangular_map_names_fit_and_do_not_overlap_stars(self):
        from orion.app import MAP
        from orion.galaxy_fleet_view import fleet_markers, star_label_rects
        labels = list(star_label_rects(self.app, MAP).values())
        stars = [pg.Rect(round(x)-14, round(y)-14, 28, 28)
                 for x, y in (self.app.star_pos(s) for s in self.app.game.systems)]
        for index, label in enumerate(labels):
            self.assertTrue(MAP.contains(label))
            self.assertEqual(label.collidelist(stars), -1)
            self.assertEqual(label.collidelist(labels[index+1:]), -1)
        for ships, badge, anchor in fleet_markers(self.app, MAP):
            self.assertEqual(badge.collidelist(labels), -1)

    def test_map_accepts_a_local_course_and_blocks_a_distant_one(self):
        self.app.game = new_game(seed=8, rival_count=5, fog_of_war=False)
        self.app.go("galaxy")
        game = self.app.game
        near = next(s for s in game.systems[1:] if game.within_fuel_range(s.id))
        far = next(s for s in game.systems[1:] if not game.within_fuel_range(s.id))
        self.click("map_fleet_1")
        self.click(f"star_{near.id}")
        self.assertTrue(all(s.destination == near.id and s.departure_pending for s in game.ships_owned_by()))
        self.click("star_0")
        self.assertTrue(all(not s.has_course for s in game.ships_owned_by()))
        before = game.to_dict()
        self.click(f"star_{far.id}")
        self.assertEqual(game.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
