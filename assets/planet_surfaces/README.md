# Planet surface artwork

Eight detailed, pre-rendered landscape backgrounds match the approved Terran
colony concept. They use a shared elevated viewpoint, a wide 3:1 composition,
an open foreground for colony buildings, and lighting from the upper left.
The landscapes contain no buildings, roads, artificial circular bases or UI.

| Planet type | PNG | Environment |
| --- | --- | --- |
| Terran | `terran-v1.png` | Temperate grassland, conifers, rocky hills and distant mountains |
| Gaia | `gaia-v1.png` | Rich green meadows, flowers, lush vegetation and distant cliffs |
| Ocean | `ocean-v1.png` | Natural coastal terrace, turquoise shallows and island horizon |
| Desert | `desert-v1.png` | Sand and ochre soil, weathered sandstone and dry mesas |
| Ice | `ice-v1.png` | Glacial ice sheet, sculpted snow and frozen mountain ranges; no vegetation |
| Barren | `barren-v1.png` | Lifeless regolith, broken rock, cratered ridges and an airless sky |
| Volcanic | `volcanic-v1.png` | Cooled basalt plateau, distant lava and smoking volcanoes |
| Toxic | `toxic-v1.png` | Sulfur-stained rock, dry mineral crust and a dense toxic atmosphere |

## Files and integration

The project paths are `assets/planet_surfaces/<biome>-v1.png`. Each file is the
original opaque PNG returned by the built-in image-generation tool, without
resizing or conversion. `manifest.json` records the actual pixel dimensions
and SHA-256 checksums. `generation-prompts.json` records the exact prompt set,
references and editing mode, including the Barren vegetation-removal pass
and the replacement of the earlier Tundra concept with Ice. The Toxic landscape
uses Barren as its visual reference.

As of v0.78, `orion/planet_surface_art.py` loads these images for the colony
overview. It crops centrally to the viewport aspect ratio and scales directly
from the original PNG. Eight source images and up to 24 viewport images are
cached, shared between colonies. Missing or corrupt images fall back to the
seeded renderer in `orion/colony_scene.py`.

Buildings remain separate clickable sprites. The renderer no longer adds
service roads or oval pads beneath them. Ocean artwork provides natural dry
ground for buildings; Ice has a solid glacial placement area and Toxic a dry
mineral plain. Original sprites,
construction queues, counts and building actions are unchanged.

The earlier `tundra-v1.png` is obsolete and is not loaded by the game. It may
remain in installations that used the concept artwork pack. Legacy Tundra
biome data migrate to Ice when old saves or balance profiles are loaded.
