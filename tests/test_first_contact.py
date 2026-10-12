from scenarios import legacy_research_payload
from scenarios import legacy_economy
"""Confirmed contact, private diplomacy, collective AI and persistent introductions."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion import ai, first_contact, tomb_worlds
from orion.diplomacy import advance_diplomacy
from orion.exploration import record_survey, refresh
from orion.model import GameState, RuleError, SaveError, Ship, new_game
from orion.personalities import PERSONALITIES
from orion.races import RACES
from orion.storage import Storage
from scenarios import place_near
from test_research_expansion import discover


def campaign(**kwargs):
    return new_game(seed=2408, with_guardians=False, with_tombs=False, random_starts=False, **kwargs)


def add_ship(game, kind, sid, owner):
    ship = Ship(game.next_ship_id, kind, sid, owner=owner)
    game.next_ship_id += 1
    game.ships.append(ship)
    return ship


class ContactRulesTests(unittest.TestCase):
    def test_every_civilization_has_a_distinct_greeting_and_character(self):
        self.assertEqual(set(PERSONALITIES), set(RACES))
        greetings = [p.greeting for p in PERSONALITIES.values()]
        self.assertEqual(len(set(greetings)), 11)
        self.assertTrue(all(0 < len(s) <= 180 and s.isprintable() for s in greetings))
        self.assertEqual(RACES["concord"].default_empire, "Concord Collective")
        self.assertIn("Assimilat", PERSONALITIES["concord"].traits)
        self.assertNotEqual(PERSONALITIES["concord"], PERSONALITIES["nexus"])

    def test_revealed_map_queues_every_starting_empire_on_turn_one(self):
        game = campaign(fog_of_war=False, rival_count=5)
        self.assertEqual(set(first_contact.pending(game)), set(game.opponents))
        self.assertTrue(all(game.diplomacy_between("player", o).contact_turn == 1 for o in game.opponents))
        snapshot = game.to_dict()
        refresh(game)
        self.assertEqual(game.to_dict(), snapshot)

    def test_fog_hides_identities_and_blocks_diplomacy_before_contact(self):
        game = campaign(fog_of_war=True)
        self.assertEqual(first_contact.known_opponents(game), [])
        self.assertEqual(first_contact.pending(game), [])
        before = game.to_dict()
        for action in ("envoy", "gift", "trade", "research"):
            with self.assertRaisesRegex(RuleError, "first contact"):
                game.diplomacy_action(action)
        self.assertEqual(game.to_dict(), before)

    def test_incoming_ship_opens_channel_without_revealing_foreign_home(self):
        game = campaign(fog_of_war=True)
        ship = add_ship(game, "scout", 0, "rival")
        refresh(game)
        self.assertEqual(first_contact.pending(game), ["rival"])
        self.assertIsNone(game.known_system(game.opponent.home_system))
        self.assertIn(PERSONALITIES[game.opponent.race_id].greeting,
                      [e.message for e in game.diplomacy.events])
        game.ships.remove(ship)
        first_contact.acknowledge(game, "rival")
        refresh(game)
        restored = GameState.from_dict(game.to_dict())
        self.assertTrue(first_contact.known(restored, "player", "rival"))
        self.assertFalse(first_contact.pending(restored))

    def test_scout_at_foreign_colony_establishes_contact_even_without_foreign_ships(self):
        game = campaign(fog_of_war=True)
        game.ships[:] = [s for s in game.ships if s.owner == "player"]
        game.ships[0].system_id = game.opponent.home_system
        refresh(game)
        self.assertTrue(first_contact.known(game, "player", "rival"))

    def test_sensor_identification_opens_channel_without_planetary_intelligence(self):
        game = campaign(fog_of_war=True)
        discover(game, "deep_space_radar")
        sid = next(s.id for s in game.systems if s.id not in (0, game.opponent.home_system))
        place_near(game, sid, distance=4)
        add_ship(game, "frigate", sid, "rival")
        refresh(game)
        self.assertTrue(first_contact.pending(game))
        self.assertFalse(game.system_explored(sid))
        self.assertIsNone(game.known_system(game.opponent.home_system))

    def test_two_foreign_empires_meeting_does_not_reveal_them_to_player(self):
        game = campaign(fog_of_war=True, rival_count=3)
        add_ship(game, "scout", game._empire("rival_2").home_system, "rival_3")
        refresh(game)
        self.assertTrue(first_contact.known(game, "rival_2", "rival_3"))
        self.assertFalse(first_contact.known_opponents(game))

    def test_remnant_news_establishes_contact_only_for_notified_observers(self):
        for scouted in (False, True):
            game = campaign(fog_of_war=True, with_ai=False)
            sid = next(s.id for s in game.systems[1:] if s.worlds)
            if scouted:
                record_survey(game, sid, "player")
            tomb = tomb_worlds.TombWorld(sid, 0)
            game.tomb_worlds.append(tomb)
            tomb_worlds.awaken(game, tomb)
            refresh(game)
            self.assertEqual(bool(first_contact.pending(game)), scouted)
            self.assertFalse(game.system_visible(sid))

    def test_pending_and_acknowledged_introductions_survive_real_saves(self):
        game = campaign(fog_of_war=False, rival_count=3)
        first_contact.acknowledge(game, "rival")
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            loaded, _ = storage.load(storage.save(game))
        self.assertEqual(loaded, game)
        self.assertEqual(first_contact.pending(loaded), ["rival_2", "rival_3"])

    def test_v25_migration_preserves_assets_history_and_source_file(self):
        game = campaign(fog_of_war=False, rival_count=3)
        legacy_economy(game)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 25
            legacy_research_payload(payload)
            states = [payload["game"]["diplomacy"], *payload["game"]["other_diplomacy"].values()]
            for state in states:
                state.pop("contact_turn")
                state.pop("introduced")
            path.write_text(json.dumps(payload))
            original = path.read_bytes()
            loaded, _ = storage.load(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(first_contact.pending(loaded))
            self.assertEqual(loaded.systems, game.systems)
            self.assertEqual(loaded.ships, game.ships)
            self.assertEqual(loaded.diplomacy.events, game.diplomacy.events)
            self.assertEqual(storage.load(storage.save(loaded))[0], loaded)

    def test_v25_fog_migration_preserves_old_active_diplomatic_channels(self):
        game = campaign(fog_of_war=True, rival_count=3)
        game.diplomacy.trade_active = True
        loaded = GameState.from_dict(legacy_research_payload(game.to_dict()), version=25)
        self.assertEqual(first_contact.known_opponents(loaded), ["rival"])
        self.assertTrue(loaded.diplomacy.introduced)

    def test_invalid_contact_metadata_is_rejected(self):
        game = campaign(fog_of_war=False)
        for change in ({"contact_turn": -1}, {"contact_turn": True}, {"contact_turn": 2},
                       {"introduced": 1}, {"contact_turn": 0, "introduced": True}):
            data = game.to_dict()
            data["diplomacy"].update(change)
            with self.subTest(change=change), self.assertRaises(SaveError):
                GameState.from_dict(data)
        for key in ("contact_turn", "introduced"):
            data = game.to_dict()
            data["diplomacy"].pop(key)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class PersonalityRulesTests(unittest.TestCase):
    def test_envoys_and_gifts_reflect_recipient_personality(self):
        expected = {"aelari": (15, 13), "kharuun": (12, 15), "concord": (6, 5)}
        for race, (envoy, gift) in expected.items():
            game = campaign(fog_of_war=False, rival_race_id=race)
            game.diplomacy_action("envoy")
            self.assertEqual(game.diplomacy.relations, envoy)
            game.diplomacy_action("gift")
            self.assertEqual(game.diplomacy.relations, envoy+gift)
            self.assertEqual(game.credits, 60)
            self.assertEqual(game.opponent.credits, 170)

    def test_collective_requires_stronger_relations_for_treaties(self):
        game = campaign(fog_of_war=False, rival_race_id="concord")
        game.diplomacy.relations = 30
        self.assertIn("declined", game.diplomacy_action("trade"))
        self.assertFalse(game.diplomacy.trade_active)
        game.diplomacy.offer_ready_turn = game.turn
        game.diplomacy.relations = 45
        self.assertIn("accepted", game.diplomacy_action("trade"))

    def test_breach_penalty_depends_on_offended_civilization(self):
        for race, penalty in (("lithar", 25), ("varkesh", 10), ("concord", 20)):
            game = campaign(fog_of_war=False, rival_race_id=race)
            game.diplomacy.relations = 80
            game.diplomacy.trade_active = True
            game.diplomacy_action("end_trade")
            self.assertEqual(game.diplomacy.relations, 80-penalty)

    def test_wary_relations_thaw_at_different_rates_but_collective_never_forgets(self):
        for race, expected in (("wanderers", -7), ("lithar", -10), ("concord", -10)):
            game = campaign(fog_of_war=False, rival_race_id=race)
            game.diplomacy.relations = -10
            for turn in range(1, 13):
                game.turn, game.year = turn, 2299+turn
                advance_diplomacy(game)
            self.assertEqual(game.diplomacy.relations, expected, race)
            game.diplomacy.relations = -100
            advance_diplomacy(game)
            self.assertEqual(game.diplomacy.relations, -100)

    def invasion_scenario(self, race="concord", fog=False):
        game = campaign(fog_of_war=fog, rival_race_id=race)
        game.turn, game.year = 12, 2311
        sid = game.opponent.home_system
        place_near(game, sid, distance=6)
        for _ in range(3):
            add_ship(game, "frigate", sid, "rival")
        return game

    def test_collective_declares_assimilation_campaign_against_reachable_neutral_world(self):
        game = self.invasion_scenario()
        message = ai.diplomatic_orders(game, "rival")
        self.assertIn("assimilation", message[0])
        self.assertEqual(game.diplomacy.relations, -60)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_peaceful_races_do_not_start_the_same_conquest(self):
        for race in ("aelari", "lithar", "xenonflora", "wanderers", "aetheri", "nexus"):
            game = self.invasion_scenario(race)
            self.assertFalse(ai.diplomatic_orders(game, "rival"))
            self.assertEqual(game.diplomacy.relations, 0)

    def test_collective_respects_treaties_friendship_and_unknown_targets(self):
        for setting in ("trade", "research", "friendly", "unknown", "outmatched"):
            game = self.invasion_scenario(fog=setting == "unknown")
            if setting in ("trade", "research"):
                setattr(game.diplomacy, setting+"_active", True)
            if setting == "friendly":
                game.diplomacy.relations = 25
            if setting == "outmatched":
                for _ in range(6):
                    add_ship(game, "frigate", 0, "player")
            before = game.diplomacy.relations
            self.assertFalse(ai.diplomatic_orders(game, "rival"), setting)
            self.assertEqual(game.diplomacy.relations, before)

    def test_assimilated_population_and_buildings_survive_conquest(self):
        game = campaign(fog_of_war=False, race_id="concord")
        sid, world = game.headquarters("rival")
        game.ships[:] = [s for s in game.ships if s.system_id != sid.id]
        for _ in range(3):
            add_ship(game, "troop_transport", sid.id, "player")
        world.buildings.append("factory")
        population = world.population
        report = game.invade(sid.id, world.id)
        self.assertTrue(report.captured)
        self.assertEqual(world.population, population)
        self.assertIn("factory", world.buildings)
        self.assertIn("assimilated", game.diplomacy.events[-1].message)

    def test_protective_ai_invests_in_fortifications_during_peacetime(self):
        game = campaign(fog_of_war=False, rival_race_id="lithar")
        # Three established, fed colonies with trained forces and room to build.
        game.ships.clear()
        home = game.opponent.home_system
        worlds = game.systems[home].worlds[:3]
        for world in worlds:
            world.owner, world.colonized, world.population = "rival", True, 8
            world.size = "Huge"
            world.buildings = ["hydroponic_farm", "factory", "barracks"]
        game.opponent.credits = 1000
        ai.run_ai(game, "rival")
        self.assertTrue(any(q.item_id == "fortifications" for p in worlds for q in p.construction_queue))
        self.assertEqual(game.diplomacy.relations, 0)


class ContactInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def test_real_start_queue_save_reload_and_skip(self):
        self.app.fog_of_war = False
        self.app.rival_count = 5
        self.app.seed = "2408"
        self.app.start_game()
        self.assertEqual(self.app.screen, "contact")
        before = self.app.game.turn
        for key in (pg.K_e, pg.K_d, pg.K_f, pg.K_r, pg.K_v):
            self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.assertEqual(self.app.game.turn, before)
        self.assertEqual(self.app.screen, "contact")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        original = self.app.contact_owner
        self.click("contact_continue")
        self.assertNotEqual(self.app.contact_owner, original)
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(self.app.screen, "contact")
        self.assertNotEqual(self.app.contact_owner, original)
        self.click("contact_skip")
        self.assertEqual(self.app.screen, "galaxy")
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(self.app.screen, "galaxy")

    def test_replay_is_read_only_and_returns_to_diplomacy(self):
        self.app.game = campaign(fog_of_war=False)
        first_contact.acknowledge(self.app.game, "rival")
        self.app.go("diplomacy")
        before = self.app.game.to_dict()
        self.click("diplomacy_greeting")
        self.assertEqual(self.app.screen, "contact")
        self.click("contact_continue")
        self.assertEqual(self.app.screen, "diplomacy")
        self.assertEqual(self.app.game.to_dict(), before)

    def test_contact_dismissal_returns_to_unresolved_battle(self):
        game = self.app.game = campaign(fog_of_war=True)
        add_ship(game, "frigate", 0, "player")
        add_ship(game, "frigate", 0, "rival")
        game.start_combat(0)
        self.app.go("combat")
        self.app.show_first_contact()
        battle = copy.deepcopy(game.combat)
        self.app.time += 5
        self.app.update_combat()
        self.assertEqual(game.combat, battle)
        self.click("contact_continue")
        self.assertEqual(self.app.screen, "combat")
        self.assertEqual(game.combat, battle)

    def test_skipping_existing_introductions_does_not_skip_future_remnant(self):
        self.app.game = game = campaign(fog_of_war=False)
        self.app.go("galaxy")
        self.app.show_first_contact()
        self.app.skip_contacts()
        sid = next(s.id for s in game.systems if s.worlds and not any(p.colonized for p in s.worlds))
        tomb = tomb_worlds.TombWorld(sid, 0)
        game.tomb_worlds.append(tomb)
        tomb_worlds.awaken(game, tomb)
        refresh(game)
        self.assertTrue(self.app.show_first_contact())
        self.assertEqual(game._empire(self.app.contact_owner).race_id, "remnant")

    def test_pending_transmission_does_not_consume_news_and_reload_returns_to_it(self):
        from orion import news
        self.app.game = game = campaign(fog_of_war=True, with_ai=False)
        from scenarios import set_idle_trade_goods
        set_idle_trade_goods(game)
        game.tomb_worlds.append(tomb_worlds.TombWorld(0, 3))
        self.app.go("galaxy")
        with patch("orion.tomb_worlds.awakening_due", return_value=True):
            self.app.advance_turn()
        self.assertEqual(self.app.screen, "contact")
        self.assertEqual(news.unread_count(game), 1)
        self.assertEqual(game.news_read_turn, 0)
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(self.app.screen, "contact")
        self.click("contact_continue")
        self.assertEqual(self.app.screen, "news")
        self.assertEqual(news.unread_count(self.app.game), 0)

    def test_completed_campaign_does_not_interrupt_result_with_greetings(self):
        self.app.game = game = campaign(fog_of_war=False)
        home = game.headquarters("rival")[1]
        home.owner = "player"
        game.eliminate_defeated()
        game.check_victory()
        self.app.go("result")
        self.assertFalse(self.app.show_first_contact())
        self.assertEqual(self.app.screen, "result")

    def test_unknown_civilizations_are_absent_from_diplomacy_reports_and_objectives(self):
        self.app.game = campaign(fog_of_war=True, rival_count=3)
        from orion.ui import text_image
        for screen in ("diplomacy", "rival", "objectives"):
            self.app.go(screen)
            with patch("orion.ui.text_image", wraps=text_image) as draw:
                self.app.render()
            words = " ".join(str(c.args[0]) for c in draw.call_args_list)
            for rival in self.app.game.opponents.values():
                self.assertNotIn(rival.name, words)

    def test_every_portrait_and_greeting_renders_with_accessible_controls(self):
        for race in RACES:
            self.app.game = campaign(fog_of_war=False, rival_race_id=race)
            self.app.go("galaxy")
            self.app.show_first_contact()
            self.app.render()
            self.assertEqual([b.key for b in self.app.buttons], ["contact_continue"])
            self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in self.app.buttons))
            self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
            self.assertEqual(self.app.screen, "galaxy")


if __name__ == "__main__":
    unittest.main()
