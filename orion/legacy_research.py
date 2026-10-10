"""Frozen pre-v0.37 research rules, used only to validate older discoveries."""

# identifier: (branch, tier, RP cost, exclusive, named prerequisites)
LEGACY_TECHNOLOGIES = {
    'automated_factories': ('construction', 1, 40, True, ()),
    'civil_engineering': ('construction', 1, 40, True, ()),
    'prefabricated_structures': ('construction', 2, 100, True, ()),
    'orbital_assembly': ('construction', 2, 100, True, ()),
    'ion_drives': ('power', 1, 40, True, ()),
    'compact_reactors': ('power', 1, 40, True, ()),
    'fusion_drives': ('power', 2, 100, True, ()),
    'fusion_grids': ('power', 2, 100, True, ()),
    'research_instruments': ('physics', 1, 40, True, ()),
    'field_laboratories': ('physics', 1, 40, True, ()),
    'planetary_observatories': ('physics', 2, 100, True, ()),
    'quantum_optics': ('physics', 2, 100, True, ()),
    'radiation_shields': ('fields', 1, 40, True, ()),
    'habitat_shields': ('fields', 1, 40, True, ()),
    'thermal_barriers': ('fields', 2, 100, True, ()),
    'industrial_force_fields': ('fields', 2, 100, True, ()),
    'deep_core_drills': ('materials', 1, 40, True, ()),
    'lightweight_alloys': ('materials', 1, 40, True, ()),
    'superconductors': ('materials', 2, 100, True, ()),
    'composite_structures': ('materials', 2, 100, True, ()),
    'colony_biospheres': ('biology', 1, 40, True, ()),
    'symbiotic_farming': ('biology', 1, 40, True, ()),
    'colony_biogenesis': ('biology', 2, 100, True, ()),
    'ecology_networks': ('biology', 2, 100, True, ()),
    'research_networks': ('computers', 1, 40, True, ()),
    'trade_algorithms': ('computers', 1, 40, True, ()),
    'distributed_computing': ('computers', 2, 100, True, ()),
    'planetary_automation': ('computers', 2, 100, True, ()),
    'colonial_administration': ('society', 1, 40, True, ()),
    'scientific_institutes': ('society', 1, 40, True, ()),
    'commerce_guilds': ('society', 2, 100, True, ()),
    'cultural_exchange': ('society', 2, 100, True, ()),
    'ascension_theory': ('ascension', 3, 500, True, ()),
    'fusion_power': ('power', 3, 120, False, ()),
    'advanced_fortifications': ('construction', 3, 120, False, ()),
    'orbital_defense_systems': ('physics', 3, 120, False, ()),
    'planetary_shielding': ('fields', 3, 120, False, ()),
    'barrier_fields': ('fields', 4, 220, False, ('planetary_shielding',)),
    'siege_weapons': ('physics', 4, 220, False, ('orbital_defense_systems',)),
    'deep_space_radar': ('computers', 3, 120, False, ()),
    'long_range_sensors': ('computers', 4, 220, False, ('deep_space_radar',)),
    'subspace_scanners': ('computers', 5, 360, False, ('long_range_sensors',)),
    'colonial_navigation': ('computers', 3, 120, False, ()),
    'jump_gates': ('power', 4, 220, False, ('colonial_navigation',)),
    'gravity_wells': ('fields', 3, 120, False, ()),
    'subspace_interdiction': ('fields', 4, 220, False, ('gravity_wells',)),
    'field_stabilization': ('power', 3, 120, False, ()),
    'targeting_computers': ('computers', 3, 120, False, ()),
    'predictive_fire_control': ('computers', 4, 220, False, ('targeting_computers',)),
    'quantum_targeting': ('computers', 5, 360, False, ('predictive_fire_control',)),
    'precision_beam_optics': ('physics', 3, 120, False, ()),
    'torpedo_guidance': ('computers', 4, 220, False, ('targeting_computers',)),
    'electronic_countermeasures': ('computers', 3, 120, False, ()),
}


def _available(identifier, completed):
    if not isinstance(identifier, str) or identifier not in LEGACY_TECHNOLOGIES or identifier in completed:
        return False
    branch, tier, _, exclusive, requires = LEGACY_TECHNOLOGIES[identifier]
    known = [LEGACY_TECHNOLOGIES[t] for t in completed]
    if identifier == "ascension_theory":
        return sum(t[1] == 2 for t in known) == 8
    if not exclusive:
        return any(t[0] == branch and t[1] <= 2 for t in known) and all(t in completed for t in requires)
    if any(t[0] == branch and t[1] == tier and t[3] for t in known):
        return False
    return tier == 1 or any(t[0] == branch and t[1] == tier-1 for t in known)


def validate_legacy(completed, active=None, progress=0):
    """Reject malformed old saves without imposing the replacement tier layout."""
    if not isinstance(completed, list) or len(completed) > len(LEGACY_TECHNOLOGIES):
        raise ValueError("Invalid legacy discoveries")
    known = []
    for identifier in completed:
        if not _available(identifier, known):
            raise ValueError("Invalid legacy technology sequence")
        known.append(identifier)
    if type(progress) is not int or progress < 0:
        raise ValueError("Invalid legacy progress")
    if active is None:
        if progress:
            raise ValueError("Legacy progress without a project")
    elif not _available(active, known) or progress >= LEGACY_TECHNOLOGIES[active][2]:
        raise ValueError("Invalid legacy active technology")
