"""Colony-list scrolling in logical UI coordinates, independent of the campaign."""

import pygame as pg


def row_key(system, planet):
    return f"empire_colony_{system.id}_{planet.id}"


class ColonyScroll:
    def __init__(self):
        self.offset = 0.0
        self.rect = pg.Rect(0, 0, 0, 0)
        self.row_height = 72
        self.keys = ()
        self.drag = None
        self.selected = None
        self.focus_seen = None

    @property
    def maximum(self):
        return max(0, len(self.keys)*self.row_height-self.rect.h)

    def reset(self):
        self.offset = 0.0
        self.drag = self.selected = self.focus_seen = None

    def configure(self, rect, row_height, keys):
        rect, keys = pg.Rect(rect), tuple(keys)
        if (rect, row_height, keys) != (self.rect, self.row_height, self.keys):
            # Keep the same first colony when resizing between table and cards.
            self.offset = self.offset*row_height/self.row_height
            self.drag = self.focus_seen = None
        self.rect, self.row_height, self.keys = rect, row_height, keys
        self.scroll(0)

    def scroll(self, delta):
        self.offset = min(self.maximum, max(0, self.offset+delta))

    def ensure_visible(self, key):
        if key not in self.keys:
            return
        top = self.keys.index(key)*self.row_height
        bottom = top+self.row_height
        if top < self.offset:
            self.offset = top
        elif bottom > self.offset+self.rect.h:
            self.offset = min(top, bottom-self.rect.h)
        self.scroll(0)

    def visible_range(self):
        first = int(self.offset//self.row_height)
        stop = min(len(self.keys), int((self.offset+self.rect.h-1)//self.row_height)+1)
        return range(first, stop)

    def scrollbar(self):
        track = pg.Rect(self.rect.right-12, self.rect.y, 12, self.rect.h)
        if not self.maximum:
            return track, track.copy()
        height = max(32, round(track.h*track.h/(len(self.keys)*self.row_height)))
        thumb = pg.Rect(track.x+2, track.y+round((track.h-height)*self.offset/self.maximum), 8, height)
        return track, thumb


def handle_input(app, event):
    if app.screen != "empire" or app.dialog or app.empire_layout is None:
        return False
    view = app.empire_scroll
    if event.type == pg.WINDOWFOCUSLOST:
        view.drag = None
    if event.type == pg.MOUSEWHEEL and event.y:
        view.scroll(-getattr(event, "precise_y", event.y)*60)
        app.keyboard_mode, app.pressed = False, None
        app.focus_empire_row(restore=False)
        return True
    if event.type in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP, pg.MOUSEMOTION):
        pos = app.logical_pos(event.pos)
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and view.maximum:
            track, thumb = view.scrollbar()
            if track.collidepoint(pos):
                if not thumb.collidepoint(pos):
                    view.scroll((view.rect.h-24)*(1 if pos[1] > thumb.bottom else -1))
                view.drag = pos[1], view.offset
                app.mouse, app.keyboard_mode, app.pressed = pos, False, None
                return True
        elif event.type == pg.MOUSEMOTION and view.drag:
            track, thumb = view.scrollbar()
            origin, offset = view.drag
            view.offset = offset+(pos[1]-origin)*view.maximum/max(1, track.h-thumb.h)
            view.scroll(0)
            app.mouse = pos
            return True
        elif event.type == pg.MOUSEBUTTONUP and event.button == 1 and view.drag:
            view.drag = None
            app.pressed = None
            app.focus_empire_row(restore=False)
            return True
    if event.type != pg.KEYDOWN:
        return False
    if event.key in (pg.K_PAGEUP, pg.K_PAGEDOWN, pg.K_LEFT, pg.K_RIGHT, pg.K_HOME, pg.K_END):
        if event.key == pg.K_HOME:
            view.offset = 0
        elif event.key == pg.K_END:
            view.offset = view.maximum
        else:
            direction = -1 if event.key in (pg.K_PAGEUP, pg.K_LEFT) else 1
            view.scroll(direction*max(view.row_height, view.rect.h-view.row_height))
        app.keyboard_mode, app.pressed = True, None
        app.focus_empire_row(restore=False)
        if view.keys and event.key in (pg.K_HOME, pg.K_END):
            app.focus = view.keys[0 if event.key == pg.K_HOME else -1]
            view.selected = app.focus
        return True
    if event.key in (pg.K_TAB, pg.K_DOWN, pg.K_UP):
        controls = [b.key for b in app.buttons if b.enabled and not b.key.startswith("empire_colony_")]
        footer = [key for key in controls if key in ("galaxy_map", "end_turn")]
        keys = [key for key in controls if key not in footer]+list(view.keys)+footer
        if not keys:
            return True
        direction = -1 if event.key == pg.K_UP or (event.key == pg.K_TAB and getattr(event, "mod", 0) & pg.KMOD_SHIFT) else 1
        index = keys.index(app.focus) if app.focus in keys else (-1 if direction > 0 else 0)
        app.focus = keys[(index+direction) % len(keys)]
        view.ensure_visible(app.focus)
        view.selected = app.focus if app.focus in view.keys else view.selected
        app.keyboard_mode, app.pressed = True, None
        return True
    return False
