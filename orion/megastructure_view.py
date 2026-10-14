"""System project controls and staged orbital illustrations."""
from functools import lru_cache
from pathlib import Path
import pygame as pg

from . import megastructures as rules
from .model import RuleError
from .planet_art import draw_star
from .research import BRANCHES
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text

ART = Path(__file__).resolve().parents[1]/"assets"/"megastructures"


@lru_cache(maxsize=32)
def sprite(kind, width, height):
    original = pg.image.load(str(ART/f"{kind}-v1.png")).convert_alpha()
    bounds = original.get_bounding_rect()
    original = original.subsurface(bounds)
    scale = min(width/original.get_width(), height/original.get_height())
    return pg.transform.smoothscale(original, (max(1, round(original.get_width()*scale)), max(1, round(original.get_height()*scale))))


def draw_art(surface, kind, rect, *, stage=4, progress=0):
    area = pg.Rect(rect)
    art = sprite(kind, area.w, area.h)
    target = art.get_rect(center=area.center)
    if kind == "dyson_sphere":
        draw_star(surface, target.center, min(target.w, target.h)//5, (246, 195, 112))
    if stage < rules.STAGES:
        ghost = art.copy()
        ghost.set_alpha(38)
        surface.blit(ghost, target)
        clip = surface.get_clip()
        fraction = (stage+progress)/rules.STAGES
        surface.set_clip(target.clip(pg.Rect(target.x, target.y, round(target.w*fraction), target.h)))
        surface.blit(art, target)
        surface.set_clip(clip)
    else:
        surface.blit(art, target)


def effect(spec, stage=4):
    if spec.id == "dyson_sphere":
        return "Unlimited energy · entire empire" if stage == 4 else f"+{stage*spec.energy_per_stage} energy / colony"
    if spec.id == "stellar_forge":
        return f"{1+stage*spec.ship_speed_per_stage}× ship production · this system"
    if spec.id == "research_array":
        return f"{stage*spec.discovery_chance_per_stage}% discovery chance / turn · no RP output"
    return f"+{stage*spec.resources_per_stage:,} resources / turn · empire reserve"


def perform(app, callback):
    try:
        message = callback()
        app.save_game(autosave=True)
        app.toast(message or "Megastructure orders updated")
    except RuleError as exc:
        app.toast(exc, True)


def commission(app, kind):
    spec = rules.MEGASTRUCTURES[kind]
    app.confirm(f"Commission {spec.name}?",
                f"This uses your civilization's once-per-campaign commission for this type. "
                f"The four stages require {spec.resource_cost*10:,} resources and {spec.work_cost*10:,} industry in total. "
                "Materials are paid as work proceeds. Initially 50% of this system's industry contributes; you can change or pause this at any time.",
                "Commission", lambda: perform(app, lambda: rules.start(app.game, app.game.selected_system, kind)))


def draw_ribbon(app, system, live):
    m = system.megastructure
    surface = app.canvas
    panel(surface, (64, 630, 1312, 149), (8, 20, 29))
    draw_art(surface, m.kind, (76, 638, 314, 133), stage=m.stage,
             progress=m.progress/m.stage_work if m.stage_work else 0)
    text(surface, "SYSTEM MEGASTRUCTURE", (418, 645), 10, GOLD, "mono", 2)
    text(surface, m.spec.name, (416, 667), 27, INK, "title")
    text(surface, f"Stage {m.stage}/4 · "+effect(m.spec, m.stage), (418, 706), 13, CYAN)
    status = "Last observed construction" if not live else rules.operating_status(app.game, app.game.systems[system.id])
    if live and m.owner == "player" and m.stage < 4:
        status = rules.work_error(app.game, system, m.owner) or ("Construction paused" if m.paused else f"{m.allocation}% local industry assigned")
    text(surface, shorten(status, 705, 12), (418, 743), 12, MUTED)
    app.button("system_megastructure_details", "View structure →", (1142, 667, 213, 53), lambda: app.go("megastructure"))


def draw_megastructure(app):
    game, surface = app.game, app.canvas
    system = game.known_system(game.selected_system)
    app.chrome("SYSTEM ENGINEERING")
    app.button("mega_back", "← Solar system", (64, 126, 220, 46), lambda: app.go("system"))
    if system is None:
        text(surface, "Survey this system to inspect its megastructures.", (64, 235), 24, MUTED)
        return
    live = game.system_visible(system.id)
    text(surface, system.name+" · Megastructures", (64, 193), 37, INK, "title")
    text(surface, "One structure per system · Each civilization commissions each type once · Work requires sole settled control", (67, 251), 14, MUTED)
    m = system.megastructure
    if m is None:
        for index, spec in enumerate(rules.MEGASTRUCTURES.values()):
            x = 64+index*334
            panel(surface, (x, 290, 310, 484), (9, 20, 28))
            draw_art(surface, spec.id, (x+12, 303, 286, 170))
            size = 19 if spec.id == "asteroid_network" else 22
            text(surface, shorten(spec.name, 278, size, "title"), (x+16, 489), size, INK, "title")
            paragraph(surface, spec.description, (x+17, 528), 276, 13, MUTED, 20)
            text(surface, f"{spec.resource_cost*10:,} RES · {spec.work_cost*10:,} work total", (x+17, 644), 13, GOLD)
            text(surface, f"{BRANCHES[spec.branch].name} · tier {spec.tier}", (x+17, 672), 11, CYAN)
            reason = rules.start_error(game, system.id, spec.id) if live else "Survey must be refreshed first."
            if game.is_observer:
                reason = "Observer view"
            app.button(f"mega_start_{spec.id}", "Commission", (x+16, 715, 278, 43),
                       lambda kind=spec.id: commission(app, kind), enabled=reason is None)
            if reason:
                paragraph(surface, reason, (x+8, 791), 298, 11, MUTED, 16)
        return

    own = live and m.owner == "player" and not game.is_observer
    panel(surface, (64, 290, 722, 449), (6, 17, 26))
    text(surface, "ORBITAL CONSTRUCTION · "+("LIVE" if live else "LAST SURVEY"), (86, 311), 10, GOLD, "mono", 1)
    draw_art(surface, m.kind, (84, 348, 682, 298), stage=m.stage,
             progress=m.progress/m.stage_work if m.stage_work else 0)
    text(surface, m.spec.name, (88, 674), 28, INK, "title")
    text(surface, f"Owner: {game.empire_name_for(m.owner)} · Hull {m.hull:,}/{m.max_hull:,}", (90, 715), 13, MUTED)
    panel(surface, (810, 290, 566, 449))
    text(surface, f"STAGE {m.stage} / 4", (832, 312), 13, GOLD, "mono", 2)
    paragraph(surface, effect(m.spec, m.stage), (832, 350), 518, 22, CYAN, 30)
    paragraph(surface, m.spec.description, (832, 427), 518, 14, MUTED, 23)
    if m.stage < 4:
        pg.draw.rect(surface, LINE, (832, 526, 518, 7))
        pg.draw.rect(surface, CYAN, (832, 526, round(518*m.progress/m.stage_work), 7))
        text(surface, f"Next stage: {m.progress:,} / {m.stage_work:,} work", (832, 546), 16, INK)
        paid = (m.progress*m.stage_resources+m.stage_work-1)//m.stage_work
        text(surface, f"Stage materials: {paid:,} / {m.stage_resources:,} RES", (832, 578), 14, GOLD)
    else:
        text(surface, "All construction stages complete", (832, 546), 19, INK)
    status = "Stored survey · send a ship to refresh" if not live else rules.operating_status(game, system)
    if own:
        plan = rules.plan_for(game, m.owner)
        order = next((o for o in plan.orders if o[0] == system.id), None)
        work = sum(v for (sid, _), v in plan.contributions.items() if sid == system.id)
        cost = order[2] if order else 0
        reason = rules.work_error(game, system, m.owner)
        text(surface, f"Next turn: {work} industry · {cost} resources", (832, 624), 14, CYAN)
        status = reason or ("Construction paused; completed sections can still operate" if m.paused else "Repairing hull before further construction" if m.hull < m.max_hull else "Construction funded" if order else rules.operating_status(game, system) if m.stage == 4 else "Waiting for industry / resources")
    paragraph(surface, status, (832, 663), 518, 13, MUTED, 21)
    if own:
        text(surface, "LOCAL INDUSTRY CONTRIBUTION", (66, 764), 10, GOLD, "mono", 1)
        for index, value in enumerate((0, 25, 50, 75, 100)):
            app.button(f"mega_allocation_{value}", f"{value}%", (64+index*105, 792, 95, 46),
                       lambda n=value: perform(app, lambda: rules.configure(game, system.id, allocation=n)),
                       "primary" if m.allocation == value else "normal")
        app.button("mega_pause", "Resume work" if m.paused else "Pause work", (614, 792, 172, 46),
                   lambda: perform(app, lambda: rules.configure(game, system.id, paused=not m.paused)))
        text(surface, "Fuel is funded first. Unspent industry stays with colony queues. Materials are paid progressively.", (66, 862), 12, MUTED)
    elif live and m.owner != "player" and not game.is_observer:
        reason = rules.attack_error(game, system.id)
        app.button("mega_attack", "Attack megastructure", (810, 785, 290, 46),
                   lambda: app.confirm("Attack megastructure?", "Your armed ships will use their bombardment action for this turn. This can start a war.",
                       "Attack", lambda: perform(app, lambda: rules.attack(game, system.id))), enabled=reason is None)
        if reason:
            paragraph(surface, reason, (812, 847), 545, 12, MUTED, 17)
