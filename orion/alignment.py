"""Fixed-reference shared values; a standing diplomatic contribution, not a tick."""
from dataclasses import dataclass
import math

AXES = ('autonomy', 'openness', 'restraint', 'innovation', 'stewardship')
AXIS_LABELS = ('Autonomy', 'Openness', 'Restraint', 'Innovation', 'Stewardship')
POLES = (
    ('Collective control', 'Independence'),
    ('Isolation', 'Exchange'),
    ('Coercion', 'Coexistence'),
    ('Preservation', 'Experimentation'),
    ('Exploitation', 'Living worlds'),
)
# Mean L1 distance across the 55 distinct pairs of the original 11-race roster.
# Freeze it: campaign membership, eliminated empires and future races cannot move it.
REFERENCE_DISTANCE = 402 / 55
MAX_MODIFIER = 25


@dataclass(frozen=True)
class Values:
    autonomy: int
    openness: int
    restraint: int
    innovation: int
    stewardship: int

    @property
    def vector(self):
        return tuple(getattr(self, axis) for axis in AXES)


PROFILES = {
    'terran': Values(1, 2, 1, 1, 0),
    'kharuun': Values(0, 1, 1, 1, -1),
    'aelari': Values(1, 1, 2, 2, 1),
    'lithar': Values(0, -1, 1, -1, 0),
    'varkesh': Values(-2, -1, -2, 0, -2),
    'wanderers': Values(2, 2, 1, 1, 0),
    'xenonflora': Values(-1, 0, 2, 1, 2),
    'nexus': Values(-2, 0, 0, 2, -1),
    'aetheri': Values(1, 1, 2, 2, 1),
    'concord': Values(-2, 1, -2, 2, 0),
    'remnant': Values(0, -2, 0, -1, 1),
}


def distance(first, second):
    return sum(abs(a-b) for a,b in zip(PROFILES[first].vector, PROFILES[second].vector))


def raw_score(first, second):
    return MAX_MODIFIER * (REFERENCE_DISTANCE-distance(first, second)) / REFERENCE_DISTANCE


def score(first, second):
    # Match the published table; custom extremes stay within the configured cap.
    value = max(-MAX_MODIFIER, min(MAX_MODIFIER, raw_score(first, second)))
    return math.floor(value+0.5) if value >= 0 else math.ceil(value-0.5)


def between(game, first, second):
    return score(game._empire(first).race_id, game._empire(second).race_id)


@dataclass(frozen=True)
class Relationship:
    alignment: int
    history: int
    total: int


def relationship(game, first, second):
    total = game.diplomacy_between(first, second).relations
    standing = between(game, first, second)
    # Relations already store the total. Never add the standing modifier again.
    # Legacy campaigns retain their total; history includes their old baseline.
    return Relationship(standing, total-standing, total)
