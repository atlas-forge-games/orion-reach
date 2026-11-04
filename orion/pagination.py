"""Page growing civilization lists without reducing their text or row sizes."""

import pygame as pg

from .ui import MUTED, text, text_image


def page_rows(app, rows, page_size, key, rect, *, state=None):
    state = app.list_pages if state is None else state
    pages = max(1, (len(rows)+page_size-1)//page_size)
    page = max(0, min(pages-1, state.get(key, 0)))
    state[key] = page
    start = page*page_size
    if pages > 1:
        bar = pg.Rect(rect)
        app.button(key+"_previous", "←", (bar.x, bar.y, 48, bar.h),
                   lambda: state.update({key: page-1}), enabled=page > 0)
        app.button(key+"_next", "→", (bar.right-48, bar.y, 48, bar.h),
                   lambda: state.update({key: page+1}), enabled=page < pages-1)
        end = min(start+page_size, len(rows))
        span = str(end) if start+1 == end else f"{start+1}–{end}"
        label = f"{span} / {len(rows)}"
        size = text_image(label, 14, MUTED).get_size()
        text(app.canvas, label, (bar.centerx-size[0]/2, bar.centery-size[1]/2), 14, MUTED)
    return rows[start:start+page_size]
