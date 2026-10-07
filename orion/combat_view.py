"""A compact tactical screen with opposing formations and alternating activations."""

import pygame as pg

from .combat import retreat_destination
from .fleet_art import ship_icon
from .model import PLAYER, RIVAL
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED, RIVAL_COLOR, panel, paragraph, shorten, text

SHIPS_PER_PAGE = 4


def draw_combat(app):
    surface, game = app.canvas, app.game
    battle = game.combat
    active = battle.status == "active"
    player_turn = active and battle.active_owner == PLAYER
    app.chrome("TACTICAL COMMAND")
    text(surface, "FLEET ENGAGEMENT", (65, 142), 11, GOLD, "mono", 2)
    text(surface, f"YEAR {game.year} · TURN {game.turn} · STRATEGIC TIME PAUSED", (1376, 142), 11, MUTED, "mono", right=True)
    text(surface, shorten(f"Battle of {game.systems[battle.system_id].name}", 1200, 43, "title"), (64, 190), 43, INK, "title")
    text(surface, "Select a ship and an enemy target. Each ship acts once per round; sides alternate activations.", (66, 253), 14, MUTED)

    for owner, x, color in ((PLAYER, 64, CYAN), (RIVAL, 898, RIVAL_COLOR)):
        fleet = battle.fleet(owner, alive=False)
        last = max(0, (len(fleet)-1)//SHIPS_PER_PAGE)
        page = app.combat_pages[owner] = min(max(0, app.combat_pages[owner]), last)
        text(surface, shorten(game.empire_name_for(owner), 334, 18), (x, 292), 18, color)
        text(surface, f"{len(battle.fleet(owner))}/{len(fleet)} SHIPS", (x+477, 298), 10, MUTED, "mono", right=True)
        for index, ship in enumerate(fleet[page*SHIPS_PER_PAGE:(page+1)*SHIPS_PER_PAGE]):
            y = 326+index*86
            selected = ship.id == (app.combat_ship_id if owner == PLAYER else app.combat_target_id)
            ready = ship.hull > 0 and ship.id not in battle.acted
            border = GOLD if selected and ship.hull else LINE
            panel(surface, (x, y, 478, 76), (19, 35, 43) if selected else PANEL, border)
            ship_icon(surface, (x+53, y+36), .9, color if ship.hull else FAINT,
                      kind=ship.kind, facing=1 if owner == PLAYER else -1)
            text(surface, ship.name, (x+101, y+10), 17, INK if ship.hull else FAINT)
            caption = "DESTROYED" if not ship.hull else "ACTED" if not ready else "UNARMED" if not ship.damage else "READY"
            text(surface, caption, (x+460, y+14), 9, RED if not ship.hull else color if ready else FAINT, "mono", right=True)
            text(surface, f"{ship.hull}/{ship.max_hull} hull · {ship.damage} damage", (x+102, y+36), 11, MUTED)
            pg.draw.rect(surface, LINE, (x+102, y+60, 357, 4))
            if ship.hull:
                pg.draw.rect(surface, color, (x+102, y+60, round(357*ship.hull/ship.max_hull), 4))
            app.button(f"combat_ship_{ship.id}", "", (x, y, 478, 76),
                       lambda sid=ship.id, side=owner: app.select_combat_ship(side, sid), "hotspot",
                       enabled=player_turn and (ready if owner == PLAYER else ship.hull > 0))
        text(surface, f"PAGE {page+1}/{last+1}", (x+1, 690), 10, FAINT, "mono")
        app.button(f"combat_{owner}_previous", "← Prev", (x+217, 678, 121, 32),
                   lambda side=owner: app.change_combat_page(side, -1), enabled=page > 0)
        app.button(f"combat_{owner}_next", "Next →", (x+352, 678, 126, 32),
                   lambda side=owner: app.change_combat_page(side, 1), enabled=page < last)

    panel(surface, (564, 294, 312, 366), (12, 25, 34), GOLD if player_turn else LINE)
    text(surface, f"ROUND {battle.round:02}", (583, 312), 11, GOLD, "mono", 2)
    if active:
        text(surface, "Your activation" if player_turn else "Opponent's activation", (582, 340), 21, INK)
        text(surface, "Choose a ship, then a target." if player_turn else "The enemy is choosing an action.",
             (584, 378), 12, MUTED)
        ship, target = battle.ship(app.combat_ship_id), battle.ship(app.combat_target_id)
        text(surface, "YOUR SELECTED SHIP", (584, 420), 9, CYAN, "mono", 1)
        text(surface, ship.name if ship else "Waiting for next round", (583, 439), 17, INK if ship else MUTED)
        text(surface, "ENEMY TARGET", (584, 477), 9, RIVAL_COLOR, "mono", 1)
        text(surface, target.name if target else "Choose an enemy ship", (583, 496), 17, INK if target else MUTED)
        can_fire = bool(player_turn and ship and ship.damage and target and target.hull)
        label = f"Fire · {ship.damage} damage" if ship and ship.damage else "Unarmed transport"
        app.button("combat_fire", label, (582, 538, 276, 53), lambda: app.combat_action("fire"),
                   "primary" if can_fire else "normal", enabled=can_fire)
        app.button("combat_hold", "Hold", (582, 608, 130, 36), lambda: app.combat_action("hold"),
                   enabled=player_turn and ship is not None)
        app.button("combat_retreat", "Retreat", (725, 608, 133, 36), app.retreat_request,
                   enabled=player_turn and retreat_destination(game) is not None)
    else:
        title = {"player_victory": "Victory", "rival_victory": "Defeat",
                 "player_retreat": "Fleet withdrawn", "rival_retreat": "Enemy withdrew"}[battle.status]
        text(surface, title, (582, 347), 27, GOLD, "title")
        lost = {side: sum(s.hull == 0 for s in battle.fleet(side, alive=False)) for side in (PLAYER, RIVAL)}
        text(surface, f"Your ships lost: {lost[PLAYER]}", (584, 402), 14, CYAN)
        text(surface, f"Enemy ships lost: {lost[RIVAL]}", (584, 431), 14, RIVAL_COLOR)
        caption = "Surviving ships remain in orbit. Hull damage is retained; colonies keep their current owners."
        if battle.retreat_destination is not None:
            destination = game.systems[battle.retreat_destination].name
            caption = f"The withdrawing fleet is travelling to {destination}. Surviving ships retain their hull damage."
        paragraph(surface, caption, (584, 474), 267, 13, MUTED, 21)
        app.button("combat_continue", "Return to system", (582, 588, 276, 53), app.finish_combat, "primary")

    panel(surface, (64, 725, 1312, 91))
    text(surface, "COMBAT LOG", (85, 741), 10, GOLD, "mono", 1)
    for index, message in enumerate(battle.log[-3:]):
        text(surface, shorten(message, 1088, 13), (253, 738+index*24), 13, INK if index == len(battle.log[-3:])-1 else MUTED)
    app.button("combat_pause", "Menu · Esc", (64, 835, 163, 44), app.pause)
    app.button("combat_save", "Save · F5", (241, 835, 172, 44), app.save_game)
    text(surface, "Fixed damage · No range limits · Hold uses an action · Retreat moves the whole fleet", (445, 849), 12, MUTED)
