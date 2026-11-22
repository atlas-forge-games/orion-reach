# Age of the Stars — v0.97.6 manual Turn News

**Dispatches from the frontier no longer opens automatically.** Open the journal
with the **Turn news** button or the **N** shortcut whenever you want to read it.

- New reports remain unread and show a gold count on the Turn news button.
- The count includes routine and urgent dispatches. It clears when you open the
  journal, and new reports received later mark the button again.
- Unread reports survive further turns and saving/loading.
- Finishing a battle, raid, first-contact greeting or council decision no longer
  sends you to Turn news. Battle reports, required decisions, research reminders
  and campaign results retain their normal screens.

## Installation

Extract this ZIP into the existing game repository, beside `orion/` and `tests/`,
and allow the included files to be replaced. Restart the game.
This is an incremental update based on **v0.97.5** (commit `6275aea`).

Existing saves work without conversion. Save format remains **65**;
no new game, dependencies or artwork are required.

## Validation

The focused interface and notification checks passed **92 tests and 19 subtests**.
They cover repeated turns with unread urgent news, the badge and mouse/keyboard
access at three window sizes, save/load, ground and space battles, first contact,
council decisions, research reminders and manual news after a campaign ends.

One older format-25 migration test also fails on unchanged v0.97.5 because its
legacy ship data is rejected; this update does not change save validation.

Run the focused checks from the repository root:

```bash
python -m pytest tests/test_quiet_notifications.py tests/test_tomb_worlds.py::NewsInterfaceTests tests/test_research_overview.py tests/test_first_contact.py tests/test_council.py tests/test_varkesh.py::VarkeshInterfaceTests tests/test_galaxy_hud.py -q
```

## Commit commands

```bash
git status
git add README.md orion/__init__.py orion/app.py orion/news.py tests/test_council.py tests/test_first_contact.py tests/test_quiet_notifications.py tests/test_research_overview.py tests/test_tomb_worlds.py tests/test_varkesh.py
git diff --cached --stat
git commit -m "Make Turn News manual and retain unread report badges"
git push
```
