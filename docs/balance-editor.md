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
