"""Capture full-roster setup and paged reports without opening player saves."""
import argparse
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame as pg
from orion.app import App
from orion import council, first_contact
from orion.model import new_game


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        app.window = pg.display.set_mode((1440, 900))
        app.settings["autosave"] = app.settings["animated_background"] = False
        app.settings["ui_scale"] = 100
        app.mouse, app.focus = (-1, -1), None

        def capture(name):
            app.render()
            app.present()
            output = BytesIO()
            pg.image.save(app.window, output, "preview.png")
            (args.output/(name+"_v0880.png")).write_bytes(output.getvalue())

        def pages(name, key):
            for index in range(10):
                capture(f"{name}_{index+1}")
                button = next(b for b in app.buttons if b.key == key)
                if not button.enabled:
                    break
                button.action()

        try:
            app.choose_rival_count("all")
            app.go("setup")
            capture("setup_all_civilizations")
            app.choose_race("observer")
            capture("setup_all_observer")
            app.choose_race("terran")
            app.game = new_game(seed=2408, galaxy_size="Compact", rival_count="all", fog_of_war=False)
            for owner in first_contact.pending(app.game):
                first_contact.acknowledge(app.game, owner)
            app.go("galaxy")
            capture("galaxy_all_civilizations")
            app.go("statistics")
            pages("statistics_all", "statistics_empires_next")
            app.objectives_tab = "race"
            app.go("objectives")
            pages("objectives_all", "objectives_empires_next")
            app.go("diplomacy")
            app.rival_id = "rival_12"
            capture("diplomacy_last_contact")
            app.show_diplomatic_affairs("coalitions", "rival")
            pages("coalitions_all", "coalition_targets_next")
            app.cancel_dialog()
            council.schedule(app.game)
            council.convene_due(app.game)
            app.go("council")
            pages("council_all", "council_empires_next")
            app.game = new_game(seed=2408, race_id="observer", rival_count="all", fog_of_war=False)
            app.go("observer")
            app.observer_page = 2
            capture("observer_all_last_page")
        finally:
            app.audio.close()
            pg.quit()
    print(f"Saved full-roster previews to {args.output}")


if __name__ == "__main__":
    main()
