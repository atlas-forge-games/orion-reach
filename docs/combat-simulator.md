# Standalone combat simulator

Start the laboratory from the game folder, using the same Python/Conda
environment as Orion Reach:

```bash
python combat_simulator.py
```

It uses the existing Pygame dependency. There is no campaign to generate or
play through, and no campaign save is loaded or written.

## Build a matchup

1. Use **+ Yours** and **+ Enemy** in the ship catalogue. The side panels
   change quantities or clear a fleet. Each side supports 60 ships and up to
   three planetary missile bases. Standard civilian ships and motherships
   are on the catalogue's second page.
2. Choose each side's race and combat research. **No combat upgrades** uses
   baseline equipment, **Targeting computers** applies that research, and
   **Advanced combat upgrades** applies Quantum Targeting, Electronic
   Countermeasures, Precision Beam Optics, Quantum Optics and Advanced
   Torpedo Guidance. Their effects come from the active balance profile.
3. Use **New custom design**, or select a catalogue ship and choose
   **Edit / customize selected**, to specify its weapons, defenses and support
   modules. All hulls and equipment are available immediately; normal slot,
   scanner, carrier and support-module hull restrictions still apply. Save the blueprint, then
   add it to either or both fleets using **+ Yours / + Enemy** in the designer.
   Right-click equipment for its actual hull-scaled properties.
4. Choose the first side, seed and accuracy mode. **Every shot hits** bypasses
   accuracy rolls for damage experiments; shields, interception, cooldowns
   and weapon effects still apply. Command and ECM accuracy effects are
   inactive in this mode. Normal accuracy is the default.
5. Select **Fight manually** or **Watch AI vs AI**. The side moving first
   must have an armed ship, carrier or missile base. An unarmed convoy can
   be tested by letting the attacker move first.

The **Copy yours → enemy** button makes an independent copy of your current
fleet, race, upgrades and bases. Later quantity changes affect only the
selected side. Custom designs are shared by the scenario: updating a saved
design changes all references to that design on the next battle launch.
Use **Save as new** to compare two variants side by side.

The seven quick scenarios are Fleet skirmish, Carrier clash, Capital duel,
Shield laboratory, Planetary assault, Convoy interception and Combined arms. Cycle the
scenario button and select **Apply** to replace the current setup. Save a
named setup first if you want to return to it.

**Combined arms** includes custom escort destroyers, a command titan, an ECM
cruiser, a battleship, a carrier and frigates facing a carrier/torpedo force.
It is a demonstration matchup, not an equal-cost balance benchmark. Remove
escorts or change their loadouts to explore the trade-offs. Standard destroyers
and titans also supply their basic support roles; custom ships must fit the
corresponding modules. See [Fleet cooperation](fleet-support.md).

## During combat

| Control | Action |
| --- | --- |
| Click a friendly ship, then a highlighted cell | Move |
| Select an enemy, then Fire | Fire the selected ship's available weapons |
| E | End your side's turn |
| N | Select the next available ship |
| A | Toggle automatic control of your fleet |
| P or Esc | Pause/resume orders and animations |
| Speed button | Cycle 1×, 4× and 12× playback |
| R or Rematch | Restore the original fleets and replay with the same seed and initial control mode |
| Edit fleets | Return to the original setup to adjust the matchup |
| Mouse wheel / Page Up / Page Down | Scroll a large battlefield |
| F5 | Save the scenario's setup and saved blueprints |
| F1 | Simulator help |
| F11 | Toggle fullscreen |

The normal combat engine handles movement, tracking, hit chances, shields,
weapon cooldowns, damage control, drones, missile bases, retreat and losses.
Escort protection, command links and ECM are automatic. Select a provider to
see its radius, or another ship to see its supporting links. The right panel
shows current shared protection, command accuracy and ECM. Different ship
sizes are visual; movement and click targets still use one cell per unit.
Motherships use their real mobile habitats and basic shields. Retreating
fleets have nearby test anchorages available. Strategic turns never advance.

The result shows losses, rounds, shots and surviving ship hull. A rematch
restores damaged ships, destroyed bases, shield capacity, repair reserves,
drone launches and spent actions. The setup is never modified by the battle.
After 300 rounds the simulator pauses to make stalled matchups manageable;
you can edit, rematch or explicitly resume. It does not invent a winner.

## Approach, torpedoes and ship details

Fleets begin 17 cells apart on a 24-column battlefield. The map shows 13 rows
at once and scrolls vertically for large fleets. Ship sizes remain distinct;
each ship still occupies one cell. Stationary planetary batteries form a
forward defensive line and can engage opposing batteries.

Torpedoes, MIRV warheads, bomber torpedoes and planetary missiles travel three
cells per round. A volley moves at the start of its firing side's next turn,
so the enemy always has a turn to respond before the first impact. An
8-cell shot takes three advances against a stationary target. Moving the
target changes the path and estimated time. Beams hit immediately.

**Right-click any ship on the battlefield**, including enemy ships, during
manual play, automatic combat or a movement animation. A paused detail panel
shows hull and shield condition, movement, regeneration, repair reserves,
point defense, allied screens, drone capacity and status. Its tabs show:

- **Weapons:** installed weapons, damage, shot counts, range, base aim,
  recharge state and special effects.
- **Equipment:** the fitted modules and their descriptions, with pages for
  larger loadouts.
- **Ordnance:** incoming and outgoing projectiles, targets, payload, locked
  aim, remaining fuel and estimated arrival in rounds.

Esc or Close returns to the battle with the same selection and pause/auto
state. Weapon aim in the Weapons tab is the base value; the targeting sidebar
shows target-specific modifiers. Travel estimates assume the target stays
where it is. See [the detailed rules](combat-projectiles.md).

## Save and load

Choose a scenario name and select **Save scenario** or press **F5**. The
saved JSON contains the initial fleet setup and its saved custom blueprints,
not an in-progress tactical turn. **Load scenario** opens the scenario browser.
Saving again under the same name updates that scenario; another name creates
another scenario. Scenario files have a distinct format and are validated
before loading. Invalid loads leave the current setup intact.

The default folder is the game's user-data folder followed by
`combat-simulator/scenarios`. On Windows this is normally
`%LOCALAPPDATA%\OrionReach\combat-simulator\scenarios`. The load screen displays
the actual path. Quit closes the simulator; save setups you want to keep.

For a local scenario directory:

```bash
python combat_simulator.py --data-dir combat_lab
```

This writes scenarios under `combat_lab/scenarios`. Simulator code never
calls campaign save storage, even when given a directory containing campaign
saves.

## Balance and reproducibility

By default the simulator reads `balance.json` beside the launcher, just like
the game. Edit the profile with `editor.py`, save it, then restart the
simulator to test it. Scenarios store compositions and loadouts; they use the
profile loaded by the current simulator session rather than embedding a
balance snapshot. Identical seeds, equipment, settings and orders reproduce
the same battle under the same profile. Changing the seed changes hit rolls.

```bash
python combat_simulator.py --balance test_balance.json
python combat_simulator.py --scenario combat_lab/scenarios/example.json
python combat_simulator.py --preset 2 --auto --seed 12345
```

Presets are numbered 1–7 in the order listed above. All equipment is
available independently of the selected passive combat research. This makes
it possible to compare advanced weapons with basic or advanced targeting.
The simulator does not implement new combat rules, campaign research
progression, ground battles or post-battle strategic actions.

## Screenshots and verification

```bash
python combat_simulator.py --headless --screenshot screenshots/combat_setup.png
python combat_simulator.py --headless --preset 4 --screen designer --screenshot screenshots/combat_design.png
python combat_simulator.py --headless --preset 5 --screen combat --screenshot screenshots/combat_battle.png
python combat_simulator.py --headless --preset 2 --screen result --screenshot screenshots/combat_result.png
python -m unittest discover -s tests -p test_combat_simulator.py -q
```

The result preview runs both sides through the ordinary combat AI. A preview
that cannot finish within the round/action limit reports an error instead of
running indefinitely.
