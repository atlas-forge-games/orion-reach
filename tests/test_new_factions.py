"""Accession, retained species, invasion replacement and v0.68.1 compatibility."""

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from orion import accession, balance, exploration, population, species
from orion.model import GameState, RuleError, SaveError, ConstructionProject, new_game
from orion.races import RACES


def campaign(race="serevan", rival="lithar", ai=True):
    return new_game(seed=4242, race_id=race, rival_race_id=rival if ai else None,
        with_ai=ai, random_starts=False, with_guardians=False, with_tombs=False,
        with_black_holes=False, with_encounters=False, fog_of_war=False, victory_conditions=())


def frontier(game):
    p = game.planet_at(0, 3)
    p.owner, p.colonized, p.population = "rival", True, 6
    p.biome, p.size = "Terran", "Small"
    p.species = {game.opponent.race_id: p.population}
    game.diplomacy.relations = 40
    exploration.refresh(game)
    return p


class FactionRulesTests(unittest.TestCase):
    def test_roster_and_portraits_and_round_trip(self):
        for race in ("serevan", "skirr", "concord"):
            g = campaign(race, ai=False)
            g.advance_turn()
            self.assertEqual(GameState.from_dict(g.to_dict()), g)
        self.assertEqual(len(RACES), 13)
        self.assertEqual(RACES["concord"].name, "Dominion of One")
        self.assertEqual(RACES["kharuun"].name, "Kharuun")

    def test_union_accession_preserves_species_buildings_and_local_traits(self):
        g = campaign()
        p = frontier(g)
        g.headquarters()[1].buildings = ["trade_center", "trade_center"]
        p.buildings = ["factory"]
        before = p.population
        mission = accession.start(g, 0, p.id)
        self.assertEqual(g.credits, 90)
        self.assertGreater(accession.support(g, mission)[0], 0)
        # Exercise a complete campaign of successful outreach ticks.
        for _ in range(30):
            if p.owner == "player":
                break
            g.turn += 1
            g.year += 1
            accession.advance(g, [])
        self.assertEqual(p.owner, "player")
        self.assertEqual(p.population, before)
        self.assertEqual(p.species, {"lithar": before})
        self.assertIn("factory", p.buildings)
        report = g.population_report(p)
        self.assertEqual(report.capacity, population.POPULATION_LIMITS[p.size]*2)
        self.assertEqual(report.consumed, 3)
        self.assertEqual(report.growth_percent, 25)
        self.assertFalse(g.union_missions)
        exploration.refresh(g)
        self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_missions_are_saved_and_cost_five_credits_per_turn(self):
        g = campaign()
        p = frontier(g)
        before = g.empire_rates[0]
        m = accession.start(g, 0, p.id)
        m.progress = 37
        self.assertEqual(g.empire_rates[0], before-5)
        h = GameState.from_dict(g.to_dict())
        self.assertEqual(h.union_missions[0].progress, 37)
        accession.cancel(h, 0, p.id)
        self.assertEqual(h.empire_rates[0], before)

    def test_real_turn_accounts_for_outreach_and_completes_accession(self):
        from orion.empire import summarize_empire
        g = campaign()
        p = frontier(g)
        g.headquarters()[1].buildings = ["trade_center", "trade_center"]
        accession.start(g, 0, p.id).progress = 99
        before, income = g.credits, g.empire_rates[0]
        summary = summarize_empire(g)
        self.assertEqual(summary.gross_income-summary.maintenance, income)
        with patch("orion.ai.run_ai", return_value=[]):
            report = g.advance_turn()
        self.assertEqual(report.income, income)
        self.assertEqual(g.credits, before+income)
        self.assertEqual(p.owner, "player")
        self.assertIn("lithar", p.species)
        self.assertIn("lithar", g.legacy.willing["player"])
        self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_active_mission_ends_when_target_is_conquered(self):
        g = campaign()
        p = frontier(g)
        accession.start(g, 0, p.id)
        p.owner = "player"
        accession.advance(g, [])
        self.assertFalse(g.union_missions)

    def test_civic_investment_decays_support_and_war_blocks_progress(self):
        g = campaign()
        p = frontier(g)
        m = accession.start(g, 0, p.id)
        m.progress = 50
        accession.invest(g, 0, p.id, "rival")
        accession.advance(g, [])
        self.assertEqual(m.progress, 38)
        p.loyalty_until = 0
        g.diplomacy.relations = -100
        self.assertLess(accession.support(g, m)[0], 0)
        self.assertNotEqual(p.owner, "player")

    def test_civic_investment_protects_eight_completed_turns(self):
        g = campaign()
        p = frontier(g)
        g.headquarters()[1].buildings = ["trade_center", "trade_center"]
        m = accession.start(g, 0, p.id)
        accession.invest(g, 0, p.id, "rival")
        for _ in range(8):
            g.turn += 1
            self.assertEqual(accession.support(g, m)[0], -12)
        g.turn += 1
        self.assertGreater(accession.support(g, m)[0], 0)

    def test_capitals_collectives_and_unseen_targets_are_protected(self):
        g = campaign()
        self.assertIn("Capitals", accession.eligibility(g, "player", g.opponent.home_system, g.opponent.home_planet))
        for rid in ("skirr", "nexus", "concord"):
            g = campaign(rival=rid)
            p = frontier(g)
            self.assertIn("collective", accession.start_error(g, "player", 0, p.id))
        g = campaign()
        p = frontier(g)
        g.fog_of_war = True
        # Move all local observers away; retain only an old survey.
        for ship in g.ships:
            if ship.owner == "player":
                ship.system_id = 1
        p2 = g.systems[g.opponent.home_system].worlds[0]
        if p2.id == g.opponent.home_planet:
            self.skipTest("This seed has no second rival-system planet")
        p2.owner, p2.colonized, p2.population = "rival", True, 3
        self.assertIn("scanners", accession.eligibility(g, "player", g.opponent.home_system, p2.id))

    def test_skirr_growth_food_colony_cost_and_build_speed(self):
        g = campaign("skirr", ai=False)
        p = g.headquarters()[1]
        report = g.population_report(p)
        ordinary = replace(report, growth_percent=100)
        self.assertEqual(report.consumed, 12)
        self.assertEqual(report.growth_rate, ordinary.growth_rate*3)
        self.assertEqual(g.project_price("colony_ship"), 360)
        self.assertEqual(g.starting_colonists(), 2)
        normal, brood = deepcopy(p), deepcopy(p)
        normal.construction_queue = [ConstructionProject("colony_ship")]
        brood.construction_queue = [ConstructionProject("colony_ship")]
        normal.advance_construction({}, fund=lambda p: True)
        brood.advance_construction({"colony_work_multiplier": 2}, fund=lambda p: True)
        self.assertEqual(brood.construction_queue[0].progress, normal.construction_queue[0].progress*2)

    def test_swarm_starvation_replacement_and_liberation(self):
        g = campaign("skirr", rival="serevan")
        p = g.headquarters()[1]
        p.species = {"terran": 8}
        g.turn, g.year = 2, 2301
        species.advance_swarm(g, [])
        self.assertEqual(p.species, {"terran": 7, "skirr": 1})
        p.owner = "rival"
        g.turn, g.year = 4, 2303
        species.advance_swarm(g, [])
        self.assertEqual(p.species, {"terran": 7, "skirr": 1})
        p.owner = "player"
        p.farmers, p.scientists, p.miners = 0, 0, 0
        p.biome = "Desert"
        population.advance(p, g.population_report(p))
        self.assertEqual(p.population, 7)
        self.assertEqual(sum(p.species.values()), 7)
        self.assertEqual(p.growth_progress, 0)

    def test_swarm_rejects_treaties_in_both_directions(self):
        for race, rival in (("terran", "skirr"), ("skirr", "terran")):
            g = campaign(race, rival)
            g.diplomacy.relations = 100
            for action in ("trade", "research", "friendship", "non_aggression"):
                self.assertIn("Skirr", g.diplomacy_error(action))

    def test_version_49_save_migrates_name_and_population(self):
        g = campaign("concord", ai=False)
        data = g.to_dict()
        data["empire_name"] = "Concord Collective"
        data.pop("union_missions")
        for s in data["systems"]:
            for p in s["worlds"]:
                p.pop("species")
                p.pop("loyalty_until")
        h = GameState.from_dict(data, version=49)
        self.assertEqual(h.empire_name, "Dominion of One")
        self.assertEqual(h.headquarters()[1].species, {"concord": 8})

    def test_old_balance_profiles_gain_new_races_without_resetting_custom_costs(self):
        old = balance.default_profile()
        old["version"] = 13
        for section in ("races", "personalities", "alignment", "diplomatic_preferences"):
            for race in ("serevan", "skirr"):
                old["data"][section].pop(race)
        old["data"]["ships"]["colony_ship"]["resource_cost"] = 1000
        with balance.using_profile(old):
            self.assertIn("skirr", RACES)
            self.assertEqual(RACES["concord"].name, "Dominion of One")
            self.assertEqual(balance.active_profile()["data"]["ships"]["colony_ship"]["resource_cost"], 1000)

    def test_corrupted_species_and_mission_progress_are_rejected(self):
        g = campaign()
        p = frontier(g)
        accession.start(g, 0, p.id)
        data = g.to_dict()
        data["union_missions"][0]["progress"] = 1000
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        data = g.to_dict()
        data["systems"][0]["worlds"][2]["species"] = {"unknown": 8}
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
