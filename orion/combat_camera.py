"""Presentation-only tactical camera shared by rendering and pointer input."""

from dataclasses import dataclass
import math
import pygame as pg

from .combat import BOARD_COLUMNS

CELL = 42
VISIBLE_ROWS = 13
BOARD = pg.Rect(32, 186, BOARD_COLUMNS*CELL, VISIBLE_ROWS*CELL)
ZOOM_LEVELS = (.5, .75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)


@dataclass(frozen=True)
class Viewport:
    x: float
    y: float
    zoom: float

    @property
    def cell_size(self):
        return CELL*self.zoom

    @property
    def width(self):
        return BOARD.w/self.cell_size

    @property
    def height(self):
        return BOARD.h/self.cell_size

    def project(self, cell):
        return (round(BOARD.x+(cell[0]-self.x+.5)*self.cell_size),
                round(BOARD.y+(cell[1]-self.y+.5)*self.cell_size))

    def unproject(self, point):
        return ((point[0]-BOARD.x)/self.cell_size+self.x-.5,
                (point[1]-BOARD.y)/self.cell_size+self.y-.5)

    def cell_rect(self, cell, inset=0):
        left = round(BOARD.x+(cell[0]-self.x)*self.cell_size)
        top = round(BOARD.y+(cell[1]-self.y)*self.cell_size)
        right = round(BOARD.x+(cell[0]-self.x+1)*self.cell_size)
        bottom = round(BOARD.y+(cell[1]-self.y+1)*self.cell_size)
        return pg.Rect(left+inset, top+inset, right-left-2*inset, bottom-top-2*inset)

    def columns(self):
        return range(max(0, math.floor(self.x)), min(BOARD_COLUMNS, math.ceil(self.x+self.width)))

    def rows(self, count):
        return range(max(0, math.floor(self.y)), min(count, math.ceil(self.y+self.height)))


def view(app):
    return Viewport(app.combat_camera_col, app.combat_camera_row, app.combat_zoom)


def clamp_axis(value, total, visible):
    # Center a whole battlefield when it fits; otherwise stop at its edges.
    return (total-visible)/2 if total <= visible else min(total-visible, max(0, value))


def clamp(app):
    camera = view(app)
    app.combat_camera_col = clamp_axis(camera.x, BOARD_COLUMNS, camera.width)
    app.combat_camera_row = clamp_axis(camera.y, app.game.combat.rows, camera.height)


def invalidate(app):
    # A wheel/drag followed by a click in the same event batch must not use
    # hitboxes left over from the old camera. The next render rebuilds them.
    app.pressed = None
    app.buttons = []


def pan(app, dx=0, dy=0):
    app.combat_camera_col += dx
    app.combat_camera_row += dy
    clamp(app)
    invalidate(app)


def zoom(app, steps, anchor=None):
    old = view(app)
    index = min(range(len(ZOOM_LEVELS)), key=lambda i: abs(ZOOM_LEVELS[i]-old.zoom))
    level = ZOOM_LEVELS[max(0, min(len(ZOOM_LEVELS)-1, index+int(steps)))]
    if level == old.zoom:
        return
    point = anchor if anchor is not None and BOARD.collidepoint(anchor) else BOARD.center
    world = old.unproject(point)
    app.combat_zoom = level
    app.combat_camera_col = world[0]+.5-(point[0]-BOARD.x)/(CELL*level)
    app.combat_camera_row = world[1]+.5-(point[1]-BOARD.y)/(CELL*level)
    clamp(app)
    invalidate(app)


def reveal(app, positions):
    """Show a complete action when it fits; otherwise follow its destination."""
    positions = tuple(positions)
    if not positions:
        return
    camera = view(app)
    for axis, attr, extent, start in ((0, 'combat_camera_col', camera.width, camera.x),
                                      (1, 'combat_camera_row', camera.height, camera.y)):
        lo, hi = min(p[axis] for p in positions), max(p[axis] for p in positions)
        if lo < start or hi+1 > start+extent:
            center = (lo+hi+1)/2 if hi-lo+1 <= extent else positions[-1][axis]+.5
            setattr(app, attr, center-extent/2)
    clamp(app)


def reset(app):
    app.combat_zoom = 1.0
    app.combat_camera_col = app.combat_camera_row = 0
    ship = app.game.combat.ship(app.combat_ship_id)
    if ship:
        reveal(app, (ship.position,))
    clamp(app)
    invalidate(app)


def handle_input(app, event):
    if app.screen != 'combat' or app.dialog or app.game is None or app.game.combat is None:
        app.combat_drag = None
        return False
    if event.type == pg.WINDOWFOCUSLOST:
        app.combat_drag = None
    if event.type == pg.MOUSEBUTTONDOWN and event.button == 2:
        point = app.logical_pos(event.pos)
        if BOARD.collidepoint(point):
            app.combat_drag = point
            app.pressed = None
            return True
    if event.type == pg.MOUSEBUTTONUP and event.button == 2:
        dragging = app.combat_drag is not None
        app.combat_drag = None
        return dragging
    if event.type == pg.MOUSEMOTION and app.combat_drag is not None:
        point = app.logical_pos(event.pos)
        if point == (-1, -1):
            app.combat_drag = None
        else:
            size = view(app).cell_size
            pan(app, (app.combat_drag[0]-point[0])/size, (app.combat_drag[1]-point[1])/size)
            app.combat_drag = point
        return True
    if event.type == pg.MOUSEWHEEL and BOARD.collidepoint(app.mouse):
        mod = getattr(event, 'mod', pg.key.get_mods())
        if mod & pg.KMOD_SHIFT:
            pan(app, dx=-getattr(event, 'x', 0)*2, dy=-event.y*2)
        else:
            zoom(app, event.y, app.mouse)
            if getattr(event, 'x', 0):
                pan(app, dx=-event.x*2)
        return True
    if event.type == pg.KEYDOWN and not app.field:
        if event.key in (pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS, pg.K_MINUS, pg.K_KP_MINUS):
            zoom(app, -1 if event.key in (pg.K_MINUS, pg.K_KP_MINUS) else 1)
            return True
        if event.key in (pg.K_0, pg.K_KP0, pg.K_HOME):
            reset(app)
            return True
        if event.mod & pg.KMOD_SHIFT and event.key in (pg.K_LEFT, pg.K_RIGHT, pg.K_UP, pg.K_DOWN):
            dx, dy = {pg.K_LEFT: (-2, 0), pg.K_RIGHT: (2, 0), pg.K_UP: (0, -2), pg.K_DOWN: (0, 2)}[event.key]
            pan(app, dx, dy)
            return True
    return False
