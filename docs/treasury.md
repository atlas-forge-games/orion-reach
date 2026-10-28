# Debt interest and bankruptcy — v0.84.0

Every completed turn charges 10% of an empire's opening negative balance,
rounded up to a whole credit. Positive and zero balances cost nothing.
The game snapshots the charge before AI actions, then includes it once in the
ordinary treasury settlement. Income, upkeep and this charge determine the
new balance. An End Turn interrupted for combat does not charge interest.

| Opening credits | Other net income | Interest | Closing credits |
| ---: | ---: | ---: | ---: |
| 1,000 | −100 | 0 | 900 |
| −1,000 | +25 | 100 | −1,075 |
| −1 | +2 | 1 | 0 |
| 0 | −25 | 0 | −25 |
| −9,500 | +5 | 950 | −10,445: bankruptcy |

New debt starts accruing interest on the following turn. Unpaid interest is
part of the next opening debt, so it compounds. The displayed net income and
AI affordability calculations include interest; income is not charged twice.

## Bankruptcy

At −10,000 CR or below, the player receives a bankruptcy defeat. This rule is
compulsory, including single-empire games and campaigns with all optional
victory goals disabled. Bankruptcy takes priority over earning a victory in
the same turn, and prevents a new battle from postponing the defeat. Further
campaign orders and End Turn are blocked by the existing terminal-game rules.

Bankrupt AI empires abandon their colonies, fleets and mobile homes. Existing
defeat cleanup removes their outposts, stations and agreements. Their final
treasury remains recorded and no longer accrues interest. Conquest can award
victory to the last surviving empire if enabled. An Observer has no treasury
obligations and cannot personally go bankrupt. Rival collapse messages obey
the existing contact visibility rules.

## Interface

The galaxy credit card shows debt in red, the interest cost, and a warning when
the current projection reaches the bankruptcy limit next turn. The Empire
overview separately lists upkeep and interest so its budget arithmetic agrees
with net income. It also shows the projected treasury and the bankruptcy limit.
Objectives and the encyclopedia explain the compulsory rule. End-turn alerts
state the actual charge, and the result screen identifies bankruptcy as defeat.

## Compatibility

Install this incremental update over v0.83.4. Save format 60 accepts the new
bankruptcy result and keeps the same underlying campaign fields. Older saves
are migrated in memory without rewriting their source file. Below the limit,
their existing debt is retained and begins paying interest next turn. Ongoing
older campaigns already at or below −10,000 CR become bankrupt on loading when
no battle is pending; otherwise normal result checking applies after combat.
Previously completed campaigns retain their recorded outcome, including after
saving again. Final bankruptcy saves and autosaves can be loaded normally.

## Validation

All 15 new tests pass. They cover integer rounding, compound interest, zero
and positive balances, first-turn debt, opening-balance snapshots before AI
actions, AI forecasts and settlement, interrupted turns, the exact inclusive
limit, disabled victory options, bankruptcy before new combat, order blocking,
AI elimination, mobile homes, Observer games, repeated result checks, old-save
migration, immutable completed results, result validation, budget UI and the
actual End Turn / defeat / autosave flow.

The additional 39 economy, ship-maintenance, HUD and victory checks produced
33 passes and the same six failures reproduced against untouched v0.83.4:

- `test_empire.EmpireInterfaceTests.test_turn_completion_refreshes_filters_and_autosaves`
- `test_empire.EmpireReportTests.test_filters_and_numerical_sorts_include_only_settlements`
- `test_empire.EmpireReportTests.test_reports_do_not_modify_saves_and_refresh_after_completion`
- `test_empire.EmpireReportTests.test_totals_cover_all_colonies_and_reserved_slots`
- `test_victory.VictorySaveTests.test_legacy_finale_continues_identically_after_saving`
- `test_victory.VictorySaveTests.test_v8_upgrade_preserves_in_flight_ships_damaged_combat_and_research`

The first five hit an existing `BuildingSpec.growth_bonus` error. The sixth
fails an existing v8 ship-save fixture validation. No new failure was found.
The full unrelated gameplay suite was not run. Actual budget, warning and
defeat captures were visually inspected, and changed Python files compile.

Run the new checks from the project root:

```text
python -m unittest discover -s tests -p test_treasury.py
```

Recreate the captures with `python tools/preview_treasury.py`.
