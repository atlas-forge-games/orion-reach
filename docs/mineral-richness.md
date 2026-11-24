# Mineral scarcity — v0.98.3

| Mineral class | Mining multiplier | Ordinary generation chance |
| --- | ---: | ---: |
| Void | ×0 | 40% |
| Poor | ×0.3 | 30% |
| Solid | ×1 | 20% |
| Rich | ×4 | 8% |
| Ultra-rich | ×10 | 2% |

The chance is per ordinary generated world, not a guaranteed galaxy quota.
Weighted selection also covers the first planet of ordinary systems and alien
home-system neighbors. Starting homeworlds remain Solid. The fixed Sol
planets, deliberately valuable guardian rewards and gas-giant conversions keep
their existing mineral classes. Existing worlds are never rerolled on loading.

The expected multiplier for ordinary random worlds is ×0.81. Void and Poor
worlds make up 70% of ordinary planets, concentrating extraction in the rare
Rich and Ultra-rich colonies. Individual galaxies vary.

## Extraction and colony specialization

Mining buildings' base production and all miners' production use the mineral
multiplier. Additional copies of a mine add their base extraction; the worker
bonus still applies once per distinct operating building type. Power shortages,
administrative strain and rounding retain their existing effects.

A zero multiplier means no local mining at all. It also disables the fixed
baseline extraction, flat colony resource bonuses and flat mining research
bonuses. Void describes mineral availability; it does not prohibit settlement.
Other colony outputs and building costs are unchanged. Resources remain shared
across the empire, so Void worlds can build using imports. Backup generators
can still burn imported Resources, making a Void colony's net resource output
negative even though gross extraction is zero. Orbital mining megastructures
are separate from planetary mineral richness.

For example, four miners and one fully powered Mining Complex yield 0, 6, 16,
58 and 142 Resources per turn on Void, Poor, Solid, Rich and Ultra-rich worlds,
respectively, before other bonuses and strain. On nonzero-mineral worlds this is
`2 + floor((2 + 4 × (2 + 1)) × multiplier)`: the existing baseline of 2 is flat.

AI colonies with a zero multiplier assign no miners and do not choose mining
facilities for development. The production breakdown explains zero extraction,
and the encyclopedia and guardian reward details show the active profile's values.

## Balance profiles and saves

Fresh standard games use the table above. The balance editor exposes both the
multiplier and the relative generation weight for every class. Multipliers
accept zero and weights must be nonnegative integers with a positive total.

Solid is the displayed name of the former Average class. Saves and balance
profiles retain the internal `Average` key, so this label change needs no data
migration. Existing version-23 profiles also retain their generation weights.

Balance format 23 adds Void and the generation weights to version-22 profiles.
Existing saved multipliers, including custom ones, are preserved. If an existing
`balance.json` retains the old values, reset its Mineral richness entries before
starting a new game to use the new defaults. Pre-profile saves retain their
historical mineral factors as well.

Campaign save format is 67. Version-66 saves remain readable; their planet
classes and saved balance settings are retained. Versions before v0.98.2
cannot read format-67 saves. This update does not change ships, fitted
equipment, combat or other parts of the saved campaign.

## Focused checks

```bash
python -m pytest tests/test_mineral_richness.py -q
```

These cover real colony output for every class, Void bonuses and fuel use,
construction with shared Resources, generated mineral frequencies, all random
generation paths, save continuity, guardian rewards, AI behavior and editor
validation. Existing mining and repeated-building regressions also cover the
new multipliers and whole-unit rounding.
