# Mothership module artwork

Thirteen separate transparent PNG sprites were generated with the built-in
image generation tool. Bronze frames, ivory panels and cyan indicators match
the Wanderer city-ark. The equipment sits on spacecraft compartments and docking
connectors rather than planetary foundations. Original PNG bytes and alpha are
preserved; the runtime caches proportionally scaled images.

`generation-prompts.json` contains the full prompts and final asset paths.
`manifest.json` records checksums, dimensions and alpha bounds. Each filename is
`<family>-v1.png`; the mapping lives in `orion/habitat_modules.py`. Advanced
industry, extraction and research reuse their family with visible tier markers.

The module renderer is selected by the habitat, regardless of its owner's race.
Planetary building sprites remain separate. Missing module images use a simple
compartment fallback so controls remain available. No costs or outputs are
encoded in the artwork. Run `python tools/preview_habitat_modules.py` to render
the actual overview, management, construction, specialist and art catalogue views.
