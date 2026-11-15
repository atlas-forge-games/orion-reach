# v0.97.1 — engraved main-menu plaques

The *Age of the Stars* opening menu now uses carved, art-backed button sprites
rather than generic rectangular UI controls. The game continues to draw the
existing animated background, logo, fleet and footer independently.

## Visible changes

- **New Game**, **Load Game**, **Settings**, **Quit** and the optional
  **Continue** each have matching ivory-gold and navy-blue engraved plaques.
- The initially selected button uses the gold variant. Hovering over another
  button or moving focus with the keyboard transfers the gold selection.
- Buttons remain real mouse/keyboard hit regions, with the same click actions,
  input shortcuts and ordering. Pressed buttons shift by one pixel.
- Art is split into transparent PNG sprites under `assets/title/`. The title
  screen is not a pre-rendered screenshot.
- The About button and other screens retain their existing styling.

## Install

Install this **incremental patch over v0.97.0**, replacing existing files.
Extract the ZIP in the repository root (the directory that contains `orion/`
 and `assets/`). Restart the game. No save migration is necessary.

For example, in PowerShell from the repository root:

```powershell
Expand-Archive -Path "C:\path\to\orion_reach_v0971_engraved_title_buttons.zip" -DestinationPath . -Force
python main.py
```

## Git commands

```bash
git status
git add orion/__init__.py orion/app.py orion/title_screen.py assets/title/plaque-*.png tests/test_title_plaques.py docs/title-screen-plaques.md README.md screenshots/title_engraved_buttons.png
git commit -m "Add engraved interactive title-menu plaques (v0.97.1)"
git push
```

## Verification

```bash
python -m pytest tests/test_title_plaques.py -q
```

The texture assets were generated for this game. `title_screen.py` also has a
procedural fallback if the new PNGs are missing, so a partial installation will
not prevent the menu from opening.
