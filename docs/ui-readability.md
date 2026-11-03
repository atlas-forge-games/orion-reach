# Readable interface — v0.86.0

## Global typography and layout

The readable type system now covers every game screen, all dialogs, the combat
simulator and the balance editor. The shared logical minimum is 14 pixels;
normal information and primary values retain their larger role sizes. Both
measurement and rendering apply the same floor. Letter spacing on formerly tiny
labels is limited to one logical pixel, and paragraphs reserve enough line height.
Long unbroken names wrap instead of running outside the available width.

Logical font sizing is separate from native pixel rasterization: a logical 14px
label in a small window must not have the minimum applied a second time to its
physical font. The map's colored label bands now clip native text, and menu text,
chart labels, building captions and the intro no longer stretch rendered glyphs.
The standalone balance editor also draws directly at its window scale.

Galaxy resource cards use their full width for captions. The system summary uses
two columns, and planet lists use a compact single line when there is insufficient
height for two readable lines. Construction lists have more line spacing; research
choices reserve separate space for their status. Combat chance rows use readable
spacing and a full-text summary when a volley has many weapon types. Small controls
fit their labels without dropping below the minimum size.

An ellipsis retains the original text. Hover for 0.4 seconds to display it in an
opaque panel inside the visible, scrolled viewport. Tooltips do not add controls or
change game state. Background labels are excluded while a modal or pause menu is
open. The missing initial colony catalogue page is also restored, fixing the
legacy colony screen's opening error.

The existing 100–175% interface setting, native canvas, scrollbars, coordinate
mapping and responsive Empire layout remain in use. Other screens preserve their
layout with the targeted spacing changes above and scrolling at larger UI sizes.
The balance editor follows its window size; it has no separate zoom preference.
Game rules, balance data and save format 60 are unchanged.

## v0.86.0 validation

Base: v0.85.0, repository commit `516525b` (the previous readability release).

- Eight new tests pass. They cover readable font metrics, native glyphs at four
  fractional scales, small control labels, long-word wrapping, preserved full
  labels and clipped hover regions, delayed tooltips in a scrolled enlarged view,
  all game screens/dialog fixtures, and native editor resizing/input coordinates.
- The preview fixtures render 68 states, including all 27 game screens, menus,
  five settings pages, populated construction and specialist panels, research and
  economy dialogs, first contact, council voting, gas giants, black holes, mobile
  habitats and combat. Each is exercised at 1440×900 / 100%, 1280×800 / 175% and
  1920×1080 / 125%. Turn counters and treasury, resources and banked research do
  not change during rendering. The simulator and editor were captured separately.
- Core regression selection: 146 tests, 145 passed. The remaining tactical save
  migration assertion expects version 53 while the game uses version 60; it is
  unchanged from the baseline.
- Wider screen selection: 189 tests, 176 passed. All 13 remaining failures/errors
  also reproduce with the same selection on v0.85.0 (which has 16). They concern
  older balance/save fixtures, a statistics hover assertion and an AI movement
  assertion. Three colony-opening errors in this selection and four in the core
  selection are fixed by initializing the catalogue page. No new failures remain.
- Real captures were inspected; measurements checked expanded text against panel
  bounds and compared new text collisions with the baseline. Compile checks and
  `git diff --check` pass.

```sh
python -m unittest discover -s tests -p test_global_readability.py
python -m unittest discover -s tests -p test_ui_readability.py
python tools/preview_all_screens.py --output /tmp/orion-screens
python tools/preview_all_screens.py --width 1280 --height 800 --scale 175 --output /tmp/orion-large-text
```

## Previous release: v0.85.0

### Player-visible changes

- Empire labels use 16–18 logical pixels and key values use 28. Text is drawn at
  its actual display size, including non-integer window scales.
- Resource cards form a responsive grid of up to four columns. Secondary text
  uses light grey, values use brighter cyan, and information has solid dark panels.
- Colony rows are taller. Narrow layouts switch to labelled cards while retaining
  population, food, industry, credits, research, slots and construction details.
- Pagination adapts to available height. Filters, numeric sorting, shortcuts,
  colony links, debt warnings, upkeep and budget information remain available.
- Settings → Interface offers 100%, 125%, 150% and 175% interface sizes. Preferences
  apply immediately and persist across restarts. Ctrl + / Ctrl − changes size;
  Ctrl 0 resets to 100%.
- Empire reflows to the available width. Other screens keep their existing layouts
  and can be scrolled when enlarged. Drag the scrollbars or use Shift + wheel;
  a wheel over an overflowing Empire page scrolls vertically. Page Up / Page Down
  continue to change colony pages. Keyboard focus scrolls its control into view.

### Rendering and input

`orion.display.Canvas` stores pixels at the viewport's native resolution while
exposing logical coordinates to the existing scene code. The shared `text()`
helper rasterizes glyphs at the final font size; `present()` no longer rescales
those glyphs as part of a completed frame. Existing raster illustrations remain
bitmaps. Panels and pygame drawing primitives transform alongside the text.

A pygame drawing adapter dispatches only Canvas targets; ordinary pygame surfaces,
including off-screen artwork, masks and effects, retain their usual behaviour.
DisplayView owns offsets, scrollbars and logical mouse conversion. Resizes refresh
rendering before input uses the new viewport. Standard confirmation dialogs fit
within the visible region of a scrolled interface.

This is an interface change. Game rules, save format 60, campaign contents and
research/economy calculations are unchanged. Old settings files default to 100%.

### Validation

Base: repository commit `d545cc3689f426bc498321a733f3ce1ae8415682` (v0.84.0).

- Twelve new tests pass: direct native font rasterization, ordinary-surface parity,
  clipping, panel contrast, all four UI sizes at 1280×800 / 1440×900 / 1920×1080,
  no overlapping controls, complete sorted pagination, scaled/scrolled colony
  clicks, keyboard focus, preference persistence and invalid values, scrollbar
  dragging and wheel navigation, and reachability on legacy screens.
- Broader regression run: 138 tests, 133 passed. The same five failures are present
  in the untouched base with the equivalent 126-test selection: four legacy colony
  screen tests access the already-missing `colony_catalog_page` attribute; one
  tactical migration test still expects save version 53 instead of 60. These are
  not introduced by this update and are left outside this interface change.
  An isolated combat-zoom test also exposes an existing order-dependent fixture
  assumption (15 hull versus the current 30); it fails identically on the base.
- Existing assertions were updated only for intentional changes: dynamic Empire
  page capacity, the additional settings key, scaled click coordinates, and exact
  palette checks at 1:1 resolution (avoiding antialiasing-dependent color equality).
- Real screenshots were inspected at 100%, 125% and 175%, including the scrolled
  footer, settings, confirmation dialog and existing galaxy view. The preview
  script reproduces five captures using temporary data.
- Compile checks and `git diff --check` pass. A short headless 1920×1080 run measured
  approximately 8 ms/frame for Empire and 12 ms/frame for the galaxy on this test
  machine; these are smoke measurements, not a hardware-independent guarantee.

From the project root:

```sh
python -m unittest discover -s tests -p test_ui_readability.py
python tools/preview_readability.py
```
