# Orion Reach — Python prototype 0.2

A first playable application shell for a MOO2-inspired space strategy game.
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
- Back buttons and Escape follow **Planet → System → Galaxy**. Pause, settings
  and Continue preserve the active overview. Previous/Next controls browse
  systems and planets, including systems with no planets.
- These are separate full-window screens inside the game, not additional
  operating-system windows.
- Real JSON saves: one autosave and any number of separate manual snapshots.
  Load Game shows dates, empire names and turns, with pagination.
- Autosave on campaign creation, End Turn, return to menu and normal exit.
- Fullscreen, animated background and interface-sound settings persist.
- Mouse and keyboard navigation, resizing with correct letterboxed hit regions.
- Damaged/incompatible saves appear as unavailable instead of crashing the app.

**Scope:** this is the menu/application foundation. Combat, colonies, research,
diplomacy, fleet movement, AI opponents and victory conditions are not yet
implemented. End Turn currently adds one year and eight credits as an explicit
placeholder. Planet attributes, population and habitability are illustrative
game data, not scientific predictions or a colony simulation. Sol intentionally
includes only four inner worlds; its artwork is stylized. Settings contains
interface sounds, not music.

## Controls

| Action | Control |
| --- | --- |
| Select a control | Mouse, Tab / Shift+Tab, Up / Down |
| Activate focused control | Left click, Enter or Space |
| Edit name/seed | Click field or focus it and press Enter; type; Enter finishes |
| Replace field contents | Ctrl+A (Cmd+A on macOS), then type |
| Back from planet to system, then to galaxy | Escape or the Back button |
| Pause / resume on the galaxy screen | Escape |
| Pause from any overview | Menu button |
| Fullscreen | F11 |
| Save a manual snapshot | F5, or Save Game on any overview |
| Advance one turn | E, or End Turn |
| Open a solar system | Click a star; or Left / Right then Enter on the galaxy screen |
| Open a planet | Click its globe/caption; or Left / Right then Enter in the system screen |
| Browse planets while viewing details | Left / Right, or Previous / Next buttons |

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

**Compatibility:** v0.2 loads v0.1 saves and generates their missing planet
details deterministically without rewriting the original file. New saves use
format version 2 and include planet data and the selected planet. These new
saves cannot be opened by v0.1. Loading a save starts at the galaxy map; the
system/planet selection is retained. Keep a manual v0.1 snapshot if you plan
to switch between prototype versions.

## Extend the prototype

| File | Responsibility |
| --- | --- |
| `main.py` | Entry point, CLI and screenshot capture |
| `orion/app.py` | Event loop, screens and transitions |
| `orion/ui.py` | Buttons, focus styling, text and layout helpers |
| `orion/art.py` | Starfield animation, orbit guides and spacecraft |
| `orion/system_views.py` | Solar-system and planet overview layouts |
| `orion/planet_art.py` | Cached, deterministic globe drawings for six environments |
| `orion/model.py` | Game state and seeded generation; no pygame dependency |
| `orion/storage.py` | Save validation, atomic writes, settings and data paths |
| `assets/` | Bundled artwork and fonts |
| `tools/build_art.py` | Rebuild the original planet/background (optional) |
| `tests/test_prototype.py` | Save integrity and UI event-flow checks |

Keep new simulation rules in `model.py` or additional model modules. Add screens
to the UI controller as needed. The next practical increment is adding colony
management to the planet overview; fleet and tactical combat systems can follow. Bump the
save version and add migrations when the data schema changes.

## Development checks

The automated checks use Python's built-in unittest and SDL's dummy drivers:

```sh
python -m unittest discover -s tests -v
python main.py --headless --screenshot menu.png
python main.py --headless --screen galaxy --screenshot galaxy.png
python main.py --headless --screen system --screenshot system.png
python main.py --headless --screen planet --screenshot planet.png
```

`--screen` supports `menu`, `setup`, `load`, `settings`, `galaxy`, `system`,
`planet`, and `about`.
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
git switch -c feature/colony-screen
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
