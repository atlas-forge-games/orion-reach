"""Render the v0.69 race selection and actual accession controls."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion import accession, accession_view, exploration

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        output = ROOT / "screenshots"
        output.mkdir(exist_ok=True)
        for race in ("serevan", "skirr", "concord", "nexus"):
            app.choose_race(race)
            app.go("race_select")
            app.mouse = (-1, -1)
            app.render()
            assert all(app.canvas.get_rect().contains(b.rect) for b in app.buttons)
            pg.image.save(app.canvas, str(output/f"v069_{race}.png"))
        g = app.game = new_game(empire_name="Serevan Union", seed=4242, race_id="serevan", rival_race_id="lithar",
            random_starts=False, with_guardians=False, with_tombs=False,
            with_black_holes=False, with_encounters=False, fog_of_war=False, victory_conditions=())
        p = g.planet_at(0, 3)
        p.owner, p.colonized, p.population = "rival", True, 6
        p.species = {"lithar": 6}
        g.headquarters()[1].buildings = ["trade_center", "trade_center"]
        g.diplomacy.relations = 40
        exploration.refresh(g)
        accession.start(g, 0, p.id).progress = 42
        app.go("diplomacy")
        accession_view.open_panel(app)
        app.render()
        pg.image.save(app.canvas, str(output/"v069_accession.png"))
        app.dialog = {"alignment_info": True, "alignment_matrix": True}
        app.render()
        pg.image.save(app.canvas, str(output/"v069_alignment.png"))
        print("Rendered four race profiles, accession controls and the expanded matrix.")
    finally:
        app.audio.close()
        pg.quit()
