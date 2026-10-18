"""System research, exclusive shortcuts, save integrity and real UI controls."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_motherships import campaign, target, advance
from orion import ai, combat, exploration, hyperlanes as lanes, motherships, news, monsters
from orion.empire import summarize_empire
from orion.model import GameState, RuleError, SaveError, Ship
from orion.storage import Storage, SAVE_VERSION


def scientists(game, home=None):
    home = home or motherships.homes(game)[0]
    home.habitat.population = 8
    home.habitat.trade_goods = True
    game.set_workforce(home.system_id, home.habitat.id, 2, 3, 1, owner=home.owner)
    return home


def recovered(game, system_id=0, owner='player'):
    project = lanes.start(game, system_id, owner)
    game._empire(owner).research = project.cost
    lanes.invest(game, system_id, owner)
    return project


def distant(game, project, distance=60):
    origin, dest = game.systems[project.system_id], game.systems[project.destination]
    dest.x, dest.y = origin.x+distance/140, origin.y
    return dest


class HyperlaneResearchTests(unittest.TestCase):
    def test_only_stationary_wanderer_homes_can_start_and_no_duplicate_source(self):
        game = campaign()
        home = scientists(game)
        with self.assertRaisesRegex(RuleError, 'Only the Wanderers'):
            lanes.start(campaign(race_id='terran'), 0)
        with self.assertRaisesRegex(RuleError, 'Station a mothership'):
            lanes.start(game, 1)
        game.send_ship(home.id, target(game).id)
        with self.assertRaisesRegex(RuleError, 'departure order'):
            lanes.start(game, 0)
        game.cancel_departures([home.id])
        project = lanes.start(game, 0)
        self.assertEqual((project.cost, project.allocation), (300, 50))
        with self.assertRaisesRegex(RuleError, 'one forgotten hyperlane'):
            lanes.start(game, 0)
        for value in (-1, 101, True, '50'):
            with self.assertRaises(RuleError):
                lanes.configure(game, 0, allocation=value)

    def test_multiple_local_homes_pool_rp_without_double_spending_or_remote_output(self):
        game = campaign()
        scientists(game)
        second = motherships.create(game, 0, 'player')
        scientists(game, second)
        remote = motherships.create(game, 1, 'player')
        scientists(game, remote)
        gross = game.empire_rates[1]
        local = sum(game.planet_yields(s.habitat)[2] for s in (motherships.homes(game)[0], second))
        project = lanes.start(game, 0)
        lanes.configure(game, 0, allocation=100)
        self.assertEqual(lanes.local_research(game, 0), local)
        self.assertEqual(game.empire_rates[1], gross-local)
        self.assertEqual(summarize_empire(game).research, gross-local)
        report = advance(game)
        self.assertEqual((project.progress, game.research, report.research), (local, gross-local, gross-local))
        self.assertEqual(project.progress+game.research, gross)

    def test_pause_departure_and_return_retain_progress(self):
        game = campaign()
        home = scientists(game)
        project = lanes.start(game, 0)
        advance(game)
        progress = project.progress
        lanes.configure(game, 0, paused=True)
        advance(game)
        self.assertEqual(project.progress, progress)
        lanes.configure(game, 0, paused=False)
        dest = target(game, .25)
        game.send_ship(home.id, dest.id)
        self.assertEqual(lanes.contribution(game, project), 0)
        advance(game)
        self.assertEqual(project.progress, progress)
        with self.assertRaisesRegex(RuleError, 'Station a mothership'):
            lanes.invest(game, 0)
        game.send_ship(home.id, 0)
        advance(game)
        self.assertEqual(project.progress, progress)
        advance(game)
        self.assertGreater(project.progress, progress)

    def test_reserve_investment_only_spends_available_points_and_remaining_cost(self):
        game = campaign()
        project = lanes.start(game, 0)
        game.research = 23
        lanes.invest(game, 0)
        self.assertEqual((project.progress, game.research), (23, 0))
        with self.assertRaisesRegex(RuleError, 'No banked'):
            lanes.invest(game, 0)
        game.research = 400
        lanes.invest(game, 0)
        self.assertEqual((project.progress, game.research, project.completed_turn), (300, 123, game.turn))
        with self.assertRaisesRegex(RuleError, 'no unfinished'):
            lanes.invest(game, 0)

    def test_final_turn_only_diverts_remaining_rp_and_reports_completion(self):
        game = campaign()
        scientists(game)
        gross = game.empire_rates[1]
        project = lanes.start(game, 0)
        project.progress = project.cost-1
        report = advance(game)
        self.assertTrue(project.complete)
        self.assertEqual(game.research, gross-1)
        self.assertEqual(project.completed_turn, game.turn)
        self.assertTrue(any('hyperlane discovered' in m for m in report.completed))
        self.assertEqual(game.empire_rates[1], gross)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_destination_is_stable_and_does_not_reveal_a_survey(self):
        game = campaign()
        prior = copy.deepcopy(game.exploration)
        project = lanes.start(game, 0)
        self.assertNotEqual(project.destination, 0)
        self.assertEqual(lanes.visible_routes(game), [])
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored.hyperlane_projects[0].destination, project.destination)
        self.assertEqual(lanes.start(campaign(), 0).destination, project.destination)
        game.research = 300
        lanes.invest(game, 0)
        self.assertEqual(game.exploration, prior)
        self.assertFalse(game.system_explored(project.destination))

    def test_guardians_and_hostile_blockades_stop_research(self):
        game = campaign(with_ai=True, rival_race_id='terran')
        scientists(game)
        project = lanes.start(game, 0)
        guardian = monsters.Guardian(0, 1, 'space_serpent', 48)
        game.guardians.append(guardian)
        self.assertIn('guardian', lanes.work_error(game, 0))
        self.assertEqual(lanes.contribution(game, project), 0)
        game.guardians.clear()
        from orion.diplomacy import start_war
        start_war(game, 'player', 'rival')
        game.ships.append(Ship(game.next_ship_id, 'frigate', 0, owner='rival'))
        game.next_ship_id += 1
        self.assertIn('blocking', lanes.work_error(game, 0))
        self.assertEqual(lanes.contribution(game, project), 0)

    def test_reverse_link_is_reserved_and_no_black_hole_destinations(self):
        game = campaign()
        project = recovered(game)
        self.assertNotIn(0, lanes.candidates(game, project.destination, 'player'))
        home = motherships.homes(game)[0]
        game.send_ship(home.id, project.destination)
        advance(game)
        other = lanes.start(game, project.destination)
        self.assertNotIn(other.destination, (0, project.destination))
        with_holes = campaign(with_black_holes=True)
        candidates = lanes.candidates(with_holes, 0, 'player')
        from orion.black_holes import KIND
        self.assertTrue(all(with_holes.systems[sid].kind != KIND for sid in candidates))

    def test_completed_news_is_private_persistent_and_readable_even_same_turn(self):
        game = campaign(with_ai=True, rival_race_id='wanderers')
        news.mark_read(game)
        project = recovered(game)
        self.assertEqual(news.unread_count(game), 1)
        self.assertEqual(sum(e.category == 'FORGOTTEN HYPERLANE' for e in news.entries(game)), 1)
        news.mark_read(game)
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(news.unread_count(restored), 0)
        remote = motherships.homes(game, 'rival')[0].system_id
        recovered(game, remote, 'rival')
        game.fog_of_war = False
        self.assertEqual(lanes.visible_routes(game), [project])
        self.assertEqual(sum(e.category == 'FORGOTTEN HYPERLANE' for e in news.entries(game)), 1)


class HyperlaneMovementTests(unittest.TestCase):
    def test_convoy_uses_both_directions_in_one_turn_without_fuel_and_remains_available(self):
        game = campaign()
        project = recovered(game)
        dest = distant(game, project)
        ids = [s.id for s in game.ships]
        self.assertFalse(game.within_fuel_range(dest.id, ships=game.ships))
        self.assertEqual(game.send_ships(ids, dest.id), 1)
        self.assertTrue(all(s.hyperlane and s.departure_pending for s in game.ships))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        advance(game)
        self.assertTrue(all(s.system_id == dest.id and not s.has_course and not s.hyperlane for s in game.ships))
        self.assertEqual(lanes.connections(game, 0), [dest.id])
        self.assertEqual(game.send_ships(ids, 0), 1)
        advance(game)
        self.assertTrue(all(s.system_id == 0 for s in game.ships))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_cannot_use_a_lane_from_an_unrelated_origin(self):
        game = campaign()
        project = recovered(game)
        dest = distant(game, project)
        scout = next(s for s in game.ships if s.kind == 'scout')
        scout.system_id = next(s.id for s in game.systems if s.id not in (0, dest.id))
        self.assertFalse(game.can_reach(dest.id, ships=[scout]))
        with self.assertRaisesRegex(RuleError, 'fuel range'):
            game.send_ship(scout.id, dest.id)

    def test_other_empires_including_other_wanderers_cannot_use_private_routes(self):
        for race in ('terran', 'wanderers'):
            with self.subTest(race=race):
                game = campaign(with_ai=True, rival_race_id=race)
                project = recovered(game)
                scout = next(s for s in game.ships_owned_by('rival') if s.kind == 'scout')
                scout.system_id = 0
                dest = game.systems[project.destination]
                self.assertFalse(lanes.connects(game, 0, dest.id, 'rival'))
                with patch.object(game, 'supply_distance', return_value=100):
                    with self.assertRaisesRegex(RuleError, 'fuel range'):
                        game.send_ship(scout.id, dest.id, owner='rival')
                self.assertGreater(game.travel_turns(game.systems[0], dest, 'rival'), 1)

    def test_orders_can_be_cancelled_and_regular_orders_keep_their_saved_duration(self):
        game = campaign()
        project = recovered(game)
        scout = next(s for s in game.ships if s.kind == 'scout')
        game.send_ship(scout.id, project.destination)
        game.cancel_departures([scout.id])
        self.assertFalse(scout.hyperlane)
        ordinary = game.systems[next(sid for sid in lanes.candidates(game, 0, 'player') if sid != project.destination)]
        ordinary.x, ordinary.y = game.systems[0].x+6/140, game.systems[0].y
        game.send_ship(scout.id, ordinary.id)
        duration = scout.travel_total
        game.hyperlane_projects.append(lanes.HyperlaneProject('player', ordinary.id, 0, progress=300, completed_turn=1))
        self.assertFalse(scout.hyperlane)
        self.assertEqual(GameState.from_dict(game.to_dict()).ship_at(scout.id).travel_total, duration)

    def test_guardian_at_exit_still_starts_combat(self):
        game = campaign()
        project = recovered(game)
        sid = project.destination
        guardian = monsters.Guardian(sid, game.systems[sid].worlds[0].id, 'space_serpent', 48)
        game.guardians.append(guardian)
        game.send_ship(next(s.id for s in game.ships if s.kind == 'scout'), sid)
        advance(game)
        self.assertIsNotNone(game.combat)
        self.assertEqual(game.combat.system_id, sid)

    def test_retreat_can_use_a_remote_recovered_endpoint(self):
        game = campaign(with_ai=True, rival_race_id='terran')
        project = recovered(game)
        dest = distant(game, project)
        scout = next(s for s in game.ships if s.kind == 'scout' and s.owner == 'player')
        game.ships[:] = [s for s in game.ships if s.owner == 'player']
        for system in game.systems:
            if system.id not in (0, dest.id):
                system.x, system.y = game.systems[0].x+.6, game.systems[0].y
        game.ships.append(Ship(game.next_ship_id, 'frigate', 0, owner='rival'))
        game.next_ship_id += 1
        game.start_combat(0, owner='rival', target='player')
        self.assertEqual(combat.retreat_destination(game).id, dest.id)
        self.assertIn(scout.id, {s.id for s in game.ships})

    def test_ai_can_research_and_send_scouts_through_its_own_route(self):
        game = campaign(race_id='terran', with_ai=True, rival_race_id='wanderers')
        home = scientists(game, motherships.homes(game, 'rival')[0])
        lanes.ai_orders(game, 'rival')
        project = lanes.project_at(game, home.system_id, 'rival')
        self.assertIsNotNone(project)
        game._empire('rival').research = project.cost
        lanes.invest(game, home.system_id, 'rival')
        with patch.object(game, 'supply_distance', return_value=100):
            ai.scouting_orders(game, 'rival')
        scouts = [s for s in game.ships_owned_by('rival') if s.kind == 'scout']
        self.assertTrue(any(s.destination == project.destination and s.hyperlane for s in scouts))
        self.assertEqual(lanes.visible_routes(game), [])


class HyperlaneSaveTests(unittest.TestCase):
    def test_version_45_migrates_without_rewriting_source_and_current_round_trips(self):
        game = campaign()
        game.legacy.last_turn = game.turn
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(Path(folder))
            path = storage.save(game)
            data = json.loads(path.read_text())
            data['version'] = 45
            data['game']['victory_conditions'] = ['conquest', 'science', 'council']
            data['game'].pop('hyperlane_projects')
            for ship in data['game']['ships']:
                ship.pop('hyperlane')
            original = json.dumps(data)
            path.write_text(original)
            restored, _ = storage.load(path)
            self.assertEqual(restored, game)
            self.assertEqual(path.read_text(), original)
            recovered(restored)
            restored.send_ships([s.id for s in restored.ships], restored.hyperlane_projects[0].destination)
            loaded, meta = storage.load(storage.save(restored))
            self.assertEqual((loaded, meta['version']), (restored, 51))
            self.assertEqual(SAVE_VERSION, 51)

    def test_invalid_projects_and_forged_voyages_are_rejected(self):
        game = campaign()
        recovered(game)
        game.send_ships([s.id for s in game.ships], game.hyperlane_projects[0].destination)
        bad = [('owner', 'missing'), ('owner', []), ('destination', 0), ('system_id', True),
               ('progress', 301), ('progress', -1), ('cost', 0), ('allocation', 101), ('paused', 1),
               ('completed_turn', 0), ('news_read', 1), ('started_turn', game.turn+1)]
        for key, value in bad:
            with self.subTest(key=key, value=value):
                raw = game.to_dict()
                raw['hyperlane_projects'][0][key] = value
                with self.assertRaises(SaveError):
                    GameState.from_dict(raw)
        for change in ('missing_route', 'duplicate', 'ordinary_speed', 'fake_duration', 'missing_flag', 'not_boolean'):
            with self.subTest(change=change):
                raw = game.to_dict()
                if change == 'missing_route':
                    raw['hyperlane_projects'] = []
                elif change == 'duplicate':
                    raw['hyperlane_projects'] *= 2
                elif change == 'ordinary_speed':
                    raw['ships'][0]['speed_bonus'] = 25
                elif change == 'fake_duration':
                    raw['ships'][0]['travel_total'] = 2
                elif change == 'missing_flag':
                    raw['ships'][0].pop('hyperlane')
                else:
                    raw['ships'][0]['hyperlane'] = 1
                with self.assertRaises(SaveError):
                    GameState.from_dict(raw)


class HyperlaneScreenTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign()
        scientists(self.app.game)
        self.app.go('galaxy')
        self.app.present()

    def click(self, key):
        import pygame as pg
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def drawn(self):
        from orion.ui import text_image
        with patch('orion.ui.text_image', wraps=text_image) as spy:
            self.app.render()
        return '\n'.join(str(call.args[0]) for call in spy.call_args_list)

    def test_actual_research_controls_portal_and_map_course(self):
        app, game = self.app, self.app.game
        self.click('galaxy_hyperlanes')
        self.click('hyperlane_start')
        project = lanes.project_at(game, 0)
        self.assertNotIn(game.systems[project.destination].name, self.drawn())
        self.click('hyperlane_allocation_75')
        self.assertEqual(project.allocation, 75)
        self.click('hyperlane_pause')
        self.assertTrue(project.paused)
        self.click('hyperlane_pause')
        game.research = 300
        self.click('hyperlane_invest')
        self.assertIn('HYPERLANE RECOVERED', self.drawn())
        self.click('hyperlane_back')
        self.click('system_hyperlane_portal')
        dest = distant(game, project)
        self.click(f'hyperlane_plot_{dest.id}')
        self.assertEqual(app.screen, 'galaxy')
        self.assertIn('FORGOTTEN HYPERLANE · 1 TURN', self.drawn())
        self.assertIn('No fuel limit', self.drawn())
        app.select_star(dest.id)
        self.assertTrue(all(s.hyperlane for s in game.ships))

    def test_research_summary_displays_diversion_and_other_races_have_no_button(self):
        game = self.app.game
        project = lanes.start(game, 0)
        self.app.open_research()
        self.assertIn(f'after {lanes.contribution(game, project)} RP to hyperlanes', self.drawn())
        self.app.game = campaign(race_id='terran')
        self.app.open_system(0)
        self.app.render()
        self.assertFalse(any(b.key == 'system_hyperlanes' for b in self.app.buttons))

    def test_pagination_and_portal_targets_do_not_cover_planets_or_homes(self):
        game = self.app.game
        for sid in range(1, 6):
            game.hyperlane_projects.append(lanes.HyperlaneProject('player', sid, 0, progress=300, completed_turn=1))
        self.app.open_system(0)
        self.app.render()
        portal = next(b.rect for b in self.app.buttons if b.key == 'system_hyperlane_portal')
        self.assertEqual(portal.collidelist([b.rect for b in self.app.buttons if b.key.startswith(('world_', 'system_mothership_'))]), -1)
        self.click('system_hyperlanes')
        self.assertEqual(sum(b.key.startswith('hyperlane_plot_') for b in self.app.buttons), 3)
        self.click('hyperlane_next')
        self.assertEqual(sum(b.key.startswith('hyperlane_plot_') for b in self.app.buttons), 2)


if __name__ == '__main__':
    unittest.main()
