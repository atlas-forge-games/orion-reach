# Civilization legacies — v0.72

Choose **Race-specific** in galaxy setup. Open **Objectives → Your race objectives**
for exact targets, live progress, installation status and known rivals.
Conquest and Galactic Council victory remain separate options. Disable every
victory option for an open-ended campaign.

## Shared rules

The twelve planetary civilizations unlock their own legacy installation after
**8 discovered technologies**. Build it through normal colony production.
Default cost is **300 Resources, 180 work, one building slot, 6 local energy and
4 CR upkeep per turn**, before ordinary modifiers. The balance editor exposes
these buildings. They cannot be bought with credits or installed in motherships.

Most goals require installations in **2 / 3 / 5 separate systems** in Compact /
Standard / Expansive galaxies. Skirr need one extra system; Varkesh need only the
original homeworld. Targets are capped by suitable generated systems. Diversity
requirements can require additional sites in a Compact galaxy.

An operating site needs power, nonnegative food balance, and **4 B citizens**.
Nexus, Xenonflora and Dominion sites need 6 B; Skirr sites need 8 B. Nexus and Skirr
sites require those citizens to belong to their native species. Other local
requirements appear in the table below and in the installation's status.

Hostile armed ships in orbit block operation. Friendly ships and unarmed scouts
do not. Bombardment interrupts operation on its turn and the following turn.
Capture destroys completed and queued legacy installations, including captures
by another empire of the same race. Ordinary buildings retain their capture rules.

**Satisfy every requirement for 5 consecutive completed turns** to finish the
legacy. Failure resets the finale. Planetary Minds, World Trees and Queen Nests
also lose their local maturity when operation stops. Committed Resources or RP,
raid trophies and voluntary membership history remain recorded. A newly completed
installation begins maturing on the following turn.

Final stages begin automatically. Turn news reports their start, interruption
and penultimate turn to the player and contacted rivals. Rival progress is
aggregate: no hidden system names, colony names or destinations are disclosed.
AI empires use the same costs and checks, and build and support their installations.
Simultaneous race completions draw; eliminated empires cannot win. Existing
conquest and council precedence remains when several victory types are enabled.

## All thirteen goals

| Civilization | Legacy | Additional requirements |
| --- | --- | --- |
| Terran | **The Galactic Charter** | Friendship with up to two surviving diplomatic empires. Peace with every surviving empire and no broken promise in the last 10 turns. Friends remain independent. |
| Kharuun | **The Eternal Work** | Commit 600 Resources per required system. Each operating foundry consumes up to 20 stored Resources per turn and needs an operating factory, mine and two industrial workers. |
| Aelari | **The Living Archive** | Personally scout-scan 40% of ordinary star systems, record up to six generated biomes and discover 12 technologies. A revealed map does not count as personal exploration. |
| Lithar | **Awaken the Mountains** | Planetary Minds on Desert, Tundra, Barren or Volcanic worlds. Each needs 12 consecutive operating turns. Awaken up to three different generated harsh biomes. |
| Varkesh | **The Throne of Fear** | A Great Moot on the original homeworld, three unique raid trophies or clan trials, surviving fleet combat strength 120, and a homeworld garrison of eight. Repeated raids on one world grant only one trophy. |
| Xenonflora | **The Second Spring** | World Trees across up to three different settleable biomes. Each needs 6 B citizens, +3 food and 10 consecutive operating turns. Trees represent restored biospheres without changing the underlying planet biome. |
| Nexus | **The Final Computation** | Processing Cores with 6 B Nexus citizens and three scientists each. Dedicate 500 RP per required system; each operating core diverts up to 20 banked/incoming RP per turn before normal research. |
| Aetheri | **The Star That Woke** | Personally scout-scan 60% of ordinary star systems. Operate Resonance Choirs around up to three different available stellar types. |
| Dominion of One | **The Last Independent Thought** | Hold up to two surviving rival founding worlds, control at least 50% of galactic civilian population and make at least 80% of your citizens Dominion. Each operating Overmind Node converts 1 B local non-Dominion citizens per turn. |
| Serevan Union | **Many Peoples, One Future** | Up to three willing cultures, each with at least 2 B surviving citizens. Maintain peace and 10 turns without broken promises. Voluntary accession and friendship-based immigration establish willing membership. Conquest alone does not. |
| Skirr Swarm | **The Great Hatching** | Mature Queen Nests in one more system than the normal target. Each needs 8 B Skirr, +2 food and eight consecutive operating turns. Maintain at least 8 B Skirr per required system across mature nests. |
| Remnant | **The Throne Beyond Memory** | Personally scout-scan up to three ancient archive or tomb systems. Dedicate 500 RP per required system; each operating Memory Throne diverts up to 20 RP per turn before normal research. Previously claimed archives still count when personally surveyed. |
| Wanderers | **Recover every forgotten hyperlane** | Unchanged: independently discover every unique connection in the finite hidden network. Two-way routes count once. No installation or five-turn finale is required. |

## Voluntary Union membership

With an operating forum and a friendship treaty, the Union can welcome **1 B
settlers of that partner's native culture every third turn for 25 CR**, until
it has 2 B of that culture. The source colony must retain at least 3 B citizens;
the destination needs room under its population capacity. These are transferred
citizens, not newly created population. Only the culture actually volunteering
gains membership. Ending friendship stops further immigration; existing settlers
remain citizens. A voluntary colony accession records its consenting cultures.
Enslaved inhabitants do not count as member cultures.

## Small, solo and unusual galaxies

Requirements use generated content and surviving civilizations rather than a
mandatory checklist of every race. Terran friendship targets fall to the number
of eligible survivors; Dominion and Skirr are excluded as charter partners. The
Union's culture target includes available diplomatic cultures and willing
residents already present. Solo diplomatic campaigns can use their native
civilization and colonial institutions.

The Dominion has no foreign founding-world requirement when none exist. Destroyed
founding worlds no longer count towards that target; mobile Wanderer homes are
excluded. When no other inhabited colonies remain, Varkesh with an operating Moot
and fleet strength 120 may earn a clan-trial trophy **every sixth turn for 200
Resources**, until they have three. Remnant's ancient-site target can fall to zero
if none were generated; reconstruction remains necessary.

## Older campaigns

Save format is **51**; balance format is **16**.

- Active campaigns with Science enabled now enable Race-specific instead.
- Unfinished Ascension Theory refunds its invested RP. Completed theory in an
  unfinished campaign refunds its cost in the campaign's loaded balance profile.
- Built gates refund their profile Resource cost. Queued gates refund paid
  Resources and legacy credits. Gates and orders are removed from live worlds
  and stale survey records. Unspent work is not refunded.
- Completed science victories, including draws, remain historical snapshots.
  They can be viewed and saved again; gate victory does not return to active play.
- Other victory options, ordinary technology choices, fleets, colonies and
  Wanderer discoveries retain their normal migrations.
- New legacy history starts at migration. Past raid trophies, accession consent
  and maturity are not fabricated retrospectively.
- Balance profiles acquire the new installation defaults and retain custom values.

The [original proposals](race-victory-proposals.md) are a design archive.
This implementation uses ordinary production, scouting, diplomacy and population.
Physical trophy cargo, construction convoys, dispute-resolution controls and
bespoke multi-step quest chains remain future ideas.
