"""A paginated encyclopedia index and a scrollable, read-only article pane."""

from functools import lru_cache
import pygame as pg

from .command_buttons import command_icon
from .encyclopedia import CATEGORIES, Article, articles, category_articles
from . import black_holes
from .ui import ASSETS, CYAN, GOLD, INK, LINE, MUTED, font, panel, shorten, text, wrapped_lines

ARTICLES_PER_PAGE = 8
CATEGORY_RECT = pg.Rect(64, 226, 216, 574)
INDEX_RECT = pg.Rect(296, 226, 324, 574)
ARTICLE_RECT = pg.Rect(636, 226, 740, 574)


def selected_article(app):
    entries = category_articles(app.info_category)
    return next((article for article in entries if article.id == app.info_article), entries[0])


@lru_cache(maxsize=256)
def article_lines(article: Article, width):
    """Keep complete text; wrapping and scrolling never truncate an article."""
    result, y = [], 0
    for heading, body in article.sections:
        result.append((heading, y, 11, GOLD, "mono_bold"))
        y += 26
        for paragraph in body.split("\n"):
            for line in wrapped_lines(paragraph, width, 16):
                result.append((line, y, 16, INK, "sans"))
                y += 24
            if not paragraph:
                y += 12
        y += 25
    return tuple(result), max(0, y-25)


def article_body_rect(article):
    titles = wrapped_lines(article.title, ARTICLE_RECT.w-48, 27)
    top = ARTICLE_RECT.y+54+len(titles)*34+26+(64 if article.planned else 0)
    inset = 304 if article.image else 0
    return pg.Rect(ARTICLE_RECT.x+24+inset, top, ARTICLE_RECT.w-60-inset, 738-top)


def illustration_rect(article):
    area = article_body_rect(article)
    side = min(280, area.h-48)
    return pg.Rect(ARTICLE_RECT.x+24, area.y, side, side)


@lru_cache(maxsize=32)
def article_illustration(path, size):
    """Load reference artwork lazily; a missing image never blocks its text."""
    try:
        source = pg.image.load(str(ASSETS/path))
        scale = min(size[0]/source.get_width(), size[1]/source.get_height())
        return pg.transform.smoothscale(source, (max(1, round(source.get_width()*scale)),
                                                max(1, round(source.get_height()*scale))))
    except (OSError, pg.error):
        return None


def draw_article_illustration(app, article):
    rect = illustration_rect(article)
    panel(app.canvas, rect, (5, 12, 19))
    image = article_illustration(article.image, rect.size)
    if image is not None:
        app.canvas.blit(image, image.get_rect(center=rect.center))
        pg.draw.rect(app.canvas, LINE, rect, 1)
    else:
        icon = command_icon("info", 44, MUTED)
        app.canvas.blit(icon, icon.get_rect(center=(rect.centerx, rect.centery-17)))
        text(app.canvas, "Artwork unavailable", (rect.x+54, rect.centery+20), 13, MUTED)
    text(app.canvas, article.image_caption, (rect.x, rect.bottom+14), 13, GOLD)
    if article.planned:
        text(app.canvas, "No current gameplay effects", (rect.x, rect.bottom+34), 12, MUTED)


def scroll_article(app, delta):
    article = selected_article(app)
    area = article_body_rect(article)
    _, height = article_lines(article, area.w)
    app.info_scroll = max(0, min(max(0, height-area.h), app.info_scroll+delta))


def draw_info(app):
    surface = app.canvas
    app.chrome("ENCYCLOPEDIA")
    app.button("info_back", "← Back · F1", (64, 124, 192, 46), app.close_info, "ghost")
    text(surface, "Galactic encyclopedia", (282, 127), 32, INK, "title")
    text(surface, f"{len(articles())} ENTRIES", (1376, 143), 11, CYAN, "mono", right=True)
    text(surface, "The guide to your expedition: rules, civilizations and the tools to build an empire.", (66, 191), 15, MUTED)

    for rect in (CATEGORY_RECT, INDEX_RECT, ARTICLE_RECT):
        panel(surface, rect, (9, 20, 29))
    text(surface, "CONTENTS", (82, 247), 11, GOLD, "mono", 1)
    for index, (category, name) in enumerate(CATEGORIES.items()):
        rect = pg.Rect(76, 273+index*46, 192, 39)
        selected = category == app.info_category
        app.button("info_category_"+category, name, rect,
                   lambda value=category: app.select_info_category(value), "tab_active" if selected else "tab")
        if selected:
            pg.draw.rect(surface, CYAN, (rect.left-6, rect.top+5, 3, rect.h-10))

    entries = category_articles(app.info_category)
    last = (len(entries)-1)//ARTICLES_PER_PAGE
    page = min(app.info_page, last)
    start = page*ARTICLES_PER_PAGE
    collected = {"artifact_"+site.relic_id for site in black_holes.collection(app.game)}
    text(surface, CATEGORIES[app.info_category].upper(), (314, 247), 10, GOLD, "mono")
    text(surface, str(len(entries)), (602, 247), 10, MUTED, "mono", right=True)
    for index, article in enumerate(entries[start:start+ARTICLES_PER_PAGE]):
        rect = pg.Rect(308, 273+index*56, 300, 49)
        button = app.button("info_article_"+article.id, "", rect,
                            lambda value=article.id: app.select_info_article(value), "hotspot")
        selected = article.id == app.info_article
        active = app.is_active(button)
        panel(surface, rect, (20, 38, 49) if selected or active else (10, 23, 32), GOLD if active else CYAN if selected else LINE)
        if article.id in collected:
            pg.draw.rect(surface, GOLD, (rect.x+2, rect.y+5, 3, rect.h-10))
        title = wrapped_lines(article.title, rect.w-24, 14)
        if len(title) > 1:
            for row, line in enumerate(title):
                text(surface, line, (rect.x+12, rect.y+6+row*18), 14, INK)
        else:
            text(surface, article.title, (rect.x+12, rect.y+6), 14, INK)
            subtitle = "Recovered · In your collection" if article.id in collected else article.subtitle
            text(surface, shorten(subtitle, rect.w-24, 10), (rect.x+12, rect.y+29), 10, GOLD if article.id in collected else MUTED)
    app.button("info_previous", "← Prev", (308, 751, 91, 35), lambda: app.change_info_page(-1), enabled=page>0)
    text(surface, f"{page+1} / {last+1}", (458, 762), 12, MUTED, "mono", right=True)
    app.button("info_next", "Next →", (515, 751, 93, 35), lambda: app.change_info_page(1), enabled=page<last)

    article = selected_article(app)
    text(surface, CATEGORIES[article.category].upper(), (660, 247), 11, GOLD, "mono", 1)
    for index, line in enumerate(wrapped_lines(article.title, ARTICLE_RECT.w-48, 27)):
        text(surface, line, (660, 280+index*34), 27, INK)
    area = article_body_rect(article)
    if article.planned:
        notice = pg.Rect(660, area.top-64, 692, 50)
        panel(surface, notice, (29, 29, 24), (112, 96, 61))
        owned = article.id in collected
        text(surface, ("RECOVERED RELIC" if owned else "LEGENDARY RELIC")+" · PROPOSED EFFECTS", (674, notice.y+7), 10, GOLD, "mono_bold")
        text(surface, ("In your collection." if owned else "Recover relics at black holes.")+" Placement and bonuses remain planned.",
             (674, notice.y+26), 13, INK)
    else:
        pg.draw.line(surface, LINE, (660, area.top-15), (1352, area.top-15))
    if article.image:
        draw_article_illustration(app, article)
    lines, height = article_lines(article, area.w)
    scroll_article(app, 0)
    clip = surface.get_clip()
    surface.set_clip(area)
    for value, y, size, color, family in lines:
        top = area.y+y-app.info_scroll
        if top+font(size, family).get_height() > area.top and top < area.bottom:
            text(surface, value, (area.x, top), size, color, family)
    surface.set_clip(clip)
    maximum = max(0, height-area.h)
    if maximum:
        track = pg.Rect(1360, area.y, 3, area.h)
        pg.draw.rect(surface, LINE, track)
        thumb = max(26, round(area.h*area.h/height))
        pg.draw.rect(surface, CYAN, (track.x, track.y+round((area.h-thumb)*app.info_scroll/maximum), 3, thumb))
    surface.blit(command_icon("info", 22, CYAN), (660, 758))
    text(surface, "Scroll to read more" if maximum else "Complete article", (696, 762), 12, MUTED)
    app.button("info_scroll_up", "↑", (1232, 751, 52, 35), lambda: scroll_article(app, -area.h+24), enabled=app.info_scroll>0)
    app.button("info_scroll_down", "↓", (1300, 751, 52, 35), lambda: scroll_article(app, area.h-24), enabled=app.info_scroll<maximum)
    text(surface, "Browse the index: ← / →     Read: mouse wheel or Page Up / Page Down     Return: Esc / F1", (66, 832), 13, MUTED)
