"""Real image loading, viewport crops, shared caches and optional-art fallback."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame as pg

from orion import planet_surface_art as art
from orion.colony_scene import landscape, fallback_landscape
from orion.model import BIOMES


class PlanetSurfaceArtTests(unittest.TestCase):
    def setUp(self):
        art.load_surface_art.cache_clear()
        art.surface_background.cache_clear()
        self.addCleanup(art.load_surface_art.cache_clear)
        self.addCleanup(art.surface_background.cache_clear)
        self.addCleanup(fallback_landscape.cache_clear)

    def test_every_canonical_biome_has_detailed_art_at_both_overview_sizes(self):
        self.assertEqual(set(art.SURFACE_FILES), set(BIOMES))
        for biome in BIOMES:
            with self.subTest(biome=biome):
                original = art.load_surface_art(biome)
                self.assertIsNotNone(original)
                self.assertGreaterEqual(original.get_width(), 2000)
                self.assertGreaterEqual(original.get_height(), 700)
                for size in ((1392, 406), (1392, 526)):
                    image = landscape(biome, 'first colony', size, True)
                    self.assertEqual(image.get_size(), size)
                    self.assertIs(image, landscape(biome, 'another colony', size, False))

    def test_cover_crop_preserves_geometry_in_wide_and_tall_viewports(self):
        self.assertEqual(art.cover_crop((1200, 400), (600, 200)), pg.Rect(0, 0, 1200, 400))
        self.assertEqual(art.cover_crop((1200, 400), (400, 400)), pg.Rect(400, 0, 400, 400))
        self.assertEqual(art.cover_crop((1200, 400), (1200, 200)), pg.Rect(0, 100, 1200, 200))

    def test_missing_or_corrupt_art_keeps_a_renderable_landscape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'planet_surfaces').mkdir()
            (root / 'planet_surfaces/ice-v1.png').write_bytes(b'broken PNG')
            with patch.object(art, 'ASSETS', root):
                for biome in BIOMES:
                    self.assertIsNone(art.load_surface_art(biome))
                    self.assertEqual(landscape(biome, 'fallback', (1392, 406), True).get_size(), (1392, 406))


if __name__ == '__main__':
    unittest.main()
