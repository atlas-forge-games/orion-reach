# Orion Reach — colony buildings v1

Six original building graphics used by the planet colony scene.
Generated using the built-in image-generation tool, with a shared architectural
palette, lighting direction and elevated three-quarter view.

Extract this pack into the repository root. Files belong under
`assets/buildings/`.

| Asset | File | Intended role |
| --- | --- | --- |
| Headquarters palace | `headquarters-v1.png` | A distinctive landmark marking planetary headquarters |
| Factory | `factory-v1.png` | Industrial production; matches the existing `factory` building ID |
| Shipyard | `shipyard-v1.png` | A surface ship-construction facility |
| Research lab | `research_lab-v1.png` | Research production; matches `research_lab` |
| Trade centre | `trade_center-v1.png` | Commercial exchange; matches `trade_center` |
| Mining complex | `mine-v1.png` | Mineral extraction; matches `mine` |

## Art and integration notes

These are separate original RGBA PNGs with transparent backgrounds, preserved
byte-for-byte from generation. They contain no UI labels, so the game can draw
names, selection outlines and building state separately.

The palace has a tall command beacon; the factory has production halls and
exhaust stacks; the shipyard contains a colony ship under construction; the lab
has a glass dome and instruments; the trade centre has a tall commercial atrium;
the mine has an extraction headframe and ore-processing equipment.

The assets form the first shared colony style in prototype 0.8. The planet
Overview tab displays completed buildings and faded previews for queued types;
repeat buildings share a graphic and count. The Colony catalogue, occupied
slots and Shipyard use the same sprites. Click surface buildings to open their
controls. Headquarters and shipyard artwork marks existing capabilities, without
introducing new constructible buildings or changing production rules.

Rendering notes:

- `orion/building_art.py` loads the RGBA images and caches proportionally scaled sprites.
- Preserve the PNG alpha channel; do not remove a guessed background color.
- Scale proportionally. Original image dimensions differ; never stretch them
  all into the same rectangle.
- Buildings align by the bottom of their visible foundations. The renderer
  calculates bounds from alpha; the manifest also records bounds for reference.
- `orion/colony_scene.py` draws a seeded landscape for the planet's biome and
  paints foreground buildings after the rear row.
- The palace marks Earth and the AI's homeworld; the shipyard appears on every
  colony. Both are separate from the four constructible building types.

`manifest.json` records filenames, dimensions, checksums and model-ID mappings.
`generation-prompts.json` preserves the complete prompt set and generation mode.
