# Species environments and Toxic planets — v0.78

Each species has a growth efficiency for every planet type. **100% means its
usual growth speed**, 150% means one and a half times that speed, and 25% means
one quarter. These are multipliers, not percentage points of population per
turn. They affect food-based growth, Nexus assembly and Aetheri passive growth.

## Default preferences

| Species | Terran | Ocean | Desert | Ice | Barren | Volcanic | Toxic | Gaia |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Terrans | 100% | 90% | 70% | 50% | 40% | 25% | 25% | 125% |
| Kharuun | 100% | 60% | 120% | 90% | 150% | 130% | 60% | 110% |
| Aelari | 100% | 150% | 40% | 50% | 35% | 25% | 25% | 125% |
| Lithar | 100% | 60% | 120% | 110% | 140% | 150% | 85% | 110% |
| Varkesh | 100% | 75% | 75% | 55% | 50% | 60% | 40% | 110% |
| Wanderers | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| Xenonflora | 100% | 110% | 50% | 30% | 25% | 20% | 10% | 150% |
| Nexus | 60% | 50% | 110% | 150% | 130% | 85% | 110% | 75% |
| Aetheri | 100% | 90% | 100% | 60% | 85% | 150% | 100% | 110% |
| Dominion of One | 100% | 90% | 75% | 70% | 55% | 50% | 35% | 125% |
| Serevan Union | 100% | 90% | 70% | 60% | 40% | 30% | 25% | 125% |
| Skirr Swarm | 80% | 70% | 100% | 40% | 60% | 55% | 150% | 100% |
| The Remnant | 100% | 90% | 70% | 65% | 45% | 40% | 30% | 125% |

An unsuitable environment slows growth; it does not by itself kill population
or forbid settlement. Food, capacity and existing colony restrictions still
matter. A rich, large Ice world can remain worthwhile for Terrans even when a
small, poor Terran world would grow faster. Gaia keeps its existing extra food,
capacity and base growth limit, alongside the species multiplier.

## Growth calculation

The game first calculates the existing growth progress per turn, including food
surplus and racial growth bonuses, or the existing assembly/passive-growth rule.
It then applies the environment:

```text
if base growth is zero: environmental growth = 0
otherwise: environmental growth = max(1, floor(base growth × efficiency / 100))
```

The normal threshold of 100 progress per additional billion inhabitants is
unchanged. Full colonies stop growing. Nexus still reserves the same industry
for assembly; environment changes the resulting population progress, not the
industry cost. Aetheri passive growth is affected even though it does not need a
food surplus. Existing Skirr starvation remains in force.

Example with equal food surplus and a base rate of 10: Terrans gain 10 progress
per turn on Terran terrain and 5 on Ice. Their low Ice food production may also
require more farmers. The displayed time to the next population increase uses
the same final rate as turn processing.

## Residents and mixed colonies

Established colonies use their actual resident species, not the identity of the
empire that governs them. Their efficiency is the population-weighted mean,
rounded down. This applies under every government. Half Nexus and half Terran
residents on Ice therefore yield `(150 + 50) / 2 = 100%`.

The multiplier changes as residents migrate, assimilate or are replaced through
existing species mechanics. It does not introduce separate growth queues for
each species. Existing government-specific food and production traits retain
their earlier rules. Mobile habitats always use 100% environment efficiency,
regardless of the planet they orbit or their inhabitants.

## Toxic worlds and native homes

Toxic worlds have 15 generic habitability, zero base food and two food per
farmer before bonuses. Normal colony ships can settle them without a new
technology. Existing restrictions still apply: Varkesh cannot found ordinary
colonies, Wanderers use their habitats, and Barren/Volcanic gates are unchanged.

Most organic species grow poorly on Toxic worlds. Skirr has 150% efficiency and
receives six natural food per Toxic colony, representing usable toxic biota.
This food is weighted by the Skirr share of residents and rounded down: a half
Skirr colony receives three. It is subject to the usual local food-output
reductions and is shown in the production breakdown. Habitats receive no toxic
biota food. Nexus has 110% efficiency on Toxic and still needs no food.

| New civilization | Native homeworld terrain |
| --- | --- |
| Skirr Swarm | Toxic |
| Nexus | Ice |
| Aelari | Ocean |

These native terrain choices apply to player and computer starts, including a
new rival added to a solo game. Existing saved civilizations keep their worlds.
Skirr and Aelari start with enough farmers for a food surplus under default
rules; Nexus retains its foodless starting allocation. Other civilizations keep
their existing home generation.

New galaxies use a separate seeded pass with a 12% Toxic chance per eligible
non-Gaia world outside the player's home system, before rival homes and special
sites are initialized. This does not change star coordinates or shuffle the
other generation RNG streams. Subsequent home and special-site rules can
replace the selected terrain, so the final fraction is not exactly 12%.

The new Toxic landscape is an original 2171 × 724 PNG with a matching globe and
procedural fallback. Buildings remain separate clickable sprites.

## Interface, AI and balance editor

Race selection highlights the best two environments; setup shows native home
terrain. Unsettled world overviews show the player's prospective efficiency.
Colonized overviews and colony management show the residents' actual weighted
efficiency. The encyclopedia includes each species' complete preference row.

AI world quality combines growth efficiency, mineral richness and building
capacity. Its score is `efficiency + 18 × richness index + 3 × building slots`;
richness runs from Poor (0) through Ultra-rich (3). Existing travel, visibility,
fuel, settlement and administration rules still govern eligible destinations
and system choice. The score is used when choosing a world within a system and
when comparing otherwise equivalent destination systems.

The balance editor section **Species / planet growth (%)** exposes every
species/biome multiplier (10–200) and its `toxic_food` bonus (0–30). Settings are
stored with the campaign. Native homeworld choices and the Toxic seeding rate
are generation rules rather than editable balance fields.

## Compatibility

- Save format is 55; balance profile format is 19.
- Older profiles gain the preference table and Toxic biome defaults while
  preserving their previous custom values.
- Loading an existing campaign applies the new growth multipliers but does not
  reseed its galaxy, transform its existing homes or alter current population.
  Future growth and its displayed estimates can therefore change.
- Toxic map generation and native home choices are visible when starting a new
  campaign; adding a new rival initializes that rival's native terrain too.
- Already charted terrain remains valid when a rival is added; stale population
  and ownership information is not revealed by that initialization.
- Loading does not rewrite the original save or balance file. Save explicitly
  to write the upgraded formats.

For verification commands and baseline limitations, see
[planet-environment-validation.md](planet-environment-validation.md).
