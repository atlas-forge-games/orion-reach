# Age of the Stars title screen — v0.80

The approved design is implemented as three separate image layers with native
pygame menu controls. The logo and menu occupy the left side; a detailed planet
and gently drifting exploration fleet occupy the right. The existing studio
intro remains available. The footer retains the studio credit and About link.

## Controls and rendering

New Game, Load Game, Settings and Quit retain their existing actions and keys.
With a campaign in memory, Continue becomes the primary button and the five
rows fit above the footer. Mouse, Tab, arrow keys and Enter use the existing
event dispatcher, including fullscreen and letterboxed windows. Hover, keyboard
focus and pressed states are drawn independently from the image layers.

The renderer caches decoded and scaled artwork. All scaling preserves aspect
ratio; background overflow is clipped at the right edge. The logo remains still
while ships and a few stars move gently. Disabling Animated background makes
the whole scene stationary. Missing/corrupt background art falls back to the
existing procedural backdrop; a missing logo uses a text title; a missing fleet
layer is omitted without blocking the menu.

## Display name and compatibility

`orion.GAME_TITLE` is the visible game name. The application, About screen,
encyclopedia, observer reports, combat simulator and balance editor display
Age of the Stars. The compact galaxy header uses the same name on two lines.

The repository, Python package and existing files have not been renamed.
`python main.py`, `python combat_simulator.py` and `python editor.py` still work.
The `orion-reach` save identifier, `orion-reach-balance` profile identifier,
`ORION_REACH_DATA_DIR`, platform save directories, settings keys, save format 56
and balance format 20 are unchanged. No save migration or new campaign is needed.

## Validation

49 existing interface tests passed:

- `test_prototype.InterfaceTests`: 13 tests, including complete new/save/load flow,
  keyboard navigation, letterboxing, quit cancellation and save-failure handling.
- `test_galaxy_hud`: 7 tests, including return to menu and resume with pending orders.
- `test_encyclopedia`: 5 tests.
- `test_combat_simulator.SimulatorUITests`: 12 tests.
- `test_balance_editor.EditorInterfaceTests`: 3 tests.
- `test_optional_autosave`: 9 tests.

Additional checks confirmed that animation-off frames remain identical as time
advances, enabled animation changes the artwork without changing campaign state,
Continue-menu hit regions do not overlap, missing artwork remains usable, and
the original generated alpha channels are present. The actual menu and Continue
layout were visually inspected at the native canvas size and in a 1000x900
letterboxed window. Source compilation and archive integrity were also checked.
The full gameplay suite was not rerun for this visual update.

Reproduce the main-menu screenshot without changing a campaign:

```bash
python main.py --headless --skip-intro --screen menu --screenshot screenshots/menu.png
```

Exact artwork prompts and checksums are in `assets/title/`.
