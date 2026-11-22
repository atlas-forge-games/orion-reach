"""Shared campaign and simulator interactions for the visual ship designer."""

from .designs import HULLS, ShipDesign, loadout_error
from .ship_fitting import arrange, mounts_for, options, ordered

DESIGNS_PER_PAGE = 3
OPTIONS_PER_PAGE = 3
_SELECTED = object()


def new(app):
    app.design_id, app.design_name, app.design_kind = None, "", "frigate"
    app.design_modules, app.design_unplaced, app.design_mounts = [], [], {}
    app.design_original = None
    app.design_edited = True
    app.design_layout_kind = app.design_kind
    app.design_module_filter, app.design_module_page = "all", 0
    select(app, "core_1")


def load(app, design):
    app.design_id, app.design_name, app.design_kind = design.id, design.name, design.kind
    app.design_modules = list(design.modules)
    fitted, app.design_unplaced = arrange(design.kind, design.modules, design.mounts)
    app.design_mounts = dict(fitted)
    app.design_layout_kind = design.kind
    app.design_original, app.design_edited = design, False
    select(app, "core_1")


def sync(app):
    """Keep direct draft edits, including simulator callers, on the same path."""
    if not hasattr(app, "design_mounts"):
        new(app)
    existing = [m for _, m in ordered(app.design_layout_kind, app.design_mounts)] + app.design_unplaced
    from collections import Counter
    if app.design_layout_kind != app.design_kind or Counter(existing) != Counter(app.design_modules):
        set_modules(app, app.design_modules, tuple(app.design_mounts.items()))


def set_modules(app, modules, preferred=()):
    fitted, app.design_unplaced = arrange(app.design_kind, modules, preferred)
    app.design_mounts = dict(fitted)
    app.design_layout_kind = app.design_kind
    app.design_edited = True
    refresh_modules(app)
    if getattr(app, "design_mount", None) not in {m.id for m in mounts_for(app.design_kind)}:
        select(app, "core_1")


def refresh_modules(app):
    app.design_modules = [m for _, m in ordered(app.design_kind, app.design_mounts)] + app.design_unplaced


def draft(app):
    sync(app)
    original = getattr(app, "design_original", None)
    if (original is not None and not app.design_edited and app.design_name.strip() == original.name
            and app.design_kind == original.kind and tuple(app.design_modules) == original.modules):
        return original
    fitted = ordered(app.design_kind, app.design_mounts)
    return ShipDesign(app.design_id or "design_1", app.design_name.strip(), app.design_kind,
                      tuple(m for _, m in fitted) + tuple(app.design_unplaced), 3, fitted)


def choose_hull(app, kind):
    if kind not in HULLS or kind == app.design_kind:
        return
    sync(app)
    app.design_kind = kind
    set_modules(app, app.design_modules, tuple(app.design_mounts.items()))
    select(app, "unplaced" if app.design_unplaced else "core_1")


def choices(app):
    if app.design_mount == "unplaced":
        return ()
    result = options(app.design_kind, app.design_mount)
    if app.design_mount in ("engine", "armor"):
        result = (None, *result)
    return result


def select(app, slot_id):
    app.design_mount = slot_id
    app.design_module_page = 0
    available = choices(app)
    fitted = app.design_mounts.get(slot_id)
    app.design_candidate = fitted if fitted in available else next(iter(available), None)
    if app.design_candidate in available:
        app.design_module_page = available.index(app.design_candidate)//OPTIONS_PER_PAGE


def choose_module(app, identifier):
    if identifier in choices(app):
        app.design_candidate = identifier


def candidate(app, *, module=_SELECTED):
    """A hover/selection preview never changes the draft or its read-only snapshot."""
    current = draft(app)
    if app.design_mount == "unplaced":
        return current, None
    identifier = app.design_candidate if module is _SELECTED else module
    mounts = dict(app.design_mounts)
    if identifier is None:
        mounts.pop(app.design_mount, None)
    else:
        mounts[app.design_mount] = identifier
    fitted = ordered(app.design_kind, mounts)
    modules = tuple(m for _, m in fitted)
    error = loadout_error(app.design_kind, modules, require_weapon=False, fit_version=3)
    return ShipDesign(current.id, current.name, current.kind, modules, 3, fitted), error


def install(app):
    if app.design_mount == "unplaced" or app.design_candidate not in choices(app):
        return
    if app.design_mounts.get(app.design_mount) == app.design_candidate:
        return
    _, error = candidate(app)
    if error:
        app.toast(error, True)
        return
    if app.design_candidate is None:
        app.design_mounts.pop(app.design_mount, None)
    else:
        app.design_mounts[app.design_mount] = app.design_candidate
        if app.design_candidate in app.design_unplaced:
            app.design_unplaced.remove(app.design_candidate)
    app.design_edited = True
    refresh_modules(app)


def remove(app):
    if app.design_mount in app.design_mounts:
        app.design_mounts.pop(app.design_mount)
        app.design_edited = True
        refresh_modules(app)
        select(app, app.design_mount)


def discard_unplaced(app, index=None):
    if index is None:
        app.design_unplaced.clear()
    elif 0 <= index < len(app.design_unplaced):
        app.design_unplaced.pop(index)
    app.design_edited = True
    refresh_modules(app)
    if not app.design_unplaced:
        select(app, "core_1")


def change_module(app, identifier, amount):
    """Programmatic quick-fit uses the same positions and constraints as clicks."""
    sync(app)
    if amount < 0:
        slot = next((key for key, value in app.design_mounts.items() if value == identifier), None)
        if slot:
            app.design_mounts.pop(slot)
        elif identifier in app.design_unplaced:
            app.design_unplaced.remove(identifier)
        app.design_edited = True
        refresh_modules(app)
    else:
        from .ship_fitting import category, hull_allows
        slot = next((s for s in mounts_for(app.design_kind) if s.id not in app.design_mounts
                     and s.category == category(identifier) and hull_allows(app.design_kind, identifier)), None)
        if slot:
            select(app, slot.id)
            choose_module(app, identifier)
            install(app)


def change_page(app, delta):
    count = len(app.design_unplaced) if app.design_mount == "unplaced" else len(choices(app))
    last = max(0, (count-1)//OPTIONS_PER_PAGE)
    app.design_module_page = max(0, min(last, app.design_module_page+delta))


def error(app):
    design = draft(app)
    if app.design_unplaced and (app.design_edited or design.fit_version == 3):
        return "Fit or remove the unplaced equipment before saving."
    return loadout_error(design.kind, design.modules, fit_version=design.fit_version)
