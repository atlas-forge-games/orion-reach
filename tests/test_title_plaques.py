"""Engraved title menu assets and keyboard/mouse selection (v0.97.1)."""
from pathlib import Path
import struct

import pytest


TITLE = Path(__file__).resolve().parents[1] / "assets" / "title"
LABELS = ("continue", "new-game", "load-game", "settings", "quit")


@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("variant", ("gold", "blue"))
def test_engravings_are_supplied_for_each_real_menu_label(label, variant):
    path = TITLE / f"plaque-{label}-{variant}-v1.png"
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width >= 442 and height >= 66
    assert data[25] == 6  # RGBA; transparent outside the physical button


def test_blank_skins_are_available_for_future_labels():
    assert (TITLE / "plaque-gold-v1.png").is_file()
    assert (TITLE / "plaque-blue-v1.png").is_file()


def test_pointer_and_keyboard_move_single_selected_plaque(monkeypatch):
    pg = pytest.importorskip("pygame")
    from orion import title_screen

    pg.init()

    class Art:
        def draw(self, app):
            pass

    class Brand:
        def draw_menu_credit(self, surface):
            pass

    class MenuApp:
        def __init__(self):
            self.canvas = pg.Surface((1440, 900))
            self.title_art = Art()
            self.brand = Brand()
            self.game = None
            self.keyboard_mode = False
            self.mouse = (200, 570)  # The second button: Load Game
            self.focus = None
            self.buttons = []
            self.campaign_view = "galaxy"

        def button(self, key, label, rect, action, style="normal"):
            self.buttons.append((key, label, rect, style))

        def go(self, screen):
            pass

        def show_settings(self):
            pass

        def quit_request(self):
            pass

    monkeypatch.setattr(title_screen, "text", lambda *args, **kwargs: None)
    app = MenuApp()
    title_screen.draw_menu(app)
    selected = [key for key, _label, _rect, style in app.buttons
                if style == "title_primary"]
    assert selected == ["load"]
    assert [key for key, *_ in app.buttons][:4] == ["new", "load", "settings", "quit"]

    app.buttons.clear()
    app.keyboard_mode = True
    app.focus = "settings"
    title_screen.draw_menu(app)
    assert [key for key, _label, _rect, style in app.buttons
            if style == "title_primary"] == ["settings"]

    app.buttons.clear()
    app.game = object()
    app.focus = "resume"
    title_screen.draw_menu(app)
    assert app.buttons[0][0:2] == ("resume", "Continue")
    assert [key for key, _label, _rect, style in app.buttons
            if style == "title_primary"] == ["resume"]
