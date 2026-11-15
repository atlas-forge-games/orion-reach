"""Regression checks for v0.97.2 centered plaque engraving."""
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL.Image")
np = pytest.importorskip("numpy")

ASSETS = Path(__file__).resolve().parents[1] / "assets/title"
LABELS = ("continue", "new-game", "load-game", "settings", "quit")


@pytest.mark.parametrize("variant", ("gold", "blue"))
@pytest.mark.parametrize("label", LABELS)
def test_lettering_is_optically_centered(variant, label):
    blank = np.asarray(PIL.open(ASSETS / f"plaque-{variant}-v1.png").convert("RGBA"), dtype=np.int16)
    engraved = np.asarray(PIL.open(ASSETS / f"plaque-{label}-{variant}-v1.png").convert("RGBA"), dtype=np.int16)
    assert blank.shape == engraved.shape == (164, 1080, 4)
    # The blank background is identical. An RGB difference greater than 20
    # detects the engraved lettering rather than the gold/blue decoration.
    pixel_difference = np.abs(engraved[:, :, :3] - blank[:, :, :3]).max(axis=2)
    ys, xs = np.where(pixel_difference > 20)
    assert len(ys) > 1000
    assert 78 <= np.median(ys) <= 85, (label, variant, np.median(ys))
    # All glyphs retain their top common cap line, including the Q descender.
    assert 47 <= ys.min() <= 49
    if label != "quit":
        assert 114 <= ys.max() <= 116
