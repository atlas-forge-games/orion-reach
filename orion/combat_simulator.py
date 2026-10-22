"""Desktop combat laboratory; campaign UI actions are isolated here."""

from copy import deepcopy
import hashlib
from pathlib import Path
import re

import pygame as pg

from .app import App
from .auto_designs import auto_design
from .combat_sandbox import (MAX_BASES, PRESETS, ROUND_LIMIT, SIDES, UPGRADES,
                             UPGRADE_DETAILS, ScenarioError, build_game,
                             load_scenario, preset, save_scenario)
from .designs import HULLS
from .model import RuleError
from .races import RACES
from .research import TECHNOLOGIES
from .storage import default_data_dir
from .ui import CYAN, GOLD, INK, LINE, MUTED, emblem, text


class CombatSimulator(App):
    combat_simulator = True

    def __init__(self, data_dir=None, *, scenario=None, capture=False):
        self.scenario = deepcopy(scenario) if scenario is not None else preset()
        self.scenario.validate()
        self.scenario_name = self.scenario.name
        self.catalogue_tab = "stock"
        self.catalogue_page = 0
        self.catalogue_selected = "frigate"
        self.fleet_pages = {side: 0 for side in SIDES}
        self.preset_index = 0
        self.sim_speed = 1
        self.sim_paused = False
        self.sim_limit_reached = False
        self.scenario_files = []
        self.scenario_names = {}
        self.scenario_page = 0
        self.last_mode_auto = False
        root = Path(data_dir) if data_dir is not None else default_data_dir()/"combat-simulator"
        self.scenarios_dir = root/"scenarios"
        super().__init__(root, capture=capture, skip_intro=True)
        self.seed = str(self.scenario.seed)
        self.settings["autosave"] = False
        pg.display.set_caption("Orion Reach | Combat Simulator")
        self.edit_setup()
        self.render()

    def go(self, screen, **kwargs):
        # This app never navigates to strategic screens or loads a campaign.
        if screen not in ("sim_setup", "sim_load", "designer", "combat"):
            screen = "sim_setup"
        self.screen = screen
        self.buttons, self.technology_regions, self.module_regions = [], [], []
        self.focus = self.pressed = self.field = None
        self.select_all = False
        pg.key.stop_text_input()
        if screen == "combat":
            self.sync_combat_selection()
        if screen == "designer":
            self.designer_return = "sim_setup"

    def chrome(self, section="COMBAT SIMULATOR", back=None):
        emblem(self.canvas, 55, 57, .65)
        text(self.canvas, "ORION REACH", (88, 39), 18, INK, spacing=2)
        text(self.canvas, "COMBAT SIMULATOR", (89, 68), 10, CYAN, "mono", 2)
        if self.screen == "combat":
            self.button("sim_setup_back", "Edit fleets", (738, 36, 147, 43), self.edit_setup)
            self.button("sim_speed", f"Speed {self.sim_speed}×", (897, 36, 138, 43), self.cycle_speed)
            self.button("sim_pause", "Resume · P" if self.sim_paused else "Pause · P",
                        (1047, 36, 160, 43), self.pause,
                        "primary" if self.sim_paused else "normal", enabled=self.game.combat.status == "active")
        else:
            self.button("sim_save", "Save scenario · F5", (738, 36, 202, 43), self.save_game)
            self.button("sim_load", "Load scenario", (952, 36, 171, 43), self.open_scenarios)
        self.button("sim_help", "Help · F1", (1230, 36, 178, 43), self.open_info)
        pg.draw.line(self.canvas, LINE, (32, 107), (1408, 107))

    def button(self, key, label, rect, action, style="normal", *args, **kwargs):
        if key.startswith("sim_") and style == "normal" and (rect[2] < 150 or rect[3] < 36):
            style = "tab"  # Compact, centered labels in fleet quantity controls.
        return super().button(key, label, rect, action, style, *args, **kwargs)

    def draw_sim_setup(self):
        from .combat_simulator_view import draw_setup
        draw_setup(self)

    def draw_sim_load(self):
        from .combat_simulator_view import draw_scenarios
        draw_scenarios(self)

    def sync_fields(self):
        name = self.scenario_name.strip()
        if not self.seed or not self.seed.isascii() or not self.seed.isdecimal():
            raise ScenarioError("Enter a numeric battle seed.")
        # Validate the complete candidate before changing the working scenario.
        candidate = deepcopy(self.scenario)
        candidate.name, candidate.seed = name, int(self.seed)
        candidate.validate()
        self.scenario.name, self.scenario.seed = candidate.name, candidate.seed

    def launch(self, automatic=False):
        try:
            self.sync_fields()
            game = build_game(self.scenario)
        except (ScenarioError, RuleError) as exc:
            self.toast(exc, True)
            return False
        self.game = game
        self.reset_combat_view()
        self.sim_paused = self.sim_limit_reached = False
        self.last_mode_auto = self.combat_auto = automatic
        self.dialog = None
        self.go("combat")
        return True

    def edit_setup(self):
        self.game = build_game(self.scenario, start=False)
        self.reset_combat_view()
        self.sim_paused = False
        self.dialog = None
        self.go("sim_setup")

    def finish_combat(self):
        self.edit_setup()

    def rematch(self):
        return self.launch(self.last_mode_auto)

    def change_ship(self, side, identifier, amount):
        try:
            self.scenario.change(side, identifier, amount)
        except ScenarioError as exc:
            self.toast(exc, True)

    def clear_fleet(self, side):
        self.scenario.fleet(side).ships.clear()
        self.scenario.fleet(side).bases = 0
        self.fleet_pages[side] = 0

    def change_bases(self, side, amount):
        fleet = self.scenario.fleet(side)
        fleet.bases = max(0, min(MAX_BASES, fleet.bases+amount))

    def cycle_race(self, side, delta):
        fleet = self.scenario.fleet(side)
        ids = list(RACES)
        fleet.race = ids[(ids.index(fleet.race)+delta)%len(ids)]

    def cycle_upgrades(self, side):
        fleet = self.scenario.fleet(side)
        ids = list(UPGRADES)
        fleet.upgrades = ids[(ids.index(fleet.upgrades)+1)%len(ids)]
        self.toast(UPGRADE_DETAILS[fleet.upgrades])

    def mirror_fleet(self):
        self.scenario.rival = deepcopy(self.scenario.player)
        self.fleet_pages["rival"] = 0

    def switch_catalogue(self, tab):
        self.catalogue_tab, self.catalogue_page = tab, 0
        rows = self.catalogue()
        if rows:
            self.catalogue_selected = rows[0]

    def catalogue(self):
        from .production import SHIP_TYPES
        return list(HULLS)+[k for k in SHIP_TYPES if k not in HULLS] if self.catalogue_tab == "stock" else [d.id for d in self.scenario.designs]

    def page_catalogue(self, delta):
        self.catalogue_page = max(0, min((max(1, len(self.catalogue()))-1)//6, self.catalogue_page+delta))

    def page_fleet(self, side, delta):
        last = (max(1, len(self.scenario.fleet(side).ships))-1)//6
        self.fleet_pages[side] = max(0, min(last, self.fleet_pages[side]+delta))

    def cycle_preset(self):
        self.preset_index = (self.preset_index+1)%len(PRESETS)

    def apply_preset(self):
        try:
            candidate = preset(self.preset_index)
        except ScenarioError as exc:
            self.toast(f"Preset is incompatible with this balance profile: {exc}", True)
            return
        self.use_scenario(candidate)

    def use_scenario(self, scenario):
        self.scenario = scenario
        self.scenario_name, self.seed = scenario.name, str(scenario.seed)
        self.catalogue_tab, self.catalogue_page = ("custom" if scenario.designs else "stock"), 0
        self.catalogue_selected = scenario.designs[0].id if scenario.designs else "frigate"
        self.fleet_pages = {side: 0 for side in SIDES}
        self.edit_setup()

    def open_designer(self, identifier=None):
        # A separate, non-combat model backs blueprint editing. Launch builds a
        # new battle from the scenario, including the selected combat upgrades.
        self.game = build_game(self.scenario, start=False)
        self.new_design()
        if identifier and (design := self.scenario.design(identifier)):
            self.load_design(design)
        elif identifier in HULLS:
            self.design_kind = identifier
            self.auto_fit_design()
        self.design_campaign = self.game.campaign_id
        self.go("designer")

    def auto_fit_design(self):
        design = auto_design(self.design_kind, tuple(sorted(TECHNOLOGIES)), planning=True)
        if design:
            self.design_modules = list(design.modules)

    def save_ship_design(self, copy=False):
        try:
            design = self.game.save_design(self.design_name, self.design_kind, self.design_modules,
                                           None if copy else self.design_id)
        except RuleError as exc:
            self.toast(exc, True)
            return
        self.scenario.designs = list(self.game.designs)
        self.load_design(design)
        self.design_page = self.game.designs.index(design)//7
        self.catalogue_selected, self.catalogue_tab = design.id, "custom"
        self.toast(f"{design.name} saved in this scenario. Add it to either fleet.")

    def add_design_to(self, side):
        if self.scenario.design(self.design_id):
            self.change_ship(side, self.design_id, 1)
            self.toast(f"Added {self.design_name} to {'your' if side == 'player' else 'the enemy'} fleet.")

    def save_game(self, autosave=False):
        # App's combat animation calls this after every order. Never save a
        # synthetic GameState through campaign Storage, even with an override.
        if autosave:
            return True
        try:
            self.sync_fields()
            slug = re.sub(r"[^A-Za-z0-9_-]+", "-", self.scenario.name).strip("-") or "battle"
            suffix = hashlib.sha256(self.scenario.name.encode("utf-8")).hexdigest()[:8]
            path = self.scenarios_dir/f"scenario-{slug}-{suffix}.json"
            save_scenario(path, self.scenario)
        except (ScenarioError, OSError, ValueError) as exc:
            self.toast(f"Scenario could not be saved: {exc}", True)
            return False
        self.toast(f"Saved {path.name}")
        return True

    def open_scenarios(self):
        try:
            self.scenario_files = sorted(self.scenarios_dir.glob("*.json"), key=lambda p: p.name.casefold())
        except OSError as exc:
            self.toast(exc, True)
            return
        self.scenario_names = {}
        self.scenario_page = 0
        self.go("sim_load")

    def load_selected_scenario(self, path):
        try:
            scenario = load_scenario(path)
            # Build before replacing the current setup, so failures are atomic.
            build_game(scenario, start=False)
        except (ScenarioError, RuleError) as exc:
            self.toast(exc, True)
            return
        self.use_scenario(scenario)
        self.toast(f"Loaded {path.name}")

    def page_scenarios(self, delta):
        self.scenario_page = max(0, min((max(1, len(self.scenario_files))-1)//8, self.scenario_page+delta))

    def scenario_label(self, path):
        if path not in self.scenario_names:
            try:
                self.scenario_names[path] = load_scenario(path).name
            except ScenarioError:
                self.scenario_names[path] = f"{path.name} · Invalid or incompatible scenario"
        return self.scenario_names[path]

    def cycle_speed(self):
        speeds = (1, 4, 12)
        self.sim_speed = speeds[(speeds.index(self.sim_speed)+1)%len(speeds)]
        self.combat_ai_due = self.time+.4/self.sim_speed

    def pause(self):
        if self.screen == "combat" and self.game.combat.status == "active":
            self.sim_paused = not self.sim_paused
            self.combat_last_update = self.time
            self.combat_ai_due = self.time+.4/self.sim_speed

    def combat_input_ready(self):
        return not self.sim_paused and super().combat_input_ready()

    def after_combat_action(self, event):
        super().after_combat_action(event)
        self.combat_ai_due = self.time+.4/self.sim_speed

    def update_combat(self):
        if self.screen != "combat" or self.sim_paused or self.dialog:
            self.combat_last_update = self.time
            return
        if self.game.combat.round > ROUND_LIMIT and not self.sim_limit_reached:
            self.sim_limit_reached = self.sim_paused = True
            self.toast(f"Paused after {ROUND_LIMIT} rounds. Edit fleets, rematch, or resume to continue.", True)
            self.combat_last_update = self.time
            return
        previous = self.combat_animation
        if previous:
            previous.elapsed += max(0, self.time-self.combat_last_update)*(self.sim_speed-1)
        super().update_combat()
        if previous and self.combat_animation is None:
            self.combat_ai_due = self.time+.35/self.sim_speed

    def open_info(self):
        self.confirm("Combat simulator", "Add stock ships or save custom loadouts in the designer. Both fleets can use any hull and equipment. "
                     "Combat upgrades set each side's passive research bonuses. The same seed and orders reproduce the same shots. "
                     "A toggles automatic control, P pauses, R restarts, E ends your turn and N selects your next ship. "
                     "Right-click either fleet's ships for weapons, hull, shields and incoming ordnance. "
                     "Torpedoes travel five cells per round and apply damage on arrival. "
                     "Mouse wheel or +/- zooms the battlefield; 0 resets. Middle-drag or Shift+arrows pans. "
                     "F5 saves the fleet setup; Load scenario restores it. Battles use the loaded balance profile.",
                     "Back to simulator", lambda: None)

    def quit_request(self):
        self.quit_now()

    def inspect_ship(self, ship_id):
        if self.dialog or self.screen != "combat" or not self.game.combat.ship(ship_id):
            return
        self.dialog = {"combat_ship_info": ship_id, "inspection_tab": "weapons", "inspection_page": 0,
                       "return_focus": self.focus}
        self.focus, self.pressed = "dialog_close", None
        self.buttons = []
        self.combat_last_update = self.time

    def inspect_tab(self, tab):
        self.dialog.update(inspection_tab=tab, inspection_page=0)

    def inspect_page(self, delta):
        self.dialog["inspection_page"] = max(0, self.dialog["inspection_page"]+delta)

    def draw_dialog(self):
        if "combat_ship_info" in self.dialog:
            from .combat_inspector import draw
            self.backdrop.dim(self.canvas)
            self.buttons = []
            draw(self)
        else:
            super().draw_dialog()

    def cancel_dialog(self):
        super().cancel_dialog()
        self.combat_last_update = self.time
        self.combat_ai_due = self.time+.4/self.sim_speed

    def handle_event(self, event):
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 3 and self.screen == "combat" and not self.dialog:
            from .combat_camera import BOARD, view
            point = self.logical_pos(event.pos)
            if BOARD.collidepoint(point):
                for ship in reversed(self.game.combat.ships):
                    if ship.hull <= 0:
                        continue
                    effect = self.combat_animation
                    position = (effect.moving_position() if effect and effect.kind == "move" and effect.ship_id == ship.id
                                else ship.position)
                    if view(self).ship_rect(ship, position).clip(BOARD).collidepoint(point):
                        self.inspect_ship(ship.id)
                        break
            return
        if event.type == pg.KEYDOWN and not self.dialog and not self.field:
            if event.key == pg.K_F5:
                self.save_game()
                return
            if self.screen == "combat" and event.key in (pg.K_p, pg.K_r):
                self.pause() if event.key == pg.K_p else self.rematch()
                return
            if self.screen == "sim_setup" and event.key == pg.K_ESCAPE:
                self.quit_request()
                return
            if self.screen == "designer":
                if event.key in (pg.K_PAGEUP, pg.K_PAGEDOWN):
                    self.design_module_page_change(-1 if event.key == pg.K_PAGEUP else 1)
                    return
                if event.key not in (pg.K_ESCAPE, pg.K_F1, pg.K_F11, pg.K_RETURN, pg.K_KP_ENTER,
                                      pg.K_SPACE, pg.K_TAB, pg.K_UP, pg.K_DOWN):
                    return
        if event.type == pg.MOUSEWHEEL and not self.dialog and event.y:
            delta = -1 if event.y > 0 else 1
            if self.screen == "sim_setup":
                if self.mouse[0] < 422:
                    self.page_fleet("player", delta)
                elif self.mouse[0] > 1018:
                    self.page_fleet("rival", delta)
                else:
                    self.page_catalogue(delta)
                return
            if self.screen == "sim_load":
                self.page_scenarios(delta)
                return
            if self.screen == "designer":
                self.design_module_page_change(delta)
                return
        super().handle_event(event)
