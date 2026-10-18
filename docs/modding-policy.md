# Modding the development version

This page explains section 3 of the [development license](../LICENSE).
The license controls if a summary here is inconsistent with it.

You can inspect the source, experiment with balance, design ships and scenarios,
use the editors and privately change your copy of the game. You do not have to
publish private changes.

For public sharing, distribute a free add-on or patch that needs a lawful copy
of the game. Examples include your own scenario, a balance patch, your own
replacement art, or a source diff with only the context needed to apply it.
Provide installation instructions and the supported game version. Keep
copyright/license notices and identify the mod as unofficial.

For changes to existing source or game data, a Git patch is a suitable format:

```bash
git diff -- orion/combat.py > my-combat-mod.patch
```

List only the files you intend to share. Include the project license with a
patch containing project material. New files containing your original work
may be supplied alongside a patch; a full copy of an existing game file is
not a substitute for a patch under this permission.

Recipients can check and apply a patch in their own game checkout:

```bash
git apply --check my-combat-mod.patch
git apply my-combat-mod.patch
```

Free mod sharing does not authorize uploading the entire game, bundling the
game's artwork or soundtrack, selling a mod, or releasing a standalone clone
using protected project material. Written permission is needed for those uses,
unless another applicable license or the law already permits them. Public
GitHub forks remain subject to the permissions in GitHub's terms.

You retain rights in your original mod contributions. Submitting a patch does
not automatically transfer ownership to the project. Before incorporating an
outside contribution into a commercial release, the maintainer should obtain
clear permission covering that use.
