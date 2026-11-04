"""Colony shortages apply to each building's contribution, including its workers."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from orion import combat, defenses, economy, ground_combat, navigation, production_breakdown, specialists
from orion.buildings import BUILDINGS
from orion.model import GameState
from scenarios import empty_fleet_game


class ProportionalPowerTests(unittest.TestCase):
    def setUp(self):
        self.game = empty_fleet_game(seed=2408, with_ai=False)
        self.planet = self.game.headquarters('player')[1]
        self.planet.buildings = ['factory', 'mine', 'research_lab', 'trade_center']
        self.planet.richness = 'Average'
        self.planet.population = 12
        self.planet.species = {'terran': 12}
        self.planet.farmers, self.planet.miners, self.planet.scientists = 1, 1, 4

    def test_seven_of_ten_scales_buildings_and_workforce_through_end_turn(self):
        g, p = self.game, self.planet
        with patch.object(economy, 'BASE_ENERGY', 7):
            power = g.planet_energy(p)
            self.assertEqual((power.generated, power.demand, power.used, power.efficiency), (7, 10, 7, .7))
            # Six workers plus 70% of a factory's (4 fixed + 6 worker bonus).
            self.assertEqual(g.planet_yields(p), (13, 13, 13))
            self.assertEqual(g.planet_resources(p), 6)
            self.assertEqual(economy.building_status(p, 0, g.bonuses_for()), '70% POWER')
            p.buildings.reverse()
            self.assertEqual(g.planet_yields(p), (13, 13, 13))
            breakdown = production_breakdown.describe(g, p, 'industry')
            self.assertEqual(breakdown.total, 13)
            for phrase in ('70%', '6 × 0.7', 'Factory (incl. upgrades): 2.8'):
                self.assertIn(phrase, ' '.join(breakdown.lines))
            from orion.colony_view import building_effect
            self.assertEqual(building_effect(g, BUILDINGS['factory'], p, power.efficiency),
                             '+2.8 IND · +0.7 IND/worker')
            g.queue_building(0, p.id, 'solar_array')
            estimate = g.queue_estimates(p)[0]
            start = g.resources
            turn = g.advance_turn()
            self.assertEqual((p.construction_queue[0].progress, turn.research, turn.resources), (13, 13, 6))
            self.assertEqual(g.resources, start+6-p.construction_queue[0].paid_resources)
            self.assertTrue(any('70% efficiency' in alert for alert in turn.alerts))
            self.assertEqual(estimate, 2)
            g.advance_turn()
            self.assertIn('solar_array', p.buildings)
            self.assertEqual(g.planet_energy(p).efficiency, 1)

    def test_zero_draw_blackout_surplus_and_disabling(self):
        g, p = self.game, self.planet
        p.buildings.append('field_lab')
        free_lab = replace(BUILDINGS['field_lab'], energy_use=0)
        with patch.dict(BUILDINGS, field_lab=free_lab), patch.object(economy, 'BASE_ENERGY', 0):
            power = g.planet_energy(p)
            self.assertEqual((power.active, power.offline, power.efficiency), ((4,), (0, 1, 2, 3), 0))
            self.assertEqual(g.planet_yields(p)[2], 8+3+4)
            p.disabled_buildings = [0, 1, 2, 3]
            self.assertEqual((g.planet_energy(p).demand, g.planet_energy(p).efficiency), (0, 1))
            self.assertEqual(g.building_efficiency(p, 'field_lab'), 1)
        p.buildings.pop()
        p.disabled_buildings.clear()
        upkeep = g.planet_maintenance(p)
        with patch.object(economy, 'BASE_ENERGY', 7):
            g.toggle_building(0, p.id, p.buildings.index('factory'))
            self.assertEqual((g.planet_energy(p).demand, g.planet_energy(p).efficiency), (7, 1))
            self.assertEqual(g.planet_maintenance(p), upkeep)
            g.toggle_building(0, p.id, p.buildings.index('factory'))
            self.assertEqual(g.planet_energy(p).efficiency, .7)
        for supply in (10, 20):
            with patch.object(economy, 'BASE_ENERGY', supply):
                self.assertEqual((g.planet_energy(p).efficiency, g.planet_yields(p)), (1, (16, 16, 16)))

    def test_food_mining_and_population_facilities(self):
        g, p = self.game, self.planet
        p.buildings = ['hydroponic_farm', 'mine', 'research_lab', 'barracks', 'trade_center']
        p.farmers, p.miners = 6, 2
        with patch.object(economy, 'BASE_ENERGY', 7):
            self.assertEqual(g.population_report(p).produced, 25)  # 6 natural + 12 farmers + 7 facilities.
            self.assertEqual(g.planet_resources(p), 8)  # 6 base plus 2.8 from the mine.
            self.assertEqual(production_breakdown.describe(g, p, 'food').total, 25)
            p.buildings = ['medical_centre', 'enclosed_biosphere', 'habitat_dome']
            local = economy.local_bonuses(p, g.bonuses_for())
            self.assertEqual((local['facility_growth'], local['facility_capacity'], local['facility_adaptation']),
                             (17.5, 14, 14))
            self.assertIs(type(g.population_report(p).capacity), int)

    def test_shields_missiles_and_fractional_recruits_survive_save(self):
        g, p = self.game, self.planet
        p.buildings = ['planetary_shield', 'missile_base', 'barracks', 'jump_gate']
        p.shield_points, p.battery_hull = 100, 40
        with patch.object(economy, 'BASE_ENERGY', 14):
            self.assertEqual(defenses.effective_shield(g, p), 70)
            self.assertEqual(defenses.recovery_rates(g, p), (17, 2))
            self.assertEqual(combat.battle_bases(g, 0, 'player')[0].damage, 7)
            self.assertEqual(ground_combat.train(p, g.bonuses_for()), 0)
            restored = GameState.from_dict(g.to_dict())
            home = restored.planet_at(0, p.id)
            self.assertAlmostEqual(home.training_progress, .7)
            recruits = 0
            for _ in range(9):
                recruits += ground_combat.train(home, restored.bonuses_for())
                home.garrison = 0  # Trained troops depart after each turn.
            self.assertEqual((recruits, home.training_progress), (7, 0))

    def test_gate_uses_the_weaker_endpoint_and_space_hub_visits_slow(self):
        g, p = self.game, self.planet
        p.buildings = ['jump_gate', 'space_hub']
        system = next(s for s in g.systems[1:] if s.worlds and not s.worlds[0].is_gas_giant)
        other = system.worlds[0]
        other.owner, other.colonized, other.population = 'player', True, 1
        other.buildings = ['jump_gate', 'solar_array']
        with patch.object(economy, 'BASE_ENERGY', 7):
            self.assertEqual(navigation.route_modifiers(g, g.systems[0], system, 'player')[0], 35)
            self.assertEqual(specialists.visit_chance(g, 'player'), specialists.SOCIAL_VISIT_CHANCE*.7)
            p.ascension_gate = True
            power = g.planet_energy(p)
            self.assertFalse(power.gate_powered)
            self.assertEqual((power.used, power.efficiency), (7, .7))

    def test_mothership_modules_follow_the_local_grid(self):
        g = empty_fleet_game(seed=2408, race_id='wanderers', with_ai=False)
        home = g.headquarters('player')[1]
        self.assertTrue(home.habitat)
        home.buildings = ['factory', 'mine', 'research_lab', 'trade_center']
        with patch.object(economy, 'BASE_ENERGY', 7):
            self.assertEqual(g.planet_energy(home).efficiency, .7)
            for index in range(len(home.buildings)):
                self.assertEqual(economy.building_status(home, index, g.bonuses_for()), '70% POWER')
            restored = GameState.from_dict(g.to_dict())
            self.assertEqual(restored.planet_energy(restored.headquarters('player')[1]).efficiency, .7)

    def test_old_battle_roster_and_in_flight_firepower_survive_migration(self):
        from tools.preview_planetary_combat import scenario
        for old_base_present in (True, False):
            with self.subTest(old_base_present=old_base_present):
                g, earth, mars = scenario()
                base_id = defenses.base_id(0, earth.id)
                if old_base_present:
                    g.combat_fire(base_id, defenses.base_id(0, mars.id))
                earth.buildings = (['missile_base']+['research_lab']*3 if old_base_present
                                   else ['research_lab']*3+['missile_base'])
                old = g.to_dict()
                old['combat'].pop('standby_bases')
                for ship in old['combat']['ships']:
                    ship.pop('battery_damage')
                if not old_base_present:
                    old['combat']['ships'] = [s for s in old['combat']['ships'] if s['id'] != base_id]
                restored = GameState.from_dict(old, version=61)
                self.assertEqual(bool(restored.combat.ship(base_id)), old_base_present)
                if old_base_present:
                    self.assertEqual(restored.combat.projectiles[0].strength, 10)
                self.assertEqual(GameState.from_dict(restored.to_dict()), restored)
