# Illustrated fleets and fixed docks — v0.83.2

Later updates add [subtle dashed fleet routes](galaxy-fleet-routes.md).
Since v0.83.4, hovering previews the route and queued departures immediately
line up at its start, facing the destination. This supersedes the v0.83.2
queued-departure placement described below; unordered fleets keep fixed docks.

Clean mode replaces its geometric fleet symbol with a dedicated illustrated
ship icon. The original transparent master is in `assets/map/fleet-icon-v1.png`.
The renderer retains the ceramic armor, dark machinery and bright engine
detail, adds a one-pixel faction rim, and fits the result inside the existing
22 × 22 px click target. Fleets containing a mothership use the existing
illustrated mothership instead.

## Placement and movement

A docked fleet's first slot is **30 pixels right and 24 pixels below** its
system marker. Extra groups use adjacent slots with 24-pixel spacing, wrapping
after three columns. These offsets are screen pixels and stay constant during
zoom and pan. They are independent of labels, guardian symbols and nearby stars.

The view remembers occupied slots using ship membership. An arriving fleet
takes an available slot, without moving fleets already docked. Splitting and
merging groups preserves existing slots where possible. The cache is local to
the current view and is not written into campaign saves.

A queued departure is still docked. During flight, the marker is centered on
the position supplied by the existing navigation model. Its bow follows the
origin-to-destination vector in displayed map coordinates, with clockwise
headings measured from north. This handles diagonal routes and the map's
different horizontal and vertical scales. Arrival restores a docking position.

Fixed positions take precedence over global collision-driven placement. Names
and threat markers move around the fleet targets. At viewport edges, icons
and click targets are clipped rather than sliding to another side of a star.
Zooming helps distinguish unusually dense groups of neighboring systems.

The Clean guardian legend is drawn below the map and hidden while fleet-order
controls occupy that row. This keeps it from covering fixed dock positions.
Classic retains its original badge placement, route lines and in-map legend.

## Compatibility

Install over v0.83.1. The existing Clean/Classic preference and save format 59
remain unchanged. This update does not change ship orders, speeds, positions,
fog-of-war knowledge or campaign rules. Missing artwork has a visible fallback.
Image decoding, resampling and rotation are cached.

## Validation

**74 checks: 71 passed; three unchanged baseline gameplay failures.** The six
new icon tests cover transparency, detailed artwork and missing-file fallback;
all eight travel headings; fixed offsets across pan, zoom and renaming;
arrivals, splits, merges and departures; arrival docking; and clipped hit areas.
The existing map, settings, fleet-input, ownership, fog, camera, hyperlane,
encounter and guardian tests were also run. Older tests specifically asserting
collision-avoiding badges now explicitly select Classic.

The three baseline failures are the same ones reproduced against untouched
v0.83 during the previous update: two AI building-projection errors involving
`BuildingSpec.growth_bonus` and one older expectation about isolated AI fleet
orders. See `galaxy-map-styles.md` for their full test names. No additional
failures remain in this run. The unrelated full gameplay suite was not run.

Classic was compared pixel-for-pixel with the previous busy-map capture and
matched exactly. The new game captures, docked-fleet view and eight-direction
icon sheet were visually inspected. Python compilation passed.

Run the new checks:

```text
python -m unittest discover -s tests -p test_galaxy_fleet_icons.py
```

Recreate the captures:

```text
python tools/preview_galaxy_icons.py
```
