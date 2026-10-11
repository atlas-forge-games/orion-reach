"""Random expedition starts and independent empires across strategy, combat and saves."""

import copy
import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion import combat, exploration, monsters
from orion.empires import PLAYER, RIVAL, RIVAL_IDS, empire_color
from orion.model import GALAXY_SIZES, GameState, SaveError, Ship, new_game
from orion.production import GATE_CHARGE_TURNS
from orion.research import BRANCHES, TECHNOLOGIES, branch_tiers, choices
from orion.victory import gate_blocked


def add_ships(game, system_id, owner, kinds):
    result = []
    for kind in kinds:
        ship = Ship(game.next_ship_id, kind, system_id, owner=owner)
        game.next_ship_id += 1
        game.ships.append(ship)
        result.append(ship)
    return result


def capture(game, attacker, defender):
    empire = game._empire(defender)
    sid, pid = (0, 2) if defender == PLAYER else (empire.home_system, empire.home_planet)
    game.ships[:] = [s for s in game.ships if s.system_id != sid]
    add_ships(game, sid, attacker, ["troop_transport"]*3)
    return game.invade(sid, pid, owner=attacker)


class RandomStartTests(unittest.TestCase):
    def test_all_sizes_and_rival_counts_create_separate_equipped_empires(self):
        for size in GALAXY_SIZES:
            for count in range(6):
                with self.subTest(size=size, count=count):
                    game = new_game(seed=2408, galaxy_size=size, rival_count=count)
                    self.assertEqual(tuple(game.opponents), RIVAL_IDS[:count])
                    self.assertEqual(len({game.race_id, *(r.race_id for r in game.opponents.values())}), count+1)
                    homes = [0, *(r.home_system for r in game.opponents.values())]
                    self.assertEqual(len(set(homes)), count+1)
                    self.assertFalse(set(homes) & {g.system_id for g in game.guardians})
                    self.assertEqual(len({empire_color(o) for o in game.owners}), count+1)
                    for owner in game.owners:
                        system, world = game.headquarters(owner)
                        self.assertEqual((world.owner, world.population), (owner, 8))
                        expected = ["frigate", "scout", "scout", "troop_transport", "troop_transport"] if game._empire(owner).race_id == "varkesh" else ["colony_ship", "scout", "scout"]
                        self.assertEqual(sorted(s.kind for s in game.ships_owned_by(owner)), expected)
                        self.assertEqual({s.system_id for s in game.ships_owned_by(owner)}, {system.id})
                        self.assertEqual([s.system_id for s in game.exploration.surveys if s.owner == owner], [system.id])
                    self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_seed_reproduces_worlds_races_and_random_homes(self):
        locations, rosters = set(), set()
        for seed in (2, 101, 2408, 82576):
            a = new_game(seed=seed, rival_count=5)
            b = new_game(seed=seed, rival_count=5)
            da, db = a.to_dict(), b.to_dict()
            da.pop("campaign_id")
            db.pop("campaign_id")
            self.assertEqual(da, db)
            locations.add((a.systems[0].x, a.systems[0].y))
            rosters.add(tuple(r.race_id for r in a.opponents.values()))
            self.assertNotEqual((a.systems[0].x, a.systems[0].y), (.35, .55))
        self.assertEqual(len(locations), 4)
        self.assertGreater(len(rosters), 1)

    def test_invalid_counts_are_rejected_and_solo_has_no_conquest_result(self):
        for count in (-1, 6, True, 1.5, "3", []):
            with self.subTest(count=count), self.assertRaises(SaveError):
                new_game(seed=2, rival_count=count)
        solo = new_game(seed=2, rival_count=0)
        for _ in range(3):
            solo.advance_turn()
        self.assertIsNone(solo.result)
        self.assertFalse(solo.opponents)
        self.assertEqual(GameState.from_dict(solo.to_dict()), solo)


class IndependentEmpireTests(unittest.TestCase):
    def test_every_ai_develops_and_resumes_deterministically_with_both_fog_settings(self):
        for fog in (False, True):
            game = new_game(seed=101, galaxy_size="Compact", rival_count=5, fog_of_war=fog)
            twin = GameState.from_dict(game.to_dict())
            for _ in range(35):
                game.advance_turn()
                twin.advance_turn()
                self.assertEqual(game, twin)
            for owner in game.opponents:
                colonies = [p for s in game.systems for p in s.worlds if p.owner == owner]
                self.assertTrue(any(p.buildings for p in colonies), owner)
                self.assertGreater(len(game._empire(owner).events), 1, owner)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_diplomacy_gifts_cooldowns_and_treaties_are_bilateral(self):
        game = new_game(seed=101, rival_count=3, fog_of_war=False)
        target = "rival_2"
        original = copy.deepcopy(game.diplomacy)
        game.diplomacy_action("gift", target)
        self.assertEqual((game.credits, game._empire(target).credits, game.opponent.credits), (70, 170, 120))
        self.assertEqual(game.diplomacy, original)
        self.assertEqual(game.diplomacy_between(target, "rival_3").relations, 0)
        game.diplomacy_action("envoy", RIVAL)
        self.assertEqual(game.diplomacy_between(PLAYER, target).relations, 12)  # Lithar response to gifts.
        for owner in (RIVAL, target):
            state = game.diplomacy_between(PLAYER, owner)
            state.relations = 60
            state.trade_active = state.research_active = True
        self.assertEqual(game.diplomatic_yields(), (10, 6))
        self.assertEqual(game.diplomatic_yields("rival_3"), (0, 0))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_scout_discoveries_and_surveys_belong_to_the_actual_visitor(self):
        game = new_game(seed=2408, rival_count=3, with_guardians=False)
        homes = {0, *(r.home_system for r in game.opponents.values())}
        sid = next(s.id for s in game.systems if s.id not in homes and exploration.discovery_at(game, s.id))
        scout = next(s for s in game.ships_owned_by("rival_3") if s.kind == "scout")
        scout.system_id = sid
        before = (game.credits, game.opponent.credits, game._empire("rival_2").credits)
        exploration.refresh(game, recover=True)
        self.assertEqual((game.credits, game.opponent.credits, game._empire("rival_2").credits), before)
        self.assertEqual(game.exploration.discoveries[0].owner, "rival_3")
        self.assertTrue(game.system_explored(sid, "rival_3"))
        for owner in (PLAYER, RIVAL, "rival_2"):
            self.assertFalse(game.system_explored(sid, owner))
            self.assertNotIn(sid, game.exploration.scanned(owner))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_guardian_knowledge_and_ai_encounters_are_independent(self):
        game = new_game(seed=2408, galaxy_size="Expansive", rival_count=3)
        guardian = game.guardians[0]
        scout = next(s for s in game.ships_owned_by("rival_3") if s.kind == "scout")
        scout.system_id = guardian.system_id
        exploration.refresh(game)
        self.assertEqual(monsters.known_status(game, guardian.system_id, "rival_3"), "alive")
        self.assertIsNone(monsters.known_status(game, guardian.system_id, RIVAL))
        self.assertIsNone(monsters.known_status(game, guardian.system_id, PLAYER))
        monsters.intercept(game)
        self.assertIsNone(game.combat)
        self.assertTrue(scout.in_transit or scout not in game.ships)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_capture_eliminates_one_rival_without_ending_or_revealing_to_third_party(self):
        game = new_game(seed=2408, rival_count=3, with_guardians=False)
        target = "rival_2"
        home = game._empire(target).home_system
        scout = next(s for s in game.ships_owned_by(target) if s.kind == "scout")
        scout.system_id = 0
        report = capture(game, PLAYER, target)
        self.assertTrue(report.captured)
        self.assertIsNone(game.result)
        self.assertFalse(game.ships_owned_by(target))
        self.assertIsNotNone(game.diplomacy_error("gift", target))
        for owner in (PLAYER, target):
            self.assertEqual(game.known_system(home, owner).worlds[game._empire(target).home_planet].owner, PLAYER)
        for owner in (RIVAL, "rival_3"):
            self.assertFalse(game.system_explored(home, owner))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        capture(game, PLAYER, RIVAL)
        self.assertIsNone(game.result)
        capture(game, PLAYER, "rival_3")
        self.assertEqual((game.result.winner, game.result.condition), (PLAYER, "conquest"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_losing_player_home_ends_game_while_multiple_rivals_remain(self):
        game = new_game(seed=2408, rival_count=3, with_guardians=False)
        self.assertTrue(capture(game, "rival_3", PLAYER).captured)
        self.assertEqual(game.result.condition, "elimination")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_any_rival_can_win_science_and_third_party_ships_block_gates(self):
        game = new_game(seed=2408, rival_count=3, with_guardians=False)
        owner = "rival_3"
        for branch in BRANCHES:
            for tier in branch_tiers(branch):
                tech = choices(branch, tier)[0]
                game._empire(owner).research += tech.cost
                game.choose_research(tech.id, owner=owner)
        game._empire(owner).research += TECHNOLOGIES["ascension_theory"].cost
        game.choose_research("ascension_theory", owner=owner)
        system, planet = game.headquarters(owner)
        add_ships(game, system.id, "rival_2", ["scout"])
        self.assertTrue(gate_blocked(game, system.id, owner))
        planet.ascension_gate, planet.gate_charge = True, GATE_CHARGE_TURNS
        game.check_victory()
        self.assertEqual((game.result.winner, game.result.condition), (owner, "science"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class MultipleFleetTests(unittest.TestCase):
    def encounter(self):
        game = new_game(seed=2408, rival_count=3, with_guardians=False, fog_of_war=False)
        game.ships.clear()
        add_ships(game, 0, PLAYER, ["frigate", "frigate"])
        add_ships(game, 0, RIVAL, ["scout"])
        add_ships(game, 0, "rival_2", ["frigate"])
        return game

    def test_targeted_combat_preserves_third_party_and_its_relationships(self):
        game = self.encounter()
        third_party = copy.deepcopy(game.ships_owned_by(RIVAL))
        game.diplomacy.relations, game.diplomacy.trade_active = 60, True
        game.start_combat(0, target="rival_2")
        self.assertEqual(game.combat.sides, (PLAYER, "rival_2"))
        self.assertTrue(game.diplomacy.trade_active)
        self.assertEqual(game.diplomacy_between(PLAYER, "rival_2").relations, -100)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        combat.autoresolve(game)
        self.assertEqual(game.ships_owned_by(RIVAL), third_party)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.finish_combat()
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_rival_retreat_preserves_full_owner_identifier(self):
        game = self.encounter()
        game.start_combat(0, owner="rival_2", target=PLAYER)
        game.combat_retreat("rival_2")
        self.assertEqual(game.combat.status, "rival_2_retreat")
        self.assertTrue(all(s.in_transit for s in game.ships_owned_by("rival_2")))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_hostile_ai_fleets_resolve_without_human_and_leave_bystanders_alone(self):
        game = self.encounter()
        sid = game.opponent.home_system
        add_ships(game, sid, RIVAL, ["frigate", "frigate"])
        add_ships(game, sid, "rival_3", ["frigate"])
        before = copy.deepcopy(game.ships_owned_by(PLAYER))
        game.diplomacy_between(RIVAL, "rival_3").relations = -100
        self.assertFalse(combat.intercept(game))
        self.assertIsNone(game.combat)
        self.assertFalse(game.fleet_at(sid, RIVAL) and game.fleet_at(sid, "rival_3"))
        self.assertEqual(game.ships_owned_by(PLAYER), before)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_three_empire_active_battle_can_resume_after_save(self):
        game = self.encounter()
        game.start_combat(0, target="rival_2")
        twin = GameState.from_dict(game.to_dict())
        for _ in range(200):
            if game.combat.status != "active":
                break
            self.assertEqual(combat.ai_action(game, game.combat.active_owner), combat.ai_action(twin, twin.combat.active_owner))
            self.assertEqual(game, twin)
        self.assertNotEqual(game.combat.status, "active")


class MultipleEmpireSaveTests(unittest.TestCase):
    def test_json_object_order_does_not_change_empire_identity(self):
        game = new_game(seed=2, rival_count=5)
        data = game.to_dict()
        data["other_opponents"] = dict(reversed(list(data["other_opponents"].items())))
        self.assertEqual(GameState.from_dict(data), game)

    def test_unknown_owners_missing_relations_and_mixed_observer_data_are_rejected(self):
        game = new_game(seed=2, rival_count=3)
        valid = game.to_dict()
        cases = []
        bad = copy.deepcopy(valid)
        bad["ships"][0]["owner"] = "rival_5"
        cases.append(bad)
        bad = copy.deepcopy(valid)
        bad["other_diplomacy"].pop(next(iter(bad["other_diplomacy"])))
        cases.append(bad)
        bad = copy.deepcopy(valid)
        bad["exploration"]["scanned_others"]["rival_5"] = []
        cases.append(bad)
        bad = copy.deepcopy(valid)
        bad["other_opponents"]["rival_5"] = bad["other_opponents"].pop("rival_2")
        cases.append(bad)
        for index, bad in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(SaveError):
                GameState.from_dict(bad)
        self.assertEqual(game.to_dict(), valid)


class MultipleEmpireInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.present()
        self.app.game = new_game(seed=2408, rival_count=3, fog_of_war=False, with_guardians=False)
        from orion.first_contact import pending, acknowledge
        for owner in pending(self.app.game):
            acknowledge(self.app.game, owner)

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def test_switching_contacts_targets_actions_and_reports(self):
        self.app.go("diplomacy")
        self.click("contact_next")
        self.assertEqual(self.app.selected_rival_id(), "rival_2")
        self.click("diplomacy_gift")
        self.assertEqual((self.app.game.opponent.credits, self.app.game._empire("rival_2").credits), (120, 170))
        self.click("diplomacy_intelligence")
        self.assertEqual(self.app.selected_rival_id(), "rival_2")
        self.click("contact_next")
        self.assertEqual(self.app.selected_rival_id(), "rival_3")
        self.click("contact_next")
        self.assertEqual(self.app.selected_rival_id(), RIVAL)
        self.click("contact_previous")
        self.assertEqual(self.app.selected_rival_id(), "rival_3")
        saved, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(saved, self.app.game)

    def test_system_target_selector_engages_only_selected_empire(self):
        game = self.app.game
        game.ships.clear()
        for owner in (PLAYER, RIVAL, "rival_2"):
            add_ships(game, 0, owner, ["frigate"])
        self.app.go("system")
        self.click("system_target_next")
        self.assertEqual(self.app.selected_rival_id(), "rival_2")
        self.click("system_engage")
        self.click("dialog_ok")
        self.assertEqual(self.app.screen, "combat")
        self.assertEqual(game.combat.sides, (PLAYER, "rival_2"))


if __name__ == "__main__":
    unittest.main()
