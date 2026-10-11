"""Render real council voting, decisions, victory and objective screens."""

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
from orion import council, first_contact
from orion.app import App
from orion.model import new_game


def campaign(counts):
    game = new_game(seed=2408, galaxy_size="Compact", rival_count=len(counts)-1,
                    fog_of_war=False, with_tombs=False, with_guardians=False)
    for owner, wanted in zip(game.owners, counts):
        while council.world_votes(game).get(owner, 0) < wanted:
            system = next(s for s in game.systems if s.worlds and not any(p.colonized for p in s.worlds))
            p = system.worlds[0]
            p.biome, p.colonized, p.owner, p.population = "Terran", True, owner, 1
    return game


def main():
    output = ROOT/"screenshots"
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            def capture(name):
                app.notice = ""
                app.render()
                pg.image.save(app.canvas, str(output/name))

            app.game = campaign((2, 7, 2, 1, 1, 1))
            app.go("objectives")
            capture("council_objectives.png")
            council.schedule(app.game)
            app.game.check_victory()
            for owner in first_contact.pending(app.game):
                first_contact.acknowledge(app.game, owner)
            app.go("council")
            capture("council_vote.png")
            app.cast_council_vote("player")
            capture("council_ruling.png")
            app.decide_council(False)
            capture("council_defiance_news.png")

            app.game = campaign((7, 4, 3))
            council.schedule(app.game)
            app.game.check_victory()
            app.cast_council_vote("player")
            capture("council_victory.png")
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == "__main__":
    main()
