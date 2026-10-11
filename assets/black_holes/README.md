# Black-hole artwork

Three original images generated for Orion Reach on 2026-10-11:

- `maw-v1.png`: The Maw, an amber accretion disk and dark central silhouette.
- `silent_eye-v1.png`: The Silent Eye, a pale violet photon ring.
- `broken_crown-v1.png`: The Broken Crown, warm golden light and ancient debris.

The original 1536 × 1024 RGBA PNGs are preserved. `manifest.json` records their
SHA-256 hashes and dimensions. No third-party game artwork is used.

Generation direction: realistic cinematic space-strategy assets, transparent
exterior, pitch-black core, restrained highlights, landscape 3:2 composition,
no lettering, frames or background starfield. Each image has a distinct disk
silhouette and palette, readable at galaxy-map scale and in the detail panel.

`orion/black_hole_view.py` scales and caches them in memory. The map uses compact
60 × 40 sprites; the overview uses a larger illustration. A dark core behind the
sprite blocks background stars. A simple ring is used if an image cannot load.
The map's subtle rotating glint follows the existing animation setting.
