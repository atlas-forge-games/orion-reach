# Galaxy fleet routes and previews — v0.83.4

Select a fleet in Clean mode and move the pointer over a destination system.
A gold dashed path previews a reachable course; an out-of-range target uses
red. Hovering does not issue an order, move the ship icon or change the game.
The preview uses the same destination targeting as the existing fleet controls.

Click the target to issue the order. The icon immediately appears on the route
near the departure system, facing the destination. The path remains visible
when the fleet panel is closed and after saving and loading. Hovering a new
target adds a proposed route while the icon stays on its issued route; clicking
the new target redirects the queued order.

Ships left behind keep their lower-right dock positions. Clicking the origin
before End Turn cancels the selected ships' departure and returns their icons
to the dock. The queued icon position is a display offset only: the turn,
navigation position and saved travel duration do not advance when clicked.
End Turn starts movement, and actual travelling icons use the navigation
model's position. Arrival removes the route and restores a dock position.

Unselected issued routes use a muted faction color. Lines remain one pixel
wide beneath stars, labels and icons, with constant screen-sized dashes during
zoom and panning. Shared paths for the same faction draw once. Clipping still
shows paths crossing the viewport when a fleet is off-screen. Hidden enemy
routes and sensor-contact destinations are not drawn; queued enemy orders do
not reveal a route or directional icon under fog of war.

Classic retains its previous badges, connectors and route presentation. Counts
remain available in the fleet details after clicking a Clean marker.

## Install

Close the game and extract this incremental ZIP over v0.83.3 in the folder
containing `main.py`, `orion/` and `assets/`. Replace the included files, then
run `python main.py`. No dependency, settings or save-format change is needed.

## Validation

All 34 focused checks pass: the route-preview, route, icon and map-style suites,
eight existing fleet-input scenarios, and three camera-input scenarios.
The five new UI tests cover hover without orders, out-of-range feedback,
immediate placement, partial-fleet selection, cancellation, save/reload,
redirecting, all eight headings at three zoom levels, panning and enemy-route
visibility. Existing checks cover dashes, clipping, arrival, artwork, settings,
counts, keyboard navigation and preserving orders across screen changes.

Actual game captures of hover, immediate placement and a closed fleet panel
were inspected. The queued-order Classic capture matches v0.83.3 pixel-for-pixel.
The unrelated full gameplay suite was not rerun; the previously documented
baseline gameplay failures remain outside this update's scope.

Run the four focused suites from the project root:

```bash
PYTHONPATH=tests python -m unittest test_galaxy_route_preview test_galaxy_fleet_routes test_galaxy_fleet_icons test_galaxy_style -q
```

These suites contain 23 of the 34 checks. The additional checks are the existing
fleet UI cases for subset sending, hover/close, origin cancellation, reload,
selection across pages, unissued orders across navigation/End Turn, arrival,
and origin/empty-space clicks; plus camera cases for zoomed destination clicks,
dragging without orders and keyboard panning.

Recreate the captures with `python tools/preview_galaxy_route_orders.py`.
