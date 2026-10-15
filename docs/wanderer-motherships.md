# Wanderer motherships

The Wanderers inhabit ships, with no populated planets. Their starting habitat
inherits the normal starting population and jobs. The vacated homeworld remains
an ordinary unclaimed planet. Two scouts accompany the starting mothership.

| Property | Initial rule |
| --- | --- |
| Population | Hard maximum of 50 B per mothership, including researched capacity bonuses |
| Facilities | 12 slots per mothership |
| Strategic speed | 25% of normal ship speed, with the same researched speed modifiers |
| Starting speed | 0.5 light-years per turn |
| Initial convoy range | 25 LY with standard balance; 15 LY more than an ordinary Wanderer fleet |
| Hull | 180, unarmed |
| New construction | 1200 Resources, 600 work before racial discounts |
| New inhabitants | Normal starting-colonist amount, included in construction |
| Workforce | Farming, industry, research and mining, managed independently per home |
| Expansion | Build another mothership; settle and planetary occupation are unavailable |

## Controls and movement

The galaxy fleet badge uses a gold habitat-ring silhouette and ship count, with
no population label. During travel, it also shows remaining turns. Select the
fleet and use its Home button, or click the habitat in the solar-system overview
or galaxy system sidebar. Empire and Fleets also open it. The home overview
has the normal workforce controls, right-click output calculations, production
queue and a Set course button. Movement remains editable until End Turn.

A fleet containing a mothership travels at its speed. Selecting only ordinary
ships allows them to leave at normal speed. Escorts retreating with a mothership
also use the same slow speed. The current route and ETA survive saving.

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

Each habitat uses an enclosed Terran-equivalent environment and average resource
yields, retaining existing economic rules and the Wanderers' industry penalty.
Food, credits, research, resources and facility construction continue during
travel. A ship project waits at the front of its queue until arrival; completed
ships launch at the arrival system. Queue estimates include the remaining travel.
Ascension Gates can be built aboard, but charge only while anchored.

Missile bases, planetary shields, fortifications, jump gates and interdictors
cannot be built aboard. Motherships participate in space combat and can be
repaired while anchored. Destroying one removes its population, facilities and
queue. Surviving homes keep the empire alive. Losing the last home eliminates
it. Each inhabited mothership supplies one council vote, matching the existing
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
