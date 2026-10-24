# Population display and growth inspection

Version 0.81.2 replaces the small worker-count heading in the planet overview
with a population line, for example:

**8 billion (+100 mil / turn) / 16 billion max**

Right-click anywhere on that line to open the population explanation. A normal
click or keyboard activation also works. Esc, a second right-click or Close
dismisses it and restores the previous focus. Opening the explanation does not
change worker selection, production orders or game state, and does not save.

## Meaning of the numbers

Population is the current whole-billion civilian count. The signed millions
show the existing growth progress earned per turn; the simulation adds one
worker when a full billion has accumulated. The explanation shows both the
accumulated progress and the number of turns until the next billion at the
current rate. These figures do not change the growth model or round timing.

The maximum includes world size, Gaia capacity and applicable local capacity
traits. Mothership habitats retain their fixed 50-billion limit. Slaves are
listed separately, because they contribute workers and consume food but do not
participate in native growth or its population limit.

## Growth calculation

The displayed rate comes from the same `PopulationReport` used by turn
resolution. The explanation follows that report through its active growth
method, traits, environmental suitability and capacity checks:

- Organic growth uses food surplus, the normal or Gaia growth cap, general
  and lush-world traits, and resident species' planet suitability.
- Synthetic growth uses the industry's actual assembly reservation and its
  cap, followed by environmental suitability.
- Passive growth uses its configured rate, followed by suitability.
- Mixed populations use the same local physiology bonuses and weighted
  environmental suitability as the simulation.
- Full worlds show zero growth. Ordinary food shortages pause food-based
  growth without removing existing inhabitants or accumulated progress.
- Starving Skirr colonies show a loss of 1,000 million per turn, stopping at
  the simulation's one-billion minimum; starvation resets growth progress.

The food details account for farmers, active facilities, natural/native food,
local bonuses, consumption and administrative strain. Disabled or unpowered
food facilities are identified. The existing Food output explanation remains
available for its full production calculation.

## Visibility and compatibility

Old surveys show the last-observed population and mark current growth and
capacity unknown. Their explanation does not query current hidden population,
food or bonuses. Gas giants have no population control and remain uncolonizable.
Habitat inspection uses the selected mothership's inhabitants.

No simulation rules, save schema, balance profile, dependencies or artwork
change. Install the incremental package over v0.81.1; save format remains 57
and balance profile version remains 20.

## Validation

`tests/test_population_info.py` compares displayed growth with actual population
advancement for ordinary growth, harsh environments, Lithar, Xenonflora, Nexus
and Aetheri. It also covers capacity, food shortages, Skirr starvation, disabled
farms, mixed populations, slaves and empty worlds. UI checks exercise a scaled
viewport, preserved game state and worker selection, refreshed values, stale
surveys, habitats, gas giants, keyboard access, pagination and focus restoration.

The focused verification run passed **53 tests and 20 subtests**, covering the
new population inspector together with population rules, environmental effects,
building information, production breakdowns, planet overview controls and
habitat modules. Compilation passed. Rendered overviews and explanations for
Terrans, Nexus, Skirr starvation and Wanderer habitats were also checked.
