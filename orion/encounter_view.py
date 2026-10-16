"""Known neutral threats and deliberate scout searches; never reveal hidden sites."""

import pygame as pg

from . import encounters as rules, combat
from .fleet_art import ship_icon
from .model import RuleError
from .ui import CYAN, GOLD, INK, LINE, MUTED, panel, paragraph, shorten, text

PER_PAGE = 3


def draw_pirate_badge(surface, center, size=20):
    """A small corsair pennant that remains readable alongside fleet markers."""
    x, y = map(round, center)
    r = max(4, round(size/2))
    color = rules.COLOR
    pg.draw.line(surface, color, (x-r+2, y-r), (x-r+2, y+r), 2)
    pg.draw.polygon(surface, color, [(x-r+3, y-r), (x+r, y-r+2), (x+r-3, y+1), (x-r+3, y)])
    pg.draw.line(surface, (12, 22, 30), (x-2, y-r+3), (x+3, y-1), 2)
    pg.draw.line(surface, (12, 22, 30), (x+3, y-r+3), (x-2, y-1), 2)


def perform(app, action):
    try:
        action()
        app.save_game(autosave=True)
        if app.game.combat:
            app.reset_combat_view()
            app.go("combat")
        else:
            app.toast("Scout search assigned. Keep the scout here for two turns.")
    except RuleError as exc:
        app.toast(str(exc), True)


def draw_encounters(app):
    game, surface = app.game, app.canvas
    system = game.systems[game.selected_system]
    app.chrome("SYSTEM ENCOUNTERS")
    app.button("encounters_back", "← Solar system", (64, 126, 220, 46), lambda: app.go("system"))
    text(surface, "SCOUT REPORTS & NEUTRAL THREATS", (1376, 143), 11, GOLD, "mono", right=True)
    text(surface, shorten(system.name+" · Encounters", 1300, 42, "title"), (64, 195), 42, INK, "title")
    text(surface, "Planet guards defend one world. Hidden flotillas and raiders attack fleets in the system.", (67, 255), 15, MUTED)
    panel(surface, (64, 297, 514, 432))
    ship_icon(surface, (118, 350), 1.1, CYAN, kind="scout")
    text(surface, "SCOUT SEARCH", (174, 326), 11, GOLD, "mono", 1)
    current = rules.search_at(game, system.id)
    ready = ("player", system.id) in rules.ready_searches(game)
    caption = ("Search complete" if current and current.completed_turn else
               f"{current.progress} / {rules.SEARCH_TURNS} turns" if current else "Explore the unknown")
    text(surface, caption, (174, 355), 25, INK, "title")
    paragraph(surface, "Assign one stationary scout for two full turns. It may find supplies, research archives, a hidden pirate flotilla, or nothing of value.",
              (87, 412), 466, 17, INK, 27)
    paragraph(surface, "An armed escort is recommended. A discovery belongs to the first empire to recover it. Each empire can search a system once.",
              (87, 507), 466, 14, MUTED, 23)
    reason = rules.search_error(game, system.id)
    label = ("System searched" if current and current.completed_turn else "Search in progress" if ready else
             "Assign replacement scout" if current else "Start search · 2 turns")
    app.button("encounters_search", label, (87, 590, 466, 44),
               lambda: perform(app, lambda: rules.start_search(game, system.id)), "primary" if reason is None else "normal", enabled=reason is None)
    detail = ("Neutral encounters were disabled for this campaign." if not game.encounters.enabled else
              "The scout is searching. Moving it pauses progress; another scout can resume the search." if ready else
              "Search paused. Station a scout here and assign it to resume." if current and not current.completed_turn and not rules.work_error(game, system.id) else
              reason or "No credit or research cost. Keep the assigned scout here until the search finishes.")
    paragraph(surface, detail, (87, 651), 466, 13, CYAN if ready else MUTED, 20)

    fleets = sorted(rules.known_at(game, system.id), key=lambda e: (rules.known_status(game, e) not in ("active", "incoming"), -e.id))
    if app.encounter_system != system.id:
        app.encounter_system, app.encounter_page = system.id, 0
    last = max(0, (len(fleets)-1)//PER_PAGE)
    app.encounter_page = min(app.encounter_page, last)
    text(surface, "KNOWN PIRATE FLEETS", (607, 300), 11, GOLD, "mono", 1)
    if last:
        text(surface, f"{app.encounter_page+1}/{last+1}", (1246, 302), 11, MUTED, right=True)
        for key, step, x, enabled in (("previous", -1, 1260, app.encounter_page > 0), ("next", 1, 1320, app.encounter_page < last)):
            app.button("encounters_"+key, "←" if step < 0 else "→", (x, 291, 54, 28),
                       lambda n=step: setattr(app, "encounter_page", app.encounter_page+n), enabled=enabled)
    for i, fleet in enumerate(fleets[app.encounter_page*PER_PAGE:(app.encounter_page+1)*PER_PAGE]):
        y = 332+i*132
        observed = rules.known_status(game, fleet)
        live = game.system_visible(system.id) or game.is_observer
        panel(surface, (602, y, 774, 120), border=rules.COLOR if observed in ("active", "incoming") else LINE)
        ship_icon(surface, (647, y+40), .7, rules.COLOR, kind="frigate")
        draw_pirate_badge(surface, (671, y+23), 16)
        text(surface, fleet.name, (690, y+14), 20, INK)
        subtitle = (f"Guards {system.worlds[fleet.planet_id].name} · Other worlds remain accessible" if fleet.kind == "planet" else
                    f"Arrival in {max(0, fleet.arrival_turn-game.turn)} turns · Defend the system" if observed == "incoming" else
                    f"Withdraws in {max(0, fleet.expires_turn-game.turn)} turns" if fleet.kind == "raid" and observed == "active" else
                    "Discovered during a scout search" if fleet.kind == "ambush" else "Raid concluded")
        text(surface, shorten(subtitle, 654, 12), (690, y+43), 12, MUTED)
        detail = (f"{sum(h > 0 for h in fleet.hulls)} frigate(s) · {sum(fleet.hulls)} hull" if live and observed == "active" else
                  "Last known hostile contact" if observed == "active" else observed.capitalize())
        credits, resources = rules.BOUNTIES[fleet.kind]
        text(surface, detail, (621, y+75), 12, rules.COLOR if observed in ("active", "incoming") else MUTED)
        text(surface, f"Bounty: {credits} CR + {resources} RES", (621, y+96), 10, GOLD)
        if observed == "active":
            reason = rules.engagement_error(game, fleet.id) if live else "Send a fleet to refresh this contact."
            app.button(f"encounters_engage_{fleet.id}", "Engage pirates", (1106, y+72, 250, 34),
                       lambda fid=fleet.id: perform(app, lambda: combat.begin_pirate_combat(game, fid)), enabled=reason is None)
            if reason:
                text(surface, shorten(reason, 233, 10), (860, y+85), 10, MUTED)
    if not fleets:
        paragraph(surface, "No known pirate fleets here. A quiet system may still hold undiscovered sites.", (626, 361), 710, 21, MUTED, 32)
        paragraph(surface, "Frontier raids announce their arrival three turns in advance. Bring defenders to protect vulnerable ships and settlements.", (626, 477), 710, 16, MUTED, 27)
    reports = [e for e in rules.news(game) if e.system_id == system.id]
    panel(surface, (64, 747, 1312, 80))
    text(surface, "LATEST DISPATCH", (83, 765), 10, GOLD, "mono", 1)
    paragraph(surface, reports[-1].message if reports else "No encounter reports for this system yet. Discoveries and warnings also appear in Turn News.",
              (284, 765), 1060, 14, MUTED, 22)
    app.button("encounters_news", "Turn News", (64, 850, 205, 42), app.open_news)
    text(surface, "Pirates are independent. Fighting them does not declare war on an empire.", (294, 864), 12, MUTED)
    app.button("encounters_end_turn", "End turn · E", (1100, 850, 276, 42), app.advance_turn, enabled=game.strategy_error() is None)
