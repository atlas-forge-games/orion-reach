"""Ground invasion planning and casualty reports; battles resolve in the model."""

import math
import pygame as pg

from .colony_scene import landscape
from .ground_combat import GroundForces, forces, resolve
from . import production as production_balance
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text
from .victory import troop_transports, transport_losses
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
    raid = report.cause in ("raid", "mothership_raid") if report else raiding.is_varkesh(game)
    sid, pid = (report.system_id, report.planet_id) if report else app.ground_target
    from . import boarding, motherships
    from .model import RuleError
    system = game.systems[sid]
    try:
        planet = game.planet_at(sid, pid)
    except RuleError:
        if not report or report.cause not in ("boarding", "mothership_raid"):
            raise
        from types import SimpleNamespace
        planet = SimpleNamespace(name=report.target_name, biome="Mobile habitat", population=0, habitat=True)
    mobile = planet.habitat
    if mobile and not report:
        raid = app.ground_mode == "raid"
    ship = motherships.ship_for(game, planet) if mobile else None
    if report:
        attack = report.attack
        defence = GroundForces(report.militia, report.garrison, report.defence_bonus)
        attacker, defender = report.attacker, report.defender
        attack_left, defence_left = report.attacker_survivors, report.defender_survivors
        captured, rounds, count = report.captured, report.rounds, report.transports
    else:
        count = len(troop_transports(game, sid))
        attack = count*production_balance.TROOP_STRENGTH
        defence = boarding.defending_forces(game, ship) if mobile else forces(planet, game.bonuses_for(planet.owner))
        outcome = resolve(attack, defence)
        attacker, defender = "player", planet.owner
        attack_left, defence_left = None, None
        captured, rounds = outcome.captured, outcome.rounds
    lost, ground_troops = transport_losses(count, report.attacker_survivors if report else outcome.attackers)
    if tomb:
        ground_troops = report.attacker_survivors
    attack_color = app.empire_color("player") if attacker == "player" else RED
    defence_color = app.empire_color("player") if defender == "player" else RED
    success_color = attack_color if captured else defence_color
    app.chrome("GROUND OPERATIONS")
    title = f"Awakening on {planet.name}" if tomb else f"Raid on {planet.name}" if raid else f"Invasion of {planet.name}"
    if mobile and not raid:
        title = f"Boarding of {planet.name}"
    text(surface, shorten(title, 1050, 38, "title"), (64, 130), 38, INK, "title")
    text(surface, f"{system.name.upper()}  /  {planet.biome.upper()}  /  {planet.population} B CIVILIANS", (66, 185), 12, MUTED, "mono")
    text(surface, "BATTLE REPORT" if report else "RAID PLAN" if raid else "BOARDING PLAN" if mobile else "LANDING PLAN", (1376, 146), 12, GOLD, "mono", right=True)
    force_card(surface, 64, "AWAKENED REMNANT" if tomb else "RAIDING FORCE" if raid else "BOARDING PARTY" if mobile else "INVADING FORCE",
               game.empire_name_for(attacker) if attacker else "The Remnant", attack, attack_left,
               f"{attack} troops emerged from buried vaults" if tomb else f"{count} transports × {production_balance.TROOP_STRENGTH} troops", attack_color)
    force_card(surface, 776, "HABITAT DEFENCE" if mobile else "PLANETARY DEFENCE", game.empire_name_for(defender), defence.troops, defence_left,
               f"{defence.garrison} garrison + {defence.militia} militia · +{defence.defence_bonus}% firepower", defence_color)
    text(surface, "VS", (693, 287), 23, GOLD)

    if mobile:
        panel(surface, (64, 410, 1312, 156), (9, 22, 33))
        from .mothership_art import draw
        draw(surface, (720, 488), 1.8)
    else:
        surface.blit(landscape(planet.biome, f"ground:{game.seed}:{sid}:{pid}", (1312, 156), True), (64, 410))
    shade = pg.Surface((1312, 156), pg.SRCALPHA)
    shade.fill((5, 14, 24, 150))
    surface.blit(shade, (64, 410))
    text(surface, "DOCKING PORTS" if mobile else "OPENED VAULTS" if tomb else "LANDING ZONE", (84, 424), 10, attack_color, "mono", 2)
    text(surface, "HABITAT DECKS" if mobile else "COLONY PERIMETER", (1000, 424), 10, defence_color, "mono", 2)
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
        rules = ("Transport losses follow troop casualties, rounded up to full loads. Full squads re-embark; other survivors and captives return home. Empty colonies are abandoned; inhabited colonies keep their owner." if raid else
                 "Transport losses follow troop casualties, rounded up to full loads. Full squads re-embark; remaining troops hold the colony. Civilians and buildings survive.")
        if mobile:
            rules = ("Habitat decks give defenders +25% firepower. Transport losses follow troop casualties. "
                     +("Raids leave ownership intact. Stores have a ten-turn raid cooldown; Varkesh take up to a quarter of the population, leaving at least one." if raid else
                       "Surviving full squads re-embark. Remaining troops garrison the captured home; population and facilities survive."))
        paragraph(surface, rules,
                  (85, 715), 766, 14, MUTED, 23)

    panel(surface, (907, 588, 469, 212))
    title = ("Colony captured" if captured else "Invasion repelled") if report else ("Capture predicted" if captured else "Defeat predicted")
    if raid:
        title = ("Raid succeeded" if captured else "Raid repelled") if report else ("Raid success predicted" if captured else "Defeat predicted")
    if mobile and not raid and report:
        title = "Mothership captured" if captured else "Boarding repelled"
    text(surface, title, (929, 611), 28, success_color)
    if mobile and raid:
        credits, resources, slaves = (report.credits_stolen, report.resources_stolen, report.slaves_taken) if report else boarding.loot(game, ship)
        detail = (f"{credits} CR, {resources} RES and {slaves} slave units "+("taken." if report else "available on victory.")
                  +" The habitat keeps its owner. Loot is limited by actual stocks; another raid must wait ten turns.")
        if report and not captured:
            detail = "Boarding was repelled. No stores or captives were taken."
    elif raid and report:
        detail = (f"{report.slaves_taken} slave units and {report.credits_stolen} CR taken. {ground_troops} troops returned home; {count-lost} transports remain. "
                  +( "The empty colony was abandoned." if report.colony_razed else "The colony keeps its owner.")) if captured else "No captives or credits taken. Surviving defenders retain the colony."
    elif raid:
        slaves, credits = raiding.expected_loot(game, planet)
        detail = f"On victory: up to {slaves} slave units and {credits} CR, limited by the victim's treasury. {ground_troops} troops return home; full squads re-embark."
    elif report:
        detail = (f"{ground_troops} invaders remain as the new garrison. Militia will remuster gradually."
                  if captured else f"{defence_left} defenders remain. Garrison losses need barracks; militia recover one troop per turn.")
    else:
        detail = (f"Expected survivors: {outcome.attackers} invaders, {outcome.defenders} defenders. "
                  "Preview uses the actual battle rules.")
    paragraph(surface, detail, (929, 659), 424, 15, INK, 25)
    footer = f"{len(rounds)} rounds · assault from beneath the surface" if tomb else f"{len(rounds)} rounds · transports: {lost} lost / {count-lost} survive"
    text(surface, footer, (929, 766), 12, MUTED)
    if report:
        app.button("ground_continue", "Next report →" if len(app.ground_reports) > 1 else "Continue →",
                   (1056, 828, 320, 50), app.close_ground, "primary")
        text(surface, "The battle is resolved. Continue to return to the campaign.", (65, 845), 13, MUTED)
    else:
        app.button("ground_cancel", "←  Back to mothership" if mobile else "←  Back to colony", (64, 828, 249, 50), app.close_ground)
        app.button("ground_launch", "Launch raid" if raid else "Board mothership" if mobile else "Launch invasion", (1056, 828, 320, 50), app.launch_ground_assault, "primary",
                   enabled=(boarding.error(game, ship.id, app.ground_mode) if mobile else game.invasion_error(sid, pid)) is None)
        warning = ("Raids end treaties and set relations to −100.\nHomeworld slave limit: 100; 5% mortality per unit each turn." if raid else
                   "Invasion ends treaties and sets relations to −100.\nCapture destroys any Ascension Gate.")
        if mobile:
            warning = "Boarding starts war and sets relations to −100.\nCapture preserves the home; raids leave it with its current owner."
        paragraph(surface, warning, (342, 832), 670, 12, MUTED, 21)
