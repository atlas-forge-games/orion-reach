# Visual ship fitting — v0.98.0

The designer uses a large ship view with clickable positions. Selecting a mount
filters the equipment panel to compatible modules. Cyan marks an available
position; gold marks the current selection. The preview is labeled separately
and does not change the draft until **Install module** or **Plan module** is used.

## Hull layouts

| Hull | External mounts | Shared internal bays | Drone hangars |
|---|---:|---:|---:|
| Frigate | 4 | 1 | 0 |
| Destroyer | 4 | 1 | 0 |
| Cruiser | 4 | 2 | 0 |
| Battleship | 6 | 2 | 0 |
| Carrier | 4 | 1 | 2 |
| Titan | 6 | 3 | 0 |

Every hull also has one engine selection and one armor selection. Standard
propulsion and hull plating are included; choosing an upgrade replaces the
previous upgrade. Reset restores the standard equipment. Heavy armor's movement
penalty combines with the engine's tactical movement bonus.

Weapons and point defense share external mounts. Shields, repair systems,
scanners, command relays and other fleet-support equipment share internal bays.
Each bay holds one module. Different bays on a larger hull can carry different
systems. Command relays fit all combat hulls; escort arrays remain destroyer-only,
ECM projectors cruiser-only, and the stronger flag bridge Titan-only. Command
bonuses still use the strongest nearby source and do not stack.

Dedicated carrier hangars accept assault, interceptor or bomber drone bays.
Fitting a drone bay does not consume an internal equipment bay.

Existing weapon ranges, hull-scaled equipment, accuracy, shields, repair reserves
and fleet-support effects continue to determine combat. Physical positions store
the layout of equipment; they do not introduce directional firing arcs or
individually destructible ship sections. A valid combat blueprint still needs
an offensive weapon or drone bay.

## Editing and production

New designs start with a bare hull. Use the name field, then **Save design**.
Choose an owned colony on the left and **Queue ship** after saving. Unresearched
blueprints remain available for planning; research is checked when building.

Changing hull keeps compatible equipment and puts everything else in the
**Unplaced equipment** list. Nothing is discarded just because the hull changes.
Use **Review unplaced** to remove individual items or clear the list, or choose
a hull that can carry them. Assigning an unplaced item to an empty compatible
mount consumes that item from the list. Replacing equipment removes the previous
module from the draft. Each mount's location survives saving, including gaps.

Right-click a fitted module or an equipment card for help. Use the equipment
panel's arrows or Page Up / Page Down to browse choices. The saved-blueprint
list has its own page controls. Auto fit chooses researched equipment, with
hull-specific planning support as before. The combat simulator uses the same
controls with all equipment available.

## Compatibility and data

Blueprint fitting version 3 stores canonical `(mount_id, module_id)` pairs in
`ShipDesign.mounts`, alongside the equipment list used by combat and production.
Both representations are validated together. Unknown positions, repeated
positions, incompatible equipment and mismatched equipment lists are rejected.

Fitting versions 1 and 2 retain their original equipment rules and statistics.
Viewing an old blueprint does not change it. Editing previews a refit under the
new physical rules; any excess equipment must be resolved before saving. Ships
and paid orders hold immutable snapshots, so later blueprint changes do not
alter them. Old stock snapshots are still recognized as stock equipment.

Campaign save format 66 stores mounting positions. Combat-scenario format 2
accepts earlier format-1 scenarios. Balance-profile format 22 adds
`external_mounts`, `internal_bays` and `hangar_bays`, upgrading old profiles in
memory while retaining their existing values. The older capacity fields remain
available to validate older blueprint snapshots.

The designer's original hull and equipment atlases are included in
`assets/designer/`. Rendering and click regions use the same fitted image bounds,
including native display scaling and compact layouts.
