"""Civilization endings through real state, production, migration and persistence."""
import copy
import unittest
from unittest.mock import patch
from orion import race_victory as legacy, victory, species, exploration
from orion.model import new_game, GameState, Ship, ConstructionProject, RuleError, SaveError
from orion.research import BRANCHES, choices, TECHNOLOGIES


def discover(game, owner="player", count=12):
    state = game.research_state(owner)
    for tier in (1, 2, 3):
        for branch in BRANCHES:
            options = choices(branch, tier)
            if options and state.choice_error(options[0].id) is None:
                state.active = options[0].id
                state.spend(options[0].cost)
                if len(state.completed) >= count:
                    return


def prepared(rid, game=None, owner="player"):
    game = game or new_game(race_id=rid, seed=2408, galaxy_size="Standard", with_ai=False,
                           with_guardians=False, with_tombs=False, with_black_holes=False,
                           with_encounters=False, victory_conditions=("race",))
    game.year += 40-game.turn
    game.turn = 40
    discover(game, owner)
    empire = game._empire(owner)
    empire.credits = empire.resources = empire.research = 10000
    spec = legacy.LEGACIES[rid]
    home = game.headquarters(owner)
    candidates = [home]
    seen = {home[0].kind}
    remaining = [(s, s.worlds[0]) for s in legacy.ordinary(game) if s.worlds and s.id != home[0].id and not any(p.colonized for p in s.worlds)]
    if rid == "aetheri":
        for row in remaining[:]:
            if row[0].kind not in seen:
                candidates.append(row); remaining.remove(row); seen.add(row[0].kind)
    candidates += remaining
    count = 1 if rid == "varkesh" else max(3, legacy.scale(game, owner))
    for i, (s, p) in enumerate(candidates[:count]):
        p.colonized, p.owner, p.population, p.size = True, owner, 12, "Huge"
        p.species = {rid: 12}
        p.biome = ("Desert", "Tundra", "Barren")[i % 3] if rid == "lithar" else ("Gaia", "Terran", "Ocean")[i % 3]
        p.buildings = ["solar_array", "hydroponic_farm", spec.building]
        p.disabled_buildings = []; p.construction_queue = []
        p.farmers = 0 if rid == "nexus" else 6
        p.scientists = 3 if rid == "nexus" else 0
        p.miners = 0
        p.garrison = 8
        if rid == "kharuun":
            p.buildings += ["factory", "mine"]
        game.legacy.sites.append(legacy.Site(owner, s.id, p.id, 20, 20))
    if rid in ("nexus", "remnant", "kharuun"):
        game.legacy.investments[owner] = (600 if rid == "kharuun" else 500)*legacy.scale(game, owner)
    if rid == "varkesh":
        game.legacy.trophies[owner] = [f"world:{s.id}:0" for s in game.systems if s.worlds and s.id != home[0].id][:3]
        for _ in range(30):
            game.ships.append(Ship(game.next_ship_id, "frigate", home[0].id, owner=owner))
            game.next_ship_id += 1
    if owner == "player":
        game.exploration.scanned_player = [s.id for s in legacy.ordinary(game)]
    elif owner == "rival":
        game.exploration.scanned_rival = [s.id for s in legacy.ordinary(game)]
    else:
        game.exploration.scanned_others[owner] = [s.id for s in legacy.ordinary(game)]
    for s in legacy.ordinary(game):
        exploration.record_survey(game, s.id, owner)
    species.normalize(game)
    for survey in list(game.exploration.surveys):
        exploration.record_survey(game, survey.system_id, survey.owner)
    return game


def tick(game):
    game.turn += 1
    game.year += 1
    legacy.advance(game, [])
    game.check_victory()


class CivilizationLegacyTests(unittest.TestCase):
    def test_all_twelve_planetary_civilizations_complete_and_reload(self):
        for rid in legacy.LEGACIES:
            with self.subTest(race=rid):
                game = prepared(rid)
                self.assertTrue(all(r.complete for r in legacy.requirements(game)), legacy.requirements(game))
                for _ in range(legacy.FINAL_TURNS-1):
                    tick(game)
                    self.assertIsNone(game.result)
                    self.assertEqual(GameState.from_dict(game.to_dict()), game)
                tick(game)
                self.assertEqual((game.result.winner, game.result.condition), ("player", "race"))
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_queries_are_pure_and_fog_is_not_personal_exploration(self):
        game = new_game(race_id="aelari", seed=10, fog_of_war=False, with_ai=False, with_guardians=False)
        before = copy.deepcopy(game.to_dict())
        for _ in range(3):
            legacy.requirements(game); victory.race_goal(game); legacy.research_reservation(game)
        self.assertEqual(game.to_dict(), before)
        self.assertLess(legacy.requirements(game)[1].current, legacy.requirements(game)[1].target)

    def test_unlock_racial_restriction_and_real_production_commission(self):
        game = new_game(race_id="terran", seed=20, with_ai=False, with_guardians=False, with_tombs=False)
        home = game.headquarters()[1]
        self.assertIn("8", game.build_error(0, 2, "charter_hall"))
        discover(game)
        self.assertIn("another", game.build_error(0, 2, "queen_nest"))
        game.resources = 1000
        game.queue_building(0, 2, "charter_hall")
        self.assertFalse(game.legacy.sites)
        order = home.construction_queue[0]
        game.fund_project(order, "player")
        order.progress = order.spec.work_cost-1
        game.queue_estimates(home)
        self.assertFalse(game.legacy.sites)
        game.advance_turn()
        self.assertIn("charter_hall", home.buildings)
        self.assertEqual(len(game.legacy.sites), 1)
        self.assertEqual(game.legacy.sites[0].age, 0)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_interruptions_reset_maturity_and_finale(self):
        for condition in ("power", "food", "bombardment"):
            game = prepared("skirr")
            tick(game)
            s, p = legacy.sites(game, "player")[0]
            if condition == "power":
                p.disabled_buildings = [p.buildings.index("queen_nest")]
            elif condition == "food":
                p.farmers = 0; p.biome = "Barren"
            else:
                p.bombarded_turn = game.turn
            tick(game)
            self.assertEqual(s.age, 0)
            self.assertEqual(game.legacy.final_turns["player"], 0)
            self.assertIsNone(game.result)

    def test_only_hostile_armed_ships_blockade(self):
        game = new_game(race_id="nexus", rival_race_id="terran", seed=20, with_guardians=False, victory_conditions=("race",))
        prepared("nexus", game)
        s, p = legacy.sites(game, "player")[0]
        scout = Ship(game.next_ship_id, "scout", s.system_id, owner="rival")
        game.next_ship_id += 1; game.ships.append(scout)
        self.assertIsNone(legacy.site_error(game, s, p))
        warship = Ship(game.next_ship_id, "frigate", s.system_id, owner="rival")
        game.next_ship_id += 1; game.ships.append(warship)
        game.diplomacy.relations = 50
        self.assertIsNone(legacy.site_error(game, s, p))
        game.diplomacy.end_agreements()
        game.diplomacy.relations = -100
        self.assertEqual(legacy.site_error(game, s, p), "Hostile blockade")

    def test_capture_and_demolition_remove_history_and_queued_legacy(self):
        game = prepared("skirr")
        s, p = legacy.sites(game, "player")[0]
        p.owner = None
        legacy.normalize(game)
        self.assertNotIn("queen_nest", p.buildings)
        self.assertNotIn(s, game.legacy.sites)
        s, p = legacy.sites(game, "player")[0]
        game.demolish_building(s.system_id, p.id, p.buildings.index("queen_nest"))
        self.assertNotIn(s, game.legacy.sites)
        p.buildings += ["queen_nest"]
        p.construction_queue.append(ConstructionProject("queen_nest"))
        legacy.strip(p)
        self.assertNotIn("queen_nest", p.buildings)
        self.assertFalse(p.construction_queue)

    def test_final_turn_cannot_advance_twice_and_failure_restarts_it(self):
        game = prepared("terran")
        tick(game)
        legacy.advance(game, [])
        self.assertEqual(game.legacy.final_turns["player"], 1)
        s, p = legacy.sites(game, "player")[0]
        p.disabled_buildings = [2]
        tick(game)
        self.assertEqual(game.legacy.final_turns["player"], 0)
        p.disabled_buildings = []
        tick(game)
        self.assertEqual(game.legacy.final_turns["player"], 1)

    def test_research_dedication_uses_real_bank_once_and_survives_reload(self):
        game = prepared("nexus")
        game.legacy.investments["player"] = 0
        game.research = 100
        tick(game)
        self.assertEqual((game.research, game.legacy.investments["player"]), (40, 60))
        legacy.advance(game, [])
        self.assertEqual(game.research, 40)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        for s, p in legacy.sites(game, "player"):
            p.scientists = 2
        tick(game)
        self.assertEqual(game.research, 40)

    def test_kharuun_uses_stored_resources_and_retains_investment(self):
        game = prepared("kharuun")
        game.legacy.investments["player"] = 0; game.resources = 25
        tick(game)
        self.assertEqual((game.resources, game.legacy.investments["player"]), (0, 25))
        for s, p in legacy.sites(game, "player"):
            p.disabled_buildings = [2]
        tick(game)
        self.assertEqual(game.legacy.investments["player"], 25)

    def test_dominion_converts_citizens_without_duplicating_population(self):
        game = prepared("concord")
        s, p = legacy.sites(game, "player")[0]
        p.species = {"terran": 12}
        tick(game)
        self.assertEqual(p.species, {"terran": 11, "concord": 1})
        self.assertEqual(p.population, 12)

    def test_union_migration_is_voluntary_conserves_population_and_marks_only_migrants(self):
        game = new_game(race_id="serevan", rival_race_id="terran", seed=20, with_guardians=False, victory_conditions=("race",))
        prepared("serevan", game)
        dest = legacy.sites(game, "player")[0][1]
        dest.species = {"serevan": 10, "aelari": 2}
        source = game.headquarters("rival")[1]
        source.species = {"terran": source.population}
        total = sum(p.population for _, p in game.settlements())
        game.turn = 41; game.year += 1
        tick(game)
        self.assertNotIn("terran", game.legacy.willing.get("player", []))
        game.diplomacy.relations = 50
        game.diplomacy.friendship_active = game.diplomacy.trade_active = game.diplomacy.non_aggression_active = True
        game.turn = 44; game.year += 2
        tick(game)
        self.assertEqual(sum(p.population for _, p in game.settlements()), total)
        self.assertIn("terran", game.legacy.willing["player"])
        self.assertNotIn("aelari", game.legacy.willing["player"])

    def test_varkesh_trophies_are_unique_and_solo_trials_cost_resources(self):
        game = prepared("varkesh")
        game.legacy.trophies = {}
        legacy.record_raid(game, "player", next(s.id for s in game.systems if s.worlds and s.id != 0), 0)
        legacy.record_raid(game, "player", next(s.id for s in game.systems if s.worlds and s.id != 0), 0)
        self.assertEqual(len(game.legacy.trophies["player"]), 1)
        game.turn = 41; game.year += 1
        before = game.resources
        tick(game)
        self.assertEqual(len(game.legacy.trophies["player"]), 2)
        self.assertEqual(game.resources, before-200)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_queues_own_installation_and_real_ai_turn_can_win(self):
        game = new_game(seed=20, rival_race_id="nexus", with_guardians=False, with_tombs=False, victory_conditions=("race",))
        prepared("nexus", game, "rival")
        game.legacy.final_turns["rival"] = 4
        game.advance_turn()
        self.assertEqual((game.result.winner, game.result.condition), ("rival", "race"))
        game = new_game(seed=20, rival_race_id="nexus", with_guardians=False, victory_conditions=("race",))
        discover(game, "rival")
        home = game.headquarters("rival")[1]
        home.buildings = ["solar_array", "trade_center"]
        game.opponent.resources = game.opponent.credits = 1000
        legacy.ai_orders(game, "rival")
        self.assertEqual(home.construction_queue[0].item_id, "processing_core")

    def test_simultaneous_completions_draw_and_eliminated_empires_do_not_win(self):
        game = new_game(race_id="nexus", rival_race_id="nexus", seed=20, with_guardians=False, victory_conditions=("race",))
        prepared("nexus", game)
        prepared("nexus", game, "rival")
        game.legacy.final_turns = {"player": 4, "rival": 4}
        tick(game)
        self.assertEqual((game.result.winner, game.result.condition), (None, "race"))

    def test_current_save_validation_rejects_forged_state(self):
        game = prepared("nexus")
        for mutate in (lambda d: d["legacy"]["sites"][0].update(age=10000),
                       lambda d: d["legacy"]["final_turns"].update(player=6),
                       lambda d: d["legacy"]["investments"].update(intruder=1),
                       lambda d: d["legacy"]["willing"].update(player=["nexus"])):
            raw = game.to_dict(); mutate(raw)
            with self.assertRaises(SaveError):
                GameState.from_dict(raw)

    def test_gate_research_and_new_science_campaigns_are_retired(self):
        with self.assertRaises(SaveError):
            new_game(victory_conditions=("science",))
        game = prepared("nexus")
        with self.assertRaises(RuleError):
            game.choose_research("ascension_theory")
        with self.assertRaises(RuleError):
            game.queue_gate(0, 2)

    def test_active_old_campaign_refunds_ascension_and_preserves_other_progress(self):
        game = prepared("nexus")
        for s, p in legacy.sites(game, "player"):
            legacy.strip(p)
        game.legacy = legacy.LegacyState()
        state = game.technology
        # A historically valid capstone requires every research branch first.
        from test_victory import discover_branches
        game = new_game(seed=20, with_ai=False, with_guardians=False)
        discover_branches(game)
        state = game.technology
        state.active, state.progress = "ascension_theory", 1234
        game.victory_conditions = ("conquest", "science", "council")
        raw = game.to_dict()
        restored = GameState.from_dict(raw, version=50)
        self.assertIsNone(restored.technology.active)
        self.assertEqual(restored.research, game.research+1234)
        self.assertEqual(restored.victory_conditions, victory.CONDITIONS)
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)
        self.assertEqual(raw, game.to_dict())

    def test_completed_science_snapshot_remains_historical_and_resaveable(self):
        from test_victory import discover_branches
        from orion.production import GATE_CHARGE_TURNS
        game = new_game(seed=20, with_ai=False, with_guardians=False)
        discover_branches(game)
        game.technology.completed.append("ascension_theory")
        game.victory_conditions = ("science",)
        home = game.headquarters()[1]
        home.ascension_gate, home.gate_charge = True, GATE_CHARGE_TURNS
        game.check_victory()
        restored = GameState.from_dict(game.to_dict(), version=50)
        self.assertEqual(restored.result.condition, "science")
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_actual_turn_diverts_research_before_spending_on_technology(self):
        game = prepared("nexus")
        game.legacy.investments["player"] = 0
        game.research = 0
        technology = next(t for t in TECHNOLOGIES.values() if t.id != "ascension_theory" and game.research_error(t.id) is None)
        game.choose_research(technology.id)
        income = game.empire_rates[1]
        game.advance_turn()
        paid = game.legacy.investments["player"]
        self.assertEqual(paid, min(60, income))
        self.assertEqual(paid+game.technology.progress+game.research, income)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_galaxy_scaling_and_absent_ancient_sites_remain_finishable(self):
        for size, expected in (("Compact", 2), ("Standard", 3), ("Expansive", 5)):
            game = new_game(galaxy_size=size, race_id="remnant", seed=20, with_ai=False, with_tombs=False, with_guardians=False)
            self.assertEqual(legacy.scale(game, "player"), expected)
            with patch("orion.exploration.discovery_at", return_value=None):
                requirement = legacy.requirements(game)[-1]
                self.assertEqual(requirement.target, 0)
                self.assertTrue(requirement.complete)
            game.race_id = "skirr"
            self.assertEqual(legacy.scale(game, "player"), expected+1)

    def test_built_and_queued_gate_refunds_preserve_other_projects(self):
        from test_victory import discover_theory
        from orion.production import ASCENSION_GATE
        for built in (False, True):
            game = new_game(seed=20, with_ai=False, with_guardians=False)
            discover_theory(game)
            home = game.headquarters()[1]
            if built:
                home.ascension_gate, home.gate_charge = True, 3
            else:
                game.resources = 1000
                q = ConstructionProject("ascension_gate", resource_cost=ASCENSION_GATE.resource_cost)
                game.fund_project(q, "player")
                q.progress = 10
                home.construction_queue.append(q)
            home.construction_queue.append(ConstructionProject("factory"))
            before_resources, before_research = game.resources, game.research
            restored = GameState.from_dict(game.to_dict(), version=50)
            self.assertFalse(restored.headquarters()[1].ascension_gate)
            self.assertEqual([q.item_id for q in restored.headquarters()[1].construction_queue], ["factory"])
            self.assertEqual(restored.resources, before_resources+ASCENSION_GATE.resource_cost)
            self.assertEqual(restored.research, before_research+TECHNOLOGIES["ascension_theory"].cost)
            self.assertNotIn("ascension_theory", restored.technology.completed)
            self.assertEqual(GameState.from_dict(restored.to_dict()), restored)
