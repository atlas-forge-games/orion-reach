# Age of the Stars — rollback from v0.97.3 to v0.97.2

This patch **undoes only v0.97.3** (the unwanted galaxy-map engraved buttons and controls removal). It restores the v0.97.2 state, including the engraved gold/blue **title-screen** buttons and the corrected label centering.

What is restored:
- The original galaxy-map command bar and all its previous button styles.
- Galaxy zoom controls (minus / plus / Fit / Center).
- The Sensors overlay toggle and its `S` shortcut.
- The Hide panel toggle.
- The v0.97.2 engraved title-screen buttons, including the selected gold state and centered labels.
- The v0.97.1 title button drawing integration into `app.py`.

**Gameplay from v0.97.0 (diplomacy, ceasefires, promises) remains intact.**

## Installation

1. Extract this ZIP into your **existing Age of the Stars game repository**, allowing the files in `orion/` and `assets/title/` to replace the installed files.
2. Restart the game.

Nothing needs to be deleted from your game saves, and you do **not** need to revert your Git history or reset the whole project.

## Git commands

```bash
git status
git add orion/app.py orion/console_theme.py orion/title_screen.py orion/__init__.py assets/title/
git commit -m "Revert galaxy map UI changes and restore v0.97.2 title menu"
git push
```

If `git status` reports no changes for some files, that is normal: the archive includes some assets simply to ensure the correct v0.97.2 appearance.
