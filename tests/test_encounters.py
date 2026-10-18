"""Neutral guards, private discoveries, timed raids and tactical save continuity."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from orion import encounters as rules, combat, exploration, news, outposts, ai, defenses
from orion.model import new_game, GameState, Ship, RuleError, SaveError
from orion.production import distance_ly, SHIP_TYPES
from orion.storage import Storage, SAVE_VERSION


def campaign(*, ai_enabled=False, **options):
    game = new_game(seed=12, with_ai=ai_enabled, random_starts=False, with_guardians=False,
                    with_tombs=False, with_black_holes=False, with_encounters=False, **options)
    game.encounters = rules.EncounterState(enabled=True)
    return game


def add(game, kind='frigate', sid=0, owner='player'):
    ship = Ship(game.next_ship_id, kind, sid, owner=owner)
    game.next_ship_id += 1
    game.ships.append(ship)
    return ship


def jump(game, turn):
    game.year += turn-game.turn
    game.turn = turn


def win(game):
    for ship in game.combat.fleet(rules.PIRATES):
        ship.hull = ship.shields = 0
    combat.check_losses(game)


class EncounterPlacementTests(unittest.TestCase):
    def test_seeded_sites_repeat_without_changing_other_galaxy_content(self):
        for size in ('Compact', 'Standard', 'Expansive'):
            options = dict(seed=120, galaxy_size=size, random_starts=False)
            first = new_game(**options)
            again = new_game(**options)
            off = new_game(**options, with_encounters=False)
            self.assertEqual(first.encounters, again.encounters)
            self.assertEqual(first.systems, off.systems)
            self.assertTrue(first.encounters.enabled)
            self.assertFalse(off.encounters.fleets or off.encounters.sites)
            homes = [s for o in first.owners for s in first.colony_systems(o)]
            guards = {g.system_id for g in first.guardians}
            for fleet in first.encounters.fleets:
                star = first.systems[fleet.system_id]
                self.assertNotIn(star.id, guards)
                self.assertFalse(any(p.colonized for p in star.worlds))
                self.assertGreaterEqual(min(distance_ly(star, home) for home in homes), 18)
                self.assertEqual(fleet.kind, 'planet')
            self.assertEqual(GameState.from_dict(first.to_dict()), first)

    def test_hidden_site_contents_are_not_exposed_by_known_threats_or_news(self):
        game = campaign(fog_of_war=False)
        game.encounters.sites.append(rules.SearchSite(0, 'ambush'))
        self.assertEqual(rules.known_at(game, 0), [])
        self.assertEqual(rules.news(game), [])
        self.assertIsNone(game.combat)

    def test_disabled_campaign_has_no_searches_or_events(self):
        game = new_game(seed=12, with_encounters=False, with_ai=False)
        for turn in range(20, 121, 10):
            jump(game, turn)
            rules.finish_turn(game, [])
        self.assertIn('disabled', rules.search_error(game, 0))
        self.assertFalse(game.encounters.fleets or game.encounters.events)


class PlanetGuardTests(unittest.TestCase):
    def test_first_sighting_is_reported_once(self):
        game = campaign()
        rules.create(game, 0, 'planet', planet_id=0)
        exploration.refresh(game)
        self.assertEqual(len(rules.news(game)), 1)
        self.assertIn('Mercury', rules.news(game)[0].message)
        exploration.refresh(game)
        self.assertEqual(len(rules.news(game)), 1)

    def test_guard_defends_only_its_planet_and_does_not_intercept_arrivals(self):
        game = campaign()
        worlds = [p for p in game.systems[0].worlds if not p.colonized]
        guarded, accessible = worlds[:2]
        fleet = rules.create(game, 0, 'planet', planet_id=guarded.id)
        add(game, 'outpost_ship')
        self.assertFalse(rules.intercept(game))
        self.assertIn('guarding', game.colonize_error(0, guarded.id))
        self.assertIn('guarding', outposts.deployment_error(game, 0, guarded.id))
        self.assertIsNone(outposts.deployment_error(game, 0, accessible.id))
        with self.assertRaises(RuleError):
            combat.begin_pirate_combat(game, fleet.id)
        add(game)
        combat.begin_pirate_combat(game, fleet.id)
        win(game)
        game.finish_combat()
        self.assertIsNone(outposts.deployment_error(game, 0, guarded.id))

    def test_bounty_is_paid_once_and_diplomacy_does_not_change(self):
        game = campaign(ai_enabled=True)
        add(game)
        fleet = rules.create(game, 0, 'planet', planet_id=0)
        before = copy.deepcopy(game.diplomacy)
        credits, resources = game.credits, game.resources
        battle = combat.begin_pirate_combat(game, fleet.id)
        win(game)
        self.assertEqual((game.credits-credits, game.resources-resources), rules.BOUNTIES['planet'])
        rules.commit_battle(game, battle)
        self.assertEqual((game.credits-credits, game.resources-resources), rules.BOUNTIES['planet'])
        self.assertEqual(before, game.diplomacy)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_pirate_battle_uses_real_tactical_combat(self):
        game = campaign()
        for _ in range(4):
            add(game)
        fleet = rules.create(game, 0, 'planet', planet_id=0)
        combat.begin_pirate_combat(game, fleet.id)
        combat.autoresolve(game)
        self.assertEqual(game.combat.status, 'player_victory')
        self.assertFalse(fleet.alive)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_retreat_keeps_pirate_damage_and_pays_no_bounty(self):
        game = campaign()
        game.systems[1].x, game.systems[1].y = game.systems[0].x+.01, game.systems[0].y
        for ship in game.ships:
            ship.system_id = 1
        add(game, sid=1)
        exploration.refresh(game)
        fleet = rules.create(game, 1, 'ambush')
        combat.begin_pirate_combat(game, fleet.id, intercept=True)
        game.combat.fleet(rules.PIRATES)[0].hull -= 7
        credits = game.credits
        combat.retreat(game)
        self.assertEqual(fleet.hulls, [SHIP_TYPES['frigate'].hull-7])
        self.assertEqual(game.credits, credits)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_missile_bases_defend_raids_but_do_not_attack_another_planet(self):
        game = campaign()
        home = game.settlements()[0][1]
        home.buildings.append('missile_base')
        defenses.commissioned(game, home, 'missile_base')
        add(game)
        guard = rules.create(game, 0, 'planet', planet_id=0)
        combat.begin_pirate_combat(game, guard.id)
        self.assertFalse(any(s.kind == 'missile_base' for s in game.combat.ships))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        win(game)
        game.finish_combat()
        raid = rules.create(game, 0, 'raid', target_owner='player')
        jump(game, raid.arrival_turn)
        combat.begin_pirate_combat(game, raid.id)
        self.assertTrue(any(s.kind == 'missile_base' for s in game.combat.ships))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class ScoutSearchTests(unittest.TestCase):
    def test_two_full_turns_and_one_time_salvage_reward(self):
        game = campaign()
        game.encounters.sites.append(rules.SearchSite(0, 'salvage'))
        search = rules.start_search(game, 0)
        game.advance_turn()
        self.assertEqual(search.progress, 1)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        control = GameState.from_dict(game.to_dict())
        control.encounters.sites.clear()
        control.advance_turn()
        game.advance_turn()
        self.assertEqual(search.progress, 2)
        self.assertEqual((game.credits-control.credits, game.resources-control.resources), (60, 40))
        with self.assertRaises(RuleError):
            rules.start_search(game, 0)
        self.assertEqual(game.encounters.sites[0].claimed_by, 'player')

    def test_departure_pauses_and_replacement_scout_resumes_progress(self):
        game = campaign()
        search = rules.start_search(game, 0)
        game.advance_turn()
        scout = game.ship_at(search.ship_id)
        game.systems[1].x, game.systems[1].y = game.systems[0].x+.01, game.systems[0].y
        game.send_ship(scout.id, 1)
        self.assertNotIn(('player', 0), rules.ready_searches(game))
        self.assertFalse(rules.reserved(game, scout))
        game.advance_turn()
        self.assertEqual(search.progress, 1)
        rules.start_search(game, 0)
        self.assertNotEqual(search.ship_id, scout.id)
        game.advance_turn()
        self.assertEqual(search.progress, 2)

    def test_arriving_scout_starts_work_on_the_following_turn(self):
        game = campaign()
        scout = next(s for s in game.ships if s.kind == 'scout')
        game.systems[1].x, game.systems[1].y = game.systems[0].x+.001, game.systems[0].y
        game.send_ship(scout.id, 1)
        self.assertIn('Station a scout', rules.search_error(game, 1))
        game.advance_turn()
        search = rules.start_search(game, 1)
        self.assertEqual(search.progress, 0)
        game.advance_turn()
        self.assertEqual(search.progress, 1)

    def test_hidden_ambush_only_fights_after_search_completes(self):
        game = campaign()
        game.encounters.sites.append(rules.SearchSite(0, 'ambush'))
        rules.start_search(game, 0)
        game.advance_turn()
        self.assertIsNone(game.combat)
        game.advance_turn()
        self.assertEqual(game.combat.sides, ('player', rules.PIRATES))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        self.assertEqual(len(game.encounters.fleets), 1)

    def test_archive_reward_is_claimed_by_first_empire_only(self):
        game = campaign(ai_enabled=True)
        game.encounters.sites.append(rules.SearchSite(0, 'archive'))
        add(game, 'scout', owner='rival')
        rules.start_search(game, 0, 'rival')
        rules.start_search(game, 0)
        before = {o: game._empire(o).research for o in game.owners}
        for _ in range(2):
            ready = rules.ready_searches(game)
            jump(game, game.turn+1)
            rules.finish_searches(game, ready)
        self.assertEqual(game.opponent.research-before['rival'], 80)
        self.assertEqual(game.research, before['player'])
        self.assertEqual(game.encounters.sites[0].claimed_by, 'rival')
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_search_survives_destroyed_scout_and_accepts_new_assignment(self):
        game = campaign()
        search = rules.start_search(game, 0)
        game.ships = [s for s in game.ships if s.id != search.ship_id]
        self.assertEqual(rules.ready_searches(game), [])
        restored = GameState.from_dict(game.to_dict())
        resumed = rules.start_search(restored, 0)
        self.assertNotEqual(search.ship_id, resumed.ship_id)

    def test_ai_keeps_search_scout_stationary_then_resumes_exploration(self):
        game = campaign(ai_enabled=True)
        owner = 'rival'
        sid = game.opponent.home_system
        rules.ai_orders(game, owner)
        search = rules.search_at(game, sid, owner)
        self.assertIsNotNone(search)
        ai.scouting_orders(game, owner)
        self.assertFalse(game.ship_at(search.ship_id, owner=owner).has_course)
        for _ in range(2):
            ready = rules.ready_searches(game)
            jump(game, game.turn+1)
            rules.finish_searches(game, ready)
        self.assertFalse(rules.reserved(game, game.ship_at(search.ship_id, owner=owner)))


class PirateRaidTests(unittest.TestCase):
    def test_three_turn_warning_one_theft_and_timed_withdrawal(self):
        game = campaign()
        game.ships.clear()
        game.credits = 1000
        fleet = rules.create(game, 0, 'raid', target_owner='player')
        self.assertEqual(fleet.arrival_turn, 4)
        self.assertEqual(rules.known_status(game, fleet), 'incoming')
        self.assertFalse(rules.active(game, fleet))
        jump(game, 3)
        rules.finish_turn(game, [])
        self.assertEqual(game.credits, 1000)
        jump(game, 4)
        rules.finish_turn(game, [])
        self.assertEqual((game.credits, fleet.loot, fleet.raided), (940, 60, True))
        jump(game, 5)
        rules.finish_turn(game, [])
        self.assertEqual(game.credits, 940)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        jump(game, fleet.expires_turn)
        rules.finish_turn(game, [])
        self.assertTrue(fleet.departed)
        self.assertIsNone(rules.blockade(game, 0))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_poor_empires_lose_at_most_ten_percent_of_credits(self):
        game = campaign()
        game.ships.clear()
        game.credits = 53
        fleet = rules.create(game, 0, 'raid', target_owner='player')
        jump(game, fleet.arrival_turn)
        rules.finish_turn(game, [])
        self.assertEqual((game.credits, fleet.loot), (48, 5))

    def test_defended_settlement_fights_instead_of_losing_money(self):
        game = campaign()
        add(game)
        fleet = rules.create(game, 0, 'raid', target_owner='player')
        credits = game.credits
        jump(game, fleet.arrival_turn)
        rules.finish_turn(game, [])
        self.assertFalse(fleet.raided)
        self.assertEqual(game.credits, credits)
        self.assertTrue(rules.intercept(game))
        self.assertEqual(game.combat.encounter_id, fleet.id)

    def test_recovered_loot_is_added_to_bounty_once(self):
        game = campaign()
        game.ships.clear()
        fleet = rules.create(game, 0, 'raid', target_owner='player')
        jump(game, fleet.arrival_turn)
        rules.finish_turn(game, [])
        add(game)
        credits = game.credits
        battle = combat.begin_pirate_combat(game, fleet.id)
        win(game)
        self.assertEqual(game.credits-credits, rules.BOUNTIES['raid'][0]+fleet.loot)
        rules.commit_battle(game, battle)
        self.assertEqual(game.credits-credits, rules.BOUNTIES['raid'][0]+fleet.loot)

    def test_raids_do_not_capture_planets_or_hit_an_absent_settlement(self):
        game = campaign()
        game.ships.clear()
        fleet = rules.create(game, 1, 'raid', target_owner='player')
        credits = game.credits
        jump(game, fleet.arrival_turn)
        rules.finish_turn(game, [])
        self.assertFalse(fleet.raided)
        self.assertEqual(game.credits, credits)
        self.assertFalse(any(p.colonized for p in game.systems[1].worlds))

    def test_scheduler_protects_early_home_system_and_limits_active_raids(self):
        game = campaign()
        with patch.object(rules.random, 'Random') as rng:
            rng.return_value.random.return_value = 0
            rng.return_value.choice.side_effect = lambda choices: choices[0]
            jump(game, 20)
            rules.schedule_raid(game)
            self.assertEqual(game.encounters.fleets, [])
            jump(game, 60)
            rules.schedule_raid(game)
            self.assertEqual(len(game.encounters.fleets), 1)
            rules.schedule_raid(game)
            self.assertEqual(len(game.encounters.fleets), 1)

    def test_ai_pirate_battle_resolves_without_waiting_for_player(self):
        game = campaign(ai_enabled=True)
        sid = game.opponent.home_system
        for _ in range(4):
            add(game, sid=sid, owner='rival')
        fleet = rules.create(game, sid, 'ambush')
        self.assertFalse(rules.intercept(game))
        self.assertIsNone(game.combat)
        self.assertFalse(fleet.alive)
        self.assertEqual(rules.news(game), [])

    def test_unseen_defeat_does_not_leak_through_stale_map_contact(self):
        game = campaign(ai_enabled=True)
        sid = game.opponent.home_system
        for _ in range(4):
            add(game, sid=sid, owner='rival')
        fleet = rules.create(game, sid, 'ambush')
        fleet.known['player'] = 'active'
        self.assertFalse(game.system_visible(sid))
        rules.intercept(game)
        self.assertEqual(rules.known_status(game, fleet), 'active')
        self.assertEqual(rules.status(game, fleet), 'defeated')
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_private_news_stays_private_even_with_fog_disabled(self):
        game = campaign(ai_enabled=True, fog_of_war=False)
        rules.create(game, game.opponent.home_system, 'raid', target_owner='rival')
        self.assertFalse(rules.news(game))
        self.assertFalse(any(e.category == 'NEUTRAL ENCOUNTER' for e in news.entries(game)))
        rules.create(game, 0, 'raid', target_owner='player')
        self.assertEqual(len(rules.news(game)), 1)
        self.assertGreater(news.unread_count(game), 0)
        news.mark_read(game)
        self.assertEqual(game.encounters.news_read, game.encounters.next_event_id-1)


class EncounterSaveTests(unittest.TestCase):
    def test_partially_destroyed_fleet_can_be_fought_again_and_saved(self):
        game = campaign()
        game.systems[1].x, game.systems[1].y = game.systems[0].x+.01, game.systems[0].y
        add(game, sid=1)
        fleet = rules.create(game, 1, 'ambush', count=2)
        combat.begin_pirate_combat(game, fleet.id, intercept=True)
        game.combat.fleet(rules.PIRATES)[0].hull = 0
        combat.retreat(game)
        game.finish_combat()
        add(game, sid=1)
        battle = combat.begin_pirate_combat(game, fleet.id, intercept=True)
        self.assertEqual(len(battle.fleet(rules.PIRATES)), 1)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        win(game)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_impossible_search_progress_or_unearned_claim_is_rejected(self):
        game = campaign()
        rules.start_search(game, 0)
        payload = game.to_dict()
        payload['encounters']['searches'][0]['progress'] = 1
        with self.assertRaises(SaveError):
            GameState.from_dict(payload)
        game.encounters.sites.append(rules.SearchSite(0, 'archive', 'player', 1))
        with self.assertRaises(SaveError):
            GameState.from_dict(game.to_dict())

    def test_version_48_migration_keeps_new_encounters_disabled(self):
        game = campaign()
        payload = game.to_dict()
        payload.pop('encounters')
        original = copy.deepcopy(payload)
        restored = GameState.from_dict(payload, version=48)
        self.assertEqual(payload, original)
        self.assertFalse(restored.encounters.enabled)
        self.assertEqual(SAVE_VERSION, 51)
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_real_save_file_roundtrip_keeps_search_and_private_warning(self):
        game = campaign()
        rules.start_search(game, 0)
        rules.create(game, 0, 'raid', target_owner='player')
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            loaded, meta = storage.load(path)
            self.assertEqual((loaded, meta['version']), (game, 51))

    def test_corrupt_pirate_state_is_rejected_without_mutating_source(self):
        game = campaign()
        rules.create(game, 0, 'raid', target_owner='player')
        mutations = [lambda s: s.update(enabled='yes'), lambda s: s.update(next_id=9),
                     lambda s: s['fleets'][0].update(hulls=[999]),
                     lambda s: s['fleets'][0].update(hulls=[True]),
                     lambda s: s['fleets'][0].update(system_id=-1),
                     lambda s: s['fleets'][0].update(arrival_turn=99),
                     lambda s: s['fleets'][0].update(target_owner='pirates'),
                     lambda s: s['fleets'][0].update(loot=60),
                     lambda s: s['fleets'][0].update(departed=True),
                     lambda s: s['fleets'][0].update(known={'player': 'active'}),
                     lambda s: s.update(enabled=False)]
        for change in mutations:
            payload = game.to_dict()
            change(payload['encounters'])
            original = copy.deepcopy(payload)
            with self.subTest(change=change), self.assertRaises(SaveError):
                GameState.from_dict(payload)
            self.assertEqual(payload, original)

    def test_incomplete_or_mismatched_tactical_pirates_are_rejected(self):
        game = campaign()
        add(game)
        fleet = rules.create(game, 0, 'ambush', count=2)
        combat.begin_pirate_combat(game, fleet.id, intercept=True)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        payload = game.to_dict()
        payload['combat']['ships'].pop()
        with self.assertRaises(SaveError):
            GameState.from_dict(payload)
        payload = game.to_dict()
        payload['combat']['encounter_id'] = None
        with self.assertRaises(SaveError):
            GameState.from_dict(payload)


class EncounterInterfaceTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign()
        for _, planet in self.app.game.settlements():
            planet.trade_goods = True
        self.app.go('galaxy')

    def button(self, key):
        self.app.render()
        return next(b for b in self.app.buttons if b.key == key)

    def test_system_search_button_and_render_do_not_modify_campaign(self):
        app = self.app
        app.open_system(0)
        self.button('system_encounters').action()
        self.assertEqual(app.screen, 'encounters')
        before = app.game.to_dict()
        app.render()
        self.assertEqual(before, app.game.to_dict())
        button = self.button('encounters_search')
        self.assertTrue(button.enabled)
        button.action()
        self.assertIsNotNone(rules.search_at(app.game, 0))

    def test_guarded_world_and_map_badge_open_encounter_panel(self):
        app, game = self.app, self.app.game
        add(game)
        fleet = rules.create(game, 0, 'planet', planet_id=0)
        exploration.refresh(game)
        self.button('pirates_0').action()
        self.assertEqual(app.screen, 'encounters')
        app.open_system(0)
        app.open_planet(0)
        self.button('planet_pirates').action()
        self.assertEqual(app.screen, 'encounters')
        self.button(f'encounters_engage_{fleet.id}').action()
        self.assertEqual(app.screen, 'combat')
        self.assertEqual(game.combat.encounter_id, fleet.id)

    def test_setup_encounter_toggle_controls_created_game(self):
        app = self.app
        app.go('setup')
        self.button('neutral_encounters').action()
        self.assertFalse(app.with_encounters)
        app.start_game()
        self.assertFalse(app.game.encounters.enabled)
