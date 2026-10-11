# Galaxy map background

`galaxy-v1.png` is the user-provided **Weite kosmische Sternenlandschaft(1).png**
(1672 × 941). The original PNG bytes are preserved. The game scales it to cover
the map, crops the excess at the center, and slightly dims it in memory so that
system labels, fleets and routes remain readable. It is static decoration and
does not change gameplay or reveal hidden systems.

**Settings → Galaxy background** switches the image on or off; the default is on.
A missing or unreadable image falls back to the plain map.

To use another background, replace `assets/backgrounds/galaxy-v1.png` with a PNG
and restart the game. A wide image with a dark, relatively quiet center works
best. Loading and scaling are cached rather than repeated every frame.
