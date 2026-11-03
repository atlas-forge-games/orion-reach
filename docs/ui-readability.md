# Readable interface — v0.85.0

## Player-visible changes

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

## Rendering and input

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

## Validation

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
