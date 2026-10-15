"""Versioned, atomic JSON saves. No pickle, executable content, or cloud service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sys
import tempfile

from .model import GameState, SaveError
from .empires import DEFAULT_PALETTE, PLAYER_PALETTES
from . import balance

SAVE_VERSION = 46
DEFAULT_SETTINGS = {"fullscreen": False, "animated_background": True, "sound": True,
                    "music": True, "music_volume": 30, "galaxy_palette": DEFAULT_PALETTE,
                    "galaxy_background": True}


def default_data_dir():
    override = os.environ.get("ORION_REACH_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "OrionReach"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/OrionReach"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "orion-reach"


def atomic_json(path, payload):
    """Replace only after a complete write; a failed write preserves the old file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".writing-", suffix=".tmp", delete=False) as f:
            tmp = Path(f.name)
            json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


class Storage:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else default_data_dir()
        self.saves_dir = self.root / "saves"

    def load_settings(self):
        result = DEFAULT_SETTINGS.copy()
        try:
            path = self.root / "settings.json"
            if path.stat().st_size > 16_384:
                return result
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result.update({k: v for k, v in data.items()
                               if k in ("fullscreen", "animated_background", "sound", "music", "galaxy_background") and type(v) is bool})
                if type(data.get("music")) is not bool:
                    result["music"] = result["sound"]  # Respect older muted preferences.
                volume = data.get("music_volume")
                if type(volume) is int and 0 <= volume <= 100:
                    result["music_volume"] = volume
                palette = data.get("galaxy_palette")
                if type(palette) is str and palette in PLAYER_PALETTES:
                    result["galaxy_palette"] = palette
        except (OSError, ValueError, RecursionError):
            pass
        return result

    def save_settings(self, settings):
        try:
            atomic_json(self.root / "settings.json", settings)
        except (OSError, ValueError) as exc:
            raise SaveError("Settings could not be saved. Check folder permissions.") from exc

    def save(self, state, autosave=False):
        payload = {"format": "orion-reach", "version": SAVE_VERSION,
                   "saved_at": datetime.now(timezone.utc).isoformat(),
                   "autosave": bool(autosave), "game": state.to_dict(),
                   "balance": balance.profile_for(state)}
        # One autosave; manual saves are separate snapshots and never overwrite each other.
        name = "autosave.json" if autosave else f"save-{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}-{state.campaign_id[:8]}.json"
        try:
            path = self.saves_dir / name
            atomic_json(path, payload)
            return path
        except (OSError, ValueError) as exc:
            raise SaveError("The game could not be saved. Check folder permissions or free space.") from exc

    def load(self, path, *, activate_balance=True):
        previous = balance.active_profile()
        success = False
        try:
            path = Path(path)
            if path.stat().st_size > 12_000_000:
                raise SaveError("This save is too large for this prototype.")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != "orion-reach":
                raise SaveError("This is not an Orion Reach save.")
            if type(data.get("version")) is not int or data["version"] not in range(1, SAVE_VERSION+1):
                raise SaveError("This save uses an unsupported version.")
            profile = data.get("balance") if data["version"] >= 36 else balance.legacy_profile()
            balance.activate(profile)
            # Migrate older formats in memory; never rewrite a loaded source file.
            state = GameState.from_dict(data.get("game"), version=data["version"])
            stamp = data.get("saved_at", "")
            if not isinstance(stamp, str) or len(stamp) > 64:
                raise SaveError("This save has an invalid timestamp.")
            datetime.fromisoformat(stamp)
            balance.tag_game(state, profile)
            success = True
            return state, data
        except SaveError:
            raise
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            raise SaveError("This save is damaged or cannot be read.") from exc
        finally:
            if not success or not activate_balance:
                balance.activate(previous)

    def list_saves(self):
        rows = []
        try:
            paths = list(self.saves_dir.glob("*.json"))
            paths.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
        except OSError:
            return [{"path": None, "error": "Save folder cannot be read."}]
        for path in paths:
            try:
                state, meta = self.load(path, activate_balance=False)
                rows.append({"path": path, "state": state, "meta": meta})
            except SaveError as exc:
                rows.append({"path": path, "error": str(exc)})
        return rows
