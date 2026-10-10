"""Research, planetary siege, navigation, sensor privacy and weapon accuracy."""

import copy
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from orion import ai, combat, defenses, navigation, news, sensors
from orion.designs import ShipDesign
from orion.exploration import refresh
from orion.ground_combat import forces
from orion.model import GameState, RuleError, SaveError, Ship
from orion.research import TECHNOLOGIES, choices
from orion.storage import Storage
from scenarios import empty_fleet_game, place_near


def game_at_start(**kwargs):
    return empty_fleet_game(seed=2408, **kwargs)


def discover(game, identifier, owner="player"):
    state, tech = game.research_state(owner), TECHNOLOGIES[identifier]
    if identifier in state.completed:
        return
    if state.active:
        raise AssertionError("Fixture already researching")
    if tech.tier > 1 and tech.branch != "ascension" and not any(
            TECHNOLOGIES[t].branch == tech.branch and TECHNOLOGIES[t].tier <= 2 for t in state.completed):
        discover(game, choices(tech.branch, 1)[0].id, owner)
    for prerequisite in tech.requires:
        discover(game, prerequisite, owner)
    game._empire(owner).research += tech.cost
    game.choose_research(identifier, owner=owner)


def add_ship(game, kind="frigate", sid=0, owner="player", design=None):
    ship = Ship(game.next_ship_id, kind, sid, owner=owner, design=design)
    game.next_ship_id += 1
    game.ships.append(ship)
    return ship


def install(game, planet, building):
    planet.buildings.append(building)
    defenses.commissioned(game, planet, building)


def foreign_colony(game):
    return game.headquarters("rival")


class ExpansionResearchTests(unittest.TestCase):
    def test_projects_require_foundations_and_chained_prerequisites(self):
        game = game_at_start()
        projects = [t for t in TECHNOLOGIES.values() if not t.exclusive]
        self.assertEqual(len(projects), 19)
        for technology in projects:
            self.assertEqual(game.technology.status(technology.id), "locked")
        discover(game, "deep_space_radar")
        self.assertEqual(game.technology.status("long_range_sensors"), "available")
        self.assertEqual(game.technology.status("subspace_scanners"), "locked")
        discover(game, "quantum_targeting")
        self.assertEqual(game.bonuses_for()["accuracy"], 30)
        self.assertEqual(game.technology.status("long_range_sensors"), "available")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_every_project_can_be_researched_in_one_campaign(self):
        game = game_at_start()
        for technology in TECHNOLOGIES.values():
            if not technology.exclusive:
                discover(game, technology.id)
        self.assertEqual(sum(not TECHNOLOGIES[t].exclusive for t in game.technology.completed), 19)
        self.assertEqual(game.bonuses_for()["sensor_range"], 20)
        self.assertEqual(game.bonuses_for()["shield_capacity"], 200)
        self.assertEqual(game.bonuses_for()["interdiction_slow"], 40)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_locked_infrastructure_cannot_spend_credits_or_reserve_slots(self):
        game = game_at_start()
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "Requires"):
            game.queue_building(0, 2, "planetary_shield")
        self.assertEqual(before, game.to_dict())
        discover(game, "planetary_shielding")
        game.credits = 1000
        game.queue_building(0, 2, "planetary_shield")
        game.buy_construction(0, 2)
        self.assertEqual(game.planet_at(0, 2).shield_points, 100)
        self.assertIsNotNone(game.build_error(0, 2, "planetary_shield"))

    def test_upgraded_generators_charge_their_actual_maintenance(self):
        game = game_at_start()
        planet = game.planet_at(0, 2)
        install(game, planet, "planetary_shield")
        install(game, planet, "interdictor")
        self.assertEqual(game.planet_maintenance(planet), 7)
        before = game.planet_yields(planet)[1]
        discover(game, "barrier_fields")
        discover(game, "subspace_interdiction")
        self.assertEqual(game.planet_maintenance(planet), 11)
        self.assertEqual(game.planet_yields(planet)[1], before-4)

    def test_fortifications_improve_actual_defender_firepower(self):
        game = game_at_start()
        planet = game.planet_at(0, 2)
        planet.buildings = ["fortifications"]
        old = forces(planet, game.bonuses_for())
        discover(game, "advanced_fortifications")
        new = forces(planet, game.bonuses_for())
        self.assertEqual((old.defence_bonus, new.defence_bonus), (50, 75))
        self.assertGreater(new.strength, old.strength)

    def test_ai_researches_new_projects_after_establishing_foundations(self):
        game = game_at_start()
        for branch in ("computers", "fields", "construction", "physics"):
            discover(game, choices(branch, 1)[0].id, "rival")
        game.headquarters("rival")[1].buildings = ["trade_center", "trade_center"]
        game.fog_of_war = False
        game.opponent.research = 1
        ai.research_choice(game)
        self.assertEqual(game.opponent.technology.active, "deep_space_radar")


class SiegeTests(unittest.TestCase):
    def setUp(self):
        self.game = game_at_start()
        self.system, self.planet = foreign_colony(self.game)
        self.ship = add_ship(self.game, sid=self.system.id)
        for _ in range(4):
            add_ship(self.game, "troop_transport", self.system.id)
        refresh(self.game)

    def test_shields_block_both_invasion_and_varkesh_raids(self):
        install(self.game, self.planet, "planetary_shield")
        self.assertIn("shield", self.game.invasion_error(self.system.id, self.planet.id).lower())
        self.game.race_id = "varkesh"
        self.assertIn("shield", self.game.invasion_error(self.system.id, self.planet.id).lower())

    def test_bombardment_applies_shields_before_troops_once_per_ship(self):
        install(self.game, self.planet, "planetary_shield")
        self.planet.shield_points = 3
        population, troops = self.planet.population, forces(self.planet).troops
        result = self.game.bombard(self.system.id, self.planet.id)
        self.assertEqual((result.shield_damage, result.troop_losses), (3, 0))
        self.assertEqual((self.planet.population, forces(self.planet).troops), (population, troops))
        self.assertIsNotNone(self.game.bombardment_error(self.system.id, self.planet.id))
        self.assertEqual(self.game.diplomacy.relations, -100)
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)

    def test_siege_research_improves_standard_bombardment_and_custom_cannons(self):
        self.assertEqual(defenses.bombardment_power(self.game, self.system.id), 5)
        discover(self.game, "siege_weapons")
        self.assertEqual(defenses.bombardment_power(self.game, self.system.id), 10)
        cannon = ShipDesign("design_1", "Siege frigate", "frigate", ("siege",))
        add_ship(self.game, sid=self.system.id, design=cannon)
        self.assertEqual(defenses.bombardment_power(self.game, self.system.id), 34)

    def test_siege_bonus_does_not_triple_damage_to_unshielded_troops(self):
        self.game.ships.remove(self.ship)
        cannon = ShipDesign("design_1", "Siege frigate", "frigate", ("siege",))
        add_ship(self.game, sid=self.system.id, design=cannon)
        self.assertEqual(defenses.bombardment_forecast(self.game, self.system.id, self.planet.id), (0, 1))
        install(self.game, self.planet, "planetary_shield")
        self.planet.shield_points = 6
        self.assertEqual(defenses.bombardment_forecast(self.game, self.system.id, self.planet.id), (6, 1))
        report = self.game.bombard(self.system.id, self.planet.id)
        self.assertEqual((report.shield_damage, report.troop_losses), (6, 1))

    def test_bombardment_removes_military_without_killing_civilians(self):
        self.planet.garrison = 3
        population = self.planet.population
        report = self.game.bombard(self.system.id, self.planet.id)
        self.assertEqual(report.troop_losses, 1)
        self.assertEqual(self.planet.population, population)
        self.assertEqual(forces(self.planet).troops, forces(self.planet).militia+2)

    def test_missile_base_is_a_real_immobile_unit_and_blocks_landings(self):
        install(self.game, self.planet, "missile_base")
        self.assertIn("base", self.game.invasion_error(self.system.id, self.planet.id).lower())
        self.assertIsNotNone(self.game.bombardment_error(self.system.id, self.planet.id))
        self.game.start_combat(self.system.id)
        base = next(s for s in self.game.combat.ships if s.kind == "missile_base")
        self.assertEqual((base.max_hull, base.damage, base.weapon_range, base.movement), (40, 10, 8, 0))
        self.assertFalse(self.game.combat.can_move(base))
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)

    def test_destroyed_battery_is_removed_from_colony_and_roundtrips(self):
        install(self.game, self.planet, "missile_base")
        self.game.start_combat(self.system.id)
        base = next(s for s in self.game.combat.ships if s.kind == "missile_base")
        base.hull = 0
        combat.check_losses(self.game)
        self.assertNotIn("missile_base", self.planet.buildings)
        self.assertEqual(self.planet.battery_hull, 0)
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)

    def test_save_cannot_omit_a_colonys_base_from_its_battle(self):
        install(self.game, self.planet, "missile_base")
        add_ship(self.game, sid=self.system.id, owner="rival")
        self.game.start_combat(self.system.id)
        data = self.game.to_dict()
        data["combat"]["ships"] = [s for s in data["combat"]["ships"] if s["kind"] != "missile_base"]
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_regeneration_stops_under_hostile_blockade_and_resumes_in_peace(self):
        install(self.game, self.planet, "planetary_shield")
        self.planet.shield_points = 40
        self.game.diplomacy.relations = -100
        self.game.turn = 2
        defenses.advance(self.game)
        self.assertEqual(self.planet.shield_points, 40)
        self.game.ships.clear()
        defenses.advance(self.game)
        self.assertEqual(self.planet.shield_points, 65)
        self.planet.bombarded_turn = 2
        self.game.turn = 3
        defenses.advance(self.game)
        self.assertEqual(self.planet.shield_points, 65)
        self.game.turn = 4
        defenses.advance(self.game)
        self.assertEqual(self.planet.shield_points, 90)

    def test_allied_ships_do_not_block_peaceful_regeneration(self):
        install(self.game, self.planet, "planetary_shield")
        self.planet.shield_points = 0
        self.game.diplomacy.trade_active = True
        self.game.turn = 2
        defenses.advance(self.game)
        self.assertEqual(self.planet.shield_points, 25)

    def test_raided_abandoned_world_drops_all_defense_state(self):
        from orion.raiding import abandon
        install(self.game, self.planet, "planetary_shield")
        install(self.game, self.planet, "missile_base")
        abandon(self.planet)
        self.assertEqual((self.planet.shield_points, self.planet.battery_hull, self.planet.bombarded_turn), (0, 0, 0))


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.game = game_at_start()
        self.origin = self.game.systems[0]
        self.target, self.planet = foreign_colony(self.game)
        place_near(self.game, self.target.id, distance=6)

    def test_navigation_only_accelerates_routes_between_own_colonies(self):
        discover(self.game, "colonial_navigation")
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player")[0], 0)
        self.planet.owner = "player"
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player")[0], 25)
        expected = navigation.duration(self.origin, self.target, route_bonus=25)
        self.assertEqual(self.game.travel_turns(self.origin, self.target), expected)

    def test_two_jump_gates_replace_the_navigation_bonus(self):
        discover(self.game, "jump_gates")
        self.planet.owner = "player"
        install(self.game, self.game.planet_at(0, 2), "jump_gate")
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player")[0], 25)
        install(self.game, self.planet, "jump_gate")
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player")[0], 50)

    def test_interdiction_uses_strongest_field_and_stabilization_halves_it(self):
        install(self.game, self.planet, "interdictor")
        self.game.diplomacy.relations = -100
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player"), (0, 5, 25))
        discover(self.game, "subspace_interdiction", "rival")
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player"), (0, sensors.distance(self.target.x, self.target.y, self.origin), 40))
        discover(self.game, "field_stabilization")
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player"), (0, sensors.distance(self.target.x, self.target.y, self.origin), 20))
        self.game.diplomacy.trade_active = True
        self.assertEqual(navigation.route_modifiers(self.game, self.origin, self.target, "player"), (0, 0, 0))

    def test_existing_voyages_keep_snapshot_after_technology_and_ownership_changes(self):
        install(self.game, self.planet, "interdictor")
        self.game.diplomacy.relations = -100
        ship = add_ship(self.game)
        self.game.send_ship(ship.id, self.target.id)
        total, modifiers = ship.travel_total, (ship.route_bonus, ship.approach_range, ship.approach_slow)
        discover(self.game, "field_stabilization")
        self.planet.buildings.clear()
        self.planet.owner = "player"
        self.game.check_victory()
        refresh(self.game)
        self.assertEqual(ship.travel_total, total)
        self.assertEqual((ship.route_bonus, ship.approach_range, ship.approach_slow), modifiers)
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)

    def test_interdicted_position_uses_slower_final_segment(self):
        ship = add_ship(self.game)
        ship.destination = self.target.id
        ship.travel_total, ship.turns_remaining = 10, 5
        ship.approach_range, ship.approach_slow = 2, 40
        x, y = navigation.position(self.game, ship)
        travelled = sensors.distance(x, y, self.origin)
        self.assertGreater(travelled, 3)
        ship.turns_remaining = 1
        self.assertLess(sensors.distance(*navigation.position(self.game, ship), self.target), 1)

    def test_invalid_navigation_modifiers_are_rejected_on_load(self):
        ship = add_ship(self.game)
        self.game.send_ship(ship.id, self.target.id)
        for field, value in (("route_bonus", 75), ("approach_slow", 99), ("approach_range", float("nan"))):
            data = self.game.to_dict()
            data["ships"][0][field] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class SensorTests(unittest.TestCase):
    def setUp(self):
        self.game = game_at_start()
        self.remote = next(s for s in self.game.systems[1:] if s.id != self.game.opponent.home_system)
        place_near(self.game, self.remote.id, distance=4)
        self.ship = add_ship(self.game, sid=self.remote.id, owner="rival")
        self.game.diplomacy.relations = -100

    def test_radar_reveals_position_owner_without_survey_or_manifest(self):
        self.assertFalse(self.game.system_explored(self.remote.id))
        self.assertFalse(sensors.contacts(self.game))
        discover(self.game, "deep_space_radar")
        contact, = sensors.contacts(self.game)
        self.assertEqual((contact.owner, contact.x, contact.y), ("rival", self.remote.x, self.remote.y))
        self.assertIsNone(contact.count)
        self.assertEqual(contact.classes, [])
        self.assertIsNone(contact.heading)
        self.assertNotIn(self.ship, self.game.visible_ships())
        self.assertFalse(self.game.system_explored(self.remote.id))
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)

    def test_higher_sensors_reveal_count_then_classes_and_heading_only(self):
        add_ship(self.game, "scout", self.remote.id, "rival")
        discover(self.game, "long_range_sensors")
        contact, = sensors.contacts(self.game)
        self.assertEqual((contact.count, contact.classes), (2, []))
        discover(self.game, "subspace_scanners")
        contact, = sensors.contacts(self.game)
        self.assertEqual(contact.classes, ["Frigate × 1", "Scout × 1"])
        self.assertNotIn("destination", contact.__dict__)
        self.ship.destination, self.ship.travel_total, self.ship.turns_remaining = 0, 4, 2
        live = next(c for c in sensors.contacts(self.game) if c.anchor == self.ship.id)
        self.assertIsNotNone(live.heading)
        self.assertLess(sensors.distance(live.x, live.y, self.game.systems[0]), 4)

    def test_arrays_extend_each_colonys_radius_without_stacking(self):
        discover(self.game, "deep_space_radar")
        home = self.game.planet_at(0, 2)
        self.assertEqual(sensors.centers(self.game)[0][1], 5)
        install(self.game, home, "sensor_array")
        other = self.game.planet_at(0, 3)
        other.owner, other.colonized, other.population = "player", True, 2
        install(self.game, other, "sensor_array")
        self.assertEqual([(s.id, radius) for s, radius in sensors.centers(self.game)], [(0, 10)])

    def test_departed_contact_retains_dated_position_then_expires(self):
        discover(self.game, "deep_space_radar")
        original, = sensors.contacts(self.game)
        self.ship.system_id = self.game.opponent.home_system
        self.game.turn += 1
        self.game.year += 1
        refresh(self.game)
        stale, = sensors.contacts(self.game)
        self.assertFalse(stale.active)
        self.assertEqual((stale.x, stale.y, stale.seen_turn), (original.x, original.y, 1))
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)
        self.game.turn += 21
        refresh(self.game)
        self.assertFalse(sensors.contacts(self.game))

    def test_hostile_contact_news_is_saved_once_and_can_be_marked_read(self):
        discover(self.game, "deep_space_radar")
        self.assertEqual(len(self.game.sensor_reports), 1)
        self.assertEqual(news.unread_count(self.game), 1)
        refresh(self.game)
        self.assertEqual(len(self.game.sensor_reports), 1)
        report, = news.entries(self.game)
        self.assertIsNone(report.planet_id)
        self.assertIn("unknown", report.detail.lower())
        news.mark_read(self.game)
        self.assertEqual(news.unread_count(self.game), 0)
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)

    def test_ai_has_its_own_coverage_and_redacted_observations(self):
        self.game.ships.clear()
        place_near(self.game, self.remote.id, anchor=self.game.opponent.home_system, distance=4)
        add_ship(self.game, sid=self.remote.id)
        discover(self.game, "deep_space_radar", "rival")
        contact, = sensors.contacts(self.game, "rival")
        self.assertEqual((contact.observer, contact.owner, contact.count), ("rival", "player", None))
        self.assertFalse(self.game.system_explored(self.remote.id, "rival"))

    def test_sensor_save_rejects_lower_level_private_information(self):
        discover(self.game, "deep_space_radar")
        data = self.game.to_dict()
        data["sensor_contacts"][0]["heading"] = 50
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class ExpansionAITests(unittest.TestCase):
    def test_defeat_mid_turn_keeps_earlier_ai_reports_saveable(self):
        game = game_at_start(rival_count=2)
        planet = game.planet_at(0, 2)
        install(game, planet, "planetary_shield")
        planet.shield_points = 5
        game.other_opponents["rival_2"].race_id = "terran"
        game.diplomacy_between("player", "rival_2").relations = -100
        add_ship(game, sid=0, owner="rival_2")
        for _ in range(4):
            add_ship(game, "troop_transport", 0, "rival_2")
        refresh(game)
        game.advance_turn()
        self.assertIsNotNone(game.result)
        self.assertEqual(game.turn, 1)
        self.assertTrue(any("Queued a scout" in event.message for event in game.opponent.events))
        self.assertTrue(all(event.turn <= game.turn for empire in game.opponents.values() for event in empire.events))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_suppresses_shield_before_landing_troops(self):
        game = game_at_start()
        planet = game.planet_at(0, 2)
        install(game, planet, "planetary_shield")
        planet.shield_points = 5
        game.diplomacy.relations = -100
        add_ship(game, sid=0, owner="rival")
        for _ in range(4):
            add_ship(game, "troop_transport", 0, "rival")
        refresh(game)
        reports = []
        messages = ai.invasion_orders(game, ground_reports=reports)
        self.assertTrue(any("Bombardment" in message for message in messages))
        self.assertEqual((planet.shield_points, planet.owner), (0, "rival"))
        self.assertTrue(reports[0].captured)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_moves_defenders_to_a_colony_with_a_sensor_threat(self):
        game = game_at_start()
        home, _ = game.headquarters("rival")
        secondary, remote = [s for s in game.systems[1:] if s.id != home.id and s.worlds][:2]
        place_near(game, secondary.id, anchor=home.id, distance=6)
        place_near(game, remote.id, anchor=home.id, distance=7)
        planet = secondary.worlds[0]
        planet.owner, planet.colonized, planet.population = "rival", True, 2
        defender = add_ship(game, sid=home.id, owner="rival")
        add_ship(game, sid=remote.id)
        game.diplomacy.relations = -100
        discover(game, "deep_space_radar", "rival")
        self.assertFalse(game.system_visible(remote.id, "rival"))
        self.assertEqual(sensors.contacts(game, "rival")[0].near_system, secondary.id)
        ai.military_orders(game)
        self.assertEqual(defender.destination, secondary.id)
        self.assertTrue(defender.departure_pending)


class AccuracyTests(unittest.TestCase):
    def battle(self, design=None):
        game = game_at_start(fog_of_war=False)
        own = add_ship(game, design=design)
        enemy = add_ship(game, owner="rival")
        game.start_combat(0)
        first, second = game.combat.ship(own.id), game.combat.ship(enemy.id)
        first.x, first.y, second.x, second.y = 7, 4, 10, 4
        return game, first, second

    def test_targeting_range_evasion_and_specialized_guidance(self):
        game, first, second = self.battle()
        base = combat.accuracy_breakdown(game, first, second, "laser")
        self.assertEqual(base, {"base": 85, "targeting": 0, "range": 3, "evasion": 10, "chance": 72})
        game.combat = None
        discover(game, "quantum_targeting")
        discover(game, "electronic_countermeasures", "rival")
        discover(game, "precision_beam_optics")
        discover(game, "torpedo_guidance")
        self.assertEqual(combat.accuracy_breakdown(game, first, second, "laser")["chance"], 94)
        torpedo = combat.accuracy_breakdown(game, first, second, "torpedo")
        self.assertEqual((torpedo["evasion"], torpedo["chance"]), (10, 92))
        second.x = 8
        self.assertEqual(combat.accuracy_breakdown(game, first, second, "laser")["chance"], 95)

    def test_hits_and_misses_are_real_and_reload_cannot_reroll(self):
        outcomes = set()
        for seed in range(25):
            game, first, second = self.battle()
            game.seed = seed
            resumed = GameState.from_dict(game.to_dict())
            damage = game.combat_fire(first.id, second.id)
            self.assertEqual(resumed.combat_fire(first.id, second.id), damage)
            self.assertEqual(resumed, game)
            outcomes.add(damage)
            self.assertEqual(game.combat.shots_fired, 1)
        self.assertEqual(outcomes, {0, 5})

    def test_each_weapon_rolls_separately_and_misses_do_not_consume_shields(self):
        design = ShipDesign("design_1", "Twin lasers", "frigate", ("laser", "laser"))
        game, first, second = self.battle(design)
        with patch("orion.combat.accuracy_breakdown", return_value={"chance": 0}):
            self.assertEqual(game.combat_fire(first.id, second.id), 0)
        self.assertEqual(second.hull, second.max_hull)
        self.assertEqual(game.combat.shots_fired, 2)
        self.assertIn("0/2 hits", game.combat.log[-1])

    def test_siege_weapon_does_triple_damage_to_missile_bases(self):
        game = game_at_start()
        system, planet = foreign_colony(game)
        install(game, planet, "missile_base")
        design = ShipDesign("design_1", "Siege frigate", "frigate", ("siege",))
        ship = add_ship(game, sid=system.id, design=design)
        game.start_combat(system.id)
        first = game.combat.ship(ship.id)
        base = next(s for s in game.combat.ships if s.kind == "missile_base")
        first.x, first.y = base.x-1, base.y
        with patch("orion.combat.accuracy_breakdown", return_value={"chance": 100}):
            self.assertEqual(game.combat_fire(first.id, base.id), 24)

    def test_schema_24_battles_keep_guaranteed_hit_rules(self):
        game, first, second = self.battle()
        data = game.to_dict()
        data["combat"].pop("accuracy")
        data["combat"].pop("shots_fired")
        restored = GameState.from_dict(data, version=24)
        self.assertFalse(restored.combat.accuracy)
        self.assertEqual(restored.combat_fire(first.id, second.id), 5)
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_negative_shot_sequence_rejected(self):
        game, _, _ = self.battle()
        data = game.to_dict()
        data["combat"]["shots_fired"] = -1
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class ExpansionInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(data_dir=self.folder.name, capture=True)
        self.app.game = game_at_start()
        self.app.game.selected_planet = 2

    def tearDown(self):
        import pygame as pg
        pg.quit()
        self.folder.cleanup()

    def render(self, screen):
        self.app.go(screen)
        self.app.render()
        self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in self.app.buttons))
        return {b.key: b for b in self.app.buttons}

    def test_projects_are_paginated_reachable_and_active_project_opens_correct_page(self):
        app = self.app
        app.research_branch, app.research_mode = "computers", "projects"
        buttons = self.render("research")
        self.assertIn("research_choose_deep_space_radar", buttons)
        self.assertTrue(buttons["research_project_next"].enabled)
        app.change_research_page(1)
        self.render("research")
        discover(app.game, "predictive_fire_control")
        app.game.choose_research("quantum_targeting")
        app.go("galaxy")
        app.open_research()
        app.render()
        self.assertEqual(app.research_mode, "projects")
        self.assertIn("research_choose_quantum_targeting", {b.key for b in app.buttons})

    def test_new_buildings_are_accessible_in_colony_and_surface(self):
        app, planet = self.app, self.app.game.planet_at(0, 2)
        app.colony_build_page = 1
        buttons = self.render("colony")
        for identifier in ("missile_base", "planetary_shield", "sensor_array", "jump_gate", "interdictor"):
            self.assertIn("build_"+identifier, buttons)
            install(app.game, planet, identifier)
        buttons = self.render("planet")
        self.assertTrue(all("surface_"+b in buttons for b in planet.buildings))

    def test_sensor_contact_opens_redacted_sidebar_and_closes(self):
        app, game = self.app, self.app.game
        remote = next(s for s in game.systems[1:] if s.id != game.opponent.home_system)
        place_near(game, remote.id, distance=4)
        ship = add_ship(game, sid=remote.id, owner="rival")
        discover(game, "deep_space_radar")
        buttons = self.render("galaxy")
        self.assertIn(f"sensor_contact_{ship.id}", buttons)
        app.open_sensor_contact(ship.id)
        buttons = self.render("galaxy")
        self.assertIn("sensor_close", buttons)
        self.assertNotIn("open_system", buttons)
        app.close_sensor_contact()
        self.assertIn("open_system", self.render("galaxy"))

    def test_base_only_enemy_can_be_engaged_from_galaxy_and_system(self):
        app, game = self.app, self.app.game
        system, planet = foreign_colony(game)
        add_ship(game, sid=system.id)
        install(game, planet, "missile_base")
        refresh(game)
        game.selected_system, game.selected_planet = system.id, planet.id
        self.assertTrue(self.render("galaxy")["galaxy_engage"].enabled)
        self.assertTrue(self.render("system")["system_engage"].enabled)

    def test_selecting_a_combat_target_previews_chance_without_firing(self):
        app, game = self.app, self.app.game
        first = add_ship(game)
        second = add_ship(game, owner="rival")
        game.start_combat(0)
        game.combat.ship(first.id).x = 7
        game.combat.ship(second.id).x = 10
        app.reset_combat_view()
        app.combat_ship_id = first.id
        app.select_combat_ship("rival", second.id)
        buttons = self.render("combat")
        self.assertEqual(game.combat.shots_fired, 0)
        self.assertTrue(buttons["combat_fire"].enabled)


if __name__ == "__main__":
    unittest.main()
