# Legendary artifact concept artwork

Ten original 1254 × 1254 PNG illustrations, generated individually with the
built-in image-generation tool. Their original bytes are preserved;
`generation-prompts.json` records the prompts and `manifest.json` records the
filenames, dimensions and SHA-256 hashes.

These are encyclopedia illustrations only. The proposed lore and effects live
in `orion/encyclopedia_artifacts.py`, which is imported by the reference catalog.
They are not registered as discoveries, equipment, buildings or gameplay bonuses.

The encyclopedia loads images on demand, scales them proportionally in memory
and keeps the artwork and planned-content notice visible while the text scrolls.
If an image is missing, the article remains readable with a labeled placeholder.

Run `python tools/preview_artifact_encyclopedia.py` to capture the flagship and
capital reference entries in the real interface.
