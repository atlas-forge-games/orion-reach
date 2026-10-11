"""Ground invasion planning and casualty reports; battles resolve in the model."""

import math
import pygame as pg

from .colony_scene import landscape
from .ground_combat import GroundForces, forces, resolve
from .production import TROOP_STRENGTH
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text
from .victory import troop_transports
from . import raiding


def force_card(surface, x, title, empire, initial, survivors, detail, color):
    panel(surface, (x, 222, 600, 166))
    text(surface, title, (x+20, 237), 11, color, "mono", 2)
    text(surface, shorten(empire, 370, 13), (x+579, 237), 13, MUTED, right=True)
    text(surface, str(initial if survivors is None else survivors), (x+20, 264), 48, INK)
    caption = "troops ready" if survivors is None else f"survivors / {initial} deployed"
    text(surface, caption, (x+130, 289), 18, MUTED)
    text(surface, detail, (x+21, 332), 13, color)
    if survivors is not None:
        text(surface, f"{initial-survivors} casualties", (x+577, 334), 12, MUTED, right=True)
    pg.draw.rect(surface, LINE, (x+21, 366, 558, 5))
    pg.draw.rect(surface, color, (x+21, 366, round(558*(1 if survivors is None else survivors/max(1, initial))), 5))


def units(surface, x, count, color, facing):
    # Abstract platoon markers keep the battle view appropriate for every species.
    markers = min(24, count)
    for i in range(markers):
        px, py = x+(i%12)*31, 461+(i//12)*33
        pg.draw.rect(surface, (17, 31, 39), (px-9, py-9, 23, 24), border_radius=4)
        pg.draw.circle(surface, color, (px+2, py-4), 4)
        pg.draw.line(surface, color, (px+2, py+2), (px+2, py+10), 3)
        pg.draw.line(surface, color, (px+2, py+4), (px+2+facing*9, py+1), 2)
    return max(1, math.ceil(count/24))


def draw_ground(app):
    game, surface = app.game, app.canvas
    report = app.ground_reports[0] if app.ground_reports else None
    tomb = bool(report and report.cause == "tomb")
    raid = report.cause == "raid" if report else raiding.is_varkesh(game)
    sid, pid = (report.system_id, report.planet_id) if report else app.ground_target
    planet, system = game.planet_at(sid, pid), game.systems[sid]
    if report:
        attack = report.attack
        defence = GroundForces(report.militia, report.garrison, report.defence_bonus)
        attacker, defender = report.attacker, report.defender
        attack_left, defence_left = report.attacker_survivors, report.defender_survivors
        captured, rounds, count = report.captured, report.rounds, report.transports
    else:
        count = len(troop_transports(game, sid))
        attack, defence = count*TROOP_STRENGTH, forces(planet, game.bonuses_for(planet.owner))
        outcome = resolve(attack, defence)
        attacker, defender = "player", planet.owner
        attack_left, defence_left = None, None
        captured, rounds = outcome.captured, outcome.rounds
    attack_color = app.empire_color("player") if attacker == "player" else RED
    defence_color = app.empire_color("player") if defender == "player" else RED
    success_color = attack_color if captured else defence_color
    app.chrome("GROUND OPERATIONS")
    title = f"Awakening on {planet.name}" if tomb else f"Raid on {planet.name}" if raid else f"Invasion of {planet.name}"
    text(surface, shorten(title, 1050, 38, "title"), (64, 130), 38, INK, "title")
    text(surface, f"{system.name.upper()}  /  {planet.biome.upper()}  /  {planet.population} B CIVILIANS", (66, 185), 12, MUTED, "mono")
    text(surface, "BATTLE REPORT" if report else "RAID PLAN" if raid else "LANDING PLAN", (1376, 146), 12, GOLD, "mono", right=True)
    force_card(surface, 64, "AWAKENED REMNANT" if tomb else "RAIDING FORCE" if raid else "INVADING FORCE",
               game.empire_name_for(attacker) if attacker else "The Remnant", attack, attack_left,
               f"{attack} troops emerged from buried vaults" if tomb else f"{count} transports × {TROOP_STRENGTH} troops", attack_color)
    force_card(surface, 776, "PLANETARY DEFENCE", game.empire_name_for(defender), defence.troops, defence_left,
               f"{defence.garrison} garrison + {defence.militia} militia · +{defence.defence_bonus}% firepower", defence_color)
    text(surface, "VS", (693, 287), 23, GOLD)

    surface.blit(landscape(planet.biome, f"ground:{game.seed}:{sid}:{pid}", (1312, 156), True), (64, 410))
    shade = pg.Surface((1312, 156), pg.SRCALPHA)
    shade.fill((5, 14, 24, 150))
    surface.blit(shade, (64, 410))
    text(surface, "OPENED VAULTS" if tomb else "LANDING ZONE", (84, 424), 10, attack_color, "mono", 2)
    text(surface, "COLONY PERIMETER", (1000, 424), 10, defence_color, "mono", 2)
    a_scale = units(surface, 118, attack if attack_left is None else attack_left, attack_color, 1)
    d_scale = units(surface, 922, defence.troops if defence_left is None else defence_left, defence_color, -1)
    for y in range(430, 544, 18):
        pg.draw.line(surface, GOLD, (720, y), (720, y+8))
    if defence.defence_bonus:
        for y in (451, 489):
            pg.draw.rect(surface, (89, 106, 114), (848, y, 28, 26), border_radius=3)
            pg.draw.line(surface, defence_color, (842, y+12), (859, y+12), 3)
    text(surface, "Simultaneous combat rounds · no tactical orders", (84, 539), 11, MUTED)
    if max(a_scale, d_scale) > 1:
        text(surface, "Markers show groups; exact troop counts above.", (1356, 539), 11, MUTED, right=True)

    panel(surface, (64, 588, 823, 212))
    text(surface, "CASUALTY LOG" if report else "RULES OF ENGAGEMENT", (85, 606), 11, GOLD, "mono", 2)
    if report:
        pages = max(1, math.ceil(len(rounds)/6))
        app.ground_page = min(app.ground_page, pages-1)
        for i, row in enumerate(rounds[app.ground_page*6:app.ground_page*6+6]):
            number = app.ground_page*6+i+1
            text(surface, f"Round {number:02}    Invaders −{row.attacker_losses}  /  {row.attackers} left"
                 f"       Defenders −{row.defender_losses}  /  {row.defenders} left", (85, 636+i*22), 12, INK, "mono")
        if not rounds:
            text(surface, "No defending troops remained. The landing was unopposed.", (85, 646), 14, INK)
        if pages > 1:
            app.button("ground_previous", "←", (706, 600, 62, 28),
                       lambda: setattr(app, "ground_page", app.ground_page-1), enabled=app.ground_page > 0)
            app.button("ground_next", "→", (779, 600, 62, 28),
                       lambda: setattr(app, "ground_page", app.ground_page+1), enabled=app.ground_page < pages-1)
    else:
        paragraph(surface, "Troops exchange fire simultaneously. Every four troops inflict one casualty per round, rounded up. Fortifications increase defending firepower.",
                  (85, 637), 766, 15, INK, 25)
        rules = ("Raid transports are consumed. Captives and surviving troops return home immediately. Empty colonies are abandoned; inhabited colonies keep their owner." if raid else
                 "All landing transports are consumed. Surviving invaders hold a captured colony. Civilian population and ordinary buildings survive.")
        paragraph(surface, rules,
                  (85, 715), 766, 14, MUTED, 23)

    panel(surface, (907, 588, 469, 212))
    title = ("Colony captured" if captured else "Invasion repelled") if report else ("Capture predicted" if captured else "Defeat predicted")
    if raid:
        title = ("Raid succeeded" if captured else "Raid repelled") if report else ("Raid success predicted" if captured else "Defeat predicted")
    text(surface, title, (929, 611), 28, success_color)
    if raid and report:
        detail = (f"{report.slaves_taken} slave units and {report.credits_stolen} CR taken. {attack_left} troops returned home. "
                  +( "The empty colony was abandoned." if report.colony_razed else "The colony keeps its owner.")) if captured else "No captives or credits taken. Surviving defenders retain the colony."
    elif raid:
        slaves, credits = raiding.expected_loot(game, planet)
        detail = f"On victory: up to {slaves} slave units and {credits} CR, limited by the victim's treasury. {outcome.attackers} surviving troops return home."
    elif report:
        detail = (f"{attack_left} invaders remain as the new garrison. Militia will remuster gradually."
                  if captured else f"{defence_left} defenders remain. Garrison losses need barracks; militia recover one troop per turn.")
    else:
        detail = (f"Expected survivors: {outcome.attackers} invaders, {outcome.defenders} defenders. "
                  "Preview uses the actual battle rules.")
    paragraph(surface, detail, (929, 659), 424, 15, INK, 25)
    footer = f"{len(rounds)} rounds · assault from beneath the surface" if tomb else f"{len(rounds)} rounds · {count} transports {'consumed' if report else 'will be consumed'}"
    text(surface, footer, (929, 766), 12, MUTED)
    if report:
        app.button("ground_continue", "Next report →" if len(app.ground_reports) > 1 else "Continue →",
                   (1056, 828, 320, 50), app.close_ground, "primary")
        text(surface, "The battle is resolved. Continue to return to the campaign.", (65, 845), 13, MUTED)
    else:
        app.button("ground_cancel", "←  Back to colony", (64, 828, 249, 50), app.close_ground)
        app.button("ground_launch", "Launch raid" if raid else "Launch invasion", (1056, 828, 320, 50), app.launch_ground_assault, "primary",
                   enabled=game.invasion_error(sid, pid) is None)
        warning = ("Raids end treaties and set relations to −100.\nHomeworld slave limit: 100; 5% mortality per unit each turn." if raid else
                   "Invasion ends treaties and sets relations to −100.\nCapture destroys any Ascension Gate.")
        paragraph(surface, warning, (342, 832), 670, 12, MUTED, 21)
