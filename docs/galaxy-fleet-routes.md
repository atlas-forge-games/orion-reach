# Galaxy fleet flight paths — v0.83.3

In Clean mode, fleets travelling between systems now have a one-pixel dashed
path from their departure system to their destination. The line uses a muted
version of the fleet's faction color. It is drawn below stars, labels and ship
icons, leaving the direction visible through the ship's existing heading.

Paths appear when movement begins and disappear on arrival. Docked fleets and
queued departures remain line-free. Counts still appear after clicking a fleet.
Classic retains its existing routes and numbered badges.

Dash lengths stay constant on screen as the map zooms, and their pattern stays
anchored to the route during panning. Routes are clipped to the viewport and
remain visible when the fleet itself is off-screen. Shared paths belonging to
the same faction are drawn once, including voyages in opposite directions.
Only fleets already visible through the game's visibility rules receive paths;
sensor contacts never expose a hidden destination.

## Install

Close the game and extract this incremental ZIP over v0.83.2 in the folder
containing `main.py`, `orion/` and `assets/`. Replace the included files, then
run `python main.py`. No dependency, settings or save-format change is needed.

## Validation

All 18 focused route, map-style and fleet-icon tests pass. The new route checks
cover departure and arrival, unchanged campaign data, sensor-only enemy
contacts, observer visibility, off-screen crossings, clip restoration, panning,
shared routes, visible gaps, diagonal paths and zero-length paths.

Clean and zoomed Clean captures were inspected in the actual game renderer.
The same active-flight scenario in Classic matches v0.83.2 pixel-for-pixel.
This update does not rerun the unrelated gameplay suite; previously documented
baseline gameplay failures remain outside its scope.

Run the focused checks from the project root:

```bash
PYTHONPATH=tests python -m unittest test_galaxy_fleet_routes test_galaxy_style test_galaxy_fleet_icons -q
```

Recreate the captures with `python tools/preview_galaxy_routes.py`.
