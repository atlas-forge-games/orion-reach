"""Orbital industry: real orders, shared power, war, fog, saves and screens."""
from copy import deepcopy
from dataclasses import asdict
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from orion import balance, economy, exploration, gas_giants as gas, megastructures
from orion.model import GameState, Planet, RuleError, SaveError, Ship, new_game
from orion.storage import Storage, SAVE_VERSION


def campaign(**options):
    settings = dict(seed=2408, with_ai=False, fog_of_war=False, with_guardians=False,
                    with_tombs=False, with_black_holes=False, with_encounters=False)
    settings.update(options)
    game = new_game(**settings)
    game.credits = game.resources = 2000
    return game


def ship(game, kind, sid, owner='player'):
    s = Ship(game.next_ship_id, kind, sid, owner=owner)
    game.next_ship_id += 1
    game.ships.append(s)
    return s


def giant(game):
    return next((s, p) for s in game.systems for p in s.worlds if p.is_gas_giant)


def colony(system, owner='player'):
    p = next(p for p in system.worlds if not p.is_gas_giant and not p.colonized)
    p.biome = 'Terran'
    p.colonized, p.owner, p.population = True, owner, 8
    p.farmers = 4
    return p


class OrbitalStationTests(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())

    def deploy(self, game, kind='refinery', owner='player'):
        s, p = giant(game)
        ship(game, 'outpost_ship', s.id, owner)
        gas.build(game, s.id, p.id, kind, owner)
        return s, p

    def test_remote_construction_consumes_ship_and_charges_exactly_once(self):
        game = campaign()
        s, p = giant(game)
        builder = ship(game, 'outpost_ship', s.id)
        spec = gas.specification(game, s.id, p.id, 'refinery')
        before = game.resources, game.credits, len(game.colony_systems())
        station = gas.build(game, s.id, p.id, 'refinery')
        self.assertNotIn(builder, game.ships)
        self.assertEqual((game.resources, game.credits), (before[0]-spec.resources, before[1]-spec.credits))
        self.assertEqual(station.ready_turn, game.turn+2)
        self.assertFalse(gas.operating(game, s.id, p))
        self.assertFalse(p.colonized)
        self.assertEqual(len(game.colony_systems()), before[2])
        self.assertFalse(game.can_settle(p))
        self.assertNotIn(s, game.supply_systems())
        snapshot = game.to_dict()
        with self.assertRaisesRegex(RuleError, 'one main station'):
            gas.build(game, s.id, p.id, 'research')
        self.assertEqual(game.to_dict(), snapshot)

    def test_local_colony_supplies_crews_without_consuming_a_ship(self):
        game = campaign()
        s, p = giant(game)
        colony(s)
        before = len(game.ships)
        gas.build(game, s.id, p.id, 'research')
        self.assertEqual(len(game.ships), before)

    def test_rejected_orders_do_not_spend_resources_or_consume_ships(self):
        game = campaign()
        s, p = giant(game)
        for kind in ('missing', 'energy'):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                gas.build(game, s.id, p.id, kind)
            self.assertEqual(before, game.to_dict())
        builder = ship(game, 'outpost_ship', s.id)
        game.credits = 0
        before = game.to_dict()
        with self.assertRaises(RuleError):
            gas.build(game, s.id, p.id, 'refinery')
        self.assertEqual(game.to_dict(), before)
        self.assertIn(builder, game.ships)

    def test_properties_are_stable_and_apply_tradeoffs(self):
        game = campaign()
        s, p = giant(game)
        self.assertEqual(gas.trait(game, s.id, p.id), gas.trait(deepcopy(game), s.id, p.id))
        with patch.object(gas, 'trait', return_value='storms'):
            spec = gas.specification(game, s.id, p.id, 'research')
            self.assertEqual((spec.resources, spec.credits, spec.output, spec.upkeep), (125, 50, 5, 3))
        with patch.object(gas, 'trait', return_value='calm'):
            self.assertEqual(gas.specification(game, s.id, p.id, 'energy').resources, 96)
        with patch.object(gas, 'trait', return_value='magnetic'):
            self.assertEqual(gas.specification(game, s.id, p.id, 'energy').output, 10)

    def test_two_assembly_turns_then_income_is_banked(self):
        game = campaign()
        s, p = self.deploy(game)
        spec = gas.specification(game, s.id, p.id, 'refinery')
        for _ in range(2):
            self.assertEqual(gas.income(game, 'player'), (0, 0, spec.upkeep))
            expected = game.empire_rates[0]
            before = game.credits
            report = game.advance_turn()
            self.assertEqual(game.credits-before, expected)
        self.assertTrue(gas.operating(game, s.id, p))
        self.assertEqual(gas.income(game, 'player'), (spec.output, 0, spec.upkeep))
        before, expected = game.credits, game.empire_rates[0]
        game.advance_turn()
        self.assertEqual(game.credits-before, expected)

    def test_energy_is_shared_once_locally_and_reduces_backup_fuel(self):
        game = campaign()
        s, p = giant(game)
        a, b = colony(s), colony(s)
        for world in (a, b):
            world.buildings = ['factory']*8+['thermal_plant']
        p.orbital_station = gas.OrbitalStation('energy', 'player')
        with patch.object(gas, 'trait', return_value='ordinary'):
            power = [game.planet_energy(w) for w in (a, b)]
            self.assertEqual(sum(r.orbital_generated for r in power), 8)
            self.assertEqual([r.orbital_generated for r in power], [8, 0])
            self.assertTrue(all(r.balance >= 0 for r in power))
            base_fuel = economy.energy_report(a, game._base_bonuses(), fuel_budget=2000).fuel_used
            self.assertLess(power[0].fuel_used, base_fuel)
            home = next(w for sys, w in game.settlements('player') if sys.id != s.id)
            self.assertEqual(game.planet_energy(home).orbital_generated, 0)
            a.disabled_buildings = list(range(8))
            self.assertEqual(game.planet_energy(b).orbital_generated, 8)
            game._settle_power()
            self.assertEqual(game.planet_energy(b).orbital_generated, 8)
            p.orbital_station = None
            self.assertEqual(game.planet_energy(b).orbital_generated, 8)  # frozen outgoing turn
            del game._turn_power
            self.assertEqual(game.planet_energy(b).orbital_generated, 0)

    def test_megastructure_dispatch_includes_orbital_power_without_duplication(self):
        game = campaign()
        s, p = giant(game)
        a, b = colony(s), colony(s)
        a.buildings = b.buildings = ['factory']*8
        p.orbital_station = gas.OrbitalStation('energy', 'player')
        spec = megastructures.MEGASTRUCTURES['stellar_forge']
        s.megastructure = megastructures.Megastructure('stellar_forge', 'player', 'player', hull=spec.hull)
        plan = megastructures.make_plan(game, 'player')
        self.assertEqual(sum(plan.power[id(w)].orbital_generated for w in (a, b)), gas.specification(game, s.id, p.id, 'energy').output)
        self.assertEqual(game.planet_energy(a), plan.power[id(a)])

    def test_peaceful_ships_do_not_blockade_but_warships_at_war_do(self):
        game = campaign(with_ai=True)
        s, p = self.deploy(game)
        p.orbital_station.ready_turn = 0
        enemy = ship(game, 'frigate', s.id, 'rival')
        relation = game.diplomacy_between('player', 'rival')
        relation.relations = 0
        self.assertTrue(gas.operating(game, s.id, p))
        from orion.diplomacy import start_war
        start_war(game, 'rival', 'player')
        self.assertFalse(gas.operating(game, s.id, p))
        self.assertEqual(gas.income(game, 'player')[:2], (0, 0))
        self.assertGreater(gas.income(game, 'player')[2], 0)
        game.ships.remove(enemy)
        ship(game, 'outpost_ship', s.id, 'rival')
        self.assertTrue(gas.operating(game, s.id, p))

    def test_capture_requires_damage_transport_and_honors_treaties(self):
        game = campaign(with_ai=True)
        s, p = giant(game)
        p.orbital_station = gas.OrbitalStation('research', 'rival')
        escort = ship(game, 'frigate', s.id)
        transport = ship(game, 'troop_transport', s.id)
        self.assertIn('30 hull', gas.attack_error(game, s.id, p.id, capture=True))
        p.orbital_station.hull = 30
        relation = game.diplomacy_between('player', 'rival')
        relation.non_aggression_active = True
        self.assertIn('pact', gas.attack_error(game, s.id, p.id, capture=True))
        relation.non_aggression_active = False
        gas.attack(game, s.id, p.id, capture=True)
        self.assertEqual(p.orbital_station.owner, 'player')
        self.assertNotIn(transport, game.ships)
        self.assertEqual(escort.bombarded_turn, game.turn)
        self.assertTrue(relation.at_war)
        self.assertFalse(gas.operating(game, s.id, p))
        self.assertIsNotNone(gas.attack_error(game, s.id, p.id, capture=True))

    def test_bombardment_can_destroy_and_dismantling_has_no_refund(self):
        game = campaign(with_ai=True)
        s, p = giant(game)
        p.orbital_station = gas.OrbitalStation('refinery', 'rival', hull=1)
        ship(game, 'frigate', s.id)
        self.assertIn('destroyed', gas.attack(game, s.id, p.id))
        self.assertIsNone(p.orbital_station)
        p.orbital_station = gas.OrbitalStation('refinery', 'player')
        banks = game.resources, game.credits
        gas.dismantle(game, s.id, p.id)
        self.assertEqual((game.resources, game.credits), banks)
        self.assertIsNone(p.orbital_station)

    def test_station_observes_system_and_old_surveys_do_not_reveal_changes(self):
        game = campaign(with_ai=True, fog_of_war=True)
        s, p = self.deploy(game)
        self.assertTrue(game.system_visible(s.id))
        self.assertNotIn(s, game.supply_systems())
        exploration.record_survey(game, s.id, 'rival')
        p.orbital_station.kind = 'research'
        self.assertFalse(game.system_visible(s.id, 'rival'))
        self.assertEqual(game.known_system(s.id, 'rival').worlds[p.id].orbital_station.kind, 'refinery')
        saved = game.to_dict()
        loaded = GameState.from_dict(saved)
        self.assertEqual(loaded.to_dict(), saved)

    def test_saves_load_old_campaigns_without_adding_worlds_and_reject_bad_stations(self):
        game = campaign()
        s, p = self.deploy(game)
        with tempfile.TemporaryDirectory() as root:
            storage = Storage(root)
            loaded, metadata = storage.load(storage.save(game))
        self.assertEqual(metadata['version'], SAVE_VERSION)
        self.assertEqual(loaded.to_dict(), game.to_dict())
        old = game.to_dict()
        for sys in old['systems']:
            for world in sys['worlds']:
                world.pop('orbital_station', None)
        legacy = GameState.from_dict(old, version=56)
        self.assertEqual([len(s.worlds) for s in legacy.systems], [len(s.worlds) for s in game.systems])
        self.assertFalse(gas.installations(legacy))
        for changes in ({'hull': -1}, {'hull': True}, {'kind': 'unknown'}, {'owner': 'unknown'},
                        {'ready_turn': game.turn+3}, {'last_attacked': game.turn+1}):
            payload = game.to_dict()
            payload['systems'][s.id]['worlds'][p.id]['orbital_station'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                GameState.from_dict(payload)
        payload = game.to_dict()
        payload['systems'][s.id]['worlds'][0]['orbital_station'] = asdict(p.orbital_station)
        with self.assertRaises(SaveError):
            GameState.from_dict(payload)

    def test_ai_commissions_affordable_station_and_defeated_empire_loses_it(self):
        game = campaign(with_ai=True)
        s, p = giant(game)
        colony(s, 'rival')
        game.opponent.credits = game.opponent.resources = 500
        gas.ai_orders(game, 'rival')
        self.assertEqual(p.orbital_station.owner, 'rival')
        for _, world in game.settlements('rival'):
            world.colonized, world.owner, world.population = False, None, 0
        game.eliminate_defeated()
        self.assertIsNone(p.orbital_station)

    def test_ai_preserves_remote_outpost_ship_for_fuel_expansion(self):
        game = campaign(with_ai=True)
        system, planet = giant(game)
        builder = ship(game, 'outpost_ship', system.id, 'rival')
        game.opponent.resources = game.opponent.credits = 1000
        gas.ai_orders(game, 'rival')
        self.assertIn(builder, game.ships)
        self.assertIsNone(planet.orbital_station)

    def test_research_and_station_upkeep_match_empire_budget_and_real_turn(self):
        from orion.empire import summarize_empire
        game = campaign()
        system, planet = self.deploy(game, 'research')
        planet.orbital_station.ready_turn = 0
        spec = gas.specification(game, system.id, planet.id, 'research')
        before = game.research
        expected = game.empire_rates[1]
        self.assertGreaterEqual(expected, spec.output)
        summary = summarize_empire(game)
        self.assertEqual(summary.gross_income-summary.maintenance, summary.income)
        game.advance_turn()
        self.assertEqual(game.research-before, expected)

    def test_blockade_removes_energy_immediately_and_dismantle_updates_final_survey(self):
        from orion.diplomacy import start_war
        game = campaign(with_ai=True, fog_of_war=True)
        system, planet = self.deploy(game, 'energy')
        local = colony(system)
        local.buildings = ['factory']*8+['thermal_plant']
        planet.orbital_station.ready_turn = 0
        power = game.planet_energy(local)
        self.assertGreater(power.orbital_generated, 0)
        enemy = ship(game, 'frigate', system.id, 'rival')
        start_war(game, 'rival', 'player')
        blocked = game.planet_energy(local)
        self.assertEqual(blocked.orbital_generated, 0)
        self.assertGreater(blocked.fuel_used, power.fuel_used)
        game.ships.remove(enemy)
        local.owner, local.colonized, local.population = None, False, 0
        local.farmers = 0
        local.buildings = []
        gas.dismantle(game, system.id, planet.id)
        self.assertFalse(game.system_visible(system.id))
        self.assertIsNone(game.known_system(system.id).worlds[planet.id].orbital_station)

    def test_anchored_mothership_receives_power_but_travelling_home_does_not(self):
        game = campaign(race_id='wanderers')
        system, planet = giant(game)
        home = next(s for s in game.ships if s.habitat)
        home.system_id = system.id
        home.habitat.buildings = ['factory']*8
        planet.orbital_station = gas.OrbitalStation('energy', 'player')
        self.assertGreater(game.planet_energy(home.habitat).orbital_generated, 0)
        home.destination = next(s.id for s in game.systems if s.id != system.id)
        home.turns_remaining = home.travel_total = 2
        self.assertEqual(game.planet_energy(home.habitat).orbital_generated, 0)

    def test_forecast_includes_station_assembly_without_mutating_campaign(self):
        game = campaign()
        system, planet = giant(game)
        local = colony(system)
        local.buildings = ['factory']*7
        gas.build(game, system.id, planet.id, 'energy')
        game.queue_ship(system.id, local.id, 'colony_ship')
        # A long ship project makes the powered factories matter.
        local.construction_queue[0].progress = 0
        before = game.to_dict()
        estimate = game.queue_estimates(local)[0]
        self.assertEqual(game.to_dict(), before)
        turns = 0
        while local.construction_queue and turns < 20:
            game.advance_turn()
            turns += 1
        self.assertEqual(estimate, turns)
        self.assertFalse(local.construction_queue)

    def test_actual_screen_shows_choices_executes_confirmation_and_disables_stale_orders(self):
        import pygame as pg
        from orion.app import App
        from orion.gas_giant_view import request
        with tempfile.TemporaryDirectory() as root:
            app = App(Path(root), capture=True)
            self.addCleanup(pg.quit)
            self.addCleanup(app.audio.close)
            app.game = game = campaign(fog_of_war=True)
            s, p = giant(game)
            ship(game, 'outpost_ship', s.id)
            game.selected_system = s.id
            app.open_planet(p.id)
            app.render()
            buttons = {b.key:b for b in app.buttons}
            self.assertTrue(all(buttons['orbital_build_'+kind].enabled for kind in gas.STATIONS))
            self.assertFalse(buttons['colonize_planet'].enabled)
            with patch.object(app, 'confirm', side_effect=lambda title, body, label, action: action()):
                request(app, s.id, p.id, 'build', 'energy')
            app.render()
            self.assertIn('orbital_dismantle', {b.key for b in app.buttons})
            self.assertEqual(p.orbital_station.kind, 'energy')
            p.orbital_station = None
            app.render()
            self.assertFalse(any(b.enabled for b in app.buttons if b.key.startswith('orbital_build_')))


if __name__ == '__main__':
    unittest.main()
