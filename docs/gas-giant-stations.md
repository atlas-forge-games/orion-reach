# Gas giant orbital industry — v0.81

Gas giants remain uncolonizable, with zero population, surface buildings and
surface outposts. Every civilization can operate **one main orbital station per
gas giant**, shared across all empires. Aetheri atmospheric habitats and
population are a later feature.

## Play

Open a surveyed gas giant in the planet overview and choose one of three
specializations. Costs and output shown on the cards include the atmosphere's
modifier. A colony or anchored mothership in that system supplies construction
crews. Without one, an **idle outpost ship is consumed** as the station's
foundation, in addition to the listed construction payment.

Pay Resources and Credits immediately. Assembly takes two End Turns. Upkeep
starts immediately; production begins on the following outgoing turn. A station
ordered on turn 1 is operational when turn 3 begins and produces during turn 3.
An occupied slot cannot be upgraded into another specialization. Dismantling
removes it without a refund and lets its owner commission a replacement.

Base values before planetary modifiers:

| Installation | Resources | Credits | Gross output per turn | Upkeep per turn |
| --- | ---: | ---: | --- | ---: |
| Gas refinery | 80 | 20 | 6 Credits | 1 Credit |
| Energy platform | 120 | 30 | 8 system energy | 2 Credits |
| Research station | 100 | 40 | 4 research points | 2 Credits |

The refinery therefore adds 5 net Credits per turn on an ordinary giant.
Credits and research enter the owning empire's normal turn totals. Station
upkeep appears separately in the Empire screen's budget breakdown. Values are
initial balance constants in `orion/gas_giants.py`; the existing balance-profile
format is unchanged.

## Atmospheric properties

Each gas giant has one deterministic property, derived from the campaign seed
and its system/planet IDs without changing galaxy generation. Existing giants
receive the same properties every time their campaign is loaded; no planets are
added to old maps.

| Property | Effect | Relative generation weight |
| --- | --- | ---: |
| Ordinary atmosphere | Standard values | 4 |
| Gas-rich atmosphere | +25% refinery output | 2 |
| Strong magnetic field | +25% energy output | 2 |
| Extreme storms | +25% research; +25% construction cost; +1 Credit upkeep | 1 |
| Calm atmosphere | −20% Resources and Credits for construction | 2 |

Output rounds down and construction costs round up to whole units. The overview
shows the resulting values, so a gas-rich refinery produces 7 gross Credits.

## Shared system energy

Platforms contribute a finite pool for the owning empire **in their own system**.
Colonies receive power in the existing deterministic system/planet order, up to
their deficit in steady generation. Remaining capacity passes to later colonies.
Power is allocated once, before fuel-burning backup plants are dispatched from
the empire's shared Resource stockpile. Whole-building activation rules still
apply. Surplus is not stored, exported or duplicated between colonies.

Anchored motherships can receive power; travelling ones cannot. Other empires'
colonies never receive the station's output. Completed Dyson Spheres make orbital
power unnecessary. The colony energy display identifies orbital contributions.
Turn processing freezes one dispatch before travel and construction. Construction
forecasts include assembly completion and use the same allocation rules.

## Military control

- Stations are unarmed, with 60 hull. Normal fleets defend their system.
- Armed ships from an empire at war, system guardians and pirate blockades
  suspend output. Peaceful visitors and unarmed transports do not blockade.
- Assembly dates continue to elapse under blockade, but production remains off.
  Upkeep continues during both assembly and blockade.
- Defeat opposing ships and missile bases before bombarding or capturing.
  Non-aggression pacts and coalitions protect stations through the normal rules.
- Bombardment uses the same attacks and once-per-turn ship action as surface
  outposts. Zero hull destroys the station and frees the slot.
- Capture requires 30 hull or less, an armed escort with an unused bombardment
  action, and an idle troop transport. The transport is consumed as the occupation
  crew. Ownership transfers immediately, hull stays damaged, and production waits
  until at least the next turn. Capture also spends the escort's bombardment action.
- Attacks/capture start war and end treaties through the existing diplomacy rules.
- Stations recover 4 hull per peaceful turn after the same one-turn damage delay
  as outposts. They provide observation, but no fuel coverage, population, votes
  or empire survival. A defeated empire loses its installations.

AI empires use the same construction and combat rules. They invest from a reserve in systems with their own colonies or anchored
motherships, keep remote outpost ships on refuelling-expansion orders, prefer energy where local colonies have shortages, and may choose storm research
stations when their budget permits. They can bombard or capture undefended enemy
stations, and station systems are included in military targeting.

## Persistence and presentation

Save format 57 adds an optional `orbital_station` record to planets and their
survey snapshots. Saves through format 56 migrate with no stations. Validation
rejects invalid owners, station types, hull values, future attack dates and
stations attached to solid worlds or mobile habitats. The balance profile remains
version 20.

Owned stations provide live local intelligence. Other empires see only the last
observed snapshot until they return. Destruction, capture and dismantling record
a final dispatch for the previous owner. Galaxy labels and system markers include
station ownership without treating a station as a colony.

The new overview reuses the detailed extraction, fusion and research module PNGs
already shipped with v0.66.1, over the existing gas-giant atmosphere landscape.
No new artwork installation or external dependency is required.
