# Consistent campaign navigation — v0.87.0

## Behaviour

All 27 campaign screens use the same navigation convention. The Galaxy screen
retains its original End turn control. Every other campaign screen has Galaxy map
on the left and End turn on the right, grouped in the lower-right corner. G opens
the galaxy map; E retains its existing turn behaviour. Escape remains contextual.
Menus, setup, the read-only encyclopedia and the standalone combat simulator keep
their own controls.

The shared component is `orion/campaign_navigation.py`. It also owns the campaign
screen registry, re-exported from `orion.app` for existing callers. `App.draw_frame`
adds the controls after the view and before modal dialogs. Individual views no
longer draw their own campaign End turn or separate Galaxy map buttons.

The component uses the existing native Canvas and logical coordinates, including
the responsive Empire layout. At enlarged interface sizes, the existing scrolling
and keyboard-focus behaviour reveal the footer. The map button preserves the
selected system, planet, sidebar page and local return history. Leaving an idle
colony still selects Trade Goods through the ordinary screen transition.

Required combat, first-contact acknowledgements, council votes, ground reports,
completed campaigns and busy turns disable the relevant campaign controls. Hover
over a disabled control to read its reason. Landing plans can be left without
launching an assault. The tactical action is labelled End combat turn to distinguish
it from advancing the campaign. No simulation rule or save-format change is made.

## Layout changes

- Empire removes the top-level Galaxy map link and reserves sufficient footer
  height for its budget, Menu, Save and the shared actions.
- Planet and mothership views keep a contextual System link near the title.
  Planet administration and population controls fit above the campaign actions.
- Production keeps its Colony return by the catalogue; system cycling moves next
  to the system heading. Ship-design actions remain together on the lower left.
- Pagination, observer navigation, combat camera controls and mandatory decision
  actions leave the shared lower-right area clear.
- Long footer hints use the existing full-text hover treatment.

## Validation

The ten navigation tests cover all 27 campaign screens, including populated
screens, observers, motherships, black holes and mandatory decisions. They verify
one unobstructed pair per non-galaxy view, labels and order, mouse input at 100%
and 175%, G and contextual return behaviour, selection preservation, production
prompts, single-turn advancement, repeated-key suppression, modal guards, landing
plan cleanup and simulator isolation.

The 68 representative screen/dialog states render at 1440×900 / 100%,
1280×800 / 175% and 1920×1080 / 125% in the existing global-readability suite.
Native screenshots were inspected, and the text-layout comparison found no new
visible text collisions. Background text behind modal panels is excluded from
that assessment.

Regression checks were compared with an unchanged v0.86.0 snapshot:

- The core run passed 120 of 123 tests. Its three failures also occur on v0.86.0:
  old workforce-save migration expectations, a mothership label inspection, and
  an obsolete production-save version assertion.
- The view run passed 95 of 104 tests, including all ten navigation tests. Its
  eight failures and one error also occur on the baseline: outdated combat and
  exploration expectations, statistics hover coordinates and a missing legacy
  research card fixture. The corresponding baseline run passed 84 of 94 tests.
  The additional improvement comes from correcting the research UI test's click
  mapping to use the actual Canvas scale for the responsive Empire view.
- Existing navigation tests now use the shared control identifiers. Local System
  returns and the completed-campaign report return are still tested separately.
- All three surface-placement UI checks pass in a real letterboxed window;
  the placement fixture now derives its click from the displayed landscape size.
  All five encyclopedia checks pass.
- Python compilation and `git diff --check` pass.

Run the focused navigation checks with:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=.:tests \
  python3 -m unittest test_campaign_navigation
```

Run `python tools/preview_all_screens.py --output screenshots/navigation-preview`
to reproduce the representative screens. No player saves are opened by the
fixtures, and this update does not commit or push repository changes.
