"""Constructible facilities unlocked by the six research fields."""

# id, name, technology, Resources, work, outputs. Each takes its own colony slot.
FACILITIES = (
    ('advanced_factory', 'Advanced factory', 'automated_factories', 70, 42, dict(industry=6, industry_per_worker=1, energy_use=4, maintenance=3)),
    ('construction_bureau', 'Construction bureau', 'civil_engineering', 55, 33, dict(industry=5, energy_use=2, maintenance=2)),
    ('commercial_exchange', 'Commercial exchange', 'trade_algorithms', 65, 39, dict(income=6, income_per_population=.5, energy_use=2, maintenance=2)),
    ('administration_centre', 'Administration centre', 'colonial_administration', 90, 54, dict(strain_relief=15, energy_use=3, maintenance=2)),
    ('commercial_complex', 'Commercial complex', 'commerce_guilds', 135, 81, dict(income=8, income_per_population=1, energy_use=4, maintenance=4)),
    ('mineral_processor', 'Mineral processor', 'industrial_force_fields', 120, 72, dict(resources=6, energy_use=4, maintenance=3)),
    ('superconducting_foundry', 'Superconducting foundry', 'superconductors', 180, 108, dict(industry=10, industry_per_worker=2, energy_use=4, maintenance=5)),
    ('compact_reactor', 'Compact reactor', 'compact_reactors', 45, 27, dict(energy_output=18, maintenance=2)),
    ('antimatter_plant', 'Antimatter plant', 'antimatter_power', 110, 66, dict(energy_output=40, maintenance=4)),
    ('advanced_planetary_shield', 'Advanced planetary shield', 'barrier_fields', 200, 120, dict(shield_capacity=200, energy_use=12, maintenance=6)),
    ('advanced_interdictor', 'Advanced interdiction generator', 'subspace_interdiction', 190, 114, dict(interdiction_slow=40, interdiction_range=8, energy_use=12, maintenance=5)),
    ('planetary_fortress', 'Planetary fortress', 'advanced_fortifications', 100, 60, dict(defence_bonus=75, energy_use=2, maintenance=3)),
    ('enclosed_biosphere', 'Enclosed biosphere', 'colony_biospheres', 65, 39, dict(capacity_bonus=20, energy_use=3, maintenance=2)),
    ('symbiotic_farm', 'Symbiotic farm', 'symbiotic_farming', 65, 39, dict(food=8, food_per_farmer=2, energy_use=4, maintenance=2)),
    ('medical_centre', 'Population care centre', 'medical_centres', 60, 36, dict(growth_bonus=25, energy_use=3, maintenance=2)),
    ('habitat_dome', 'Habitat dome', 'habitat_shields', 85, 51, dict(adaptation=20, energy_use=4, maintenance=2)),
    ('population_centre', 'Population cultivation centre', 'colony_biogenesis', 120, 72, dict(growth_bonus=50, energy_use=5, maintenance=3)),
    ('ecology_centre', 'Ecology centre', 'ecology_networks', 100, 60, dict(food=4, capacity_bonus=10, energy_use=3, maintenance=2)),
    ('adaptation_centre', 'Adaptation centre', 'adaptive_ecology', 130, 78, dict(adaptation=35, energy_use=6, maintenance=3)),
    ('terraforming_facility', 'Terraforming facility', 'terraforming_facilities', 220, 132, dict(adaptation=60, capacity_bonus=10, energy_use=10, maintenance=5)),
    ('biosphere_restorer', 'Biosphere restorer', 'biosphere_restoration', 200, 120, dict(food=8, food_per_farmer=2, capacity_bonus=20, energy_use=8, maintenance=5)),
    ('population_engineering_centre', 'Population engineering centre', 'population_engineering', 220, 132, dict(growth_bonus=75, capacity_bonus=10, energy_use=9, maintenance=5)),
    ('analysis_lab', 'Analytical laboratory', 'research_instruments', 60, 36, dict(research=6, energy_use=3, maintenance=2)),
    ('field_lab', 'Field laboratory', 'field_laboratories', 40, 24, dict(research=3, research_per_scientist=1, energy_use=2, maintenance=1)),
    ('scientific_institute', 'Scientific institute', 'scientific_institutes', 90, 54, dict(research=6, income=3, energy_use=4, maintenance=2)),
    ('research_network_hub', 'Research network hub', 'research_networks', 95, 57, dict(research=3, research_per_scientist=2, energy_use=5, maintenance=3)),
    ('data_centre', 'Data centre', 'distributed_computing', 130, 78, dict(research=10, energy_use=5, maintenance=3)),
    ('data_archive', 'Planetary data archive', 'planetary_data_vaults', 135, 81, dict(research=6, research_per_scientist=2, energy_use=6, maintenance=3)),
    ('relic_research_centre', 'Relic research centre', 'relic_analysis', 230, 138, dict(research=18, research_per_scientist=1, energy_use=10, maintenance=6)),
)
NEW_BUILDINGS = tuple(row[0] for row in FACILITIES)
ART_FAMILIES = {
    **dict.fromkeys(('advanced_factory', 'construction_bureau', 'superconducting_foundry'), 'factory'),
    **dict.fromkeys(('commercial_exchange', 'commercial_complex', 'administration_centre'), 'trade_center'),
    'mineral_processor': 'mine', 'compact_reactor': 'fusion_plant', 'antimatter_plant': 'singularity_plant',
    'advanced_planetary_shield': 'planetary_shield', 'advanced_interdictor': 'interdictor', 'planetary_fortress': 'fortifications',
    **dict.fromkeys(('enclosed_biosphere', 'symbiotic_farm', 'medical_centre', 'habitat_dome', 'population_centre',
                    'ecology_centre', 'adaptation_centre', 'terraforming_facility', 'biosphere_restorer',
                    'population_engineering_centre'), 'hydroponic_farm'),
    **dict.fromkeys(('analysis_lab', 'field_lab', 'scientific_institute', 'research_network_hub',
                    'data_centre', 'data_archive', 'relic_research_centre'), 'research_lab'),
}

# Related facilities share the new high-resolution sprites. Placement remains
# tied to ART_FAMILIES so a different illustration never moves a saved building.
SHARED_ART = {
    **dict.fromkeys(('construction_bureau', 'superconducting_foundry', 'mineral_processor'), 'advanced_factory'),
    **dict.fromkeys(('commercial_exchange', 'commercial_complex'), 'administration_centre'),
    'compact_reactor': 'antimatter_plant',
    **dict.fromkeys(('population_centre', 'population_engineering_centre'), 'medical_centre'),
    **dict.fromkeys(('symbiotic_farm', 'habitat_dome', 'ecology_centre', 'adaptation_centre',
                    'terraforming_facility', 'biosphere_restorer'), 'enclosed_biosphere'),
    **dict.fromkeys(('analysis_lab', 'field_lab', 'scientific_institute', 'research_network_hub',
                    'data_centre', 'data_archive'), 'relic_research_centre'),
}


def install(spec_type, buildings):
    for key, name, technology, resources, work, values in FACILITIES:
        if values.get('growth_bonus'):
            description = 'Supports medical care, replication or brood development for resident species. Benefits ordinary, assembly and passive growth while powered.'
        elif values.get('adaptation'):
            description = 'Local habitat engineering reduces environmental growth penalties without changing the planet type or racial preferences. Combined adaptation is capped at 80% of the penalty.'
        elif values.get('capacity_bonus'):
            description = 'Creates additional habitable living space while powered. Does not increase mothership capacity or allow settlement of gas giants.'
        elif values.get('strain_relief'):
            description = 'Local administration reduces output losses from empire size, integration and capital distance while powered.'
        elif values.get('shield_capacity'):
            description = 'A separately constructed shield generator blocks hostile landings. Multiple generators use the strongest operating capacity; capacities do not add.'
        elif values.get('interdiction_slow'):
            description = 'A separately constructed subspace generator slows hostile final approaches. Multiple generators use the strongest operating field.'
        else:
            description = 'Research unlocks this separate facility. Requires construction and power; occupies its own slot and never upgrades other buildings automatically.'
        buildings[key] = spec_type(key, name, description, resources, work, technology=technology, **values)
