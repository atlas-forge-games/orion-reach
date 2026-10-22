"""Actual generated PCM/playback, mute handling and delayed impact timing."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion.audio import Audio
from orion.combat_effects import CombatAnimation
from orion.combat_sounds import DURATIONS, samples


class CombatSoundTests(unittest.TestCase):
    def tearDown(self):
        pg.quit()

    def test_every_cue_has_finite_faded_pcm_and_plays(self):
        audio = Audio()
        self.addCleanup(audio.close)
        self.assertTrue(audio.ready)
        for name, duration in DURATIONS.items():
            pcm = samples(name, 48000, 2)
            self.assertEqual(len(pcm), round(48000*duration)*2)
            self.assertGreater(max(pcm), 500)
            self.assertLess(max(map(abs, pcm)), 32767)
            self.assertLess(abs(pcm[-1]), 10)
            audio.play_effect(name)
            self.assertIn(name, audio.effects)
            self.assertGreater(audio.effects[name].get_num_channels(), 0)
            audio.effects[name].stop()

    def test_capture_and_muting_never_initialize_or_play_effects(self):
        with patch.object(pg.mixer, "init") as init:
            audio = Audio(enabled=False)
            audio.play_effect("beam")
            init.assert_not_called()
        audio = Audio()
        self.addCleanup(audio.close)
        audio.play_effect("beam", False)
        self.assertEqual(audio.effects, {})

    def test_fire_and_impact_cues_are_separate_and_never_replayed(self):
        audio = Mock()
        effect = CombatAnimation("fire", 1, ((0, 0), (2, 0)), 2, "laser", 5,
                                 absorbed=3)
        effect.play_audio(audio, True)
        self.assertEqual([c.args[0] for c in audio.play_effect.call_args_list], ["beam"])
        effect.elapsed = .19
        effect.play_audio(audio, True)
        self.assertEqual([c.args[0] for c in audio.play_effect.call_args_list], ["beam", "impact", "shield"])
        effect.elapsed = .5
        effect.play_audio(audio, True)
        self.assertEqual(audio.play_effect.call_count, 3)

    def test_projectile_launch_has_no_early_impact_and_salvo_sounds_are_bounded(self):
        audio = Mock()
        launch = CombatAnimation("launch_projectile", 1, ((0, 0), (5, 0)), 2, "torpedo")
        launch.elapsed = .5
        launch.play_audio(audio, True)
        self.assertEqual([c.args[0] for c in audio.play_effect.call_args_list], ["launch"])
        flight = dict(impact=True, missed=False, damage=10, absorbed=0, destroyed=True)
        impact = CombatAnimation("ordnance", 0, (), flights=(flight,)*12)
        impact.play_audio(audio, True)
        self.assertEqual(audio.play_effect.call_count, 1)
        impact.elapsed = .4
        impact.play_audio(audio, True)
        self.assertEqual(audio.play_effect.call_count, 3)
        self.assertEqual({c.args[0] for c in audio.play_effect.call_args_list[1:]}, {"impact", "explosion"})

    def test_missed_projectile_has_no_hit_sound(self):
        effect = CombatAnimation("ordnance", 0, (), flights=(dict(impact=True, missed=True, damage=0,
                                 absorbed=0, destroyed=False),), elapsed=1)
        audio = Mock()
        effect.play_audio(audio, True)
        audio.play_effect.assert_not_called()

    def test_campaign_actions_schedule_beam_then_impact_once(self):
        from orion.app import App
        from test_combat import encounter
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), capture=True, skip_intro=True)
            try:
                app.game = encounter()
                app.game.combat.ship(2).x = 7
                app.game.combat.accuracy = False
                app.go('combat')
                app.combat_ship_id, app.combat_target_id = 1, 2
                with patch.object(app.audio, 'play_effect') as play:
                    app.combat_action('fire')
                    self.assertEqual([call.args[0] for call in play.call_args_list], ['beam'])
                    app.time += .25
                    app.update_combat()
                    self.assertEqual([call.args[0] for call in play.call_args_list], ['beam', 'impact'])
                    app.render(); app.render()
                    self.assertEqual(play.call_count, 2)
                    app.time += 2
                    app.update_combat()
                    self.assertEqual(play.call_count, 2)
            finally:
                app.audio.close()


if __name__ == "__main__":
    unittest.main()
