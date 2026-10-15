"""Headless timings and deterministic state/frame fingerprints; no user saves touched.

Run from the checkout: python tools/benchmark_performance.py
Timings are machine-dependent. Compare the same scenario on both revisions.
"""
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
from time import perf_counter

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame as pg
from orion.app import App
from orion.model import new_game


def timed(action):
    start = perf_counter()
    action()
    return (perf_counter()-start)*1000


def fingerprint(value):
    return hashlib.sha256(value).hexdigest()


def main():
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.game = game = new_game(seed=12, race_id='wanderers', rival_count=5,
                                      random_starts=False, with_guardians=False,
                                      with_tombs=False, with_black_holes=False)
            for _, home in game.settlements('player'):
                home.trade_goods = True
            app.go('galaxy')
            for _ in range(3):
                app.render()
                app.present()
            initial_frame = fingerprint(pg.image.tobytes(app.canvas, 'RGB'))
            renders = [timed(app.render) for _ in range(16)]
            events = [pg.event.Event(pg.MOUSEMOTION, pos=(640+i, 360)) for i in range(24)]

            def input_batch():
                if hasattr(app, 'process_events'):
                    app.process_events(events)
                else:
                    for event in events:
                        app.handle_event(event)
                        app.render()
                app.render()
                app.present()

            batch_ms = timed(input_batch)
            app.mouse = (-1, -1)
            turns, saves, frames, states = [], [], [], []
            for _ in range(8):
                turns.append(timed(game.advance_turn))
                saves.append(timed(lambda: app.save_game(autosave=True)))
                frames.append(timed(lambda: (app.render(), app.present())))
                state = game.to_dict()
                state.pop('campaign_id', None)
                states.append(fingerprint(json.dumps(state, sort_keys=True).encode()))
            print(json.dumps({
                'scenario': 'seed 12, 48 stars, Wanderers, five AI rivals, eight turns',
                'median_render_ms': round(statistics.median(renders), 2),
                'motion_batch_ms': round(batch_ms, 2),
                'median_simulation_ms': round(statistics.median(turns), 2),
                'median_autosave_ms': round(statistics.median(saves), 2),
                'median_render_present_ms': round(statistics.median(frames), 2),
                'initial_frame_sha256': initial_frame,
                'final_frame_sha256': fingerprint(pg.image.tobytes(app.canvas, 'RGB')),
                'turn_state_sha256': states,
            }, indent=2))
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    main()
