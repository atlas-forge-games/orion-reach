# Gas giants — v0.79

Gas giants are large atmospheric worlds without surface settlement.
This document describes their v0.79 introduction. Version 0.81 adds
[orbital industry](gas-giant-stations.md), including gas extraction, shared
system energy and research. Atmospheric colonies and moon colonization remain
outside the current implementation.

## Rules

| Property | Gas giant behavior |
| --- | --- |
| Planet type | Gas Giant |
| Generated size / gravity | Huge / High |
| Population and building capacity | 0 |
| Growth efficiency | 0 for every species |
| Colonization | Unavailable to every species, regardless of technology |
| Surface outposts | Unavailable |
| Buried Remnant tombs | Excluded |
| Exploration and surveys | Normal visibility and persistent survey rules |

Lithar, Nexus and Aetheri can settle every solid-surface biome under their
existing rules, but cannot settle gas giants. Changing generic habitability in
a custom balance profile does not bypass this restriction. Existing shipboard
habitats remain separate from planetary settlement and retain their rules.

AI colony and surface-outpost target selection excludes gas giants. Rejected
orders leave the colony/outpost ship and campaign state unchanged. Save
validation rejects colonies, surface outposts and tombs attached to gas giants.

## New-galaxy generation

After existing worlds, home systems and special sites are initialized, each
eligible system has a deterministic 35% chance of receiving one additional gas
giant. Eligibility requires at least one world, fewer than eight worlds, no
starting settlement or habitat, and no existing gas giant. Empty systems and
black holes stay empty. There can never be more than eight worlds in a system.

The gas giant occupies the next planet ID and the outermost orbit, at 1.6–2.0
times the previous outer world's orbit. It receives the system's next Roman
numeral. An orbit exceeding the existing 500 AU save limit is skipped.

Independent per-system random streams preserve existing star coordinates,
terrestrial properties, racial home worlds, guardian prizes, pirate sites and
tomb locations. No existing planet is converted or replaced. Starting systems
retain their established layout. Repeating the seeding pass does not add a
second giant to a system.

## Presentation

System diagrams show a larger globe with cloud belts and oval storms. Its
full disc is clickable without overlapping adjacent planet targets. The
galaxy sidebar labels it as not colonizable rather than showing ordinary
mineral suitability.

Opening the planet shows an atmospheric survey, a high-resolution cloud-deck
panorama and disabled Colonize / Build outpost controls. Worker assignments,
surface building prompts and growth percentages are omitted. The globe and
cloud fallback are seeded, code-native artwork; the panorama was created with
the built-in image-generation tool.

Project asset: `assets/planet_surfaces/gas-giant-v1.png` (2170 × 725 RGB PNG).
The exact generation prompt is stored in
`assets/planet_surfaces/generation-prompts.json`; its checksum and dimensions
are in the adjacent manifest.

## Compatibility

New saves use version 56 and balance profiles use version 20. Older profiles
gain the Gas Giant biome metadata while retaining custom terrestrial values
and species preferences. Existing saves load without regenerating worlds or
adding gas giants, and loading does not rewrite the source file. Start a new
campaign to see naturally generated giants.

Gas giants are outside the eight solid-surface environment preferences, since
their settlement restriction is absolute in this version. The complete
species preference matrix from v0.78 remains unchanged.

See [validation](gas-giant-validation.md) for tests and baseline limitations.
