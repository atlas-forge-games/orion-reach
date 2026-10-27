"""Display-only galaxy preferences, independent of campaigns and save formats."""

STYLES = ("clean", "classic")
DEFAULT_STYLE = "clean"


def map_style(app):
    value = getattr(app, "settings", {}).get("galaxy_style", DEFAULT_STYLE)
    return value if value in STYLES else DEFAULT_STYLE


def clean_map(app):
    return map_style(app) == "clean"
