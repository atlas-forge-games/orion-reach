"""Clickable tactical battlefield, per-ship orders, weapon effects and results."""

from functools import lru_cache
from collections import Counter
import math
import random

import pygame as pg

from .combat import BEAMS, BOARD_COLUMNS, action_error, accuracy_breakdown, in_range, reachable, retreat_destination, interception
from . import combat_planets, fleet_support, combat_projectiles, combat_camera, flagships, projectile_art, combat_geometry as geometry
from .combat_camera import CELL, VISIBLE_ROWS, BOARD
from .fleet_art import ship_icon, load_ship_art, ship_sprite
from .model import PLAYER, RIVAL
from .monsters import MONSTER, MONSTERS
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, RIVAL_COLOR, panel, paragraph, shorten, text

SHIP_LENGTHS = {"combat_drone": 13, "scout": 19, "frigate": 25, "destroyer": 32,
                "cruiser": 39, "carrier": 44, "battleship": 47, "titan": 52,
                "mothership": 53, "colony_ship": 31, "outpost_ship": 29, "troop_transport": 30}
SUPPORT_COLORS = {"escort_interception": (95, 236, 205), "command_accuracy": (108, 169, 255),
                  "jamming": (204, 144, 255)}


@lru_cache(maxsize=256)
def tactical_sprite(kind, color, facing, cell_size=CELL, footprint=(1, 1)):
    """Scale original artwork directly to the zoomed hull, never enlarge an icon."""
    length = SHIP_LENGTHS.get(kind, 50)*cell_size/56
    width, height = footprint
    max_width = length if width == 1 else (width-.2)*cell_size
    max_height = min(38*cell_size/CELL, length) if height == 1 else (height-.5)*cell_size
    source = load_ship_art(kind)
    if source is not None:
        sw, sh = source.get_size()
        oriented_w, oriented_h = (sh, sw) if facing else (sw, sh)
        ratio = min(max_width/oriented_w, max_height/oriented_h)
        sprite = ship_sprite(kind, max(1, round(sh*ratio)), facing).copy()
        # Paint ownership lights at screen resolution after the single rescale.
        if kind != "mothership":
            cx, cy = sprite.get_rect().center
            marker = (round(cx-sprite.get_width()*.38*facing), cy) if facing else (cx, round(sprite.get_height()*.88))
            pg.draw.circle(sprite, color, marker, max(1, round(1.5*cell_size/CELL)))
        return sprite
    # Procedural guardians and missing-asset fallbacks are drawn large first.
    paint_scale = max(1.0, 2*max(max_width, max_height)/60)
    edge = math.ceil(100*paint_scale)
    art = pg.Surface((edge, edge), pg.SRCALPHA)
    ship_icon(art, (edge//2, edge//2), paint_scale, color, kind=kind, facing=facing)
    bounds = art.get_bounding_rect(min_alpha=16)
    if not bounds.w or not bounds.h:
        return pg.Surface((1, 1), pg.SRCALPHA)
    ratio = min(max_width/bounds.w, max_height/bounds.h)
    return pg.transform.smoothscale(art.subsurface(bounds),
                                   (max(1, round(bounds.w*ratio)), max(1, round(bounds.h*ratio))))


def draw_support_ranges(surface, battle, selected, project, scale=1):
    if selected is None or selected.hull <= 0:
        return
    for key, _, radius in fleet_support.auras(selected):
        if not battle.accuracy and key != "escort_interception":
            continue
        color = SUPPORT_COLORS[key]
        pg.draw.circle(surface, color, project(geometry.center(selected)), round(radius*CELL*scale), 1)
        for ally in battle.fleet(selected.owner):
            if (ally.id != selected.id and fleet_support.eligible(ally, key)
                    and math.dist(geometry.center(ally), geometry.center(selected)) <= radius):
                pg.draw.circle(surface, color, project(geometry.center(ally)), round(23*scale), 1)
    # Selecting a supported ship also shows the providers it depends on.
    for key in fleet_support.EFFECTS:
        if not battle.accuracy and key != "escort_interception":
            continue
        for source, _ in fleet_support.sources(battle, selected, key):
            pg.draw.line(surface, tuple(c//2 for c in SUPPORT_COLORS[key]),
                         project(geometry.center(source)), project(geometry.center(selected)), 1)
    if battle.accuracy and (leader := flagships.source(battle, selected)):
        pg.draw.line(surface, (55, 87, 108), project(geometry.center(leader)), project(geometry.center(selected)), 1)


def draw_flagship_auras(app, battle, camera):
    """Quiet, always-visible command coverage; follows movement and camera zoom."""
    overlay = pg.Surface(BOARD.size, pg.SRCALPHA)
    leaders = {ship.id for owner in battle.sides if (ship := flagships.select(battle, owner))}
    for identifier in leaders:
        ship = battle.ship(identifier)
        effect = app.combat_animation
        position = (effect.moving_position() if effect and effect.kind == "move"
                    and effect.ship_id == ship.id else ship.position)
        cx, cy = camera.project(geometry.center(ship, position))
        centre = cx-BOARD.x, cy-BOARD.y
        color = tuple(app.empire_color(ship.owner))
        selected = ship.id == app.combat_ship_id
        radius = round(flagships.radius(ship)*camera.cell_size)
        pg.draw.circle(overlay, (*color, 12 if selected else 7), centre, radius)
        pg.draw.circle(overlay, (*color, 74 if selected else 42), centre, radius, 1)
        pg.draw.circle(overlay, (*color, 30), centre, max(1, round(24*camera.zoom)))
        pg.draw.circle(overlay, (*color, 95), centre, max(1, round(24*camera.zoom)), 1)
    app.canvas.blit(overlay, BOARD)
    return leaders


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


def movement_targets(ship, paths):
    """Map reachable hull cells to placements by their exposed leading edge."""
    targets, scores = {}, {}
    width, height = geometry.size(ship)
    for destination, path in paths.items():
        cx, cy = geometry.center(ship, destination)
        # Use the edge entering new cells, so a one-cell move stays clickable
        # even when a faster ship could place its centre under the same pointer.
        if destination[0] != ship.x:
            cx = destination[0]+(width-1 if destination[0] > ship.x else 0)
        if destination[1] != ship.y:
            cy = destination[1]+(height-1 if destination[1] > ship.y else 0)
        for cell in geometry.cells(ship, destination):
            score = ((cell[0]-cx)**2+(cell[1]-cy)**2, len(path), destination)
            if cell not in scores or score < scores[cell]:
                targets[cell], scores[cell] = destination, score
    return targets


def draw_movement_preview(surface, ship, destination, path, camera):
    """Show the exact landing footprint, including cells over the current hull."""
    scale = camera.zoom
    pg.draw.lines(surface, CYAN, False,
                  [camera.project(geometry.center(ship, point)) for point in path],
                  max(1, round(2*scale)))
    overlay = pg.Surface(BOARD.size, pg.SRCALPHA)
    for cell in geometry.cells(ship, destination):
        rect = camera.cell_rect(cell, inset=max(1, round(scale))).move(-BOARD.x, -BOARD.y)
        pg.draw.rect(overlay, (*CYAN, 38), rect)
        pg.draw.rect(overlay, (*CYAN, 145), rect, max(1, round(scale)))
    surface.blit(overlay, BOARD)
    pg.draw.rect(surface, CYAN, camera.ship_rect(ship, destination, inset=max(1, round(scale))),
                 max(1, round(2*scale)))


def draw_battlefield(app):
    surface, battle = app.canvas, app.game.combat
    combat_camera.clamp(app)
    camera = combat_camera.view(app)
    project, scale = camera.project, camera.zoom
    size = lambda value: max(1, round(value*scale))
    offset = lambda value: round(value*scale)
    effect = app.combat_animation
    player_turn = app.combat_input_ready()
    selected = battle.ship(app.combat_ship_id)
    old_clip = surface.get_clip()
    surface.set_clip(BOARD)
    surface.blit(background(battle.system_id), BOARD)
    paths = reachable(battle, selected) if selected and player_turn else {}
    if selected and player_turn and battle.can_fire(selected):
        for x in camera.columns():
            for y in camera.rows(battle.rows):
                if math.dist((x, y), geometry.nearest(selected, (x, y))) <= selected.ready_range:
                    pg.draw.rect(surface, (19, 20, 34), camera.cell_rect((x, y)))
        reach = round(selected.ready_range*camera.cell_size)
        footprint = camera.ship_rect(selected)
        margin = round((selected.ready_range-.5)*camera.cell_size)
        pg.draw.rect(surface, (78, 48, 63), footprint.inflate(2*margin, 2*margin),
                     1, border_radius=reach)
    targets = movement_targets(selected, paths) if paths else {}
    current_cells = set(geometry.cells(selected)) if selected else set()
    move_preview = None
    for cell, destination in targets.items():
        rect = camera.cell_rect(cell, inset=size(1))
        if BOARD.colliderect(rect):
            pg.draw.rect(surface, (15, 38, 48), rect)
            # The current hull remains selectable. Its exposed destination
            # edges provide movement targets even when the hulls overlap.
            if cell in current_cells:
                continue
            app.button(f"combat_cell_{cell[0]}_{cell[1]}", "", BOARD.clip(rect),
                       lambda point=destination: app.move_combat_ship(*point), "hotspot")
            if rect.collidepoint(app.mouse):
                move_preview = destination
    start = camera.cell_rect((0, 0)).topleft
    end = camera.cell_rect((BOARD_COLUMNS-1, battle.rows-1)).bottomright
    for x in range(max(0, math.floor(camera.x)), min(BOARD_COLUMNS, math.ceil(camera.x+camera.width))+1):
        line_x = camera.cell_rect((x, 0)).x
        pg.draw.line(surface, (22, 34, 45), (line_x, start[1]), (line_x, end[1]))
    for y in range(max(0, math.floor(camera.y)), min(battle.rows, math.ceil(camera.y+camera.height))+1):
        line_y = camera.cell_rect((0, y)).y
        pg.draw.line(surface, (22, 34, 45), (start[0], line_y), (end[0], line_y))
    draw_support_ranges(surface, battle, selected, project, scale)
    flag_ids = draw_flagship_auras(app, battle, camera)
    preview_target = battle.ship(app.combat_target_id)
    if (selected and preview_target and player_turn and preview_target.hull > 0
            and any(not BEAMS[w].projectile for w, _, _ in selected.ready_weapons)):
        obstacle = geometry.blocker(battle, selected, preview_target)
        if obstacle:
            start, _ = geometry.firing_points(selected, preview_target)
            stop = geometry.nearest(obstacle, start)
            pg.draw.line(surface, (163, 71, 65), project(start), project(stop), size(1))
            pg.draw.rect(surface, (163, 71, 65), camera.ship_rect(obstacle, inset=size(2)), size(1))
    # Planets remain on the battlefield after their batteries are destroyed.
    for unit in battle.ships:
        planet = combat_planets.planet_for(app.game, unit)
        if planet is None:
            continue
        cx, cy = project(unit.position)
        cell = camera.cell_rect(unit.position)
        if not BOARD.colliderect(cell):
            continue
        surface.set_clip(BOARD.clip(cell))
        before_impact = effect and effect.pre_impact_damage(unit.id) is not None
        combat_planets.draw_base(surface, app.game, unit, (cx, cy), app.empire_color(unit.owner),
                                 1 if unit.owner == PLAYER else -1, diameter=40*scale,
                                 destroyed=unit.hull <= 0 and not before_impact)
        text(surface, shorten(planet.name, cell.w-size(6), max(6, size(8))),
             (cell.x+size(3), cell.y), max(6, size(8)), app.empire_color(unit.owner))
        if unit.hull <= 0 and not before_impact:
            text(surface, "BASE LOST", (cx-offset(19), cy+offset(10)), max(5, size(6)), MUTED, "mono")
        surface.set_clip(BOARD)
    if effect and effect.kind == "move":
        moving_ship = battle.ship(effect.ship_id)
        effect.draw(surface, lambda point: project(geometry.center(moving_ship, point)))
    for ship in battle.ships:
        pending_damage = effect.pre_impact_damage(ship.id) if effect else None
        before_impact = pending_damage is not None
        if ship.hull <= 0 and not before_impact:
            continue
        position = effect.moving_position() if effect and effect.kind == "move" and effect.ship_id == ship.id else ship.position
        cell = camera.ship_rect(ship, position)
        if not BOARD.colliderect(cell):
            continue
        cx, cy = project(geometry.center(ship, position))
        color = MONSTERS[ship.kind].color if ship.owner == MONSTER else app.empire_color(ship.owner)
        is_selected = ship.id == app.combat_ship_id
        targetable = bool(selected and player_turn and ship.owner != PLAYER
                          and battle.can_fire(selected) and in_range(selected, ship, battle))
        box = camera.ship_rect(ship, position, inset=size(3))
        if is_selected or targetable or ship.id == app.combat_target_id:
            pg.draw.rect(surface, GOLD if is_selected else RED if targetable else FAINT, box, 1, border_radius=size(6))
        planetary = combat_planets.planet_for(app.game, ship) is not None
        if not planetary:
            icon_color = BEAMS[ship.weapon].color if ship.kind == "combat_drone" else color
            sprite = tactical_sprite(ship.kind, tuple(icon_color), 1 if ship.owner == PLAYER else -1,
                                     camera.cell_size, geometry.size(ship))
            surface.blit(sprite, sprite.get_rect(center=(cx, cy-offset(1))))
        hull = min(ship.max_hull, ship.hull+(pending_damage if before_impact else 0))
        hull_y = cy+offset(17) if planetary else cell.bottom-size(11)
        pg.draw.rect(surface, LINE, (cx-offset(18), hull_y, size(36), size(3)))
        pg.draw.rect(surface, color, (cx-offset(18), hull_y, round(size(36)*hull/ship.max_hull), size(3)))
        if ship.max_shields:
            pg.draw.rect(surface, (79, 169, 255), (cx-offset(18), hull_y+size(4),
                         round(size(36)*ship.shields/ship.max_shields), size(2)))
        if not planetary:
            label = "GUARD" if ship.owner == MONSTER else "RAIDER" if ship.owner == "pirates" else "DRONE" if ship.kind == "combat_drone" else f"{ship.id:03}"
            text(surface, label, (cell.x+size(4), cell.y+size(3)), max(5, size(7)), color, "mono")
        if ship.id in flag_ids:
            pole = cell.right-size(23), cell.y+size(4)
            pg.draw.line(surface, color, pole, (pole[0], pole[1]+size(9)), size(1))
            pg.draw.polygon(surface, color, (pole, (pole[0]+size(6), pole[1]+size(2)),
                                            (pole[0], pole[1]+size(5))))
        if ship.graviton_slow:
            text(surface, "SLOW", (cx-offset(17), cy+offset(4)), max(5, size(7)), BEAMS["graviton"].color, "mono")
        for index, (key, _, _) in enumerate(fleet_support.auras(ship)):
            pg.draw.circle(surface, SUPPORT_COLORS[key], (cell.x+size(8+index*6), cell.bottom-size(6)), size(2))
        if ship.owner == PLAYER and ship.hull > 0 and not planetary:
            for dx, available in ((12, battle.can_move(ship)), (19, battle.can_fire(ship) or battle.can_launch(ship))):
                pg.draw.circle(surface, CYAN if available else LINE, (cell.right-size(25-dx), cell.y+size(10)), size(2))
        if BOARD.colliderect(box):
            app.button(f"combat_ship_{ship.id}", "", BOARD.clip(box),
                       lambda side=ship.owner, sid=ship.id: app.select_combat_ship(side, sid), "hotspot",
                       enabled=player_turn and ship.hull > 0)
    moving = {f["id"] for f in effect.flights} if effect and effect.kind == "ordnance" else set()
    for shot in battle.projectiles:
        if shot.id in moving:
            continue
        target = battle.ship(shot.target_id)
        position = project(shot.position)
        if not BOARD.inflate(size(30), size(30)).collidepoint(position):
            continue
        shade = BEAMS[shot.weapon].color
        target_center = geometry.nearest(target, shot.position)
        projectile_art.draw(surface, position, (target_center[0]-shot.x, target_center[1]-shot.y),
                            shot.weapon, zoom=scale, phase=app.time*12+shot.id)
        if {shot.source_id, shot.target_id} & {app.combat_ship_id, app.combat_target_id}:
            text(surface, f"~{combat_projectiles.eta(shot, target)}r",
                 (position[0]+size(5), position[1]-size(14)), max(7, size(9)), shade, "mono")
    def anchor(unit):
        center = project(geometry.center(unit))
        return (combat_planets.surface_anchor(center, 1 if unit.owner == PLAYER else -1, diameter=40*scale)
                if combat_planets.planet_for(app.game, unit) else center)
    if effect and effect.kind == "ordnance":
        anchors = {unit.id: anchor(unit) for unit in battle.ships if combat_planets.planet_for(app.game, unit)}
        effect.draw(surface, project, explosion_scale=scale*CELL/56, anchors=anchors,
                    planet_explosion_scale=.35*scale, projectile_zoom=scale,
                    live_projectile_ids={shot.id for shot in battle.projectiles})
    if effect and effect.kind in ("fire", "launch_projectile"):
        attacker, target = battle.ship(effect.ship_id), battle.ship(effect.target_id)
        effect.draw(surface, project,
                    origin=anchor(attacker) if combat_planets.planet_for(app.game, attacker) else project(effect.path[0]),
                    target=anchor(target) if combat_planets.planet_for(app.game, target) else project(effect.path[1]),
                    explosion_scale=scale*(.35 if combat_planets.planet_for(app.game, target) else
                                           SHIP_LENGTHS.get(target.kind, 50)/47), projectile_zoom=scale)
    if move_preview is not None:
        draw_movement_preview(surface, selected, move_preview, paths[move_preview], camera)
    surface.set_clip(old_clip)
    pg.draw.rect(surface, LINE, BOARD, 1)


def draw_combat(app):
    surface, game, battle = app.canvas, app.game, app.game.combat
    simulator = getattr(app, "combat_simulator", False)
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
    if simulator and app.sim_paused:
        turn = "PAUSED"
    text(surface, f"ROUND {battle.round:02}  ·  "+turn, (1038, 128), 12, CYAN if automatic else GOLD, "mono", right=True)
    instructions = "Wheel: zoom · Middle-drag / Shift+arrows: pan · "+("Right-click: ship details" if simulator else "N: next ship")
    text(surface, instructions, (34, 162), 12, MUTED)
    app.button("combat_zoom_out", "−", (850, 153, 40, 28), lambda: app.zoom_combat(-1),
               enabled=app.combat_zoom > combat_camera.ZOOM_LEVELS[0])
    app.button("combat_zoom_reset", f"{app.combat_zoom:.0%}", (898, 153, 86, 28), app.reset_combat_camera)
    app.button("combat_zoom_in", "+", (992, 153, 48, 28), lambda: app.zoom_combat(1),
               enabled=app.combat_zoom < combat_camera.ZOOM_LEVELS[-1])
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
        leader = flagships.is_flagship(battle, ship)
        text(surface, f"FLAGSHIP · {flagships.radius(ship)}-CELL COMMAND" if leader else "COMPUTER COMMAND" if automatic else "PLANETARY DEFENSE" if planet else "SELECTED SHIP", (x, 210), 10, CYAN if leader or automatic else MUTED, "mono", 1)
        if ship:
            if planet:
                combat_planets.draw_base(surface, game, ship, (1357, 256), app.empire_color(ship.owner), 1, diameter=60)
            else:
                ship_icon(surface, (1357, 254), .85, app.empire_color(ship.owner), kind=ship.kind, facing=1)
            text(surface, shorten(planet.name if planet else ship.name, 235, 21), (x, 235), 21, INK)
            text(surface, f"{'BASE' if planet else 'HULL'}  {ship.hull} / {ship.max_hull}", (x, 267), 12, CYAN, "mono")
            if planet:
                text(surface, "Surface missile base · "+planet.biome, (x, 286), 10, MUTED)
            if ship.design or ship.max_shields or interception(battle, ship):
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
            elif fleet_support.auras(ship):
                text(surface, shorten(fleet_support.providing_text(ship), 308, 10), (x, 420), 10, CYAN)
            elif ship.design and (ship.design.repair_rate or ship.design.shield_regeneration):
                text(surface, f"Repair reserve {ship.repair_remaining} · Shield regen +{ship.design.shield_regeneration}", (x, 420), 11, CYAN)
            elif ship.design:
                text(surface, "Only weapons in range fire; one volley per turn.", (x, 420), 11, MUTED)
            support_text = (f"Fleet aura: +{flagships.ACCURACY} aim / +{flagships.EVASION} evade (other ships)"
                            if leader and battle.accuracy else
                            fleet_support.receiving_text(battle, ship, accuracy=battle.accuracy))
            text(surface, shorten(support_text, 308, 9), (x, 438), 9, CYAN)
        else:
            paragraph(surface, "The computer is managing your fleet's orders and turns." if automatic else "Your ships have finished their orders. End your turn to let the opponent act.", (x, 239), 308, 16, MUTED, 26)
        pg.draw.line(surface, LINE, (x, 454), (1388, 454))
        target_planet = combat_planets.planet_for(game, target)
        text(surface, "PLANETARY TARGET" if target_planet else "ENEMY FLAGSHIP" if flagships.is_flagship(battle, target) else "ENEMY TARGET", (x, 464), 9, RIVAL_COLOR, "mono", 1)
        text(surface, shorten(combat_planets.unit_name(game, target), 308, 17) if target else "Click an enemy ship or base", (x, 482), 17, INK)
        if target and target.owner == MONSTER:
            ship_icon(surface, (1356, 481), .45, kind=target.kind)
        caption = (f"{target.hull}/{target.max_hull} base hull" if target_planet else f"{target.hull}/{target.max_hull} hull · {target.shields} shields") if target else "Targets must be within weapon range."
        if target and ship:
            caption += f"  ·  Distance {geometry.distance(ship, target):.1f}"
        text(surface, caption, (x, 507), 10, MUTED)
        if target:
            jam = fleet_support.strongest(battle, target, "jamming") if battle.accuracy else 0
            evasion = flagships.evasion(battle, target) if battle.accuracy else 0
            text(surface, f"PD {interception(battle, target)}% · ECM −{jam} aim · Fleet evade +{evasion}", (x, 522), 9, MUTED)
        can_fire = bool(player_turn and ship and target and action_error(game, PLAYER, ship.id, target.id) is None)
        label = "Fire at target" if can_fire else "Weapons recharging" if ship and ship.damage and not ship.ready_damage else "Line of fire blocked" if ship and target and in_range(ship, target) and not in_range(ship, target, battle) else "Target out of range" if ship and target and ship.damage and not in_range(ship, target) else "Weapon spent" if ship and ship.id in battle.acted else "Unarmed" if ship and not ship.damage else "Select a target"
        blocked_beams = bool(ship and target and geometry.blocker(battle, ship, target)
                             and any(not BEAMS[w].projectile for w, _, _ in ship.ready_weapons))
        text(surface, "BEAMS BLOCKED · guided ordnance can launch" if blocked_beams and can_fire
             else "HIT CHANCE · fleet support / ECM / tracking" if battle.accuracy
             else "GUARANTEED HITS · aim / evasion / ECM off", (x, 538), 9, GOLD)
        if ship and target and in_range(ship, target, battle):
            groups = list(Counter(w for w, _ in ship.volley(target, battle)).items())
            limit = 2 if ship.drone_bays else 4
            for index, (weapon, count) in enumerate(groups[:limit]):
                if index == limit-1 and len(groups) > limit:
                    text(surface, f"+ {len(groups)-index} other weapon types in this volley", (x, 553+index*11), 10, MUTED)
                    break
                chance = accuracy_breakdown(game, ship, target, weapon)
                shot_label = (f"{count*BEAMS[weapon].shots}× {BEAMS[weapon].name}: {chance['chance']}%  "
                         f"(track −{chance['tracking']})")
                text(surface, shot_label, (x, 553+index*11), 10, CYAN)
        else:
            text(surface, "Move to a clear firing lane." if label == "Line of fire blocked" else "Choose an enemy within weapon range.", (x, 554), 10, MUTED)
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
            text(surface, f"{disabled} motherships disabled"+("" if simulator else " · 3-turn repair window"), (x, details_y), 11, GOLD)
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
        if simulator:
            from .combat_sandbox import battle_report
            report = battle_report(game)
            caption = (f"{battle.round} rounds · {battle.shots_fired} shots. "
                       f"Ship hull remaining: {report['player']['hull_remaining']} yours / {report['rival']['hull_remaining']} enemy. "
                       "Rematch restores the original fleets, equipment and seed. Edit fleets to change the matchup.")
        paragraph(surface, caption, (x, max(377, details_y)), 302, 15, MUTED, 26)
        app.button("combat_continue", "Edit fleets" if simulator else "Return to system", (x, 641, 308, 51), app.finish_combat, "primary")

    text(surface, f"ORDNANCE IN FLIGHT: {len(battle.projectiles)}  ·  {combat_projectiles.SPEED} cells / round  ·  ~N r = estimated arrival", (34, 741), 10, GOLD, "mono")
    panel(surface, (32, 763, 1376, 77))
    text(surface, "COMBAT LOG", (48, 778), 10, GOLD, "mono", 1)
    for i, message in enumerate(battle.log[-3:]):
        text(surface, shorten(message, 1120, 12), (233, 773+i*21), 12, INK if i == len(battle.log[-3:])-1 else MUTED)
    app.button("combat_pause", ("Resume · Esc" if app.sim_paused else "Pause · Esc") if simulator else "Menu · Esc",
               (32, 851, 153, 38), app.pause, enabled=not simulator or battle.status == "active")
    app.button("combat_save", "Rematch · R" if simulator else "Save · F5", (198, 851, 153, 38),
               app.rematch if simulator else app.save_game)
    if active:
        app.button("combat_auto", "Take control · A" if automatic else "Auto combat · A", (364, 851, 218, 38),
                   app.toggle_combat_auto, "primary" if automatic else "normal", enabled=battle.status == "active")
    status = ("Firing…" if busy and app.combat_animation.kind == "fire" else "Ordnance advancing…" if busy and app.combat_animation.kind == "ordnance" else "Launching…" if busy and app.combat_animation.kind == "launch_projectile" else "Maneuvering…" if busy
              else "Computer is giving your fleet orders…" if automatic and battle.active_owner == PLAYER
              else "Enemy is giving orders…" if battle.status == "active" and battle.active_owner != PLAYER
              else "Battle ended · Review the result to continue" if not active
              else "One move + one shot per ship · Strategic time paused")
    if simulator and app.sim_paused:
        status = "Paused · P resumes · R starts a fresh battle"
    text(surface, shorten(status, 454, 12), (600 if active else 372, 863), 12, CYAN if automatic else MUTED)
    camera = combat_camera.view(app)
    horizontal = camera.width < BOARD_COLUMNS
    vertical = camera.height < battle.rows
    if horizontal or vertical:
        cols, rows = camera.columns(), camera.rows(battle.rows)
        text(surface, f"COLS {cols.start+1}–{cols.stop} · ROWS {rows.start+1}–{rows.stop}/{battle.rows}",
             (1038, 742), 9, MUTED, "mono", right=True)
        for key, label, left, dx, dy, enabled in (
                ("left", "←", 1110, -3, 0, camera.x > 0),
                ("right", "→", 1185, 3, 0, camera.x+camera.width < BOARD_COLUMNS),
                ("up", "↑", 1260, 0, -3, camera.y > 0),
                ("down", "↓", 1335, 0, 3, camera.y+camera.height < battle.rows)):
            app.button("combat_map_"+key, label, (left, 851, 73, 38),
                       lambda a=dx, b=dy: app.pan_combat(b, dx=a), enabled=enabled)
