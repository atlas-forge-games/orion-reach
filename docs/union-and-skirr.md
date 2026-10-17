# The Serevan Union and Skirr Swarm — v0.69

## Serevan Union

The Union offers prosperity and protection to many species. Its colonies retain
their civilian species after voluntary accession or conquest. Local physiology
and productivity bonuses are population-weighted: for example, a Lithar colony
keeps its population capacity, lower food consumption and slower growth.
Military technology, settlement permissions and diplomatic bonuses belong to
the governing empire. The Union receives +2 CR from trade pacts and +1 RP from
research agreements, in addition to ordinary agreement yields.

Open **Diplomacy → Populations & accession**, or the same button on a colony,
to inspect populations, start or withdraw outreach, and protect your colonies.

### Voluntary accession

- Opening outreach costs **30 CR**. Each active mission costs **5 CR per turn**,
  included in the Empire budget and AI budget projections. Each Union can
  operate **two missions**; a colony can host only one mission.
- The colony must be inhabited, foreign, within logistical range and currently
  visible. First contact, peace and non-negative relations are required.
- Capitals, mobile habitats, and colonies governed by the Dominion of One,
  Nexus or Skirr cannot vote to join through outreach.
- A colony is dissatisfied at **20% administrative strain** or any food
  shortage. Without either, support falls by 8 points per turn. War, negative
  relations or loss of visibility/range also reduce support by 8.
- Base support ranges from 4 to 12 points according to strain. Food shortages add
  3, friendship adds 2 and trade adds 1. Broken promises reduce the rate. A
  negative Union net income reduces support by 4 instead; a negative treasury
  reduces it by 8. The panel shows the current reason and rate.
- At **100% support**, ownership changes without combat. Civilian species,
  population, ordinary buildings and construction remain. Garrisons disband;
  an Ascension Gate and any queued gate are removed. Normal integration strain
  applies and relations with the former government fall by 12.
- Both parties receive news. The former owner can improve food and
  administration, or pay **40 CR for eight completed turns of civic investment**,
  reducing accession support by 12 per turn. AI empires use these defenses.

Withdrawing ends upkeep immediately and does not refund the opening cost.
If another force takes the target, the mission ends during the next turn.
An AI Union checks for promising opportunities every fourth turn.

## Skirr Swarm

The Skirr see other civilizations as obstacles to their broods. They have:

| Trait | Effect |
| --- | --- |
| Rapid breeding | +200% base population growth, giving three times ordinary growth at the same food surplus |
| Hunger | +50% food consumption; shortages cost 1 B population per turn, down to a minimum of 1 B |
| Colonization | Colony ships cost 55% fewer resources and receive double construction work; new colonies start at 2 B |
| Fleet production | Other ships cost 15% fewer resources |
| Research | Colony research −25% |
| Replacement | Fed Skirr colonies replace 1 B non-Skirr civilians on every even-numbered turn |
| Diplomacy | No trade, research, friendship, non-aggression or coalition agreements |

At default prices, a colony ship costs **360 resources** rather than 800.
Replacement leaves total population unchanged; normal births add Skirr.
Liberation stops forced replacement immediately. The AI builds larger fleets,
favors expansion and can attack neutral neighbors when its military position
supports an invasion. It still checks fuel range, food and affordability.

## Dominion of One and portraits

The existing `concord` identifier is retained for save compatibility. Its visible
name is **Dominion of One**, with conquest-focused diplomatic priorities and the
same existing economic and military rules. Default legacy empire names migrate;
custom empire names remain. Civilian species describe biological populations,
not political independence from the collective.

The update uses the supplied Skirr and Nexus portraits and the generated Union
portrait. Existing Kharuun art and identity remain unchanged.

## Saves and existing campaigns

Save format **50** records civilian species, civic protection and missions.
Older campaigns load without creating new empires or changing existing colony
ownership. Species in older saves are inferred from the owner recorded on each
world or dated survey; past conquered species cannot be recovered when the old
save did not record them. Stale surveys retain their historical information.

Balance profiles upgrade to **14**, adding the new race definitions and renaming
the collective while retaining existing custom prices and research settings.
The alignment reference remains fixed, so adding races does not change the
alignment scores between existing races. New random campaigns may have different
opponents for the same seed because the available roster has expanded.

Version 0.68.1 cannot load newly saved format-50 campaigns. Keep an old save if
you want to return to the earlier executable.
