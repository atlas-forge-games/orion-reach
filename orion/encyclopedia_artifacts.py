"""Relic lore and proposed powers; collecting a relic does not activate bonuses."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactConcept:
    id: str
    name: str
    placement: str
    lore: str
    bonus: str
    power: str


ARTIFACT_CONCEPTS = (
    ArtifactConcept(
        'heart_of_a_dead_sun',
        'The Heart of a Dead Sun',
        'Flagship',
        'A collapsing star imprisoned inside an ancient reactor. It still burns with the light of its destroyed worlds.',
        '+25% fleet energy-weapon damage.',
        'Stellar Pulse: once per battle, the flagship releases a devastating blast against nearby enemies.',
    ),
    ArtifactConcept(
        'aegis_of_eternity',
        'The Aegis of Eternity',
        'Flagship',
        "The shield generator of a civilization's final refuge, recovered intact from a universe of wreckage.",
        '+30% fleet shield capacity.',
        'Last Refuge: once per battle, a fatal hit leaves the flagship barely alive and restores its shields.',
    ),
    ArtifactConcept(
        'silent_choir',
        'The Silent Choir',
        'Flagship',
        'Thousands of ancient admirals preserved as one consciousness. They speak only when battle begins.',
        '+15 percentage points of fleet weapon accuracy.',
        'Perfect Foresight: at battle start, the Choir identifies one enemy ship whose exposed weaknesses increase damage against it.',
    ),
    ArtifactConcept(
        'spear_of_the_last_dawn',
        'The Spear of the Last Dawn',
        'Flagship',
        'A weapon built to kill something its creators refused to name.',
        'Equips the flagship with a unique relic weapon.',
        'Last Dawn: once per battle, fire a shield-piercing strike that deals enormous damage to one target.',
    ),
    ArtifactConcept(
        'funeral_bell',
        'The Funeral Bell',
        'Flagship',
        'No sound travels through space. Yet every surviving account says the enemy heard it.',
        'Equips the flagship with a fleet-disruption relic.',
        'Toll of Silence: once per battle, nearby enemies lose movement and cannot launch drones during their next turn.',
    ),
    ArtifactConcept(
        'worldseed',
        'The Worldseed',
        'Capital',
        'A living fragment of the first garden, older than any known civilization.',
        'Increases capital population capacity and grants an empire-wide food bonus.',
        'First Garden: gradually transforms the capital into a Gaia world.',
    ),
    ArtifactConcept(
        'forge_of_creation',
        'The Forge of Creation',
        'Capital',
        'A machine that remembers how matter was made.',
        "Substantial output bonuses for the capital's industrial workers and miners.",
        'Matter Rewritten: periodically finish one ordinary construction project instantly, provided its Resources are available.',
    ),
    ArtifactConcept(
        'unwritten_equation',
        'The Unwritten Equation',
        'Capital',
        'A formula that changes whenever it is understood. Extinct civilizations appear among its intermediate calculations.',
        '+25% empire research.',
        'Forbidden Insight: rare opportunities to recover a technology excluded by an earlier research choice.',
    ),
    ArtifactConcept(
        'throne_of_the_last_emperor',
        'The Throne of the Last Emperor',
        'Capital',
        'Its builders ruled a thousand suns. The throne still considers their empire alive.',
        'Additional council votes from the capital and stronger capital ground defenses.',
        "Imperial Proclamation: installation announces the relic's claim to every contacted civilization.",
    ),
    ArtifactConcept(
        'captive_horizon',
        'The Captive Horizon',
        'Capital',
        'A miniature black hole suspended inside a ring with no measurable age.',
        'Enormous local capital energy without Resource fuel.',
        'Horizon Gate: a special transit connection speeds travel between the capital and its other colonies.',
    ),
)
