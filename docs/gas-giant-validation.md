# Gas giant validation — v0.79

## Results

Python 3.12 / pygame-ce 2.5.8, with SDL dummy video and audio.

| Run | Tests | Passed | Failures | Errors |
| --- | ---: | ---: | ---: | ---: |
| Unchanged v0.78 baseline, previously completed full run | 1,368 | 1,345 | 19 | 4 |
| v0.79 full run, before updating four older expectations | 1,379 | 1,352 | 23 | 4 |
| Final focused run after those test updates | 32 | 32 | 0 | 0 |

All 11 new gas-giant tests pass. The full run took 273.391 seconds. It found the
same 23 failing baseline test identities plus four assertions that assumed every
planet could host a colony or buried tomb, or should show a guardian warning.
Those four tests were updated to distinguish gas giants and passed in the final
32-test run. The entire suite was not rerun after these test-only updates.
The unchanged baseline failures remain unresolved; this is not a clean full-suite
pass.

The initial focused run of gas giants, species environments and landscape assets
also passed all 28 tests. A separate broader guardian-class run exposed two
order-dependent legacy ship-balance expectations (scout hull 8 versus 20, and
frigate attack thresholds); both were reproduced against unchanged v0.78.

## What is checked

- Deterministic, idempotent outer-orbit generation across multiple seeds, with
  no changes to existing terrestrial worlds, homes, star coordinates or special
  sites, and no more than eight worlds per system.
- Settlement exclusion for all 13 races, including custom habitability and
  technology flags; zero population/building capacity and growth efficiency.
- Actual colony and outpost orders fail without consuming ships or mutating
  the campaign. AI target lists exclude gas giants.
- Existing mobile habitats retain their separate capacity and growth rules.
- Save round trips, stale surveys and turn continuation preserve gas giants.
- v55/profile19 migration preserves old galaxies, custom preferences and source
  bytes while adding the new profile metadata.
- Save validation rejects forged gas-giant colonies, outposts and tomb records;
  the Remnant awakening path cannot create a colony there.
- The actual planet overview disables settlement and omits worker/building
  controls without changing campaign state.
- Larger globe hit areas contain their full discs and remain separate for
  two-, four-, six- and eight-world layouts.
- All nine overview images load at native resolution; cropping, shared caches
  and missing/corrupt-image fallback tests pass.

The updated existing tests cover guardian prize worlds, colony-only food/capacity
fixtures, Lithar's solid-surface settlement ability and terrestrial tomb eligibility.

## Visual review and asset integrity

Rendered and inspected the actual generated system and gas-giant overview via
`tools/preview_gas_giants.py`. The atmosphere has no ground/buildings, and the
larger banded globe, labels and disabled controls fit the existing interface.

The original built-in generated image was copied unchanged to
`assets/planet_surfaces/gas-giant-v1.png`: 2170 × 725 RGB PNG, 2,662,625 bytes,
SHA-256 `478e405e394b99fae1a334687d84eeb73293612b1b329fb8d6bbb0b6e9850f92`.
Its exact prompt is included in `generation-prompts.json` beside the asset.

All changed Python modules compile. The incremental archive is compared against
the v0.78 baseline, CRC-checked, and each stored file is byte-compared with its
source. Saves, settings, custom balance files, caches, logs and QA screenshots
are excluded.

## Reproduction

Run from the project root:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 \
  PYTHONPATH=.:tests python3 -m unittest discover -s tests -v

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 \
  PYTHONPATH=.:tests python3 -m unittest test_gas_giants test_environments \
  test_planet_surface_art \
  test_monsters.GuardianExpansionTests.test_leviathan_protects_three_distinct_worlds_that_can_all_be_settled \
  test_population.PopulationRulesTests.test_limits_and_food_follow_size_and_biome_without_mutation \
  test_races.RaceRulesTests.test_lithar_settle_solid_surface_biomes_and_keep_growing_beyond_the_old_limit \
  test_tomb_worlds.GenerationTests.test_solid_worlds_including_homes_harsh_worlds_and_guardian_prizes_are_eligible -v

python3 tools/preview_gas_giants.py
```

The 23 unchanged full-suite baseline failures are listed in
[the v0.78 validation report](planet-environment-validation.md).
