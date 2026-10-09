"""Racial economies, shared AI rules, portrait selection and the setup wizard."""

from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion.app import App
from orion.model import BIOMES, GameState, PLAYER, RIVAL
from scenarios import fixed_start_game as new_game, place_near
from orion.population import farmers_needed, report
from orion.exploration import refresh
from orion.races import RACES
from orion.research import gross_colony_yields
from orion.storage import Storage
from orion.race_art import _load_portrait, draw_race_emblem


def solo(race):
    return new_game(seed=2408, race_id=race, with_ai=False, with_guardians=False)


class RaceRulesTests(unittest.TestCase):
    def test_original_economies_and_cached_technology_bonuses_are_unchanged(self):
        human = solo("terran")
        cached = deepcopy(human.technology.bonuses)
        for race in RACES:
            game = solo(race)
            game.bonuses_for()["colony_industry"] = 999
            self.assertEqual(game.technology.bonuses, cached)
        for race in ("terran", "kharuun", "aelari"):
            game = solo(race)
            world = game.planet_at(0, 2)
            self.assertEqual(game.planet_yields(world), (6, 8, 0))
            self.assertEqual((game.population_report(world).consumed, game.population_report(world).growth_rate), (8, 10))
            self.assertEqual(game.project_price("frigate"), 60)

    def test_lithar_settle_every_biome_and_keep_growing_beyond_the_old_limit(self):
        game = solo("lithar")
        world = game.planet_at(0, 2)
        for biome in BIOMES:
            world.biome = biome
            self.assertTrue(game.can_settle(world))
        world.biome, world.size = "Gaia", "Huge"
        world.population, world.farmers, world.growth_progress = 55, 0, 99
        world.farmers = farmers_needed(world, game.bonuses_for())
        info = game.population_report(world)
        self.assertEqual((info.capacity, info.consumed), (56, 28))
        self.assertGreater(info.growth_rate, 0)
        self.assertLess(info.growth_rate, report(world).growth_rate or 35)
        game.advance_turn()
        self.assertEqual((world.population, world.growth_progress), (56, 0))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        self.assertEqual(game.population_report(world).growth_rate, 0)

    def test_lithar_colonization_assigns_only_needed_farmers(self):
        game = solo("lithar")
        target = game.planet_at(0, 0)
        target.biome = "Volcanic"
        game.colonize(3, 0, 0)
        self.assertEqual(target.population, 1)
        self.assertGreaterEqual(game.population_report(target).balance, 0)
        refresh(game)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_varkesh_discount_stacks_with_research_and_applies_to_designs(self):
        game = solo("varkesh")
        design = game.save_design("Raider", "frigate", ["laser"])
        self.assertLess(game.project_price(design.id), design.credit_cost)
        self.assertEqual(game.project_price("frigate"), 48)
        game.queue_ship(0, 2, design.id)
        paid = game.planet_at(0, 2).construction_queue[0].paid_credits
        game.technology.completed.append("lightweight_alloys")
        self.assertLess(game.project_price(design.id), paid)
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].paid_credits, paid)
        game.set_workforce(0, 2, 2, 2)
        self.assertEqual(game.planet_yields(game.planet_at(0, 2))[2], 3)

    def test_wanderer_range_extends_routes_and_survives_a_saved_voyage(self):
        game = solo("wanderers")
        target = place_near(game, 1, distance=9)
        self.assertTrue(game.within_fuel_range(target.id))
        ordinary = solo("terran")
        place_near(ordinary, target.id, distance=9)
        self.assertFalse(ordinary.within_fuel_range(target.id))
        duration = game.send_ship(1, target.id)
        game.advance_turn()
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored.ship_at(1).turns_remaining, duration-1)
        game.technology.completed.append("lightweight_alloys")
        self.assertEqual(game.fuel_range(), 20)
        self.assertLess(game.planet_yields(game.planet_at(0, 2))[0], 6)

    def test_xenonflora_lush_world_growth_has_a_real_harsh_world_tradeoff(self):
        game = solo("xenonflora")
        world = game.planet_at(0, 2)
        for biome in ("Terran", "Ocean", "Gaia"):
            world.biome = biome
            baseline = report(world)
            info = game.population_report(world)
            self.assertEqual(info.produced, baseline.produced+3)
            self.assertGreater(info.growth_rate, baseline.growth_rate)
            self.assertEqual(game.planet_yields(world)[0], 6)
        for biome in ("Desert", "Tundra", "Barren", "Volcanic"):
            world.biome = biome
            self.assertEqual(game.planet_yields(world)[0], 4)
            self.assertEqual(game.population_report(world).produced, report(world).produced)

    def test_nexus_assembly_consumes_industry_and_stops_at_capacity(self):
        game = solo("nexus")
        world = game.planet_at(0, 2)
        info = game.population_report(world)
        self.assertEqual((world.farmers, info.produced, info.consumed), (0, 0, 0))
        gross = gross_colony_yields(world, game.bonuses_for())[0]
        self.assertEqual(game.planet_yields(world)[0]+info.assembly_industry, gross)
        self.assertGreater(info.assembly_industry, 0)
        for _ in range(info.turns_to_growth):
            game.advance_turn()
        self.assertEqual(world.population, 9)
        world.population = info.capacity
        self.assertEqual(game.population_report(world).assembly_industry, 0)
        self.assertEqual(game.planet_yields(world)[0], gross_colony_yields(world, game.bonuses_for())[0])

    def test_nexus_construction_forecast_uses_the_same_reserved_industry_as_turns(self):
        game = solo("nexus")
        world = game.planet_at(0, 2)
        world.growth_progress = 90
        game.queue_building(0, 2, "factory")
        estimate = game.queue_estimates(world)[0]
        for _ in range(estimate-1):
            game.advance_turn()
            self.assertNotIn("factory", world.buildings)
        game.advance_turn()
        self.assertIn("factory", world.buildings)

    def test_foodless_colonies_grow_on_volcanic_worlds_without_farmers(self):
        for race in ("nexus", "aetheri"):
            with self.subTest(race=race):
                game = solo(race)
                target = game.planet_at(0, 0)
                target.biome = "Volcanic"
                game.colonize(3, 0, 0)
                self.assertEqual(target.farmers, 0)
                self.assertEqual(game.population_report(target).consumed, 0)
                for _ in range(game.population_report(target).turns_to_growth):
                    game.advance_turn()
                self.assertEqual(target.population, 2)

    def test_concord_relies_on_treaties_to_offset_lower_local_income(self):
        game = new_game(seed=2408, race_id="concord", with_guardians=False)
        self.assertEqual(game.planet_yields(game.planet_at(0, 2))[1], 7)
        before = game.empire_rates
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        self.assertEqual(game.empire_rates, (before[0]+8, before[1]+4))
        game.diplomacy_action("envoy")
        self.assertEqual(game.diplomacy.relations, 10)

    def test_remnant_starting_knowledge_is_spendable_and_not_granted_again_on_load(self):
        game = solo("remnant")
        self.assertEqual(game.research, 80)
        game.choose_research("ion_drives")
        self.assertIn("ion_drives", game.technology.completed)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
        self.assertEqual(restored.research, game.research)
        self.assertLess(restored.research, 80)
        game.set_workforce(0, 2, 2, 2)
        self.assertEqual(game.planet_yields(game.planet_at(0, 2)), (3, 8, 5))

    def test_every_rival_runs_racial_economy_and_save_resume_deterministically(self):
        for race in RACES:
            with self.subTest(race=race):
                game = new_game(seed=2408, rival_race_id=race, with_guardians=False)
                for _ in range(25):
                    game.advance_turn()
                restored = GameState.from_dict(game.to_dict())
                game.advance_turn()
                restored.advance_turn()
                self.assertEqual(restored, game)
                colonies = [p for s in game.systems for p in s.worlds if p.owner == RIVAL]
                if race == "varkesh":
                    self.assertEqual(len(colonies), 1)
                    self.assertFalse(any(s.kind == "colony_ship" for s in game.ships_owned_by(RIVAL)))
                else:
                    self.assertGreater(len(colonies), 1)
                if race in ("nexus", "aetheri"):
                    self.assertTrue(all(p.farmers == 0 and "hydroponic_farm" not in p.buildings for p in colonies))


class RaceSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.present()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.tmp.cleanup()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))

    def test_two_screen_setup_preserves_options_and_autosaves_random_rivals(self):
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.click("new")
        self.assertEqual(self.app.screen, "race_select")
        self.app.render()
        self.assertFalse({"empire", "seed", "launch", "fog_of_war"} & {b.key for b in self.app.buttons})
        for race in RACES:
            self.click("race_"+race)
            self.assertEqual(self.app.race_id, race)
            self.assertEqual(self.app.empire, RACES[race].default_empire)
        self.click("setup_next")
        self.click("size_Compact")
        self.click("fog_of_war")
        for count in range(6):
            self.click("rival_count_"+str(count))
            self.assertEqual(self.app.rival_count, count)
        self.app.seed, self.app.empire = "2408", "Last Horizon"
        self.click("setup_back")
        self.click("race_lithar")
        self.click("setup_next")
        self.assertEqual((self.app.seed, self.app.empire, self.app.size, self.app.fog_of_war), ("2408", "Last Horizon", "Compact", False))
        self.click("launch")
        game = self.app.game
        self.assertEqual(game.race_id, "lithar")
        self.assertEqual(len(game.opponents), 5)
        self.assertEqual(len({r.race_id for r in game.opponents.values()} | {game.race_id}), 6)
        self.assertEqual((len(game.systems), game.fog_of_war), (24, False))
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, game)

    def test_escape_returns_to_race_selection_before_the_menu(self):
        self.app.go("setup")
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
        self.assertEqual(self.app.screen, "race_select")
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
        self.assertEqual(self.app.screen, "menu")

    def test_all_portraits_and_fallback_seals_render_and_foodless_workers_are_clear(self):
        seals = []
        for race in RACES:
            self.assertIsNotNone(_load_portrait(race), race)
            surface = pg.Surface((120, 120))
            draw_race_emblem(surface, race, (60, 60), 45)
            seals.append(pg.image.tobytes(surface, "RGB"))
        self.assertEqual(len(set(seals)), len(RACES))
        self.app.game = solo("nexus")
        self.app.game.selected_planet = 2
        self.app.go("planet")
        self.app.worker_source = "workers"
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "worker_farmers").enabled)


if __name__ == "__main__":
    unittest.main()
