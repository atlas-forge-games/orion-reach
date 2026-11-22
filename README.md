# Age of the Stars — v0.98.0 visual ship designer

Build your ship directly on a large top-down hull. Choose a hull on the left,
click a mounting point on the ship, then select equipment on the right.

- Outer mounts carry weapons or point defense; fitted equipment appears on the hull.
- Shared internal bays make shields, damage control, scanners and command systems
  compete for space. A frigate can now carry a command relay.
- Click the stern to replace its engine, or **Hull plating** to choose armor.
  Standard propulsion and plating are included in the bare hull.
- Carriers have two dedicated drone hangars.
- Hover over or select a module to preview changes to hull, shields, firepower,
  movement and cost. **Install module** applies the selection; **Remove** or
  **Reset** clears it. Right-click equipment for details.
- Unresearched equipment can be planned; building waits for the required research.
- Changing hull preserves compatible equipment. Excess equipment is listed for
  review and must be fitted or removed before saving the new design.
- Auto fit, saved blueprints, colony construction and the combat simulator all
  use the new designer. AI designs follow the same physical fitting limits.

## Installation

Extract this incremental ZIP into the existing repository beside `orion/`,
`assets/`, `tests/` and `docs/`, replacing the included files. Restart the game.
The base version is **v0.97.6**, commit `13d4947`.

Existing campaigns and blueprints load normally. Existing ships and queued
orders retain their equipment; updating a blueprint changes future orders.
New saves use format **66** to retain exact mounting positions. Older source
save files are not rewritten when loaded. No new dependencies are needed.

## Validation

The focused fitting, UI, planning, simulator, scaling, fleet-support and arsenal
checks passed **103 tests and 134 subtests**. These include physical limits,
module replacement, mouse clicks across all six hulls at three window sizes,
exact mount persistence, production snapshots, AI fittings and combat scenarios.

A save created with actual v0.97.6 code, including old blueprints, a queued ship
and an active battle, loaded successfully. Combat resumed, and a new save
round-tripped without changing the old equipment or source file. Actual screens
were reviewed at 980×900, 1280×800 and 1920×1080; fitting also worked with 175%
UI size using the existing scrolling interface.

The wider historical suite has eight pre-existing failures, reproduced on
unchanged v0.97.6: five expect earlier ship statistics/costs, two expect older
research names or equipment scaling, and one concerns colony-layout save
migration. No additional failures remain in the affected checks.

Run the focused checks:

```bash
python -m pytest tests/test_visual_designer.py tests/test_designer.py::DesignerUITests tests/test_designer_planning.py::BlueprintPlanningUITests tests/test_combat_simulator.py tests/test_ship_scaling.py tests/test_fleet_support.py tests/test_arsenal.py -q
```

## Preview

![Visual ship designer](screenshots/visual_ship_designer.png)

See [the fitting rules](docs/ship-designer.md) for slot counts and save details.

## Commit commands

```bash
git status
git add README.md docs/ship-designer.md assets/designer screenshots/visual_ship_designer.png
git add orion/__init__.py orion/app.py orion/auto_designs.py orion/balance.py orion/combat.py orion/combat_sandbox.py orion/combat_simulator.py orion/designer_art.py orion/designer_controls.py orion/designer_info.py orion/designer_view.py orion/designs.py orion/model.py orion/ship_fitting.py orion/ship_scaling.py orion/storage.py orion/window_layout.py
git add tests/test_arsenal.py tests/test_combat_simulator.py tests/test_designer.py tests/test_designer_planning.py tests/test_fleet_support.py tests/test_visual_designer.py
git diff --cached --stat
git commit -m "Add visual hull-first ship designer with physical mounting points (v0.98.0)"
git push
```
