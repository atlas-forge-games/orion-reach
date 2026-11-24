# Age of the Stars — v0.98.4 equipment improvements

Research now has two tabs: **New technologies** for the existing discovery tree,
and **Improve existing** for repeatable improvements to unlocked weapons, ship
shields and armor. Choose either stronger equipment or cheaper manufacturing,
with independent levels for each equipment type and track.

Both use the same research output and one active project. Switching preserves
invested points, and completion preserves overflow. Improvements do not advance
discovery tiers or unlock excluded technologies.

The first performance level adds 10%; the first manufacturing level saves 6%
of that module's Resources and construction work. Each subsequent gain is 70%
of the previous gain, while its research cost rises by 60%. Existing fitted ships
receive performance upgrades automatically. Discounts apply to new construction
orders; existing orders retain their original price, work and refund terms.

See [the equipment improvement guide](docs/equipment-improvements.md) for the
formulas, examples, rounding rules, AI behavior and save compatibility.
The [six-field research tree](docs/six-field-research.md) and
[v0.98.3 mineral rules](docs/mineral-richness.md) remain available.

## Install

Extract this incremental ZIP into your **v0.98.3** repository beside `orion/`,
`assets/`, `tests/` and `docs/`, replacing the included files. Restart the game.
No new dependencies are needed. Apply the earlier v0.98.3 update first if needed.

Existing campaigns start with no equipment improvement levels. Their discoveries,
research progress, fitted equipment and saved balance settings are preserved.
Campaign save format is now **68**; newly written saves require v0.98.4 or later.
Older saves remain readable. Balance profile format remains **23**.

## Validation

All **13 focused improvement tests** pass. They cover diminishing benefits,
independent tracks, shared research accounting and switching, unlock gates,
actual combat damage and shields, armor damage preservation, existing and future
construction orders, AI spending, save validation and round-trips, normal turn
completion, designer values, and UI clicks at three window sizes.

A real v0.98.3 save was loaded without changing its existing campaign data or
balance profile, then saved and reloaded in v0.98.4 and again after completing
an improvement. The source save remained unchanged. Both research tabs and
the ship designer were rendered and visually inspected.

The selected broader run passed **119 tests and 228 subtests**. It also reported
13 failures, all reproduced on unmodified v0.98.3 before this update: three in
research switching/information, two in designer planning, seven in tactical
combat and one in the encyclopedia. No additional failure was introduced in
that selected run.

```bash
python -m pytest tests/test_equipment_improvements.py -q
```

## Commit commands

After extracting this update over your committed v0.98.3 checkout:

```bash
git status
git add README.md docs/equipment-improvements.md docs/six-field-research.md
git add orion/__init__.py orion/improvements.py orion/improvements_view.py
git add orion/research.py orion/research_view.py orion/model.py orion/storage.py
git add orion/designs.py orion/designer_controls.py orion/designer_info.py orion/designer_view.py
git add orion/app.py orion/ai.py orion/combat.py orion/encyclopedia.py
git add orion/galaxy_hud.py orion/observer.py orion/observer_view.py orion/rival_view.py
git add tests/test_equipment_improvements.py tests/test_research_overview.py tests/test_six_field_research.py
git diff --cached --stat
git commit -m "Add repeatable equipment research with diminishing improvements (v0.98.4)"
git push
```
