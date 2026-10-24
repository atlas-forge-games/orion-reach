# v0.81 validation

Environment: Python 3.12, pygame-ce 2.5.8, SDL dummy video/audio for headless tests.
The actual App was also rendered at its native 1440×900 canvas size.

## Targeted regression checks

Command:

```sh
python -m pytest -q \
  tests/test_gas_stations.py tests/test_gas_giants.py tests/test_ai.py \
  tests/test_outposts.py tests/test_megastructures.py tests/test_power_plants.py \
  tests/test_empire.py tests/test_galaxy_colors.py tests/test_encyclopedia.py \
  tests/test_performance.py
```

Result: **148 passed, 54 subtests passed**.

The 19 new orbital station tests cover:

- Exact construction charges, remote ship consumption, local crews, single-slot
  enforcement and atomic rejection of invalid orders.
- Deterministic properties, construction discounts and storm trade-offs.
- Two assembly turns, actual banked Credits/research, upkeep and budget equality.
- Finite power allocation across local colonies, backup fuel savings, immediate
  blockade changes, frozen turn dispatch and megastructure coexistence.
- Power for anchored motherships, with travelling homes excluded.
- Construction forecasts that include station assembly without mutating the game.
- Diplomatic protection, bombardment, destruction, damaged-station capture,
  occupation ship consumption and shared bombardment actions.
- Local intelligence, stored surveys, dismantling's final dispatch and save/load
  round trips; old campaigns retain their existing worlds.
- Invalid station kinds, owners, hull values, future dates and non-gas locations.
- AI investment, preservation of remote refuelling orders and defeated empires.
- Actual UI choices, the confirmation action, disabled surface settlement and
  disabled orders from stale surveys.

## Visual checks

Rendered and inspected the new three-choice station overview and an opposing
station with bombard/capture controls. Also rendered assembly and operating
states. Artwork and text fit their panels at 1440×900. The existing atmospheric
landscape and detailed module artwork are reused. Disabled Colonize and Surface
outpost controls preserve the gas-giant settlement restriction.

## Existing test issues

The reconstructed, unmodified v0.80 baseline has **24 failing tests** in its full
suite (1,359 passed). Most involve older save fixtures, absent audio/portrait
assets, or older ship/research expectations. Separate focused runs also expose
order-dependent old scout-price, v9/v14/v25 migration expectations; each was
reproduced against v0.80. These unrelated tests were not rewritten to conceal
baseline failures. The gas-giant save-format assertion now follows SAVE_VERSION.

## Full-suite comparison

Final v0.81 run: **1,378 passed, 1,641 subtests passed, 24 failed**.
The 24 failing test IDs are exactly the same as the unmodified v0.80 baseline;
there are **zero additional full-suite failures**. The final run includes all
19 new station tests and the final AI/forecast changes. Python compilation and
ZIP integrity checks also passed.
