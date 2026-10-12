"""Expedition rules, one-time rewards, secrecy, migration and actual UI controls."""

import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import ai, black_holes, combat, council, exploration, monsters, news, sensors
from orion.model import GameState, RuleError, SaveError, Ship, new_game
from orion.research import ResearchState, TECHNOLOGIES, choices
from orion.storage import Storage


def campaign(**kwargs):
    return new_game(**dict(seed=42, with_ai=False, with_tombs=False, random_starts=False,
                           with_guardians=False, with_black_holes=True, **kwargs))


def research(game, tier=7, owner="player", alternative=False):
    for level in range(1, tier+1):
        identifier = choices("computers", level)[int(level == 6 and alternative)].id
        if identifier not in game.research_state(owner).completed:
            game._empire(owner).research += TECHNOLOGIES[identifier].cost
            game.choose_research(identifier, owner=owner)


def near(game, site, ly=6, origin=0):
    home, target = game.systems[origin], game.systems[site.system_id]
    target.x = home.x+ly/140 if home.x+ly/140 <= .98 else home.x-ly/140
    target.y = home.y


def fleet(game, sid, owner="player", count=8, kind="titan"):
    ships = [Ship(game.next_ship_id+i, kind, sid, owner=owner) for i in range(count)]
    game.next_ship_id += count
    game.ships.extend(ships)
    return ships


class BlackHoleRulesTests(unittest.TestCase):
    def test_new_galaxies_have_two_or_three_distinct_deterministic_sites(self):
        for size, count in (("Compact", 2), ("Standard", 3), ("Expansive", 3)):
            for seed in (0, 1, 42, 2408, 99999):
                with self.subTest(size=size, seed=seed):
                    game = new_game(seed=seed, galaxy_size=size, rival_count=5)
                    same = new_game(seed=seed, galaxy_size=size, rival_count=5)
                    self.assertEqual(game.black_holes, same.black_holes)
                    self.assertEqual(len(game.black_holes.sites), count)
                    for field in ("system_id", "kind", "relic_id"):
                        self.assertEqual(len({getattr(s, field) for s in game.black_holes.sites}), count)
                    homes = {0, *(e.home_system for e in game.opponents.values())}
                    for site in game.black_holes.sites:
                        system = game.systems[site.system_id]
                        self.assertNotIn(system.id, homes)
                        self.assertEqual((system.kind, system.planets, system.worlds), (black_holes.KIND, 0, []))
                        self.assertTrue(monsters.alive_at(game, system.id))
                        self.assertFalse(any(t.system_id == system.id for t in game.tomb_worlds))
                    self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_generation_preserves_homes_normal_guardians_and_solar_council_denominator(self):
        game = new_game(seed=42)
        original = new_game(seed=42, with_black_holes=False)
        self.assertEqual(len(game.systems), len(original.systems))
        for sid in (0, game.opponent.home_system):
            self.assertEqual(game.systems[sid], original.systems[sid])
        self.assertEqual([g for g in game.guardians if g.kind in monsters.PRIZE_WORLDS], original.guardians)
        self.assertEqual(council.solar_systems(game), len(game.systems)-3)

    def test_detection_is_required_even_without_fog_and_observer_sees_all(self):
        for fog in (True, False):
            game = campaign(fog_of_war=fog)
            site = game.black_holes.sites[0]
            self.assertNotIn(game.systems[site.system_id], black_holes.chart_systems(game))
            self.assertIsNone(game.known_system(site.system_id))
            self.assertIsNone(monsters.known_status(game, site.system_id))
            research(game, 6)
            self.assertIn(game.systems[site.system_id], black_holes.chart_systems(game))
            self.assertIsNone(monsters.known_status(game, site.system_id))
            self.assertFalse(game.system_explored(site.system_id))
        observer = new_game(seed=42, race_id="observer", rival_count=3)
        self.assertEqual(black_holes.chart_systems(observer), observer.systems)

    def test_research_alternatives_do_not_lock_out_navigation_and_mapping_reports_once(self):
        game = campaign()
        research(game, 6, alternative=True)
        self.assertFalse(black_holes.can_detect(game))
        research(game, 7, alternative=True)
        self.assertTrue(black_holes.can_detect(game))
        self.assertTrue(black_holes.can_explore(game))
        self.assertTrue(game.technology.has_unlock("gravitic_mapping"))
        self.assertEqual(len(game.black_holes.events), 3)
        black_holes.report_mapping(game, "player")
        self.assertEqual(len(game.black_holes.events), 3)
        self.assertEqual([len(choices("computers", t)) for t in (6, 7)], [2, 2])
        self.assertEqual([TECHNOLOGIES[k].cost for k in ("gravitic_mapping", "event_horizon_navigation")], [2160, 3040])

    def test_orders_are_atomic_and_unsafe_departure_can_be_cancelled(self):
        game = campaign()
        site = game.black_holes.sites[0]
        near(game, site)
        for accepted in (False, True):
            before = game.to_dict()
            with self.assertRaisesRegex(RuleError, "Gravitic Mapping"):
                game.send_ships([1, 2], site.system_id, accept_black_hole_risk=accepted)
            self.assertEqual(before, game.to_dict())
        research(game, 6)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "every ship"):
            game.send_ships([1, 2], site.system_id)
        self.assertEqual(before, game.to_dict())
        game.send_ships([1, 2], site.system_id, accept_black_hole_risk=True)
        game.cancel_departures([1, 2])
        self.assertEqual(game.to_dict(), before)

    def test_unsafe_arrival_destroys_only_the_expedition_without_revealing_guardian(self):
        game = campaign()
        site = game.black_holes.sites[0]
        near(game, site)
        research(game, 6)
        turns = game.send_ships([1, 2], site.system_id, accept_black_hole_risk=True)
        # Research finishing on the arrival turn is too late for this approach.
        game.choose_research("event_horizon_navigation")
        for index in range(turns):
            if index == turns-1:
                game.research = TECHNOLOGIES["event_horizon_navigation"].cost
            report = game.advance_turn()
        self.assertTrue(black_holes.can_explore(game))
        self.assertEqual([s.id for s in game.ships], [3])
        self.assertIsNone(game.combat)
        self.assertIsNone(monsters.known_status(game, site.system_id))
        self.assertEqual(game.black_holes.events[-1].ships, 2)
        self.assertTrue(any("ships lost" in line for line in report.alerts))
        self.assertEqual(report.arrivals, [])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_normal_route_crossing_black_hole_is_safe(self):
        game = campaign()
        site = game.black_holes.sites[0]
        near(game, site, 3)
        target = next(s for s in game.systems[1:] if s.kind != black_holes.KIND)
        target.x, target.y = game.systems[0].x+6/140, game.systems[0].y
        turns = game.send_ship(1, target.id)
        for _ in range(turns):
            game.advance_turn()
        self.assertEqual(game.ship_at(1).system_id, target.id)
        self.assertEqual(game.black_holes.events, [])

    def test_safe_arrival_battles_and_awards_one_relic_after_real_combat(self):
        for kind in black_holes.SITES:
            with self.subTest(kind=kind):
                game = campaign()
                research(game)
                site = next(s for s in game.black_holes.sites if s.kind == kind)
                near(game, site)
                ships = fleet(game, 0)
                turns = game.send_ships([s.id for s in ships], site.system_id)
                game = GameState.from_dict(game.to_dict())
                site = black_holes.at(game, site.system_id)
                for _ in range(turns):
                    game.advance_turn()
                self.assertEqual(game.combat.system_id, site.system_id)
                self.assertIsNone(site.claimed_by)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)
                combat.autoresolve(game)
                self.assertEqual(game.combat.status, "player_victory")
                self.assertEqual(site.claimed_by, "player")
                self.assertEqual(len(black_holes.collection(game)), 1)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)
                game.finish_combat()
                before = copy.deepcopy(game.black_holes)
                guardian = monsters.at(game, site.system_id)
                self.assertIsNone(monsters.commit_battle_result(game, guardian, 0, "player"))
                self.assertFalse(monsters.intercept(game))
                self.assertEqual(game.black_holes, before)

    def test_retreat_and_defeat_do_not_award_relic_and_damage_persists(self):
        game = campaign()
        research(game)
        site = game.black_holes.sites[0]
        near(game, site)
        game.ship_at(1).system_id = site.system_id
        combat.begin_guardian_combat(game, site.system_id)
        game.combat.guardian.hull -= 10
        combat.retreat(game)
        self.assertIsNone(site.claimed_by)
        self.assertEqual(monsters.at(game, site.system_id).hull, game.combat.guardian.initial_hull-10)
        self.assertNotEqual(game.systems[game.combat.retreat_destination].kind, black_holes.KIND)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.finish_combat()
        game.ship_at(2).system_id = site.system_id
        combat.begin_guardian_combat(game, site.system_id)
        # Resolve an actual lethal hit against the unarmed expedition.
        unit = game.combat.fleet("player")[0]
        unit.hull = 0
        combat.check_losses(game)
        self.assertEqual(game.combat.status, "monster_victory")
        self.assertIsNone(site.claimed_by)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_only_launches_prepared_expeditions_and_can_claim_relics(self):
        game = new_game(seed=42, with_tombs=False, random_starts=False)
        site = game.black_holes.sites[0]
        owner, home = "rival", game.opponent.home_system
        near(game, site, origin=home)
        ships = fleet(game, home, owner)
        with patch.object(game, "send_ship", wraps=game.send_ship) as send:
            ai.scouting_orders(game, owner)
            self.assertNotIn(site.system_id, [call.args[1] for call in send.call_args_list])
        research(game, 6, owner)
        monsters.ai_orders(game, owner)
        self.assertTrue(all(s.destination != site.system_id for s in ships))
        research(game, 7, owner)
        monsters.ai_orders(game, owner)
        self.assertTrue(all(s.destination == site.system_id for s in ships))
        for ship in ships:
            game._clear_course(ship)
            ship.system_id = site.system_id
        monsters.intercept(game)
        self.assertEqual(site.claimed_by, owner)
        self.assertFalse(black_holes.events(game))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_fleet_and_sensor_views_do_not_reveal_hidden_endpoints(self):
        game = new_game(seed=42, with_tombs=False, fog_of_war=False)
        site = game.black_holes.sites[0]
        ship = fleet(game, site.system_id, "rival", count=1)[0]
        self.assertNotIn(ship, game.visible_ships())
        self.assertEqual(sensors.detection_level(game, ship), 0)
        research(game, 6)
        self.assertIn(ship, game.visible_ships())
        self.assertIsNone(monsters.known_status(game, site.system_id))

    def test_news_is_private_persistent_and_has_read_markers(self):
        game = campaign()
        research(game, 6)
        self.assertEqual(news.unread_count(game), 3)
        self.assertEqual(len(news.entries(game)), 3)
        news.mark_read(game)
        self.assertEqual(news.unread_count(game), 0)
        with tempfile.TemporaryDirectory() as d:
            storage = Storage(d)
            self.assertEqual(storage.load(storage.save(game))[0], game)

    def test_v33_migration_preserves_every_world_and_old_ascension_goal(self):
        game = new_game(seed=42, with_black_holes=False)
        data = game.to_dict()
        data.pop("black_holes")
        for empire in (data, data["opponent"], *data["other_opponents"].values()):
            empire["technology"].pop("legacy_black_holes")
        restored = GameState.from_dict(data, version=33)
        self.assertEqual(restored.systems, game.systems)
        self.assertEqual(restored.black_holes.sites, [])
        self.assertEqual(restored.technology.required_tiers("computers"), (1, 2, 3, 4, 5))
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)
        self.assertEqual(ResearchState().required_tiers("computers"), tuple(range(1, 8)))

    def test_invalid_sites_claims_events_and_guardians_are_rejected(self):
        game = campaign()
        site = game.black_holes.sites[0]
        mutations = (
            lambda d: d["black_holes"]["sites"][0].update(relic_id="unknown"),
            lambda d: d["black_holes"]["sites"][0].update(system_id=0),
            lambda d: d["black_holes"]["sites"][1].update(relic_id=site.relic_id),
            lambda d: d["black_holes"]["sites"][0].update(claimed_by="player", recovered_turn=1),
            lambda d: d["black_holes"].update(sites=[]),
            lambda d: d["black_holes"].update(news_read=1),
            lambda d: d["guardians"][0].update(hull=0),
            lambda d: d["guardians"][0].update(planet_id=0),
            lambda d: d["systems"][site.system_id].update(planets=1),
            lambda d: d["black_holes"]["events"].append(dict(id=1, owner="rival", system_id=site.system_id, turn=1, kind="mapped", ships=0)),
        )
        for mutation in mutations:
            data = game.to_dict()
            mutation(data)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class BlackHoleInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign()
        self.app.game.choose_research("ion_drives")
        self.app.go("galaxy")
        self.app.render()
        self.app.present()

    def click(self, key):
        app = self.app
        app.render()
        button = next(b for b in app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        view = app.viewport
        x, y = button.rect.center
        pos = round(view.x+x*view.w/1440), round(view.y+y*view.h/900)
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            app.render()

    def test_hidden_sites_have_no_labels_hit_targets_or_hover_destinations(self):
        from orion.app import MAP
        from orion.galaxy_fleet_view import star_label_rects
        app, game = self.app, self.app.game
        for site in game.black_holes.sites:
            self.assertNotIn(site.system_id, star_label_rects(app, MAP))
            self.assertNotIn(f"star_{site.system_id}", {b.key for b in app.buttons})
            app.mouse = app.star_pos(game.systems[site.system_id])
            app.keyboard_mode = False
            self.assertNotEqual(app.fleet_route_target(), site.system_id)
            app.select_star(site.system_id)
            app.open_system(site.system_id)
            self.assertEqual(game.selected_system, 0)

    def test_fatal_confirmation_cancel_accept_and_pending_cancel(self):
        app, game = self.app, self.app.game
        research(game, 6)
        site = game.black_holes.sites[0]
        near(game, site)
        self.click("map_fleet_1")
        self.click(f"star_{site.system_id}")
        self.assertIn("every ship", app.dialog["body"])
        self.assertTrue(all(not s.has_course for s in game.ships))
        self.click("dialog_cancel")
        self.assertTrue(all(not s.has_course for s in game.ships))
        self.click(f"star_{site.system_id}")
        self.click("dialog_ok")
        self.assertTrue(all(s.departure_pending for s in game.ships))
        self.assertEqual({s.destination for s in game.ships}, {site.system_id})
        self.click("star_0")
        self.assertTrue(all(not s.has_course for s in game.ships))

    def test_detail_panel_navigation_research_and_recovered_article(self):
        app, game = self.app, self.app.game
        research(game, 6)
        site = game.black_holes.sites[0]
        self.click(f"star_{site.system_id}")
        self.click("black_hole_navigation")
        self.assertEqual((app.screen, app.research_branch, app.research_tier), ("research", "computers", 7))
        research(game)
        app.go("galaxy")
        monsters.commit_battle_result(game, monsters.at(game, site.system_id), 0, "player")
        app.render()
        before = game.to_dict()
        self.click("black_hole_relic")
        self.assertEqual(app.info_article, "artifact_"+site.relic_id)
        self.assertEqual(app.screen, "info")
        self.assertEqual(game.to_dict(), before)

    def test_observer_and_all_three_site_panels_render_with_both_backgrounds(self):
        app = self.app
        app.game = new_game(seed=42, race_id="observer", rival_count=3)
        for background in (True, False):
            app.settings["galaxy_background"] = background
            for site in app.game.black_holes.sites:
                app.open_system(site.system_id)
                app.render()
                self.assertEqual(app.screen, "galaxy")
                self.assertIn("black_hole_guide", {b.key for b in app.buttons})


if __name__ == "__main__":
    unittest.main()
