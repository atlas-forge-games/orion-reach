# Galaxy map styles — v0.83.1

This page records the initial style update. v0.83.2 added
[illustrated icons and fixed dock positions](galaxy-fleet-icons.md), and v0.83.3
adds [dashed paths for travelling fleets](galaxy-fleet-routes.md) in Clean mode.
v0.83.4 extends these paths to hover previews and queued departures, with icons
lining up on the route as soon as the order is issued.

The crowded galaxy map previously combined bold labels, numbered fleet badges,
label and badge connectors, travel routes and sensor contact annotations.
Clean replaces those fleet badges with small colored silhouettes, uses 11 px
regular system labels, and removes the map connectors and route lines.
Clicking a marker opens the existing detailed panel and movement controls.

## Player controls

Open **Settings → Interface → Galaxy map style** and select **Clean** or
**Classic**. Both choices save immediately. Clean is the default when no valid
choice exists. Palette and campaign preferences are independent of this choice.

| Element | Clean | Classic |
| --- | --- | --- |
| System names | 11 px, regular, original name casing | Original 13 px bold uppercase |
| Fleet markers | Colored silhouettes, about 11 × 15 px | Original ship artwork in numbered badges |
| Mothership marker | Distinct broader silhouette | Original mothership badge |
| Fleet click area | 22 × 22 px, larger than the symbol | Original badge rectangle |
| Fleet counts | Detailed panel after clicking | Badge and detailed panel |
| Sensor contacts | Small diamonds, details on click | Numbered badges with connectors and heading strokes |
| Label, fleet and threat connectors | Hidden | Visible |
| Travel routes and order preview lines | Hidden; selected fleet and destination remain highlighted | Visible |
| Discovered hyperlanes | Smaller portal markers | Portals and connecting curves |
| Sensor coverage | Faint shading | Shading and outlines |

Names, contacts and ownership still use the existing exploration and sensor
knowledge. Unknown systems remain unnamed. Shared-ownership colors still split
the label. Clean's generic fleet silhouette deliberately leaves composition to
the manifest; a wider silhouette identifies fleets containing a mothership.

## Compatibility

This incremental package targets v0.83. It changes presentation and local
preferences only. Save format 59 and the research and economy rules are
unchanged. Existing settings files are read without being rewritten; a missing
or invalid `galaxy_style` uses `clean`. Choosing either mode persists the value.

The full application source was reconstructed from the saved project updates
through v0.83 to run the existing UI. This archive contains only the changed
modules, documentation, affected tests and new captures; it is not a full game.

## Validation

The map regression run executed **60 tests: 57 passed, 3 pre-existing gameplay
tests failed**. All eight new style tests passed, covering preference validation,
clicking the small icons, counts in the opened panels, movement orders, style
switching at several window sizes, saved-game independence, ownership and fog,
hyperlane markers and dense-map layout with two fleets per system at 1×, 2×
and 4× zoom.

The same three failures occurred in the untouched v0.83 source and tests:

- `test_galaxy_fleets.GalaxyFleetInterfaceTests.test_rival_and_transit_fleets_are_inspection_only`:
  the existing AI building projection raises `AttributeError` for
  `BuildingSpec.growth_bonus` while advancing a turn.
- `test_galaxy_layout.RectangularGalaxyTests.test_starting_colony_ship_can_reach_and_settle_a_neighbour`:
  the same existing AI building-projection error.
- `test_galaxy_layout.RectangularGalaxyTests.test_isolated_empires_can_research_tanks_without_moving_the_map`:
  an existing expectation that AI fleets have no course no longer matches the
  baseline game's orders.

Six additional hyperlane/encounter UI tests and two guardian-map tests passed,
for **68 checks in total: 65 passed and the same 3 baseline failures**.
No additional failures occurred in the regression run. These unrelated
gameplay issues are not changed by this display update.

Actual Clean, Classic, selected-fleet and Interface screens were rendered and
visually inspected. The Classic busy-map screenshot is pixel-identical to the
same scenario rendered with the original v0.83 application. Python compilation
passed. The whole unrelated gameplay suite was not run.

Run the new style tests from the project root:

```text
python -m unittest discover -s tests -p test_galaxy_style.py
```

Render the comparison screens with:

```text
python tools/preview_galaxy_styles.py
```

The generated concept image in chat is illustrative. Screenshots shipped in
this update are direct captures from the implemented game.
