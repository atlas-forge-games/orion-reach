# Pirates and neutral encounters (v0.68)

The first expansion uses pirate frigates alongside the existing system guardians.
Open a surveyed solar system and choose **Encounters & search**. Orange pennants
on the galaxy map open the same panel; guarded worlds are labelled in the system
and planet views. Discoveries, first sightings, raid warnings and bounties appear
in **Turn News**.

## Four encounter paths

| Encounter | Trigger | What is at stake |
| --- | --- | --- |
| Existing system guardian | Enter its system | Existing guardian rules and rewards remain unchanged. |
| Pirate planet guard | Choose **Engage pirates** | One named planet is protected. Other planets, searches and travel remain accessible. Defeat the guard to settle that world or build an outpost. |
| Hidden flotilla | Complete a scout search | A pirate frigate attacks the ships present. Bring an escort or use the normal tactical retreat. |
| Event raid | Three turns after a warning | Raiders attack fleets in the target system and may steal credits from an undefended settlement. They leave after five turns. |

Pirates use the normal tactical battle rules, with existing frigate artwork and a
corsair flag. They are independent of the diplomatic empires: fighting them does
not declare war or change relationships. Surviving pirate hull damage persists;
a defeated fleet cannot award its bounty again. Operational missile bases defend
against ambushes and raids, but cannot attack guards at another planet.

## Scout searches

- Assign one stationary scout for **two full turns**. There is no CR or RP cost.
- A moving or destroyed scout pauses its assignment. Station another scout and
  choose **Assign replacement scout** to retain completed progress.
- Each empire may search a system once. The first empire to finish claims any
  hidden site; another empire cannot collect the same reward.
- Possible results: **60 CR + 40 RES** supply cache; **80 RP** navigation archive;
  a hostile frigate; or no useful discovery.
- Hidden outcomes are fixed at galaxy creation, and remain hidden even with fog
  of war disabled. Reloading does not reroll them.
- Ordinary automatic scout charting and the earlier discovery system still work.
- Active system guardians, hostile armed empire fleets and active ambush/raid
  pirates block searches. Planet guards do not. Black holes retain their own
  expedition mechanics.

## Placement and raid timing

Placement uses a separate deterministic random stream. Eligible systems have
planets, no settlements or existing guardians, and lie at least **18 LY** from
starting settlement systems. Compact, Standard and Expansive galaxies place up
to **1, 2 or 3** guarded planets respectively. Remaining eligible systems have a
20% chance of a hidden flotilla, 25% of salvage, 15% of an archive and 40% of no
search site. Home systems can be searched but contain none of these seeded sites.

From turn **20**, every tenth turn has a **35%** chance to schedule a raid when
there is a suitable target. Only one pending or active event raid exists at a
time. Targets are inhabited systems without existing living pirates or system
guardians; current headquarters systems are excluded before turn **60**. A
travelling mothership's former system is not an inhabited target by itself.

The target empire gets **three turns' warning**. Raiders arrive with one frigate,
or two from turn **80**, and leave **five turns after arrival**. If the target
still has a settlement and no operational fleet or missile base, the pirates can
steal **10% of its current positive treasury, capped at 60 CR**, once per raid.
They never capture colonies or take population. They may disable a mothership
through ordinary space combat, but do not board it. Defeat the fleet before it
leaves to recover its stolen credits. Raids against an abandoned site collect no
money.

| Defeated pirate fleet | Bounty |
| --- | --- |
| Planet guards | 80 CR + 40 RES |
| Search ambush | 40 CR + 20 RES |
| Event raiders | 60 CR + 20 RES, plus any stolen credits |

Active ambushes and raiders prevent settlement, scout searches, local hyperlane
research, megastructure work, bombardment, invasion and mothership boarding until
cleared. The victim can still move surviving ships away, subject to combat.

## AI, visibility and compatibility

AI scouts can undertake the same searches. They keep the assigned scout in place
and use ordinary exploration afterwards. AI empires challenge local planet guards
when they have sufficient armed hull strength. Pirate battles without a human
participant resolve through the existing tactical simulation.

Only visible threats and remembered contacts appear on the map. Off-screen
victories do not silently update another empire's last-known contact. Search
reports and raid warnings remain private; the Observer can inspect all events.

New-game **Pirate encounters: ON/OFF** controls the new guards, searches and event
raids. It defaults to ON and does not change the earlier guardian encounters.
Saved campaigns from versions before v0.68 migrate with this setting OFF. Start a
new campaign to use the new encounters. Current saves retain hidden outcomes,
search progress, warning deadlines, damage, rewards, reports and ongoing battles.
Save format is **49**; balance profile **12** is unchanged.
