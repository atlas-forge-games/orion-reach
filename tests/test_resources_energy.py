"""Economy invariants, shared supply, recovery, old saves and actual UI actions."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from orion import ai, defenses, economy, exploration, navigation, population, sensors, victory
from orion.buildings import BUILDINGS
from orion.empire import summarize_empire, colony_rows
from orion.model import ConstructionProject, GameState, RuleError, SaveError, Ship, new_game
from orion.storage import Storage


def campaign(**kwargs):
    return new_game(seed=804, with_ai=kwargs.pop("with_ai", False), with_guardians=False,
                    with_tombs=False, fog_of_war=False, random_starts=False, **kwargs)


class ResourceRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = campaign()
        self.planet = self.game.planet_at(0, 2)

    def test_four_jobs_conserve_population_and_change_distinct_outputs(self):
        g, p = self.game, self.planet
        self.assertEqual((p.farmers, p.workers, p.scientists, p.miners), (2, 4, 0, 2))
        self.assertEqual(g.planet_resources(p), 6)
        g.move_worker(0, 2, "workers", "miners")
        self.assertEqual((g.planet_resources(p), g.planet_yields(p)[0]), (8, 3))
        g.move_worker(0, 2, "miners", "scientists")
        self.assertEqual((g.planet_resources(p), g.planet_yields(p)[2]), (6, 2))
        self.assertEqual(sum(getattr(p, role) for role in population.WORKER_ROLES), p.workforce)
        for miners in (True, -1, 1.2, 9):
            before = g.to_dict()
            with self.assertRaises(RuleError):
                g.set_workforce(0, 2, 2, 1, miners)
            self.assertEqual(g.to_dict(), before)

    def test_richness_scales_mining_without_multiplying_industry(self):
        g, p = self.game, self.planet
        p.buildings = ["mine", "factory"]
        industrial = g.planet_yields(p)[0]
        for richness, resources in (("Poor", 6), ("Average", 10), ("Rich", 14), ("Ultra-rich", 26)):
            p.richness = richness
            self.assertEqual(g.planet_resources(p), resources)
            self.assertEqual(g.planet_yields(p)[0], industrial)
        g.technology.completed = ["deep_core_drills"]
        self.assertEqual(g.planet_resources(p), 28)

    def test_queue_without_resources_waits_then_reserves_once_and_refunds_unused_material(self):
        g, p = self.game, self.planet
        g.resources, g.credits = 0, 0
        g.queue_building(0, 2, "mine")
        q = p.construction_queue[0]
        for _ in range(4):
            g.advance_turn()
            self.assertEqual((q.progress, q.paid_resources), (0, 0))
        self.assertEqual(g.resources, 24)
        self.assertEqual(g.construction_status(p), "Waiting for 6 resources")
        g.advance_turn()
        self.assertEqual((q.paid_resources, q.progress, g.resources), (30, 4, 0))
        bank = g.resources
        refund = q.resource_refund
        credits = g.credits
        self.assertEqual(g.cancel_construction(0, 2, 0), f"{refund} RES")
        self.assertEqual((g.resources, g.credits), (bank+refund, credits))

    def test_cancel_unstarted_order_never_creates_resources_or_credits(self):
        g = self.game
        g.queue_ship(0, 2, "scout")
        before = (g.resources, g.credits)
        self.assertEqual(g.cancel_construction(0, 2, 0), "0 RES")
        self.assertEqual((g.resources, g.credits), before)

    def test_rush_cannot_bypass_resources_and_only_pays_credits_for_remaining_work(self):
        g, p = self.game, self.planet
        g.queue_building(0, 2, "factory")
        g.resources = 44
        before = g.to_dict()
        with self.assertRaisesRegex(RuleError, "resources"):
            g.buy_construction(0, 2)
        self.assertEqual(g.to_dict(), before)
        g.resources = 45
        price = g.buy_construction_cost(0, 2)
        g.buy_construction(0, 2)
        self.assertEqual((g.resources, g.credits, p.buildings), (0, 120-price, ["factory"]))

    def test_cost_snapshot_keeps_discount_after_later_research_and_reordering(self):
        g, p = self.game, self.planet
        g.queue_building(0, 2, "factory")
        original = p.construction_queue[0]
        g.technology.completed = ["civil_engineering", "prefabricated_structures"]
        g.change_production(0, 2, "factory")
        self.assertEqual([q.resource_cost for q in p.construction_queue], [36, 45])
        g.prioritize_construction(0, 2, 1)
        self.assertIs(p.construction_queue[0], original)
        g.advance_turn()
        self.assertEqual(original.paid_resources, 45)
        self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_two_colonies_share_supply_and_forecast_matches_actual_competing_queues(self):
        g, p = self.game, self.planet
        other = g.planet_at(0, 3)
        other.colonized, other.owner, other.population = True, "player", 4
        other.farmers, other.miners = 2, 2
        g.resources = 0
        g.queue_building(0, 2, "factory")
        g.queue_ship(0, 2, "scout")
        g.queue_building(0, 3, "mine")
        before = g.to_dict()
        estimates = g.queue_estimates(p)
        self.assertEqual(g.to_dict(), before)
        actual = []
        for elapsed in range(1, estimates[-1]+1):
            report = g.advance_turn()
            actual.extend([elapsed]*sum(f"on {p.name}" in name for name in report.completed))
        self.assertEqual(actual, estimates)
        self.assertGreaterEqual(g.resources, 0)

    def test_empire_stockpiles_never_fund_other_empires(self):
        g = campaign(with_ai=True)
        sid, p = g.headquarters("rival")
        g.resources, g.opponent.resources = 1000, 0
        g.queue_building(sid.id, p.id, "factory", owner="rival")
        self.assertFalse(g.fund_project(p.construction_queue[0], "rival"))
        self.assertEqual((g.resources, g.opponent.resources), (1000, 0))


class EnergyRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = campaign()
        self.planet = self.game.planet_at(0, 2)

    def test_generation_is_local_and_priority_preserves_farms_and_mines(self):
        g, p = self.game, self.planet
        p.buildings = ["research_lab"]*3+["hydroponic_farm", "mine"]
        report = g.planet_energy(p)
        self.assertEqual((report.generated, report.demand, report.used), (12, 16, 12))
        self.assertEqual(report.offline, (2,))
        self.assertEqual(g.planet_yields(p)[2], 8)
        other = g.planet_at(0, 3)
        other.colonized, other.owner, other.population = True, "player", 1
        other.buildings = ["solar_array"]*2
        totals = summarize_empire(g)
        self.assertGreater(totals.energy_generated, totals.energy_demand)
        self.assertEqual(totals.energy_shortages, 1)
        self.assertEqual(colony_rows(g, "power"), [(g.systems[0], p)])

    def test_manual_switch_frees_energy_but_retains_upkeep_and_survives_reload(self):
        g, p = self.game, self.planet
        p.buildings = ["research_lab"]*4
        before = g.planet_maintenance(p)
        g.toggle_building(0, 2, 0)
        self.assertEqual(g.planet_energy(p).active, (1, 2, 3))
        self.assertEqual(g.planet_maintenance(p), before)
        self.assertEqual(GameState.from_dict(g.to_dict()), g)
        g.demolish_building(0, 2, 1)
        self.assertEqual(p.disabled_buildings, [0])
        g.demolish_building(0, 2, 0)
        self.assertEqual(p.disabled_buildings, [])

    def test_zero_bank_and_power_shortage_can_recover_without_external_help(self):
        g, p = self.game, self.planet
        p.buildings, p.farmers, p.scientists, p.miners = ["research_lab"]*4, 0, 8, 0
        g.resources, g.credits = 0, 0
        g.queue_building(0, 2, "solar_array")
        estimate = g.queue_estimates(p)[0]
        self.assertGreater(g.planet_resources(p), 0)
        for _ in range(estimate):
            g.advance_turn()
        self.assertIn("solar_array", p.buildings)
        self.assertGreaterEqual(g.planet_energy(p).balance, 0)

    def test_generators_and_mining_completed_this_turn_affect_next_turns_income(self):
        g, p = self.game, self.planet
        g.queue_building(0, 2, "mine")
        q = p.construction_queue[0]
        g.fund_project(q)
        q.progress = q.spec.work_cost-1
        start = g.planet_resources(p)
        self.assertEqual(g.advance_turn().resources, start)
        self.assertEqual(g.advance_turn().resources, g.planet_resources(p))
        self.assertGreater(g.planet_resources(p), start)

    def test_power_research_unlocks_generator_and_improves_basic_supply(self):
        g, p = self.game, self.planet
        self.assertIsNotNone(g.build_error(0, 2, "fusion_plant"))
        g.research = 500
        g.choose_research("compact_reactors")
        self.assertEqual(g.planet_energy(p).generated, 16)
        g.choose_research("fusion_drives")
        g.choose_research("fusion_power")
        self.assertIsNone(g.build_error(0, 2, "fusion_plant"))
        p.buildings = ["fusion_plant"]
        self.assertEqual(g.planet_energy(p).generated, 46)

    def test_offline_shields_bases_gates_sensors_and_training_lose_their_effect(self):
        g = campaign(with_ai=True)
        p = g.planet_at(0, 2)
        p.buildings = ["planetary_shield", "missile_base", "sensor_array", "barracks", "jump_gate"]
        p.shield_points, p.battery_hull = 100, 40
        p.disabled_buildings = list(range(5))
        self.assertEqual(defenses.effective_shield(g, p), 0)
        self.assertEqual(defenses.bases(g, 0, "player"), [])
        from orion.ground_combat import train
        self.assertEqual(train(p), 0)
        g.technology.completed = ["research_networks", "deep_space_radar"]
        self.assertEqual(sensors.centers(g)[0][1], 5)
        p.ascension_gate = True
        p.disabled_buildings = []
        before = p.gate_charge
        victory.advance_gates(g, [(0, 2, "player")])
        self.assertEqual(p.gate_charge, before)

    def test_ai_restores_power_and_assigns_mining_without_cheating_resources(self):
        g = campaign(with_ai=True)
        system, p = g.headquarters("rival")
        p.buildings = ["research_lab"]*8
        p.miners = 0
        g.opponent.resources = 0
        with patch("orion.ai.military_orders"):
            for _ in range(35):
                if g.combat or g.result:
                    break
                g.advance_turn()
                self.assertGreaterEqual(g.opponent.resources, 0)
                GameState.from_dict(g.to_dict())
        self.assertTrue(any(BUILDINGS[b].energy_output for b in p.buildings))
        self.assertGreaterEqual(g.planet_energy(p).balance, 0)
        self.assertGreater(g.resource_rate("rival"), 2)


class EconomySaveTests(unittest.TestCase):
    def test_real_v0351_campaign_preserves_paid_orders_and_surveys(self):
        payload = json.loads((Path(__file__).parent/"fixtures"/"v0351_campaign.json").read_text())
        g = GameState.from_dict(payload["game"], version=payload["version"])
        self.assertEqual(g.resources, economy.STARTING_RESOURCES)
        for old_system, system in zip(payload["game"]["systems"], g.systems):
            for old, p in zip(old_system["worlds"], system.worlds):
                self.assertEqual((p.miners, p.disabled_buildings), (0, []))
                for prior, q in zip(old["construction_queue"], p.construction_queue):
                    self.assertEqual((q.progress, q.paid_credits, q.resource_cost),
                                     (prior["progress"], prior["paid_credits"], 0))
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            self.assertEqual(storage.load(storage.save(g))[0], g)
        for _ in range(5):
            if g.combat or g.result:
                break
            g.advance_turn()
            self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_rejects_negative_stockpiles_invalid_jobs_power_indices_and_unpaid_progress(self):
        g = campaign()
        g.queue_building(0, 2, "factory")
        for mutate in (
            lambda d: d.update(resources=-1),
            lambda d: d.update(resources=True),
            lambda d: d["systems"][0]["worlds"][2].update(miners=99),
            lambda d: d["systems"][0]["worlds"][2].update(disabled_buildings=[0]),
            lambda d: d["systems"][0]["worlds"][2]["construction_queue"][0].update(progress=1),
            lambda d: d["systems"][0]["worlds"][2]["construction_queue"][0].update(paid_resources=1),
        ):
            data = copy.deepcopy(g.to_dict())
            mutate(data)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class EconomyInterfaceTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.game = campaign()
        self.app.game.selected_system, self.app.game.selected_planet = 0, 2
        self.app.go("planet")
        self.app.present()

    def click(self, key):
        import pygame as pg
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        v = self.app.viewport
        pos = (v.x+round(button.rect.centerx*v.w/1440), v.y+round(button.rect.centery*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_mining_row_moves_real_workers_and_autosave_keeps_all_four_jobs(self):
        g = self.app.game
        p = g.planet_at(0, 2)
        self.click("worker_workers")
        self.click("worker_miners")
        self.assertEqual((p.workers, p.miners), (3, 3))
        self.assertEqual(g.planet_resources(p), 8)
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, g)
        self.assertEqual(g.turn, 1)

    def test_building_power_switch_and_new_generator_catalogue_are_reachable(self):
        g = self.app.game
        p = g.planet_at(0, 2)
        p.buildings = ["research_lab"]*4
        self.app.go("colony")
        self.click("colony_slot_0")
        self.click("toggle_building")
        self.assertEqual(p.disabled_buildings, [0])
        self.assertEqual(g.planet_energy(p).offline, ())
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, g)
        self.click("colony_power")
        self.click("build_solar_array")
        self.assertEqual(p.construction_queue[-1].item_id, "solar_array")
        self.assertEqual(g.credits, 120)

    def test_energy_header_finds_a_local_shortage_despite_empire_surplus(self):
        g = self.app.game
        p = g.planet_at(0, 2)
        p.buildings = ["research_lab"]*4
        other = g.planet_at(0, 3)
        other.owner, other.colonized, other.population = "player", True, 1
        other.buildings = ["solar_array"]*2
        self.app.go("galaxy")
        self.click("energy_report")
        self.assertEqual((self.app.screen, self.app.empire_filter), ("empire", "power"))
        self.assertEqual([p.name for _, p in colony_rows(g, "power")], ["Earth"])
        self.click("empire_colony_0_2")
        self.assertEqual((self.app.screen, g.selected_planet), ("planet", 2))


if __name__ == "__main__":
    unittest.main()
