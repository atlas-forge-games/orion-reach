"""Place an authored interface in a window while keeping type and game units uniform."""
from dataclasses import dataclass

from functools import lru_cache

import pygame as pg


def interface_scale(window, percent=100):
    width, height = window
    fit = min(width/1440, height/900)
    if height > width:
        # A tall window can wrap columns. Increase type gradually as it
        # turns upright, down to a 960-unit-wide layout at 100%.
        fit *= min(1.5, height/width)
    return fit*percent/100


def view_profile(app):
    screen, game = app.screen, app.game
    if screen == 'settings' and not app.settings_section:
        return 'settings_overview'
    if screen == 'objectives':
        return 'objectives_race' if app.objectives_tab == 'race' else 'objectives_standard'
    if screen == 'research':
        from .research import BRANCHES
        from .research_fields import is_modern
        if not app.research_overview:
            return 'research_detail'
        if not is_modern(BRANCHES):
            return 'research_classic'
    if screen == 'rival' and game.is_observer:
        return 'rival_observer'
    if screen == 'planet' and game.selected_planet is not None:
        if app.selected_habitat():
            return 'planet_habitat'
        planet = game.planet_at(game.selected_system, game.selected_planet)
        if planet.colonized and (planet.owner == 'player' or game.is_observer) and game.system_visible(game.selected_system):
            return 'planet_colony'
    return screen


@dataclass(frozen=True)
class LayoutAxis:
    source: int
    target: int
    fixed_start: int = 0
    fixed_end: int = 0
    target_start: int | None = None
    target_end: int | None = None

    def __post_init__(self):
        if self.target_start is None:
            object.__setattr__(self,'target_start',self.fixed_start)
        if self.target_end is None:
            object.__setattr__(self,'target_end',self.fixed_end)

    @staticmethod
    def _map(value, source, target, start, end, new_start, new_end):
        if value < start and start:
            return value*new_start/start
        if value > source-end and end:
            return target-(source-value)*new_end/end
        return new_start+(value-start)*(target-new_start-new_end)/(source-start-end)

    def place(self, value):
        return self._map(value,self.source,self.target,self.fixed_start,self.fixed_end,
                         self.target_start,self.target_end)

    def unplace(self, value):
        return self._map(value,self.target,self.source,self.target_start,self.target_end,
                         self.fixed_start,self.fixed_end)


@dataclass(frozen=True)
class WindowLayout:
    x: LayoutAxis
    y: LayoutAxis
    # A battle occupies a row with an inspector beside it. Inside
    # that row extra width belongs to the inspector, keeping tactical cells
    # at one scale. The header and dock can still span the row.
    board: tuple | None = None

    @classmethod
    def for_view(cls, source, target, *, fixed_x=(0, 0), fixed_y=(0, 0), board=None):
        return cls(LayoutAxis(source[0], target[0], *fixed_x),
                   LayoutAxis(source[1], target[1], *fixed_y), board)

    @property
    def size(self):
        return self.x.target, self.y.target

    def place(self, point):
        x, y = point
        axis = self._row(y)
        return axis.place(x), self.y.place(y)

    def unplace(self, point):
        x, y = point
        y = self.y.unplace(y)
        return self._row(y).unplace(x), y

    def _row(self, y):
        if self.board is not None:
            top, bottom, axis = self.board
            if top <= y < bottom:
                return axis
        return self.x

    def rect_edges(self, rect):
        # Pick a row once. A panel ending precisely where the dock starts
        # must use the same column geometry for both of its edges.
        row = self._row(rect.centery)
        return (row.place(rect.left), self.y.place(rect.top),
                row.place(rect.right), self.y.place(rect.bottom))

    def source_edges(self, left, top, right, bottom):
        row = self._row(self.y.unplace((top+bottom)/2))
        return row.unplace(left), self.y.unplace(top), row.unplace(right), self.y.unplace(bottom)


@lru_cache(maxsize=64)
def reference_layout(source, available, screen, *, compact=True):
    """Extra room goes into content. Keep outer gutters and dock margins stable."""
    spatial = screen == 'combat'
    if compact and available[0] < (source[0] if spatial else 1200):
        return PanelFlow.build(COMPACT_ROWS.get(screen, SINGLE_COLUMN), available, screen)
    width = available[0] if compact else max(source[0],available[0])
    target = (width, max(source[1],available[1]))
    if target == source:
        return None
    if spatial:
        from .combat_camera import BOARD as board
        row = (board.top, board.bottom, LayoutAxis(source[0], target[0], board.right, 64))
        return WindowLayout.for_view(source, target, fixed_x=(64, 64),
                                     fixed_y=(board.bottom, 100), board=row)
    return WindowLayout.for_view(source, target, fixed_x=(64, 64), fixed_y=(48, 100))


# Each row ends at a boundary between authored panels. When panels will not
# fit alongside each other, start a new row. Drawing and input use the same
# rectangles, so sorting, paging and tooltips continue to use the view's data.
HEADER = (110, (382, 583, 802, 990, 1184))
FOOTER = (900, (816,))
SINGLE_COLUMN = ((900, ()),)
COMPACT_ROWS = {
    'statistics': (HEADER, (180, (900,)), (260, ()), (318, (498, 938)),
                   (789, (1040,)), (814, ()), FOOTER),
    'contact': (HEADER, (810, (708,)), FOOTER),
    'production': ((142, ()), (801, (478, 924)), FOOTER),
    'setup': ((294, ()), (824, (416,)), (900, (960,))),
    'race_select': ((285, ()), (800, (878,)), (900, (960,))),
    'objectives_race': (HEADER, (179, ()), (282, (990,)), (802, (830,)), FOOTER),
    'objectives_standard': (HEADER, (179, ()), (282, (990,)), (713, (499, 945)),
                            (810, ()), FOOTER),
    'planet': ((50, (660,)), (306, (278, 1068)), (810, ()), FOOTER),
    'planet_colony': ((50, (660,)), (306, (278, 1068)), (702, ()), (810, (946,)), FOOTER),
    'planet_habitat': ((50, (660,)), (306, (278, 1068)), (840, (750,)), FOOTER),
    'combat': ((110, ()), (749, (1050,)), (810, ()), FOOTER),
    'designer': (HEADER, (208, ()), (808, (342, 973)), FOOTER),
    'specialists': (HEADER, (280, ()), (823, (422,)), FOOTER),
    'exploration': (HEADER, (282, ()), (385, (500, 946)), (820, (940,)), FOOTER),
    'ground': (HEADER, (214, ()), (400, (712,)), (580, ()), (806, (896,)), FOOTER),
    'shipyard': (HEADER, (300, ()), (800, (661,)), FOOTER),
    'fleet': (HEADER, (282, ()), (818, (954,)), FOOTER),
    'hyperlane': (HEADER, (285, ()), (686, (797,)), (806, ()), FOOTER),
    'megastructure': (HEADER, (285, ()), (745, (797,)), (806, ()), FOOTER),
    'encounters': (HEADER, (290, ()), (739, (590,)), (830, ()), FOOTER),
    'system': (HEADER, (304, ()), (632, ()), (802, (393,725,1057)), FOOTER),
    'settings': ((314, ()), (715, (336,)), (900, ())),
    'settings_overview': ((314,()), (500,(720,)), (705,(720,)), (900,())),
    'sim_setup': ((110,(705,)), (204,(999,)), (732,(436,1005)), (832,(693,)), (900,(982,))),
    'diplomacy': (HEADER, (181,(813,)), (320,(753,)), (784,(416,)), (810,()), FOOTER),
    'fleets': (HEADER, (282,()), (380,(499,945)), (422,()),
               *((bottom,(953,)) for bottom in (510,597,684,771)), (819,()), FOOTER),
    'rival': (HEADER, (282,()), (398,(499,945)), (800,()), FOOTER),
    'rival_observer': (HEADER, (284,()), (398,(319,580,842,1104)), (800,(815,)), FOOTER),
    'info': ((218,()), (802,(288,628)), FOOTER),
    'research': (HEADER, (296,()), (464,(720,)), (632,(720,)), (803,(720,)), FOOTER),
    'research_classic': (HEADER, (296,()), (821,(720,)), FOOTER),
    'research_detail': (HEADER, (405,()), (812,(396,)), FOOTER),
    'council': ((315,()), (752,()), (810,()), FOOTER),
    'observer': ((309,()), (703,()), (810,()), FOOTER),
    'news': (HEADER, (821,()), FOOTER),
    'result': ((572,()), (715,(721,)), (811,()), FOOTER),
}


@dataclass(frozen=True)
class Pane:
    source: pg.Rect
    target: pg.Rect
    columns: LayoutAxis
    spatial: bool = False

    def place(self, x, y):
        return (self.target.x+self.columns.place(x-self.source.x),
                self.target.y+(y-self.source.y)*self.target.h/self.source.h)

    def unplace(self, x, y):
        return (self.source.x+self.columns.unplace(x-self.target.x),
                self.source.y+(y-self.target.y)*self.source.h/self.target.h)


@dataclass(frozen=True)
class PanelFlow:
    panes: tuple
    size: tuple

    @classmethod
    def build(cls, rows, available, screen):
        width, height = available
        top = next_y = 0
        panes = []
        for bottom, divisions in rows:
            edges = (0, *divisions, 1440)
            cells = [pg.Rect(left, top, right-left, bottom-top)
                     for left, right in zip(edges, edges[1:])]
            while cells:
                line = [cells.pop(0)]
                total = line[0].w
                while cells and total+cells[0].w <= width:
                    cell = cells.pop(0)
                    line.append(cell)
                    total += cell.w
                # Preserve the aspect of the battle grid, including
                # the camera positions used for zoom and selection.
                spatial = screen == 'combat' and top == 110 and line[0].left == 0
                row_height = round((bottom-top)*width/total) if spatial else bottom-top
                if bottom == 900:
                    row_height = max(90, row_height)
                left = used = 0
                for cell in line:
                    used += cell.w
                    right = round(used*width/total)
                    columns = LayoutAxis(cell.w,right-left)
                    if divisions and 180 <= top and bottom < 900 and not spatial:
                        gutter = 24 if screen.startswith('planet') or screen in ('combat','production') else 64
                        columns = LayoutAxis(cell.w,right-left, gutter if cell.left == 0 else 6,
                                             gutter if cell.right == 1440 else 6,
                                             24 if left == 0 else 6,24 if right == width else 6)
                    panes.append(Pane(cell, pg.Rect(left,next_y,right-left,row_height), columns,spatial))
                    left = right
                next_y += row_height
            top = bottom
        if height > next_y:
            for pane in panes:
                if pane.source.h == 900:
                    pane.target.h = height
                elif pane.source.bottom == 900:
                    pane.target.y += height-next_y
        return cls(tuple(panes), (width, max(height, next_y)))

    def pane_at(self, point):
        x, y = point
        inside = max(0,min(1439,x)), max(0,min(899,y))
        return next((p for p in self.panes if p.source.collidepoint(inside)), self.panes[-1])

    def place(self, point):
        return self.pane_at(point).place(*point)

    def unplace(self, point):
        pane = next((p for p in self.panes if p.target.collidepoint(point)), None)
        return pane.unplace(*point) if pane else (-1, -1)

    def line_segments(self, start, end):
        """Clip a rule to each panel when its two ends wrap onto different rows."""
        first = self.pane_at(start)
        if first is self.pane_at(end):
            return None
        parts = []
        for pane in self.panes:
            segment = pane.source.clipline(start, end)
            if segment:
                parts.append(tuple(pane.place(*point) for point in segment))
        return parts

    def rect_edges(self, rect):
        if rect == pg.Rect(0, 0, 1440, 900):
            return (0, 0, *self.size)
        pane = self.pane_at(rect.center)
        return (*pane.place(*rect.topleft), *pane.place(*rect.bottomright))

    def panel_slots(self, rect):
        """A card spanning wrapped columns needs a background on both rows."""
        slots = []
        for pane in self.panes:
            part = rect.clip(pane.source)
            if not part.w or not part.h:
                continue
            left,top = map(round,pane.place(*part.topleft))
            right,bottom = map(round,pane.place(*part.bottomright))
            slot = pg.Rect(left,top,right-left,bottom-top)
            if slots and slots[-1].right == left and slots[-1].top == top and slots[-1].h == slot.h:
                slots[-1].union_ip(slot)
            else:
                slots.append(slot)
        return slots

    def source_edges(self, left, top, right, bottom):
        center = ((left+right)/2,(top+bottom)/2)
        pane = next((p for p in self.panes if p.target.collidepoint(center)), self.panes[-1])
        return (*pane.unplace(left,top), *pane.unplace(right,bottom))
