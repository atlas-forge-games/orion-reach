"""Casualty accounting must conserve troops and surviving transport identities."""
import unittest
from unittest.mock import patch
from orion.ground_combat import GroundOutcome
from orion.model import GameState
from orion.production import TROOP_STRENGTH
from orion.victory import transport_losses
from test_ground_combat import scenario, add_transports


class TransportSurvivalTests(unittest.TestCase):
    def test_casualty_boundaries_and_troop_conservation(self):
        for casualties in (0, 1, 7, 8, 9, 15, 16, 23, 24):
            with self.subTest(casualties=casualties):
                survivors = 24-casualties
                lost, garrison = transport_losses(3, survivors)
                self.assertEqual(lost, (casualties+7)//8)
                self.assertEqual((3-lost)*TROOP_STRENGTH+garrison, survivors)
                self.assertTrue(0 <= garrison < TROOP_STRENGTH)

    def test_invasion_keeps_original_surviving_ships_and_save_roundtrip(self):
        for casualties in (0, 1, 8, 9, 23, 24):
            with self.subTest(casualties=casualties):
                game = scenario()
                sid, pid = game.opponent.home_system, game.opponent.home_planet
                add_transports(game, sid, 3)
                original = list(game.ships)
                survivors = 24-casualties
                with patch('orion.victory.resolve', return_value=GroundOutcome(survivors, 0, ())):
                    report = game.invade(sid, pid)
                lost, garrison = transport_losses(3, survivors)
                self.assertEqual(game.ships, original[lost:])
                if report.captured:
                    self.assertEqual(game.planet_at(sid, pid).garrison, garrison)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)
