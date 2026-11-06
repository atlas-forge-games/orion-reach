# Star Atlas — v0.92.1

Star Atlas is the default galaxy presentation, based on the smaller-ship version
of concept A. It replaces the label “Clean” in Settings → Interface. The saved
preference key remains `clean`, so existing settings adopt the new appearance.
Classic keeps its earlier rendering. Campaign saves still use format 62.

## Appearance and interaction

- Stars have steady white cores, coloured halos and fine tapered rays. Halos
  and rays pulse by about 15% on four-to-six-second cycles, with a stable phase
  and period for each system. Turning off Settings → Graphics → Animated effects
  freezes the light at its normal level. Selection
  uses four corner brackets, which turn red for an unreachable route target.
- Names use 16-pixel logical bold sans-serif type with a quiet dark outline.
  Actual display-pixel glyph bounds determine their placement, including at
  fractional interface sizes. Names avoid stars, fleet targets and map controls.
- Known ownership appears in one thin ring. Multiple owners share its arc;
  colonies, refuelling outposts, stations and anchored motherships all contribute.
  Unvisited systems have no names or ownership rings. Stored surveys and current
  visibility continue to govern the information shown.
- Illustrated ships occupy at most 24 logical pixels inside a 28-pixel target.
  Neutral hulls retain faction-coloured navigation and engine accents. Selecting
  a fleet adds a gold outline without hiding those faction colours.
- Dock slots start 30 pixels right and 30 pixels below the star at 100% zoom.
  The initial offset grows with the star; slots remain 32 pixels apart. Existing
  fleet membership retains its slot during arrivals and splits.
  Ship direction, queued departures and dashed route previews use the existing
  navigation geometry.

Star Atlas stars, ownership rings, selection brackets and click targets grow
with the square root of map zoom: 1.4× at 200%, 1.7× at 300% and 2× at 400%.
Name offsets and dock positions leave room for the larger symbols. Names and
ship icons keep their screen size. Interface size scales the whole interface.
The guardian legend and its reserved footer strip have been removed in both
map styles. Guardian symbols and system inspection continue to work.

## Rendering

The renderer caches separate star core/marker and light layers at their final
display size; threefold sampling smooths curves before the native-size blit.
Pulsing only changes the cached light layer's opacity; time is not a cache key.
It uses the presentation clock and system ID, never game RNG or campaign state.
Ship sprites are made from a
256-pixel cropped master, rotated and reduced to their final display size.
The final blit bypasses canvas image rescaling. Missing artwork retains the
silhouette fallback. `galaxy_labels.py` measures and draws the same native font
size, including its outline, so scaled labels do not clip or overlap controls.

## Validation

Focused checks cover galaxy navigation, fleet docking and splitting, arrival,
all eight travel headings, fog, shared ownership, motherships, palette changes,
zoom, route previews, panel folding and native resource cards. Visual checks
cover five window/interface-size combinations, a crowded galaxy, fleet orders,
Wanderers and settings. Animation checks cover steady cores, disabled motion,
native scaling and unchanged RNG. Zoomed destination tests use enlarged target
edges to check that hover previews and clicks agree.

![Radiant stars in the game](../screenshots/galaxy_radiant_stars.png)
