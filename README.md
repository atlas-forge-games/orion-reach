# Age of the Stars — v0.98.5 setup cleanup

Removed the explanatory text from the second expedition setup page: the subtitle,
seed hint, fog-of-war hint, pirate description, civilization-count summary,
starting-fleet footer and descriptions beneath the three victory toggles.
Equivalent observer, solo and alternate-race helper text is also omitted.
The controls, labels, portraits, settings and game rules remain in place.

## Install

Extract this incremental ZIP over your existing **v0.98.4** repository, beside
`orion/`, replacing the included files. Restart the game. No new dependencies
or save-format changes are needed.

## Validation

Four existing interface checks pass: normal setup and victory-option launch,
observer setup with victories disabled, all-civilization launch, and switching
between observer and normal race setup. The cleaned setup screen was rendered
and visually inspected. Whitespace checks also pass.

## Commit commands

From your repository root after extracting the update:

```bash
git status
git add README.md orion/setup_view.py orion/__init__.py
git diff --cached --stat
git commit -m "Remove extra explanatory text from expedition setup (v0.98.5)"
git push
```
