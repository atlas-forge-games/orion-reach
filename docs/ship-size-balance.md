# Ship size balance — v0.76

This is a physics-inspired game model. Size, material prices, component
performance and the conversion to credits are explicit design assumptions;
they are not claims about real spacecraft engineering. Once chosen, the same
assumptions determine standard ships and custom designs.

## Inputs and formulas

`orion/ship_scaling.py` defines the assumptions and preset equipment.
The balance editor exposes sizes under **Ship sizes** and coefficients under
**Global rules → Ship scaling**. A profile stores these inputs alongside the
calculated catalogue, so a saved campaign remains reproducible.

- Size indices: Scout 1, Frigate 2, Destroyer 6, Cruiser 12, Carrier 20,
  Battleship 25, Titan 80. They represent usable displacement, not board cells.
- Base hull: `20 × size`.
- Bare frame Resources: `50 × size^1.1`, rounded to the nearest 10.
- Bare frame work: `ceil(frame Resources × 0.6)`.
- Equipment scale: `size / 2`, relative to a frigate-sized mount. Each module
  occupies one category slot. Damage, armor hull bonuses, shields, regeneration,
  repair reserves, component Resources and component work scale by this factor,
  rounding each component value upward. Range, movement bonuses, accuracy and
  interception percentages do not scale.
- Total Resources/work: frame plus every installed component. Existing racial
  discounts and industrial bonuses still apply through the ordinary economy.
- Maintenance: `ceil(size × 1 credit)` per strategic turn, for standard ships
  and custom ships of that class. This is a class operating budget; extra armor
  or weapons already consume its fixed fitting capacity.
- Dockyard repair: `max(4, ceil(maximum hull × 5%))` each eligible peaceful turn.
  The ordinary repair location and safety requirements still apply.

Armor adds structural endurance in the existing game rules. This update does
not introduce a separate armor-thickness or penetration simulation.

## Standard equipment and prices

| Class | Bare frame RES | Equipped RES | Work | Hull | Volley | CR/turn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Scout | 50 | 50 | 30 | 20 | 0 | 1 |
| Frigate | 110 | 134 | 82 | 40 | 10 | 2 |
| Destroyer | 360 | 600 | 372 | 120 | 60 | 6 |
| Cruiser | 770 | 1,118 | 690 | 240 | 120 | 12 |
| Carrier | 1,350 | 2,190 | 1,330 | 400 | 50 | 20 |
| Battleship | 1,720 | 2,720 | 1,682 | 500 | 376 | 25 |
| Titan | 6,200 | 11,320 | 7,080 | 1,600 | 1,200 | 80 |

- Frigate: two lasers.
- Destroyer: two torpedo launchers, point defense and an escort array.
- Cruiser: two lasers, a torpedo launcher and point defense.
- Carrier: a laser, point defense and two drone bays.
- Battleship: two lasers, two torpedo launchers and point defense.
- Titan: two lasers, two torpedo launchers, two point-defense modules and a
  flag bridge. The bridge's cost is included.

The Scout is unarmed. Colony ships, outpost ships, troop transports and mobile
mothership habitats retain their prior mission-specific construction and upkeep
budgets. Their existing tactical footprints are unchanged.

Standard warships now carry immutable `ShipDesign` snapshots, just like AI and
custom designs. Their nominal attack is the sum of their fitted weapon volleys.
Their construction requires the hull and equipment research. Captured or awarded
standard ships remain usable without granting their owner new technology.
Research no longer swaps a standard warship's installed laser for a quantum
weapon for free; choose advanced equipment in the designer. AI blueprints keep
choosing equipment from the AI empire's researched technologies.

## Attack and carriers

Module damage is total damage per volley. Pulse and MIRV module values already
include all shots; do not multiply their module damage by the shot count again.
The designer's sustained figure is the sum of `volley / (1 + reload turns)`.
Actual expected damage is target-specific: the tactical engine applies range,
line of sight, tracking, hit chance, shields, interception and weapon effects.
Beams still cannot pass through other ships; projectiles retain travel time.

A carrier bay retains two active tactical markers and four launches per battle.
Each marker now represents a wing scaled by the carrier's mount factor (10 by
default), avoiding dozens of additional map units. Assault wings have 60 hull
and 30 damage; interceptor wings have 60 hull and 20 damage; bomber wings have
60 hull and 50 damage, before their existing target-specific multipliers.
Launching still spends the carrier's weapon action. Wings are lost with their
carrier. The carrier's direct volley in the table excludes launched wings.

Capital ships require a developed industrial and credit economy. The AI checks
the actual fitted construction price and deducts both active and queued ship
maintenance from its available operating budget.

## Balance editing and compatibility

Balance schema 17 adds the size inputs and an `ENABLED` switch. Save format
remains 53 because ship and battle records already support equipment snapshots.

For new default campaigns, sizes and components recalculate the corresponding
ship fields. The editor prevents direct changes to those calculated fields and
supports undo/redo of the entire recalculation. Disable **Ship scaling → Enabled**
to use manually specified ship and hull statistics.

Profiles from schema 16 or earlier load with scaling disabled and keep their
original prices, hulls, mount scales and upkeep. Saves predating embedded balance
profiles use the historical ship catalogue. Neither paid construction nor active
battles are repriced. Merely opening an old save does not rewrite its file.

To opt an existing custom `balance.json` into the new system, enable ship scaling
in the balance editor, save, and start a **new campaign**. Other custom economy,
research and race settings are preserved. This update does not migrate an
in-progress campaign to the new economy.

Simulator scenarios use the currently loaded balance and rebuild their ships at
launch; replaying an old scenario under the new profile therefore uses new stats.
Campaign saves keep their own profile.

## Validation

`tests/test_ship_scaling.py` covers the scale table, equivalent standard/custom
fits, live mixed beam/torpedo damage, sustained fire and reloads, preset support
modules, AI budgets, construction research, editor recalculation, invalid input,
partial paid orders, saved damage, older profile compatibility, carrier wings,
mid-battle saves, repairs and every simulator preset's completion.

Historical module-scale and aura fixtures explicitly retain their original
balance where they assert the old numbers. Other balance, economy, simulator
and presentation checks exercise the updated integration.
