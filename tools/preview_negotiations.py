"""Capture the real diplomacy UI with deterministic, reviewable example states."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion import diplomacy, exploration, first_contact, negotiations


def fixture():
    game = new_game(seed=12, race_id='terran', rival_race_id='lithar', rival_count=5,
                    random_starts=False, fog_of_war=False, with_guardians=False,
                    with_tombs=False, with_black_holes=False, with_encounters=False)
    for owner in first_contact.pending(game):
        first_contact.acknowledge(game, owner)
    for i, owner in enumerate(game.owners):
        home, _ = game.headquarters(owner)
        home.x, home.y = .30+i*.04, .50
    homes = {s.id for o in game.owners for s in game.colony_systems(o)}
    system = next(s for s in game.systems if s.id not in homes and s.worlds)
    system.x, system.y = .32, .51
    system.worlds[0].biome = 'Terran'
    game.turn, game.year = 41, game.year+40
    game.diplomacy.relations = 45
    exploration.refresh(game)
    return game, system.id


def main():
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game, sid = fixture()
            app.go('galaxy')
            app.open_diplomacy()
            negotiations.offer(app.game, 'rival', 'player', 'territory', system_id=sid)
            app.show_diplomatic_affairs('negotiations', 'rival')
            def capture(name):
                app.notice = ''
                app.render()
                pg.image.save(app.canvas, ROOT/'screenshots'/name)
            capture('diplomacy_negotiations.png')
            app.cancel_dialog()
            negotiations.respond(app.game, 'rival', True)
            app.show_diplomatic_affairs('negotiations', 'rival')
            capture('diplomacy_promises.png')
            app.cancel_dialog()
            diplomacy.start_war(app.game, 'player', 'rival')
            app.game.turn += 12
            app.game.year += 12
            diplomacy.record_defeat(app.game, 'rival', 'player')
            app.show_diplomatic_affairs('negotiations', 'rival')
            capture('diplomacy_peace.png')
            app.cancel_dialog()
            app.show_diplomatic_affairs('reasons', 'rival')
            capture('diplomacy_reasons.png')
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    main()
