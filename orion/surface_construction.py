"""Choose a construction site on open ground without moving existing buildings."""

import pygame as pg

from . import colony_layout
from .building_art import draw_building_art
from .buildings import BUILDINGS
from .model import PLAYER, RuleError
from .ui import GOLD, INK, RED, panel, text, shorten


def location(app):
    return (app.game.campaign_id, app.game.selected_system, app.game.selected_planet)


def can_place(app):
    if (not app.game or app.screen != 'planet' or app.dialog or app.selected_habitat()
            or app.game.selected_planet is None or app.game.strategy_error()):
        return False
    game = app.game
    if not game.system_visible(game.selected_system):
        return False
    planet = game.planet_at(game.selected_system, game.selected_planet)
    return planet.colonized and planet.owner == PLAYER and not planet.is_gas_giant


def point_on_surface(app, pos):
    rect = app.surface_scene_rect
    if rect is None or not rect.collidepoint(pos):
        return None
    x = (pos[0]-rect.x) * colony_layout.WIDTH / rect.w
    y = (pos[1]-rect.y) * colony_layout.HEIGHT / rect.h
    return (round(x), round(y)) if y >= colony_layout.MIN_BOTTOM else None


def begin_preview(app, identifier):
    request = app.surface_build_request
    if not request or request['location'] != location(app) or identifier not in BUILDINGS:
        return False
    reason = app.game.build_error(app.game.selected_system, app.game.selected_planet, identifier)
    if reason:
        app.toast(reason, True)
        return True
    rect = app.surface_scene_rect.copy()
    app.go('planet', idle_prompt=True)
    app.surface_build_preview = {**request, 'identifier': identifier}
    x, y = request['point']
    app.mouse = (rect.x+x*rect.w/colony_layout.WIDTH, rect.y+y*rect.h/colony_layout.HEIGHT)
    app.keyboard_mode = False
    return True


def preview(app):
    data = app.surface_build_preview
    point = point_on_surface(app, app.mouse)
    if point is None:
        return None, 'Choose a spot on the foreground.'
    site = colony_layout.at_point(data['identifier'], point)
    game = app.game
    world = game.planet_at(game.selected_system, game.selected_planet)
    error = game.build_error(game.selected_system, game.selected_planet, data['identifier'])
    if not error:
        try:
            colony_layout.reserve(game, game.selected_system, world, data['identifier'], point)
        except ValueError as exc:
            error = str(exc)
    return site, error


def handle_input(app, event):
    if event.type == pg.WINDOWFOCUSLOST:
        app.surface_ground_down = None
    if app.surface_build_preview:
        if app.surface_build_preview['location'] != location(app) or not can_place(app):
            app.surface_build_preview = None
            app.surface_ground_down = None
            return False
        if event.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            app.mouse = app.logical_pos(event.pos)
            app.keyboard_mode = False
        if ((event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE)
                or (event.type == pg.MOUSEBUTTONUP and event.button == 3)):
            app.surface_build_preview = None
            app.surface_ground_down = None
            app.pressed = None
            return True
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            app.surface_ground_down = app.mouse
        if event.type == pg.MOUSEBUTTONUP and event.button == 1:
            pressed = app.surface_ground_down
            app.surface_ground_down = None
            if pressed is not None:
                site, error = preview(app)
                if error:
                    app.toast(error, True)
                else:
                    identifier = app.surface_build_preview['identifier']
                    try:
                        app.game.queue_building(app.game.selected_system, app.game.selected_planet,
                                                identifier, surface_site=point_on_surface(app, app.mouse))
                    except RuleError as exc:
                        app.toast(exc, True)
                    else:
                        app.surface_build_preview = None
                        app.pressed = None
                        if app.save_game(autosave=True):
                            app.toast(f'{BUILDINGS[identifier].name} queued at this site.')
        return event.type in (pg.KEYDOWN, pg.KEYUP, pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP, pg.MOUSEWHEEL)

    if not can_place(app) or event.type not in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP) or event.button != 1:
        return False
    pos = app.logical_pos(event.pos)
    point = point_on_surface(app, pos)
    blocked = any(button.rect.collidepoint(pos) for button in app.buttons)
    if event.type == pg.MOUSEBUTTONDOWN:
        app.surface_ground_down = pos if point and not blocked else None
        if app.surface_ground_down:
            app.pressed = None
            return True
    elif app.surface_ground_down:
        start = app.surface_ground_down
        app.surface_ground_down = None
        if point and not blocked and abs(pos[0]-start[0])+abs(pos[1]-start[1]) < 8:
            request = {'location': location(app), 'point': point}
            app.open_production()
            app.surface_build_request = request
        return True
    return False


def draw_preview(app, rect):
    app.surface_scene_rect = pg.Rect(rect)
    if not app.surface_build_preview:
        return
    site, error = preview(app)
    color = RED if error else GOLD
    if site:
        x, bottom, width, height = site
        sx, sy = rect[2]/colony_layout.WIDTH, rect[3]/colony_layout.HEIGHT
        target = pg.Rect(rect[0]+round((x-width//2)*sx), rect[1]+round((bottom-height)*sy),
                         round(width*sx), round(height*sy))
        draw_building_art(app.canvas, app.surface_build_preview['identifier'], target, alpha=150)
        pg.draw.rect(app.canvas, color, target, 1, border_radius=3)
    panel(app.canvas, (rect[0]+14, rect[1]+45, rect[2]-28, 36), (10, 23, 30), color)
    name = BUILDINGS[app.surface_build_preview['identifier']].name
    hint = error or 'Click to confirm this site · Esc or right-click cancels'
    text(app.canvas, shorten(name+' · '+hint, rect[2]-60, 14), (rect[0]+28, rect[1]+54), 14, INK)
