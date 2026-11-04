"""Local garrisons and deterministic, simultaneous ground-combat rounds."""

from dataclasses import dataclass

from .economy import operating_facilities, whole_output

MAX_GARRISON = 100_000  # Includes occupation forces larger than the training limit.


@dataclass(frozen=True)
class GroundForces:
    militia: int
    garrison: int
    defence_bonus: int

    @property
    def troops(self):
        return self.militia+self.garrison

    @property
    def strength(self):
        return (self.troops*(100+self.defence_bonus)+99)//100


@dataclass(frozen=True)
class GroundRound:
    attackers: int
    defenders: int
    attacker_losses: int
    defender_losses: int


@dataclass(frozen=True)
class GroundOutcome:
    attackers: int
    defenders: int
    rounds: tuple[GroundRound, ...]

    @property
    def captured(self):
        # An exhausted assault cannot occupy a world, even in a mutual defeat.
        return self.attackers > 0 and self.defenders == 0


def forces(planet, bonuses=None):
    if not planet.colonized:
        return GroundForces(0, 0, 0)
    buildings = operating_facilities(planet, bonuses)
    bonus = (bonuses or {}).get("fortification_bonus", 0)*max(
        (rate for b, rate in buildings if b.id == "fortifications"), default=0)
    return GroundForces(max(0, 4+planet.population-planet.militia_losses), planet.garrison,
                        whole_output(sum(b.defence_bonus*rate for b, rate in buildings)+bonus))


def training_limit(planet, bonuses=None):
    return whole_output(sum(b.garrison_limit*rate for b, rate in operating_facilities(planet, bonuses)))


def training_rate(planet, bonuses=None):
    return sum(b.training*rate for b, rate in operating_facilities(planet, bonuses))


def train(planet, bonuses=None):
    """Train locally without removing population or consuming worker assignments."""
    if not planet.colonized:
        return 0
    # Militia remuster gradually; losses cannot be reset by reopening an invasion.
    planet.militia_losses = max(0, planet.militia_losses-1)
    room = max(0, training_limit(planet, bonuses)-planet.garrison)
    training = training_rate(planet, bonuses)
    if not training or not room:
        return 0
    progress = planet.training_progress+training
    recruits = min(room, whole_output(progress))
    planet.training_progress = round(max(0, progress-recruits), 12) if recruits < room else 0
    planet.garrison += recruits
    return recruits


def resolve(attackers, defence):
    """Each side inflicts one casualty per four troops, rounded up, simultaneously.

    Fortifications increase defending firepower. The same calculation is used
    for the preview and the actual landing, with no hidden dice rolls.
    """
    defenders = defence.troops
    rounds = []
    while attackers > 0 and defenders > 0:
        attack_loss = min(attackers, (defenders*(100+defence.defence_bonus)+399)//400)
        defence_loss = min(defenders, (attackers+3)//4)
        attackers -= attack_loss
        defenders -= defence_loss
        rounds.append(GroundRound(attackers, defenders, attack_loss, defence_loss))
    return GroundOutcome(attackers, defenders, tuple(rounds))


def transports_needed(planet, troop_strength, bonuses=None):
    """Smallest winning landing force, using the same rules as actual combat."""
    defence = forces(planet, bonuses)
    low, high = 1, max(1, (defence.strength*2)//troop_strength+1)
    while not resolve(high*troop_strength, defence).captured:
        high *= 2
    while low < high:
        mid = (low+high)//2
        if resolve(mid*troop_strength, defence).captured:
            high = mid
        else:
            low = mid+1
    return low
