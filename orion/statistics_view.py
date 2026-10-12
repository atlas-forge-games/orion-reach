"""Diplomacy graphs with turn inspection and independently visible empire lines."""

import math
import pygame as pg

from .statistics import METRICS, visible_series
from .races import RACES
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, panel, shorten, text, text_image

PLOT = pg.Rect(144, 396, 844, 316)


def centered(surface, value, pos, size, color, family="sans"):
    image = text_image(value, size, color, family)
    surface.blit(image, (pos[0]-image.get_width()/2, pos[1]))


def axis_ticks(values):
    low, high = min([0, *values]), max([0, *values])
    if low == high:
        return (0, 1)
    raw = (high-low)/5
    power = 10**math.floor(math.log10(raw))
    step = max(1, next(n for n in (1, 2, 5, 10) if n*power >= raw)*power)
    start, end = math.floor(low/step), math.ceil(high/step)
    return tuple(round(n*step, 8) for n in range(start, end+1))


def number(value):
    for scale, suffix in ((10**12, "T"), (10**9, "B"), (10**6, "M"), (10**3, "K")):
        if abs(value) >= scale*10:
            return f"{value/scale:.1f}".removesuffix(".0")+suffix
    return f"{value:,.0f}"


def compact_points(points):
    """Keep each pixel column's extrema so long histories retain short spikes."""
    result, group = [], []
    for point in points:
        if group and round(point[0]) != round(group[0][0]):
            keep = {0, len(group)-1, min(range(len(group)), key=lambda i: group[i][1]),
                    max(range(len(group)), key=lambda i: group[i][1])}
            result.extend(group[i] for i in sorted(keep))
            group = []
        group.append(point)
    if group:
        keep = {0, len(group)-1, min(range(len(group)), key=lambda i: group[i][1]),
                max(range(len(group)), key=lambda i: group[i][1])}
        result.extend(group[i] for i in sorted(keep))
    return result


def draw_statistics(app):
    game, surface = app.game, app.canvas
    metric = METRICS[app.statistics_metric]
    series = visible_series(game, app.statistics_metric)
    app.chrome("DIPLOMACY · STATISTICS")
    back = "← Observer reports · Esc" if game.is_observer else "← Diplomacy · Esc"
    app.button("statistics_back", back, (64, 124, 283, 46), app.close_statistics, "ghost")
    app.button("statistics_galaxy", "Galaxy map", (364, 124, 172, 46), lambda: app.go("galaxy"), "ghost")
    for index, (span, label) in enumerate(((0, "All turns"), (25, "Last 25"), (100, "Last 100"))):
        app.button(f"statistics_range_{span}", label, (946+index*145, 124, 140, 46),
                   lambda n=span: app.set_statistics_range(n), "tab_active" if app.statistics_range == span else "tab")
    text(surface, "Empire statistics", (64, 188), 39, INK, "title")
    text(surface, "Full recorded history appears when contact is established. Your current turn updates as orders change."
         if not game.is_observer else "Historical development of every civilization. The Observer has no empire of its own.",
         (66, 237), 14, MUTED)
    for index, (key, item) in enumerate(METRICS.items()):
        app.button("statistics_metric_"+key, item.title, (64+index*220, 268, 208, 37),
                   lambda k=key: app.set_statistics_metric(k), "tab_active" if key == app.statistics_metric else "tab")

    panel(surface, (64, 323, 966, 464))
    panel(surface, (1050, 323, 326, 464))
    text(surface, metric.title, (87, 341), 23, INK)
    text(surface, metric.unit.upper(), (1006, 350), 11, GOLD, "mono", right=True)
    text(surface, "CURRENT TURN "+str(game.turn), (87, 374), 10, MUTED, "mono")
    start = max(1, game.turn-app.statistics_range+1) if app.statistics_range else 1
    stop = game.turn
    shown = {o: [(t, v) for t, v in rows if start <= t <= stop]
             for o, rows in series.items() if o not in app.statistics_hidden}
    ticks = axis_ticks([value for rows in shown.values() for _, value in rows])
    low, high = ticks[0], ticks[-1]

    def x(turn):
        return PLOT.centerx if start == stop else PLOT.left+(turn-start)/(stop-start)*PLOT.width

    def y(value):
        return PLOT.bottom-(value-low)/(high-low)*PLOT.height

    for value in ticks:
        at = round(y(value))
        pg.draw.line(surface, MUTED if value == 0 else LINE, (PLOT.left, at), (PLOT.right, at))
        text(surface, number(value), (PLOT.left-14, at-7), 11, MUTED, "mono", right=True)
    turns = sorted({round(start+(stop-start)*index/5) for index in range(6)})
    for turn in turns:
        at = round(x(turn))
        pg.draw.line(surface, LINE, (at, PLOT.top), (at, PLOT.bottom))
        centered(surface, str(turn), (at, PLOT.bottom+13), 11, MUTED, "mono")
    centered(surface, "TURN", (PLOT.centerx, 755), 10, GOLD, "mono")
    cursor = stop
    hovering = not app.dialog and PLOT.collidepoint(app.mouse)
    if hovering:
        cursor = max(start, min(stop, round(start+(app.mouse[0]-PLOT.left)/PLOT.width*(stop-start))))
        pg.draw.line(surface, GOLD, (round(x(cursor)), PLOT.top), (round(x(cursor)), PLOT.bottom))
    app.statistics_cursor_turn = cursor
    old_clip = surface.get_clip()
    surface.set_clip(PLOT.inflate(8, 8))
    for owner, rows in shown.items():
        color = app.empire_color(owner)
        points = compact_points([(x(turn), y(value)) for turn, value in rows])
        if len(points) > 1:
            pg.draw.lines(surface, color, False, points, 2)
            pg.draw.aalines(surface, color, False, points)
        if points:
            pg.draw.circle(surface, color, (round(points[-1][0]), round(points[-1][1])), 4)
        inspected = next((v for t, v in rows if t == cursor), None)
        if hovering and inspected is not None:
            pg.draw.circle(surface, color, (round(x(cursor)), round(y(inspected))), 5)
            pg.draw.circle(surface, INK, (round(x(cursor)), round(y(inspected))), 5, 1)
    surface.set_clip(old_clip)
    if not shown:
        centered(surface, "Select a civilization to show its graph.", PLOT.center, 18, MUTED)
    elif game.turn == 1:
        centered(surface, "Advance turns to extend the history.", (PLOT.centerx, PLOT.top+20), 14, MUTED)

    text(surface, f"TURN {cursor} · "+("LIVE" if cursor == game.turn else "HISTORY"), (1070, 343), 12, GOLD, "mono")
    for index, (owner, rows) in enumerate(series.items()):
        top = 370+index*54
        color = app.empire_color(owner)
        selected = owner not in app.statistics_hidden
        value = next((v for t, v in rows if t == cursor), None)
        empire = game._empire(owner)
        app.button("statistics_empire_"+owner, "", (1064, top, 298, 49),
                   lambda o=owner: app.toggle_statistics_empire(o), "hotspot")
        pg.draw.line(surface, color if selected else FAINT, (1072, top+15), (1091, top+15), 3 if selected else 1)
        label = game.empire_name_for(owner)
        value_text = f"{value:,}" if value is not None else "—"
        value_width = text_image(value_text, 13, color).get_width()
        text(surface, shorten(label, min(170, 238-value_width), 14), (1100, top+3), 14, INK if selected else MUTED)
        text(surface, value_text, (1352, top+5), 13, color if selected else MUTED, right=True)
        race_label = RACES[empire.race_id].name+(" · You" if owner == "player" else "")
        text(surface, shorten(race_label+(" · Hidden" if not selected else ""), 250, 11), (1100, top+25), 11, MUTED)
    text(surface, "Click a civilization to show / hide its line.", (1070, 758), 10, MUTED)
    text(surface, metric.description, (65, 799), 13, CYAN)
    first = min((rows[0][0] for rows in series.values() if rows), default=game.turn)
    hint = (f"Records begin at turn {first}; earlier values were not stored." if first > 1 else
            "Hover over the graph to inspect a turn. New civilizations have no history before they exist.")
    text(surface, hint, (65, 820), 11, MUTED)
    app.button("statistics_pause", "Menu", (64, 850, 126, 36), app.pause)
    app.button("statistics_save", "Save · F5", (204, 850, 172, 36), app.save_game)
    text(surface, f"{len(series)} civilizations · "+("All recorded turns" if not app.statistics_range else f"Last {app.statistics_range} turns"),
         (400, 861), 12, MUTED)
    app.button("statistics_end_turn", "End turn · E", (1081, 843, 295, 43), app.advance_turn, "primary")
