"""Steady generators, paid backup dispatch and consistent colony forecasts."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import ai, economy
from orion.buildings import BUILDINGS
from orion.model import GameState
from orion.research import TECHNOLOGIES
from orion.storage import Storage
from scenarios import empty_fleet_game


def campaign(**kwargs):
    return empty_fleet_game(seed=2408, with_ai=kwargs.pop("with_ai", False), **kwargs)


def unlock(game, *identifiers):
    for identifier in identifiers:
        game.research += TECHNOLOGIES[identifier].cost
        game.choose_research(identifier)


class PowerDispatchTests(unittest.TestCase):
    def setUp(self):
        self.game = campaign()
        self.planet = self.game.planet_at(0, 2)

    def test_all_steady_sources_add_output_without_resource_fuel(self):
        g, p = self.game, self.planet
        p.buildings = ["solar_array", "geothermal_plant", "fusion_plant", "singularity_plant"]
        g.resources = 0
        power = g.planet_energy(p)
        self.assertEqual((power.generated, power.base_generated, power.fuel_used), (124, 124, 0))
        self.assertEqual(g.planet_maintenance(p), 11)

    def test_backup_is_last_even_when_its_building_slot_is_first(self):
        g, p = self.game, self.planet
        p.buildings = ["thermal_plant"]+["research_lab"]*4+["solar_array"]
        before = g.to_dict()
        power = g.planet_energy(p)
        self.assertEqual((power.generated, power.backup_generated, power.fuel_used), (24, 0, 0))
        self.assertEqual(economy.building_status(p, 0, g.bonuses_for()), "STANDBY")
        self.assertEqual(g.to_dict(), before)
        start = g.resources
        report = g.advance_turn()
        self.assertEqual((g.resources-start, report.resources), (2, 2))

    def test_backup_throttles_and_rounds_only_the_actual_fuel_needed(self):
        g, p = self.game, self.planet
        p.buildings = ["research_lab"]*3+["trade_center", "thermal_plant"]
        power = g.planet_energy(p)
        self.assertEqual((power.demand, power.backup_generated, power.fuel_used), (13, 1, 1))
        self.assertEqual(economy.building_status(p, 4, g.bonuses_for()), "BACKUP ON")
        p.buildings.insert(3, "research_lab")
        power = g.planet_energy(p)
        self.assertEqual((power.demand, power.backup_generated, power.fuel_used), (17, 5, 2))

    def test_fuel_shortage_never_creates_unpaid_output_or_a_negative_bank(self):
        g, p = self.game, self.planet
        p.buildings = ["planetary_shield", "interdictor", "research_lab", "thermal_plant"]
        g.resources = 1
        power = g.planet_energy(p)
        self.assertEqual((power.used, power.backup_generated, power.fuel_used), (16, 4, 1))
        self.assertEqual(power.offline, (2,))
        self.assertEqual(g.planet_yields(p)[2], 0)
        g.resources = 0
        power = g.planet_energy(p)
        self.assertEqual((power.used, power.fuel_used, power.backup_generated), (12, 0, 0))
        self.assertEqual(economy.building_status(p, 3, g.bonuses_for()), "NO FUEL")
        for _ in range(5):
            g.advance_turn()
            self.assertGreaterEqual(g.resources, 0)

    def test_fuel_is_not_burned_for_partial_power_that_cannot_run_a_building(self):
        g, p = self.game, self.planet
        p.buildings = ["planetary_shield", "interdictor", "jump_gate", "thermal_plant"]
        g.resources = 0
        self.assertEqual(g.planet_energy(p).used, 8)
        # One Resource powers the second 8-energy load using the spare steady 4.
        g.resources = 1
        self.assertEqual((g.planet_energy(p).used, g.planet_energy(p).fuel_used), (16, 1))
        # Another 4 energy cannot power the final 8-energy load, so keep its fuel.
        g.resources = 2
        self.assertEqual((g.planet_energy(p).used, g.planet_energy(p).fuel_used), (16, 1))

    def test_multiple_backup_plants_share_capacity_and_leave_unneeded_ones_idle(self):
        g, p = self.game, self.planet
        p.buildings = ["planetary_shield"]*5+["thermal_plant", "thermal_plant"]
        power = g.planet_energy(p)
        self.assertEqual((power.demand, power.backup_generated, power.fuel_used), (40, 28, 7))
        self.assertEqual(power.plants, ((5, 24, 6), (6, 4, 1)))
        p.buildings[0] = "solar_array"
        power = g.planet_energy(p)
        self.assertEqual(power.plants[-1], (6, 0, 0))
        self.assertEqual(economy.building_status(p, 6, g.bonuses_for()), "STANDBY")

    def test_disabling_and_demolishing_generators_immediately_changes_dispatch(self):
        g, p = self.game, self.planet
        p.buildings = ["research_lab"]*4+["solar_array", "thermal_plant"]
        self.assertEqual(g.planet_energy(p).fuel_used, 0)
        g.toggle_building(0, 2, 4)
        self.assertEqual(g.planet_energy(p).fuel_used, 1)
        g.toggle_building(0, 2, 5)
        self.assertEqual((g.planet_energy(p).fuel_used, g.planet_energy(p).offline), (0, (3,)))
        self.assertEqual(economy.building_status(p, 5, g.bonuses_for()), "DISABLED")
        g.toggle_building(0, 2, 5)
        g.demolish_building(0, 2, 4)
        self.assertEqual(g.planet_energy(p).fuel_used, 1)
        self.assertEqual(p.disabled_buildings, [])

    def test_same_empire_cannot_spend_the_same_resource_at_two_colonies(self):
        g, first = self.game, self.planet
        second = next(s for s in g.systems[1:] if len(s.worlds) > 2).worlds[2]
        second.colonized, second.owner, second.population = True, "player", 2
        for p in (first, second):
            p.buildings = ["research_lab"]*4+["thermal_plant"]
        g.resources = 1
        self.assertEqual((g.planet_energy(first).fuel_used, g.planet_energy(second).fuel_used), (1, 0))
        self.assertEqual(g.planet_energy(second).offline, (3,))
        g.resources = 2
        self.assertEqual((g.planet_energy(first).fuel_used, g.planet_energy(second).fuel_used), (1, 1))
        g.resources = 1
        before = g.resources
        report = g.advance_turn()
        self.assertEqual((g.resources-before, report.resources), (3, 3))
        self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_enemy_resources_cannot_fund_your_backup(self):
        g = campaign(with_ai=True)
        own, enemy = g.planet_at(0, 2), g.headquarters("rival")[1]
        for p in (own, enemy):
            p.buildings = ["research_lab"]*4+["thermal_plant"]
        g.resources, g.opponent.resources = 0, 100
        self.assertEqual((g.planet_energy(own).fuel_used, g.planet_energy(enemy).fuel_used), (0, 1))

    def test_backup_power_supplies_mining_food_and_defenses_through_the_same_grid(self):
        g, p = self.game, self.planet
        p.buildings = ["planetary_shield", "interdictor", "mine", "hydroponic_farm", "thermal_plant"]
        p.shield_points = 100
        p.miners, p.farmers = 1, 1
        powered = g.population_report(p)
        power = g.planet_energy(p)
        self.assertEqual(power.used, 20)
        self.assertTrue(g.building_operational(p, "interdictor"))
        self.assertEqual(g.planet_resources(p), economy.mining_output(p, g.bonuses_for())-2)
        self.assertGreater(powered.produced, 6)
        g.resources = 0
        self.assertFalse(g.building_operational(p, "interdictor"))
        # Farms and mines retain priority even without reserve fuel.
        self.assertEqual(g.population_report(p).produced, powered.produced)
        self.assertEqual(g.planet_energy(p).fuel_used, 0)


class PowerProgressionTests(unittest.TestCase):
    def test_new_plants_unlock_through_the_existing_paired_research(self):
        g = campaign()
        for identifier in ("geothermal_plant", "thermal_plant", "singularity_plant", "fusion_plant"):
            self.assertIn("Requires", g.build_error(0, 2, identifier))
        unlock(g, "deep_core_drills", "compact_reactors", "fusion_grids", "fusion_power", "field_stabilization")
        for identifier in ("geothermal_plant", "thermal_plant", "singularity_plant", "fusion_plant"):
            self.assertIsNone(g.build_error(0, 2, identifier))
            g.resources = g.credits = 1000
            g.queue_building(0, 2, identifier)
            g.buy_construction(0, 2)
        self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_backup_cost_is_charged_once_before_new_construction(self):
        g = campaign()
        p = g.planet_at(0, 2)
        p.buildings = ["research_lab"]*4+["thermal_plant"]
        g.resources = 29
        g.queue_building(0, 2, "solar_array")
        # 29 in store + 2 mined - 1 fuel = exactly the 30 needed by the order.
        estimate = g.queue_estimates(p)[0]
        first = g.advance_turn()
        self.assertEqual((g.resources, first.resources, first.research), (0, 1, 16))
        while p.construction_queue:
            g.advance_turn()
        self.assertEqual(g.turn-1, estimate)
        self.assertEqual(g.planet_energy(p).fuel_used, 0)
        self.assertEqual(g.resources, estimate)  # The exhausted reserve also causes a fuel-free recovery turn.

    def test_forecast_matches_fuel_limited_production_across_colonies(self):
        g = campaign()
        p = g.planet_at(0, 2)
        p.buildings = ["research_lab", "research_lab", "factory", "factory", "thermal_plant"]
        system = next(s for s in g.systems[1:] if len(s.worlds) > 2)
        other = system.worlds[2]
        other.colonized, other.owner, other.population = True, "player", 2
        other.buildings = ["research_lab"]*4+["thermal_plant"]
        g.resources = 1
        g.queue_building(0, 2, "solar_array")
        g.queue_building(system.id, 2, "mine")
        expected = g.queue_estimates(p)[0]
        self.assertIsNotNone(expected)
        for _ in range(expected):
            g.advance_turn()
        self.assertFalse(p.construction_queue)
        self.assertIn("solar_array", p.buildings)
        self.assertGreaterEqual(g.resources, 0)

    def test_advance_and_save_do_not_change_or_double_charge_planned_dispatch(self):
        g = campaign()
        p = g.planet_at(0, 2)
        p.buildings = ["research_lab"]*4+["thermal_plant"]
        g.resources = 1
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored = store.load(store.save(g))[0]
            for _ in range(6):
                self.assertEqual(g.planet_energy(p), restored.planet_energy(restored.planet_at(0, 2)))
                self.assertEqual(g.advance_turn(), restored.advance_turn())
                self.assertEqual(g, restored)
                self.assertFalse(hasattr(g, "_turn_power"))

    def test_ai_prefers_unlocked_steady_generation_over_continuous_resource_burning(self):
        g = campaign()
        p = g.planet_at(0, 2)
        p.buildings = ["trade_center"]*2
        self.assertEqual(ai.steady_power_plant(g, p, "player"), "solar_array")
        unlock(g, "deep_core_drills", "compact_reactors", "fusion_grids", "fusion_power", "field_stabilization")
        self.assertEqual(ai.steady_power_plant(g, p, "player"), "singularity_plant")
        self.assertFalse(BUILDINGS[ai.steady_power_plant(g, p, "player")].energy_per_resource)


class PowerInterfaceTests(unittest.TestCase):
    def test_power_tab_exposes_every_generator_and_locked_research(self):
        from orion.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App(folder, capture=True)
            app.game = campaign()
            app.game.selected_system, app.game.selected_planet = 0, 2
            app.go("colony")
            app.render()
            next(b for b in app.buttons if b.key == "colony_power").action()
            app.render()
            buttons = {b.key: b for b in app.buttons}
            self.assertTrue(buttons["build_solar_array"].enabled)
            for identifier in ("geothermal_plant", "fusion_plant", "thermal_plant", "singularity_plant"):
                self.assertIn("build_"+identifier, buttons)
                self.assertFalse(buttons["build_"+identifier].enabled)
            unlock(app.game, "compact_reactors", "fusion_grids")
            app.render()
            buttons = {b.key: b for b in app.buttons}
            self.assertTrue(buttons["build_thermal_plant"].enabled)
            buttons["build_thermal_plant"].action()
            self.assertEqual(app.game.planet_at(0, 2).construction_queue[-1].item_id, "thermal_plant")
            for page in (0, 1, 2):
                app.colony_build_page = page
                app.render()
                self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
        pg.quit()


if __name__ == "__main__":
    unittest.main()
