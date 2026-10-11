"""Fleet splitting, complete movement orders, and real galaxy-map input flows."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.fleets import fleet_containing, group_fleets
from orion.model import PLAYER, RIVAL, GameState, RuleError, Ship
from scenarios import fixed_start_game as new_game, use_nearby_system
from functools import partial

# Preserve these pre-exploration scenarios; fog-on rules have their own tests.
new_game = partial(new_game, fog_of_war=False)
from orion.research import TECHNOLOGIES
from orion.storage import Storage


def fixture(*, ai=False):
    game = new_game(seed=2408, with_ai=ai, with_guardians=False)
    use_nearby_system(game, 1)
    use_nearby_system(game, 11, excluding=(1,))
    game.ships = [Ship(1, "frigate", 0, hull=15), Ship(2, "frigate", 0),
                  Ship(3, "colony_ship", 0), Ship(4, "troop_transport", 0)]
    game.next_ship_id = 5
    return game


class FleetOrderTests(unittest.TestCase):
    def test_subset_departs_together_and_arrival_merges_with_destination_fleet(self):
        game = fixture()
        game.ships.append(Ship(5, "frigate", 1))
        game.next_ship_id = 6
        duration = game.send_ships([1, 3], 1)
        self.assertEqual([(s.id, s.destination) for s in game.ships], [(1, 1), (2, None), (3, 1), (4, None), (5, None)])
        self.assertEqual(game.ship_at(1).turns_remaining, duration)
        self.assertEqual(game.ship_at(3).travel_total, duration)
        self.assertEqual(game.ship_at(1).hull, 15)
        self.assertEqual([s.id for s in fleet_containing(game.ships, 1)], [1, 3])
        for _ in range(duration):
            game.advance_turn()
        self.assertEqual([s.id for s in fleet_containing(game.ships, 1)], [1, 3, 5])
        self.assertEqual([s.id for s in game.fleet_at(0)], [2, 4])

    def test_invalid_member_never_sends_part_of_the_selection(self):
        game = fixture(ai=True)
        game.ships += [Ship(5, "frigate", 0, owner=RIVAL), Ship(6, "frigate", 1)]
        game.next_ship_id = 7
        game.send_ship(4, 1)
        game.ship_at(4).departure_pending = False  # An already committed flight.
        for identifiers, destination in (([], 1), ([1, 99], 1), ([1, 5], 1), ([1, 4], 1),
                                         ([1, 6], 2), ([1, 1], 1), ([1, True], 1),
                                         ([1, "2"], 1), ([1, 2], 0), ([1, 2], -1),
                                         ([1, 2], True), ([1, 2], 900)):
            with self.subTest(ids=identifiers, destination=destination):
                before = game.to_dict()
                with self.assertRaises(RuleError):
                    game.send_ships(identifiers, destination)
                self.assertEqual(game.to_dict(), before)

    def test_rival_orders_and_combat_lock_apply_to_the_whole_group(self):
        game = fixture(ai=True)
        game.ships += [Ship(5, "frigate", 0, owner=RIVAL), Ship(6, "colony_ship", 0, owner=RIVAL)]
        game.next_ship_id = 7
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.send_ships([5, 6], 1)
        self.assertEqual(before, game.to_dict())
        game.start_combat(0)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "battle"):
            game.send_ships([1, 2], 1)
        self.assertEqual(before, game.to_dict())
        game = fixture(ai=True)
        game.ships = [Ship(1, "frigate", 0, owner=RIVAL), Ship(2, "colony_ship", 0, owner=RIVAL)]
        from scenarios import place_near
        place_near(game, game.opponent.home_system, anchor=1)
        game.send_ships([1, 2], 1, owner=RIVAL)
        self.assertTrue(all(s.destination == 1 for s in game.ships))

    def test_separate_voyages_do_not_merge_until_arrival(self):
        game = fixture()
        destination = max((s for s in game.systems[1:] if game.within_fuel_range(s.id)), key=lambda s: game.travel_turns(game.systems[0], s))
        game.send_ships([1, 2], destination.id)
        game.advance_turn()
        game.send_ships([3, 4], destination.id)
        self.assertEqual([[s.id for s in group] for group in group_fleets(game.ships)], [[1, 2], [3, 4]])
        self.assertEqual(fleet_containing(game.ships, 999), [])

    def test_group_orders_keep_speed_snapshot_damage_and_save_compatibility(self):
        game = fixture()
        speed_tech = next(t for t in TECHNOLOGIES.values() if t.tier == 1 and dict(t.effects).get("ship_speed"))
        game.research = speed_tech.cost
        game.choose_research(speed_tech.id)
        destination = max((s for s in game.systems[1:] if game.within_fuel_range(s.id)), key=lambda s: game.travel_turns(game.systems[0], s))
        duration = game.send_ships([1, 2, 3], destination.id)
        self.assertTrue(all(s.speed_bonus == dict(speed_tech.effects)["ship_speed"] for s in game.ships[:3]))
        game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored, _ = store.load(store.save(game))
        self.assertEqual(restored, game)
        self.assertEqual(restored.ship_at(1).hull, 15)
        self.assertEqual(restored.ship_at(1).turns_remaining, duration-1)
        self.assertEqual([s.id for s in fleet_containing(restored.ships, 2)], [1, 2, 3])
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)


class GalaxyFleetInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.game = fixture()
        self.app.go("galaxy")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.render()
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.click_position(button.rect.center)

    def click_position(self, point):
        x, y = point
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def test_click_fleet_select_subset_and_send_with_one_destination_click(self):
        self.click("map_fleet_1")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertTrue(self.app.fleet_popup)
        self.assertEqual(self.app.fleet_selected_ids, {1, 2, 3, 4})
        self.click("fleet_select_2")
        self.click("fleet_select_4")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.map_order_ids, (1, 3))
        self.assertTrue(all(not s.in_transit for s in self.app.game.ships))
        self.click("star_1")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.map_order_ids, (1, 3))
        self.assertEqual([s.id for s in self.app.game.ships if s.departure_pending], [1, 3])
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, self.app.game)
        self.assertTrue(any(b.key == "map_fleet_2" for b in self.app.buttons))
        self.click("fleet_popup_close")
        self.click("star_1")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.game.selected_system, 1)

    def test_hover_and_close_never_issue_orders(self):
        self.click("map_fleet_1")
        self.click("fleet_select_4")
        before = [s.__dict__.copy() for s in self.app.game.ships]
        x, y = self.app.star_pos(self.app.game.systems[1])
        v = self.app.viewport
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=(round(v.x+x*v.w/1440), round(v.y+y*v.h/900)), rel=(0, 0), buttons=(0, 0, 0)))
        self.app.render()
        self.assertEqual(self.app.fleet_route_target(), 1)
        self.assertEqual(before, [s.__dict__ for s in self.app.game.ships])
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "galaxy")
        self.assertFalse(self.app.fleet_popup)
        self.assertEqual(self.app.map_order_ids, ())
        self.click("map_fleet_1")
        self.click("cancel_fleet_course")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(before, [s.__dict__ for s in self.app.game.ships])

    def test_origin_click_and_empty_space_do_not_issue_order(self):
        self.click("map_fleet_1")
        self.click("star_0")
        self.assertTrue(self.app.map_order_ids)
        self.assertFalse(self.app.notice_error)
        self.click_position((78, 739))
        self.assertFalse(self.app.fleet_popup)
        self.assertTrue(all(not s.in_transit for s in self.app.game.ships))
        self.click("map_fleet_1")
        self.click("star_1")
        self.assertTrue(all(s.departure_pending for s in self.app.game.ships))

    def test_all_none_and_selection_across_manifest_pages(self):
        self.app.game.ships = [Ship(i, "frigate", 0) for i in range(1, 15)]
        self.app.game.next_ship_id = 15
        self.click("map_fleet_1")
        self.click("fleet_select_none")
        self.assertFalse(self.app.map_order_ids)
        self.click("star_1")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertTrue(all(not s.has_course for s in self.app.game.ships))
        self.click("fleet_select_2")
        self.key(pg.K_PAGEDOWN)
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.fleet_selected_ids, {2, 7})
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=-1, x=0))
        self.app.render()
        self.click("fleet_select_14")
        self.assertEqual(self.app.fleet_selected_ids, {2, 7, 14})
        self.key(pg.K_RIGHT)
        self.key(pg.K_RETURN)
        self.assertEqual([s.id for s in self.app.game.ships if s.departure_pending], [2, 7, 14])
        self.click("map_fleet_1")
        self.click("fleet_select_all")
        self.assertEqual(len(self.app.fleet_selected_ids), 11)

    def test_rival_and_transit_fleets_are_inspection_only(self):
        self.app.game = fixture(ai=True)
        self.app.game.ships += [Ship(5, "frigate", 0, owner=RIVAL)]
        self.app.game.next_ship_id = 6
        self.click("map_fleet_5")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertFalse(self.app.fleet_selected_ids)
        self.assertFalse(any(b.key == "fleet_choose_destination" for b in self.app.buttons))
        self.assertFalse(any(b.key == "fleet_select_all" for b in self.app.buttons))
        self.assertFalse(self.app.fleet_selected_ids)
        self.key(pg.K_ESCAPE)
        self.app.game.send_ships([1, 2], 1)
        self.app.game.advance_turn()
        self.click("map_fleet_1")
        self.assertFalse(self.app.fleet_selected_ids)
        self.assertFalse(any(b.key.startswith("fleet_select_") and b.enabled for b in self.app.buttons))

    def test_unissued_order_is_not_saved_or_replayed_after_navigation_or_end_turn(self):
        self.click("map_fleet_1")
        self.key(pg.K_F5)
        path = next(self.app.storage.saves_dir.glob("*.json"))
        self.app.load_game(path)
        self.app.render()
        self.assertFalse(self.app.map_order_ids)
        self.assertTrue(all(not s.in_transit for s in self.app.game.ships))
        self.click("map_fleet_1")
        self.key(pg.K_r)
        self.assertFalse(self.app.map_order_ids)
        self.key(pg.K_ESCAPE)
        self.click("star_1")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.game.selected_system, 1)
        self.click("map_fleet_1")
        self.key(pg.K_e)
        self.assertFalse(self.app.map_order_ids)
        self.assertTrue(all(not s.in_transit for s in self.app.game.ships))

    def test_transit_manifest_tracks_arrival_and_requires_fresh_selection(self):
        duration = self.app.game.send_ships([1, 2], 1)
        self.app.game.advance_turn()
        self.click("map_fleet_1")
        self.assertFalse(self.app.fleet_selected_ids)
        for _ in range(duration-1):
            self.key(pg.K_e)
        self.click("research_back")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertFalse(self.app.fleet_popup)
        self.click("map_fleet_1")
        self.assertEqual([s.id for s in self.app.viewed_fleet()], [1, 2])
        self.assertEqual(self.app.fleet_selected_ids, {1, 2})
        self.click("star_0")
        self.assertEqual(self.app.game.ship_at(1).destination, 0)

    def test_dense_map_badges_remain_inside_map_and_clear_of_stars_and_other_badges(self):
        from orion.app import MAP
        from orion.galaxy_fleet_view import fleet_markers, star_label_rects
        for seed in (0, 2408, 100):
            game = new_game(seed=seed, galaxy_size="Expansive")
            game.ships = [Ship(i+1, "frigate", system.id, owner=owner)
                          for i, (system, owner) in enumerate((s, o) for s in game.systems for o in (PLAYER, RIVAL))]
            self.app.game = game
            markers = fleet_markers(self.app, MAP)
            self.assertEqual(len(markers), 144)
            rects = [rect for _, rect, _ in markers]
            labels = list(star_label_rects(self.app, MAP).values())
            stars = [pg.Rect(int(x)-18, int(y)-18, 36, 36)
                     for x, y in (self.app.star_pos(s) for s in game.systems)]
            for index, rect in enumerate(rects):
                self.assertTrue(MAP.contains(rect))
                self.assertEqual(rect.collidelist(stars), -1)
                self.assertEqual(rect.collidelist(labels), -1)
                self.assertEqual(rect.collidelist(rects[:index]), -1)

    def test_clicking_origin_cancels_selected_departures_and_preserves_unselected_ships(self):
        from orion.app import MAP
        self.click("map_fleet_1")
        self.assertFalse(self.app.fleet_popup_rect.colliderect(MAP))
        self.click("fleet_select_2")
        self.click("fleet_select_4")
        self.click("star_1")
        self.assertEqual([s.id for s in self.app.game.ships if s.departure_pending], [1, 3])
        self.click("star_0")
        self.assertTrue(all(not s.has_course for s in self.app.game.ships))
        self.assertEqual(self.app.fleet_selected_ids, {1, 3})
        self.assertEqual([s.id for s in self.app.viewed_fleet()], [1, 2, 3, 4])
        self.key(pg.K_e)
        self.click("research_back")
        self.assertTrue(all(s.system_id == 0 for s in self.app.game.ships))
        self.assertEqual(self.app.screen, "galaxy")
        self.assertFalse(self.app.fleet_popup)

    def test_closing_or_switching_popups_keeps_orders_and_reload_allows_cancellation(self):
        self.click("map_fleet_1")
        self.click("fleet_select_none")
        self.click("fleet_select_1")
        self.click("star_1")
        self.click("map_fleet_2")
        self.click("star_11")
        self.key(pg.K_ESCAPE)
        self.assertTrue(all(s.departure_pending for s in self.app.game.ships))
        save = self.app.storage.saves_dir/"autosave.json"
        self.app.load_game(save)
        self.app.render()
        self.assertFalse(self.app.fleet_popup)
        self.click("map_fleet_1")
        self.click("star_0")
        self.assertFalse(self.app.game.ship_at(1).has_course)
        self.assertTrue(all(self.app.game.ship_at(i).destination == 11 for i in (2, 3, 4)))


if __name__ == "__main__":
    unittest.main()
