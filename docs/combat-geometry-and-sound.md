# Combat geometry, defenses and sound — v0.75

## Separate defenses

Tactical ship shields absorb beam damage. Torpedoes and missiles, including
fusion, MIRV, antimatter and bomber warheads, bypass ship shields and damage
the hull after point defense. A surviving ship keeps its shield charge when
hit by a projectile. Destroyed ships still have zero shields.

Point defense, flak, escort arrays and interceptor screens reduce projectile
damage. They do not reduce laser, assault-drone or interceptor-drone beam
damage. Ion amplification, phased penetration, hardening, regeneration and
repair reserves retain their beam-specific roles. The same damage forecast
is used by the AI and actual combat.

This is a fictional defense model. Ordinary magnetic fields do not provide
laser-proof barriers. The game's shields represent speculative beam-absorbing
technology. The strategic planetary shield/invasion rules are separate from
these tactical ship shields.

## Hull footprints

| Unit | Occupied cells (width × height) |
| --- | --- |
| Scout, frigate, combat drone, outpost ship | 1 × 1 |
| Destroyer, colony ship, troop transport | 2 × 1 |
| Cruiser | 2 × 2 |
| Battleship, carrier | 3 × 2 |
| Titan | 3 × 3 |
| Mothership | 4 × 3 |
| Guardians | 2 × 2 to 3 × 3, depending on type |
| Planetary battery | 1 × 1 |

Ships keep a fixed orientation; there is no rotation action. Every occupied
cell participates in collision detection. Movement checks the full hull at
every step and both intermediate placements for diagonal moves. A large ship
cannot squeeze through a narrow gap or clip another ship's corner.

Deployment packs complete hulls without overlap and increases board height
when necessary. Flagships begin near the vertical centre of their formation.
Drone launch positions surround the carrier's entire footprint. Clicking any
visible occupied cell selects the ship; simulator right-click inspection uses
the same full footprint. Artwork, selection boxes and movement previews grow
with the hull and follow the zoomed camera.

Movement highlighting covers all cells the ship can occupy at a legal
destination. Hovering an exposed highlighted cell previews the exact landing
footprint with every occupied square marked: six for a battleship, nine for a
titan, and twelve for a mothership. Clicking uses that same previewed placement.
The newly occupied edge cells allow short moves even for faster, larger ships.
The current hull remains selectable, including where a destination overlaps it.

Weapon range and projectile travel use nearest hull-cell coordinates. Support
and flagship radii use hull centres, matching their displayed circles.

## Beam firing lines

All direct-fire beam families require a clear line between the nearest firing
and target points. Friendly and enemy hulls block this line, including diagonal
corner contacts. Destroyed ships cease to block. The UI identifies a blocked
firing line and outlines the obstruction; firing such a beam is unavailable.
There is no automatic friendly fire or penetration through an intervening hull.

In a mixed beam/torpedo design, an obstructed target can still receive guided
torpedoes. Only legal weapons join the volley. The AI checks the same lines
when choosing a target and seeks a clear lane when moving.

Guided ordnance is not subject to the direct-fire line rule. Its existing
homing travel remains an abstraction rather than physical obstacle routing.
Phased beams can penetrate shields, but cannot pass through ships.

## Graphics at high zoom

From v0.75.2, large ships use the original high-resolution artwork at their
final screen size. The renderer avoids enlarging small intermediate icons,
so hull panels and weapons remain detailed at 300% zoom. Procedural guardians
and missing-art fallbacks are drawn at a suitably large resolution too.

Torpedoes and missiles have distinct silhouettes and exhaust trails. Their
graphics follow their actual position between turns and their interpolated
position during a flight animation. See [ordnance](combat-projectiles.md).

## Sound

Original synthesized cues distinguish ordinary beams, heavy beams, missile
launches, shield hits, hull impacts and explosions. They are generated with
the existing Pygame mixer and Python standard library; no new dependency or
downloaded sound asset is required.

Launch sounds occur when firing. Projectile impact sounds occur when the
warheads arrive, rather than at launch. Misses have no impact cue. Salvos
coalesce repeated cues and use available mixer channels to avoid excessive
overlap. Rendering and reopening a save do not replay a sound or apply damage.

**Settings → Sound → Sound effects** controls combat cues and interface tones;
music remains independently controlled. Screenshot mode stays silent, and a
missing audio device does not prevent the game from running. Sounds are player
feedback, not a simulation of sound propagation through vacuum.

## Saved games and installation

Install over v0.74 by extracting the update into the directory containing
`main.py`, with the game closed, and replacing the listed files. Start with
`python main.py` or `python combat_simulator.py`.

Save format 53 records hull layout and battlefield height. Existing unfinished
battles loaded from format 52 or earlier retain one-cell footprints and their
positions, orders and in-flight warheads. New battles use the new footprints.
The new defense rules apply when further attacks resolve. Older game versions
cannot read newly written format-53 saves; retain a backup before updating.

Use `python tools/preview_combat_geometry.py` to reproduce the firing-line
preview. See `TEST_REPORT_v075.txt` for the verified test scope.
