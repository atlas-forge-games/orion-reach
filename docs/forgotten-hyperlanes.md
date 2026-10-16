# Forgotten hyperlanes

Wanderers can decipher ancient routes while their motherships are anchored in
a star system. This system project uses research points and has its own slot,
independent of Dyson Spheres and other physical megastructures.

## A finite hidden network

The game creates every hidden connection when it creates the galaxy. Each
ordinary system has approximately a **50% chance of at least one route, 25%
of at least two, 12.5% of at least three**, and so on. These are cumulative
probabilities: about half the systems have no routes, a quarter exactly one,
an eighth exactly two. Black holes are excluded.

Each connection has two distinct endpoints and works in both directions.
There are no duplicate pairs. The generator samples geometrically declining
endpoint counts, then joins them into an undirected network; finite galaxies
can require small adjustments to those counts. At least one connection exists
when two ordinary stars are available. Starting systems receive no preference.

The network uses its own seed-based random generator, without changing planet
or guardian generation. Saving, loading and starting research never reroll it.
Every Wanderer empire researches this same network independently. A stationary,
unblocked mothership can inspect how many routes remain in its system; hidden
destinations are revealed only by completing research.

## Research

Open **Solar system → Forgotten hyperlanes** or the **Hyperlanes** button in the
galaxy sidebar. A stationary mothership must be present to start or fund the
project. A departure order, travel, a living guardian or hostile armed ships
stop that home's contribution. Ordinary peaceful shared systems are eligible.
Black holes cannot be either endpoint.

Each empire can research **one route at a time per source system**. After
completion, Research another route starts the next, if any remain. A system
with no undiscovered, unreserved routes cannot start another project. Every
route costs **300 RP**. The
default allocation is **50%** of research produced by that empire's stationary
motherships in the system. Available controls are 0%, 25%, 50%, 75% and 100%,
plus Pause/Resume. Assign scientists and build research modules aboard those
homes to increase output. Homes in other systems do not fund the local project.

Allocation is calculated from the outgoing turn's local output, rounded down
with a minimum of one RP when a positive allocation and positive output exist.
It is capped at the remaining cost. Those points are deducted from empire RP
available for normal technology; the research screen explains the deduction.
The final turn returns any surplus output to normal research. Contributions
are frozen before movement and production, so arrivals and newly completed
facilities begin contributing on the following turn.

**Invest reserve** spends the smaller of banked RP and remaining project cost.
It cannot take points already invested in a technology. A stationary home is
still required. This voluntary investment works while the automatic allocation
is paused. Projects retain progress if every home departs or is destroyed.

Starting a project selects one of the system's pre-generated connections,
excluding already discovered or reserved pairs for that empire. The selected
destination is stored immediately, but the interface reveals it only when
research finishes. Starting from the other endpoint cannot reserve or count
the same connection again. There is no cancellation or refund/restart action.

## Race-specific victory and Objectives

New-game setup has an independent **Race-specific** victory toggle alongside
Conquest, Science and Galactic Council. The initial Wanderer goal is to
**discover every unique forgotten hyperlane with your own empire**. A two-way
connection counts once, and another empire's discoveries do not add to yours.
The final discovery wins immediately when funded from the RP reserve, or at
the end of the turn when local research completes it. Simultaneous completion
by multiple surviving empires is a draw. An eliminated empire cannot win.

Open **Objectives → Race-specific goals** to see your goal and routes found
out of the fixed total. Known empires appear with their portrait, race, goal,
count, percentage and progress bar. Contact is required under fog of war;
without fog, all empires are known. Observer Objectives includes racial progress
for every empire. Progress never reveals another empire's route locations or
destinations. Races without a defined goal are labeled accordingly.

Turning race victory off still allows discovery, research, travel and progress
tracking. Completing the network then does not end the campaign. Existing
conquest, science, council and elimination rules retain their precedence if
another victory condition is reached on the same turn.

## Travel

A recovered connection is permanent, private to its discovering empire and
usable in both directions. Other Wanderer empires must research their own
routes. Friendship, trade and scanner sharing do not grant access.

Any of the discoverer's ships can use the route, whether alone or in a fleet.
Travel takes **one End Turn**, even for motherships. Fuel limits, ordinary ship
speed, jump-gate modifiers and approach slowdowns do not affect this passage.
The fleet must be at one of the exact endpoints; a nearby star does not qualify.
Separate routes require separate travel orders. Travel spends no RP.

Use **Plot course · 1 turn** on a connection card, then click the destination
star to issue the order. Ordinary map fleet selection also works. Pending
orders can be cancelled or changed before End Turn. Existing ordinary voyages
retain their saved travel duration if a matching hyperlane is discovered later.
Combat retreats can use an available route.

Discovering a route reveals its endpoint, not the destination's planets,
resources or fleets. Arrival reveals the normal survey and still triggers
guardian or hostile fleet combat. A scout travelling alone does not create
a new supply base; moving a mothership there relocates its usual supply range.

## Presentation and AI

The project screen includes an original generated portal illustration. A
clickable portal symbol appears in the system overview. Completed routes and
their endpoints appear on the discovering empire's galaxy map; unknown projects
and foreign networks stay hidden. Observer mode can display all completed routes.
Connection lists paginate, and completed discoveries remain in Turn News.

AI Wanderers start eligible projects at 50% local allocation and use their
own links for scouting, relocation, military movement and guardian expeditions.
They obey the same RP, eligibility, fuel and travel rules as the player. With
race victory enabled, motherships stay to research local routes, then seek
unvisited reachable systems or known unfinished work. Their search remembers
systems they have inspected and does not inspect hidden routes at remote,
unvisited systems. If necessary, they backtrack through inspected systems to
reach new stars beyond their current range. Known guardians and hostile
colonies are avoided.

## Compatibility and implementation

Version 0.67 uses save format **48**. Format 47 and earlier receive a deterministic
hidden network on load, with every existing unfinished or discovered route
preserved in it. Progress, read status and hyperlane voyages are retained.
Older campaigns keep their original victory settings; race victory is not
enabled retroactively. Loading never rewrites the source file. Balance profile
**12** is unchanged. Cost and one-turn duration are fixed rules in
`orion/hyperlanes.py`.

The save stores the hidden network, inspected systems and projects. Endpoints,
duplicates, ownership, progress, completion/read status and ship voyages are
validated. Every project must belong to the network. Multiple completed
projects at one origin are allowed; simultaneous unfinished ones are not.
A one-turn voyage without a matching completed private route is rejected.
Destinations and voyage duration survive saving and loading.

`tests/test_hyperlanes.py` covers RP conservation, local pooling, paused research,
banked investments, deterministic destinations, private access, travel and
retreats, guarded exits, save compatibility, corrupt data and real mouse controls.
`tests/test_race_victory.py` also checks generation odds, finite multi-route
systems, contact filtering, AI exploration, rival wins, draws and migration.
`tools/preview_race_victory.py` renders the new screens from the actual game.
