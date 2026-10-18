"""Arsenal research, tactical counters, finite support, AI equipment and v30 saves."""

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
from orion import ai, combat, defenses
from orion.app import App
from orion.auto_designs import auto_design
from orion.combat_effects import CombatAnimation
from orion.designs import ARSENAL_TECHNOLOGIES, HULLS, MODULES, ShipDesign, loadout_error
from orion.model import GameState, RuleError, SaveError, Ship
from orion.research import BRANCHES, TECHNOLOGIES, choices, branch_tiers
from orion.storage import Storage, SAVE_VERSION
from orion.weapons import BEAMS
from scenarios import empty_fleet_game


def campaign():
    game = empty_fleet_game(seed=2408, fog_of_war=False)
    game.resources = game.credits = 100000
    game.opponent.resources = game.opponent.credits = 100000
    return game


def discover(game, identifiers, owner="player"):
    """Exercise real sequential research, selecting the requested alternatives."""
    picks = {(TECHNOLOGIES[t].branch, TECHNOLOGIES[t].tier): t for t in identifiers}
    state = game.research_state(owner)
    for branch in BRANCHES:
        last = max((tier for b, tier in picks if b == branch), default=0)
        for tier in range(1, last+1):
            identifier = picks.get((branch, tier), choices(branch, tier)[0].id)
            if tier in state.completed_tiers(branch):
                if (branch, tier) in picks and identifier not in state.completed:
                    raise AssertionError("Test requested mutually exclusive discoveries")
                continue
            game._empire(owner).research += TECHNOLOGIES[identifier].cost
            game.choose_research(identifier, owner=owner)


def equip(game, modules, *, owner="player", kind="battleship", identifier="design_1", fit_version=2):
    technologies = [MODULES[m].technology for m in modules if MODULES[m].technology]
    technologies += [{"frigate": "modular_spaceframes", "destroyer": "destroyer_hulls",
                      "cruiser": "cruiser_hulls", "battleship": "battleship_hulls",
                      "carrier": "drone_carriers", "titan": "titan_hulls"}[kind]]
    discover(game, technologies, owner)
    error = loadout_error(kind, modules, game.research_state(owner).completed, fit_version=fit_version)
    assert error is None, error
    design = ShipDesign(identifier, "Test "+kind, kind, tuple(modules), fit_version=fit_version)
    if owner == "player":
        game.designs.append(design)
    return design


def duel(weapons, defense=("laser",), *, kind="battleship", enemy_kind="titan", fit_version=1):
    game = campaign()
    # Base-effect regressions retain legacy fits; v0.53 tests exercise scaled fits.
    left = equip(game, weapons, kind=kind, fit_version=fit_version)
    right = equip(game, defense, owner="rival", kind=enemy_kind, fit_version=fit_version)
    game.ships = [Ship(1, kind, 0, design=left), Ship(2, enemy_kind, 0, owner="rival", design=right)]
    game.next_ship_id = 3
    game.start_combat(0)
    game.combat.ship(1).x, game.combat.ship(1).y = 5, 4
    game.combat.ship(2).x, game.combat.ship(2).y = 8, 4
    game.combat.accuracy = False
    return game


def round_trip(game):
    return GameState.from_dict(game.to_dict())


def cycle(game):
    game.combat_end_turn("player")
    game.combat_end_turn("rival")


class ArsenalResearchTests(unittest.TestCase):
    def setUp(self):
        from orion import balance
        previous = balance.active_profile()
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(previous))

    def test_all_new_equipment_has_research_gates_and_can_be_built(self):
        self.assertEqual(len(ARSENAL_TECHNOLOGIES), 18)
        for name, module in MODULES.items():
            if module.technology not in ARSENAL_TECHNOLOGIES:
                continue
            with self.subTest(module=name):
                game = campaign()
                kind = "carrier" if name.endswith("_bay") else "cruiser"
                discover(game, ["drone_carriers" if kind == "carrier" else "cruiser_hulls"])
                modules = [name] if module.damage or name.endswith("_bay") else ["laser", name]
                self.assertIsNotNone(loadout_error(kind, modules, game.technology.completed))
                discover(game, [module.technology])
                design = game.save_design(module.name, kind, modules)
                game.queue_ship(0, 2, design.id)
                game.buy_construction(0, 2)
                self.assertEqual(game.ships[-1].design, design)
                self.assertEqual(round_trip(game), game)

    def test_new_campaign_needs_all_new_tiers_but_every_tier_has_two_choices(self):
        game = campaign()
        for branch in BRANCHES:
            for tier in branch_tiers(branch):
                self.assertEqual(len(choices(branch, tier)), 2)
        for branch in BRANCHES:
            discover(game, [choices(branch, branch_tiers(branch)[-1])[0].id])
        self.assertEqual(len(game.technology.completed), sum(len(branch_tiers(b)) for b in BRANCHES))
        self.assertIn("retired", game.research_error("ascension_theory"))
        self.assertEqual(round_trip(game), game)

    def test_new_branch_switch_transfers_rp_and_preserves_exclusivity(self):
        game = campaign()
        discover(game, ["graviton_beams"])
        game.research = 200
        game.choose_research("particle_beams")
        game.choose_research("phased_beams")
        self.assertEqual(game.technology.progress, 200)
        game.research = TECHNOLOGIES["phased_beams"].cost-200
        game.advance_research()
        self.assertEqual(game.technology.status("particle_beams"), "excluded")
        self.assertIsNone(game.research_error("heavy_beam_mounts"))
        self.assertEqual(round_trip(game), game)


class ArsenalCombatTests(unittest.TestCase):
    def test_weapon_damage_ranges_and_independent_pulse_and_mirv_rolls(self):
        for weapon, expected, shots in (("pulse", 8, 2), ("plasma", 24, 1), ("particle", 20, 1),
                                        ("heavy_beam", 30, 1), ("fusion_torpedo", 18, 1),
                                        ("mirv", 21, 3), ("disruptor", 40, 1), ("antimatter", 36, 1)):
            with self.subTest(weapon=weapon):
                game = duel([weapon])
                before = game.combat.ship(2).hull
                self.assertEqual(game.combat_fire(1, 2), 0 if BEAMS[weapon].projectile else expected)
                if BEAMS[weapon].projectile:
                    cycle(game)
                self.assertEqual(before-game.combat.ship(2).hull, expected)
                self.assertEqual(game.combat.shots_fired, shots)
                self.assertEqual(round_trip(game), game)
        game = duel(["pulse"])
        game.combat.accuracy = True
        attacker, target = game.combat.ship(1), game.combat.ship(2)
        self.assertGreater(combat.accuracy_breakdown(game, attacker, target, "pulse")["chance"],
                           combat.accuracy_breakdown(game, attacker, target, "laser")["chance"])

    def test_plasma_short_range_and_particle_long_range_are_enforced(self):
        for weapon, distance, legal in (("plasma", 5, False), ("particle", 10, True), ("particle", 11, False)):
            game = duel([weapon]); game.combat.ship(2).x = 5+distance
            self.assertEqual(combat.in_range(game.combat.ship(1), game.combat.ship(2)), legal)
            if not legal:
                original = game.to_dict()
                with self.assertRaisesRegex(RuleError, "range"):
                    game.combat_fire(1, 2)
                self.assertEqual(game.to_dict(), original)

    def test_ion_amplifies_shield_damage_without_amplifying_hull_spillover(self):
        for shields, expected_hull, expected_shield in ((48, 0, 16), (5, 6, 0), (0, 8, 0)):
            game = duel(["ion"], ["laser", "shield", "shield", "shield", "shield"])
            game.combat.ship(2).shields = shields
            self.assertEqual(game.combat_fire(1, 2), expected_hull)
            self.assertEqual(game.combat.ship(2).shields, expected_shield)
            self.assertEqual(round_trip(game), game)

    def test_phased_damage_bypasses_shields_and_hardening_counters_it(self):
        for shield, expected_hull, expected_shield in (("shield", 8, 16), ("hardened_shield", 2, 10)):
            game = duel(["phased"], ["laser", shield, shield])
            self.assertEqual(game.combat_fire(1, 2), expected_hull)
            self.assertEqual(game.combat.ship(2).shields, expected_shield)
            self.assertEqual(round_trip(game), game)

    def test_phased_kill_clears_remaining_shields_and_commits_campaign_loss(self):
        game = duel(["phased"], ["laser", "shield", "shield"])
        game.combat.ship(2).hull = 5
        self.assertEqual(game.combat_fire(1, 2), 5)
        self.assertEqual(game.combat.ship(2).shields, 0)
        self.assertEqual(game.combat.status, "player_victory")
        self.assertEqual(round_trip(game), game)

    def test_graviton_slow_is_nonstacking_and_expires_after_targets_next_turn(self):
        game = duel(["graviton", "graviton"], ["laser"], enemy_kind="cruiser")
        target = game.combat.ship(2); original = target.movement
        game.combat_fire(1, 2)
        self.assertEqual(target.movement, original-1)
        self.assertTrue(target.graviton_slow)
        self.assertEqual(round_trip(game), game)
        game.combat_end_turn()
        self.assertEqual(target.movement, original-1)
        game.combat_end_turn("rival")
        self.assertEqual(target.movement, original)
        game = duel(["graviton"])
        game.combat_fire(1, 2)
        self.assertEqual(game.combat.ship(2).movement, 1)

    def test_recharge_skips_exactly_one_turn_and_other_weapons_can_fire(self):
        for weapon in ("disruptor", "antimatter"):
            game = duel([weapon, "laser"])
            game.combat_fire(1, 2)
            self.assertEqual(game.combat.ship(1).cooldowns, {weapon: 2})
            cycle(game)
            self.assertEqual(game.combat.ship(1).cooldowns, {weapon: 1})
            self.assertEqual(game.combat_fire(1, 2), 5)
            self.assertEqual(round_trip(game), game)
            cycle(game)
            self.assertFalse(game.combat.ship(1).cooldowns)
            self.assertEqual(game.combat_fire(1, 2), 5 if BEAMS[weapon].projectile else BEAMS[weapon].damage+5)

    def test_missed_shots_also_recharge_and_out_of_range_ready_guns_cannot_fire(self):
        game = duel(["antimatter", "laser"])
        game.combat.ship(2).x = 13
        with patch("orion.combat.accuracy_breakdown", return_value={"chance": 0}):
            self.assertEqual(game.combat_fire(1, 2), 0)
        cycle(game)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "range"):
            game.combat_fire(1, 2)
        self.assertEqual(before, game.to_dict())
        game = duel(["disruptor"]); game.combat_fire(1, 2); cycle(game)
        self.assertFalse(game.combat.can_fire(game.combat.ship(1)))
        with self.assertRaisesRegex(RuleError, "recharging"):
            game.combat_fire(1, 2)

    def test_torpedo_guidance_and_point_defense_apply_to_all_new_torpedoes(self):
        for weapon, expected in (("fusion_torpedo", 8), ("mirv", 15), ("antimatter", 15)):
            game = duel([weapon], ["laser", "point_defense", "point_defense"])
            before = game.combat.ship(2).hull
            self.assertEqual(game.combat_fire(1, 2), 0)
            cycle(game)
            self.assertEqual(before-game.combat.ship(2).hull, expected)
            self.assertEqual(round_trip(game), game)
        game = duel(["mirv"], ["laser"], enemy_kind="frigate")
        game.combat.accuracy = True
        a, b = game.combat.ship(1), game.combat.ship(2)
        before = combat.accuracy_breakdown(game, a, b, "mirv")["evasion"]
        game.combat = None; discover(game, ["torpedo_guidance"])
        game.start_combat(0)
        self.assertEqual(combat.accuracy_breakdown(game, a, b, "mirv")["evasion"], before//2)

    def test_regeneration_caps_at_capacity_and_damage_control_has_finite_reserve(self):
        game = duel(["laser"], ["laser", "regenerative_shield", "damage_control"])
        target = game.combat.ship(2)
        target.shields, target.hull = 7, target.initial_hull-20
        for _ in range(6):
            cycle(game)
        self.assertEqual(target.shields, 8)
        self.assertEqual(target.hull, target.initial_hull-8)
        self.assertEqual(target.repair_remaining, 0)
        self.assertEqual(round_trip(game), game)
        game = duel(["laser"], ["laser", "damage_control"])
        target = game.combat.ship(2); target.hull -= 1
        cycle(game)
        self.assertEqual((target.hull, target.repair_remaining), (target.initial_hull, 11))

    def test_repair_never_exceeds_entry_hull_or_revives_destroyed_ships(self):
        game = duel(["laser", "damage_control"])
        game.combat = None
        game.ships[0].hull = 50
        game.start_combat(0)
        unit = game.combat.ship(1); unit.hull = 49
        cycle(game)
        self.assertEqual(unit.hull, 50)
        self.assertEqual(round_trip(game), game)

    def test_flak_and_reinforced_armor_have_real_tactical_effects(self):
        game = duel(["fusion_torpedo"], ["laser", "flak", "flak", "reinforced_armor"])
        target = game.combat.ship(2)
        self.assertEqual(target.design.interception, 75)
        self.assertEqual(target.max_hull, 139)
        before = target.hull
        self.assertEqual(game.combat_fire(1, 2), 0)
        cycle(game)
        self.assertEqual(before-target.hull, 5)
        self.assertEqual(round_trip(game), game)

    def test_ion_bombardment_bonus_stays_on_shields(self):
        game = campaign()
        design = equip(game, ["ion"], kind="cruiser", fit_version=1)
        system, world = game.headquarters("rival")
        discover(game, ["planetary_shielding"], "rival")
        world.buildings.append("planetary_shield")
        # Keep defense powered using an ordinary generator.
        world.buildings.append("solar_array")
        world.shield_points = 5
        game.ships = [Ship(1, "cruiser", system.id, design=design)]
        game.next_ship_id = 2
        self.assertEqual(defenses.bombardment_power(game, system.id), 32)
        absorbed, troops = defenses.bombardment_forecast(game, system.id, world.id)
        self.assertEqual(absorbed, 5)
        self.assertLessEqual(troops, 1)


class ArsenalDroneTests(unittest.TestCase):
    def test_mixed_bays_launch_chosen_roles_with_separate_finite_reserves(self):
        game = duel(["interceptor_bay", "bomber_bay"], kind="carrier")
        carrier = game.combat.ship(1)
        first = game.combat_launch_drones(1, role="interceptor")
        self.assertEqual(len(first), 2)
        self.assertTrue(all(game.combat.ship(i).movement == 6 for i in first))
        cycle(game)
        second = game.combat_launch_drones(1, role="bomber")
        self.assertEqual(len(second), 2)
        self.assertTrue(all(game.combat.ship(i).movement == 3 for i in second))
        self.assertEqual(round_trip(game), game)
        for identifier in first:
            game.combat.ship(identifier).hull = 0
        cycle(game)
        game.combat_launch_drones(1, role="interceptor")
        for drone in game.combat.drones(carrier):
            if drone.drone_role == "interceptor":
                drone.hull = 0
        cycle(game)
        self.assertNotIn("interceptor", game.combat.available_drone_roles(carrier))
        with self.assertRaises(RuleError):
            game.combat_launch_drones(1, role="interceptor")
        self.assertEqual(round_trip(game), game)

    def test_interceptors_protect_nearby_allies_and_counter_drones(self):
        game = duel(["interceptor_bay"], ["laser", "drone_bay"], kind="carrier", enemy_kind="carrier")
        ids = game.combat_launch_drones(1)
        carrier = game.combat.ship(1)
        self.assertEqual(combat.interception(game.combat, carrier), 40)
        game.combat.ship(ids[0]).x = 0
        self.assertEqual(combat.interception(game.combat, carrier), 20)
        game.combat_end_turn()
        enemy = game.combat.ship(game.combat_launch_drones(2, "rival")[0])
        enemy.hull = 6
        self.assertEqual(combat.hit_damage(game.combat, enemy, "interceptor_pulse", 2)[0], 6)
        target = game.combat.ship(2)
        self.assertEqual(combat.hit_damage(game.combat, target, "interceptor_pulse", 2)[0], 2)

    def test_bombers_do_double_damage_to_capitals_and_are_interceptable(self):
        game = duel(["bomber_bay"], ["laser", "flak"], kind="carrier")
        target = game.combat.ship(2)
        self.assertEqual(combat.hit_damage(game.combat, target, "bomber_torpedo", 5)[0], 6)
        target.design = ShipDesign("design_1", "Target", "titan", ("laser",))
        self.assertEqual(combat.hit_damage(game.combat, target, "bomber_torpedo", 5)[0], 10)
        target.kind = "frigate"
        self.assertEqual(combat.hit_damage(game.combat, target, "bomber_torpedo", 5)[0], 5)


class ArsenalSaveAndAITests(unittest.TestCase):
    def test_authentic_v30_campaigns_keep_projects_battles_and_science_goals(self):
        from orion import balance
        previous = balance.active_profile()
        balance.activate(balance.legacy_profile())
        self.addCleanup(lambda: balance.activate(previous))
        path = Path(__file__).parent/"fixtures/v0412_arsenal_saves.json"
        source = path.read_bytes(); fixtures = json.loads(source)
        for name, data in fixtures["cases"].items():
            with self.subTest(case=name):
                game = GameState.from_dict(data, version=fixtures["save_version"])
                self.assertTrue(game.technology.legacy_arsenal)
                historical = (data.get("result") or {}).get("condition") == "science"
                retired = not historical and data["technology"]["active"] == "ascension_theory"
                self.assertEqual(game.technology.progress, 0 if retired else data["technology"]["progress"])
                self.assertEqual(game.technology.completed, [t for t in data["technology"]["completed"] if historical or t != "ascension_theory"])
                self.assertEqual(round_trip(game), game)
                if name.startswith("ascension"):
                    self.assertEqual(game.technology.finished_branches, 9)
                    self.assertEqual(game.technology.status("pulse_beams"), "available")
                if game.combat:
                    self.assertTrue(all(not s.cooldowns and not s.graviton_slow for s in game.combat.ships))
        self.assertEqual(path.read_bytes(), source)

    def test_malformed_combat_support_fields_are_rejected(self):
        game = duel(["antimatter", "damage_control"])
        game.combat_fire(1, 2)
        original = game.to_dict()
        invalid = (("cooldowns", {"antimatter": 3}), ("cooldowns", {"antimatter": True}),
                   ("cooldowns", {"laser": 1}), ("cooldowns", []),
                   ("repair_remaining", 13), ("repair_remaining", True),
                   ("graviton_slow", 1), ("drone_role", "interceptor"))
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(original); data["combat"]["ships"][0][field] = value
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)
        data = copy.deepcopy(original); data["technology"]["legacy_arsenal"] = 1
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_ai_builds_researched_blueprints_at_full_cost_and_preserves_orders(self):
        game = campaign()
        discover(game, ["plasma_beams", "regenerative_shields", "fusion_torpedoes",
                        "advanced_flak", "automated_damage_control"], "rival")
        kind = ai.warship_choice(game, "rival")
        spec = game.project_spec(kind, "rival")
        self.assertIsInstance(spec, ShipDesign)
        self.assertIsNone(loadout_error(kind, spec.modules, game.opponent.technology.completed))
        self.assertTrue(any(MODULES[m].technology in ARSENAL_TECHNOLOGIES for m in spec.modules))
        system, world = game.headquarters("rival")
        price = game.project_price(kind, "rival")
        game.queue_ship(system.id, world.id, kind, owner="rival")
        project = world.construction_queue[-1]
        self.assertEqual((project.resource_cost, project.design), (price, spec))
        discover(game, ["graviton_beams"], "rival")
        self.assertEqual(project.design, spec)
        game.buy_construction(system.id, world.id, owner="rival")
        self.assertEqual(game.ships[-1].design, spec)
        self.assertEqual(round_trip(game), game)

    def test_advanced_combat_save_resume_produces_identical_ai_actions_and_outcomes(self):
        game = duel(["antimatter", "graviton", "regenerative_shield", "damage_control"],
                    ["interceptor_bay", "bomber_bay", "plasma", "hardened_shield", "armor"],
                    kind="cruiser", enemy_kind="carrier")
        restored = round_trip(game)
        for step in range(1000):
            if game.combat.status != "active":
                break
            event = combat.ai_action(game, game.combat.active_owner)
            self.assertEqual(event, combat.ai_action(restored, restored.combat.active_owner))
            if step % 7 == 0:
                restored = round_trip(restored)
        self.assertNotEqual(game.combat.status, "active")
        self.assertEqual(game, restored)
        self.assertEqual(round_trip(game), game)

    def test_capture_preserves_paid_ai_blueprints_without_granting_research(self):
        game = campaign()
        discover(game, ["cruiser_hulls", "plasma_beams"], "rival")
        system, home = game.headquarters("rival")
        frontier = next(p for p in system.worlds if not p.colonized and game.can_settle(p, "rival"))
        game.ships = [Ship(1, "colony_ship", system.id, owner="rival")]
        game.next_ship_id = 2
        game.colonize(1, system.id, frontier.id, owner="rival")
        game.queue_ship(system.id, frontier.id, "cruiser", owner="rival")
        project = frontier.construction_queue[0]
        game.fund_project(project, "rival"); project.progress = 7
        original = project.design
        game.ships = [Ship(i, "troop_transport", system.id) for i in range(2, 7)]
        game.next_ship_id = 7
        report = game.invade(system.id, frontier.id)
        self.assertTrue(report.captured)
        self.assertIsNone(game.result)
        self.assertEqual((frontier.construction_queue[0].design, project.progress), (original, 7))
        self.assertEqual(game.technology.completed, [])
        self.assertEqual(round_trip(game), game)
        game.buy_construction(system.id, frontier.id)
        self.assertEqual(game.ships[-1].design, original)
        self.assertEqual(round_trip(game), game)
        planned = game.save_design("Stolen copy", original.kind, original.modules)
        with self.assertRaises(RuleError):
            game.queue_ship(system.id, frontier.id, planned.id)
        self.assertEqual(round_trip(game), game)


class ArsenalUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = campaign()

    def tearDown(self):
        self.app.audio.close(); pg.quit(); self.folder.cleanup()

    def test_all_equipment_and_eight_physics_tiers_are_reachable_on_screen(self):
        app = self.app
        app.open_designer()
        seen = set()
        for page in range(4):
            app.design_module_page = page; app.render()
            seen.update(b.key.removeprefix("design_add_") for b in app.buttons if b.key.startswith("design_add_"))
            self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
        self.assertEqual(seen, set(MODULES))
        app.filter_design_modules("support"); app.render()
        self.assertIn("design_add_bomber_bay", [b.key for b in app.buttons])
        self.assertNotIn("design_add_laser", [b.key for b in app.buttons])
        app.open_research(); app.select_research_branch("physics"); app.select_research_tier(8); app.render()
        self.assertIn("research_choose_disruptor_beams", [b.key for b in app.buttons])
        for tier in range(1, 9):
            self.assertTrue(app.canvas.get_rect().contains(next(b.rect for b in app.buttons if b.key == f"research_tier_{tier}")))

    def test_autofit_and_module_right_click_use_current_research(self):
        app = self.app
        discover(app.game, ["plasma_beams", "reinforced_armor"])
        app.open_designer(); app.auto_fit_design(); app.render()
        self.assertIn("plasma", app.design_modules)
        self.assertIsNone(loadout_error(app.design_kind, app.design_modules, app.game.technology.completed))
        app.filter_design_modules("weapon"); app.render()
        identifier, rect = next((m, r) for m, r in app.module_regions if m == "plasma")
        before = app.game.to_dict()
        app.present()
        v = app.viewport
        position = (round(v.x+rect.centerx*v.w/1440), round(v.y+rect.centery*v.h/900))
        app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, {"button": 3, "pos": position}))
        self.assertEqual(app.dialog["module"], identifier)
        self.assertEqual(app.game.to_dict(), before)

    def test_recharging_weapon_animation_keeps_fired_weapon_snapshot(self):
        app = self.app; app.game = duel(["disruptor"])
        app.go("combat"); app.combat_ship_id = 1; app.combat_target_id = 2
        app.combat_action("fire")
        self.assertEqual(app.combat_animation.weapons, ("disruptor",))
        for age in (.07, .2, .5):
            app.combat_animation.elapsed = age; app.render()
        self.assertEqual(Storage(self.folder.name).load(Path(self.folder.name)/"saves/autosave.json")[0], app.game)

    def test_all_new_effects_render_and_mixed_carrier_launch_selection_works(self):
        surface = pg.Surface((600, 300))
        for name in ("pulse", "plasma", "ion", "graviton", "particle", "heavy_beam", "phased", "disruptor", "fusion_torpedo", "mirv", "antimatter"):
            animation = CombatAnimation("fire", 1, ((40, 150), (540, 150)), 2, name, 4, weapons=(name,))
            for age in (.05, .15, .25, .5):
                animation.elapsed = age; animation.draw(surface, lambda p: p)
        app = self.app; app.game = duel(["interceptor_bay", "bomber_bay"], kind="carrier")
        app.go("combat"); app.combat_ship_id = 1; app.render()
        next(b for b in app.buttons if b.key == "combat_drone_bomber").action()
        app.combat_action("launch")
        self.assertTrue(all(s.drone_role == "bomber" for s in app.game.combat.drones(app.game.combat.ship(1))))
        self.assertEqual(round_trip(app.game), app.game)


if __name__ == "__main__":
    unittest.main()
