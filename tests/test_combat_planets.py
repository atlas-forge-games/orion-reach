"""Planetary selection, surface weapon effects, losses and save continuity."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import combat_planets, defenses, first_contact
from orion.app import App
from orion.combat_view import cell_center
from orion.model import GameState, PLAYER, RIVAL
from tools.preview_planetary_combat import scenario


class PlanetaryCombatTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True)
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.use_scenario()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def use_scenario(self, **kwargs):
        self.game, self.earth, self.mars = scenario(**kwargs)
        for owner in first_contact.pending(self.game):
            first_contact.acknowledge(self.game, owner)
        self.app.game = self.game
        self.app.reset_combat_view()
        self.app.go("combat")
        self.own_base = self.game.combat.ship(defenses.base_id(0, self.earth.id))
        self.enemy_base = self.game.combat.ship(defenses.base_id(0, self.mars.id))
        self.app.select_combat_ship(PLAYER, self.own_base.id)
        self.app.select_combat_ship(RIVAL, self.enemy_base.id)
        self.app.render()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled)
        x, y = button.rect.center
        viewport = self.app.viewport
        pos = (round(viewport.x+x*viewport.w/1440), round(viewport.y+y*viewport.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def tick(self, seconds=2):
        self.app.time += seconds
        self.app.update_combat()

    def test_multiple_worlds_use_the_correct_planets_and_are_selectable_without_moving(self):
        self.use_scenario(extra_world=True)
        before = self.game.to_dict()
        bases = [s for s in self.game.combat.ships if s.kind == "missile_base"]
        self.assertEqual(len(bases), 3)
        for base in bases:
            with self.subTest(base=base.id):
                planet = defenses.base_planet(self.game, base.id)
                self.click(f"combat_ship_{base.id}")
                selected = self.app.combat_ship_id if base.owner == PLAYER else self.app.combat_target_id
                self.assertEqual(selected, base.id)
                self.assertIs(combat_planets.planet_for(self.game, base), planet)
                self.assertIn(planet.name, combat_planets.unit_name(self.game, base))
                self.assertFalse(self.game.combat.can_move(base))
                self.assertFalse(any(b.key.startswith("combat_cell_") for b in self.app.buttons))
        self.assertEqual(self.game.to_dict(), before)
        self.assertEqual(GameState.from_dict(before).to_dict(), before)

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_both_sides_fire_from_surface_launchers_and_hit_the_other_battery(self):
        self.click("combat_fire")
        for owner, attacker, target in ((PLAYER, self.own_base, self.enemy_base),
                                        (RIVAL, self.enemy_base, self.own_base)):
            with self.subTest(owner=owner):
                if owner == RIVAL:
                    self.tick()
                    self.game.combat_end_turn()
                    damage = self.game.combat_fire(attacker.id, target.id, RIVAL)
                    self.app.after_combat_action({"kind": "fire", "ship_id": attacker.id,
                                                  "target_id": target.id, "damage": damage})
                effect = self.app.combat_animation
                self.assertEqual(effect.kind, "launch_projectile")
                with patch.object(effect, "draw", wraps=effect.draw) as draw:
                    self.app.render()
                arguments = draw.call_args.kwargs
                for key, unit in (("origin", attacker), ("target", target)):
                    center = cell_center(unit.position, self.app.combat_camera_row)
                    self.assertEqual(arguments[key], combat_planets.surface_anchor(center, 1 if unit.owner == PLAYER else -1))
                    self.assertNotEqual(arguments[key], center)
                    button = next(b for b in self.app.buttons if b.key == f"combat_ship_{unit.id}")
                    self.assertTrue(button.rect.collidepoint(arguments[key]))
                self.assertEqual(arguments["explosion_scale"], .35)
                self.assertEqual(target.hull, 40)
        for _ in range(4):
            owner = self.game.combat.active_owner
            flights = self.game.combat_end_turn(owner)
            self.app.after_combat_action({"kind": "end_turn", "flights": flights})
        self.assertEqual((self.own_base.hull, self.enemy_base.hull), (30, 30))

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_destroying_a_base_leaves_its_world_and_colony_intact(self):
        self.use_scenario(enemy_ships=False, damaged_base=True)
        population, owner = self.mars.population, self.mars.owner
        self.click("combat_fire")
        self.assertEqual(self.game.combat.status, "active")
        for _ in range(4):
            flights = self.game.combat_end_turn(self.game.combat.active_owner)
        self.app.after_combat_action({"kind": "end_turn", "flights": flights})
        self.assertEqual(self.game.combat.status, "player_victory")
        with patch("orion.combat_planets.draw_base", wraps=combat_planets.draw_base) as draw:
            self.app.render()
            target_call = next(call for call in draw.call_args_list if call.args[2].id == self.enemy_base.id)
            self.assertFalse(target_call.kwargs["destroyed"])
        self.tick(.45)
        with patch("orion.combat_planets.draw_base", wraps=combat_planets.draw_base) as draw:
            self.app.render()
            target_call = next(call for call in draw.call_args_list if call.args[2].id == self.enemy_base.id)
            self.assertTrue(target_call.kwargs["destroyed"])
        self.tick()
        from orion.combat_view import text
        with patch("orion.combat_view.text", wraps=text) as labels:
            self.app.render()
        messages = [call.args[1] for call in labels.call_args_list]
        self.assertIn("Enemy ships lost: 0", messages)
        self.assertIn("Missile bases lost: 0 yours · 1 enemy", messages)
        self.assertIn(self.mars.name, messages)
        self.assertNotIn(f"combat_ship_{self.enemy_base.id}", [b.key for b in self.app.buttons])
        self.assertNotIn("missile_base", self.mars.buildings)
        self.assertEqual((self.mars.population, self.mars.owner, self.mars.colonized), (population, owner, True))
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_existing_battle_save_load_retains_worlds_positions_damage_and_manual_control(self):
        self.click("combat_fire")
        before = self.game.to_dict()
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(self.app.screen, "combat")
        self.assertIsNone(self.app.combat_animation)
        self.assertFalse(self.app.combat_auto)
        for unit in self.app.game.combat.ships:
            if unit.kind == "missile_base":
                self.assertEqual(combat_planets.planet_for(self.app.game, unit).name,
                                 defenses.base_planet(self.game, unit.id).name)
        self.app.render()
        self.assertEqual(self.app.game.to_dict(), before)

    def test_auto_combat_commands_surface_batteries(self):
        self.click("combat_auto")
        for _ in range(150):
            self.tick()
            effect = self.app.combat_animation
            if effect and effect.kind == "launch_projectile" and effect.ship_id == self.own_base.id:
                break
        else:
            self.fail("Automatic fleet control did not fire its planetary battery")
        self.app.render()
        self.assertEqual(self.app.combat_ship_id, self.own_base.id)
        self.assertEqual(self.own_base.position, (8, 6))
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], self.game)


if __name__ == "__main__":
    unittest.main()
