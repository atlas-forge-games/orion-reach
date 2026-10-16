# Orion Reach ship artwork

Twelve original transparent PNG illustrations share pale ceramic armor,
charcoal navy machinery, muted bronze details and cyan running lights with
the colony building artwork. Ships use a top-down view with the bow pointing
up. Each class has its own silhouette, from the narrow destroyer and broad
battleship to the carrier's recessed drone hangars and small combat drone.
The troop transport has a blunt armored bow and protected personnel pods;
the colony ship has rounded habitat modules and enclosed greenhouses; the
slender scout carries scanning dishes and a dorsal sensor lens. These three
support ships are visibly unarmed, matching their existing in-game roles.

The images were generated individually with the built-in image-generation
tool. Original PNG bytes are preserved. `generation-prompts.json` records
the prompts; `manifest.json` records dimensions, alpha bounds at the renderer's
32/255 threshold, and SHA-256.

`orion/fleet_art.py` crops transparent margins only in memory, scales with
the original proportions, caches sprites and rotates them for combat.
Owner-colored lights and the tactical hull bars distinguish empires.
All standard ships, including civilian craft, use the same artwork loader.
Missing-asset fallbacks retain procedural illustrations.

Run `python tools/preview_ship_art.py` to render the artwork catalogue and
the real research, designer, shipyard and carrier combat screens.
Run `python tools/preview_support_ship_art.py` for the three support ships,
their small-icon comparisons, and the real shipyard, fleet and combat screens.

Version 0.60.2 adds `outpost_ship-v1.png`: an unarmed construction vessel with prefabricated base modules, crane booms and fuel tanks. Prompt in `outpost_ship-prompt.txt`; original transparent PNG preserved.

Version 0.66 adds `mothership-v1.png`: an inhabited ark with two living rings, city districts, docking bays, laser turrets and cyan shield emitters. Generated with the built-in image-generation tool; original transparent PNG bytes are preserved. The full prompt is in `mothership-prompt.txt`. Fleet, galaxy, system, habitat and tactical views share the cached artwork, with the previous procedural image retained as a missing-file fallback.
