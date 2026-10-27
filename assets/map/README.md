# Galaxy fleet icon

`fleet-icon-v1.png` is a dedicated, original transparent map icon generated with
the built-in image-generation tool. It uses `assets/ships/frigate-v1.png` as a
design reference: ivory ceramic armor, dark navy machinery and muted bronze.
The generated PNG bytes are preserved unchanged. `fleet-icon-v1-prompt.txt`
contains the exact prompt; `manifest.json` records the source dimensions,
alpha bounds and SHA-256.

`orion/galaxy_fleet_icons.py` crops transparent margins in memory, caches the
image, rotates it toward the destination and scales it to the map's compact
size. A colored rim distinguishes factions without numeric badges. The
mothership variant reuses the existing `assets/ships/mothership-v1.png`.

The master is deliberately much larger than its final map rendering, so it
can also be used at higher display resolutions without enlarging a tiny sprite.
