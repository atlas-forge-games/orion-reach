# Equipment improvements — v0.98.4

## Discovery and improvement

Open Research and choose **New technologies** or **Improve existing**. Discovery
keeps the existing field/tier rules. Improvements refine individual unlocked
equipment types, so Laser cannon improvements do not improve Pulse beams or
torpedoes. Each empire has its own levels.

Both activities spend the same research points and share one active project.
Switching transfers all invested RP to the new project. Any excess after
completion stays in the empire's research bank. A partly researched improvement
has no effect until it finishes. Choose the next level manually when ready;
repeated levels do not start automatically.

Improving equipment does not count as a new discovery, advance a research tier,
recover excluded choices or satisfy a discovery-based victory requirement.
Improvements remain available after the discovery tree is exhausted.

## Eligible equipment and tracks

Only unlocked equipment appears. Basic equipment without a research requirement
is available from the beginning. Fitting still requires a compatible hull.

| Equipment | Performance track | Manufacturing track |
| --- | --- | --- |
| Direct-damage beam weapons | More damage per shot | Lower module Resources and work |
| Direct-damage torpedoes | More damage per hit | Lower module Resources and work |
| Ship shield modules | More shield capacity | Lower module Resources and work |
| Armor modules | More added hull points | Lower module Resources and work |

The two tracks progress independently for every equipment type. This release
does not add improvements for buildings, engines, drone bays or point defense.
Refinements change the fitted module's values; they do not alter range, accuracy,
torpedo speed, shield regeneration, the hull's base statistics or unrelated
equipment. Existing combat modifiers and defenses still apply.

## Diminishing gains and research prices

The first performance level adds 10% of the module's original performance; the
first manufacturing level removes 6% of its original Resources and work. Each
later level contributes 70% of the preceding level's gain. Gains add against
the original value rather than multiplying the already improved value.

For completed level `n`, the cumulative benefit is:

```text
performance_bonus(n) = 0.10 × (1 − 0.70^n) / (1 − 0.70)
manufacturing_saving(n) = 0.06 × (1 − 0.70^n) / (1 − 0.70)
```

| Completed level | Total performance bonus | Total manufacturing saving | Research cost for this level, if base is 100 RP |
| ---: | ---: | ---: | ---: |
| 0 | 0% | 0% | — |
| 1 | 10% | 6% | 100 RP |
| 2 | 17% | 10.2% | 160 RP |
| 3 | 21.9% | 13.14% | 256 RP |
| 4 | 25.33% | 15.198% | 410 RP |
| 5 | 27.731% | 16.6386% | 655 RP |

Performance approaches a +33⅓% bonus; manufacturing approaches a 20% saving.
Research for level `n` costs `round(base_cost × 1.60^(n−1))`, rounding halves up.
The base cost is the larger of 100 RP and 25% of the equipment's unlock
technology cost, rounded up. Equipment without an unlock technology starts at
100 RP. Each track has its own level and therefore its own next research price.
Imported/save-file levels are bounded at 100, well beyond normal research budgets.

The game uses whole-point combat statistics. Performance is applied to a fitted
module's hull-scaled value and then rounded; a small weapon can therefore need
several levels before its displayed damage rises again. The screen shows the
percentage and rounded base-module result before research starts.

Manufacturing savings apply only to the improved modules' contributions, not
the whole ship. Fractional savings from all fitted modules are combined before
rounding the total Resources or work. Individual module descriptions round their
reference prices separately, so summing those displayed prices can differ
slightly from the actual ship total. Existing empire-wide ship discounts still
apply through the usual construction rules.

## Existing ships, designs and construction

Completing a performance level updates that empire's matching fitted equipment
on existing ships, saved player blueprints and ships already in construction.
No manual refit is needed. Armor increases maximum and current hull by the same
amount, preserving the ship's existing absolute damage.

Manufacturing levels update blueprint prices and new ship orders. Previously
queued orders retain their original Resources paid, required construction work,
progress and refund terms, including when a performance improvement completes
during construction. No retroactive resource refund is issued.

The designer uses current improvement levels for module descriptions, fitted
statistics and new-order prices. Upgrades are equipment-specific: a larger hull
uses its normal equipment scaling, and improving one beam type does not upgrade
every beam. Special inherent weapons without fitted modules are outside this
system.

## AI and campaign compatibility

AI empires pay the same RP prices and improve equipment currently fitted to
their fleets. They consider approximately one refinement per three discoveries,
with urgent fuel-range research retaining priority. Once discoveries run out,
they can continue refining their fitted equipment. They receive no free levels.

Older saves load with empty improvement levels and no active improvement. Their
existing research progress, discoveries, blueprint layouts, construction orders
and saved balance values are preserved. New saves include per-empire levels,
the active improvement, shared progress and per-design equipment snapshots.
Malformed levels, unavailable equipment and simultaneous active discovery and
improvement projects are rejected when loading.

Campaign save format is 68. Newly saved campaigns require v0.98.4 or later;
loading an older save does not rewrite the original file. Balance profile format
remains 23. The improvement formulas in this release are fixed; equipment values
and discovery costs continue to use the campaign's saved balance profile.

## Verification

Run `python -m pytest tests/test_equipment_improvements.py -q` for the 13 focused
checks. The release also exercised an actual v0.98.3 save and inspected the two
research screens and designer. See the root README for the selected regression
results and known pre-existing failures.
