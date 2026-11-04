# All civilizations — v0.88.0

New Game → Galaxy options now offers **All civilizations** alongside individual
rival counts. There are 13 competing civilizations. A normal campaign supports
0–12 rivals; Observer mode supports 2–13 computer empires. All selects every race
once and stays selected if the player switches between Observer and a playable
race. A numeric selection is clamped when leaving Observer mode.

## Generation and saves

- The full roster works on Compact, Standard and Expansive galaxies. Starting
  empires retain independent economies, exploration, research, fleets and
  bilateral diplomacy. Each receives a different home system.
- The existing seeded race shuffle and preference for separated homes remain.
  If a crowded seed runs out of systems containing planets, an empty unclaimed
  system receives a generated homeworld. No stars are moved.
- Black-hole generation protects every starting home, including Wanderers whose
  population lives aboard a mothership rather than on the starting planet.
- Existing empire IDs and the first seven colors remain unchanged. Extra IDs
  and colors cover the full roster and a reserve slot for an awakened Remnant.
- Save format **61** accepts the extended roster. Earlier formats retain their
  original roster validation, including the special sixth Remnant empire. Old
  saves load without adding civilizations; saves written by this release need
  v0.88.0 or later.
- The programmatic `new_game(rival_count="all")` option resolves to 12 rivals
  for a player or 13 for an Observer. Numeric limits and invalid inputs are
  validated before generation. An explicitly mirrored player race is rejected
  with `"all"`, while the pre-existing numeric mirror-race API remains available.

Compact starts are more crowded with the full roster. Because the Council forms
when half the galaxy is settled, it can convene early on that map size; the
formation rule is unchanged.

## Reports and navigation

Growing lists use the shared pagination helper without reducing text or row
sizes: Council delegates (six per page), statistics legends (six), known rival
objectives (ten), and coalition targets (five). Arrows and visible-range counters
show the remaining entries. Statistics visibility choices persist across pages,
and all selected empire lines remain plotted regardless of the legend page.
Coalition details name the selected target even when its button is on another
page. Existing contact selectors and Observer reports already support paging.

The shared **Galaxy map / End turn** footer, turn guards, fog-of-war visibility,
and 100–175% interface scaling remain in place.

## Validation

The 12 new tests in `tests/test_all_civilizations.py` cover:

- Every playable race and Observer, on all three galaxy sizes, with all 13
  civilizations and save round trips.
- Seed reproducibility, all-versus-numeric equivalence, distinct homes/colors,
  bilateral diplomacy and a deliberately sparse galaxy needing new homeworlds.
- Real save files, format-60 compatibility, and deterministic continuation of
  all 13 AI empires for 12 turns after loading.
- Real mouse activation of setup, last-page votes, graph toggles and coalition
  targets, including a 1080×720 window at 175% interface scale.

Existing multi-empire count tests now exercise 0–12 rivals at every galaxy size.
Observer tests include 13 empires. Statistics tests follow paged legends and use
the current native-rendering coordinate conversion and save-version constant.
Navigation and readability tests also render all 68 existing screen/dialog
fixtures at their normal and enlarged sizes. Sixteen full-roster previews were
rendered and validated as complete images. Representative setup, Council,
statistics, objectives and diplomacy views were visually inspected; three
captures are included.

| Regression group | Passed | Existing failures |
| --- | ---: | ---: |
| Full-roster, multiple empires, Observer, tomb worlds, black holes, Council, diplomacy, statistics | 146 / 148 | 2 |
| Full-roster, statistics, navigation, global readability, races, home systems | 63 / 64 | 1 |

These groups overlap. Python compilation and `git diff --check` also pass.

Three unrelated failures were reproduced in the unmodified v0.87.0 snapshot:

- `ObserverRulesTests.test_v039_saves_remain_normal_player_campaigns`: old-format
  fixture compares stored surface layout with a migrated empty layout.
- `SaveTests.test_v21_load_keeps_existing_campaign_without_reseeding_tombs`: the
  same pre-existing surface-layout expectation in a legacy tomb-world save.
- `RaceRulesTests.test_varkesh_discount_stacks_with_research_and_applies_to_designs`:
  an obsolete frigate price expectation (48 instead of the current 108).

These are not new failures from the larger roster. Production behavior covered
by those old fixtures was not changed by this update.

Run the focused tests from the repository root:

```bash
PYTHONPATH=.:tests python3 -m unittest test_all_civilizations test_statistics test_campaign_navigation test_global_readability
```

Reproduce the full-roster captures without opening player saves:

```bash
python tools/preview_all_civilizations.py --output screenshots/all-civilizations
```

No new game dependency is required. No commit or push was performed.
