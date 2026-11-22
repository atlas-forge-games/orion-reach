# Modular versions of the original ships — v0.98.1

These images retain the established ivory armor, bronze fittings, dark machinery
and cyan lights of `assets/ships/`. They were made with built-in image generation
using the original sprites and the approved modular previews as references.
Original generated PNG bytes are preserved; `manifest.json` records dimensions,
SHA-256 hashes and the generation briefs.

- `frigate-v1.png`, `destroyer-v1.png`, `cruiser-v1.png`: individual bare hulls.
- `capital-hulls-v1.png`: battleship, carrier and titan, left to right. Runtime
  cropping excludes the captions without altering the source PNG.
- `components-v1.png`: a regular four-column, three-row atlas. Row 1: laser,
  torpedo, point defense, sensor. Row 2: shield, repair, command, drone.
  Row 3: engine pod, armor, reinforced armor, internal bay cover.

`orion/modular_art.py` defines measured source-pixel attachment rectangles.
It extracts transparent bounds, composes each loadout, and scales to the requested
view. The designer uses open core bays and adds separate editing outlines.
Flight and combat use closed bay covers. Extra access trays and unused mounts
are covered when the configured hull has fewer active positions.

The same renderer handles stock presets, custom v3 mounting positions and visual
assignment of older v1/v2 equipment. It never modifies a blueprint, a ship's
stats, a build order, or a save. Civilian and special ships retain their own
existing artwork. The older `assets/designer/` atlases are retained for history
and are no longer selected by the designer.

Generate real UI and sprite previews with:

```bash
python tools/preview_modular_ships.py --output screenshots/modular-preview
```
