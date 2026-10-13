"""A bounded, display-only camera for the strategic map and its controls."""

from dataclasses import dataclass

import pygame as pg

from .ui import INK, MUTED, panel, text

MIN_ZOOM = 1.0
MAX_ZOOM = 4.0
ZOOM_STEP = 1.25
PAN_KEYS = {pg.K_LEFT: (1, 0), pg.K_RIGHT: (-1, 0),
            pg.K_UP: (0, 1), pg.K_DOWN: (0, -1)}


@dataclass
class GalaxyCamera:
    zoom: float = MIN_ZOOM
    offset_x: float = 0.0
    offset_y: float = 0.0

    def transform(self, point, rect):
        cx, cy = rect.x+rect.w/2, rect.y+rect.h/2
        return (cx+(point[0]-cx)*self.zoom+self.offset_x,
                cy+(point[1]-cy)*self.zoom+self.offset_y)

    def unproject(self, point, rect):
        cx, cy = rect.x+rect.w/2, rect.y+rect.h/2
        return (cx+(point[0]-cx-self.offset_x)/self.zoom,
                cy+(point[1]-cy-self.offset_y)/self.zoom)

    def position(self, x, y, rect):
        return self.transform((rect.x+40+x*(rect.w-80), rect.y+32+y*(rect.h-64)), rect)

    def radii(self, distance, rect):
        return distance/140*(rect.w-80)*self.zoom, distance/100*(rect.h-64)*self.zoom

    def clamp(self, rect):
        limit_x, limit_y = rect.w*(self.zoom-1)/2, rect.h*(self.zoom-1)/2
        self.offset_x = min(limit_x, max(-limit_x, self.offset_x))
        self.offset_y = min(limit_y, max(-limit_y, self.offset_y))

    def pan(self, dx, dy, rect):
        self.offset_x += dx
        self.offset_y += dy
        self.clamp(rect)

    def zoom_at(self, steps, anchor, rect):
        before = self.zoom
        self.zoom = min(MAX_ZOOM, max(MIN_ZOOM, before*ZOOM_STEP**max(-20, min(20, steps))))
        ratio = self.zoom/before
        cx, cy = rect.x+rect.w/2, rect.y+rect.h/2
        self.offset_x = anchor[0]-cx-(anchor[0]-cx-self.offset_x)*ratio
        self.offset_y = anchor[1]-cy-(anchor[1]-cy-self.offset_y)*ratio
        self.clamp(rect)

    def center_on(self, x, y, rect):
        point = self.position(x, y, rect)
        self.pan(rect.centerx-point[0], rect.centery-point[1], rect)

    def reset(self):
        self.zoom, self.offset_x, self.offset_y = MIN_ZOOM, 0.0, 0.0


def clear_gesture(app):
    app.map_drag = None
    app.map_pan_keys.clear()


def handle_map_input(app, event, rect):
    """Consume camera gestures before selection/order handlers can see them."""
    if event.type == pg.WINDOWFOCUSLOST:
        clear_gesture(app)
        return False
    if event.type == pg.KEYUP:
        app.map_pan_keys.discard(event.key)
        if event.key in (pg.K_LSHIFT, pg.K_RSHIFT):
            app.map_pan_keys.clear()
    if app.screen != "galaxy" or app.dialog:
        clear_gesture(app)
        return False
    if app.map_drag:
        button, last = app.map_drag
        if event.type == pg.MOUSEMOTION:
            # Raw window deltas also work while the cursor crosses a letterbox.
            dx = (event.pos[0]-last[0])*1440/app.viewport.w
            dy = (event.pos[1]-last[1])*900/app.viewport.h
            app.map_camera.pan(dx, dy, rect)
            app.map_drag = (button, event.pos)
            app.pressed = None
            return True
        if event.type == pg.MOUSEBUTTONUP and event.button == button:
            app.map_drag = None
            app.pressed = None
            return True
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            clear_gesture(app)
            return True
        if event.type in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            return True
    if event.type == pg.MOUSEBUTTONDOWN and event.button in (2, 3):
        point = app.logical_pos(event.pos)
        if rect.collidepoint(point) and point[1] >= rect.y+38:
            app.mouse = point
            app.keyboard_mode = False
            app.pressed = None
            app.map_drag = (event.button, event.pos)
            return True
    if event.type == pg.MOUSEWHEEL and rect.collidepoint(app.mouse):
        horizontal = getattr(event, "x", 0)
        if pg.key.get_mods() & pg.KMOD_SHIFT:
            app.map_camera.pan(-horizontal*60, event.y*60, rect)
        else:
            if event.y:
                app.zoom_map(event.y, app.mouse)
            if horizontal:
                app.map_camera.pan(-horizontal*60, 0, rect)
        app.pressed = None
        return True
    if event.type != pg.KEYDOWN or app.field:
        return False
    if event.key in PAN_KEYS and event.mod & pg.KMOD_SHIFT:
        if event.key not in app.map_pan_keys:
            dx, dy = PAN_KEYS[event.key]
            app.map_camera.pan(dx*36, dy*36, rect)
        app.map_pan_keys.add(event.key)
        app.pressed = None
        return True
    if event.key in (pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS, pg.K_MINUS, pg.K_KP_MINUS):
        app.zoom_map(-1 if event.key in (pg.K_MINUS, pg.K_KP_MINUS) else 1)
        return True
    if event.key in (pg.K_0, pg.K_KP0, pg.K_HOME):
        app.fit_map()
        return True
    if event.key == pg.K_c:
        app.center_map()
        return True
    return False


def update_map_input(app, elapsed, rect):
    if app.screen != "galaxy" or app.dialog:
        clear_gesture(app)
        return
    dx = sum(PAN_KEYS[key][0] for key in app.map_pan_keys)
    dy = sum(PAN_KEYS[key][1] for key in app.map_pan_keys)
    if dx or dy:
        app.map_camera.pan(dx*420*elapsed, dy*420*elapsed, rect)


def draw_map_navigation(app, rect):
    """Keep navigation fixed above the moving map; block hidden click targets."""
    toolbar = pg.Rect(rect.x+2, rect.y+2, rect.w-4, 36)
    panel(app.canvas, toolbar, (9, 20, 29))
    app.button("map_toolbar", "", toolbar, lambda: None, "hotspot")
    x, y = rect.x+12, rect.y+7
    app.button("map_zoom_out", "−", (x, y, 32, 26), lambda: app.zoom_map(-1),
               "tab", enabled=app.map_camera.zoom > MIN_ZOOM)
    text(app.canvas, f"{app.map_camera.zoom*100:.0f}%", (x+40, y+7), 11, INK, "mono")
    app.button("map_zoom_in", "+", (x+89, y, 32, 26), lambda: app.zoom_map(1),
               "tab", enabled=app.map_camera.zoom < MAX_ZOOM)
    app.button("map_fit", "Fit · 0", (x+130, y, 72, 26), app.fit_map, "tab")
    app.button("map_center", "Center · C", (x+210, y, 96, 26), app.center_map, "tab")
    text(app.canvas, "Wheel: zoom · Right-drag: pan", (x+320, y+8), 10, MUTED)
