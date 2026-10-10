# Orion Reach ship artwork

Seven original transparent PNG illustrations share pale ceramic armor,
charcoal navy machinery, muted bronze details and cyan running lights with
the colony building artwork. Ships use a top-down view with the bow pointing
up. Each class has its own silhouette, from the narrow destroyer and broad
battleship to the carrier's recessed drone hangars and small combat drone.

The images were generated individually with the built-in image-generation
tool. Original PNG bytes are preserved. `generation-prompts.json` records
the prompts; `manifest.json` records dimensions, alpha bounds and SHA-256.

`orion/fleet_art.py` crops transparent margins only in memory, scales with
the original proportions, caches sprites and rotates them for combat.
Owner-colored lights and the tactical hull bars distinguish empires.
Civilian ships and missing-asset fallbacks retain procedural illustrations.

Run `python tools/preview_ship_art.py` to render the artwork catalogue and
the real research, designer, shipyard and carrier combat screens.
