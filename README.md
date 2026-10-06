# Orion Reach — Python prototype 0.4

A playable application shell and colony-building prototype for a MOO2-inspired
space strategy game.
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
- The planet screen has **Overview** and **Colony** tabs. Earth is your starting
  colony: construct factories, mines, trade centres and research labs, with a
  building-slot limit based on planet size.
- Construction queues show progress and completion estimates. Completed
  buildings contribute industry, credits and research; cancel projects for a
  refund of unspent work or demolish completed buildings to free a slot.
- **Empire Overview** combines economy totals and a sortable colony directory.
  Open it with **Empire · I** or the **I** key from any gameplay screen. Click
  a colony row to open its construction screen.
- Back buttons and Escape follow **Colony → Planet → System → Galaxy**. Pause, settings
  and Continue preserve the active overview. Previous/Next controls browse
  systems and planets, including systems with no planets.
- These are separate full-window screens inside the game, not additional
  operating-system windows.
- Real JSON saves: one autosave and any number of separate manual snapshots.
  Load Game shows dates, empire names and turns, with pagination.
- Autosave on campaign creation, construction orders/cancellations/demolition,
  End Turn, return to menu and normal exit.
- Fullscreen, animated background and interface-sound settings persist.
- Mouse and keyboard navigation, resizing with correct letterboxed hit regions.
- Damaged/incompatible saves appear as unavailable instead of crashing the app.

**Scope:** construction and its economy are playable on Earth. Population
growth, founding additional colonies, a technology tree, combat, diplomacy,
fleet movement, AI opponents and victory conditions are future work. Research
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
- Uncolonized planets show their capacity, with construction disabled. Use
  Earth until founding new colonies is implemented.

Every colony has a base of 6 industry per turn and one credit per billion
inhabitants. There is no upkeep or population growth yet. All colony income and
research contribute to the empire totals. Costs, work and capacities can be
tuned in `orion/buildings.py`.

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

Earth is still the only starting colony. The directory supports additional
colonies when colonization is implemented; the tests use synthetic settlements
to verify multi-colony sorting, totals, pagination and navigation. View filters,
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

**Compatibility:** v0.4 uses the same save format as v0.3. Existing buildings,
queues and research are preserved; no migration is needed between those versions.
It also loads v0.1/v0.2 saves without rewriting the original file during loading.
v0.1's missing planet details are generated deterministically; v0.2's existing
planet data is preserved. Those older campaigns start with empty building
lists/queues and zero research. New saves use format version 3 and cannot be
opened by v0.1/v0.2. Loading starts at the galaxy map with system/planet selection
retained. Keep a manual snapshot if you plan to return to v0.1/v0.2; normal
gameplay updates the autosave.

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
| `orion/planet_art.py` | Cached, deterministic globe drawings for six environments |
| `orion/model.py` | Game state and seeded generation; no pygame dependency |
| `orion/storage.py` | Save validation, atomic writes, settings and data paths |
| `assets/` | Bundled artwork and fonts |
| `tools/build_art.py` | Rebuild the original planet/background (optional) |
| `tests/test_prototype.py` | Save integrity and UI event-flow checks |
| `tests/test_colony.py` | Construction rules, economy timing and save migrations |
| `tests/test_empire.py` | Empire reports, filtering, pagination and colony navigation |

Keep new simulation rules in `model.py` or additional model modules. Add screens
to the UI controller as needed. The next practical increments are colony
founding, population growth and a technology tree that spends stored research.
Fleet and tactical combat systems can follow. Bump the save version and add
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
```

`--screen` supports `menu`, `setup`, `load`, `settings`, `galaxy`, `system`,
`planet`, `colony`, `empire`, and `about`.
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
git switch -c feature/empire-overview
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
