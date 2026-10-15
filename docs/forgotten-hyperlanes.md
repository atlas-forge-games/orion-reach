# Forgotten hyperlanes

Wanderers can decipher ancient routes while their motherships are anchored in
a star system. This system project uses research points and has its own slot,
independent of Dyson Spheres and other physical megastructures.

## Research

Open **Solar system → Forgotten hyperlanes** or the **Hyperlanes** button in the
galaxy sidebar. A stationary mothership must be present to start or fund the
project. A departure order, travel, a living guardian or hostile armed ships
stop that home's contribution. Ordinary peaceful shared systems are eligible.
Black holes cannot be either endpoint.

Each empire can start one project per source system. It costs **300 RP**. The
default allocation is **50%** of research produced by that empire's stationary
motherships in the system. Available controls are 0%, 25%, 50%, 75% and 100%,
plus Pause/Resume. Assign scientists and build research facilities aboard those
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

The random destination is selected once from eligible other stars, excluding
already connected or reserved pairs for that empire. It is stored immediately,
but the interface reveals it only when research finishes. Reloading cannot
reroll it. There is no cancellation or refund/restart action.

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
They obey the same RP, eligibility, fuel and travel rules as the player.

## Compatibility and implementation

Version 0.65 uses save format **46**. Format 45 and earlier load without projects
or hyperlane voyages; loading does not rewrite the source save. Balance profile
11 remains compatible. Cost and one-turn duration are initial fixed rules in
`orion/hyperlanes.py`.

Projects are stored by empire and system; every saved route, progress value,
completion/read status and ship voyage is validated. A one-turn hyperlane
voyage without a matching completed private route is rejected. Destinations
and voyage duration survive saving and loading.

`tests/test_hyperlanes.py` covers RP conservation, local pooling, paused research,
banked investments, deterministic destinations, private access, travel and
retreats, guarded exits, save compatibility, corrupt data and real mouse controls.
`tools/preview_hyperlanes.py` renders the screenshots from the actual game.
