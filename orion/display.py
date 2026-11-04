"""Native-resolution drawing for the existing logical-coordinate interface.

Only Canvas targets are transformed. Ordinary pygame surfaces (art, masks,
previews and combat effects) retain pygame's normal behaviour. This lets the
existing scene code keep its coordinates without resampling rendered fonts.
"""

from functools import wraps
from contextlib import contextmanager
import math
import pygame as pg

UI_SCALES = (100, 125, 150, 175)
_DRAW_INSTALLED = False


class Canvas(pg.Surface):
    def __init__(self, size, scale=1.0, layout=None, *, pixel_size=None):
        self.logical_size = tuple(map(int, size))
        self.scale = float(scale)
        self.layout = layout
        extent = layout.size if layout else size
        super().__init__(pixel_size or tuple(max(1, round(v*self.scale)) for v in extent))

    @staticmethod
    def fitted_pixels(extent, available, scale, window):
        # A rounded logical width can round back one pixel larger at 175%.
        # An axis that fits gets exactly the window's pixels and no scrollbar.
        return tuple(pixels if length == room else max(1, round(length*scale))
                     for length,room,pixels in zip(extent,available,window))

    @property
    def pixel_size(self):
        return pg.Surface.get_size(self)

    def get_size(self):
        return self.logical_size

    def get_width(self):
        return self.logical_size[0]

    def get_height(self):
        return self.logical_size[1]

    def get_rect(self, **kwargs):
        rect = pg.Rect((0, 0), self.logical_size)
        for key, value in kwargs.items():
            setattr(rect, key, value)
        return rect

    def get_at(self, pos):
        return pg.Surface.get_at(self, self.point(pos))

    def set_at(self, pos, color):
        pg.Surface.fill(self, color, self.rect((*pos, 1, 1)))

    def point(self, pos):
        if self.layout:
            pos = self.layout.place(pos)
        return tuple(round(v*self.scale) for v in pos)

    def logical_point(self, pos):
        point = tuple(v/self.scale for v in pos)
        return self.layout.unplace(point) if self.layout else point

    def slot(self, rect):
        """Return a panel's allocated rectangle in native UI units."""
        if not self.layout:
            return pg.Rect(rect)
        left, top, right, bottom = map(round, self.layout.rect_edges(pg.Rect(rect)))
        return pg.Rect(left, top, right-left, bottom-top)

    def source_slot(self, rect):
        if not self.layout:
            return pg.Rect(rect)
        left, top, right, bottom = map(round, self.layout.source_edges(
            rect.left, rect.top, rect.right, rect.bottom))
        return pg.Rect(left, top, right-left, bottom-top)

    @contextmanager
    def native_space(self):
        """Draw inside allocated panels with normal font, icon and padding metrics."""
        layout, size = self.layout, self.logical_size
        regions = getattr(self, 'text_regions', [])
        start = len(regions)
        self.layout, self.logical_size = None, layout.size
        try:
            yield
        finally:
            self.layout, self.logical_size = layout, size
            for index in range(start, len(regions)):
                region, label = regions[index]
                regions[index] = self.source_slot(region), label

    def rect(self, value):
        r = pg.Rect(value)
        if r.topleft == (0,0) and r.size == self.logical_size:
            return pg.Rect((0,0), self.pixel_size)
        if self.layout:
            left, top, right, bottom = (round(n*self.scale) for n in self.layout.rect_edges(r))
            return pg.Rect(left, top, right-left, bottom-top)
        left, top = self.point(r.topleft)
        right, bottom = self.point(r.bottomright)
        return pg.Rect(left, top, right-left, bottom-top)

    def logical_rect(self, value):
        r = pg.Rect(value)
        if r.topleft == (0,0) and r.size == self.pixel_size:
            return self.get_rect()
        edges = (r.left/self.scale, r.top/self.scale, r.right/self.scale, r.bottom/self.scale)
        if self.layout:
            edges = self.layout.source_edges(*edges)
        left, top = map(math.floor, edges[:2])
        right, bottom = map(math.ceil, edges[2:])
        return pg.Rect(left, top, right-left, bottom-top)

    def get_clip(self):
        return self.logical_rect(pg.Surface.get_clip(self))

    def set_clip(self, rect=None):
        return pg.Surface.set_clip(self, None if rect is None else self.rect(rect))

    def fill(self, color, rect=None, special_flags=0):
        drawn = pg.Surface.fill(self, color, None if rect is None else self.rect(rect), special_flags)
        return self.logical_rect(drawn)

    def blit(self, source, dest, area=None, special_flags=0):
        pos = dest.topleft if isinstance(dest, pg.Rect) else dest[:2]
        if isinstance(source, Canvas):
            logical = source.get_size()
            if area is None and pos == (0,0) and self.layout == source.layout and self.pixel_size == source.pixel_size:
                return self.logical_rect(pg.Surface.blit(self, source, (0,0), special_flags=special_flags))
            if area is not None:
                logical = pg.Rect(area).size
                source = pg.Surface.subsurface(source, source.rect(area))
        else:
            if area is not None:
                source = source.subsurface(pg.Rect(area).clip(source.get_rect()))
            logical = source.get_size()
        target = self.rect((*pos, *logical))
        # Images retain their proportions. Full-screen backdrops are cropped
        # to cover the window; portraits and other art fit their layout slot.
        if self.layout and tuple(logical) == self.logical_size and tuple(pos) == (0, 0):
            return self.blit_cover(source, target)
        if self.layout:
            target = pg.Rect((0, 0), logical).fit(target)
        target_size = tuple(max(1, n) for n in target.size)
        if pg.Surface.get_size(source) != target_size:
            source = pg.transform.smoothscale(source, target_size)
        result = pg.Surface.blit(self, source, target.topleft, special_flags=special_flags)
        return self.logical_rect(result)

    def blit_cover(self, source, target):
        """Fill a native pixel rectangle using a centered crop of the artwork."""
        width, height = pg.Surface.get_size(source)
        crop = target.fit(pg.Rect(0, 0, width, height))
        image = pg.Surface.subsurface(source, crop)
        if pg.Surface.get_size(image) != target.size:
            image = pg.transform.smoothscale(image, target.size)
        return self.logical_rect(pg.Surface.blit(self, image, target.topleft))

    def blits(self, blit_sequence, doreturn=True):
        result = [self.blit(*entry) for entry in blit_sequence]
        return result if doreturn else None

    def copy(self):
        result = Canvas(self.logical_size, self.scale, self.layout, pixel_size=self.pixel_size)
        pg.Surface.blit(result, self, (0, 0))
        result.set_clip(self.get_clip())
        return result

    def subsurface(self, rect):
        result = pg.Surface.subsurface(self, self.rect(rect))
        result.logical_size = pg.Rect(rect).size
        result.scale = self.scale
        result.layout = None
        return result

    def blit_native(self, source, pos):
        """Blit text already rasterized at the final pixel size."""
        return pg.Surface.blit(self, source, self.point(pos))


def install_draw_adapter():
    """Dispatch pygame primitives to native pixels only for our Canvas class."""
    global _DRAW_INSTALLED
    if _DRAW_INSTALLED:
        return
    _DRAW_INSTALLED = True

    def install(name, transform):
        original = getattr(pg.draw, name)

        @wraps(original)
        def draw(surface, color, *args, **kwargs):
            if not isinstance(surface, Canvas):
                return original(surface, color, *args, **kwargs)
            if name == 'line' and hasattr(surface.layout, 'line_segments') and len(args) >= 2:
                segments = surface.layout.line_segments(args[0], args[1])
                if segments is not None:
                    thickness = args[2] if len(args) > 2 else kwargs.get('width',1)
                    for start, end in segments:
                        a, b = [tuple(round(n*surface.scale) for n in p) for p in (start,end)]
                        original(surface, color, a, b, stroke(surface,thickness))
                    return pg.Rect(args[0],(1,1)).union(pg.Rect(args[1],(1,1)))
            args, kwargs = transform(surface, list(args), dict(kwargs))
            return surface.logical_rect(original(surface, color, *args, **kwargs))
        setattr(pg.draw, name, draw)

    def arg(args, kwargs, index, key, change, default=None):
        if len(args) > index:
            args[index] = change(args[index])
        elif key in kwargs:
            kwargs[key] = change(kwargs[key])
        elif default is not None:
            kwargs[key] = change(default)

    def stroke(s, width):
        return max(1, round(width*s.scale)) if width > 0 else width

    def rectangle(s, a, k):
        arg(a, k, 0, 'rect', s.rect)
        arg(a, k, 1, 'width', lambda n: stroke(s, n))
        for i, key in enumerate(('border_radius', 'border_top_left_radius',
                                 'border_top_right_radius', 'border_bottom_left_radius',
                                 'border_bottom_right_radius'), 2):
            arg(a, k, i, key, lambda n: stroke(s, n))
        return a, k

    def ellipse(s, a, k):
        arg(a, k, 0, 'rect', s.rect)
        arg(a, k, 1, 'width', lambda n: stroke(s, n))
        return a, k

    def circle(s, a, k):
        unit = s.scale
        if hasattr(s.layout,'pane_at'):
            pane = s.layout.pane_at(a[0] if a else k['center'])
            if pane.spatial:
                unit *= pane.target.w/pane.source.w
        arg(a, k, 0, 'center', s.point)
        arg(a, k, 1, 'radius', lambda n: max(0, round(n*unit)))
        arg(a, k, 2, 'width', lambda n: stroke(s, n))
        return a, k

    def line(s, a, k):
        arg(a, k, 0, 'start_pos', s.point)
        arg(a, k, 1, 'end_pos', s.point)
        arg(a, k, 2, 'width', lambda n: stroke(s, n), 1)
        return a, k

    def lines(s, a, k):
        arg(a, k, 1, 'points', lambda pts: [s.point(p) for p in pts])
        arg(a, k, 2, 'width', lambda n: stroke(s, n), 1)
        return a, k

    def aalines(s, a, k):
        arg(a, k, 1, 'points', lambda pts: [s.point(p) for p in pts])
        return a, k

    def polygon(s, a, k):
        arg(a, k, 0, 'points', lambda pts: [s.point(p) for p in pts])
        arg(a, k, 1, 'width', lambda n: stroke(s, n))
        return a, k

    def arc(s, a, k):
        arg(a, k, 0, 'rect', s.rect)
        arg(a, k, 3, 'width', lambda n: stroke(s, n), 1)
        return a, k

    for name, transform in (('rect', rectangle), ('ellipse', ellipse), ('circle', circle),
                            ('line', line), ('lines', lines), ('aalines', aalines),
                            ('polygon', polygon), ('arc', arc)):
        install(name, transform)


class DisplayView:
    """A scrollable, zoomable viewport with exact logical mouse coordinates."""
    BAR = 12

    def __init__(self):
        install_draw_adapter()
        self.offset = [0, 0]
        self.maximum = [0, 0]
        self.viewport = pg.Rect(0, 0, 1440, 900)
        self.bars = {}
        self.drag = None
        self.screen = None
        self.focus = None

    def configure(self, window_size, canvas, screen):
        physical = canvas.pixel_size
        geometry = (tuple(window_size), physical, canvas.layout, canvas.scale, screen)
        if geometry != getattr(self, 'geometry', None):
            self.drag = None
            self.bars = {}
            self.geometry = geometry
        if screen != self.screen:
            self.offset = [0, 0]
            self.focus = None
            self.screen = screen
        self.maximum = [max(0, physical[i]-window_size[i]) for i in (0, 1)]
        self.offset = [min(max(0, self.offset[i]), self.maximum[i]) for i in (0, 1)]
        origin = [max(0, (window_size[i]-physical[i])//2)-self.offset[i] for i in (0, 1)]
        self.viewport = pg.Rect(origin, physical)
        self.canvas = canvas
        self.window_size = window_size

    def ensure_visible(self, rect):
        native = self.canvas.rect(rect)
        for axis in (0, 1):
            start = native.x if axis == 0 else native.y
            end = native.right if axis == 0 else native.bottom
            span = self.window_size[axis]-self.BAR-8
            if start < self.offset[axis]+8:
                self.offset[axis] = max(0, int(start)-8)
            elif end > self.offset[axis]+span:
                self.offset[axis] = min(self.maximum[axis], max(0, int(end-span)))

    def scroll(self, dx=0, dy=0):
        self.offset = [min(max(0, self.offset[i]+d), self.maximum[i])
                       for i, d in enumerate((dx, dy))]

    def handle_event(self, event, app):
        if event.type == pg.KEYDOWN and getattr(event, 'mod', 0) & pg.KMOD_CTRL:
            if event.key in (pg.K_EQUALS, pg.K_PLUS, pg.K_KP_PLUS, pg.K_MINUS, pg.K_KP_MINUS, pg.K_0):
                old = app.settings.get('ui_scale', 100)
                delta = -25 if event.key in (pg.K_MINUS, pg.K_KP_MINUS) else 25
                app.set_ui_scale(100 if event.key == pg.K_0 else max(100, min(175, old+delta)))
                return True
        if event.type == pg.WINDOWFOCUSLOST:
            self.drag = None
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for axis, (track, thumb) in self.bars.items():
                if track.collidepoint(event.pos):
                    self.drag = (axis, event.pos[axis], self.offset[axis])
                    if not thumb.collidepoint(event.pos):
                        span = track.w if axis == 0 else track.h
                        start = track.x if axis == 0 else track.y
                        self.offset[axis] = round(self.maximum[axis]*max(0, min(1, (event.pos[axis]-start)/span)))
                        self.drag = (axis, event.pos[axis], self.offset[axis])
                    app.pressed = None
                    app.keyboard_mode = False
                    return True
        if event.type == pg.MOUSEMOTION and self.drag:
            axis, initial, offset = self.drag
            track, thumb = self.bars[axis]
            travel = (track.w-thumb.w) if axis == 0 else (track.h-thumb.h)
            self.offset[axis] = min(self.maximum[axis], max(0, round(offset+(event.pos[axis]-initial)*self.maximum[axis]/max(1, travel))))
            return True
        if event.type == pg.MOUSEBUTTONUP and event.button == 1 and self.drag:
            self.drag = None
            return True
        if event.type == pg.MOUSEWHEEL and any(self.maximum):
            modifiers = pg.key.get_mods()
            # Plain wheel retains map zoom and list paging on the legacy views.
            from .window_layout import PanelFlow
            compact = isinstance(app.canvas.layout, PanelFlow)
            if not app.dialog and app.on_galaxy_chart():
                if app.map_rect.collidepoint(app.mouse):
                    return False
                pane = app.galaxy_layout.inspector
                # Within a paged list the wheel changes page; the gutter and
                # Shift+wheel can always scroll the rest of a tall layout.
                compact = not (pane and pane.collidepoint(app.mouse) and app.inspector_has_pages())
            elif compact and app.screen == 'combat':
                from .combat_camera import BOARD
                compact = not BOARD.collidepoint(app.mouse)
            if ((app.screen == 'empire' or compact) and not app.dialog) or modifiers & pg.KMOD_SHIFT:
                self.scroll(-event.x*70, -event.y*70)
                if not self.maximum[1]:
                    self.scroll(-event.y*70, 0)
                app.keyboard_mode = False
                return True
        return False

    def present(self, app):
        size = app.window.get_size()
        self.configure(size, app.canvas, app.screen)
        if app.keyboard_mode and app.focus != self.focus:
            focused = next((b for b in app.buttons if b.key == app.focus), None)
            if focused:
                self.ensure_visible(focused.rect)
                self.configure(size, app.canvas, app.screen)
            self.focus = app.focus
        app.viewport = self.viewport.copy()
        app.window.fill((2, 5, 9))
        # No final smoothscale: text and primitives already use display pixels.
        app.window.blit(app.canvas, self.viewport.topleft)
        self.bars = {}
        for axis in (0, 1):
            if not self.maximum[axis]:
                continue
            length = size[axis]-self.BAR
            track = pg.Rect(0, size[1]-self.BAR, length, self.BAR) if axis == 0 else pg.Rect(size[0]-self.BAR, 0, self.BAR, length)
            thumb_length = max(30, round(length*size[axis]/self.viewport.size[axis]))
            pos = round((length-thumb_length)*self.offset[axis]/self.maximum[axis])
            thumb = pg.Rect(pos, track.y+2, thumb_length, self.BAR-4) if axis == 0 else pg.Rect(track.x+2, pos, self.BAR-4, thumb_length)
            pg.draw.rect(app.window, (18, 30, 42), track)
            pg.draw.rect(app.window, (149, 177, 195), thumb, border_radius=3)
            self.bars[axis] = (track, thumb)
        pg.display.flip()
