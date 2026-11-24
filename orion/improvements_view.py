"""Equipment selection and repeatable research alongside the discovery tree."""

from . import improvements
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, panel, paragraph, shorten, text

PER_PAGE = 7


def draw_research_tabs(app):
    for mode, label, x in (('new', 'New technologies', 824), ('improvements', 'Improve existing', 1104)):
        app.button('research_mode_'+mode, label, (x, 124, 272, 46),
                   lambda m=mode: app.select_research_mode(m),
                   'primary' if app.research_mode == mode else 'ghost')


def draw_improvements(app):
    from .research_view import draw_project_summary, project_eta, research_rate
    game, surface, state = app.game, app.canvas, app.game.technology
    app.chrome('RESEARCH DIRECTORATE')
    app.button('research_back', '← Back · R', (64, 124, 195, 46), app.close_research, 'ghost')
    text(surface, 'Equipment improvements', (290, 133), 28, INK, 'title')
    rate = research_rate(game)
    draw_project_summary(app, rate)
    targets = improvements.available_targets(state)
    if app.improvement_module not in targets:
        app.improvement_module = next(iter(targets), None)
    last = max(0, (len(targets)-1)//PER_PAGE)
    app.improvement_page = max(0, min(last, app.improvement_page))
    panel(surface, (64, 304, 350, 502))
    text(surface, 'UNLOCKED EQUIPMENT', (82, 321), 12, MUTED, 'mono', 1)
    for index, identifier in enumerate(targets[app.improvement_page*PER_PAGE:][:PER_PAGE]):
        y = 354+index*54
        spec = improvements.targets()[identifier]
        selected = identifier == app.improvement_module
        app.button('improvement_target_'+identifier, '', (74, y, 330, 50),
                   lambda m=identifier: app.select_improvement(m), 'hotspot')
        panel(surface, (75, y, 328, 49), (25, 43, 53) if selected else (11, 24, 32), GOLD if selected else LINE)
        text(surface, shorten(spec.name, 302, 17), (88, y+5), 17, GOLD if selected else INK)
        power = state.improvements.get(improvements.key_for(identifier, 'power'), 0)
        manufacturing = state.improvements.get(improvements.key_for(identifier, 'manufacturing'), 0)
        text(surface, f'Power {power} · Manufacturing {manufacturing}', (88, y+29), 11, MUTED)
    app.button('improvement_previous', '←', (80, 754, 54, 34),
               lambda: app.change_improvement_page(-1), enabled=app.improvement_page > 0)
    text(surface, f'{app.improvement_page+1} / {last+1}', (218, 765), 12, MUTED)
    app.button('improvement_next', '→', (344, 754, 54, 34),
               lambda: app.change_improvement_page(1), enabled=app.improvement_page < last)
    panel(surface, (430, 304, 946, 502))
    if not targets:
        paragraph(surface, 'Discover a weapon, shield or armor technology to begin improving it.',
                  (458, 344), 856, 22, INK, 32)
        return
    identifier = app.improvement_module
    spec = improvements.targets()[identifier]
    text(surface, spec.name, (452, 322), 27, INK, 'title')
    text(surface, 'Two independent tracks · Each uses your empire’s shared research points', (454, 363), 14, MUTED)
    for index, track in enumerate(improvements.TRACKS):
        key = improvements.key_for(identifier, track)
        item = improvements.project(state, key)
        level = item.level-1
        x = 450+index*454
        active = key == state.active_improvement
        panel(surface, (x, 397, 434, 294), (15, 31, 41), GOLD if active else LINE)
        text(surface, improvements.track_name(identifier, track), (x+18, 416), 22, GOLD if active else INK)
        text(surface, f'Level {level} → {item.level}', (x+19, 457), 17, CYAN)
        before = 100*improvements.benefit(level, track)
        after = 100*improvements.benefit(item.level, track)
        sign = '+' if track == 'power' else '−'
        text(surface, f'Total bonus: {sign}{before:.1f}% → {sign}{after:.1f}%', (x+19, 491), 17, INK)
        current = improvements.module_spec(spec, identifier, state.improvements)
        proposed = improvements.module_spec(spec, identifier, {**state.improvements, key: item.level})
        if track == 'power':
            field, label = ('damage', 'damage') if spec.damage else ('shields', 'shields') if spec.shields else ('hull_bonus', 'added hull')
            example = f'Base module: {getattr(current, field)} → {getattr(proposed, field)} {label}'
        else:
            example = f'Base module: {current.resource_cost} → {proposed.resource_cost} RES · {current.work_cost} → {proposed.work_cost} work'
        text(surface, shorten(example, 396, 14), (x+19, 527), 14, MUTED)
        text(surface, shorten(f'{item.cost:,} RP · {project_eta(game, item, rate)}', 396, 16), (x+19, 568), 16, CYAN)
        error = game.improvement_error(key)
        label = 'Researching' if active else 'Switch project' if state.project else 'Research improvement'
        app.button('improvement_choose_'+track, label, (x+18, 620, 398, 48),
                   lambda k=key: app.improvement_request(k), 'primary', enabled=error is None)
    text(surface, 'Each level gives 70% of the previous gain and costs 60% more RP.', (454, 711), 14, MUTED)
    text(surface, 'Performance upgrades apply to existing ships. Discounts apply to new orders.', (454, 740), 14, MUTED)
    text(surface, 'Base module figures round to whole points; larger hulls scale their equipment.', (454, 769), 12, FAINT)
    app.button('research_save', 'Save · F5', (64, 835, 172, 44), app.save_game)
    app.button('research_pause', 'Menu', (250, 835, 132, 44), app.pause)
    text(surface, 'Switching transfers invested research points.', (409, 834), 12, MUTED)
    text(surface, 'Improvements do not advance research tiers.', (409, 855), 11, FAINT)
