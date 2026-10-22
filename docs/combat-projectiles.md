# Tactical approach and ordnance

New battles use 24 columns, with the leading fleet columns at 3 and 20
(zero-based). Four deployment columns per side accommodate large fleets.
The minimum height is 13 cells; larger fleets extend the map vertically.
Planetary batteries sit ahead of their fleets, seven cells apart, so opposing
stationary defenses remain able to engage each other.

## Launch and arrival

A weapon volley spends the usual weapon action. Beams resolve immediately;
projectile weapons create independent homing warheads. This covers torpedoes,
fusion torpedoes, MIRVs, antimatter torpedoes, bomber torpedoes and planetary
missiles. MIRVs retain their separate hit rolls and payloads.

Each projectile advances five cells toward its target's current position at
the start of its launching side's next turn, once per tactical round. Both
sides get a response turn before an opposing launch can hit. Estimated arrival
is the remaining straight-line distance divided by five, rounded up. An
8-cell shot takes two advances if its target stays put. Range still limits
launches; moving beyond the original firing range does not cancel a flight.

The launch fixes the hit chance and deterministic roll, including range,
evasion, command and ECM modifiers. Movement changes the interception point
and travel time, rather than rerolling accuracy. Point defense and nearby escort coverage are evaluated when the warhead
arrives. From v0.75, projectiles bypass tactical ship shields. Shield
regeneration and repairs still occur on the owner's usual turn schedule.
Cooldowns begin at launch and work as before. No extra player orders are needed.
Five cells per round is faster than most warships; scouts, drones, diagonal
maneuvers and some thruster-equipped designs can still match or exceed it.

Warheads run out of fuel after six advances if they have not arrived. They
continue after their launcher is destroyed while the battle remains active.
A destroyed target discards its remaining incoming ordnance. Retreat or battle
resolution clears all flights; there are no post-battle hits or retargeting.

## Presentation and inspection

Visible projectiles remain between turns. Selecting their launcher or target
shows estimated arrival beside them. Travel and impact animations only
present damage already resolved by the rules; they cannot apply it twice.

From v0.75.2, missiles have pointed bodies and fins; torpedoes have broader
armoured bodies with weapon-coloured warheads. Both have exhaust trails,
scale with zoom, and face their flight direction. Their bodies are centred
on the saved position between turns and the interpolated position while an
advance is animated. Non-impacting warheads remain visible at the end of
their movement segment while the salvo animation finishes. Impacted or
expired warheads disappear when that segment completes. Launch flashes
do not move a second visual projectile ahead of its actual position.

In the standalone simulator, right-click either side's ship to open a paused
inspector. It shows condition, defenses, weapon details, fitted equipment and
incoming/outgoing ordnance. Close or Esc restores the prior selection and
control mode. Inspecting a moving ship pauses its animation at the current
position. Campaign and simulator battles share the same combat rules.

The campaign and simulator both support 50–300% battlefield zoom. Use the
mouse wheel over the board or +/−, and middle-drag or Shift + arrows to pan.
The percentage button, 0 and Home restore 100%; N brings the next ship into
view. Shift + wheel and Page Up / Page Down scroll vertically. The fixed
sidebar keeps orders and ship information readable. The camera changes no
positions, ranges, actions or simulation time, and is not part of campaign
saves. Starting/loading a battle or rematching resets the view.

## Save continuity

Campaign save format 52 includes projectile positions, age, payload, source,
target and locked hit rolls. Saving during travel and reloading resumes the
same combat state. Older saves load with no projectiles in flight because
those versions already resolved their missile damage instantly. Their
existing tactical positions are preserved; new battles use wider deployment.
Simulator scenario files continue to describe initial setups, not active
battles, and their format is unchanged.

As of v0.73.1, loaded in-flight ordnance uses the five-cell speed on its next
advance. Its existing position, remaining fuel and locked hit roll remain.

From v0.75, launch and impact have separate sound cues, and hull edges are used
for range and travel distances. See [combat geometry and sound](combat-geometry-and-sound.md).
