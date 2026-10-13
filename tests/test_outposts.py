"""Outpost lifecycle, supply, fog, attacks and the actual planet controls."""
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame as pg

from orion import balance, outposts, exploration, specialists
from orion.model import new_game, Ship, GameState, RuleError, SaveError
from orion.production import SHIP_TYPES
from orion.storage import Storage, SAVE_VERSION


def campaign(**kwargs):
    return new_game(seed=12, galaxy_size="Compact", random_starts=False, with_guardians=False,
                    with_tombs=False, with_black_holes=False, **kwargs)


def add_ship(game, kind, sid, owner="player"):
    ship = Ship(game.next_ship_id, kind, sid, owner=owner)
    game.next_ship_id += 1
    game.ships.append(ship)
    return ship


class OutpostRulesTests(unittest.TestCase):
    def setUp(self):
        previous = balance.active_profile()
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(previous))
        self.game = campaign()
        self.system = next(s for s in self.game.systems[1:] if s.worlds and not any(p.colonized for p in s.worlds))
        self.planet = self.system.worlds[0]

    def deploy(self, owner="player"):
        ship = add_ship(self.game, "outpost_ship", self.system.id, owner)
        outposts.deploy(self.game, ship.id, self.system.id, self.planet.id, owner)
        return ship

    def test_costs_and_actual_construction(self):
        self.assertEqual((SHIP_TYPES["colony_ship"].resource_cost, SHIP_TYPES["colony_ship"].work_cost), (800, 420))
        self.assertEqual((SHIP_TYPES["outpost_ship"].resource_cost, SHIP_TYPES["outpost_ship"].work_cost), (80, 42))
        game = self.game
        game.credits = 10000
        game.resources = 1000
        for kind, cost in (("colony_ship", 800), ("outpost_ship", 80)):
            before = game.resources
            game.queue_ship(0, 2, kind)
            self.assertEqual(game.planet_at(0, 2).construction_queue[0].resource_cost, cost)
            game.buy_construction(0, 2)
            self.assertEqual(game.resources, before-cost)
            self.assertEqual(game.ships[-1].kind, kind)

    def test_deploy_consumes_ship_observes_system_and_has_no_economic_output(self):
        game = self.game
        self.planet.biome = "Volcanic"
        rates = game.empire_rates, game.resource_rate(), len(game.colony_systems())
        ship = self.deploy()
        self.assertNotIn(ship, game.ships)
        self.assertEqual((self.planet.owner, self.planet.colonized, self.planet.population), (None, False, 0))
        self.assertEqual(self.planet.outpost_hull, outposts.OUTPOST_HULL)
        self.assertEqual((game.empire_rates, game.resource_rate(), len(game.colony_systems())), rates)
        self.assertEqual(game.planet_yields(self.planet), (0, 0, 0))
        self.assertTrue(game.system_visible(self.system.id))
        self.assertIsNotNone(game.ship_build_error(self.system.id, self.planet.id, "scout"))

    def test_supply_uses_union_and_does_not_bridge_the_gap_or_supply_rivals(self):
        game = self.game
        home = game.systems[0]
        home.x, home.y = .2, .3
        self.system.x, self.system.y = .2+6/140, .3
        remote = next(s for s in game.systems if s.id not in (0, self.system.id, game.opponent.home_system))
        remote.x, remote.y = .2+12/140, .3
        self.assertFalse(game.within_fuel_range(remote.id))
        rival_range = game.within_fuel_range(remote.id, "rival")
        self.deploy()
        self.assertTrue(game.within_fuel_range(remote.id))
        self.assertEqual(game.within_fuel_range(remote.id, "rival"), rival_range)
        remote.x = .2+13.01/140
        self.assertFalse(game.within_fuel_range(remote.id))
        outposts.clear(self.planet)
        self.assertTrue(game.within_fuel_range(self.system.id))  # Original frontier remains reachable.
        remote.x = .2+12/140
        self.assertFalse(game.within_fuel_range(remote.id))

    def test_only_one_outpost_for_all_empires_in_a_system_and_rejections_are_atomic(self):
        self.deploy()
        for owner in self.game.owners:
            ship = add_ship(self.game, "outpost_ship", self.system.id, owner)
            before = self.game.to_dict()
            with self.assertRaisesRegex(RuleError, "one outpost"):
                outposts.deploy(self.game, ship.id, self.system.id, self.planet.id, owner)
            self.assertEqual(self.game.to_dict(), before)

    def test_deployment_requires_correct_owned_ship_and_uncolonized_planet(self):
        game = self.game
        ship = add_ship(game, "outpost_ship", 0)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "uncolonized"):
            outposts.deploy(game, ship.id, 0, 2)
        self.assertEqual(game.to_dict(), before)
        with self.assertRaises(RuleError):
            outposts.deploy(game, ship.id, self.system.id, self.planet.id)
        with self.assertRaises(RuleError):
            outposts.deploy(game, 1, 0, 3)
        ship.owner = "rival"
        with self.assertRaises(RuleError):
            outposts.deploy(game, ship.id, 0, 3)

    def test_enemy_fleet_blocks_deployment_and_attack(self):
        game = self.game
        self.deploy("rival")
        attacker = add_ship(game, "frigate", self.system.id)
        escort = add_ship(game, "frigate", self.system.id, "rival")
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "opposing ships"):
            outposts.attack(game, self.system.id, self.planet.id)
        self.assertEqual(game.to_dict(), before)
        outposts.clear(self.planet)
        ship = add_ship(game, "outpost_ship", self.system.id)
        self.assertIn("opposing ships", outposts.deployment_error(game, self.system.id, self.planet.id))

    def test_attack_is_hostile_once_per_turn_and_destruction_removes_supply(self):
        game = self.game
        self.deploy("rival")
        attacker = add_ship(game, "frigate", self.system.id)
        game.diplomacy.trade_active = True
        amount = outposts.attack_damage(game, self.system.id, self.planet.id)
        message = outposts.attack(game, self.system.id, self.planet.id)
        self.assertEqual(self.planet.outpost_hull, outposts.OUTPOST_HULL-amount)
        self.assertEqual(game.diplomacy.relations, -100)
        self.assertFalse(game.diplomacy.trade_active)
        self.assertIsNotNone(outposts.attack_error(game, self.system.id, self.planet.id))
        while self.planet.outpost_owner:
            game.turn += 1
            outposts.attack(game, self.system.id, self.planet.id)
        self.assertEqual(self.planet.outpost_hull, 0)
        self.assertNotIn(self.system, game.supply_systems("rival"))
        survey = game.exploration.survey(self.system.id, "rival")
        self.assertIsNone(survey.worlds[self.planet.id]["outpost_owner"])

    def test_shared_bombardment_budget(self):
        from orion.defenses import bombardment_fleet
        game = self.game
        self.deploy("rival")
        ship = add_ship(game, "frigate", self.system.id)
        outposts.attack(game, self.system.id, self.planet.id)
        self.assertNotIn(ship, bombardment_fleet(game, self.system.id, "player"))

    def test_peaceful_repair_waits_a_turn_and_caps_at_maximum(self):
        self.deploy()
        game = self.game
        self.planet.outpost_hull = 1
        self.planet.bombarded_turn = game.turn
        game.turn += 1
        outposts.advance(game)
        self.assertEqual(self.planet.outpost_hull, 1)
        game.turn += 1
        outposts.advance(game)
        self.assertEqual(self.planet.outpost_hull, 1+outposts.OUTPOST_RECOVERY)
        add_ship(game, "frigate", self.system.id, "rival")
        game.diplomacy.relations = -100
        game.turn += 1
        outposts.advance(game)
        self.assertEqual(self.planet.outpost_hull, 1+outposts.OUTPOST_RECOVERY)

    def test_own_outpost_upgrades_to_colony_but_enemy_outpost_blocks_colonization(self):
        game = self.game
        self.planet.biome = "Terran"
        self.deploy("rival")
        colony = add_ship(game, "colony_ship", self.system.id)
        with self.assertRaisesRegex(RuleError, "opposing outpost"):
            game.colonize(colony.id, self.system.id, self.planet.id)
        self.planet.outpost_owner = "player"
        game.colonize(colony.id, self.system.id, self.planet.id)
        self.assertIsNone(self.planet.outpost_owner)
        self.assertTrue(self.planet.colonized)
        self.assertIn(self.system, game.supply_systems())

    def test_save_restores_outposts_and_stale_surveys_without_leaking_ownership(self):
        self.deploy("rival")
        game = self.game
        scout = add_ship(game, "scout", self.system.id)
        exploration.refresh(game)
        game.ships.remove(scout)
        self.planet.outpost_hull = 7
        self.assertEqual(game.known_system(self.system.id).worlds[0].outpost_hull, outposts.OUTPOST_HULL)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            loaded, meta = storage.load(path)
            self.assertEqual(meta["version"], SAVE_VERSION)
            self.assertEqual(loaded.to_dict(), game.to_dict())
            self.assertEqual(loaded.planet_at(self.system.id, 0).outpost_hull, 7)

    def test_invalid_outposts_are_rejected_on_load(self):
        self.deploy()
        sid, pid = self.system.id, self.planet.id
        for fields in ({"outpost_hull": -1}, {"outpost_hull": 0}, {"outpost_owner": "bogus"},
                       {"outpost_hull": True}, {"outpost_owner": None}, {"colonized": True, "owner": "player"}):
            data = self.game.to_dict()
            data["systems"][sid]["worlds"][pid].update(fields)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)

    def test_duplicate_planet_bases_and_unknown_owners_in_surveys_are_rejected(self):
        self.deploy()
        # The home system has several vacant worlds; two bases must not survive loading.
        data = self.game.to_dict()
        for pid in (0, 1):
            data["systems"][0]["worlds"][pid].update(outpost_owner="player", outpost_hull=30)
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        data = self.game.to_dict()
        survey = next(s for s in data["exploration"]["surveys"] if s["system_id"] == self.system.id and s["owner"] == "player")
        survey["worlds"][self.planet.id]["outpost_owner"] = "rival_5"
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_an_awakening_replaces_the_unarmed_outpost_and_informs_its_owner(self):
        from orion.tomb_worlds import TombWorld, awaken
        self.deploy()
        tomb = TombWorld(self.system.id, self.planet.id)
        awaken(self.game, tomb)
        self.assertTrue(self.planet.colonized)
        self.assertIsNone(self.planet.outpost_owner)
        self.assertEqual(self.planet.outpost_hull, 0)
        self.assertIn("player", tomb.notified_owners)

    def test_outpost_ship_survives_mid_combat_save_and_is_an_unarmed_target(self):
        from orion.combat import begin_combat
        game = self.game
        ship = add_ship(game, "outpost_ship", self.system.id, "rival")
        add_ship(game, "frigate", self.system.id)
        begin_combat(game, self.system.id)
        battle_ship = game.combat.ship(ship.id)
        self.assertEqual(battle_ship.damage, 0)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_prefers_known_unsettled_system_over_another_home_planet(self):
        from orion.ai import run_ai
        from scenarios import place_near
        game = self.game
        owner = "rival"
        home = game.opponent.home_system
        place_near(game, self.system.id, anchor=home)
        self.planet.biome = "Terran"
        game.ships[:] = [s for s in game.ships if s.owner != owner]
        ship = add_ship(game, "colony_ship", home, owner)
        scout = add_ship(game, "scout", self.system.id, owner)
        exploration.refresh(game)
        run_ai(game, owner)
        self.assertIn(ship, game.ships)
        self.assertIsNotNone(ship.destination)
        self.assertNotEqual(ship.destination, home)

    def test_old_save_profile_gets_new_default_costs_but_keeps_custom_values(self):
        profile = balance.default_profile()
        profile["version"] = 4
        profile["data"]["ships"].pop("outpost_ship")
        profile["data"]["rules"].pop("outposts")
        profile["data"]["ships"]["colony_ship"].update(resource_cost=80, work_cost=42)
        migrated = balance.upgrade_profile(profile)
        self.assertEqual(migrated["data"]["ships"]["colony_ship"]["resource_cost"], 800)
        self.assertIn("outpost_ship", migrated["data"]["ships"])
        profile["data"]["ships"]["colony_ship"]["resource_cost"] = 123
        self.assertEqual(balance.upgrade_profile(profile)["data"]["ships"]["colony_ship"]["resource_cost"], 123)
        data = self.game.to_dict()
        for system in data["systems"]:
            for planet in system["worlds"]:
                planet.pop("outpost_owner")
                planet.pop("outpost_hull")
        loaded = GameState.from_dict(data, version=39)
        self.assertTrue(all(not p.outpost_owner for s in loaded.systems for p in s.worlds))

    def test_defeated_empire_loses_outposts(self):
        self.deploy("rival")
        for system in self.game.systems:
            for planet in system.worlds:
                if planet.owner == "rival":
                    planet.owner = "player"
        self.game.eliminate_defeated()
        self.assertIsNone(self.planet.outpost_owner)

    def test_varkesh_can_use_outposts_but_not_colony_ships(self):
        game = campaign(race_id="varkesh", with_ai=False)
        self.assertIsNone(game.ship_build_error(0, 2, "outpost_ship"))
        self.assertIsNotNone(game.ship_build_error(0, 2, "colony_ship"))

    def test_ai_deploys_its_ship_and_attacks_hostile_outpost(self):
        self.deploy()
        game = self.game
        game.diplomacy.relations = -100
        ship = add_ship(game, "frigate", self.system.id, "rival")
        outposts.ai_orders(game, "rival", {"player"})
        self.assertLess(self.planet.outpost_hull, outposts.OUTPOST_HULL)
        game.ships.remove(ship)
        outposts.clear(self.planet)
        ship = add_ship(game, "outpost_ship", self.system.id, "rival")
        outposts.ai_orders(game, "rival", {"player"})
        self.assertEqual(self.planet.outpost_owner, "rival")
        self.assertNotIn(ship, game.ships)


class OutpostVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.display.set_mode((1440, 900))

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def test_range_fill_is_uniform_and_overlap_has_no_internal_edges(self):
        from orion.galaxy_fleet_view import fuel_range_overlay
        color = (50, 150, 230)
        surface = fuel_range_overlay((220, 120), ((10, 10, 100, 100), (70, 10, 100, 100)), color)
        self.assertEqual(surface.get_at((110, 60)).a, 19)
        self.assertEqual(surface.get_at((71, 60)).a, 19)
        self.assertEqual(surface.get_at((60, 60)).a, 19)
        self.assertEqual(surface.get_at((190, 60)).a, 0)
        self.assertGreater(surface.get_at((10, 60)).a, 19)
        # Disconnected supply circles are not filled as a convex hull.
        gap = fuel_range_overlay((220, 120), ((0, 10, 80, 80), (130, 10, 80, 80)), color)
        self.assertEqual(gap.get_at((105, 50)).a, 0)
        clipped = fuel_range_overlay((80, 80), ((-80, -80, 240, 240),), color)
        self.assertEqual(clipped.get_at((0, 40)).a, 19)

    def test_both_portraits_load_and_other_characters_have_fallbacks(self):
        from orion.specialist_art import load_portrait, draw_portrait
        for key in ("mara_voss", "orun_basalt"):
            self.assertIsNotNone(load_portrait(key))
            draw_portrait(pg.display.get_surface(), specialists.SPECIALISTS[key], (0, 0, 112, 112))
        self.assertIsNone(load_portrait("kaia_ren"))
        draw_portrait(pg.display.get_surface(), specialists.SPECIALISTS["kaia_ren"], (120, 0, 55, 55))

    def test_planet_controls_deploy_and_attack(self):
        from orion.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), capture=True)
            try:
                game = app.game = campaign()
                sid = next(s.id for s in game.systems[1:] if s.worlds and not any(p.colonized for p in s.worlds))
                add_ship(game, "outpost_ship", sid)
                exploration.refresh(game)
                game.selected_system = sid
                app.open_planet(0)
                app.render()
                button = next(b for b in app.buttons if b.key == "establish_outpost")
                self.assertTrue(button.enabled)
                app.confirm = lambda title, message, label, execute: execute()
                button.action()
                self.assertEqual(game.planet_at(sid, 0).outpost_owner, "player")
                app.render()
                self.assertIn("colonize_planet", {b.key for b in app.buttons})
                game.planet_at(sid, 0).outpost_owner = "rival"
                add_ship(game, "frigate", sid)
                app.render()
                button = next(b for b in app.buttons if b.key == "attack_outpost")
                self.assertTrue(button.enabled)
                button.action()
                self.assertLess(game.planet_at(sid, 0).outpost_hull, outposts.OUTPOST_HULL)
            finally:
                app.audio.close()

    def test_observer_can_inspect_outpost_without_deployment_or_attack_buttons(self):
        from orion.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), capture=True)
            try:
                game = app.game = campaign(race_id="observer")
                system = next(s for s in game.systems if any(not p.colonized for p in s.worlds))
                planet = next(p for p in system.worlds if not p.colonized)
                planet.outpost_owner, planet.outpost_hull = "rival", outposts.OUTPOST_HULL
                game.selected_system = system.id
                app.open_planet(planet.id)
                app.render()
                self.assertFalse({"attack_outpost", "establish_outpost", "colonize_planet"} & {b.key for b in app.buttons})
                self.assertIsNotNone(outposts.attack_error(game, system.id, planet.id))
                self.assertIsNotNone(outposts.deployment_error(game, system.id, planet.id))
            finally:
                app.audio.close()


if __name__ == "__main__":
    unittest.main()
