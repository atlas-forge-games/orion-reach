"""End-to-end megastructure budgets, special effects, controls and persistence."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from orion import balance, economy, exploration, megastructures as mega, statistics
from orion.model import new_game, GameState, SaveError, RuleError, Ship, ConstructionProject
from orion.research import choices, TECHNOLOGIES, ResearchState
from orion.storage import Storage


def campaign(ai=False):
    g = new_game(seed=12, galaxy_size="Compact", with_ai=ai, random_starts=False,
                 with_guardians=False, with_tombs=False, with_black_holes=False, fog_of_war=False)
    g.ships.clear()
    g.resources = 100000
    return g


def unlock(g, kind, owner="player"):
    spec = mega.MEGASTRUCTURES[kind]
    state = g.research_state(owner)
    for tier in range(1, spec.tier+1):
        if tier not in state.completed_tiers(spec.branch):
            state.completed.append(choices(spec.branch, tier)[0].id)


def install(g, kind, sid=0, stage=4, owner="player"):
    unlock(g, kind, owner)
    mega.start(g, sid, kind, owner)
    m = g.systems[sid].megastructure
    m.stage, m.progress = stage, 0
    m.hull = m.max_hull
    return m


def settle(g, sid, pid=0, owner="player"):
    p = g.planet_at(sid, pid)
    p.owner, p.colonized, p.population, p.farmers, p.scientists, p.miners = owner, True, 8, 3, 0, 0
    return p


class MegastructureTests(unittest.TestCase):
    def setUp(self):
        old = balance.active_profile()
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(old))
        self.g = campaign()
        self.p = self.g.planet_at(0, 2)
        self.sid = next(s.id for s in self.g.systems[1:] if s.worlds)

    def test_research_and_sole_control_required(self):
        self.assertIn("tier 4", mega.start_error(self.g, 0, "dyson_sphere"))
        unlock(self.g, "dyson_sphere")
        with self.assertRaises(RuleError):
            mega.start(self.g, self.sid, "dyson_sphere")
        before = self.g.to_dict()
        self.assertIsNone(mega.start_error(self.g, 0, "dyson_sphere"))
        self.assertEqual(self.g.to_dict(), before)

    def test_one_per_system_and_once_per_civilization(self):
        install(self.g, "dyson_sphere")
        unlock(self.g, "stellar_forge")
        self.assertIn("one megastructure", mega.start_error(self.g, 0, "stellar_forge"))
        settle(self.g, self.sid)
        self.assertIn("only once", mega.start_error(self.g, self.sid, "dyson_sphere"))
        self.g.systems[0].megastructure = None
        self.assertIn("only once", mega.start_error(self.g, 0, "dyson_sphere"))

    def test_other_civilization_has_independent_commission(self):
        g = campaign(True)
        install(g, "dyson_sphere")
        system = g.colony_systems("rival")[0]
        unlock(g, "dyson_sphere", "rival")
        self.assertIsNone(mega.start_error(g, system.id, "dyson_sphere", "rival"))

    def test_contested_site_preserves_progress_resources_and_industry(self):
        g = campaign(True)
        m = install(g, "stellar_forge", stage=0)
        m.progress = 15
        p = g.planet_at(0, 2)
        settle(g, 0, 0, "rival")
        plan = mega.make_plan(g, "player")
        self.assertEqual(plan.orders, [])
        self.assertEqual(plan.contributions, {})
        with patch("orion.ai.run_ai", return_value=[]):
            g.advance_turn()
        self.assertEqual(m.progress, 15)
        g.planet_at(0, 0).owner = "player"
        self.assertTrue(mega.make_plan(g, "player").orders)

    def test_outposts_are_not_settlements(self):
        g = campaign(True)
        p = g.planet_at(0, 0)
        p.outpost_owner, p.outpost_hull = "rival", 30
        unlock(g, "dyson_sphere")
        self.assertIsNone(mega.start_error(g, 0, "dyson_sphere"))

    def test_funded_work_draws_resources_and_only_real_industry(self):
        self.p.miners = 0
        m = install(self.g, "stellar_forge", stage=0)
        m.allocation = 100
        self.g.resources = 0
        plan = mega.make_plan(self.g, "player")
        self.assertGreaterEqual(plan.net_resources, 0)
        self.assertEqual(plan.orders, [])  # One work costs more than this colony extracts.
        base = self.g.planet_yields(self.p)[0]
        self.assertGreater(base, 0)
        self.g.resources = 7
        plan = mega.make_plan(self.g, "player")
        work = plan.orders[0][1]
        self.assertLess(work, base)
        self.assertEqual(self.g.planet_yields(self.p)[0], base-work)
        start = self.g.resources
        self.g.advance_turn()
        self.assertEqual(m.progress, work)
        self.assertEqual(self.g.resources, start+plan.net_resources)

    def test_shared_budget_and_rounding_cannot_double_spend(self):
        install(self.g, "stellar_forge", stage=0).allocation = 100
        settle(self.g, self.sid)
        install(self.g, "dyson_sphere", self.sid, stage=0).allocation = 100
        self.g.resources = 1
        plan = mega.make_plan(self.g, "player")
        extraction = sum(self.g.planet_resources(p) for s in self.g.systems for p in s.worlds if p.owner == "player")
        self.assertLessEqual(sum(o[2] for o in plan.orders), extraction+1)
        self.assertGreaterEqual(self.g.resources+plan.net_resources, 0)

    def test_stage_complete_has_benefit_from_next_turn(self):
        m = install(self.g, "asteroid_network", stage=0)
        m.progress = m.stage_work-1
        plan = mega.make_plan(self.g, "player")
        self.assertEqual(plan.resource_income, 0)
        start = self.g.resources
        self.g.advance_turn()
        self.assertEqual(m.stage, 1)
        self.assertEqual(m.progress, 0)
        self.assertEqual(self.g.resources, start+plan.net_resources)
        self.assertEqual(mega.make_plan(self.g, "player").resource_income, 150)

    def test_pause_keeps_completed_effects(self):
        m = install(self.g, "asteroid_network", stage=2)
        mega.configure(self.g, 0, paused=True)
        plan = mega.make_plan(self.g, "player")
        self.assertFalse(plan.orders)
        self.assertEqual(plan.resource_income, 300)

    def test_mining_is_fixed_system_output_added_once_to_reserve(self):
        baseline = self.g.resource_rate()
        install(self.g, "asteroid_network")
        self.assertEqual(self.g.resource_rate(), baseline+600)
        self.assertEqual(statistics.sample(self.g, "player")[4], baseline+600)
        settle(self.g, 0, 0)
        regular = sum(self.g.planet_resources(p) for p in self.g.systems[0].worlds if p.colonized)
        self.assertEqual(self.g.resource_rate(), regular+600)
        from orion.empire import summarize_empire
        self.assertEqual(summarize_empire(self.g).resources, regular+600)
        start, rate = self.g.resources, self.g.resource_rate()
        self.g.advance_turn()
        self.assertEqual(self.g.resources-start, rate)

    def test_dyson_unlimited_empire_energy_without_backup_fuel(self):
        other = settle(self.g, self.sid)
        install(self.g, "dyson_sphere")
        from orion.buildings import BUILDINGS
        loads = [k for k, v in BUILDINGS.items() if v.energy_use]
        for p in (self.p, other):
            p.buildings = loads[:]
            p.ascension_gate = True
            report = self.g.planet_energy(p)
            self.assertTrue(report.unlimited)
            self.assertFalse(report.offline)
            self.assertTrue(report.gate_powered)
            self.assertEqual(report.fuel_used, 0)
            self.assertEqual(report.used, report.demand)
        json.dumps(self.g.to_dict(), allow_nan=False)
        json.dumps(statistics.sample(self.g, "player"), allow_nan=False)

    def test_dyson_does_not_power_other_empires(self):
        g = campaign(True)
        install(g, "dyson_sphere")
        rival = next(p for s in g.systems for p in s.worlds if p.owner == "rival")
        self.assertFalse(g.planet_energy(rival).unlimited)
        self.assertTrue(g.planet_energy(g.planet_at(0, 2)).unlimited)

    def test_dyson_before_completion_is_finite(self):
        install(self.g, "dyson_sphere", stage=3)
        self.assertFalse(self.g.planet_energy(self.p).unlimited)
        self.assertGreaterEqual(self.g.planet_energy(self.p).generated, 90)

    def test_forge_accelerates_ships_not_industry_buildings_or_goods(self):
        p = self.p
        base = self.g.planet_yields(p)
        install(self.g, "stellar_forge")
        self.assertEqual(self.g.planet_yields(p), base)
        p.construction_queue = [ConstructionProject("titan"), ConstructionProject("factory")]
        p.advance_construction(self.g.bonuses_for(), fund=lambda q: True)
        self.assertEqual(p.construction_queue[0].progress, base[0]*13)
        p.construction_queue = [ConstructionProject("factory")]
        p.advance_construction(self.g.bonuses_for(), fund=lambda q: True)
        self.assertEqual(p.construction_queue[0].progress, base[0])
        p.trade_goods = True
        before = self.g.trade_goods_income(p)
        self.g.systems[0].megastructure = None
        self.assertEqual(self.g.trade_goods_income(p), before)

    def test_forge_mixed_queue_overflow_cannot_speed_up_buildings(self):
        install(self.g, "stellar_forge")
        ship = ConstructionProject("scout")
        self.p.construction_queue = [ship, ConstructionProject("factory")]
        self.p.advance_construction(self.g.bonuses_for(), fund=lambda q: True)
        self.assertEqual(len(self.p.construction_queue), 1)
        self.assertEqual(self.p.construction_queue[0].progress, 3)  # 52 ticks - 12 ship ticks; 13 per building work.

    def test_forge_is_local_to_its_system(self):
        other = settle(self.g, self.sid)
        install(self.g, "stellar_forge")
        self.assertEqual(economy.local_bonuses(self.p, self.g.bonuses_for())["ship_work_multiplier"], 13)
        self.assertNotIn("ship_work_multiplier", economy.local_bonuses(other, self.g.bonuses_for()))

    def test_array_produces_no_ordinary_research_points(self):
        unlock(self.g, "research_array")
        before = self.g.empire_rates[1]
        install(self.g, "research_array")
        self.assertEqual(self.g.empire_rates[1], before)

    def test_array_can_recover_excluded_choice_and_roundtrip(self):
        install(self.g, "research_array")
        alternative = choices("physics", 1)[1].id
        self.assertEqual(self.g.technology.status(alternative), "excluded")
        self.g._settle_power()
        with patch("orion.megastructures.random.Random") as rng:
            rng.return_value.randrange.return_value = 0
            rng.return_value.choice.return_value = alternative
            messages = mega.discover(self.g)
        self.assertEqual(len(messages), 1)
        self.assertIn(alternative, self.g.technology.completed)
        clone = GameState.from_dict(self.g.to_dict())
        self.assertEqual(clone.technology, self.g.technology)
        self.assertEqual(clone.technology.status(alternative), "discovered")

    def test_array_refunds_active_tech_and_skips_known_tech(self):
        install(self.g, "research_array")
        identifier = choices("biology", 1)[0].id
        state = self.g.technology
        state.active, state.progress = identifier, 9
        bank = self.g.research
        self.g._settle_power()
        with patch("orion.megastructures.random.Random") as rng:
            rng.return_value.randrange.return_value = 0
            rng.return_value.choice.return_value = identifier
            mega.discover(self.g)
        self.assertEqual(self.g.research, bank+9)
        self.assertIsNone(state.active)
        self.assertEqual(state.progress, 0)
        self.assertEqual(GameState.from_dict(self.g.to_dict()).technology, state)

    def test_array_randomness_reproducible_and_previews_dont_discover(self):
        install(self.g, "research_array")
        self.g._settle_power()
        clone = GameState.from_dict(self.g.to_dict())
        clone._settle_power()
        self.assertEqual(mega.discover(self.g), mega.discover(clone))
        self.assertEqual(self.g.technology, clone.technology)
        before = self.g.to_dict()
        for _ in range(5):
            self.g.empire_rates
            self.g.resource_rate()
            mega.make_plan(self.g, "player")
        self.assertEqual(self.g.to_dict(), before)

    def test_save_rejects_invalid_progress_duplicate_claim_and_fake_recovery(self):
        install(self.g, "dyson_sphere")
        data = self.g.to_dict()
        for key, value in (("stage", 5), ("progress", 1), ("hull", 0), ("allocation", 101)):
            bad = deepcopy(data)
            bad["systems"][0]["megastructure"][key] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(bad)
        bad = deepcopy(data)
        bad["systems"][self.sid]["megastructure"] = deepcopy(bad["systems"][0]["megastructure"])
        with self.assertRaises(SaveError):
            GameState.from_dict(bad)
        bad = deepcopy(data)
        bad["technology"]["recovered"] = ["not_a_technology"]
        with self.assertRaises(SaveError):
            GameState.from_dict(bad)

    def test_old_save_and_balance_upgrade(self):
        data = self.g.to_dict()
        data.pop("megastructure_history")
        for s in data["systems"]:
            s.pop("megastructure")
        data["technology"].pop("recovered")
        self.assertEqual(GameState.from_dict(data, version=41), self.g)
        profile = balance.default_profile()
        profile["version"] = 6
        del profile["data"]["megastructures"]
        del profile["data"]["rules"]["megastructures"]
        self.assertEqual(balance.upgrade_profile(profile), balance.default_profile())

    def test_editor_changes_real_outputs_and_rejects_invalid_branch(self):
        from orion.balance_document import BalanceDocument
        document = BalanceDocument()
        fields = dict(document.fields("megastructures", "stellar_forge"))
        self.assertIn(("ship_speed_per_stage",), fields)
        self.assertNotIn(("resources_per_stage",), fields)
        self.assertNotIn("ascension", dict(document.options("megastructures", ("branch",))))
        install(self.g, "asteroid_network")
        self.assertEqual(mega.plan_for(self.g, "player").resource_income, 600)
        profile = balance.default_profile()
        profile["data"]["megastructures"]["asteroid_network"]["resources_per_stage"] = 250
        balance.activate(profile)
        self.assertEqual(mega.plan_for(self.g, "player").resource_income, 1000)
        profile["data"]["megastructures"]["stellar_forge"]["branch"] = "ascension"
        self.assertTrue(balance.validate(profile))

    def test_array_handles_exhausted_tree_and_disabled_science(self):
        install(self.g, "research_array")
        self.g.victory_conditions = ()
        self.g.technology.completed = [t for t in TECHNOLOGIES if t != "ascension_theory"]
        self.g._settle_power()
        with patch("orion.megastructures.random.Random") as rng:
            rng.return_value.randrange.return_value = 0
            self.assertEqual(mega.discover(self.g), [])
            rng.return_value.choice.assert_not_called()

    def test_ai_obeys_control_research_and_reserve_requirements(self):
        g = campaign(True)
        g.opponent.resources = 5000
        home = g.colony_systems("rival")[0]
        unlock(g, "asteroid_network", "rival")
        mega.ai_orders(g, "rival")
        self.assertEqual(home.megastructure.kind, "asteroid_network")
        self.assertEqual(home.megastructure.allocation, 25)
        g.opponent.resources = 0
        mega.ai_orders(g, "rival")
        self.assertTrue(home.megastructure.paused)
        self.assertEqual(g.megastructure_history["rival"], ["asteroid_network"])

    def test_saved_profile_and_stage_roundtrip(self):
        m = install(self.g, "asteroid_network", stage=2)
        m.progress = 12
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            clone, _ = store.load(store.save(self.g))
        self.assertEqual(clone, self.g)
        self.assertEqual(clone.resource_rate(), self.g.resource_rate())

    def test_forecast_matches_turns_with_stage_completion_and_diversion(self):
        m = install(self.g, "stellar_forge", stage=0)
        m.progress = m.stage_work-3
        self.p.construction_queue = [ConstructionProject("scout", paid_resources=25, resource_cost=25),
                                     ConstructionProject("factory", paid_resources=30, resource_cost=30)]
        before = self.g.to_dict()
        estimate = self.g.queue_estimates(self.p)
        self.assertEqual(self.g.to_dict(), before)
        actual = []
        for turn in range(1, 150):
            count = len(self.p.construction_queue)
            self.g.advance_turn()
            actual.extend([turn]*(count-len(self.p.construction_queue)))
            if not self.p.construction_queue:
                break
        self.assertEqual(estimate, actual)

    def test_capture_pauses_work_and_does_not_stack_duplicates(self):
        g = campaign(True)
        settle(g, next(s.id for s in g.systems[1:] if s.worlds and not any(p.colonized for p in s.worlds)))
        m = install(g, "asteroid_network")
        g.planet_at(0, 2).owner = "rival"
        mega.normalize(g)
        self.assertEqual(m.owner, "rival")
        self.assertTrue(m.paused)
        rival_home = next(s.id for s in g.colony_systems("rival") if s.id != 0)
        install(g, "asteroid_network", rival_home, owner="rival")
        self.assertEqual(mega.make_plan(g, "rival").resource_income, 600)
        self.assertEqual(GameState.from_dict(g.to_dict()).megastructure_history, g.megastructure_history)

    def test_attack_uses_shared_bombardment_action_and_repairs_cost_resources(self):
        g = campaign(True)
        m = install(g, "stellar_forge")
        ship = Ship(g.next_ship_id, "frigate", 0, owner="rival")
        g.next_ship_id += 1
        g.ships.append(ship)
        self.assertIsNone(mega.attack_error(g, 0, "rival"))
        mega.attack(g, 0, "rival")
        self.assertEqual(ship.bombarded_turn, g.turn)
        self.assertIsNotNone(mega.attack_error(g, 0, "rival"))
        self.assertLess(m.hull, m.max_hull)
        self.assertFalse(mega.make_plan(g, "player").orders)  # Blockaded.
        g.ships.clear()
        plan = mega.make_plan(g, "player")
        self.assertTrue(plan.orders[0][3])
        self.assertEqual(plan.orders[0][2], plan.orders[0][1]*mega.REPAIR_RESOURCES)

    def test_stale_survey_does_not_leak_current_megastructure(self):
        self.g.fog_of_war = True
        install(self.g, "asteroid_network", stage=2)
        exploration.record_survey(self.g, 0, "player")
        self.p.colonized, self.p.owner, self.p.population = False, None, 0
        self.p.farmers = self.p.miners = self.p.scientists = 0
        self.g.systems[0].megastructure.stage = 3
        stale = self.g.known_system(0)
        self.assertEqual(stale.megastructure.stage, 2)
        self.g.systems[0].megastructure = None
        self.assertEqual(self.g.known_system(0).megastructure.stage, 2)


class MegastructureUITests(unittest.TestCase):
    def test_catalog_controls_system_view_and_unlimited_energy_render(self):
        import pygame as pg
        from orion.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), capture=True)
            try:
                app.game = campaign()
                app.game.selected_system = 0
                unlock(app.game, "dyson_sphere")
                app.go("megastructure")
                app.render()
                buttons = {b.key: b for b in app.buttons}
                self.assertTrue(buttons["mega_start_dyson_sphere"].enabled)
                buttons["mega_start_dyson_sphere"].action()
                self.assertIsNotNone(app.dialog)
                app.accept_dialog()
                app.render()
                buttons = {b.key: b for b in app.buttons}
                buttons["mega_allocation_100"].action()
                self.assertEqual(app.game.systems[0].megastructure.allocation, 100)
                buttons["mega_pause"].action()
                self.assertTrue(app.game.systems[0].megastructure.paused)
                before = app.game.to_dict()
                app.render()
                self.assertEqual(app.game.to_dict(), before)
                m = app.game.systems[0].megastructure
                m.stage, m.hull = 4, 1000
                app.go("system")
                app.render()
                self.assertIn("system_megastructure_details", [b.key for b in app.buttons])
                app.game.selected_planet = 2
                app.go("planet")
                app.render()
                app.go("empire")
                app.render()
            finally:
                pg.quit()
