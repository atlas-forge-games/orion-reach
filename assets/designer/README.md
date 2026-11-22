# Visual designer artwork

Original artwork generated for this project's modular ship designer using the
built-in image-generation tool. The original transparent PNG bytes are retained.
No network service is needed while playing. Generation specifications and hashes
are recorded in `generation-prompts.json`.

- `hulls-v1.png`: six unarmed top-down hulls in three columns. Top row: frigate,
  destroyer, cruiser. Bottom row: battleship, carrier, Titan. The row split is at
  47% of image height so the Titan's bow remains intact.
- `modules-v1.png`: a three-by-three atlas. Laser, torpedo, point defense;
  shield, repair, command; engine, sensor/ECM, drone hangar.

`orion/designer_art.py` selects cells and trims transparent margins only in
memory, fits sprites at the current native pixel size, and composes equipment
at the corresponding clickable mounting rectangles. Other weapon variants use
the appropriate beam/projectile illustration; their names and effects remain
those of the selected researched module. Armor uses layered plate illustrations
and visible reinforcement lines on the hull.
