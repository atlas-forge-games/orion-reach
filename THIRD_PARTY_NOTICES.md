# Third-party notices

The [Orion Reach development license](LICENSE) does not replace or restrict
any permission under the following components' own licenses. This is a
source-release inventory, not a complete notice bundle for a future packaged
executable. No third-party component is relicensed by this file.

| Component | Where it is used | License / notice |
| --- | --- | --- |
| DejaVu fonts | Bundled in `assets/fonts/` | Bitstream Vera terms and public-domain DejaVu changes; preserve [the supplied notice](assets/fonts/LICENSE-DejaVu.txt). |
| pygame-ce 2.5.8 | Installed separately using `requirements.txt` | GNU LGPL 2.1; retain the upstream license, notices and applicable distribution/source obligations when packaging it. |
| Python | Installed separately to run the project | PSF and other applicable Python distribution notices; preserve them if the runtime is bundled. |
| Distant Stars | `assets/audio/distant-stars.mp3` | Suno-generated recording credited to `alexander_kies`; permissions are documented separately in [the soundtrack record](assets/audio/README.md). |

The `debian/*` GPL notice in the bundled DejaVu notice refers to Debian
packaging files. It does not relicense the font files or Orion Reach's code
under the GPL.

pygame-ce permits use with commercial programs under its license. Its wheel
may contain SDL and other libraries with separate notices. A packaged release
must inventory the exact binaries it distributes and include their licenses,
copyright notices and any required source or offers. The game's proprietary
terms do not override LGPL permissions, including applicable modification,
replacement and debugging rights.

Upstream references:

- [pygame-ce documentation and license](https://pyga.me/docs/)
- [DejaVu fonts](https://dejavu-fonts.github.io/)
- [Python license](https://docs.python.org/3/license.html)

The AI artwork provenance is recorded in [ASSET_LICENSE.md](ASSET_LICENSE.md).
References to tools or providers do not imply their endorsement of the game.
