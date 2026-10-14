# Diplomatic alignment — v0.61

Each civilization has five values, from −2 to +2. All axes have equal weight.

| Axis | −2 | +2 |
| --- | --- | --- |
| Autonomy | Collective control | Independence |
| Openness | Isolation | Exchange |
| Restraint | Coercion | Coexistence |
| Innovation | Preservation | Experimentation |
| Stewardship | Exploitation | Living worlds |

## Calculation

Let D be the sum of absolute differences across the five axes. The fixed
reference M = 402/55 is the mean difference across the 55 distinct pairs in the
original 11-race roster. With modifier cap C = 25:

`alignment = round(clamp(C × (M − D) / M, −C, +C))`

Rounding uses nearest whole points, with half points away from zero. The standard
uncapped, unrounded scores average exactly zero across distinct race pairs.
Campaign roster changes and eliminated empires do not change M. Mirror empires
have alignment +25, although the matrix diagonal is displayed as a dash.

## Profiles

| Race | Autonomy | Openness | Restraint | Innovation | Stewardship |
| --- | ---: | ---: | ---: | ---: | ---: |
| Terrans | +1 | +2 | +1 | +1 | +0 |
| Kharuun | +0 | +1 | +1 | +1 | -1 |
| Aelari | +1 | +1 | +2 | +2 | +1 |
| Lithar | +0 | -1 | +1 | -1 | +0 |
| Varkesh | -2 | -1 | -2 | +0 | -2 |
| Wanderers | +2 | +2 | +1 | +1 | +0 |
| Xenonflora | -1 | +0 | +2 | +1 | +2 |
| Nexus | -2 | +0 | +0 | +2 | -1 |
| Aetheri | +1 | +1 | +2 | +2 | +1 |
| The Concord | -2 | +1 | -2 | +2 | +0 |
| The Remnant | +0 | -2 | +0 | -1 | +1 |

## Standard matrix

| Race | Terrans | Kharuun | Aelari | Lithar | Varkesh | Wanderers | Xenonflora | Nexus | Aetheri | The Concord | The Remnant |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Terrans | — | +15 | +11 | +4 | -16 | +22 | +1 | -2 | +11 | -2 | -6 |
| Kharuun | +15 | — | +8 | +8 | -6 | +11 | +4 | +8 | +8 | +1 | -2 |
| Aelari | +11 | +8 | — | -2 | -23 | +8 | +8 | -2 | +25 | -2 | -6 |
| Lithar | +4 | +8 | -2 | — | -2 | +1 | +1 | -2 | -2 | -9 | +15 |
| Varkesh | -16 | -6 | -23 | -2 | — | -19 | -13 | +4 | -23 | +4 | -6 |
| Wanderers | +22 | +11 | +8 | +1 | -19 | — | -2 | -6 | +8 | -6 | -9 |
| Xenonflora | +1 | +4 | +8 | +1 | -13 | -2 | — | +1 | +8 | -6 | -2 |
| Nexus | -2 | +8 | -2 | -2 | +4 | -6 | +1 | — | -2 | +11 | -6 |
| Aetheri | +11 | +8 | +25 | -2 | -23 | +8 | +8 | -2 | — | -2 | -6 |
| The Concord | -2 | +1 | -2 | -9 | +4 | -6 | -6 | +11 | -2 | — | -13 |
| The Remnant | -6 | -2 | -6 | +15 | -6 | -9 | -2 | -6 | -6 | -13 | — |

## Relationship history and persistence

The existing `DiplomacyState.relations` stores the bounded overall relation score.
A newly registered pair begins at its alignment; subsequent diplomatic actions
change that total. The visible history term is `relations − alignment`, so the
modifier cannot accidentally be added again at first contact, each turn or load.
History can exceed ±100 when compensating for alignment at a total-score boundary.
Existing save totals are preserved exactly; their history includes the legacy
starting baseline. This requires no change to save format 42.

Treaty acceptance, treaty cancellation, council votes, opportunistic conquest,
hostile interception and relationship labels already read the same overall score.
The default alignment alone never reaches the below−30 combat threshold.
Passive forgiveness restores minor historical grievances toward the pair's
alignment; it does not turn ideological friction into increasing friendship.
Concord still has no passive forgiveness. Treaties continue to build trust.

Balance profile version 8 adds Diplomatic values and the reference/cap controls.
Older profiles upgrade with standard alignment data, preserving their other
settings. Custom profiles are saved with campaigns. Editing the current profile
never silently recentres the other pairs.

The full matrix describes race values, not which empires exist in the campaign.
A bilateral values/history comparison is restricted to confirmed contacts.
New third-party reactions, asymmetric attitudes and new treaty types are outside
this first implementation.
