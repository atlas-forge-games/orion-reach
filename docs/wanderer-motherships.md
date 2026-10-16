# Wanderer motherships

The Wanderers inhabit ships, with no populated planets. Their starting habitat
inherits the normal starting population and jobs. The vacated homeworld remains
an ordinary unclaimed planet. Two scouts accompany the starting mothership.

| Property | Initial rule |
| --- | --- |
| Population | Hard maximum of 50 B per mothership, including researched capacity bonuses |
| Modules | 12 bays per mothership |
| Strategic speed | 25% of normal ship speed, with the same researched speed modifiers |
| Starting speed | 0.5 light-years per turn |
| Initial convoy range | 25 LY with standard balance; 15 LY more than an ordinary Wanderer fleet |
| Hull and defenses | 180 hull, defensive lasers (5 damage with standard balance), 12 shield points |
| New construction | 1200 Resources, 600 work before racial discounts |
| New inhabitants | Normal starting-colonist amount, included in construction |
| Workforce | Farming, industry, research and mining, managed independently per home |
| Expansion | Build another mothership; settle and planetary occupation are unavailable |

## Race-specific victory

Enable **Race-specific** in new-game setup to let Wanderers win by discovering
every forgotten hyperlane. The network is fixed at galaxy creation: roughly
50% of ordinary systems have at least one connection, 25% at least two, and so
on. Research costs 300 RP per route, with one project at a time in each system.
Each two-way link counts once. Other empires' discoveries do not count as yours.

**Objectives → Race-specific goals** shows your progress and the goals and
progress of empires you have met. Hidden routes stay private. Research and
travel remain available when the victory is disabled. Older saves retain their
victory settings. See [Forgotten hyperlanes](forgotten-hyperlanes.md) for the
research, network, AI and compatibility rules.

## Controls and movement

The galaxy fleet badge uses the dedicated city-ark illustration and ship count, with
no population label. During travel, it also shows remaining turns. Select the
fleet and use its Home button, or click the habitat in the solar-system overview
or galaxy system sidebar. Empire and Fleets also open it. The home overview
has the normal workforce controls, right-click output calculations, production
queue and a Set course button. Movement remains editable until End Turn.

A fleet containing a mothership travels at its speed. Selecting only ordinary
ships allows them to leave at normal speed. Escorts retreating with a mothership
also use the same slow speed. A disabled home is left behind and does not slow
escaping escorts. Both ordinary and hyperlane retreat orders survive saving.

A selected mothership adds 15 LY of onboard fuel reserves to its entire convoy.
Standard range is 7 LY + the Wanderers' 3 LY bonus + 15 LY = 25 LY. Fuel research
and percentage modifiers apply normally. Additional motherships do not stack
the reserve bonus. Independent escorts retain ordinary fleet range; the map's
range overlay, route preview and warnings follow the current selection.

Anchored homes contribute population and settlement counts in the system view,
and give the system their empire's ownership color. Shared systems retain all
visible owners' colors. Pending departure still counts as anchored; after launch,
the home contributes to neither endpoint until arrival. Undetected foreign homes
do not appear in the overview or disclose ownership through colors.

Supply and scanner centers follow the actual interpolated ship position. Leaving
a system ends the home's live view of its planets; the dated survey remains.
An anchored home can supply and repair nearby fleets. Trade distance and capital
distance use mobile positions. Travel does not eliminate an empire.

## Economy and combat

The home overview uses shipboard module names and artwork. Installed modules
open management controls; queued modules open their progress/cancellation panel;
empty bays open the production catalogue. The Space Hub module opens specialists
directly. Manage modules also exposes its power switch, dismantling and a Visit
Space Hub button. Operational hubs attract the same visitors as planetary hubs;
leaders can be assigned to the mothership and retain that assignment on travel.

| Planetary facility | Mothership module |
| --- | --- |
| Factory / Robotic factory / Nanofactory | Industry / Robotic industry / Nanoassembly module |
| Mining complex / Deep-core mine / Automated refinery | Extraction / Advanced extraction / Refinery module |
| Research lab / Advanced research lab / Quantum research lab | Research / Advanced research / Quantum research module |
| Hydroponic farm | Farming module |
| Trade centre | Commerce module |
| Barracks | Training module |
| Sensor array | Sensor module |
| Solar array | Solar power module |
| Fusion plant | Fusion reactor module |
| Geothermal plant | Thermal recovery module |
| Thermal backup plant | Backup generator module |
| Singularity plant | Singularity reactor module |
| Space Hub | Space Hub module |

This is a presentation change: modules keep the equivalent facility's costs,
outputs, upkeep, energy dispatch, research unlocks and stacking rules. Advanced
industry, extraction and research modules use their family's artwork with tier
markers. Existing saves keep the same IDs and queued progress; planetary
facilities retain their normal presentation, including on empires that own a
captured mothership. No new save or balance migration is needed for v0.66.1.

Each habitat uses an enclosed Terran-equivalent environment and average resource
yields, retaining existing economic rules and the Wanderers' industry penalty.
Food, credits, research, resources and facility construction continue during
travel. A ship project waits at the front of its queue until arrival; completed
ships launch at the arrival system. Queue estimates include the remaining travel.
Ascension Gates can be built aboard, but charge only while anchored.

Missile bases, planetary shields, fortifications, jump gates and interdictors
cannot be built aboard. Motherships participate in space combat and can be
repaired while anchored. Space defeat disables a home instead of destroying it.
Explicit destruction removes its population, facilities and queue. Surviving
homes keep the empire alive. Losing the last home eliminates it. Each inhabited mothership supplies one council vote, matching the existing
one-settlement/one-vote rule. Population tribute cannot empty a home.

## Existing campaigns and balance profiles

Save format 45 reads all previous formats. Each old Wanderer colony becomes a
mothership in the same system. Population, jobs, growth, compatible facilities,
compatible queued work, leaders and the selected home are retained. Populations
above 50 are split across additional homes. Planet-only facilities are refunded
at their base Resource cost. Incompatible queued projects use their normal
cancellation refund. Previously built colony ships become additional habitats;
an existing voyage retains its saved arrival schedule.

For an unfinished legacy battle, conversion is postponed until the battle closes.
The pending conversion itself survives a save/reload, preserving the tactical
battle and its participants. Other civilizations' saves and planets are unchanged.

Balance profile 11 adds the mothership's cost, work, hull and tactical movement
while keeping existing profile values. Capacity 50 and the quarter-speed ratio
are fixed civilization rules in this first version.

Version 0.64.1 keeps save format 45 and balance profile 11. Existing campaigns
gain the system controls and extended convoy range without conversion.

## Boarding, raiding and salvage (v0.66)

A mothership reduced to zero hull in space combat remains at **1 hull** in the
campaign, disabled for **three completed turns**. It cannot move, fight or launch
ships. Its economy, facility construction, supply and scanners continue. It does
not restart combat while disabled. When the timer expires, defenses and engines
return with at least 10% hull; ordinary repairs can restore more.

Defeat the defending fleet, hostile missile bases and any guardian before
approaching. Open the detected home in the system view. Existing non-aggression,
friendship and coalition protection rules apply. Boarding or destruction starts
war. Only one boarding attempt per home is allowed each turn.

| Action | Requirements | Result |
| --- | --- | --- |
| Board and capture | Troop transports; win the ground battle | Ownership of the ship and habitat transfers. Population, facilities and ordinary paid projects survive. Ascension Gate is removed. |
| Raid stores | Troop transports; win the ground battle | Transfer capped credits/resources from the victim's actual stocks. Owner retains the habitat. Varkesh may also take captives. |
| Destroy for salvage | An operational armed ship in the system | Remove the habitat and recover modest Resources. No troops required. |

Habitat decks add **25% defending firepower** to existing militia and garrison
bonuses. The preview uses the same simultaneous ground battle calculation as
resolution. Transport losses follow troop casualties, rounded up to whole loads.
Full surviving squads re-embark. Capture assigns leftover troops as the new
garrison; a successful raid returns them to a friendly settlement.

A raid can take at most **10 CR per inhabitant + 20 CR per installed facility**
and **3 RES per inhabitant + 10 RES per installed facility**. Actual loot is also
capped by the defender's available stocks and the attacker's stockpile capacity.
There is no separate cargo inventory and no technology loot. A successful raid
starts a **ten-turn cooldown** stored on that home, including after capture or
another space battle. Failed raids take no loot and still lose their casualties.

Varkesh captives are limited to one quarter of the population (rounded down),
available homeworld slave capacity, and leaving at least one inhabitant aboard.
A missing or full homeworld yields no captives. Ordinary empires take no slaves.

Salvage is **10% of the mothership's base Resource cost plus its installed
facilities' base Resource costs**, rounded down and capped by stockpile capacity.
It does not grant the victim's remaining treasury, research or technology.

Every civilization can operate captured homes with its own economic modifiers.
Only Wanderers can construct new homes. On a foreign capture, queued mothership
projects are cancelled with the normal refund for unfinished paid work. Private
battle dispatches preserve the home's name even after it is destroyed. AI
empires use the same requirements, favor a viable capture (or a Varkesh raid),
and can destroy a disabled enemy home when boarding is not viable.

Save format **47** persists emergency repairs, captured ownership and raid
cooldowns. Balance profile **12** upgrades the former zero-damage mothership
default to its basic armament, preserving custom nonzero values. Existing active
battles keep their shield damage; the generator begins charged in the next
engagement. Captured ships do not inherit the former owner's forgotten hyperlanes.

The dedicated PNG is cached and scaled in memory for galaxy, fleet, system,
habitat and tactical views. It uses no new animation or per-frame file loading.
