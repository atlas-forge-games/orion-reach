"""Shared campaign actions, always in the lower-right corner of a view."""

import pygame as pg

# Modal decisions still show the same destinations, disabled until resolved.
GAME_SCREENS = (
    'galaxy', 'system', 'megastructure', 'hyperlane', 'encounters', 'planet', 'production',
    'colony', 'empire', 'shipyard', 'fleets', 'fleet', 'rival', 'diplomacy',
    'statistics', 'specialists', 'research', 'combat', 'ground', 'objectives',
    'result', 'exploration', 'designer', 'news', 'contact', 'observer', 'council',
)


def available(app):
    return bool(app.game and app.screen in GAME_SCREENS and app.screen != 'galaxy'
                and not getattr(app, 'combat_simulator', False))


def blocked_reason(app):
    if app.turn_busy:
        return 'Please wait for this turn to finish.'
    if app.screen == 'contact':
        return 'Acknowledge this transmission first.'
    if app.ground_reports:
        return 'Continue through the ground battle reports first.'
    return app.game.strategy_error()


def return_to_galaxy(app):
    """Use the normal transition, including colony housekeeping and guards."""
    if app.game and app.screen != 'galaxy' and not blocked_reason(app):
        if app.screen == 'ground':
            app.reset_ground_view()
        app.go('galaxy')
        app.focus_galaxy_planet()


def rects(size):
    width, height = size
    compact = width < 1100
    margin = 24 if compact else 64
    map_width, turn_width = (194, 214) if compact else (240, 295)
    end = pg.Rect(width-margin-turn_width, height-80, turn_width, 54)
    galaxy = pg.Rect(end.left-12-map_width, end.top, map_width, end.height)
    return galaxy, end


def draw(app):
    if not available(app):
        return
    layout = getattr(app.canvas, 'layout', None)
    galaxy, end = rects(layout.size if layout else app.canvas.get_size())
    map_icon = 'system' if galaxy.w >= 240 else ''
    turn_icon = 'turn' if end.w >= 295 else ''
    if layout:
        galaxy, end = app.canvas.source_slot(galaxy), app.canvas.source_slot(end)
    reason = blocked_reason(app)
    turn_reason = reason or ('Finish or leave the landing plan first.' if app.screen == 'ground' else None)
    app.button('galaxy_map', 'Galaxy map', galaxy, lambda: return_to_galaxy(app),
               'command', icon=map_icon, shortcut='G', enabled=reason is None)
    app.button('end_turn', 'End turn', end, app.advance_turn, 'command_primary',
               icon=turn_icon, shortcut='E', enabled=turn_reason is None)
    # Explain unavailable actions without adding another line to a crowded view.
    for rect, message in ((galaxy, reason), (end, turn_reason)):
        if message:
            app.canvas.text_regions.append((rect.copy(), message))
