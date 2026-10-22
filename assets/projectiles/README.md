# Projectile artwork

The six original PNGs were supplied in `torpedo_sprite_pack.zip`. They are
included byte-for-byte; the accompanying labelled card images are not used
as in-flight sprites.

| Weapon ID | Image |
| --- | --- |
| `torpedo` | `standard_torpedo.png` |
| `fusion_torpedo` | `fusion_torpedo.png` |
| `mirv` | `mirv_torpedo.png` |
| `antimatter` | `antimatter_torpedo.png` |
| `bomber_torpedo` | `bomber_drone_torpedo.png` |
| `missile` | `defense_missile.png` |

All face right. The source PNGs have an opaque navy background and include a
blue engine plume. `orion/projectile_art.py` makes the background transparent
at load time, retaining enclosed dark machinery and the soft exhaust edge.
Its source-image measurements centre each body on the simulated position and
exclude exhaust from the body length. Rotation and zoom share the same anchor.

The loader and rendered sizes/headings are cached. Restart the game after
replacing assets. Different source dimensions or layouts require updating
the body measurements in `PROJECTILE_ART`. The earlier procedural graphics
remain available automatically if a PNG is missing or cannot be loaded.

Preview: `python tools/preview_projectile_sprites.py`.
