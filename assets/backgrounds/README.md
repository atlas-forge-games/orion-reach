# Galaxy map background

`galaxy-v2.png` (1672 × 941) is the active background. Its bright decorative
point stars, halos and diffraction spikes have been removed to distinguish the
background from selectable systems. The blue and copper nebula clouds, dark
center and diffuse distant galaxies retain the original composition.

`galaxy-v1.png` is the user-provided **Weite kosmische Sternenlandschaft(1).png**.
Its original PNG bytes remain preserved as the source artwork. The game scales
the active image to cover the map, crops the excess at the center, and slightly
dims it in memory so labels, fleets and routes remain readable. It is static
decoration and does not change gameplay or reveal hidden systems.

**Settings → Galaxy background** switches the image on or off; the default is on.
A missing or unreadable image falls back to the plain map.

To use another background, replace `assets/backgrounds/galaxy-v2.png` with a PNG
and restart the game. A wide image with a dark, relatively quiet center works
best. Loading and scaling are cached rather than repeated every frame.

## Editing provenance

Mode: built-in image generation tool, editing `galaxy-v1.png` as the sole input.
Saved asset: `assets/backgrounds/galaxy-v2.png`. No transparency was requested.

Final prompt:

> Use case: precise-object-edit. Asset type: the background texture for a space strategy game's galaxy map. Image 1 is the edit target. Remove the conspicuous individual foreground stars from this existing image: all bright point stars, circular glowing dots or halos, starbursts and diffraction spikes that could be mistaken for selectable star systems. Fill their positions naturally with the surrounding dark space or nebula texture. Keep the existing wide composition, blue nebula clouds at the upper and lower left, copper-blue diagonal nebula at the lower right, dark central region, colours and diffuse cloud detail as close to the original as possible. Only very faint fine dust-like speckle may remain; no distinct bright points, no flares. Keep any distant diffuse galaxy shapes subdued, without bright pointlike nuclei. This is a quiet background beneath separately rendered game stars. No new objects, no text, no UI, no borders. Preserve the original wide aspect ratio and opaque background.
