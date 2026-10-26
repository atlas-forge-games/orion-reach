"""Six-field choices, physical unlocks, powered facilities and classic saves."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from dataclasses import asdict

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame as pg

from orion import ai, balance, defenses, economy, megastructures, population
from orion.advanced_buildings import NEW_BUILDINGS
from orion.app import App
from orion.balance_document import BalanceDocument
from orion.buildings import BUILDINGS
from orion.model import GameState, RuleError, new_game
from orion.research import BRANCHES, TECHNOLOGIES, ResearchState, branch_tiers, choices
from orion.research_fields import TIERS
from orion.storage import SAVE_VERSION, Storage


def discover(game, identifier, owner='player'):
    tech = TECHNOLOGIES[identifier]
    state = game.research_state(owner)
    for tier in range(1, tech.tier+1):
        if tier in state.completed_tiers(tech.branch):
            continue
        selected = identifier if tier == tech.tier else choices(tech.branch, tier)[0].id
        game._empire(owner).research = TECHNOLOGIES[selected].cost
        game.choose_research(selected, owner=owner)
    assert identifier in state.completed


class SixFieldTests(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def game(self, **kwargs):
        return new_game(seed=2408, random_starts=False, with_ai=kwargs.pop('with_ai', False),
                        with_guardians=False, with_tombs=False, with_black_holes=False,
                        with_encounters=False, **kwargs)

    def test_every_tier_has_three_reachable_options_and_completion_excludes_both_others(self):
        self.assertEqual(len(BRANCHES), 6)
        self.assertEqual(sum(len(rows) for rows in TIERS.values()), 33)
        for branch in BRANCHES:
            for selected_slot in range(3):
                state = ResearchState()
                for tier in branch_tiers(branch):
                    options = choices(branch, tier)
                    with self.subTest(branch=branch, tier=tier, slot=selected_slot):
                        self.assertEqual(len(options), 3)
                        self.assertTrue(all(state.status(t.id) == 'available' for t in options))
                        chosen = options[selected_slot]
                        state.active = chosen.id
                        remaining, discovered = state.spend(chosen.cost+17)
                        self.assertEqual((remaining, discovered.id), (17, chosen.id))
                        self.assertEqual([state.status(t.id) for t in options],
                                         ['discovered' if t.id == chosen.id else 'excluded' for t in options])
                        self.assertEqual(ResearchState.from_dict(asdict(state)), state)
                self.assertEqual(state.finished_branches, 1)

    def test_switching_all_three_and_cross_field_conserves_rp_and_invalid_orders_are_atomic(self):
        game = self.game()
        game.research = 41
        ids = [t.id for t in choices('construction', 1)] + ['compact_reactors']
        for identifier in ids*3:
            game.choose_research(identifier)
            self.assertEqual((game.research, game.technology.progress), (0, 41))
            self.assertEqual(game.technology.completed, [])
        for identifier in ('nanostructured_materials', 'missing', [], None):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.choose_research(identifier)
            self.assertEqual(game.to_dict(), before)
        game.choose_research(ids[2])
        game.research = TECHNOLOGIES[ids[2]].cost-41
        game.advance_research()
        self.assertEqual(game.technology.status(ids[0]), 'excluded')
        self.assertEqual(game.technology.status(ids[1]), 'excluded')

    def test_factory_research_unlocks_construction_without_improving_existing_factories(self):
        game = self.game(); planet = game.planet_at(0, 2)
        planet.buildings = ['solar_array', 'factory']
        before = game.planet_yields(planet)[0]
        self.assertIsNotNone(game.build_error(0, 2, 'advanced_factory'))
        discover(game, 'automated_factories')
        self.assertEqual(game.planet_yields(planet)[0], before)
        self.assertIsNone(game.build_error(0, 2, 'advanced_factory'))
        game.resources = game.credits = 10000
        game.queue_building(0, 2, 'advanced_factory', surface_site=(145, 200))
        self.assertEqual(game.planet_yields(planet)[0], before)
        from scenarios import finish_building_next_turn
        finish_building_next_turn(game)
        self.assertGreater(game.planet_yields(planet)[0], before)
        self.assertEqual(planet.surface_layout['advanced_factory'][0:2], [145, 200])
        self.assertIsNotNone(game.build_error(0, 2, 'advanced_factory'))
        path = Storage(self.temp.name).save(game)
        loaded, _ = Storage(self.temp.name).load(path)
        self.assertEqual(loaded, game)

    def test_every_new_facility_is_gated_and_can_be_built_saved_and_inspected(self):
        from orion.building_info import describe
        for identifier in NEW_BUILDINGS:
            with self.subTest(building=identifier):
                game = self.game(); planet = game.planet_at(0, 2)
                self.assertIsNotNone(game.build_error(0, 2, identifier))
                discover(game, BUILDINGS[identifier].technology)
                self.assertIsNone(game.build_error(0, 2, identifier))
                game.queue_building(0, 2, identifier)
                self.assertIn(identifier, planet.surface_layout)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)
                info = describe(game, 0, planet, 'surface_'+identifier, live=True)
                self.assertIsNotNone(info)
                self.assertTrue(BUILDINGS[identifier].effect_text(planet.richness))

    def test_advanced_factory_does_not_require_earlier_factory_choice_or_building(self):
        game = self.game()
        discover(game, 'trade_algorithms')
        discover(game, 'nanostructured_materials')
        self.assertNotIn('automated_factories', game.technology.completed)
        self.assertIsNone(game.build_error(0, 2, 'nanofactory'))
        self.assertEqual(game.planet_at(0, 2).buildings, [])

    def test_population_facilities_work_for_biology_assembly_and_passive_growth_only_when_powered(self):
        for race in ('terran', 'nexus', 'xenonflora', 'skirr'):
            with self.subTest(race=race):
                game = self.game(race_id=race); planet = game.headquarters()[1]
                planet.population = 8; planet.farmers = 5; planet.scientists = 0; planet.miners = 0
                planet.buildings = ['singularity_plant', 'hydroponic_farm', 'factory']
                before = game.population_report(planet)
                self.assertGreater(before.growth_rate, 0)
                planet.buildings.append('medical_centre')
                enabled = game.population_report(planet)
                self.assertGreater(enabled.growth_rate, before.growth_rate)
                b = economy.local_bonuses(planet, game.bonuses_for())
                self.assertEqual(economy.local_bonuses(planet, b)['facility_growth'], 25)
                planet.disabled_buildings = [3]
                self.assertEqual(game.population_report(planet).growth_rate, before.growth_rate)
                planet.disabled_buildings = [0]
                planet.buildings[0] = 'solar_array'
                planet.buildings += ['quantum_research_lab', 'nanofactory']
                # Put expensive loads ahead of the care centre to exhaust local power.
                planet.buildings = ['quantum_research_lab', 'medical_centre']
                planet.disabled_buildings = []
                self.assertEqual(game.population_report(planet).facility_growth, 0)

    def test_adaptation_reduces_penalties_without_removing_racial_preferences_or_changing_planets(self):
        game = self.game(); planet = game.planet_at(0, 2)
        planet.biome = 'Ice'
        before = game.population_report(planet).environment_percent
        planet.buildings = ['singularity_plant', 'habitat_dome', 'adaptation_centre', 'terraforming_facility']
        report = game.population_report(planet)
        self.assertEqual(report.adaptation, 80)
        self.assertEqual(report.environment_percent, before+(100-before)*80//100)
        self.assertLess(report.environment_percent, 100)
        self.assertEqual(planet.biome, 'Ice')
        planet.biome = 'Gaia'
        self.assertEqual(game.population_report(planet).environment_percent, 125)

    def test_capacity_and_local_strain_are_powered_and_never_apply_twice(self):
        game = self.game(); planet = game.planet_at(0, 2)
        base = population.population_capacity(planet)
        planet.buildings = ['solar_array', 'enclosed_biosphere', 'administration_centre']
        self.assertGreater(population.population_capacity(planet), base)
        modifiers = economy.local_bonuses(planet, {'administrative_strain': 40})
        self.assertEqual(modifiers['administrative_strain'], 25)
        self.assertEqual(economy.local_bonuses(planet, modifiers)['administrative_strain'], 25)
        self.assertEqual(game.strain_report(planet).relief, 15)
        self.assertEqual(game.strain_report(planet).total,
                         economy.local_bonuses(planet, game.bonuses_for())['administrative_strain'])
        planet.disabled_buildings = [1, 2]
        self.assertEqual(population.population_capacity(planet), base)
        self.assertEqual(economy.local_bonuses(planet, {'administrative_strain': 40})['administrative_strain'], 40)

    def test_advanced_shield_requires_new_construction_and_does_not_stack_capacity(self):
        game = self.game(); planet = game.planet_at(0, 2)
        planet.buildings = ['singularity_plant', 'planetary_shield']
        defenses.commissioned(game, planet, 'planetary_shield')
        discover(game, 'barrier_fields')
        self.assertEqual(defenses.shield_capacity(game, planet), 100)
        self.assertIsNone(game.build_error(0, 2, 'advanced_planetary_shield'))
        planet.buildings.append('advanced_planetary_shield')
        defenses.commissioned(game, planet, 'advanced_planetary_shield')
        self.assertEqual(defenses.effective_shield(game, planet), 200)
        planet.disabled_buildings = [2]
        self.assertEqual(defenses.effective_shield(game, planet), 100)
        game.advance_turn()  # Enter the next recovery turn with valid history.
        defenses.advance(game)
        self.assertEqual(planet.shield_points, 100)
        planet.buildings = ['singularity_plant', 'advanced_planetary_shield']; planet.disabled_buildings = []
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_advanced_interdiction_is_powered_and_in_flight_saves_preserve_its_limits(self):
        from orion import navigation
        from orion.model import Ship
        from scenarios import place_near
        game = self.game(with_ai=True, fog_of_war=False)
        target, planet = game.headquarters('rival')
        place_near(game, target.id, distance=7)
        discover(game, 'subspace_interdiction', owner='rival')
        self.assertFalse(game.research_state('rival').has_unlock('gravity_wells'))
        planet.buildings = ['singularity_plant', 'advanced_interdictor']
        game.diplomacy.relations = -100
        game.ships = [Ship(1, 'frigate', 0)]; game.next_ship_id = 2
        ship = game.ships[0]
        game.send_ship(ship.id, target.id)
        self.assertEqual(ship.approach_slow, 40)
        self.assertGreater(ship.approach_range, 5)
        self.assertEqual(Storage(self.temp.name).load(Storage(self.temp.name).save(game))[0], game)
        planet.disabled_buildings = [1]
        self.assertEqual(navigation.route_modifiers(game, game.systems[0], target, 'player'), (0, 0, 0))
        self.assertEqual(ship.approach_slow, 40)  # Existing voyages keep their snapshot.
        profile = balance.default_profile()
        profile['data']['buildings']['advanced_interdictor']['interdiction_slow'] = 100
        self.assertTrue(balance.validate(profile))

    def test_megastructure_choices_have_real_unlocks_and_gas_giants_stay_uncolonizable(self):
        game = self.game()
        discover(game, 'nanostructured_materials')
        self.assertIn('Stellar Forge Engineering', megastructures.start_error(game, 0, 'stellar_forge'))
        self.assertIn('Asteroid Engineering', megastructures.start_error(game, 0, 'asteroid_network'))
        game = self.game(); discover(game, 'stellar_forge_engineering')
        self.assertIsNone(megastructures.start_error(game, 0, 'stellar_forge'))
        gas = next(p for s in game.systems for p in s.worlds if p.is_gas_giant)
        self.assertEqual(population.population_capacity(gas), 0)

    def test_editor_supports_third_slot_and_validates_complete_triples(self):
        document = BalanceDocument(Path(self.temp.name)/'balance.json')
        before = copy.deepcopy(document.profile)
        document.move_technology('civil_engineering', 'power', 1, 2)
        self.assertEqual(document.choices('power', 1)[2], 'civil_engineering')
        self.assertEqual(balance.validate(document.profile), [])
        document.undo(); self.assertEqual(document.profile, before)
        document.profile['data']['technologies']['civil_engineering']['tier'] = 2
        self.assertTrue(any('exactly three' in e for e in balance.validate(document.profile)))

    def test_migration_adds_new_templates_without_repairing_corrupt_original_records(self):
        from orion.research_fields import NEW_TECHNOLOGIES
        profile = balance.classic_profile()
        profile['version'] = 20
        for key in NEW_TECHNOLOGIES:
            profile['data']['technologies'].pop(key)
        for key in NEW_BUILDINGS:
            profile['data']['buildings'].pop(key)
        self.assertFalse(balance.validate(balance.upgrade_profile(profile)))
        for section, key, field in (('technologies', 'ion_drives', 'name'),
                                    ('buildings', 'factory', 'resource_cost')):
            malformed = copy.deepcopy(profile)
            malformed['data'][section][key].pop(field)
            self.assertTrue(balance.validate(balance.upgrade_profile(malformed)))
            malformed = copy.deepcopy(profile)
            malformed['data'][section].pop(key)
            self.assertTrue(balance.validate(balance.upgrade_profile(malformed)))

    def test_all_unlocked_facilities_are_reachable_through_catalogue_pages(self):
        from orion.buildings import BUILDING_GROUPS
        app = App(Path(self.temp.name), capture=True)
        self.addCleanup(app.audio.close); self.addCleanup(pg.quit)
        app.game = self.game()
        # A recovered archive can legally provide otherwise excluded choices.
        state = app.game.technology
        state.completed = [t.id for t in TECHNOLOGIES.values() if t.enabled and t.branch in BRANCHES]
        state.recovered = state.completed.copy()
        app.open_planet(2); app.go('colony')
        before = app.game.to_dict()
        for category, identifiers in enumerate(BUILDING_GROUPS):
            app.colony_build_page = category; app.colony_catalog_page = 0
            seen = set()
            while True:
                app.render()
                buttons = {b.key: b for b in app.buttons}
                seen.update(k.removeprefix('build_') for k in buttons if k.startswith('build_'))
                self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in buttons.values()))
                next_page = buttons.get('colony_catalog_next')
                if not next_page or not next_page.enabled:
                    break
                next_page.action()
            expected = {b for b in identifiers if app.game.build_error(0, 2, b) is None}
            self.assertEqual(seen, expected)
        self.assertEqual(app.game.to_dict(), before)

    def test_encyclopedia_lists_both_alternatives_and_hides_disabled_legacy_templates(self):
        from orion.encyclopedia import articles
        technology = next(a for a in articles() if a.id == 'technology_automated_factories')
        alternatives = next(value for heading, value in technology.sections if heading == 'EXCLUSIVE ALTERNATIVES')
        self.assertIn(TECHNOLOGIES['civil_engineering'].name, alternatives)
        self.assertIn(TECHNOLOGIES['trade_algorithms'].name, alternatives)
        balance.activate(balance.classic_profile())
        self.assertNotIn('technology_relic_analysis', {a.id for a in articles()})

    def test_ai_completes_all_fields_for_different_races_without_skipping_or_deadlocking(self):
        for race in ('terran', 'nexus', 'skirr', 'varkesh', 'wanderers'):
            with self.subTest(race=race):
                game = self.game(with_ai=True, rival_race_id=race)
                game.opponent.research = 1000000
                for count in range(33):
                    ai.research_choice(game)
                    self.assertEqual(len(game.opponent.technology.completed), count+1)
                self.assertEqual(game.opponent.technology.finished_branches, 6)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_real_v082_save_preserves_tree_effects_active_project_and_original_file(self):
        path = Path(__file__).parent/'fixtures'/'v082_research_save.json'
        before = path.read_bytes(); payload = json.loads(before)
        game, _ = Storage(self.temp.name).load(path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(BRANCHES), 9)
        self.assertEqual(game.technology.active, 'field_laboratories')
        self.assertEqual(game.technology.progress, 37)
        self.assertEqual(game.technology.completed, payload['game']['technology']['completed'])
        self.assertEqual(game.technology.bonuses['factory_industry'], 2)
        self.assertEqual(len(choices('construction', 1)), 2)
        self.assertIsNotNone(game.build_error(0, 2, 'advanced_factory'))
        saved = Storage(self.temp.name).save(game)
        restored, _ = Storage(self.temp.name).load(saved)
        self.assertEqual(restored, game)
        self.assertEqual(json.loads(saved.read_text())['version'], SAVE_VERSION)
        balance.activate(balance.default_profile())
        self.assertEqual(len(BRANCHES), 6)

    def test_real_screen_shows_six_blocks_and_all_three_choices_at_scaled_window_sizes(self):
        self.addCleanup(pg.quit)
        app = App(Path(self.temp.name), capture=True); app.game = self.game(); app.go('research')
        before = app.game.to_dict()
        for size in ((980, 900), (1280, 800), (1920, 1080)):
            app.window = pg.display.set_mode(size, pg.RESIZABLE)
            app.research_overview = True; app.render(); app.present()
            blocks = [b for b in app.buttons if b.key.startswith('research_branch_')]
            self.assertEqual(len(blocks), 6)
            self.assertEqual(len({b.rect.x for b in blocks}), 2)
            self.assertEqual(len({b.rect.y for b in blocks}), 3)
            for branch in BRANCHES:
                app.select_research_branch(branch)
                for tier in branch_tiers(branch):
                    app.select_research_tier(tier); app.render()
                    buttons = [b for b in app.buttons if b.key.startswith('research_choose_')]
                    self.assertEqual(len(buttons), 3)
                    self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
                    for technology in choices(branch, tier):
                        app.show_technology_info(technology.id); app.render()
                        self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
                        app.cancel_dialog()
            self.assertEqual(app.game.to_dict(), before)
        app.select_research_branch('construction'); app.select_research_tier(1); app.render(); app.present()
        third = next(b for b in app.buttons if b.key == 'research_choose_trade_algorithms')
        x, y = third.rect.center; v = app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            app.handle_event(pg.event.Event(event, pos=pos, button=1))
        self.assertEqual(app.game.technology.active, 'trade_algorithms')
