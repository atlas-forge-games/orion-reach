"""Clickable tactical battlefield, per-ship orders, weapon effects and results."""

from functools import lru_cache
from collections import Counter
import math
import random

import pygame as pg

from .combat import BEAMS, BOARD_COLUMNS, action_error, accuracy_breakdown, in_range, reachable, retreat_destination, interception
from . import combat_planets
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
    player_turn = app.combat_input_ready()
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
                if math.dist((x, y), selected.position) <= selected.ready_range:
                    pg.draw.rect(surface, (19, 20, 34), (BOARD.x+x*CELL, BOARD.y+(y-camera)*CELL, CELL, CELL))
        pg.draw.circle(surface, (78, 48, 63), project(selected.position), selected.ready_range*CELL, 1)
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
    # Worlds remain after their batteries are destroyed. Draw them underneath
    # ships so the existing movement rules and empty-cell click targets survive.
    for unit in battle.ships:
        planet = combat_planets.planet_for(app.game, unit)
        if planet is None:
            continue
        cx, cy = project(unit.position)
        cell = pg.Rect(cx-CELL//2, cy-CELL//2, CELL, CELL)
        if not BOARD.colliderect(cell):
            continue
        surface.set_clip(BOARD.clip(cell))
        before_impact = effect and effect.kind == "fire" and effect.target_id == unit.id and effect.elapsed < .18
        combat_planets.draw_base(surface, app.game, unit, (cx, cy), app.empire_color(unit.owner),
                                 1 if unit.owner == PLAYER else -1, destroyed=unit.hull <= 0 and not before_impact)
        text(surface, shorten(planet.name, CELL-6, 8), (cx-CELL//2+3, cy-CELL//2), 8, app.empire_color(unit.owner))
        if unit.hull <= 0 and not before_impact:
            text(surface, "BASE LOST", (cx-23, cy+20), 7, MUTED, "mono")
        surface.set_clip(BOARD)
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
        color = MONSTERS[ship.kind].color if ship.owner == MONSTER else app.empire_color(ship.owner)
        is_selected = ship.id == app.combat_ship_id
        targetable = bool(selected and player_turn and ship.owner != PLAYER
                          and battle.can_fire(selected) and in_range(selected, ship))
        box = pg.Rect(cx-CELL//2+3, cy-CELL//2+3, CELL-6, CELL-6)
        if is_selected or targetable or ship.id == app.combat_target_id:
            pg.draw.rect(surface, GOLD if is_selected else RED if targetable else FAINT, box, 1, border_radius=6)
        planetary = combat_planets.planet_for(app.game, ship) is not None
        if not planetary:
            icon_color = BEAMS[ship.weapon].color if ship.kind == "combat_drone" else color
            ship_icon(surface, (cx, cy-3), .55, icon_color, kind=ship.kind, facing=1 if ship.owner == PLAYER else -1)
        hull = min(ship.max_hull, ship.hull+(effect.damage if before_impact else 0))
        hull_y = cy+23 if planetary else cy+19
        pg.draw.rect(surface, LINE, (cx-18, hull_y, 36, 3))
        pg.draw.rect(surface, color, (cx-18, hull_y, round(36*hull/ship.max_hull), 3))
        if ship.max_shields:
            pg.draw.rect(surface, (79, 169, 255), (cx-18, cy+24, round(36*ship.shields/ship.max_shields), 2))
        if not planetary:
            text(surface, "GUARD" if ship.owner == MONSTER else "RAIDER" if ship.owner == "pirates" else "BASE" if ship.kind == "missile_base" else "DRONE" if ship.kind == "combat_drone" else f"{ship.id:03}", (cx-19, cy-23), 8, color, "mono")
        if ship.graviton_slow:
            text(surface, "SLOW", (cx-16, cy+28), 7, BEAMS["graviton"].color, "mono")
        if ship.owner == PLAYER and ship.hull > 0 and not planetary:
            for dx, available in ((12, battle.can_move(ship)), (19, battle.can_fire(ship) or battle.can_launch(ship))):
                pg.draw.circle(surface, CYAN if available else LINE, (cx+dx, cy-19), 2)
        if BOARD.contains(box):
            app.button(f"combat_ship_{ship.id}", "", box,
                       lambda side=ship.owner, sid=ship.id: app.select_combat_ship(side, sid), "hotspot",
                       enabled=player_turn and ship.hull > 0)
    if effect and effect.kind == "fire":
        attacker, target = battle.ship(effect.ship_id), battle.ship(effect.target_id)
        def anchor(unit):
            center = project(unit.position)
            return combat_planets.surface_anchor(center, 1 if unit.owner == PLAYER else -1) if combat_planets.planet_for(app.game, unit) else center
        effect.draw(surface, project, origin=anchor(attacker), target=anchor(target),
                    explosion_scale=.35 if combat_planets.planet_for(app.game, target) else 1.0)
    surface.set_clip(old_clip)
    pg.draw.rect(surface, LINE, BOARD, 1)


def draw_combat(app):
    surface, game, battle = app.canvas, app.game, app.game.combat
    enemy = battle.enemy(PLAYER)
    busy = app.combat_animation is not None
    active = battle.status == "active" or busy
    player_turn = app.combat_input_ready()
    automatic = app.combat_auto and battle.status == "active"
    app.chrome("TACTICAL COMMAND")
    text(surface, shorten(f"Battle of {game.systems[battle.system_id].name}", 670, 32, "title"), (32, 119), 32, INK, "title")
    turn = "YOUR TURN" if battle.active_owner == PLAYER else "ENEMY TURN" if battle.active_owner else "BATTLE ENDED"
    if automatic:
        turn = "AUTO: YOUR FLEET" if battle.active_owner == PLAYER else "AUTO: ENEMY TURN"
    text(surface, f"ROUND {battle.round:02}  ·  "+turn, (1038, 128), 12, CYAN if automatic else GOLD, "mono", right=True)
    instructions = ("Computer controls your fleet: movement, weapons and drones. Choose Take control · A to resume manual orders."
                    if automatic else "Select your ship → click a highlighted cell to move → select a target → review hit chances → Fire.")
    text(surface, instructions, (34, 162), 13, CYAN if automatic else MUTED)
    draw_battlefield(app)

    panel(surface, (1060, 119, 348, 627), (11, 22, 31), GOLD if player_turn else LINE)
    x = 1080
    text(surface, "FLEET STATUS", (x, 137), 10, GOLD, "mono", 1)
    text(surface, f"YOUR UNITS  {len(battle.fleet(PLAYER))}", (x, 164), 12, app.empire_color(PLAYER), "mono")
    text(surface, f"ENEMY  {len(battle.fleet(enemy))}", (1388, 164), 12, RIVAL_COLOR, "mono", right=True)
    pg.draw.line(surface, LINE, (x, 193), (1388, 193))
    if active:
        ship, target = battle.ship(app.combat_ship_id), battle.ship(app.combat_target_id)
        planet = combat_planets.planet_for(game, ship)
        text(surface, "COMPUTER COMMAND" if automatic else "PLANETARY DEFENSE" if planet else "SELECTED SHIP", (x, 210), 10, CYAN if automatic else MUTED, "mono", 1)
        if ship:
            if planet:
                combat_planets.draw_base(surface, game, ship, (1357, 256), app.empire_color(ship.owner), 1, diameter=60)
            else:
                ship_icon(surface, (1357, 254), .85, app.empire_color(ship.owner), kind=ship.kind, facing=1)
            text(surface, shorten(planet.name if planet else ship.name, 235, 21), (x, 235), 21, INK)
            text(surface, f"{'BASE' if planet else 'HULL'}  {ship.hull} / {ship.max_hull}", (x, 267), 12, CYAN, "mono")
            if planet:
                text(surface, "Surface missile base · "+planet.biome, (x, 286), 10, MUTED)
            if ship.design or ship.max_shields:
                text(surface, f"SHIELDS {ship.shields}/{ship.max_shields} · PD {interception(battle, ship)}%", (x, 286), 10, MUTED, "mono")
            for left, title, available, value in ((x, "MOVEMENT", battle.can_move(ship), f"{ship.movement} cells"+(" · −1" if ship.graviton_slow else "")),
                                                   (1239, "LAUNCH / FIRE" if ship.drone_bays else "WEAPON", battle.can_fire(ship) or battle.can_launch(ship),
                                                    "Ready" if ship.damage or ship.drone_bays else "Unarmed")):
                panel(surface, (left, 301, 149, 58))
                text(surface, title, (left+10, 310), 9, MUTED, "mono")
                recharging = title != "MOVEMENT" and ship.damage and not ship.ready_damage and ship.id not in battle.acted
                text(surface, "Fixed to planet" if planet and title == "MOVEMENT" else value if available else "Recharging" if recharging else "Spent" if ship.damage or ship.drone_bays or title == "MOVEMENT" else "Unarmed",
                     (left+10, 329), 15, CYAN if available else FAINT)
            beam = BEAMS[ship.weapon]
            pg.draw.line(surface, beam.color, (x, 383), (x+23, 383), 3)
            text(surface, "Drone bays" if ship.drone_bays and not ship.damage else "Weapon volley" if ship.design else beam.name, (x+34, 371), 17, beam.color)
            text(surface, f"Ready: {ship.ready_damage} damage · Range {ship.ready_range}" if ship.damage else "Launch drones or withdraw with your fleet." if ship.drone_bays else "Move or withdraw with your fleet.",
                 (x, 400), 12, MUTED)
            if ship.drone_bays:
                text(surface, f"DRONES {len(battle.drones(ship))}/{ship.drone_bays*2} active · {ship.drone_reserve} reserve", (x, 420), 11, CYAN)
            elif ship.kind == "combat_drone":
                text(surface, f"Control link: carrier {ship.carrier_id:03}", (x, 420), 11, CYAN)
            elif ship.cooldowns:
                names = ", ".join(BEAMS[w].name for w in ship.cooldowns)
                text(surface, shorten("Recharging: "+names, 308, 11), (x, 420), 11, GOLD)
            elif ship.design and (ship.design.repair_rate or ship.design.shield_regeneration):
                text(surface, f"Repair reserve {ship.repair_remaining} · Shield regen +{ship.design.shield_regeneration}", (x, 420), 11, CYAN)
            elif ship.design:
                text(surface, "Only weapons in range fire; one volley per turn.", (x, 420), 11, MUTED)
        else:
            paragraph(surface, "The computer is managing your fleet's orders and turns." if automatic else "Your ships have finished their orders. End your turn to let the opponent act.", (x, 239), 308, 16, MUTED, 26)
        pg.draw.line(surface, LINE, (x, 432), (1388, 432))
        target_planet = combat_planets.planet_for(game, target)
        text(surface, "PLANETARY TARGET" if target_planet else "ENEMY TARGET", (x, 449), 10, RIVAL_COLOR, "mono", 1)
        text(surface, shorten(combat_planets.unit_name(game, target), 308, 18) if target else "Click an enemy ship or base", (x, 473), 18, INK)
        if target and target.owner == MONSTER:
            ship_icon(surface, (1356, 472), .57, kind=target.kind)
        caption = (f"{target.hull}/{target.max_hull} base hull" if target_planet else f"{target.hull}/{target.max_hull} hull · {target.shields} shields") if target else "Targets must be within weapon range."
        if target and ship:
            caption += f"  ·  Distance {math.dist(ship.position, target.position):.1f}"
        text(surface, caption, (x, 503), 12, MUTED)
        can_fire = bool(player_turn and ship and target and action_error(game, PLAYER, ship.id, target.id) is None)
        label = "Fire at target" if can_fire else "Weapons recharging" if ship and ship.damage and not ship.ready_damage else "Target out of range" if ship and target and ship.damage and not in_range(ship, target) else "Weapon spent" if ship and ship.id in battle.acted else "Unarmed" if ship and not ship.damage else "Select a target"
        text(surface, "HIT CHANCE · aim − range − evade − tracking" if battle.accuracy else "LEGACY BATTLE · Guaranteed hits", (x, 525), 9, GOLD)
        if ship and target and in_range(ship, target):
            groups = list(Counter(w for w, _ in ship.volley(target)).items())
            limit = 3 if ship.drone_bays else 4
            for index, (weapon, count) in enumerate(groups[:limit]):
                if index == limit-1 and len(groups) > limit:
                    text(surface, f"+ {len(groups)-index} other weapon types in this volley", (x, 542+index*14), 10, MUTED)
                    break
                chance = accuracy_breakdown(game, ship, target, weapon)
                shot_label = (f"{count*BEAMS[weapon].shots}× {BEAMS[weapon].name}: {chance['chance']}%  "
                         f"(tracking −{chance['tracking']})")
                text(surface, shot_label, (x, 542+index*14), 10, CYAN)
        else:
            text(surface, "Choose an enemy within weapon range.", (x, 546), 11, MUTED)
        if ship and ship.drone_bays:
            roles = battle.available_drone_roles(ship)
            if getattr(app, "combat_drone_role", None) not in roles:
                app.combat_drone_role = next(iter(roles), None)
            for index, role in enumerate(ship.drone_bay_counts):
                app.button("combat_drone_"+role, role.title(), (x+index*103, 579, 97, 18),
                           lambda r=role: setattr(app, "combat_drone_role", r),
                           "tab_active" if role == app.combat_drone_role else "tab", enabled=player_turn and role in roles)
            app.button("combat_fire", "Fire guns", (x, 601, 130, 35), lambda: app.combat_action("fire"), enabled=can_fire)
            app.button("combat_launch", "Launch drones", (1220, 601, 168, 35), lambda: app.combat_action("launch"),
                       enabled=bool(player_turn and battle.can_launch(ship, app.combat_drone_role)))
        else:
            app.button("combat_fire", label, (x, 601, 308, 35), lambda: app.combat_action("fire"), enabled=can_fire)
        app.button("combat_next", "Next ship · N", (x, 646, 149, 32), app.next_combat_ship, enabled=player_turn and bool(battle.ready(PLAYER)))
        app.button("combat_hold", "Done ship", (1239, 646, 149, 32), lambda: app.combat_action("hold"),
                   enabled=bool(player_turn and ship and (battle.can_move(ship) or battle.can_fire(ship) or battle.can_launch(ship))))
        app.button("combat_end_turn", "End turn · E", (x, 688, 308, 35), lambda: app.combat_action("end_turn"),
                   "primary" if player_turn else "normal", enabled=player_turn)
        app.button("combat_retreat", "Retreat fleet", (x, 730, 308, 23), app.retreat_request,
                   enabled=player_turn and retreat_destination(game) is not None)
    else:
        title = ("Victory" if battle.status == "player_victory" else "Fleet withdrawn" if battle.status == "player_retreat"
                 else "Enemy withdrew" if battle.status.endswith("_retreat") else "Defeat")
        text(surface, title, (x, 221), 29, GOLD, "title")
        lost = {side: sum(s.hull == 0 and s.kind not in ("combat_drone", "missile_base", "mothership") for s in battle.fleet(side, alive=False)) for side in (PLAYER, enemy)}
        text(surface, f"Your ships lost: {lost[PLAYER]}", (x, 288), 16, CYAN)
        text(surface, f"{'Guardians' if battle.guardian else 'Enemy ships'} lost: {lost[enemy]}", (x, 321), 16, RIVAL_COLOR)
        details_y = 350
        disabled = sum(s.kind == "mothership" and s.hull == 0 for s in battle.ships)
        if disabled:
            text(surface, f"{disabled} motherships disabled · 3-turn repair window", (x, details_y), 11, GOLD)
            details_y += 27
        if any(s.kind == "missile_base" for s in battle.ships):
            bases_lost = {side: sum(s.hull == 0 and s.kind == "missile_base" for s in battle.fleet(side, alive=False)) for side in (PLAYER, enemy)}
            text(surface, f"Missile bases lost: {bases_lost[PLAYER]} yours · {bases_lost[enemy]} enemy", (x, details_y), 12, MUTED)
            details_y += 27
        if any(s.drone_bays for s in battle.ships):
            text(surface, "Surviving drones return to their carriers.", (x, details_y), 11, MUTED)
            details_y += 27
        caption = "Surviving ships remain in orbit. Hull damage is retained; colonies keep their current owners."
        if battle.retreat_destination is not None:
            caption = f"The withdrawing fleet is travelling to {game.system_name(battle.retreat_destination)}. Surviving ships retain their hull damage."
        elif battle.encounter_id is not None:
            caption = ("Pirates defeated. Their bounty and recovered stores have been added to your reserves. Return to the system to review any remaining threats."
                       if battle.status == "player_victory" else "The pirate fleet remains. Surviving raiders retain their hull damage; bring a stronger escort.")
        elif battle.guardian:
            spec = MONSTERS[battle.guardian.kind]
            caption = (f"{spec.reward}. Protected worlds are now open for colonization. Bring colony ships to settle them."
                       if battle.status == "player_victory" else "The guardian still controls this system. Assemble a stronger fleet to claim its worlds.")
            from . import black_holes
            if site := black_holes.at(game, battle.system_id):
                caption = (f"Recovered {black_holes.RELICS[site.relic_id].name}. View it in Info → Legendary artifacts. Placement and bonuses remain planned."
                           if battle.status == "player_victory" else "The legendary guardian still protects the relic. A retreat or defeat earns no reward.")
            if battle.status == "player_victory" and spec.research_reward:
                caption = f"Ancient ruins recovered: +{spec.research_reward} RP added to your research. The rich world is now open for colonization."
        if disabled:
            caption = "Open a disabled mothership in the system view to board it with troop transports, raid its stores or destroy it for salvage."
        paragraph(surface, caption, (x, max(377, details_y)), 302, 15, MUTED, 26)
        app.button("combat_continue", "Return to system", (x, 641, 308, 51), app.finish_combat, "primary")

    panel(surface, (32, 763, 1376, 77))
    text(surface, "COMBAT LOG", (48, 778), 10, GOLD, "mono", 1)
    for i, message in enumerate(battle.log[-3:]):
        text(surface, shorten(message, 1120, 12), (233, 773+i*21), 12, INK if i == len(battle.log[-3:])-1 else MUTED)
    app.button("combat_pause", "Menu · Esc", (32, 851, 153, 38), app.pause)
    app.button("combat_save", "Save · F5", (198, 851, 153, 38), app.save_game)
    if active:
        app.button("combat_auto", "Take control · A" if automatic else "Auto combat · A", (364, 851, 218, 38),
                   app.toggle_combat_auto, "primary" if automatic else "normal", enabled=battle.status == "active")
    status = ("Firing…" if busy and app.combat_animation.kind == "fire" else "Maneuvering…" if busy
              else "Computer is giving your fleet orders…" if automatic and battle.active_owner == PLAYER
              else "Enemy is giving orders…" if battle.status == "active" and battle.active_owner != PLAYER
              else "Battle ended · Review the result to continue" if not active
              else "One move + one shot per ship · Strategic time paused")
    text(surface, shorten(status, 454, 12), (600 if active else 372, 863), 12, CYAN if automatic else MUTED)
    if battle.rows > VISIBLE_ROWS:
        text(surface, f"ROWS {app.combat_camera_row+1}–{app.combat_camera_row+VISIBLE_ROWS}/{battle.rows}", (1190, 864), 10, MUTED, "mono", right=True)
        app.button("combat_map_up", "↑", (1206, 851, 90, 38), lambda: app.pan_combat(-3), enabled=app.combat_camera_row > 0)
        app.button("combat_map_down", "↓", (1306, 851, 102, 38), lambda: app.pan_combat(3), enabled=app.combat_camera_row < battle.rows-VISIBLE_ROWS)
