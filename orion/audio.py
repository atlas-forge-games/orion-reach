"""Stream the soundtrack separately from short interface sounds."""

from array import array
import math
from pathlib import Path

import pygame as pg

MUSIC_PATH = Path(__file__).resolve().parent.parent / "assets" / "audio" / "distant-stars.mp3"
MUSIC_TITLE = "Distant Stars"


class Audio:
    def __init__(self, *, enabled=True, music_path=None):
        self.music_path = Path(music_path) if music_path is not None else MUSIC_PATH
        self.ready = False
        self.click = None
        self.effects = {}
        self.started = False
        self.paused = False
        self.music_error = False
        self.disabled = not enabled
        if self.disabled:
            return  # Screenshot mode must never initialize or play audio.
        try:
            pg.mixer.init(frequency=48000, size=-16, channels=2, buffer=1024)
            self.ready = True
        except pg.error:
            return  # A missing audio device must not prevent gameplay.
        try:
            rate, sample_format, channels = pg.mixer.get_init()
            if sample_format == -16:
                frames = max(1, round(rate*.075))
                samples = array("h", (int(2600*math.sin(2*math.pi*660*i/rate)*(1-i/frames)**2)
                                      for i in range(frames) for _ in range(channels)))
                self.click = pg.mixer.Sound(buffer=samples)
        except pg.error:
            pass  # Music can still work if creating the click sound fails.

    @property
    def music_description(self):
        if not self.ready and not self.disabled:
            return "Audio is unavailable on this device."
        if self.music_error:
            return "The music file is missing or could not be played."
        return f"{MUSIC_TITLE} · Plays continuously across screens."

    def apply_music(self, enabled, volume):
        """Apply preferences without restarting a playing or muted track."""
        if not self.ready:
            return
        try:
            if not enabled or volume == 0:
                if self.started and not self.paused:
                    pg.mixer.music.pause()
                    self.paused = True
                return
            if not self.started:
                pg.mixer.music.load(str(self.music_path))
                pg.mixer.music.set_volume(volume/100)
                pg.mixer.music.play(loops=-1, fade_ms=1200)
                self.started = True
            else:
                pg.mixer.music.set_volume(volume/100)
                if self.paused:
                    pg.mixer.music.unpause()
            self.paused = False
            self.music_error = False
        except (pg.error, OSError):
            self.music_error = True

    def play_click(self, enabled):
        if enabled and self.click is not None:
            try:
                self.click.play()
            except pg.error:
                pass

    def play_effect(self, name, enabled=True):
        """Play at most one cue per free channel, without interrupting music."""
        if not enabled or not self.ready:
            return
        from .combat_sounds import DURATIONS, samples
        if name not in DURATIONS:
            return
        try:
            config = pg.mixer.get_init()
            if config is None or config[1] != -16:
                return
            if name not in self.effects:
                self.effects[name] = pg.mixer.Sound(buffer=samples(name, config[0], config[2]))
            channel = pg.mixer.find_channel()
            if channel is not None:
                channel.play(self.effects[name])
        except (pg.error, OSError):
            pass

    def close(self):
        if not self.ready:
            return
        try:
            pg.mixer.music.stop()
            pg.mixer.music.unload()
            if self.click is not None:
                self.click.stop()
            for effect in self.effects.values():
                effect.stop()
        except pg.error:
            pass
        self.ready = self.started = self.paused = False
