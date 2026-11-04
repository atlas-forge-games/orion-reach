"""Full civilization rosters, crowded starts, save compatibility and reachable UI."""
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
from orion import council, first_contact, model, victory_view
from orion.app import App
from orion.empires import EMPIRE_IDS, PLAYER_PALETTES, empire_color, max_rivals
from orion.model import GALAXY_SIZES, GameState, SaveError, new_game
from orion.races import RACES
from orion.storage import SAVE_VERSION, Storage
from orion.victory import known_race_goals


def campaign(**kwargs):
    settings = dict(seed=2408, galaxy_size="Compact", rival_count="all", fog_of_war=False)
    settings.update(kwargs)
    return new_game(**settings)


class AllCivilizationsRulesTests(unittest.TestCase):
    def assert_roster(self, game):
        self.assertEqual(len(game.owners), len(RACES))
        self.assertEqual({game._empire(o).race_id for o in game.owners}, set(RACES))
        homes = [r.home_system for r in game.opponents.values()]
        if not game.is_observer:
            homes.append(0)
        self.assertEqual(len(set(homes)), len(RACES))
        self.assertFalse(set(homes) & {g.system_id for g in game.guardians})
        for owner in game.owners:
            system, home = game.headquarters(owner)
            self.assertEqual(home.owner, owner)
            self.assertGreater(home.population, 0)
            self.assertGreaterEqual(len(game.ships_owned_by(owner)), 3)
            for other in game.owners:
                if other != owner:
                    self.assertIsNotNone(game.diplomacy_between(owner, other))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_all_civilizations_for_every_player_and_every_galaxy_size(self):
        for size in GALAXY_SIZES:
            for race in (*RACES, "observer"):
                with self.subTest(size=size, race=race):
                    self.assert_roster(campaign(galaxy_size=size, race_id=race))

    def test_all_matches_numeric_maximum_and_remains_seeded(self):
        for race in ("terran", "wanderers", "observer"):
            for seed in (2, 13, 101, 82576):
                with self.subTest(race=race, seed=seed):
                    first = campaign(race_id=race, seed=seed)
                    second = campaign(race_id=race, seed=seed, rival_count=max_rivals(race))
                    a, b = first.to_dict(), second.to_dict()
                    a.pop("campaign_id")
                    b.pop("campaign_id")
                    self.assertEqual(a, b)
                    self.assert_roster(first)
        with self.assertRaises(SaveError):
            campaign(rival_race_id="terran")

    def test_empty_systems_receive_homeworlds_if_a_crowded_seed_needs_them(self):
        original = model.generate_planets
        for race in ("terran", "observer"):
            seen = set()
            def sparse(system, seed, *, player_home=True):
                if system.id not in seen and not (system.id == 0 and player_home):
                    seen.add(system.id)
                    system.planets = 0
                    return []
                return original(system, seed, player_home=player_home)
            with self.subTest(race=race), patch("orion.model.generate_planets", side_effect=sparse):
                self.assert_roster(campaign(race_id=race))

    def test_every_identity_has_a_distinct_color_and_existing_colors_stay_stable(self):
        for palette in PLAYER_PALETTES:
            self.assertEqual(len({empire_color(o, palette) for o in EMPIRE_IDS}), len(EMPIRE_IDS))
        self.assertEqual([empire_color(o) for o in EMPIRE_IDS[:7]],
                         [(44, 164, 255), (250, 168, 111), (203, 169, 255),
                          (145, 223, 126), (249, 207, 116), (245, 151, 200), (203, 213, 239)])

    def test_current_files_and_previous_save_format_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(Path(folder))
            game = campaign(race_id="observer")
            path = storage.save(game)
            self.assertEqual(json.loads(path.read_text())["version"], SAVE_VERSION)
            self.assertEqual(storage.load(path)[0], game)
            old = campaign(rival_count=5)
            path = storage.save(old)
            payload = json.loads(path.read_text())
            payload["version"] = 60
            path.write_text(json.dumps(payload))
            self.assertEqual(storage.load(path)[0], old)
            with self.assertRaises(SaveError):
                GameState.from_dict(game.to_dict(), version=60)

    def test_all_thirteen_ai_empires_advance_and_resume_deterministically(self):
        game = campaign(race_id="observer", victory_conditions=(), with_tombs=False,
                        with_encounters=False, with_guardians=False, fog_of_war=True)
        resumed = GameState.from_dict(game.to_dict())
        for _ in range(12):
            game.advance_turn()
            resumed.advance_turn()
            self.assertEqual(game, resumed)
        self.assertEqual(game.turn, 13)
        for empire in game.opponents.values():
            self.assertGreater(len(empire.events), 1)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class AllCivilizationsUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.window = pg.display.set_mode((1440, 900))
        self.app.settings["autosave"] = self.app.settings["animated_background"] = False
        self.app.game = campaign()
        for owner in first_contact.pending(self.app.game):
            first_contact.acknowledge(self.app.game, owner)

    def frame(self):
        self.app.render()
        self.app.present()

    def button(self, key):
        return next(b for b in self.app.buttons if b.key == key)

    def click(self, key):
        self.frame()
        button = self.button(key)
        self.assertTrue(button.enabled, key)
        self.app.display_view.ensure_visible(button.rect)
        self.frame()
        pos = self.app.canvas.point(button.rect.center)
        pos = (pos[0]+self.app.viewport.x, pos[1]+self.app.viewport.y)
        self.assertTrue(self.app.window.get_rect().collidepoint(pos))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
        self.frame()

    def collect_pages(self, prefix, next_key):
        found = set()
        while True:
            self.frame()
            for button in self.app.buttons:
                if button.key.startswith(prefix):
                    found.add(button.key.removeprefix(prefix))
                    self.assertLessEqual(button.rect.bottom, 700)
            button = self.button(next_key)
            if not button.enabled:
                return found
            self.click(next_key)

    def test_setup_all_and_largest_numeric_counts_launch_without_duplicate_races(self):
        self.app.go("setup")
        self.click("rival_count_all")
        self.assertEqual(self.app.rival_count, "all")
        self.app.choose_race("observer")
        self.assertEqual(self.app.rival_count, "all")
        self.click("launch")
        self.assertTrue(self.app.game.is_observer)
        self.assertEqual(len(self.app.game.owners), len(RACES))
        self.app.choose_rival_count(len(RACES))
        self.app.choose_race("terran")
        self.assertEqual(self.app.rival_count, len(RACES)-1)
        self.app.go("setup")
        self.click("rival_count_all")
        self.click("launch")
        self.assertEqual({self.app.game._empire(o).race_id for o in self.app.game.owners}, set(RACES))

    def test_statistics_every_empire_is_reachable_and_keeps_its_toggle_when_paging(self):
        self.app.go("statistics")
        owners = self.collect_pages("statistics_empire_", "statistics_empires_next")
        self.assertEqual(owners, set(self.app.game.owners))
        last = self.button("statistics_empire_rival_12")
        self.click(last.key)
        self.assertIn("rival_12", self.app.statistics_hidden)
        self.click("statistics_empires_previous")
        self.click("statistics_empires_next")
        self.assertIn("rival_12", self.app.statistics_hidden)

    def test_council_every_candidate_is_reachable_and_last_page_vote_is_recorded(self):
        council.schedule(self.app.game)
        council.convene_due(self.app.game)
        self.app.go("council")
        owners = self.collect_pages("council_vote_", "council_empires_next")
        self.assertEqual(owners, set(self.app.game.owners))
        candidate = next(b.key for b in self.app.buttons if b.key.startswith("council_vote_"))
        self.click(candidate)
        self.assertEqual(self.app.game.council.election.ballots["player"], candidate.removeprefix("council_vote_"))

    def test_coalition_all_targets_are_reachable_and_last_page_selection_works(self):
        self.app.go("diplomacy")
        self.app.show_diplomatic_affairs("coalitions", "rival")
        owners = self.collect_pages("dialog_target_", "coalition_targets_next")
        self.assertEqual(owners, set(self.app.game.opponents)-{"rival"})
        self.click("dialog_target_rival_12")
        self.assertEqual(self.app.dialog["coalition_choice"], "rival_12")

    def test_objectives_all_known_empires_and_diplomacy_last_contact_are_reachable(self):
        self.app.objectives_tab = "race"
        self.app.go("objectives")
        names = set()
        with patch("orion.victory_view.text", wraps=victory_view.text) as drawn:
            self.frame()
            self.click("objectives_empires_next")
            names.update(str(call.args[1]) for call in drawn.call_args_list)
        for owner, _ in known_race_goals(self.app.game):
            self.assertIn(self.app.game.empire_name_for(owner), names)
        self.app.go("diplomacy")
        self.app.rival_id = "rival_12"
        self.frame()
        self.assertTrue(self.button("diplomacy_contact_rival_12").enabled)

    def test_paging_controls_remain_clickable_with_large_text_and_small_window(self):
        self.app.window = pg.display.set_mode((1080, 720))
        self.app.settings["ui_scale"] = 175
        self.app.go("setup")
        self.click("rival_count_all")
        self.assertEqual(self.app.rival_count, "all")
        self.app.go("statistics")
        self.click("statistics_empires_next")
        self.click("statistics_empires_next")
        self.click("statistics_empire_rival_12")
        self.assertIn("rival_12", self.app.statistics_hidden)


if __name__ == "__main__":
    unittest.main()
