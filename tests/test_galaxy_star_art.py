"""Animation changes illumination without flickering the core or consuming RNG."""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion.display import Canvas
from orion.galaxy_star_art import draw_atlas_star


class StarAnimationTests(unittest.TestCase):
    def test_motion_setting_freezes_light_while_enabled_pulse_keeps_core_steady(self):
        pg.init()
        self.addCleanup(pg.quit)
        random_state = random.getstate()
        for scale in (1, 1.25, 1.75):
            for zoom in (1, 2, 4):
                with self.subTest(scale=scale, zoom=zoom):
                    def frame(time, animated):
                        canvas = Canvas((120, 120), scale)
                        canvas.fill((3, 8, 14))
                        draw_atlas_star(canvas, (60, 60), (113, 181, 231),
                                        zoom=zoom, time=time, star_id=0, animated=animated)
                        return canvas
                    steady_a, steady_b = frame(0, False), frame(1.25, False)
                    self.assertEqual(pg.image.tobytes(steady_a, "RGB"), pg.image.tobytes(steady_b, "RGB"))
                    animated_a, animated_b = frame(0, True), frame(1.25, True)
                    self.assertNotEqual(pg.image.tobytes(animated_a, "RGB"), pg.image.tobytes(animated_b, "RGB"))
                    self.assertEqual(animated_a.get_at((60, 60)), animated_b.get_at((60, 60)))
        self.assertEqual(random.getstate(), random_state)
