# Fixed building sites and construction placement — v0.82

The former renderer switched to an expanded grid whenever any building's
inspection rectangle overlapped another, or certain technologies appeared.
That recalculated every building's position and size from the current count.
Queueing a factory could therefore move and shrink the headquarters and
shipyard immediately.

Buildings now use persistent individual sites. Existing structures retain
their location and sprite bounds as construction progresses, queues change or
other buildings disappear. Headquarters and shipyard retain their original
anchors. Repeated legacy building types still share one sprite and a count.

## Choosing a site

Click unoccupied foreground in an owned surface colony to open the normal
construction menu. Building actions read **Place** in this mode. Choosing a
building returns to the overview with a translucent preview. Move it to the
desired location and click to confirm. Esc or right-click cancels the preview.
No order, resource reservation or save is made until confirmation.

The preview marks occupied areas in red and explains why the site is blocked.
Inspection labels have reserved space, so neighbouring structures remain
clickable. A site near an edge is clamped inside the view. Buildings are drawn
after the landscape; a building placed near the left trees appears in front
of them. Trees remain part of the existing background artwork.

The ordinary production menu continues to queue buildings immediately and
chooses an available site automatically. Automatic placement never moves or
resizes existing buildings. Normal colonies reserve sensible foreground space
from the start; unusually crowded/custom layouts may give a newly added
building a smaller footprint. That footprint is then retained.

Building management on left-click and building information on right-click are
unchanged. The location request clears on navigation. Uncolonized worlds,
foreign colonies, stored surveys, gas giants and mothership habitats do not
accept surface placement orders. Motherships retain their module bay layout.

## Persistence and compatibility

`Planet.surface_layout` maps each displayed building type to its centre,
ground baseline, width and height in a canonical 1392 by 406 surface viewport.
The renderer scales this geometry to the current view without modifying game
state. Coordinates contain no dependencies on screen or window resolution.

The model validates ownership, availability, costs/slots and site geometry
before accepting an order; failed placement is atomic. Invalid saved geometry,
unknown building types and overlapping saved sites are rejected. Abandoning a
colony clears its sites; conversion to a mothership clears surface geometry.

Save format 58 stores locations in both live planets and survey snapshots.
Older campaigns load with stable automatic locations, without rewriting their
source files. Old surveys retain their observed buildings and do not reveal
current enemy sites. An existing developed colony may adopt the new stable
layout once when first opened after updating.

Balance profiles remain at version 20. Construction timing, costs, building
effects and slot limits are unchanged. No artwork or dependency changes are
included.

## Verification

New tests cover stable positions and sizes across queueing, prioritization,
completion, cancellation and demolition; explicit left-side placement;
save/load and old-save migration; survey isolation; invalid and overlapping
sites; abandonment and habitat conversion. UI tests use a scaled viewport to
exercise preview, confirmation, blocked sites, Esc/right-click cancellation,
unchanged game state, management/info clicks and navigation cleanup.

Across the focused suites, 162 distinct tests passed. Three legacy-save tests
also failed on the untouched v0.81.2 baseline: the version-9 exploration fixture
expects an obsolete ship design, a version-44 active combat fixture contains an
invalid combat ship, and the slave-save test hard-codes save version 52. None
of these failures is introduced by this update. All eight new placement tests
and their ten subtests passed. Compilation passed.

Rendered views were inspected before building, during the left-tree placement
preview, after queueing/completion and with a full colony. Buildings use the
existing artwork loader; missing original assets in a reconstructed development
workspace use its existing fallback sprites.
