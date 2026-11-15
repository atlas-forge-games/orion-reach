# v0.97.2 — vertical alignment of engraved title text

v0.97.1 baked the menu captions into the gold/blue PNG sprites. Their main
capital-letter band occupied source-image rows 38–105 (midpoint 71.5),
although the 164-pixel-high button skin is centered at row 81.5.

This patch moves only the pre-existing lettering and its engraved shading
down **10 source-image pixels**, or approximately **4 pixels** when the game
renders a 66-pixel-high button. The original blank skin remains unchanged;
all engraved relief, metallic borders, arrow emblems and decoration remain.

Every interactive menu label (New Game, Load Game, Settings, Quit and Continue)
has both color variants updated. Quit has a slightly lower glyph extremity
because of the Q descender; it shares the same capital-letter baseline.

## Install

Extract the ZIP into your **v0.97.1** repository, overwriting the files in
`assets/title/` and the small documentation/version files. Restart the game.
No save migration or controls changes are required.

## Verification

```bash
python -m pytest tests/test_title_plaque_alignment.py -q
```

## Commit

```bash
git status
git add orion/__init__.py README.md docs/title-text-centering.md tests/test_title_plaque_alignment.py assets/title/plaque-*.png screenshots/title_engraved_buttons.png
git commit -m "Center engraved title-menu lettering (v0.97.2)"
git push
```
