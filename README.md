# Orion Reach — Python prototype 0.6

A playable colony-building and interstellar expansion prototype with an AI rival for a
MOO2-inspired space strategy game.
**Orion Reach is a temporary working title.** The artwork, interface and code
in this project are original; no Master of Orion artwork or game data is included.

![Main menu](screenshots/menu.png)

## Run

Use a desktop computer with **Python 3.10 or newer**. This is a desktop Python
application; it does not run inside the ChatGPT Android app. Tested here on
Linux with Python 3.12.14 and pygame-ce 2.5.8. Windows/macOS launch scripts are
provided, but those platforms have not been tested in this environment.

**Recommended during development: Anaconda / Miniconda.** Extract the entire
ZIP and open Anaconda Prompt (or a terminal with Conda initialized). Change
directory into the extracted `orion_reach` folder, then run:

```sh
conda create -n moo2 python=3.12
conda activate moo2
python -m pip install -r requirements.txt
python main.py
```

The environment creation and dependency installation are one-time steps.
For later sessions, return to the project folder and run:

```sh
conda activate moo2
python main.py
```

Edit the Python files in your preferred editor, then close and restart the
game to see your changes. Tracebacks appear directly in the terminal.

**Optional Windows launcher:** open the extracted `orion_reach` folder and
double-click **launch.bat**. This creates its own `.venv` and installs the
dependency on its first launch. Python must already be installed. Use the
command-line route above when working in your Conda environment.

**macOS/Linux:** extract the ZIP, open a terminal in `orion_reach`, then run:

```sh
sh launch.sh
```

**Or use an existing Python environment**, from the project folder:

```sh
python -m pip install -r requirements.txt
python main.py
```

Only pygame-ce is required at runtime. The first dependency installation needs
internet access; the game itself works offline. pygame-ce is imported as
`pygame`; use a clean environment if you already have the separate `pygame`
package installed. Official documentation: <https://pyga.me/docs/>.

## Included

- Animated title screen: **New Game, Load Game, Settings, Quit**, plus About.
- **Continue** appears when a campaign is already open in the current session.
- New Game setup: editable empire name, three galaxy sizes (24/48/72 systems),
  and an optional reproducible seed.
- Click a star on the galaxy map to open a dedicated **solar-system screen**.
- Click a planet's globe or caption to open its **planet overview**: environment,
  size, gravity, minerals, habitability, orbital distance and colony status.
- Sol contains Mercury, Venus, Earth and Mars. Other systems have reproducible
  planet data and distinct illustrations for six environment types.
- The planet screen has **Overview**, **Colony** and **Shipyard** tabs. Earth is your starting
  colony: construct factories, mines, trade centres and research labs, with a
  building-slot limit based on planet size.
- Construction queues show progress and completion estimates. Completed
  buildings contribute industry, credits and research; cancel projects for a
  refund of unspent work or demolish completed buildings to free a slot.
- **Empire Overview** combines economy totals and a sortable colony directory.
  Open it with **Empire · I** or the **I** key from any gameplay screen. Click
  a colony row to open its construction screen.
- Build colony ships in the **Shipyard**, plot routes through **Fleets**, advance
  travel with End Turn, and settle new worlds from their planet overviews.
- The galaxy map shows flight paths, ship positions and newly claimed systems.
- The **Helios Directorate** develops its economy, builds colony ships, travels
  between systems and settles unclaimed worlds on each End Turn. Open
  **Empire → Rival report** to inspect its economy, colonies and recent activity.
- Cyan marks your colonies and ships; orange marks the rival's. Rival worlds
  can be surveyed, with construction controls disabled.
- Back buttons and Escape follow **Colony → Planet → System → Galaxy**. Pause, settings
  and Continue preserve the active overview. Previous/Next controls browse
  systems and planets, including systems with no planets.
- These are separate full-window screens inside the game, not additional
  operating-system windows.
- Real JSON saves: one autosave and any number of separate manual snapshots.
  Load Game shows dates, empire names and turns, with pagination.
- Autosave on campaign creation, construction orders/cancellations/demolition,
  ship orders, settlement, adding a rival, End Turn, return to menu and normal exit.
- Fullscreen, animated background and interface-sound settings persist.
- Mouse and keyboard navigation, resizing with correct letterboxed hit regions.
- Damaged/incompatible saves appear as unavailable instead of crashing the app.

**Scope:** construct buildings and colony ships, travel between systems, and
found additional colonies alongside an expanding AI empire. Population growth,
food, a technology tree, combat, warships, diplomacy and victory conditions are future work. Research
points accumulate but cannot yet be spent. Planet attributes, population and
habitability are illustrative game data. Sol intentionally includes only four
inner worlds; its artwork is stylized. Settings contains interface sounds,
not music.

## Build your first colony

Start or load a game, then click **Sol → Earth → Colony**. Click **Build** beside
a building in the catalogue, then advance turns with **End Turn** or **E**.
Earth starts with 120 empire credits, 6 industry per turn, and 8 credits per
turn from its population. A first factory costs 45 credits and completes after
four End Turns; it raises industry from 6 to 10 for subsequent turns.

| Planet size | Building slots |
| --- | ---: |
| Tiny | 4 |
| Small | 6 |
| Medium (Earth) | 8 |
| Large | 10 |
| Huge | 12 |

Each completed or queued building uses one slot. Repeated copies of a building
are allowed, and their outputs add together. Planet size determines capacity;
habitability does not change it in this version.

| Building | Upfront credits | Construction work | Output per turn |
| --- | ---: | ---: | --- |
| Factory | 45 | 24 | +4 industry |
| Mining complex | 30 | 18 | +1 / +2 / +3 industry on Poor / Average / Rich worlds, plus +1 credit |
| Trade centre | 40 | 24 | +4 credits |
| Research lab | 50 | 30 | +4 research points |

- Industry advances one sequential queue on each colony. Overflow work can
  start the next queued project in the same turn; unused industry is not stored.
- The catalogue estimates completion after any projects already in the queue,
  including speed increases from factories/mines that will finish ahead of it.
- A turn collects output from buildings operational at its start. A newly
  completed building starts producing on the following turn.
- Click a queued slot to inspect it and **Cancel**. An unstarted project returns
  its full credit cost; a partially built project refunds
  `floor(cost × remaining work / total work)`. The displayed refund is exact.
- Click an operational building to **Demolish** it. Confirmation is required;
  its output stops immediately and its construction cost is not refunded.
- Uncolonized planets show their capacity, with construction disabled until
  settled. Bring a colony ship to the system and use the planet's Overview tab.

Every colony has a base of 6 industry per turn and one credit per billion
inhabitants. There is no upkeep or population growth yet. All colony income and
research contribute to the empire totals. Costs, work and capacities can be
tuned in `orion/buildings.py`.

## Basic AI opponent

New games include the **Helios Directorate**, starting on a habitable world
far from your colonies. Both empires start with one colony, 8 billion inhabitants,
120 credits and no buildings or ships. The rival's starting world retains its
generated size, biome and minerals, so its building capacity can differ from Earth's.

**Continuing a v0.5 or earlier campaign:** load your save, open **Empire → Rival
report**, then click **Add rival**. This uses an unclaimed habitable world in a
system without your colonies. It preserves your existing assets and progress.
Older saves do not gain an opponent automatically. If no suitable starting world
remains, Add rival is disabled. Adding a rival autosaves the campaign.

- The AI builds factories and trade centres first, then develops research and
  mining. Its strongest colony produces colony ships; other colonies develop
  their economies. The shipyard's development target rises as the empire grows.
- Ships settle suitable unclaimed planets in their current system, otherwise
  travel to nearby systems with available worlds. The rival avoids sending more
  ships to a system than it has available planets. If a target is claimed while
  a ship is travelling, it chooses another world or route after arrival.
- Credits and research are separate for each empire. All construction, refunds,
  building slots, ship costs, travel and settlement use the same rules.
  The AI receives no extra income or production. It can have up to three colony
  ships active or queued, depending on its colony count and remaining worlds.
- **End Turn** issues the AI's orders, records starting yields, advances both
  empires' travel and construction, then deposits income in their respective
  treasuries. Newly completed ships receive their first AI order on the next
  End Turn; arrived ships can settle or reroute on the next End Turn.
- **Rival report** shows finances, output, ships, colonies and the latest six
  activity entries. Click **Survey** to inspect a colony's buildings and queue.
  The report and map reveal the rival's activity; fog of war is not implemented.
- Your Empire Overview and Fleets list only your assets. A system can contain
  colonies from both empires, shown with cyan and orange rings. Neither side
  can take over an established colony. This is competition for territory and
  development; combat, diplomacy and victory conditions come later.

AI decisions are deterministic for a given game state. Saving and loading
preserves its finances, orders, ships, ownership and recent activity.

## Build, travel and colonize

1. Open **Sol → Earth → Shipyard** and click **Build colony ship**. It costs
   **80 credits and 42 work**, completing after seven End Turns at Earth's
   initial 6 industry per turn, if there are no projects ahead of it.
2. Open **Fleets** with the top button or **F**. The finished ship starts in orbit
   around its construction system. Click its **Plot course** button.
3. On the galaxy map, click a star. The sidebar's **Send ship** button shows the
   travel time; the map previews the route and reports suitable unsettled worlds.
   Click Send to issue the order, or **Cancel / Escape** to leave without sending.
4. Use **End Turn / E** to advance the journey. Fleets shows remaining turns.
   You can save and reload during flight. Arrival is automatic; the ship waits
   in the destination system until you choose its next action.
5. Click the ship's **View system**, open a suitable planet, click **Colonize**,
   and confirm. The ship is consumed and the planet becomes a colony with
   **1 billion inhabitants**, 6 base industry and 1 credit income per turn.
   It appears immediately in Empire Overview and can build buildings and ships.

To settle **Mars** first, build a ship at Earth and open Mars directly; no travel
order is needed between planets in the same system.

| Rule | Prototype behavior |
| --- | --- |
| Suitable planets | Uncolonized Terran, Ocean, Desert and Tundra worlds |
| Hostile worlds | Barren and Volcanic require a later life-support technology |
| Ship construction | Shares the sequential queue and industry with buildings; no building slot |
| Queue capacity | Up to 20 total projects per planet |
| Cancellation | Shipyard lists every queued project; refunds follow the same unspent-work rule as buildings |
| Travel time | `ceil(hypot(1.4 * dx, dy) / 0.18)`, at least one turn between distinct systems |
| Travel restrictions | Orders require a ship in orbit; no mid-flight rerouting, fuel cost or range limit yet |
| Settlement | Requires an arrived colony ship in the target system; consumes exactly one ship |
| Population | Starting colonists are included in ship cost; homeworld population is not deducted in this version |

Unused construction overflow follows the existing building rules. A ship
finishes in orbit and receives no automatic travel order. The colony economy
starts on the next End Turn after settlement. Ship costs, initial colonists,
queue capacity and travel speed are defined in `orion/production.py`.

## Empire Overview

Click **Empire · I** at the top of the galaxy, system, planet or colony screen,
or press **I**. The overview shows:

- Total colonies and population, treasury and credit income, industry,
  stored research and research income, and occupied/available building slots.
- One row per colony, with population, per-turn output, slots, the current
  construction project, work progress, completion estimate and waiting projects.
- **All**, **Building**, **Idle** and **Full** filters. Full includes slots
  reserved by queued projects. The summary totals always cover the entire empire.
- Sortable colony name, population, industry, income, research and occupied
  slot columns. Numerical columns initially sort highest first; clicking the
  same heading again reverses the order.
- Five colonies per page; use Previous/Next, Page Up/Down, Left/Right or the
  mouse wheel to browse larger empires.

Click a row to open that colony, then use **Empire · I** to return. **Escape**,
**I**, or the overview's Back button returns to the screen you opened it from.
Save, End Turn, pause, settings and Continue work from the overview. The list
and totals refresh after construction and turn changes. Industry remains local
to each planet; the empire total is a report, not a shared construction pool.

Earth is the starting colony; each newly settled world appears in the directory.
The current project may be a building or a ship. Ship construction counts as
activity but does not reserve a building slot. View filters,
sort order and page are kept during play and reset when starting/loading a game.

## Controls

| Action | Control |
| --- | --- |
| Select a control | Mouse, Tab / Shift+Tab, Up / Down |
| Activate focused control | Left click, Enter or Space |
| Edit name/seed | Click field or focus it and press Enter; type; Enter finishes |
| Replace field contents | Ctrl+A (Cmd+A on macOS), then type |
| Back through Colony → Planet → System → Galaxy | Escape or the Back button |
| Pause / resume on the galaxy screen | Escape |
| Pause from any overview | Menu button |
| Fullscreen | F11 |
| Save a manual snapshot | F5, or Save Game on any overview |
| Advance one turn | E, or End Turn |
| Open a solar system | Click a star; or Left / Right then Enter on the galaxy screen |
| Open a planet | Click its globe/caption; or Left / Right then Enter in the system screen |
| Browse planets while viewing details | Left / Right, or Previous / Next buttons |
| Manage buildings | Colony tab on a planet overview |
| Inspect, cancel or demolish | Click a building slot in the Colony tab |
| Open / close Empire Overview | I, or the Empire button while playing |
| Open a colony from Empire Overview | Click its row, or focus it and press Enter |
| Browse colony pages | Page Up / Down, Left / Right, mouse wheel, or Previous / Next |
| Open / close Fleets | F, or the Fleets button while playing |
| Build ships / inspect the shared queue | Shipyard tab on a planet |
| Set a ship destination | Plot course in Fleets → click a star → Send ship |
| Cancel an unissued course | Cancel button or Escape on the route-selection map |
| Settle a world | Colonize on its Overview tab, with a colony ship in the system |
| Browse fleet or shipyard queue pages | Page Up / Down, mouse wheel, or Previous / Next |
| Inspect or add the AI opponent | Empire → Rival report |

## Save locations

User data is stored separately from the extracted source folder:

| System | Folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\OrionReach` |
| macOS | `~/Library/Application Support/OrionReach` |
| Linux | `$XDG_DATA_HOME/orion-reach`, default `~/.local/share/orion-reach` |

Saves are in `saves/`; preferences are in `settings.json`. To choose a different
location, use `python main.py --data-dir ./my_data` or set
`ORION_REACH_DATA_DIR`. Starting another campaign replaces the single autosave;
use **Save Game** to retain a manual snapshot first. Manual snapshots are never
overwritten. Saves use validated, versioned JSON, not executable serialization.
Writes use a temporary file followed by an atomic replacement.

**Compatibility:** v0.6 loads all earlier prototype saves without rewriting the
source file during loading. Existing colonies and ships become player-owned;
no rival is added until you choose Add rival. v0.5 ships, flights and production
are preserved. v0.3/v0.4 building queues, progress, planets and research are
preserved, and those campaigns start with no ships. v0.1's missing planets are
generated deterministically; v0.1/v0.2 start with empty production and zero research.
New saves use **format version 5**, including empire ownership and the rival's
finances, homeworld and recent activity. They cannot be opened by v0.5 or
earlier. Loading starts at the galaxy map with system/planet selection retained.
Keep an older manual snapshot if you plan to switch back; normal gameplay
updates the autosave. Unissued route previews are not saved as orders.

## Extend the prototype

| File | Responsibility |
| --- | --- |
| `main.py` | Entry point, CLI and screenshot capture |
| `orion/app.py` | Event loop, screens and transitions |
| `orion/ui.py` | Buttons, focus styling, text and layout helpers |
| `orion/art.py` | Starfield animation, orbit guides and spacecraft |
| `orion/system_views.py` | Solar-system and planet overview layouts |
| `orion/colony_view.py` | Colony slots, construction catalogue and project inspection |
| `orion/buildings.py` | Building definitions, costs, outputs and size-based capacity |
| `orion/empire.py` | Read-only empire totals, colony filtering and sorting |
| `orion/empire_view.py` | Empire Overview layout and colony directory |
| `orion/ai.py` | Deterministic rival construction, travel and settlement policy |
| `orion/rival_view.py` | Rival economy, activity and colony survey report |
| `orion/production.py` | Shared project catalogue, ship costs and travel balance |
| `orion/fleet_views.py` | Shipyard, fleets and galaxy-map routes |
| `orion/fleet_art.py` | Procedural transport icons |
| `orion/planet_art.py` | Cached, deterministic globe drawings for six environments |
| `orion/model.py` | Game state and seeded generation; no pygame dependency |
| `orion/storage.py` | Save validation, atomic writes, settings and data paths |
| `assets/` | Bundled artwork and fonts |
| `tools/build_art.py` | Rebuild the original planet/background (optional) |
| `tests/test_prototype.py` | Save integrity and UI event-flow checks |
| `tests/test_colony.py` | Construction rules, economy timing and save migrations |
| `tests/test_empire.py` | Empire reports, filtering, pagination and colony navigation |
| `tests/test_colonization.py` | Ship construction, travel, settlement, migration and the full UI loop |
| `tests/test_ai.py` | Ownership, independent economies, AI expansion, save continuity and rival controls |

Keep new simulation rules in `model.py` or additional model modules. Add screens
to the UI controller as needed. The next practical increments are population
growth, food and a technology tree that spends stored research.
Warships and tactical combat can follow. Bump the save version and add
migrations when the data schema changes.

## Development checks

The automated checks use Python's built-in unittest and SDL's dummy drivers:

```sh
python -m unittest discover -s tests -v
python main.py --headless --screenshot menu.png
python main.py --headless --screen galaxy --screenshot galaxy.png
python main.py --headless --screen system --screenshot system.png
python main.py --headless --screen planet --screenshot planet.png
python main.py --headless --screen colony --screenshot colony.png
python main.py --headless --screen empire --screenshot empire.png
python main.py --headless --screen shipyard --screenshot shipyard.png
python main.py --headless --screen fleets --screenshot fleets.png
python main.py --headless --screen rival --screenshot rival.png
```

`--screen` supports `menu`, `setup`, `load`, `settings`, `galaxy`, `system`,
`planet`, `colony`, `empire`, `shipyard`, `fleets`, `rival`, and `about`.
Screenshot mode does not create a campaign save or change your settings.
To regenerate art only, install `numpy` and `Pillow` and run
`python tools/build_art.py`; these are not needed to play.

## Start a GitHub repository

Suggested repository name: **orion-reach**. Start private while developing the
prototype. The repository root should contain `main.py`, `README.md`, `orion/`,
and `assets/` directly.

1. On <https://github.com/new>, create an empty repository. Leave the options
   to add a README, `.gitignore`, and license unselected: this project already
   includes the first two, and you can choose a license separately later.
2. Open Anaconda Prompt in the extracted `orion_reach` folder and run:

   ```sh
   git init -b main
   git add .
   git status
   git commit -m "Initial prototype: menu, galaxy preview and save/load"
   ```

3. Copy the HTTPS URL from the new repository's page. Replace `YOUR_USERNAME`
   below with your GitHub username (and adjust the repository name if needed):

   ```sh
   git remote add origin https://github.com/YOUR_USERNAME/orion-reach.git
   git push -u origin main
   ```

Complete GitHub authentication if prompted. If Git reports an unknown author
identity, set your name and preferred GitHub commit email with `git config
user.name` and `git config user.email`, then repeat the commit. If `git` is not
available in your Anaconda Prompt, install Git for Windows and reopen the prompt.

The supplied `.gitignore` excludes environments, caches, common local settings
and save directories. Keep any custom `--data-dir` outside the repository, or
add that directory to `.gitignore`. Source code, assets, tests and the bundled
screenshots are included. `.gitattributes` keeps line endings consistent.

For the next feature, start a branch from the working baseline:

```sh
git switch -c feature/basic-ai
```

After editing and checking the game, commit the change and push that branch.
Official import instructions:
<https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github>.

## Troubleshooting

- **Window does not open:** run from a terminal to see the error, and confirm a
  working desktop display is available. Headless machines can use screenshots.
- **No audio device:** gameplay works; interface sounds are skipped.
- **Fullscreen trouble:** press F11. If needed, delete `settings.json` to restore
  defaults; this does not delete saves.
- **Cannot save:** select a writable directory using `--data-dir`.
- **Linux venv error:** your Python distribution may package `venv` separately;
  install its venv support or use an existing environment.

Font notices are included in `assets/fonts/LICENSE-DejaVu.txt`. pygame-ce is
installed separately and retains its own license. No third-party game assets
are redistributed.
