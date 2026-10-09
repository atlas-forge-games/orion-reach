"""Clickable tactical battlefield, per-ship orders, weapon effects and results."""

from functools import lru_cache
import math
import random

import pygame as pg

from .combat import BEAMS, BOARD_COLUMNS, action_error, in_range, reachable, retreat_destination
from .fleet_art import ship_icon
from .model import PLAYER, RIVAL
from .monsters import MONSTER, MONSTERS
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, RIVAL_COLOR, panel, paragraph, shorten, text

CELL = 56
VISIBLE_ROWS = 10
BOARD = pg.Rect(32, 186, BOARD_COLUMNS*CELL, VISIBLE_ROWS*CELL)


def cell_center(cell, camera_row=0):
    return round(BOARD.x+(cell[0]+.5)*CELL), round(BOARD.y+(cell[1]-camera_row+.5)*CELL)


@lru_cache(maxsize=16)
def background(system_id):
    surface = pg.Surface(BOARD.size)
    surface.fill((5, 12, 22))
    rng = random.Random(4731+system_id)
    for _ in range(190):
        x, y = rng.randrange(BOARD.w), rng.randrange(BOARD.h)
        brightness = rng.randrange(36, 100)
        pg.draw.circle(surface, (brightness//2, brightness*3//4, brightness), (x, y), 1)
    # A dim orbital limb provides depth without obscuring the movement grid.
    for radius in range(250, 228, -1):
        shade = max(4, 18-(radius-228)//2)
        pg.draw.circle(surface, (shade//2, shade, shade+12), (1010, 685), radius, 1)
    return surface


def draw_battlefield(app):
    surface, battle = app.canvas, app.game.combat
    effect = app.combat_animation
    player_turn = battle.status == "active" and battle.active_owner == PLAYER and effect is None
    selected = battle.ship(app.combat_ship_id)
    camera = app.combat_camera_row
    project = lambda cell: cell_center(cell, camera)
    old_clip = surface.get_clip()
    surface.set_clip(BOARD)
    surface.blit(background(battle.system_id), BOARD)
    paths = reachable(battle, selected) if selected and player_turn else {}
    if selected and player_turn and battle.can_fire(selected):
        for x in range(BOARD_COLUMNS):
            for y in range(camera, min(battle.rows, camera+VISIBLE_ROWS)):
                if math.dist((x, y), selected.position) <= selected.weapon_range:
                    pg.draw.rect(surface, (19, 20, 34), (BOARD.x+x*CELL, BOARD.y+(y-camera)*CELL, CELL, CELL))
        pg.draw.circle(surface, (78, 48, 63), project(selected.position), selected.weapon_range*CELL, 1)
    for (x, y), path in paths.items():
        if camera <= y < camera+VISIBLE_ROWS:
            rect = pg.Rect(BOARD.x+x*CELL+1, BOARD.y+(y-camera)*CELL+1, CELL-2, CELL-2)
            pg.draw.rect(surface, (15, 38, 48), rect)
            pg.draw.circle(surface, (58, 100, 110), rect.center, 2)
            app.button(f"combat_cell_{x}_{y}", "", rect, lambda a=x, b=y: app.move_combat_ship(a, b), "hotspot")
            if rect.collidepoint(app.mouse):
                pg.draw.rect(surface, CYAN, rect, 1)
                pg.draw.lines(surface, CYAN, False, [project(p) for p in path], 2)
    for x in range(BOARD_COLUMNS+1):
        pg.draw.line(surface, (22, 34, 45), (BOARD.x+x*CELL, BOARD.top), (BOARD.x+x*CELL, BOARD.bottom))
    for y in range(VISIBLE_ROWS+1):
        pg.draw.line(surface, (22, 34, 45), (BOARD.left, BOARD.y+y*CELL), (BOARD.right, BOARD.y+y*CELL))
    if effect and effect.kind == "move":
        effect.draw(surface, project)
    for ship in battle.ships:
        firing_target = effect and effect.kind == "fire" and effect.target_id == ship.id
        before_impact = firing_target and effect.elapsed < .18
        if ship.hull <= 0 and not before_impact:
            continue
        position = effect.moving_position() if effect and effect.kind == "move" and effect.ship_id == ship.id else ship.position
        cx, cy = project(position)
        if not BOARD.inflate(CELL, CELL).collidepoint(cx, cy):
            continue
        color = MONSTERS[ship.kind].color if ship.owner == MONSTER else CYAN if ship.owner == PLAYER else RIVAL_COLOR
        is_selected = ship.id == app.combat_ship_id
        targetable = bool(selected and player_turn and ship.owner != PLAYER
                          and battle.can_fire(selected) and in_range(selected, ship))
        box = pg.Rect(cx-CELL//2+3, cy-CELL//2+3, CELL-6, CELL-6)
        if is_selected or targetable or ship.id == app.combat_target_id:
            pg.draw.rect(surface, GOLD if is_selected else RED if targetable else FAINT, box, 1, border_radius=6)
        ship_icon(surface, (cx, cy-3), .55, color, kind=ship.kind, facing=1 if ship.owner == PLAYER else -1)
        hull = min(ship.max_hull, ship.hull+(effect.damage if before_impact else 0))
        pg.draw.rect(surface, LINE, (cx-18, cy+19, 36, 3))
        pg.draw.rect(surface, color, (cx-18, cy+19, round(36*hull/ship.max_hull), 3))
        if ship.design and ship.design.shields:
            pg.draw.rect(surface, (79, 169, 255), (cx-18, cy+24, round(36*ship.shields/ship.design.shields), 2))
        text(surface, "GUARD" if ship.owner == MONSTER else f"{ship.id:03}", (cx-19, cy-23), 8, color, "mono")
        if ship.owner == PLAYER and ship.hull > 0:
            for dx, available in ((12, battle.can_move(ship)), (19, battle.can_fire(ship))):
                pg.draw.circle(surface, CYAN if available else LINE, (cx+dx, cy-19), 2)
        if BOARD.contains(box):
            app.button(f"combat_ship_{ship.id}", "", box,
                       lambda side=ship.owner, sid=ship.id: app.select_combat_ship(side, sid), "hotspot",
                       enabled=player_turn and ship.hull > 0)
    if effect and effect.kind == "fire":
        effect.draw(surface, project)
    surface.set_clip(old_clip)
    pg.draw.rect(surface, LINE, BOARD, 1)


def draw_combat(app):
    surface, game, battle = app.canvas, app.game, app.game.combat
    enemy = battle.enemy(PLAYER)
    busy = app.combat_animation is not None
    active = battle.status == "active" or busy
    player_turn = battle.status == "active" and battle.active_owner == PLAYER and not busy
    app.chrome("TACTICAL COMMAND")
    text(surface, shorten(f"Battle of {game.systems[battle.system_id].name}", 670, 32, "title"), (32, 119), 32, INK, "title")
    text(surface, f"ROUND {battle.round:02}  ·  "+("YOUR TURN" if battle.active_owner == PLAYER else "ENEMY TURN" if battle.active_owner else "BATTLE ENDED"),
         (1038, 128), 12, GOLD, "mono", right=True)
    text(surface, "Select your ship → click a highlighted cell to move → click an enemy to fire.", (34, 162), 13, MUTED)
    draw_battlefield(app)

    panel(surface, (1060, 119, 348, 627), (11, 22, 31), GOLD if player_turn else LINE)
    x = 1080
    text(surface, "FLEET STATUS", (x, 137), 10, GOLD, "mono", 1)
    text(surface, f"YOUR SHIPS  {len(battle.fleet(PLAYER))}", (x, 164), 12, CYAN, "mono")
    text(surface, f"ENEMY  {len(battle.fleet(enemy))}", (1388, 164), 12, RIVAL_COLOR, "mono", right=True)
    pg.draw.line(surface, LINE, (x, 193), (1388, 193))
    if active:
        ship, target = battle.ship(app.combat_ship_id), battle.ship(app.combat_target_id)
        text(surface, "SELECTED SHIP", (x, 210), 10, MUTED, "mono", 1)
        if ship:
            ship_icon(surface, (1357, 254), .85, CYAN, kind=ship.kind, facing=1)
            text(surface, shorten(ship.name, 235, 21), (x, 235), 21, INK)
            text(surface, f"HULL  {ship.hull} / {ship.max_hull}", (x, 267), 12, CYAN, "mono")
            if ship.design:
                text(surface, f"SHIELDS {ship.shields}/{ship.design.shields} · PD {ship.design.interception}%", (x, 286), 10, MUTED, "mono")
            for left, title, available, value in ((x, "MOVEMENT", battle.can_move(ship), f"{ship.movement} cells"),
                                                   (1239, "WEAPON", battle.can_fire(ship), "Ready" if ship.damage else "Unarmed")):
                panel(surface, (left, 301, 149, 58))
                text(surface, title, (left+10, 310), 9, MUTED, "mono")
                text(surface, value if available else "Spent" if ship.damage or title == "MOVEMENT" else "Unarmed",
                     (left+10, 329), 15, CYAN if available else FAINT)
            beam = BEAMS[ship.weapon]
            pg.draw.line(surface, beam.color, (x, 383), (x+23, 383), 3)
            text(surface, "Weapon volley" if ship.design else beam.name, (x+34, 371), 17, beam.color)
            text(surface, f"Up to {ship.damage} damage · Range {ship.weapon_range}" if ship.damage else "Move or withdraw with your fleet.",
                 (x, 400), 12, MUTED)
            if ship.design:
                text(surface, "Only weapons in range fire; one volley per turn.", (x, 420), 11, MUTED)
        else:
            paragraph(surface, "Your ships have finished their orders. End your turn to let the opponent act.", (x, 239), 308, 16, MUTED, 26)
        pg.draw.line(surface, LINE, (x, 432), (1388, 432))
        text(surface, "ENEMY TARGET", (x, 449), 10, RIVAL_COLOR, "mono", 1)
        text(surface, shorten(target.name, 308, 18) if target else "Click an enemy ship", (x, 473), 18, INK)
        if target and target.owner == MONSTER:
            ship_icon(surface, (1356, 472), .57, kind=target.kind)
        caption = f"{target.hull}/{target.max_hull} hull · {target.shields} shields" if target else "Targets must be within weapon range."
        if target and ship:
            caption += f"  ·  Distance {math.dist(ship.position, target.position):.1f}"
        text(surface, caption, (x, 503), 12, MUTED)
        can_fire = bool(player_turn and ship and target and action_error(game, PLAYER, ship.id, target.id) is None)
        label = "Fire at target" if can_fire else "Target out of range" if ship and target and ship.damage and not in_range(ship, target) else "Weapon spent" if ship and ship.id in battle.acted else "Unarmed" if ship and not ship.damage else "Select a target"
        app.button("combat_fire", label, (x, 532, 308, 43), lambda: app.combat_action("fire"), enabled=can_fire)
        app.button("combat_next", "Next ship · N", (x, 588, 149, 39), app.next_combat_ship, enabled=player_turn and bool(battle.ready(PLAYER)))
        app.button("combat_hold", "Done ship", (1239, 588, 149, 39), lambda: app.combat_action("hold"),
                   enabled=bool(player_turn and ship and (battle.can_move(ship) or battle.can_fire(ship))))
        app.button("combat_end_turn", "End turn · E", (x, 640, 308, 48), lambda: app.combat_action("end_turn"),
                   "primary" if player_turn else "normal", enabled=player_turn)
        app.button("combat_retreat", "Retreat fleet", (x, 699, 308, 33), app.retreat_request,
                   enabled=player_turn and retreat_destination(game) is not None)
    else:
        title = {"player_victory": "Victory", "rival_victory": "Defeat", "monster_victory": "Defeat",
                 "player_retreat": "Fleet withdrawn", "rival_retreat": "Enemy withdrew"}[battle.status]
        text(surface, title, (x, 221), 29, GOLD, "title")
        lost = {side: sum(s.hull == 0 for s in battle.fleet(side, alive=False)) for side in (PLAYER, enemy)}
        text(surface, f"Your ships lost: {lost[PLAYER]}", (x, 288), 16, CYAN)
        text(surface, f"{'Guardians' if battle.guardian else 'Enemy ships'} lost: {lost[enemy]}", (x, 321), 16, RIVAL_COLOR)
        caption = "Surviving ships remain in orbit. Hull damage is retained; colonies keep their current owners."
        if battle.retreat_destination is not None:
            caption = f"The withdrawing fleet is travelling to {game.systems[battle.retreat_destination].name}. Surviving ships retain their hull damage."
        elif battle.guardian:
            spec = MONSTERS[battle.guardian.kind]
            caption = (f"{spec.reward}. Protected worlds are now open for colonization. Bring colony ships to settle them."
                       if battle.status == "player_victory" else "The guardian still controls this system. Assemble a stronger fleet to claim its worlds.")
            if battle.status == "player_victory" and spec.research_reward:
                caption = f"Ancient ruins recovered: +{spec.research_reward} RP added to your research. The rich world is now open for colonization."
        paragraph(surface, caption, (x, 377), 302, 15, MUTED, 26)
        app.button("combat_continue", "Return to system", (x, 641, 308, 51), app.finish_combat, "primary")

    panel(surface, (32, 763, 1376, 77))
    text(surface, "COMBAT LOG", (48, 778), 10, GOLD, "mono", 1)
    for i, message in enumerate(battle.log[-3:]):
        text(surface, shorten(message, 1120, 12), (233, 773+i*21), 12, INK if i == len(battle.log[-3:])-1 else MUTED)
    app.button("combat_pause", "Menu · Esc", (32, 851, 153, 38), app.pause)
    app.button("combat_save", "Save · F5", (198, 851, 153, 38), app.save_game)
    status = "Firing…" if busy and app.combat_animation.kind == "fire" else "Maneuvering…" if busy else "Enemy is giving orders…" if active and not player_turn else "One move + one shot per ship · Strategic time paused"
    text(surface, status, (372, 863), 12, MUTED)
    if battle.rows > VISIBLE_ROWS:
        text(surface, f"ROWS {app.combat_camera_row+1}–{app.combat_camera_row+VISIBLE_ROWS}/{battle.rows}", (1190, 864), 10, MUTED, "mono", right=True)
        app.button("combat_map_up", "↑", (1206, 851, 90, 38), lambda: app.pan_combat(-3), enabled=app.combat_camera_row > 0)
        app.button("combat_map_down", "↓", (1306, 851, 102, 38), lambda: app.pan_combat(3), enabled=app.combat_camera_row < battle.rows-VISIBLE_ROWS)
