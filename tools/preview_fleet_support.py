"""Capture the real combined-arms setup, ranges, interception and equipment UI."""

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg
from orion import balance
from orion.combat_sandbox import preset
from orion.combat_simulator import CombatSimulator
from orion.weapons import BEAMS


def main():
    balance.configure(ROOT / "balance.json")
    with tempfile.TemporaryDirectory() as directory:
        app = CombatSimulator(Path(directory), scenario=preset(6), capture=True)
        try:
            def capture(name):
                app.render()
                pg.image.save(app.canvas, ROOT / "screenshots" / (name+".png"))

            app.launch(False)
            capture("v071_fleet_support")
            app.combat_ship_id = 2
            capture("v071_escort_range")
            for _ in range(3000):
                if app.game.combat.status != "active":
                    raise AssertionError("No protected projectile volley occurred")
                event = app.game.combat_ai_action()
                destroyers = [i for i in event.get("support_ids", ()) if app.game.combat.ship(i).kind == "destroyer"]
                if (event["kind"] == "fire" and destroyers and not event.get("missed")
                        and any(BEAMS[w].projectile for w in event.get("weapons", ()))):
                    app.after_combat_action(event)
                    app.combat_animation.elapsed = .12
                    app.combat_ship_id = destroyers[0]
                    app.combat_target_id = event["ship_id"]
                    capture("v071_escort_fire")
                    break
            else:
                raise AssertionError("No interception within action limit")
            app.edit_setup()
            app.open_designer("design_2")
            app.filter_design_modules("support")
            capture("v071_support_designer")
            app.show_designer_info(module="escort_array")
            capture("v071_support_help")
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered five fleet-support previews.")


if __name__ == "__main__":
    main()
