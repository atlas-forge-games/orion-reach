# Balance editor

Run `python editor.py` from the folder containing `main.py`. Use the game's
existing Python/Conda environment; the editor uses pygame and the bundled fonts.

## Editing values

1. Choose a catalogue on the left and select an item.
2. Click a value. Type a number or text, toggle an On/Off value, or choose from
   the reference list. Enter applies the value; Escape cancels the current edit.
3. Use the item and field filters to find a setting. The mouse wheel and arrow
   buttons browse pages. Effects appear as individual numeric fields.
4. Review the validation line at the bottom. Save is blocked while a value,
   reference or research layout is invalid. Validation reports the offending field.
5. Save with Ctrl+S. Start a new game to test the saved balance.

The editor includes 259 entries and rule groups across 18 catalogues:

| Catalogue | Examples |
| --- | --- |
| Buildings | Resource/work costs, upkeep, production, worker bonuses, energy, prerequisites |
| Standard ships | Costs, hull, strategic attack rating, tactical movement, drone bays, prerequisites |
| Designer hulls | Hull points, movement, category slots, module size/scale and tracking penalty |
| Ship modules | Base costs, damage/range, armor, shields, interception, repair and movement bonuses |
| Weapons | Damage, range, accuracy, shots, reload, shield effects, interception piercing |
| Races | Economic/population modifiers, starting research, diplomacy, AI priorities and names |
| Technologies | Branch, tier, alternative order, cost override, effects and descriptions |
| Research branches | Names, descriptions and display order |
| Guardians | Hull, movement, weapon, research reward and presentation |
| AI personalities | Diplomatic attitudes and the existing strategic preference parameters |
| Special projects | Ascension Gate cost, work and upkeep |
| Planet sizes | Building slots and population capacity |
| Planet biomes | Food, farmer output and habitability |
| Mineral richness | Output multipliers |
| Global rules | Starting funds/population, trade conversion, movement, mining, growth, defenses, diplomacy, tombs, raids, drones, sensors and council timing |
| Research costs | Shared costs for tiers I–VIII and Ascension |
| Drone roles | Name, weapon and movement |
| Galaxy sizes | Star count for the existing size presets |

Numbers drive the simulation. Descriptions, abilities and reward captions are
editable prose: update them to match your numerical changes. Art and stable IDs
remain attached to their original entities. Special rules such as Varkesh
raiding, drone-bay eligibility and relic mechanics remain implemented in Python.

Every building is limited to one per planet, including queued orders. This is
a fixed game rule. Older profiles retain a `unique` field for save compatibility;
it is hidden in the editor and cannot enable duplicate building orders.
The v0.52.1 standard research costs are four times the v0.52 defaults. Existing
profile files and saved campaigns retain their own prices; use **Research costs**
to change an existing profile, or **Reset all** to restore all current defaults.

Standard ships' **Damage** field is their strategic attack rating/armed flag.
Use **Weapons** to change their tactical shot damage and range. Designer ships
use **Ship modules** for damage/range per fitted module and **Weapons** for shot
count, accuracy, reload and special weapon effects. Standard-ship movement and
designer-hull movement are separate settings.

## Rearranging research

Select **Research tree** to see three branches at a time. Use the arrows or
mouse wheel to browse all nine. Drag a technology onto a slot in another tier
or branch. Occupied slots swap; empty slots receive the technology. Double-click
a card, or click **Edit selected**, to edit its values. Branch and tier can also
be changed directly in the value form.

- Tiers must start at 1, with no empty tiers before a later occupied tier.
- Each tier contains one or two mutually exclusive alternatives.
- Tier numbers are 1–8. The **Order** field controls order within a tier.
- **Cost override = 0** uses the shared tier cost. A positive value sets an
  individual RP cost; moving the technology then retains that individual cost.
- Ascension Theory remains a separate finale requiring completion of the branches.
- Reorder fields under **Research branches → Move earlier / Move later**.
- The existing technology IDs still unlock their associated buildings, hulls,
  modules and special mechanics after being moved.

A draft may temporarily have an invalid layout while you rearrange it. The
bottom line reports the problem and Save remains blocked. Undo/Redo restores
whole edits, including swaps. This version edits the existing entities and
branch/tier structure; it does not create or delete technologies or branches.

## Units and ranges

Costs, work, hull, food, research and most production values are whole numbers.
Per-worker industry, per-population income and mineral multipliers accept
fractions. Percentages use whole percentages: `30` means 30%, not 0.30.

`SHIP_SPEED` uses the existing map unit: **0.02 = 2 light-years per turn**.
Fuel and sensor ranges use light-years; tactical movement uses combat cells.
`TOMB_CHANCE`, `AWAKENING_CHANCE` and `MORTALITY_CHANCE` mean **one chance in N**,
so increasing N makes the event less frequent. Growth thresholds/rates are
points, with the game displaying progress as a percentage of the threshold.
Higher growth can produce multiple population units in a turn, up to capacity.

Safety limits preserve the game's existing capacities: 12 building slots per
planet, 100 B normal population capacity, up to 12 slots per designer category and
24–72 stars. New starting-population settings automatically keep worker
assignments within the available population. Food-free races still need no farmers.

## Hull-sized modules (v0.53)

Every module uses one slot of its category. In **Designer hulls**, edit
**Offensive slots**, **Defensive slots** and **Support slots** independently.
The standard offensive count is four on every combat hull. There is no shared
space budget; old capacity fields and module space are retained in JSON only
for legacy blueprint compatibility and are hidden from the editor.

**Module size** selects small, medium or heavy. It sets the target-size class.
**Module scale** is a percentage: 200 doubles module damage, armor, shields,
shield regeneration, repair output/reserve, resource cost and work. The scaled
integer rounds up. Bare-hull costs and hull points are separate. Range, movement,
interception percentages, hardening and drone counts stay at their base values.
This lets you adjust damage scale independently of physical size.

**Tracking penalty** removes that many percentage points of hit chance for each
size class by which the attacking hull exceeds its target. For example, a heavy
hull with penalty 30 loses 60 points against a small hull. Tiny scouts/drones
are one class below small; bases and guardians are heavy. Small hulls default
to zero penalty. Normal targeting, range and evasion still apply. Tracking can
lower the final hit chance to 5%; the normal upper bound remains 95%.

**Ship modules** stores small-size base output, not the resulting value for each
hull. The designer displays the effective values for the currently selected hull.
Weapon special effects remain in **Weapons**. New AI warships and Auto fit use
the same slots, scaling and prerequisites. **Standard ships** continues to tune
the fixed ship presets, separately from custom blueprints.

Profile format 2 adds these fields when opening format 1 profiles and saves them
on the next Save. Earlier prices, research order and other edits are preserved.
Old blueprints retain unscaled modules and capacity rules until explicitly
refitted in the designer; existing ships and orders keep their original fit.

## Profiles and campaigns

### Megastructures (v0.60)

The **Megastructures** catalog contains the four system projects. Edit their
names, descriptions, research branch/tier, stage-one resource and work costs,
hull per section, finite energy per stage, ship speed multiplier increment,
resource output per stage and discovery percentage per stage. Stage costs are
multiplied by 1, 2, 3 and 4; total construction costs are ten times stage one.

The completed Dyson Sphere's unlimited energy is a fixed rule. Its numeric
energy setting controls partial-stage output. The forge uses `1 + stage ×
ship_speed_per_stage`: the default increment of 3 produces 4× / 7× / 10× / 13×
ship work. Materials remain at normal prices. Array chance is 0–25% per stage
(up to 100% when complete); it never adds ordinary research points. Mining
network output goes directly to the treasury's resource reserve.

**Global rules → Megastructures** contains industry and material costs to repair
one hull point. The four-stage structure and once-per-civilization/system limits
are fixed rules. Existing format 6 profiles gain the new catalog and repair
settings when upgraded to format 7, preserving all earlier values and tree edits.

### Administrative strain (v0.59)

**Global rules → Administration** exposes system strain (4), integration strain
(4), integration turns (8), distance strain (18), distance unit in light-years
(7), total cap (90), and research/credits/industry/mining/food sensitivities
(100/100/50/50/25). Rates and sensitivities are percentages; the distance unit
accepts decimals. It is both the free radius around the capital and the length
over which one distance-strain increment accumulates. Calculation is continuous.

Set the two empire rates or the distance rate to zero to disable those individual
contributions. A zero total cap disables all output penalties. Cap values stay
below 100 and sensitivities at or below 100. Energy and maintenance are unaffected.
All races use these shared defaults in this release. Integration also applies to
conquest, with the same duration as peaceful settlement. Earlier profile formats
are upgraded to format 6 without replacing custom ship costs or research layouts.
Earlier campaigns have no acquisition timestamps, so existing systems begin
integrated when loaded; permanent size and distance penalties apply immediately.

### Saved profiles

The default profile is `balance.json` beside the launch scripts, independent of
the current working directory. The file is created on first Save; its absence
means standard balance. A saved JSON profile is a complete snapshot of the
editable data. **Open** reads a profile without activating it in a running game.
**Save as** writes another profile. Relative paths are resolved against the game
folder. Existing files get a `.bak` backup, and saving detects external edits
to the current file so another editor's changes are not silently overwritten.

The game reads its selected profile at launch and again when starting a new
campaign. Existing campaigns keep their captured settings. Loading a save
activates its balance before validating its research, ships and construction.
Browsing the save list or failing to load a damaged file preserves the active
campaign's settings. Pre-v0.52 saves use the standard balance when loaded.
Format 36 saves require v0.52 or newer.

For a separate experiment:

```bash
python editor.py --profile balance-fast.json
python main.py --balance balance-fast.json
```

For reproducible comparisons, save two named profiles and start new campaigns
with the same galaxy seed, race and setup options. Save the profile files in
git alongside your experiment notes when you want to retain them.

```bash
python editor.py --export-defaults balance-defaults.json
python editor.py --validate balance-fast.json
```

Ctrl+O opens a profile, Ctrl+Shift+S opens Save as, Ctrl+Z undoes and Ctrl+Y redoes
an applied edit. Closing with unsaved changes offers Save, Discard or Cancel.
If a JSON file was manually damaged, correct it or move it aside before opening
the editor; `--export-defaults` can create a fresh profile under another name.

## Diplomatic values (v0.61)

The **Diplomatic values** section exposes five integer scores from −2 to +2 for
each race. All five axes have equal weight. **Global rules → alignment** exposes
`REFERENCE_DISTANCE` (default `402/55`, approximately 7.30909) and `MAX_MODIFIER`
(default 25, adjustable from 0 to 25). Set the latter to zero to disable alignment
for new relationships. Existing saved relation scores remain intact.

Changing a race profile does not recalculate the reference average. This avoids
changes to unrelated pairs. Balance profile version 8 adds these fields to older
profiles while retaining all their existing values. Campaign saves use their own
profile, and retain relationship totals on load.

## Diplomatic treaties (v0.62)

Global rules → diplomacy now contains trade, non-aggression and friendship
thresholds (10, 0 and 30), the trade share (25%) and distance scale (50 ly).
Research still uses each race's research threshold. Profile version 9 upgrades
older files, removing retired envoy/gift and flat-trade fields while preserving
other settings. Active pacts add trust; friendship bundles trade and non-aggression.

## Coalitions, fear and tribute (v0.63)

**Diplomatic priorities** adds one profile per race with a public description,
interest, frontier/goal weights, pragmatism, loyalty, betrayal memory, resolve and
trade/research/friendship preferences. Interest is selected from a validated list.
These influence actual AI treaty choices, coalition willingness and fear.

**Global rules → coalitions** exposes acceptance (40) and minimum shared threat
(10). **Global rules → tribute** exposes the cooldown (100; minimum 100), fear
threshold (75), gross-income turns demanded (3) and relations penalty (15).
Population tribute remains fixed at one citizen, using existing slave capacity.

Balance profile 10 upgrades previous profiles without overwriting their existing
settings. See [coalition and tribute rules](coalitions-and-tribute.md) for formulas,
intelligence limits, defensive commitments and persistent Lithar betrayal memory.
