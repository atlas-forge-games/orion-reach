from scenarios import legacy_research_payload
from scenarios import legacy_economy
"""Guardian generation, encounters, rewards, private knowledge and save continuity."""

import copy
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion import ai, combat, exploration, monsters
from orion.buildings import BUILDINGS
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import fixed_start_game as new_game
from orion.production import distance_ly
from orion.storage import Storage
from scenarios import place_near


def fleet(game, sid, kinds, owner=PLAYER):
    rows = [Ship(game.next_ship_id+i, kind, sid, owner=owner) for i, kind in enumerate(kinds)]
    game.next_ship_id += len(rows)
    game.ships.extend(rows)
    return rows


def encounter(kind="space_serpent", kinds=("frigate",)*3, owner=PLAYER, *, start=True, solo=False):
    game = new_game(seed=2408, with_ai=not solo)
    guardian = next(g for g in game.guardians if g.kind == kind)
    game.ships.clear()
    ships = fleet(game, guardian.system_id, kinds, owner)
    exploration.refresh(game)
    if start:
        game.start_combat(guardian.system_id, owner)
    return game, guardian, ships


def fight(game, limit=1500):
    events = []
    for _ in range(limit):
        if game.combat.status != "active":
            return events
        events.append(combat.ai_action(game, game.combat.active_owner))
    raise AssertionError("Battle did not resolve")


class GuardianRulesTests(unittest.TestCase):
    def test_generation_is_rare_deterministic_and_away_from_both_homes(self):
        for size, count in (("Compact", 2), ("Standard", 4), ("Expansive", 4)):
            for seed in (0, 1, 42, 2408, 99999):
                game = new_game(seed=seed, galaxy_size=size)
                revealed = new_game(seed=seed, galaxy_size=size, fog_of_war=False)
                original = new_game(seed=seed, galaxy_size=size, with_guardians=False)
                self.assertEqual(game.guardians, revealed.guardians)
                self.assertEqual(len(game.guardians), count)
                self.assertEqual(len({g.kind for g in game.guardians}), count)
                if size != "Compact":
                    self.assertEqual({g.kind for g in game.guardians}, set(monsters.PRIZE_WORLDS))
                homes = [game.systems[0], game.systems[game.opponent.home_system]]
                prizes = {(g.system_id, pid) for g in game.guardians
                          for pid in monsters.prize_ids(game.systems[g.system_id], g)}
                for g in game.guardians:
                    self.assertGreaterEqual(min(distance_ly(game.systems[g.system_id], s) for s in homes), 28)
                    self.assertFalse(any(p.colonized for p in game.systems[g.system_id].worlds))
                for system in game.systems:
                    for p in system.worlds:
                        if (system.id, p.id) not in prizes:
                            self.assertEqual(p, original.planet_at(system.id, p.id))
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_solo_game_can_add_rival_without_placing_it_in_guarded_system(self):
        game = new_game(seed=2408, with_ai=False)
        original = copy.deepcopy(game.guardians)
        game.add_opponent()
        self.assertNotIn(game.opponent.home_system, [g.system_id for g in game.guardians])
        self.assertEqual(game.guardians, original)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_prize_worlds_have_real_economic_benefits(self):
        game = new_game(seed=2408)
        for g in game.guardians:
            p = game.planet_at(g.system_id, g.planet_id)
            p.colonized, p.owner, p.population = True, PLAYER, 1
            if g.kind == "space_serpent":
                food = game.population_report(p)
                self.assertEqual((p.size, p.population_capacity, food.produced, food.growth_rate, food.turns_to_growth),
                                 ("Huge", 28, 12, 35, 3))
                p.farmers = 1
                self.assertEqual(game.population_report(p).produced, 15)
            elif g.kind == "crystal_guardian":
                self.assertEqual(p.richness, "Ultra-rich")
                self.assertEqual(BUILDINGS["mine"].resources*3, 6)
        self.assertEqual(BUILDINGS["mine"].yields(p.richness)[0], 0)

    def test_arrival_starts_battle_and_scout_can_retreat_before_being_hit(self):
        game = new_game(seed=2408, with_ai=False)
        guardian = game.guardians[0]
        place_near(game, guardian.system_id, distance=6)
        duration = game.send_ship(1, guardian.system_id)
        for _ in range(duration-1):
            game.advance_turn()
            self.assertIsNone(game.combat)
        game.advance_turn()
        self.assertEqual(game.combat.active_owner, PLAYER)
        self.assertEqual(game.combat.guardian.kind, guardian.kind)
        self.assertEqual(game.ship_at(1).hull, 8)
        self.assertNotIn(guardian.system_id, game.exploration.scanned_player)
        game.combat_retreat()
        self.assertEqual(game.combat.status, "player_retreat")
        self.assertEqual(game.ship_at(1).hull, 8)
        self.assertTrue(game.ship_at(1).in_transit)
        self.assertFalse(game.ship_at(1).departure_pending)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_guardian_intercepts_pending_departure_before_time_advances(self):
        game, guardian, ships = encounter(kinds=("scout",), start=False, solo=True)
        game.send_ship(ships[0].id, 0)
        before = game.turn, game.credits
        game.advance_turn()
        self.assertEqual((game.turn, game.credits), before)
        self.assertIsNotNone(game.combat)
        self.assertFalse(ships[0].has_course)

    def test_all_worlds_are_blocked_until_guardian_dies_for_both_empires(self):
        for owner in (PLAYER, RIVAL):
            game, guardian, ships = encounter(kinds=("frigate",)*5+("colony_ship",), owner=owner, start=False)
            for p in game.systems[guardian.system_id].worlds:
                self.assertIn("Space Serpent", game.colonize_error(guardian.system_id, p.id, owner=owner))
            before = asdict(game.diplomacy)
            game.start_combat(guardian.system_id, owner)
            with self.assertRaises(RuleError):
                game.colonize(ships[-1].id, guardian.system_id, guardian.planet_id, owner=owner)
            fight(game)
            self.assertEqual(game.combat.status, owner+"_victory")
            self.assertEqual(asdict(game.diplomacy), before)
            self.assertFalse(guardian.alive)
            game.finish_combat()
            game.colonize(ships[-1].id, guardian.system_id, guardian.planet_id, owner=owner)
            self.assertEqual(game.planet_at(guardian.system_id, guardian.planet_id).owner, owner)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)
            self.assertFalse(monsters.intercept(game))

    def test_all_guardians_fire_and_can_be_destroyed_by_frigates(self):
        for kind, count in (("space_serpent", 3), ("crystal_guardian", 5), ("ancient_sentinel", 6), ("void_leviathan", 9)):
            game, guardian, _ = encounter(kind, ("frigate",)*count, solo=True)
            events = fight(game)
            self.assertEqual(game.combat.status, "player_victory")
            if kind == "space_serpent":
                self.assertTrue(any(e["kind"] == "move" and e["ship_id"] == guardian.combat_id for e in events))
            self.assertTrue(any(e["kind"] == "fire" and e["ship_id"] == guardian.combat_id for e in events))
            self.assertEqual(guardian.hull, 0)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_monster_victory_commits_losses_and_preserves_guardian(self):
        game, guardian, ships = encounter(kinds=("frigate",), solo=True)
        fight(game)
        self.assertEqual(game.combat.status, "monster_victory")
        self.assertNotIn(ships[0], game.ships)
        self.assertGreater(guardian.hull, 0)
        self.assertLess(guardian.hull, guardian.spec.hull)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_damage_survives_retreat_reload_and_next_encounter(self):
        game, guardian, ships = encounter(solo=True)
        game.combat_move(ships[0].id, 7, 4)
        game.combat_fire(ships[0].id, guardian.combat_id)
        self.assertEqual(guardian.hull, guardian.spec.hull)  # Campaign snapshot until resolution.
        game = GameState.from_dict(game.to_dict())
        game.combat_retreat()
        expected = guardian.spec.hull-5
        guardian = monsters.at(game, guardian.system_id)
        self.assertEqual(guardian.hull, expected)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.finish_combat()
        for s in game.ships:
            game._clear_course(s)
        game.start_combat(guardian.system_id)
        self.assertEqual(game.combat.guardian.hull, expected)

    def test_guardian_battles_do_not_break_treaties_or_involve_third_empire(self):
        game, guardian, _ = encounter(start=False)
        game.diplomacy.relations = 80
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        other = fleet(game, guardian.system_id, ("scout",), RIVAL)[0]
        from orion.first_contact import establish
        establish(game, PLAYER, RIVAL)
        original = asdict(game.diplomacy)
        game.start_combat(guardian.system_id)
        self.assertEqual(game.combat.sides, (PLAYER, monsters.MONSTER))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        fight(game)
        self.assertEqual(asdict(game.diplomacy), original)
        self.assertEqual(other.hull, 8)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_hidden_guards_and_hidden_defeats_do_not_leak_through_fog(self):
        game, guardian, own = encounter(kinds=("scout",), start=False)
        unexplored = next(g for g in game.guardians if g.system_id != guardian.system_id)
        self.assertIsNone(monsters.known_status(game, unexplored.system_id))
        self.assertEqual(monsters.known_status(game, guardian.system_id), "alive")
        own[0].system_id = 0
        fleet(game, guardian.system_id, ("frigate",)*5, RIVAL)
        monsters.intercept(game)
        self.assertIsNone(game.combat)
        self.assertFalse(guardian.alive)
        self.assertEqual(monsters.known_status(game, guardian.system_id), "alive")
        self.assertEqual(monsters.known_status(game, guardian.system_id, RIVAL), "defeated")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        own[0].system_id = guardian.system_id
        exploration.refresh(game)
        self.assertEqual(monsters.known_status(game, guardian.system_id), "defeated")
        game.fog_of_war = False
        self.assertEqual(monsters.known_status(game, unexplored.system_id), "alive")

    def test_ai_scout_retreats_and_does_not_repeat_a_known_dangerous_route(self):
        game, guardian, ships = encounter(kinds=("scout",), owner=RIVAL, start=False)
        self.assertFalse(monsters.intercept(game))
        self.assertIsNone(game.combat)
        self.assertTrue(ships[0].in_transit)
        self.assertEqual(ships[0].hull, 8)
        self.assertEqual(ai.available_worlds(game, game.systems[guardian.system_id]), [])
        ships[0].system_id = game.opponent.home_system
        game._clear_course(ships[0])
        ai.scouting_orders(game)
        self.assertNotEqual(ships[0].destination, guardian.system_id)

    def test_ai_gathers_frigates_and_attacks_when_ready(self):
        game = new_game(seed=2408)
        guardian = next(g for g in game.guardians if g.kind == "crystal_guardian")
        guardian.known_rival = "alive"
        home = game.opponent.home_system
        place_near(game, guardian.system_id, anchor=home, distance=6)
        game.ships.clear()
        ships = fleet(game, home, ("frigate",)*4, RIVAL)
        reserved = monsters.ai_orders(game)
        ai.military_orders(game, reserved)
        self.assertTrue(all(not s.has_course for s in ships))
        ships += fleet(game, home, ("frigate",), RIVAL)
        reserved = monsters.ai_orders(game)
        ai.military_orders(game, reserved)
        self.assertTrue(all(s.destination == guardian.system_id for s in ships))
        self.assertEqual(reserved, {s.id for s in ships})

    def test_guardians_do_not_count_as_empires_for_conquest(self):
        game = new_game(seed=2408)
        for s in game.systems:
            for p in s.worlds:
                if p.owner == RIVAL:
                    p.owner = PLAYER
        self.assertTrue(all(g.alive for g in game.guardians))
        self.assertEqual(game.check_victory().winner, PLAYER)


class GuardianExpansionTests(unittest.TestCase):
    def test_sentinel_ruins_pay_the_victor_once_including_after_reload(self):
        for owner in (PLAYER, RIVAL):
            game, guardian, _ = encounter("ancient_sentinel", ("frigate",)*6, owner)
            before = {o: game.research_for(o) for o in (PLAYER, RIVAL)}
            technology = copy.deepcopy(game.research_state(owner))
            fight(game)
            self.assertEqual(game.combat.status, owner+"_victory")
            self.assertEqual(game.research_for(owner), before[owner]+120)
            self.assertEqual(game.research_state(owner), technology)
            other = RIVAL if owner == PLAYER else PLAYER
            self.assertEqual(game.research_for(other), before[other])
            self.assertTrue(any("+120 RP" in line for line in game.combat.log))
            with tempfile.TemporaryDirectory() as folder:
                store = Storage(folder)
                restored, _ = store.load(store.save(game))
            self.assertEqual(restored, game)
            restored.finish_combat()
            monsters.intercept(restored)
            self.assertIsNone(restored.combat)
            self.assertEqual(restored.research_for(owner), before[owner]+120)
            colony = fleet(restored, guardian.system_id, ("colony_ship",), owner)[0]
            restored.colonize(colony.id, guardian.system_id, guardian.planet_id, owner=owner)
            self.assertEqual(restored.research_for(owner), before[owner]+120)
            self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_sentinel_does_not_award_research_for_retreat_or_defeat(self):
        for kinds, result in ((("scout",), "player_retreat"), (("frigate",), "monster_victory")):
            game, guardian, _ = encounter("ancient_sentinel", kinds, solo=True)
            original = game.research
            fight(game)
            self.assertEqual(game.combat.status, result)
            self.assertEqual(game.research, original)
            self.assertTrue(guardian.alive)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_leviathan_protects_three_distinct_worlds_that_can_all_be_settled(self):
        game, guardian, ships = encounter("void_leviathan", ("frigate",)*9+("colony_ship",)*3, start=False)
        system = game.systems[guardian.system_id]
        ids = monsters.prize_ids(system, guardian)
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual([(system.worlds[i].biome, system.worlds[i].size, system.worlds[i].richness) for i in ids],
                         [("Gaia", "Huge", "Rich"), ("Terran", "Large", "Ultra-rich"), ("Ocean", "Large", "Rich")])
        for planet in system.worlds:
            self.assertIn("Void Leviathan", game.colonize_error(system.id, planet.id))
        game.start_combat(system.id)
        fight(game)
        self.assertEqual(game.combat.status, "player_victory")
        game.finish_combat()
        for ship, pid in zip(ships[-3:], ids):
            self.assertIsNone(game.colonize_error(system.id, pid))
            game.colonize(ship.id, system.id, pid)
            self.assertEqual(system.worlds[pid].owner, PLAYER)
        self.assertEqual([system.worlds[i].population_capacity for i in ids], [28, 20, 20])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_both_new_guardians_intercept_scouts_and_allow_retreat_for_either_empire(self):
        for kind in ("ancient_sentinel", "void_leviathan"):
            for owner in (PLAYER, RIVAL):
                game, guardian, ships = encounter(kind, ("scout",), owner, start=False)
                intercepted = monsters.intercept(game)
                self.assertEqual(intercepted, owner == PLAYER)
                if owner == PLAYER:
                    self.assertEqual(game.combat.active_owner, PLAYER)
                    game.combat_retreat()
                else:
                    self.assertIsNone(game.combat)
                self.assertTrue(ships[0].in_transit)
                self.assertEqual(ships[0].hull, 8)
                self.assertEqual(guardian.hull, guardian.spec.hull)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_waits_for_six_or_nine_frigates_before_ordering_attack(self):
        for kind, count in (("ancient_sentinel", 6), ("void_leviathan", 9)):
            game = new_game(seed=2408)
            guardian = next(g for g in game.guardians if g.kind == kind)
            guardian.known_rival = "alive"
            home = game.opponent.home_system
            place_near(game, guardian.system_id, anchor=home, distance=6)
            game.ships.clear()
            ships = fleet(game, home, ("frigate",)*(count-1), RIVAL)
            ai.military_orders(game, monsters.ai_orders(game))
            self.assertTrue(all(not s.has_course for s in ships))
            ships += fleet(game, home, ("frigate",), RIVAL)
            ai.military_orders(game, monsters.ai_orders(game))
            self.assertTrue(all(s.destination == guardian.system_id for s in ships))

    def test_secondary_leviathan_prizes_are_validated_in_saves(self):
        game = new_game(seed=2408)
        guardian = next(g for g in game.guardians if g.kind == "void_leviathan")
        for pid in monsters.prize_ids(game.systems[guardian.system_id], guardian)[1:]:
            data = game.to_dict()
            data["systems"][guardian.system_id]["worlds"][pid]["richness"] = "Poor"
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class GuardianSaveTests(unittest.TestCase):
    def test_active_battle_roundtrips_after_each_action_and_resumes_identically(self):
        game, _, _ = encounter("crystal_guardian", ("frigate",)*5)
        restored = GameState.from_dict(game.to_dict())
        for _ in range(400):
            self.assertEqual(restored, game)
            if game.combat.status != "active":
                break
            action = game.combat.active_owner
            self.assertEqual(combat.ai_action(game, action), combat.ai_action(restored, action))
            restored = GameState.from_dict(restored.to_dict())
        self.assertEqual(game.combat.status, "player_victory")

    def test_new_guardian_battles_resume_after_mid_battle_save_without_extra_loot(self):
        for kind, count in (("ancient_sentinel", 6), ("void_leviathan", 9)):
            game, guardian, _ = encounter(kind, ("frigate",)*count)
            game.combat_move(game.combat.fleet(PLAYER)[0].id, 7, 4)
            game.combat_fire(game.combat.fleet(PLAYER)[0].id, guardian.combat_id)
            game.combat_end_turn()
            restored = GameState.from_dict(game.to_dict())
            self.assertEqual(fight(restored), fight(game))
            self.assertEqual(restored, game)
            self.assertEqual(restored.research, guardian.spec.research_reward)
            self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_v16_guardians_remain_unchanged_when_loaded(self):
        from scenarios import migrated_statistics
        game, _, _ = encounter()
        game.guardians = [g for g in game.guardians if g.kind in ("space_serpent", "crystal_guardian")]
        original = game.to_dict()
        legacy = game.to_dict()
        for ship in legacy["combat"]["ships"]:
            ship.pop("design")
            ship.pop("shields")
        expected = copy.deepcopy(game)
        for owner in expected.owners:
            expected.research_state(owner).legacy_starships = True
            expected.research_state(owner).legacy_arsenal = True
            expected.research_state(owner).legacy_fuel = True
            expected.research_state(owner).legacy_black_holes = True
        expected.combat.accuracy = False
        expected.combat.shots_fired = 0
        self.assertEqual(GameState.from_dict(legacy_research_payload(legacy), version=16), migrated_statistics(expected))
        self.assertEqual(game.to_dict(), original)

    def test_v15_load_does_not_add_guardians_or_change_worlds_and_orders(self):
        from scenarios import migrated_statistics
        game = new_game(seed=2408, with_guardians=False)
        place_near(game, 1)
        game.send_ship(1, 1)
        legacy_economy(game)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 15
            legacy_research_payload(payload)
            payload["game"].pop("guardians")
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            restored, _ = storage.load(path)
            self.assertEqual(restored, migrated_statistics(game))
            self.assertEqual(restored.guardians, [])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(storage.load(storage.save(restored))[0], restored)

    def test_guardian_record_validation_rejects_bad_ids_health_and_prizes(self):
        game = new_game(seed=2408)
        for mutation in (lambda r: r.update(system_id=0), lambda r: r.update(system_id=True),
                         lambda r: r.update(system_id=len(game.systems)), lambda r: r.update(planet_id=99),
                         lambda r: r.update(kind="frigate"), lambda r: r.update(kind=[]),
                         lambda r: r.update(hull=-1), lambda r: r.update(hull=500), lambda r: r.update(hull=True),
                         lambda r: r.update(known_player="defeated"), lambda r: r.update(known_rival="secret")):
            data = game.to_dict()
            mutation(data["guardians"][0])
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        data = game.to_dict()
        data["guardians"].append(copy.deepcopy(data["guardians"][0]))
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        data = game.to_dict()
        g = game.guardians[0]
        data["systems"][g.system_id]["worlds"][g.planet_id]["biome"] = "Terran"
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_battle_validation_rejects_forged_monster_identity_and_results(self):
        game, guardian, _ = encounter()
        for mutation in (lambda d: d["combat"]["ships"][-1].update(id=-999),
                         lambda d: d["combat"]["ships"][-1].update(owner=RIVAL),
                         lambda d: d["combat"]["ships"][-1].update(weapon="laser"),
                         lambda d: d["combat"]["ships"][-1].update(kind="crystal_guardian"),
                         lambda d: next(g for g in d["guardians"] if g["system_id"] == guardian.system_id).update(hull=guardian.hull-1),
                         lambda d: d["combat"].update(status="monster_victory", active_owner=None),
                         lambda d: d.update(guardians=[])):
            data = game.to_dict()
            mutation(data)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class GuardianUITests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True, skip_intro=True)

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def click(self, key):
        app = self.app
        app.render()
        app.present()
        button = next(b for b in app.buttons if b.key == key)
        x, y = button.rect.center
        v = app.viewport
        position = round(v.x+x*v.w/1440), round(v.y+y*v.h/900)
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            app.handle_event(pg.event.Event(event, button=1, pos=position))
            app.render()

    def test_galaxy_symbols_have_distinct_silhouettes_not_just_colours(self):
        from orion.monster_art import draw_guardian_symbol
        shapes = []
        for kind in monsters.MONSTERS:
            surface = pg.Surface((32, 32), pg.SRCALPHA)
            draw_guardian_symbol(surface, (16, 16), kind, 20)
            mask = pg.mask.from_surface(surface)
            self.assertGreater(mask.count(), 30)
            shapes.append(pg.image.tobytes(mask.to_surface(), "RGB"))
        self.assertEqual(len(set(shapes)), 4)

    def test_symbols_select_systems_and_accept_fleet_destinations(self):
        app = self.app
        app.game = new_game(seed=2408, fog_of_war=False)
        guardian = next(g for g in app.game.guardians if g.kind == "ancient_sentinel")
        place_near(app.game, guardian.system_id, distance=6)
        app.go("galaxy")
        app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.click(f"guardian_{guardian.system_id}")
        self.assertEqual(app.game.selected_system, guardian.system_id)
        self.assertEqual(app.screen, "galaxy")
        self.click("map_fleet_1")
        app.mouse = next(b.rect.center for b in app.buttons if b.key == f"guardian_{guardian.system_id}")
        app.keyboard_mode = False
        self.assertEqual(app.fleet_route_target(), guardian.system_id)
        self.click(f"guardian_{guardian.system_id}")
        self.assertTrue(all(s.departure_pending and s.destination == guardian.system_id for s in app.game.ships_owned_by()))
        self.click("star_0")
        self.assertTrue(all(not s.has_course for s in app.game.ships_owned_by()))

    def test_fleet_badges_do_not_cover_guardian_symbols_or_the_legend(self):
        from orion.app import MAP
        from orion.galaxy_fleet_view import fleet_markers, guardian_markers, guardian_legend_rect, known_guardian_kinds
        app = self.app
        app.game = new_game(seed=2408, galaxy_size="Expansive", fog_of_war=False)
        for guardian in app.game.guardians:
            for owner in (PLAYER, RIVAL):
                fleet(app.game, guardian.system_id, ("scout", "frigate"), owner)
        app.go("galaxy")
        app.render()
        self.assertEqual(set(known_guardian_kinds(app.game)), set(monsters.PRIZE_WORLDS))
        symbols = [rect for _, rect, _ in guardian_markers(app, MAP)]
        self.assertEqual(len(symbols), 4)
        for index, rect in enumerate(symbols):
            self.assertTrue(MAP.contains(rect))
            self.assertEqual(rect.collidelist(symbols[:index]), -1)
        for _, rect, _ in fleet_markers(app, MAP):
            self.assertEqual(rect.collidelist(symbols+[guardian_legend_rect(MAP)]), -1)

    def test_symbols_and_legend_respect_fog_and_stale_guardian_knowledge(self):
        from orion.galaxy_fleet_view import known_guardian_kinds
        app = self.app
        app.game = new_game(seed=2408)
        app.go("galaxy")
        app.render()
        self.assertEqual(known_guardian_kinds(app.game), [])
        self.assertFalse(any(b.key.startswith("guardian_") for b in app.buttons))
        guardian = next(g for g in app.game.guardians if g.kind == "void_leviathan")
        scout = app.game.ship_at(1)
        scout.system_id = guardian.system_id
        exploration.refresh(app.game)
        app.render()
        self.assertEqual(known_guardian_kinds(app.game), [guardian.kind])
        self.assertEqual([b.key for b in app.buttons if b.key.startswith("guardian_")], [f"guardian_{guardian.system_id}"])
        scout.system_id = 0
        guardian.hull = 0  # A defeat out of sight must not remove the last-known warning.
        app.render()
        self.assertTrue(any(b.key == f"guardian_{guardian.system_id}" for b in app.buttons))
        scout.system_id = guardian.system_id
        exploration.refresh(app.game)
        app.render()
        self.assertFalse(any(b.key.startswith("guardian_") for b in app.buttons))

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_new_guardian_weapons_animate_and_destroy_ships_in_the_ui(self):
        app = self.app
        for kind in ("ancient_sentinel", "void_leviathan"):
            app.game, guardian, ships = encounter(kind, ("frigate",)*3, start=False)
            ships[0].hull = 8
            app.game.start_combat(guardian.system_id)
            app.reset_combat_view()
            app.go("combat")
            app.game.combat_move(ships[0].id, 7, 4)
            app.game.combat_end_turn()
            for _ in range(12):
                app.time += 2
                app.update_combat()
                if app.combat_animation and app.combat_animation.kind == "fire":
                    break
            self.assertIsNotNone(app.combat_animation)
            self.assertEqual(app.combat_animation.weapon, guardian.spec.weapon)
            self.assertTrue(app.combat_animation.destroyed)
            app.combat_animation.elapsed = .3
            app.render()
            self.assertEqual(GameState.from_dict(app.game.to_dict()), app.game)

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_player_can_click_monster_to_fire_and_destruction_animates(self):
        app = self.app
        app.game, guardian, ships = encounter(kinds=("frigate",), solo=True)
        # A previously damaged guardian can be finished by one legal shot.
        guardian.hull = app.game.combat.guardian.initial_hull = app.game.combat.guardian.hull = 5
        app.game.combat_move(ships[0].id, 7, 4)
        app.go("combat")
        app.render()
        target = next(b for b in app.buttons if b.key == f"combat_ship_{guardian.combat_id}")
        target.action()
        app.combat_action("fire")
        self.assertEqual(app.game.combat.status, "player_victory")
        self.assertTrue(app.combat_animation.destroyed)
        self.assertEqual(app.combat_animation.target_id, guardian.combat_id)
        app.combat_animation.elapsed = .3
        app.render()
        app.combat_animation = None
        app.render()
        app.finish_combat()
        self.assertEqual(app.screen, "system")
        app.render()
        app.open_planet(guardian.planet_id)
        app.render()

    def test_monster_ai_advances_and_uses_its_coloured_beam(self):
        app = self.app
        app.game, guardian, _ = encounter("crystal_guardian", ("frigate",)*3)
        app.go("combat")
        app.game.combat_move(app.game.combat.fleet(PLAYER)[0].id, 7, 4)
        app.game.combat_end_turn()
        app.time = 10
        app.update_combat()
        self.assertIsNotNone(app.combat_animation)
        self.assertEqual(app.combat_animation.ship_id, guardian.combat_id)
        self.assertEqual(app.combat_animation.kind, "fire")
        self.assertEqual(app.combat_animation.weapon, "crystal_ray")
        app.combat_animation.elapsed = .2
        app.render()
        for _ in range(6):
            app.time += 2
            app.update_combat()
        self.assertEqual(app.game.combat.active_owner, PLAYER)

    def test_known_guardian_and_prize_screens_render_without_revealing_unknowns(self):
        app = self.app
        app.game = new_game(seed=2408)
        for g in app.game.guardians[:2]:
            app.game.selected_system = g.system_id
            app.go("galaxy")
            app.render()
            self.assertIsNone(monsters.known_status(app.game, g.system_id))
            app.game.fog_of_war = False
            app.render()
            app.open_system(g.system_id)
            app.render()
            app.open_planet(g.planet_id)
            app.render()
            self.assertFalse(next(b for b in app.buttons if b.key == "colonize_planet").enabled)
            app.game.fog_of_war = True


if __name__ == "__main__":
    unittest.main()
