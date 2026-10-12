from scenarios import legacy_research_payload
"""Varkesh movement, slave raids, population accounting, AI and save continuity."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion import combat, news, raiding, tomb_worlds
from orion.ai import enemies, invasion_orders, run_ai
from orion.empire import summarize_empire
from orion.exploration import record_survey, refresh
from orion.ground_combat import forces, resolve
from orion.model import ConstructionProject, GameState, Planet, RuleError, SaveError, Ship
from orion.population import farmers_needed
from orion.storage import Storage
from scenarios import empty_fleet_game, fixed_start_game, place_near


def scenario(**kwargs):
    return empty_fleet_game(seed=2408, race_id=kwargs.pop("race_id", "varkesh"),
                            fog_of_war=kwargs.pop("fog_of_war", False), **kwargs)


def target(game):
    sid, pid = game.opponent.home_system, game.opponent.home_planet
    return sid, pid, game.planet_at(sid, pid)


def transports(game, sid, count=2, owner="player"):
    for _ in range(count):
        game.ships.append(Ship(game.next_ship_id, "troop_transport", sid, owner=owner))
        game.next_ship_id += 1


def spare_colony(game, owner="rival"):
    sid, pid = raiding.home_location(game, owner)
    planet = next(p for p in game.systems[sid].worlds if not p.colonized)
    planet.owner, planet.colonized, planet.population, planet.farmers = owner, True, 3, 2
    return planet


class VarkeshMovementTests(unittest.TestCase):
    def test_speed_and_range_are_50_percent_greater_with_research_multiplying(self):
        game = scenario(with_ai=False)
        place_near(game, 1, distance=10.5)
        self.assertEqual(game.fuel_range(), 10.5)
        self.assertTrue(game.within_fuel_range(1))
        place_near(game, 2, distance=10.501)
        self.assertFalse(game.within_fuel_range(2))
        self.assertEqual(game.travel_turns(game.systems[0], game.systems[1]), 4)
        for technologies, speed, reach in (([], 50, 10.5), (["ion_drives"], 87.5, 10.5),
                                           (["ion_drives", "fusion_drives"], 162.5, 10.5),
                                           (["lightweight_alloys"], 50, 25.5),
                                           (["lightweight_alloys", "composite_structures"], 50, 48)):
            game.technology.completed = technologies
            self.assertEqual((game.ship_speed_bonus(), game.fuel_range()), (speed, reach))
            self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_fractional_speed_snapshot_roundtrips_and_research_does_not_retime_flight(self):
        game = scenario(with_ai=False)
        game.technology.completed = ["ion_drives"]
        place_near(game, 1, distance=10)
        game.ships = [Ship(1, "scout", 0)]
        game.next_ship_id = 2
        self.assertEqual(game.send_ship(1, 1), 3)
        self.assertEqual(game.ships[0].speed_bonus, 87.5)
        game.advance_turn()
        remaining = game.ships[0].turns_remaining
        game.technology.completed.append("fusion_drives")
        self.assertEqual(game.ships[0].turns_remaining, remaining)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_player_and_ai_cannot_colonize_any_biome_or_build_colony_ships(self):
        game = scenario(rival_race_id="varkesh")
        for owner in game.owners:
            sid, _ = raiding.home_location(game, owner)
            home = raiding.homeworld(game, owner)
            world = next(p for p in game.systems[sid].worlds if not p.colonized)
            game.research_state(owner).completed = ["radiation_shields", "ion_drives", "thermal_barriers"]
            game.ships.append(Ship(game.next_ship_id, "colony_ship", sid, owner=owner))
            game.next_ship_id += 1
            ship = game.ships[-1]
            for biome in ("Terran", "Ocean", "Gaia", "Barren", "Volcanic"):
                world.biome = biome
                self.assertFalse(game.can_settle(world, owner))
                before = game.to_dict()
                with self.assertRaisesRegex(RuleError, "cannot colonize"):
                    game.colonize(ship.id, sid, world.id, owner=owner)
                self.assertEqual(game.to_dict(), before)
            with self.assertRaisesRegex(RuleError, "cannot colonize"):
                game.queue_ship(sid, home.id, "colony_ship", owner=owner)

    def test_starting_raiding_fleets_for_human_and_ai_have_no_colony_ship(self):
        game = fixed_start_game(seed=2408, race_id="varkesh", rival_race_id="varkesh")
        for owner in game.owners:
            self.assertEqual(sorted(s.kind for s in game.ships_owned_by(owner)),
                             ["frigate", "scout", "scout", "troop_transport", "troop_transport"])
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_retreat_uses_new_speed_and_can_be_saved_awaiting_acknowledgement(self):
        game = scenario(fog_of_war=True)
        place_near(game, 1, distance=9)
        game.ships = [Ship(1, "frigate", 1), Ship(2, "frigate", 1, owner="rival")]
        game.next_ship_id = 3
        game.start_combat(1)
        game.combat_retreat()
        self.assertEqual(game.ships[0].speed_bonus, 50)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))


class VarkeshRaidTests(unittest.TestCase):
    def test_winning_raid_takes_population_and_real_credits_and_abandons_empty_colony(self):
        game = scenario()
        sid, pid, planet = target(game)
        home = game.planet_at(0, 2)
        planet.buildings = ["factory"]
        planet.construction_queue = [ConstructionProject("mine", progress=3)]
        transports(game, sid)
        expected = resolve(16, forces(planet))
        before_total = game.credits+game.opponent.credits
        report = game.invade(sid, pid)
        self.assertEqual((report.cause, report.captured, report.slaves_taken, report.credits_stolen), ("raid", True, 8, 80))
        self.assertEqual(report.rounds, expected.rounds)
        self.assertEqual((home.slaves, home.garrison), (8, expected.attackers))
        self.assertEqual(game.credits+game.opponent.credits, before_total)
        self.assertEqual((game.credits, game.opponent.credits), (200, 40))
        self.assertEqual((planet.population, planet.slaves, planet.owner, planet.colonized), (0, 0, None, False))
        self.assertFalse(planet.buildings or planet.construction_queue or game.ships)
        self.assertTrue(report.colony_razed)
        self.assertEqual(game.result.winner, "player")
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_capacity_limits_captures_and_does_not_transfer_colony_ownership(self):
        game = scenario()
        home = game.planet_at(0, 2)
        home.slaves = 98
        sid, pid, planet = target(game)
        planet.buildings = ["mine"]
        planet.construction_queue = [ConstructionProject("research_lab", progress=1)]
        transports(game, sid)
        report = game.invade(sid, pid)
        self.assertEqual((home.slaves, report.slaves_taken, planet.population), (100, 2, 6))
        self.assertEqual(planet.owner, "rival")
        self.assertTrue(planet.colonized)
        self.assertEqual(planet.buildings, ["mine"])
        self.assertEqual(planet.construction_queue[0].progress, 1)
        self.assertEqual(forces(planet).troops, 0)
        self.assertIsNone(game.result)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_full_home_still_allows_credit_raid_without_removing_people(self):
        game = scenario()
        game.planet_at(0, 2).slaves = 100
        sid, pid, planet = target(game)
        transports(game, sid)
        report = game.invade(sid, pid)
        self.assertEqual((report.slaves_taken, report.credits_stolen, planet.population, planet.owner), (0, 80, 8, "rival"))
        self.assertFalse(report.colony_razed)

    def test_credit_theft_is_capped_by_victim_treasury_including_zero(self):
        for credits in (0, 3, 47):
            game = scenario()
            game.opponent.credits = credits
            sid, pid, _ = target(game)
            transports(game, sid)
            report = game.invade(sid, pid)
            self.assertEqual((report.credits_stolen, game.credits, game.opponent.credits), (credits, 120+credits, 0))

    def test_defeated_raid_takes_nothing_and_keeps_ground_casualties(self):
        game = scenario()
        sid, pid, planet = target(game)
        planet.buildings, planet.garrison = ["barracks", "fortifications"], 8
        expected = resolve(16, forces(planet))
        transports(game, sid)
        report = game.invade(sid, pid)
        self.assertFalse(report.captured)
        self.assertEqual((report.slaves_taken, report.credits_stolen, game.planet_at(0, 2).slaves), (0, 0, 0))
        self.assertEqual((planet.owner, planet.population, forces(planet).troops), ("rival", 8, expected.defenders))
        self.assertEqual((game.credits, game.opponent.credits), (120, 120))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_raids_end_treaties_even_when_repelled(self):
        game = scenario()
        sid, pid, planet = target(game)
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        planet.garrison = 100
        transports(game, sid)
        game.invade(sid, pid)
        self.assertEqual(game.diplomacy.relations, -100)
        self.assertFalse(game.diplomacy.trade_active or game.diplomacy.research_active)

    def test_orbit_must_be_clear_and_missing_home_is_rejected_without_mutation(self):
        game = scenario()
        sid, pid, _ = target(game)
        transports(game, sid)
        game.ships.append(Ship(game.next_ship_id, "scout", sid, owner="rival"))
        game.next_ship_id += 1
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "Clear all opposing"):
            game.invade(sid, pid)
        self.assertEqual(before, game.to_dict())
        game.ships.pop()
        spare_colony(game, "player")  # A compatible old Varkesh campaign with a second colony.
        game.planet_at(0, 2).owner = "rival"
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "original homeworld"):
            game.invade(sid, pid)
        self.assertEqual(before, game.to_dict())

    def test_captives_only_go_to_original_home_not_another_old_colony(self):
        game = scenario()
        second = spare_colony(game, "player")
        sid, pid, _ = target(game)
        transports(game, sid)
        game.invade(sid, pid)
        self.assertEqual(game.planet_at(0, 2).slaves, 8)
        self.assertEqual(second.slaves, 0)

    def test_ordinary_conquest_frees_slaves_and_preserves_total_workforce(self):
        game = scenario(race_id="terran", rival_race_id="varkesh")
        sid, pid, planet = target(game)
        planet.slaves = 100
        planet.farmers, planet.scientists = 50, 20
        before_workforce = planet.workforce
        transports(game, sid, 10)
        report = game.invade(sid, pid)
        self.assertEqual(report.cause, "invasion")
        self.assertEqual((planet.population, planet.slaves), (before_workforce, 0))
        self.assertEqual(planet.workforce, before_workforce)
        self.assertEqual(forces(planet).militia, 0)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_varkesh_raid_can_transfer_another_clans_slaves(self):
        game = scenario(rival_race_id="varkesh")
        home = game.planet_at(0, 2)
        home.slaves = 97
        sid, pid, planet = target(game)
        planet.slaves = 12
        transports(game, sid)
        report = game.invade(sid, pid)
        self.assertEqual((report.slaves_taken, home.slaves, planet.slaves, planet.population), (3, 100, 9, 8))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_remnant_awakening_frees_captives_when_it_takes_homeworld(self):
        game = scenario(rival_race_id="remnant")
        planet = game.planet_at(0, 2)
        planet.slaves = 50
        tomb = tomb_worlds.TombWorld(0, 2)
        game.tomb_worlds = [tomb]
        report = tomb_worlds.awaken(game, tomb)
        self.assertTrue(report.captured)
        self.assertEqual((planet.population, planet.slaves), (58, 0))
        game.check_victory()
        self.assertEqual(game, GameState.from_dict(game.to_dict()))


class SlaveEconomyTests(unittest.TestCase):
    def test_slaves_and_free_population_produce_and_consume_identically(self):
        game = scenario(with_ai=False)
        planet = game.planet_at(0, 2)
        planet.slaves = 60
        game.set_workforce(0, 2, 30, 14)
        equivalent = copy.deepcopy(planet)
        equivalent.population += equivalent.slaves
        equivalent.slaves = 0
        self.assertEqual(game.planet_yields(planet), game.planet_yields(equivalent))
        self.assertEqual(game.population_report(planet).consumed, game.population_report(equivalent).consumed)
        self.assertEqual((planet.workforce, planet.workers), (68, 24))
        summary = summarize_empire(game)
        self.assertEqual((summary.population, summary.slaves, summary.food_consumed), (68, 60, 68))
        with self.assertRaises(RuleError):
            game.set_workforce(0, 2, 60, 20)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_mortality_is_independent_5_percent_per_unit_not_a_whole_population_roll(self):
        game = scenario(with_ai=False)
        with patch("orion.raiding.random.Random") as rng:
            rng.return_value.randrange.side_effect = list(range(20))
            self.assertEqual(raiding.deaths(game, 0, 2, "player", 20), 1)
            self.assertEqual(rng.return_value.randrange.call_count, 20)
            self.assertTrue(all(call.args == (20,) for call in rng.return_value.randrange.call_args_list))

    def test_slave_deaths_happen_after_income_and_clamp_jobs_without_harming_natives(self):
        game = scenario(with_ai=False)
        planet = game.planet_at(0, 2)
        planet.slaves = 100
        game.set_workforce(0, 2, 60, 48)
        population, credits = planet.population, game.credits
        income, _ = game.empire_rates
        with patch("orion.raiding.deaths", return_value=100):
            report = game.advance_turn()
        self.assertEqual((planet.slaves, planet.population), (0, population))
        self.assertEqual(game.credits, credits+income)
        self.assertEqual((planet.farmers, planet.scientists, planet.workers), (8, 0, 0))
        self.assertTrue(any("100 slave units died" in message for message in report.population))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_mortality_and_future_outcomes_are_stable_after_save_and_load(self):
        game = scenario(with_ai=False)
        planet = game.planet_at(0, 2)
        planet.slaves = 100
        planet.farmers = farmers_needed(planet, game.bonuses_for())
        loaded = GameState.from_dict(game.to_dict())
        for _ in range(20):
            self.assertEqual(game.advance_turn(), loaded.advance_turn())
            self.assertEqual(game, loaded)
        self.assertGreater(planet.slaves, 0)
        self.assertLess(planet.slaves, 100)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_slaves_do_not_naturally_reproduce_and_do_not_count_as_militia(self):
        game = scenario(with_ai=False)
        planet = game.planet_at(0, 2)
        planet.slaves = 10
        planet.farmers = farmers_needed(planet, game.bonuses_for())
        planet.growth_progress = 99
        self.assertEqual(forces(planet).militia, 12)
        with patch("orion.raiding.deaths", return_value=0):
            game.advance_turn()
        self.assertEqual((planet.population, planet.slaves), (9, 10))

    def test_ai_new_captives_are_not_in_the_turns_starting_mortality_pool(self):
        game = scenario(race_id="terran", rival_race_id="varkesh")
        spare_colony(game, "player")
        transports(game, 0, owner="rival")
        with patch("orion.raiding.deaths", side_effect=AssertionError("No slaves existed at turn start")):
            game.advance_turn()
        self.assertEqual(raiding.homeworld(game, "rival").slaves, 8)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_construction_forecast_accounts_for_future_slave_mortality(self):
        game = scenario(with_ai=False)
        planet = game.planet_at(0, 2)
        planet.slaves = 60
        planet.farmers = 34
        planet.construction_queue = [ConstructionProject("factory"), ConstructionProject("research_lab"),
                                     ConstructionProject("frigate"), ConstructionProject("mine")]
        expected = game.queue_estimates(planet)
        actual = []
        for elapsed in range(1, 200):
            report = game.advance_turn()
            actual.extend([elapsed]*len(report.completed))
            if not planet.construction_queue:
                break
        self.assertEqual(actual, expected)

    def test_pending_combat_does_not_apply_mortality_or_advance_turn(self):
        game = scenario()
        game.planet_at(0, 2).slaves = 100
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner="rival")]
        game.next_ship_id = 3
        game.diplomacy.relations = -100
        game.advance_turn()
        self.assertEqual((game.turn, game.planet_at(0, 2).slaves), (1, 100))


class RaidNewsAndAITests(unittest.TestCase):
    def test_private_raids_do_not_reveal_unknown_worlds(self):
        game = scenario(race_id="terran", rival_race_id="varkesh", rival_count=2, fog_of_war=True)
        enemy = game.other_opponents["rival_2"]
        game.ships.clear()
        transports(game, enemy.home_system, 10, "rival")
        report = game.invade(enemy.home_system, enemy.home_planet, owner="rival")
        self.assertTrue(report.captured)
        self.assertFalse(raiding.news(game))
        self.assertNotIn("player", game.raid_events[0].observers)
        self.assertIsNone(game.known_system(enemy.home_system))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_raids_after_reading_news_in_same_turn_still_show_as_unread(self):
        game = scenario()
        spare_colony(game)
        news.mark_read(game)
        sid, pid, _ = target(game)
        transports(game, sid)
        game.invade(sid, pid)
        self.assertEqual(news.unread_count(game), 1)
        self.assertEqual(len(news.entries(game)), 1)
        news.mark_read(game)
        self.assertEqual(news.unread_count(game), 0)
        loaded = GameState.from_dict(game.to_dict())
        self.assertEqual(news.entries(game), news.entries(loaded))
        self.assertEqual(news.unread_count(loaded), 0)

    def test_ai_raids_neutral_colonies_but_respects_existing_treaties(self):
        game = scenario(race_id="terran", rival_race_id="varkesh")
        spare_colony(game, "player")
        transports(game, 0, owner="rival")
        game.diplomacy.trade_active = True
        self.assertNotIn("player", enemies(game, "rival"))
        self.assertFalse(invasion_orders(game, "rival"))
        game.diplomacy.trade_active = False
        reports = []
        self.assertTrue(invasion_orders(game, "rival", ground_reports=reports))
        self.assertEqual((reports[0].cause, reports[0].slaves_taken), ("raid", 8))
        self.assertEqual(game.planet_at(0, 2).owner, None)
        self.assertEqual(len(game.colony_systems("rival")), 1)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_ai_builds_and_dispatches_raiding_fleets_without_colony_ships(self):
        game = scenario(race_id="terran", rival_race_id="varkesh", fog_of_war=True)
        sid, pid, planet = target(game)
        place_near(game, sid, distance=9)
        record_survey(game, 0, "rival")
        planet.buildings = ["factory", "research_lab", "barracks", "fortifications"]
        game.ships = [Ship(1, "frigate", sid, owner="rival")]
        game.next_ship_id = 2
        transports(game, sid, owner="rival")
        run_ai(game, "rival")
        self.assertTrue(all(ship.destination == 0 for ship in game.ships[:3]))
        self.assertEqual(game.diplomacy.relations, -100)
        self.assertFalse(any(q.item_id == "colony_ship" for q in planet.construction_queue))

    def test_ai_clears_neutral_defenders_then_raids_without_manual_orders(self):
        game = fixed_start_game(seed=2408, race_id="terran", rival_race_id="varkesh", fog_of_war=False)
        place_near(game, game.opponent.home_system, distance=9)
        game.planet_at(0, 2).garrison = 100
        spare_colony(game, "player")
        refresh(game)
        saw_battle = False
        for _ in range(12):
            if game.combat:
                saw_battle = True
                combat.autoresolve(game)
                if game.combat:
                    game.finish_combat()
            else:
                game.advance_turn()
            self.assertEqual(game, GameState.from_dict(game.to_dict()))
            if game.raid_events:
                break
        self.assertTrue(saw_battle)
        self.assertEqual(len(game.raid_events), 1)
        raid = game.raid_events[0]
        self.assertTrue(raid.successful)
        self.assertEqual((raid.attacker, raid.defender, raid.slaves_taken), ("rival", "player", 3))

    def test_raid_history_is_bounded_without_reusing_event_ids(self):
        game = scenario()
        sid, pid, planet = target(game)
        game.planet_at(0, 2).slaves = 100
        for _ in range(103):
            transports(game, sid)
            game.invade(sid, pid)
        self.assertEqual((len(game.raid_events), game.raid_events[0].id, game.next_raid_id), (100, 4, 104))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))


class SlaveSaveTests(unittest.TestCase):
    def test_old_v22_saves_preserve_fleets_populations_and_paid_orders(self):
        from scenarios import migrated_statistics
        game = scenario()
        for owner in game.owners:
            game.research_state(owner).legacy_starships = True
            game.research_state(owner).legacy_arsenal = True
            game.research_state(owner).legacy_fuel = True
            game.research_state(owner).legacy_black_holes = True
        game.ships = [Ship(1, "colony_ship", 0)]
        game.next_ship_id = 2
        game.planet_at(0, 2).construction_queue = [ConstructionProject("colony_ship", progress=17, paid_credits=64)]
        data = game.to_dict()
        for field in ("raid_events", "next_raid_id", "raid_news_read"):
            data.pop(field)
        for system in data["systems"]:
            for planet in system["worlds"]:
                planet.pop("slaves")
        for survey in data["exploration"]["surveys"]:
            for planet in survey["worlds"]:
                planet.pop("slaves")
        loaded = GameState.from_dict(legacy_research_payload(data), version=22)
        self.assertEqual(loaded, migrated_statistics(game))
        self.assertEqual(loaded.planet_at(0, 2).construction_queue[0].progress, 17)
        self.assertFalse(loaded.raid_events)
        self.assertIn("cannot colonize", loaded.colonize_error(0, 3))

    def test_invalid_slave_counts_locations_workforce_and_raid_data_are_rejected(self):
        game = scenario()
        for value in (-1, 101, True, 2.5):
            data = game.to_dict()
            data["systems"][0]["worlds"][2]["slaves"] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        game.planet_at(0, 2).slaves = 8
        data = game.to_dict()
        data["race_id"] = "terran"
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        other = spare_colony(game, "player")
        other.slaves = 1
        with self.assertRaises(SaveError):
            GameState.from_dict(game.to_dict())
        other.slaves = 0
        sid, pid, _ = target(game)
        transports(game, sid)
        game.invade(sid, pid)
        for fields in ({"slaves_taken": 101}, {"credits_stolen": -1}, {"successful": False},
                       {"observers": []}, {"attacker": "rival"}, {"turn": 999}):
            data = game.to_dict()
            data["raid_events"][0].update(fields)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        data = game.to_dict()
        data["raid_news_read"] = data["next_raid_id"]
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_real_storage_roundtrip_includes_slaves_and_news(self):
        game = scenario()
        sid, pid, _ = target(game)
        transports(game, sid)
        game.invade(sid, pid)
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(directory)
            path = store.save(game)
            original = path.read_bytes()
            self.assertEqual(store.load(path)[0], game)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(json.loads(original)["version"], 38)


class VarkeshInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = scenario()
        self.app.window = pg.display.set_mode((990, 760), pg.RESIZABLE)
        self.app.present()

    def click(self, key, *, x=None):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        self.assertTrue(pg.Rect(0, 0, 1440, 900).contains(button.rect))
        y = button.rect.centery
        x = button.rect.centerx if x is None else x
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_preview_cancel_launch_report_news_and_saved_outcome(self):
        game = self.app.game
        spare_colony(game)
        sid, pid, _ = target(game)
        transports(game, sid)
        self.app.open_system(sid)
        self.app.open_planet(pid)
        before = game.to_dict()
        self.click("invade_planet")
        self.assertEqual(self.app.screen, "ground")
        self.click("ground_cancel")
        self.assertEqual(game.to_dict(), before)
        self.click("invade_planet")
        self.click("ground_launch")
        self.assertEqual(self.app.ground_reports[0].cause, "raid")
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], game)
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "news")
        self.app.open_empire()
        self.app.render()
        self.assertEqual(self.app.screen, "empire")
        self.app.close_empire()
        self.app.render()
        self.assertEqual(self.app.screen, "news")

    def test_home_worker_controls_allow_slave_jobs_beyond_native_population(self):
        game = self.app.game
        planet = game.planet_at(0, 2)
        planet.slaves = 100
        self.app.open_system(0)
        self.app.open_planet(2)
        self.click("worker_workers", x=852)  # Rightmost icon selects one of the large workforce.
        self.click("worker_scientists")
        self.assertEqual(planet.scientists, 1)
        game.set_workforce(0, 2, 54, 20)
        self.app.render()
        self.assertEqual(planet.workers, 34)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_colonization_and_colony_ship_controls_are_disabled(self):
        self.app.open_system(0)
        self.app.open_planet(3)
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "colonize_planet").enabled)
        self.app.open_planet(2)
        self.app.go("shipyard")
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "build_colony_ship").enabled)
