"""Mobile home management using the same workforce and construction controls."""

import pygame as pg
from . import motherships
from .model import PLAYER
from .mothership_art import draw
from .building_art import draw_building_art
from .buildings import BUILDINGS
from .ui import CYAN, GOLD, INK, LINE, MUTED, panel, shorten, text


def draw_overview(app, ship):
    from .planet_view import workforce_panel, construction_panel, empire_stockpile
    game, surface, home = app.game, app.canvas, ship.habitat
    system = game.systems[ship.system_id]
    own = ship.owner == PLAYER and not game.is_observer
    color = app.empire_color(ship.owner)
    text(surface, shorten(home.name, 560, 28, "title"), (24, 12), 28, INK, "title")
    empire_stockpile(app, (676, 8, 740, 38))
    panel(surface, (24, 54, 248, 244))
    text(surface, "WANDERER MOTHERSHIP", (38, 69), 11, GOLD, "mono")
    draw(surface, (148, 147), 1.45, color)
    text(surface, f"{home.population} / 50 B inhabitants", (38, 204), 17, INK)
    text(surface, f"{ship.hull} / {ship.max_hull} hull", (38, 232), 13, CYAN)
    text(surface, "MOBILE HOME · ¼ FLEET SPEED", (38, 272), 10, MUTED, "mono")
    workforce_panel(app, game, home, True)
    construction_panel(app, game, system, home, True)

    panel(surface, (24, 314, 718, 526), (6, 15, 24), color)
    # A procedural starfield keeps this an actual game view at every resolution.
    for i in range(70):
        x, y = 40+(i*137+31)%680, 376+(i*97)%369
        pg.draw.circle(surface, (35+i%28, 49+i%30, 64+i%40), (x, y), 1)
    location = (f"{system.name} → {game.systems[ship.destination].name}" if ship.has_course else f"Anchored at {system.name}")
    text(surface, shorten(location, 680, 22), (43, 333), 22, INK)
    status = (f"Departure queued · {ship.turns_remaining} turns" if ship.departure_pending else
              f"In transit · Arrival in {ship.turns_remaining} turns" if ship.in_transit else
              "Self-sufficient habitat · Protect it with an escort")
    text(surface, status, (44, 369), 14, CYAN)
    if home.ascension_gate:
        from .production import GATE_CHARGE_TURNS
        text(surface, f"Ascension Gate: {home.gate_charge}/{GATE_CHARGE_TURNS}"+(" · charging paused in flight" if ship.in_transit else ""), (44, 397), 12, GOLD)
    draw(surface, (380, 587), 4.8, color)
    text(surface, "Living rings · Hydroponics · Workshops · Research decks", (44, 801), 13, GOLD)

    panel(surface, (758, 314, 658, 526), (10, 22, 31))
    text(surface, "ONBOARD FACILITIES", (780, 334), 12, GOLD, "mono", 1)
    text(surface, f"{len(home.buildings)} built / {home.building_capacity} slots", (1394, 336), 12, MUTED, right=True)
    for index in range(12):
        x, y = 780+(index%3)*206, 373+(index//3)*78
        rect = pg.Rect(x, y, 192, 68)
        panel(surface, rect, (12, 27, 36))
        if index < len(home.buildings):
            identifier = home.buildings[index]
            draw_building_art(surface, identifier, (x+4, y+6, 62, 50))
            text(surface, shorten(BUILDINGS[identifier].name, 118, 12), (x+69, y+15), 12, INK)
            from .economy import building_status
            text(surface, building_status(home, index, game.bonuses_for(ship.owner)), (x+69, y+41), 10, CYAN)
        else:
            text(surface, f"Deck {index+1:02}", (x+15, y+15), 13, MUTED)
            text(surface, "Reserved" if index < home.used_slots else "Available", (x+15, y+42), 11, GOLD if index < home.used_slots else MUTED)
    text(surface, "Food, research, industry and resource output stay aboard.", (780, 700), 13, INK)
    text(surface, "Ship construction and gate charging pause during flight.", (780, 725), 12, MUTED)
    strain = game.strain_report(home)
    text(surface, f"Administration: {strain.total:.1f}% strain · {strain.systems} home systems", (780, 752), 12, MUTED)
    app.button("mothership_facilities", "Manage facilities", (780, 785, 284, 37), lambda: app.go("colony"), enabled=own or game.is_observer)
    app.button("mothership_course", "In transit" if ship.in_transit else "Set course", (1077, 785, 314, 37),
               lambda: app.plot_course(ship.id), enabled=own and not ship.in_transit)
    text(surface, "E: End turn · R: Research · I: Empire · F5: Save", (24, 866), 12, MUTED)
    app.button("planet_return", "Galaxy map", (1210, 851, 206, 42), lambda: app.go("galaxy"), "primary")
