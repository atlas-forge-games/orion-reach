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

Each projectile advances three cells toward its target's current position at
the start of its launching side's next turn, once per tactical round. Both
sides get a response turn before an opposing launch can hit. Estimated arrival
is the remaining straight-line distance divided by three, rounded up. An
8-cell shot takes three advances if its target stays put. Range still limits
launches; moving beyond the original firing range does not cancel a flight.

The launch fixes the hit chance and deterministic roll, including range,
evasion, command and ECM modifiers. Movement changes the interception point
and travel time, rather than rerolling accuracy. Shields, point defense and
nearby escort coverage are evaluated when the warhead arrives. Shield
regeneration and repairs still occur on the owner's usual turn schedule.
Cooldowns begin at launch and work as before. No extra player orders are needed.

Warheads run out of fuel after six advances if they have not arrived. They
continue after their launcher is destroyed while the battle remains active.
A destroyed target discards its remaining incoming ordnance. Retreat or battle
resolution clears all flights; there are no post-battle hits or retargeting.

## Presentation and inspection

Visible projectiles remain between turns. Selecting their launcher or target
shows estimated arrival beside them. Travel and impact animations only
present damage already resolved by the rules; they cannot apply it twice.

In the standalone simulator, right-click either side's ship to open a paused
inspector. It shows condition, defenses, weapon details, fitted equipment and
incoming/outgoing ordnance. Close or Esc restores the prior selection and
control mode. Inspecting a moving ship pauses its animation at the current
position. Campaign and simulator battles share the same combat rules.

## Save continuity

Campaign save format 52 includes projectile positions, age, payload, source,
target and locked hit rolls. Saving during travel and reloading resumes the
same combat state. Older saves load with no projectiles in flight because
those versions already resolved their missile damage instantly. Their
existing tactical positions are preserved; new battles use wider deployment.
Simulator scenario files continue to describe initial setups, not active
battles, and their format is unchanged.
