"""Saved, fog-aware reports of awakenings, raids and hostile sensor contacts."""

from . import news
from .ui import CYAN, GOLD, INK, MUTED, panel, paragraph, shorten, text

NEWS_PER_PAGE = 3


def draw_news(app):
    game, surface = app.game, app.canvas
    app.chrome("TURN NEWS")
    app.button("news_back", "←  Campaign result · N" if game.result else "←  Galaxy map · N",
               (64, 124, 280, 46), lambda: app.go("galaxy"), "ghost")
    if game.tribute_demands and not game.is_observer:
        app.button('news_tribute', 'Answer tribute demand', (370, 124, 302, 46),
                   lambda: app.show_diplomatic_affairs('tribute', game.tribute_demands[0].sender),
                   enabled=game.strategy_error('player') is None)
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "A chronicle of the galaxy" if game.is_observer else "Dispatches from the frontier", (64, 189), 40, INK, "title")
    text(surface, "Empire activity, council elections, battles and awakenings" if game.is_observer else "Council elections, frontier reports and hostile sensor contacts · newest first", (66, 250), 15, MUTED)
    rows = news.entries(game)
    last = max(0, (len(rows)-1)//NEWS_PER_PAGE)
    app.news_page = min(max(0, app.news_page), last)
    for index, tomb in enumerate(rows[app.news_page*NEWS_PER_PAGE:(app.news_page+1)*NEWS_PER_PAGE]):
        system = game.systems[tomb.system_id] if tomb.system_id is not None else None
        planet = game.planet_at(tomb.system_id, tomb.planet_id) if tomb.planet_id is not None else None
        y = 294+index*163
        panel(surface, (64, y, 1312, 148))
        text(surface, f"TURN {tomb.turn:03}  /  {tomb.category}", (86, y+17), 11, GOLD, "mono", 1)
        text(surface, shorten(planet.name if planet else system.name if system else tomb.headline, 1050, 27), (86, y+41), 27, CYAN)
        if system is None:
            paragraph(surface, tomb.detail, (87, y+87), 1240, 15, INK, 22)
            continue
        text(surface, shorten(tomb.headline, 1240, 15), (87, y+80), 15, INK)
        paragraph(surface, tomb.detail, (87, y+106), 1240, 13, MUTED, 19)
        key = f"news_system_{tomb.system_id}_{tomb.planet_id}"+(f"_raid_{tomb.order}" if tomb.order else "")
        app.button(key, "View system" if planet else "View sensors", (1188, y+41, 164, 37),
                   (lambda sid=system.id: app.open_system(sid)) if planet else
                   (lambda sid=system.id: app.open_sensor_map(sid)), enabled=game.result is None)
    if not rows:
        panel(surface, (64, 294, 1312, 393))
        text(surface, "No news reports", (101, 354), 32, INK, "title")
        paragraph(surface, "Council elections, known tomb-world awakenings, visible raids and newly detected hostile fleets appear here. These reports remain with your campaign.",
                  (103, 423), 1010, 19, MUTED, 31)
        text(surface, "Dormant vaults are hidden. Keep exploring the galaxy.", (103, 554), 16, GOLD)
    text(surface, f"PAGE {app.news_page+1} / {last+1} · {len(rows)} REPORTS", (65, 798), 11, MUTED, "mono")
    app.button("news_previous", "← Prev", (1081, 783, 139, 36), lambda: app.change_news_page(-1), enabled=app.news_page>0)
    app.button("news_next", "Next →", (1233, 783, 143, 36), lambda: app.change_news_page(1), enabled=app.news_page<last)
    app.button("news_save", "Save game · F5", (64, 834, 242, 45), app.save_game)
    text(surface, "Reports describe events at the time; revisit a world for current intelligence.", (331, 848), 12, MUTED)
    app.button("news_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn, "primary", enabled=game.result is None)
