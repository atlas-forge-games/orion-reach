"""Shared contact selector for diplomacy and intelligence."""

from .first_contact import known_opponents
from .ui import MUTED, panel, shorten, text


def draw_rival_selector(app):
    game = app.game
    owner = app.selected_rival_id()
    if owner is None:
        return
    owners = known_opponents(game)
    panel(app.canvas, (818, 124, 558, 46), border=app.empire_color(owner))
    app.button("contact_previous", "←", (824, 129, 44, 36), lambda: app.change_rival(-1), enabled=len(owners)>1)
    app.button("contact_next", "→", (1326, 129, 44, 36), lambda: app.change_rival(1), enabled=len(owners)>1)
    label = f"{owners.index(owner)+1} / {len(owners)}  ·  {game.empire_name_for(owner)}"
    text(app.canvas, shorten(label, 436, 14), (879, 139), 14, app.empire_color(owner))
