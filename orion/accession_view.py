"""Population and accession controls, available from colonies and diplomacy."""

from . import accession, species
from .races import RACES
from .ui import GOLD, INK, MUTED, panel, paragraph, shorten, text


def open_panel(app, sid=None, pid=None):
    app.dialog = {"accession": True, "page": 0, "focus": None if sid is None else (sid, pid)}


def perform(app, action, sid, pid):
    from .model import RuleError
    from .exploration import refresh
    try:
        {"start": accession.start, "cancel": accession.cancel, "invest": accession.invest}[action](app.game, sid, pid)
        app.dialog["message"] = {"start": "Outreach opened. Progress advances on End Turn.",
            "cancel": "Mission withdrawn.", "invest": "Civic investment is active for eight turns."}[action]
        refresh(app.game)
    except RuleError as exc:
        app.dialog["message"] = str(exc)


def rows(app):
    game = app.game
    focus = app.dialog.get("focus")
    result = []
    for actual in game.systems:
        system = game.known_system(actual.id)
        if system is None:
            continue
        for planet in system.worlds:
            if planet.colonized and (focus is None or focus == (system.id, planet.id)):
                result.append((system, planet))
    for ship in game.visible_ships():
        if ship.habitat is not None and (focus is None or focus == (ship.system_id, ship.habitat.id)):
            result.append((game.systems[ship.system_id], ship.habitat))
    return sorted(result, key=lambda row: (accession.mission_at(game, row[0].id, row[1].id) is None,
        row[1].owner == "player", row[0].id, row[1].id))


def draw(app):
    surface, game = app.canvas, app.game
    panel(surface, (64, 62, 1312, 782), border=GOLD)
    text(surface, "COLONY POPULATIONS & ACCESSION", (90, 84), 24, INK, "title")
    app.button("accession_close", "Close", (1230, 80, 120, 37), lambda: setattr(app, "dialog", None))
    paragraph(surface, "Union outreach: 30 CR to open, then 5 CR/turn; at most two missions. A dissatisfied colony votes at 100% support. "
        "Capitals and collective governments are protected. Keep scanners present, relations non-negative and your budget healthy.",
        (92, 130), 1240, 13, MUTED, 20)
    paragraph(surface, "Defend loyalty with food, lower administrative strain, or civic investment (40 CR / 8 turns). "
        "Skirr replace 1 B inhabitants every two turns when fed; liberation stops replacement.", (92, 178), 1240, 12, MUTED, 18)
    items = rows(app)
    pages = max(1, (len(items)+5)//6)
    page = app.dialog["page"] = min(app.dialog.get("page", 0), pages-1)
    if not items:
        text(surface, "Explore inhabited systems to inspect their populations.", (96, 260), 18, MUTED)
    for i, (system, planet) in enumerate(items[page*6:page*6+6]):
        y = 229+i*84
        panel(surface, (88, y, 1264, 77))
        live = planet.habitat or game.system_visible(system.id)
        fallback = game._empire(planet.owner).race_id
        text(surface, shorten(f"{planet.name} · {game.empire_name_for(planet.owner)}", 960, 15), (103, y+7), 15, INK)
        text(surface, shorten(species.caption(planet, fallback), 960, 12), (103, y+30), 12, RACES[fallback].color)
        mission = accession.mission_at(game, system.id, planet.id)
        reason, action, enabled, label = "", None, False, ""
        if mission and (game.is_observer or "player" in (mission.owner, mission.target)):
            rate, reason = accession.support(game, mission)
            text(surface, f"Support {mission.progress}% ({rate:+}/turn)", (820, y+8), 12, GOLD)
            if mission.owner == "player":
                action, enabled, label = "cancel", True, "Withdraw mission"
            elif planet.owner == "player":
                action, label = "invest", "Civic aid · 40 CR"
                enabled = accession.civic_error(game, system.id, planet.id) is None
        elif not live:
            reason = "Last observed population. Re-establish local visibility for current information."
        elif planet.owner == "player":
            action, label = "invest", "Civic aid · 40 CR"
            reason = accession.civic_error(game, system.id, planet.id) or "Civic investment protects loyalty and reverses accession support."
            enabled = accession.civic_error(game, system.id, planet.id) is None
        elif not game.is_observer and game.race_id == "serevan":
            action, label = "start", "Outreach · 30 CR"
            reason = accession.start_error(game, "player", system.id, planet.id)
            enabled = reason is None
            if enabled:
                probe = accession.Mission("player", planet.owner, system.id, planet.id, game.turn)
                _, reason = accession.support(game, probe)
        elif fallback == "skirr":
            n = species.composition(planet, fallback).get("skirr", 0)
            reason = f"Brood replacement: {n}/{planet.population} B Skirr."
        else:
            reason = "Civilian species are tracked separately from their governing empire."
        text(surface, shorten(reason, 1000, 11), (103, y+53), 11, MUTED)
        if action and not game.is_observer:
            app.button(f"accession_{action}_{system.id}_{planet.id}", label, (1138, y+14, 200, 42),
                lambda act=action, sid=system.id, pid=planet.id: perform(app, act, sid, pid), enabled=enabled)
    text(surface, shorten(app.dialog.get("message", ""), 1000, 13), (94, 750), 13, GOLD)
    app.button("accession_previous", "←", (92, 791, 64, 33),
        lambda: app.dialog.update(page=page-1), enabled=page > 0)
    text(surface, f"Page {page+1} / {pages}", (178, 800), 12, MUTED)
    app.button("accession_next", "→", (296, 791, 64, 33),
        lambda: app.dialog.update(page=page+1), enabled=page+1 < pages)
    text(surface, "Progress is public to both the sponsor and the colony owner.", (1348, 803), 12, MUTED, right=True)
