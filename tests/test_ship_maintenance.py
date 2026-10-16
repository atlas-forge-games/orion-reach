"""Recurring ship costs, construction restrictions and saved balance migration."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orion import ai, balance, motherships, specialists
from orion.designs import ShipDesign
from orion.empire import summarize_empire
from orion.model import ConstructionProject, GameState, RuleError, Ship, new_game
from orion.production import SHIP_TYPES
from orion.storage import Storage
from scenarios import place_near


def campaign(**kwargs):
    return new_game(seed=12, random_starts=False, with_guardians=False,
                    with_black_holes=False, with_tombs=False, with_encounters=False,
                    fog_of_war=False, **kwargs)


class ShipMaintenanceTests(unittest.TestCase):
    def setUp(self):
        previous = balance.active_profile()
        self.addCleanup(lambda: balance.activate(previous))
        balance.activate(balance.default_profile())

    def test_live_budget_counts_each_owned_ship_once_in_orbit_or_transit(self):
        game = campaign()
        home = game.systems[0]
        design = ShipDesign('custom_1', 'Patrol', 'frigate', ('laser',))
        game.ships.append(Ship(game.next_ship_id, 'frigate', home.id, design=design))
        game.next_ship_id += 1
        scout = next(s for s in game.ships_owned_by() if s.kind == 'scout')
        destination = place_near(game, 1)
        game.send_ship(scout.id, destination.id)
        self.assertEqual(game.fleet_maintenance(), 6)
        scout.departure_pending = False
        self.assertEqual(game.fleet_maintenance(), 6)
        self.assertEqual(design.maintenance, 2)
        for owner in game.owners:
            summary = summarize_empire(game, owner=owner)
            self.assertEqual(summary.income, summary.gross_income-summary.maintenance)
            upkeep = sum(game.planet_maintenance(p) for _, p in game.settlements(owner))
            self.assertEqual(summary.maintenance, upkeep+game.fleet_maintenance(owner)+specialists.salaries(game, owner))
        baseline = game.empire_rates[0]
        game.ships = [s for s in game.ships if s.owner != 'player']
        self.assertEqual(game.empire_rates[0], baseline+6)

    def test_turn_deducts_upkeep_once_and_new_completion_starts_next_turn(self):
        game = campaign(with_ai=False)
        planet = game.systems[0].worlds[2]
        game.queue_ship(0, planet.id, 'scout')
        project = planet.construction_queue[0]
        game.fund_project(project, 'player')
        project.progress = project.spec.work_cost-1
        before, expected = game.credits, game.empire_rates[0]
        self.assertEqual(game.fleet_maintenance(), 4)
        report = game.advance_turn()
        self.assertEqual((report.income, game.credits-before), (expected, expected))
        self.assertEqual(game.fleet_maintenance(), 5)
        before, expected = game.credits, game.empire_rates[0]
        report = game.advance_turn()
        self.assertEqual((report.income, game.credits-before), (expected, expected))

    def test_ai_treasury_pays_its_own_fleet_and_debt_remains_possible(self):
        game = campaign()
        game.ships += [Ship(game.next_ship_id+i, 'titan', 0) for i in range(3)]
        game.next_ship_id += 3
        game.credits = 0
        expected = {owner: game.empire_rates_for(owner)[0] for owner in game.owners}
        before = {owner: game.treasury_for(owner) for owner in game.owners}
        with patch('orion.ai.run_ai', return_value=[]):
            report = game.advance_turn()
        self.assertLess(game.credits, 0)
        self.assertTrue(any('debt' in message for message in report.alerts))
        for owner in game.owners:
            self.assertEqual(game.treasury_for(owner)-before[owner], expected[owner])

    def test_consumed_colony_ship_stops_charging_and_capture_transfers_home_upkeep(self):
        game = campaign(with_ai=False)
        colony = next(s for s in game.ships if s.kind == 'colony_ship')
        self.assertEqual(game.fleet_maintenance(), 4)
        game.colonize(colony.id, 0, 3)
        self.assertEqual(game.fleet_maintenance(), 2)
        game = campaign(race_id='wanderers', rival_race_id='terran')
        home = motherships.homes(game)[0]
        home.disabled_turns = 3
        self.assertEqual(game.fleet_maintenance(), 6)
        before = game.fleet_maintenance('rival')
        home.owner = home.habitat.owner = 'rival'
        self.assertEqual(game.fleet_maintenance(), 2)
        self.assertEqual(game.fleet_maintenance('rival'), before+4)

    def test_queued_ships_and_current_fleets_are_in_ai_budget(self):
        game = campaign()
        owner = 'rival'
        system, planet = game.settlements(owner)[0]
        current = ai.projected_income(game, owner)
        game.queue_ship(system.id, planet.id, 'frigate', owner=owner)
        self.assertEqual(ai.projected_income(game, owner), current-2)
        self.assertFalse(ai.can_maintain_ship(game, owner, 'titan'))
        for ship in game.ships_owned_by(owner):
            ship.owner = 'player'
        self.assertEqual(ai.projected_income(game, owner), current-2+4)

    def test_existing_save_gains_defaults_without_losing_custom_balance(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(Path(directory))
            game = campaign(with_ai=False)
            path = storage.save(game)
            data = json.loads(path.read_text())
            data['balance']['version'] = 12
            for ship in data['balance']['data']['ships'].values():
                ship.pop('maintenance')
            data['balance']['data']['ships']['scout']['work_cost'] = 17
            path.write_text(json.dumps(data))
            original = path.read_bytes()
            loaded, _ = storage.load(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(SHIP_TYPES['scout'].work_cost, 17)
            self.assertEqual(loaded.fleet_maintenance(), 4)
            profile = balance.active_profile()
            profile['data']['ships']['scout']['maintenance'] = 3
            balance.activate(profile)
            balance.tag_game(loaded, profile)
            restored, _ = storage.load(storage.save(loaded))
            self.assertEqual(restored.fleet_maintenance(), 8)
            self.assertEqual(restored.empire_rates, loaded.empire_rates)

    def test_structures_cannot_be_bought_even_with_unlimited_money(self):
        for race in ('terran', 'wanderers'):
            game = campaign(with_ai=False, race_id=race)
            system, planet = game.settlements('player')[0]
            game.credits = game.resources = 100000
            for item in ('factory', 'space_hub', 'ascension_gate'):
                with self.subTest(race=race, item=item):
                    planet.construction_queue = [ConstructionProject(item, progress=1)]
                    before = copy.deepcopy(game.to_dict())
                    self.assertEqual(game.buy_construction_cost(system.id, planet.id), 0)
                    with self.assertRaisesRegex(RuleError, 'only ships'):
                        game.buy_construction(system.id, planet.id)
                    self.assertEqual(game.to_dict(), before)
            planet.construction_queue = [ConstructionProject('scout')]
            before = game.fleet_maintenance()
            game.buy_construction(system.id, planet.id)
            self.assertEqual(game.fleet_maintenance(), before+1)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)


if __name__ == '__main__':
    unittest.main()
