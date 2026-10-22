"""Read-only ship inspection for the combat laboratory."""

from collections import Counter
import math
import pygame as pg

from . import combat_projectiles, fleet_support, flagships, combat_geometry as geometry
from .combat import BEAMS, COMBAT_TYPES
from .fleet_art import ship_icon
from .ui import CYAN, GOLD, INK, LINE, MUTED, panel, paragraph, shorten, text

PAGE_SIZE = 4


def weapon_rows(battle, ship):
    rows = []
    for (weapon, strength, reach), count in Counter(ship.weapons).items():
        spec = BEAMS[weapon]
        status = ("Destroyed" if ship.hull <= 0 else f"Recharging ({ship.cooldowns[weapon]})" if weapon in ship.cooldowns
                  else "Volley spent" if ship.id in battle.acted else "Ready")
        shots = spec.shots*count
        detail = f"{strength*count} damage · {shots} {'shot' if shots == 1 else 'shots'} · Range {reach} cells · Base aim {spec.accuracy}%"
        traits = []
        if spec.projectile:
            traits.append(f"Bypasses shields · Homing · {combat_projectiles.SPEED} cells/round · up to {math.ceil(reach/combat_projectiles.SPEED)} rounds at launch range")
        if spec.shield_multiplier > 1:
            traits.append(f"{spec.shield_multiplier}× damage against shields")
        if spec.shield_bypass:
            traits.append(f"Bypasses {spec.shield_bypass}% of shields")
        if spec.interception_piercing:
            traits.append(f"Ignores {spec.interception_piercing}% of interception")
        if spec.reload:
            traits.append(f"Skips {spec.reload} turn after firing")
        if spec.slows:
            traits.append("Slows the target")
        if spec.versus_drones > 1:
            traits.append(f"{spec.versus_drones}× against drones")
        if spec.versus_capitals > 1:
            traits.append(f"{spec.versus_capitals}× against capital ships")
        rows.append((f"{count}× {spec.name}", detail, " · ".join(traits) or "Beam · Shields absorb damage · Clear firing lane required", status))
    return rows


def equipment_rows(ship):
    if ship.design:
        equipment = Counter(ship.design.specs)
    else:
        equipment = Counter(fleet_support.equipment(ship))
    return [(f"{count}× {module.name}", module.description, "", "Fitted") for module, count in equipment.items()]


def ordnance_rows(battle, ship):
    rows = []
    for shot in battle.projectiles:
        if ship.id not in (shot.source_id, shot.target_id):
            continue
        target = battle.ship(shot.target_id)
        incoming = shot.target_id == ship.id
        rounds = combat_projectiles.eta(shot, target)
        rows.append((BEAMS[shot.weapon].name, ("Incoming from " if incoming else "Target: ")+
                     (battle.ship(shot.source_id).name if incoming else target.name),
                     f"{shot.strength} damage before defenses · Aim {shot.chance}% · Fuel {combat_projectiles.MAX_FLIGHT_ROUNDS-shot.age} rounds",
                     f"~{rounds} {'round' if rounds == 1 else 'rounds'}"))
    return rows


def draw(app):
    battle = app.game.combat
    ship = battle.ship(app.dialog["combat_ship_info"])
    surface = app.canvas
    color = app.empire_color(ship.owner)
    panel(surface, (96, 104, 1248, 694), border=color)
    ship_icon(surface, (154, 158), .8, color, kind=ship.kind, facing=1)
    text(surface, shorten(ship.name, 966, 28), (208, 123), 28, INK, "title")
    side = "YOUR FLEET" if ship.owner == "player" else "ENEMY FLEET"
    text(surface, f"{side} · {COMBAT_TYPES[ship.kind].name} · {geometry.size(ship)[0]}×{geometry.size(ship)[1]} cells · Cell {ship.x+1}, {ship.y+1}", (208, 168), 13, color)
    command = flagships.description(battle, ship)
    if command and not battle.accuracy:
        command += " · Aim/evasion inactive: every shot hits"
    text(surface, shorten(command, 1108, 11), (208, 191), 11, CYAN)
    app.button("dialog_close", "Close ×", (1210, 122, 106, 36), app.cancel_dialog)

    panel(surface, (120, 212, 372, 474))
    text(surface, "CONDITION & DEFENSES", (140, 234), 11, GOLD, "mono", 1)
    for y, label, value, maximum, shade in ((270, "Hull", ship.hull, ship.max_hull, color),
                                          (348, "Beam shields", ship.shields, ship.max_shields, CYAN)):
        text(surface, label, (140, y), 18, INK)
        text(surface, f"{value} / {maximum}", (472, y), 17, shade, right=True)
        pg.draw.rect(surface, LINE, (140, y+33, 332, 7))
        if maximum and value:
            pg.draw.rect(surface, shade, (140, y+33, round(332*value/maximum), 7))
    text(surface, f"Started battle with {ship.initial_hull} hull", (140, 318), 13, MUTED)
    design = ship.design
    defense = fleet_support.interception_breakdown(battle, ship)
    lines = [
        ("Movement", f"{ship.movement} cells · "+("Ready" if battle.can_move(ship) else "Spent" if ship.movement else "Stationary")),
        ("Shield regeneration", f"+{design.shield_regeneration if design else 0} / own turn"),
        ("Shield hardening", f"{design.shield_hardening if design else 0}%"),
        ("Point defense", f"{defense['total']}% total"),
        ("Own / allied screen", f"{defense['local']}% / {defense['shared']}%"),
        ("Repairs", f"{design.repair_rate if design else 0}/turn · {ship.repair_remaining} reserve"),
        ("Drone bays", f"{ship.drone_bays} · {ship.drone_reserve} reserve"),
        ("Status", "Destroyed" if ship.hull <= 0 else "Slowed" if ship.graviton_slow else "Operational"),
    ]
    for index, (label, value) in enumerate(lines):
        y = 408+index*32
        text(surface, label, (140, y), 13, MUTED)
        text(surface, value, (472, y), 12, INK, right=True)

    panel(surface, (516, 212, 804, 474))
    tab = app.dialog.get("inspection_tab", "weapons")
    for index, (key, label) in enumerate((("weapons", "Weapons"), ("equipment", "Equipment"), ("ordnance", "Ordnance"))):
        app.button("dialog_inspect_"+key, label, (536+index*256, 232, 240, 40),
                   lambda value=key: app.inspect_tab(value), "tab_active" if tab == key else "tab")
    rows = weapon_rows(battle, ship) if tab == "weapons" else equipment_rows(ship) if tab == "equipment" else ordnance_rows(battle, ship)
    pages = max(1, math.ceil(len(rows)/PAGE_SIZE))
    page = max(0, min(pages-1, app.dialog.get("inspection_page", 0)))
    app.dialog["inspection_page"] = page
    if not rows:
        message = {"weapons": "No direct-fire weapons. Carriers can still launch their drones.",
                   "equipment": "Standard hull and equipment; no additional fitted modules.",
                   "ordnance": "No incoming or outgoing projectiles for this ship."}[tab]
        paragraph(surface, message, (540, 314), 744, 18, MUTED, 29)
    for index, (title, detail, traits, status) in enumerate(rows[page*PAGE_SIZE:(page+1)*PAGE_SIZE]):
        y = 300+index*88
        text(surface, shorten(title, 570, 18), (540, y), 18, INK)
        text(surface, status, (1296, y+2), 12, GOLD, right=True)
        paragraph(surface, detail, (540, y+28), 746, 13, MUTED, 17)
        if traits:
            text(surface, shorten(traits, 746, 12), (540, y+58), 12, CYAN)
        pg.draw.line(surface, LINE, (540, y+80), (1296, y+80))
    text(surface, fleet_support.receiving_text(battle, ship, accuracy=battle.accuracy), (536, 664), 11, CYAN)
    text(surface, "Combat pauses while you inspect. Esc or Close returns to the battle.", (120, 722), 14, MUTED)
    text(surface, "Weapon aim is before target-specific range, evasion, command and ECM modifiers.", (120, 759), 12, MUTED)
    text(surface, f"{page+1} / {pages}", (1077, 723), 13, MUTED, right=True)
    app.button("dialog_inspect_previous", "←", (1094, 708, 92, 42), lambda: app.inspect_page(-1), enabled=page > 0)
    app.button("dialog_inspect_next", "→", (1200, 708, 120, 42), lambda: app.inspect_page(1), enabled=page+1 < pages)
