"""Six fields with three independent, exclusive discoveries in each tier.

IDs remain stable so old campaign profiles can retain their original tree.
Higher tiers never require a particular earlier choice.
"""
from dataclasses import replace

FIELDS = (
    ('power', 'Energy technology', 'Reactors, shields and energy infrastructure.'),
    ('physics', 'Weapons technology', 'Beams, torpedoes, targeting and countermeasures.'),
    ('starships', 'Spaceflight', 'Engines, sensors, hulls and ship modules.'),
    ('construction', 'Industry', 'Factories, mining, commerce and construction.'),
    ('biology', 'Biotechnology', 'Population, habitats and planetary ecosystems.'),
    ('computers', 'Xenoscience', 'Laboratories, alien cultures, anomalies and relics.'),
)

TIERS = {
    'power': (
        ('compact_reactors', 'radiation_shields', 'fusion_grids'),
        ('fusion_power', 'planetary_shielding', 'gravity_wells'),
        ('antimatter_power', 'regenerative_shields', 'hardened_shields'),
        ('field_stabilization', 'barrier_fields', 'subspace_interdiction'),
    ),
    'physics': (
        ('targeting_computers', 'orbital_defense_systems', 'advanced_fortifications'),
        ('pulse_beams', 'fusion_torpedoes', 'electronic_countermeasures'),
        ('ion_beams', 'precision_beam_optics', 'advanced_flak'),
        ('quantum_optics', 'mirv_torpedoes', 'predictive_fire_control'),
        ('plasma_beams', 'siege_weapons', 'interceptor_drones'),
        ('graviton_beams', 'torpedo_guidance', 'bomber_drones'),
        ('particle_beams', 'phased_beams', 'quantum_targeting'),
        ('heavy_beam_mounts', 'disruptor_beams', 'antimatter_torpedoes'),
    ),
    'starships': (
        ('destroyer_hulls', 'ion_drives', 'lightweight_alloys'),
        ('cruiser_hulls', 'fusion_drives', 'deep_space_radar'),
        ('drone_carriers', 'composite_structures', 'reinforced_armor'),
        ('battleship_hulls', 'cryogenic_fuel_tanks', 'long_range_sensors'),
        ('automated_damage_control', 'colonial_navigation', 'deep_space_logistics'),
        ('titan_hulls', 'antimatter_fuel_tanks', 'subspace_scanners'),
        ('jump_gates', 'spatial_compression_tanks', 'advanced_jump_drives'),
    ),
    'construction': (
        ('automated_factories', 'civil_engineering', 'trade_algorithms'),
        ('prefabricated_structures', 'orbital_assembly', 'colonial_administration'),
        ('planetary_automation', 'deep_core_drills', 'commerce_guilds'),
        ('automated_refineries', 'industrial_force_fields', 'modular_spaceframes'),
        ('molecular_shipbuilding', 'mass_ship_production', 'superconductors'),
        ('nanostructured_materials', 'stellar_forge_engineering', 'asteroid_engineering'),
    ),
    'biology': (
        ('colony_biospheres', 'symbiotic_farming', 'medical_centres'),
        ('habitat_shields', 'thermal_barriers', 'barren_habitats'),
        ('colony_biogenesis', 'ecology_networks', 'adaptive_ecology'),
        ('terraforming_facilities', 'biosphere_restoration', 'population_engineering'),
    ),
    'computers': (
        ('research_instruments', 'cultural_exchange', 'field_laboratories'),
        ('planetary_observatories', 'scientific_institutes', 'research_networks'),
        ('distributed_computing', 'gravitic_mapping', 'planetary_data_vaults'),
        ('quantum_research_archives', 'event_horizon_navigation', 'relic_analysis'),
    ),
}

NEW_TECHNOLOGIES = {
    'antimatter_power': ('Antimatter Power', 'Unlock antimatter plants: 40 local energy with 4 CR/turn upkeep.', {}),
    'advanced_jump_drives': ('Advanced Jump Drives', '+75% ship speed on new voyages; stacks with other drive research.', {'ship_speed': 75}),
    'stellar_forge_engineering': ('Stellar Forge Engineering', 'Unlock the Stellar Forge system project. Its stages accelerate ship construction in the host system.', {}),
    'asteroid_engineering': ('Asteroid Engineering', 'Unlock the Asteroid Mining Network system project. Its stages deliver Resources to the empire.', {}),
    'medical_centres': ('Population Medicine', 'Unlock population care centres: +25% local growth, including assembly and passive growth. Adapted to each race.', {}),
    'barren_habitats': ('Radiation-Proof Habitats', 'Colony ships can settle barren worlds. Racial environment preferences still apply.', {'barren': 1}),
    'adaptive_ecology': ('Adaptive Ecology', 'Unlock adaptation centres: remove 35% of the local environmental growth penalty.', {}),
    'terraforming_facilities': ('Planetary Terraforming', 'Unlock terraforming facilities: remove 60% of the environmental growth penalty and add 10% population capacity. Local engineering preserves the planet type.', {}),
    'biosphere_restoration': ('Biosphere Restoration', 'Unlock biosphere restorers: 8 food, +2 food/farmer and +20% local population capacity.', {}),
    'population_engineering': ('Population Engineering', 'Unlock population engineering centres: +75% local growth, including assembly and passive growth, and +10% population capacity.', {}),
    'relic_analysis': ('Relic Analysis', 'Unlock relic research centres: 18 RP and +1 RP/scientist. Alien-material research requires an operating facility.', {}),
}

# Economic discoveries grant construction access. No free refit of old buildings.
REVISIONS = {
    'automated_factories': ('Advanced Factories', 'Unlock advanced factories: 6 industry +1 per worker, using 4 energy and 3 CR/turn.', {}),
    'civil_engineering': ('Civil Engineering', 'Unlock construction bureaus: 5 industry without a worker bonus; 2 energy and 2 CR/turn.', {}),
    'trade_algorithms': ('Commercial Exchange', 'Unlock commercial exchanges: 6 credits +0.5 per inhabitant; 2 energy and 2 CR/turn.', {}),
    'colonial_administration': ('Colonial Administration', 'Unlock administration centres: reduce local administrative strain by 15 percentage points while powered; 3 energy and 2 CR/turn.', {}),
    'planetary_automation': ('Robotic Manufacturing', 'Unlock robotic factories: 8 industry +2 per worker, using 6 energy and 4 CR/turn. Existing factories are unchanged.', {}),
    'deep_core_drills': ('Deep-Core Extraction', 'Unlock deep-core mines: 4 Resources +2 per miner, scaled by richness, using 5 energy and 3 CR/turn. Also unlock geothermal plants.', {}),
    'commerce_guilds': ('Commercial Complexes', 'Unlock commercial complexes: 8 credits +1 per inhabitant; 4 energy and 4 CR/turn.', {}),
    'automated_refineries': ('Automated Refineries', 'Unlock automated refineries: 7 Resources +3 per miner, scaled by richness; 8 energy and 5 CR/turn.', {}),
    'industrial_force_fields': ('Containment Processing', 'Unlock mineral processors: 6 Resources, scaled by richness; 4 energy and 3 CR/turn. No miner bonus.', {}),
    'superconductors': ('Superconducting Foundries', 'Unlock superconducting foundries: 10 industry +2 per worker; 4 energy and 5 CR/turn.', {}),
    'nanostructured_materials': ('Molecular Assembly', 'Unlock nanofactories: 14 industry +3 per worker, using 10 energy and 7 CR/turn. Existing factories are unchanged.', {}),
    'compact_reactors': ('Compact Reactors', 'Unlock compact reactor buildings: 18 local energy, using no Resources, with 2 CR/turn upkeep.', {}),
    'radiation_shields': ('Ship Shield Generators', 'Unlock ship shield modules. Shields absorb beam damage; point defence counters torpedoes. Barren settlement has its own Biotechnology discovery.', {}),
    'fusion_grids': ('Thermal Backup Power', 'Unlock thermal backup plants: up to 24 local energy. Consume Resources only when needed, at 4 energy per Resource.', {}),
    'planetary_shielding': ('Planetary Shielding', 'Unlock planetary shield generators: 100 shield points, 8 energy and 4 CR/turn. Blocks hostile landings until suppressed.', {}),
    'gravity_wells': ('Gravity-Well Generators', 'Unlock interdiction generators: slow hostile final approaches by 25% within 5 ly; 8 energy and 3 CR/turn.', {}),
    'barrier_fields': ('Advanced Planetary Shielding', 'Unlock advanced planetary shield generators: 200 shield points, 12 energy and 6 CR/turn. Does not upgrade existing generators.', {}),
    'subspace_interdiction': ('Subspace Interdiction', 'Unlock advanced interdiction generators: 40% hostile slowdown within 8 ly; 12 energy and 5 CR/turn. Existing generators are unchanged.', {}),
    'advanced_fortifications': ('Planetary Fortresses', 'Unlock planetary fortresses: +75% defending ground firepower, 2 energy and 3 CR/turn. Existing fortifications are unchanged.', {}),
    'quantum_optics': ('Quantum Beam Batteries', 'Unlock quantum beam batteries: 14 base damage, scaled by hull size. Standard frigates and carriers gain 7-damage beams.', {'beam_level': 1}),
    'colony_biospheres': ('Enclosed Biospheres', 'Unlock enclosed biospheres: +20% local population capacity while powered; 3 energy and 2 CR/turn.', {}),
    'symbiotic_farming': ('Symbiotic Agriculture', 'Unlock symbiotic farms: 8 food +2 per farmer; 4 energy and 2 CR/turn.', {}),
    'habitat_shields': ('Protected Habitats', 'Unlock habitat domes: remove 20% of the local environmental growth penalty; 4 energy and 2 CR/turn.', {}),
    'colony_biogenesis': ('Population Cultivation', 'Unlock population cultivation centres: +50% local growth, including assembly and passive growth; 5 energy and 3 CR/turn.', {}),
    'ecology_networks': ('Ecological Networks', 'Unlock ecology centres: 4 food and +10% local population capacity; 3 energy and 2 CR/turn.', {}),
    'research_instruments': ('Analytical Laboratories', 'Unlock analytical laboratories: 6 RP without a scientist bonus; 3 energy and 2 CR/turn.', {}),
    'field_laboratories': ('Field Laboratories', 'Unlock field laboratories: 3 RP +1 per scientist; 2 energy and 1 CR/turn.', {}),
    'planetary_observatories': ('Advanced Laboratories', 'Unlock advanced research labs: 8 RP +2 per scientist; 7 energy and 4 CR/turn.', {}),
    'scientific_institutes': ('Scientific Institutes', 'Unlock scientific institutes: 6 RP and 3 credits, without a scientist bonus; 4 energy and 2 CR/turn.', {}),
    'research_networks': ('Research Networks', 'Unlock research network hubs: 3 RP +2 per scientist; 5 energy and 3 CR/turn. Also unlock combat scanner modules.', {}),
    'distributed_computing': ('Distributed Computing', 'Unlock data centres: 10 RP without a scientist bonus; 5 energy and 3 CR/turn.', {}),
    'planetary_data_vaults': ('Planetary Data Vaults', 'Unlock planetary data archives: 6 RP +2 per scientist; 6 energy and 3 CR/turn.', {}),
    'quantum_research_archives': ('Quantum Research', 'Unlock quantum research labs: 14 RP +3 per scientist; 11 energy and 7 CR/turn.', {}),
}

BRANCH_MERGES = {'fields': 'power', 'materials': 'construction', 'society': 'computers'}


def install(branch_type, technology_type, branches, technologies):
    branches.clear()
    branches.update({key: branch_type(key, name, description) for key, name, description in FIELDS})
    for key, (name, description, effects) in NEW_TECHNOLOGIES.items():
        technologies[key] = technology_type(key, 'power', 1, name, description, tuple(effects.items()))
    for key, (name, description, effects) in REVISIONS.items():
        technologies[key] = replace(technologies[key], name=name, description=description, effects=tuple(effects.items()))
    for branch, tiers in TIERS.items():
        for tier, triple in enumerate(tiers, 1):
            for order, key in enumerate(triple):
                technologies[key] = replace(technologies[key], branch=branch, tier=tier, order=order)


def is_modern(branches):
    return set(branches) == {key for key, _, _ in FIELDS}
