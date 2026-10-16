"""Mothership presentation for existing facilities; IDs and rules stay shared."""

from .buildings import facility_family


MODULE_NAMES = {
    "factory": "Industry module",
    "robotic_factory": "Robotic industry module",
    "nanofactory": "Nanoassembly module",
    "mine": "Extraction module",
    "deep_core_mine": "Advanced extraction module",
    "automated_refinery": "Refinery module",
    "research_lab": "Research module",
    "advanced_research_lab": "Advanced research module",
    "quantum_research_lab": "Quantum research module",
    "hydroponic_farm": "Farming module",
    "trade_center": "Commerce module",
    "barracks": "Training module",
    "sensor_array": "Sensor module",
    "solar_array": "Solar power module",
    "fusion_plant": "Fusion reactor module",
    "geothermal_plant": "Thermal recovery module",
    "thermal_plant": "Backup generator module",
    "singularity_plant": "Singularity reactor module",
    "space_hub": "Space Hub module",
}

MODULE_ART = {
    "factory": "industry",
    "mine": "extraction",
    "research_lab": "research",
    "hydroponic_farm": "farming",
    "trade_center": "commerce",
    "barracks": "training",
    "sensor_array": "sensor",
    "solar_array": "solar",
    "fusion_plant": "fusion",
    "geothermal_plant": "thermal_recovery",
    "thermal_plant": "backup_generator",
    "singularity_plant": "singularity",
    "space_hub": "space_hub",
}


def display_name(spec, habitat=False):
    """Also accepts ship/project specifications, whose names remain unchanged."""
    return MODULE_NAMES.get(spec.id, spec.name) if habitat else spec.name


def art_id(building_id):
    return MODULE_ART.get(facility_family(building_id))
