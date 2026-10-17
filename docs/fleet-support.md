# Fleet cooperation

Keep controlling individual ships: one movement action and one weapon/launch
action per turn. Support equipment works automatically, including during the
opponent's turn and after the provider has moved, fired or held position.
There are no selectable battle plans or activated support abilities.

## Equipment

Default values below are editable in `python editor.py`. Each module occupies
one support slot. Resource/work costs scale with the hull; percentages and
support radii do not. Research is required for campaign construction, while
the simulator makes all equipment available for experiments.

| Module | Hull | Research | Effect on other nearby allies |
| --- | --- | --- | --- |
| Escort array | Destroyer | Basic equipment; hull needs Destroyer Hulls | +25% interception within 2 cells |
| Command relay | Cruiser or Titan | Research Networks, plus hull research | +8 accuracy percentage points within 3 cells |
| Flag bridge | Titan | Titan Hulls | +12 accuracy percentage points within 4 cells |
| ECM projector | Cruiser | Electronic Countermeasures, plus hull research | Attacks against protected allies lose 8 accuracy percentage points within 3 cells |

One copy of each module per ship. A ship can fit either a command relay or a
flag bridge. Support competes with engines, scanners, damage control and other
support equipment. A torpedo destroyer can leave off its escort array to use
that slot elsewhere. New auto-fit designs include the appropriate support
equipment when researched and when the active slot profile permits it.

Stock destroyers carry an escort array and stock titans carry a flag bridge.
These stock effects use the corresponding module's active balance values.
Custom designs, including pre-v0.71 blueprints and existing ships built from
them, receive only equipment actually fitted to that design. Updating a
campaign blueprint affects future production; it does not retrofit ships.

## What support does

Support never affects the provider itself. Distance is Euclidean, measured
between occupied cell centres, and the boundary is included. Movement changes
coverage immediately. Destroyed ships stop providing support immediately.
There are no charges or hidden support actions to manage.

Escort arrays reduce projectile and drone damage against other allied units.
Interceptor drones retain their +20% protection within 2 cells, capped at 40%
from drones. Destroyer arrays and drones together provide at most 50% shared
interception. Add that to the protected ship's own point defense, then cap the
total at 90%. Existing MIRV penetration and damage rounding still apply. Beams
ignore interception. Interception softens damage; the animation does not add
separate projectile objects or interception rolls.

Command uses only the strongest friendly source in range. It coordinates
ships, including motherships, but not autonomous drones or planetary batteries.
Range, evasion and large-mount tracking penalties still apply; a command titan
does not make heavy guns reliable against small raiders. A lone flagship gets
no benefit from its own command equipment. Losing it does not stop other ships
from taking their normal turns.

ECM uses only the strongest projector protecting the target. It affects both
beams and projectiles. It is defensive coverage around the cruiser: the
attacker does not have to be inside that radius. The usual minimum/maximum
hit chances remain. Several projectors extend coverage without multiplying the
penalty on one target. Ships can receive both command and ECM support.

When a simulator battle uses **Every shot hits**, command and ECM accuracy
effects are inactive. Escort damage reduction still works.

## Tactics and readable feedback

- Keep a destroyer near a valuable capital or civilian ship to protect it.
  Moving the destroyer away to pursue a target can expose the protected ship.
- Concentrated beam fire can eliminate the screen before torpedoes or bombers
  attack the capital. Accurate light weapons remain valuable against raiders.
- Command ships help nearby attackers; their loss removes the accuracy bonus.
  More command ships can cover a wider formation without stacking bonuses.
- ECM cruisers reduce incoming accuracy, but their own projector does not
  protect them. Separate ships can cover one another.
- Support has an equipment and economic cost. Different enemy weapons and
  formations can favour different fleet compositions.

Select a support ship to see its range and covered allies. Green denotes
escort protection, blue command and violet ECM. Selecting a supported ship
shows its links to support providers. The sidebar lists shared screening,
received aim and ECM, and the target's current defenses. Hit chances and AI
damage forecasts use the same calculations as actual firing. Defensive bursts
appear during intercepted projectile/drone attacks, and the log identifies
volleys whose damage was reduced by a shared screen.

The AI follows suitable allies with support ships, uses actual defenses in its
damage estimates and resumes ordinary attacks when no support anchor exists.
Automatic support formations do not impose movement restrictions on manual
orders. Campaign production adds escorts, carriers and support cruisers as
the available research, resources and maintenance budget allow. Queued ships
count toward those composition targets.

## Ship sizes

Tactical art grows from tiny drones and scouts through frigates, destroyers,
cruisers, carriers and battleships to titans. Artwork keeps its proportions
and is fitted inside a single grid cell. Hull bars and the full cell-sized
click area remain readable. Explosions scale with ship class.

Sizes are visual: they do not change occupancy, movement paths or the existing
accuracy model. Large-mount tracking penalties still depend on the existing
hull/module size rules. There are no multi-cell ships or new facing controls.

## Testing in the simulator

```bash
python combat_simulator.py --preset 7
```

The **Combined arms** scenario supplies ready-made blueprints for testing.
Use normal accuracy to observe command and ECM. Remove an escort, change a
support module, or alter positioning and replay. The example fleets are not
equal in cost; fair composition comparisons should also account for resource
cost, maintenance, equipment/research and which side moves first. Try several
seeds rather than treating a single battle as a balance result.

## Compatibility

Campaign save format remains 50. No new tactical state is stored: support is
recomputed from surviving ships, equipment and positions after loading.
Balance profiles upgrade from 14 to 15 by adding new modules and support
fields/rules, while preserving prior edited values. Scenario format remains 1.
Old files remain readable, although the new stock support roles and AI can
change replay outcomes. Use v0.71 to load profiles or scenarios with new modules.
