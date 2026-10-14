# Orion Reach — complete colony building artwork

Twenty original building illustrations share one architectural style: pale
warm-gray ceramic and concrete, charcoal navy metal, muted bronze fittings,
restrained cyan lights, neutral light from upper left and an elevated
three-quarter view. The built-in image-generation tool produced each building
as a separate transparent PNG. Files preserve the generated image bytes.

Version 0.38.1 adds fourteen images to the original six. Every constructible
catalogue building now has an illustration, alongside the headquarters,
shipyard and special Ascension Gate.

| Building | File | Distinctive features |
| --- | --- | --- |
| Headquarters palace | `headquarters-v1.png` | Tall civic command tower and terraced wings |
| Factory | `factory-v1.png` | Production halls, exhaust stacks and gantry |
| Shipyard | `shipyard-v1.png` | Open assembly hangar and spacecraft slipway |
| Research lab | `research_lab-v1.png` | Scientific glass dome and instruments |
| Trade centre | `trade_center-v1.png` | Commercial atrium and freight bays |
| Mining complex | `mine-v1.png` | Extraction headframe and processing equipment |
| Hydroponic farm | `hydroponic_farm-v1.png` | Glass greenhouse halls and visible crops |
| Barracks | `barracks-v1.png` | Armored accommodation wings and drill courtyard |
| Fortifications | `fortifications-v1.png` | Heavy connected bastions and central bunker |
| Missile base | `missile_base-v1.png` | Open vertical launch silos and tracking radar |
| Planetary shield | `planetary_shield-v1.png` | Three emitter pylons and cyan shield field |
| Sensor array | `sensor_array-v1.png` | Large tracking dish and antenna masts |
| Jump gate | `jump_gate-v1.png` | Upright oval transit ring and service buttresses |
| Interdiction generator | `interdictor-v1.png` | Tapered tower and three violet induction rings |
| Solar array | `solar_array-v1.png` | Blue photovoltaic panels and inverter building |
| Geothermal plant | `geothermal_plant-v1.png` | Wellheads, large heat pipes and turbine hall |
| Fusion plant | `fusion_plant-v1.png` | Cylindrical containment vessel and cooling modules |
| Thermal backup plant | `thermal_plant-v1.png` | Compact furnace, fuel hopper and two stacks |
| Singularity plant | `singularity_plant-v1.png` | Spherical containment chamber and support arches |
| Ascension Gate | `ascension_gate-v1.png` | Monumental scientific gateway and luminous aperture |

## Integration

The existing `orion/building_art.py` loader finds each `<building_id>-v1.png`,
aligns foundations using alpha bounds and caches proportionally scaled sprites.
The Colony catalogue, building slots, production lists and planet surface use
these images. `orion/victory_view.py` uses the Ascension Gate in Objectives and
victory results. Headquarters and shipyard artwork represents existing colony
capabilities; the special gate retains its separate scientific-victory rules.

Generated art contains no interface labels. The game draws labels, selection,
disabled states and construction previews independently. Preserve the alpha
channel and aspect ratio; never remove a guessed background color. Existing
procedural fallbacks remain available if an image is missing or unreadable.

`manifest.json` records all filenames, dimensions, checksums and alpha bounds.
`generation-prompts.json` contains the complete prompt set and generation mode.
Run `python tools/preview_building_art.py` from the repository root to render
`screenshots/building_art_catalogue.png` with the game's normal artwork loader.

The original six PNGs are unchanged. This artwork update changes no building
statistics, research, game rules or save data.

Version 0.60.1 adds `space_hub-v1.png`: a travelers’ glass lounge, terminal wings, landing pad and communications mast. Generated with the built-in image tool, on a transparent background, in the existing colony architectural style. Prompt recorded in `space_hub-prompt.txt`.
