"""Shared weapon statistics for tactics, fleet design and presentation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Beam:
    name: str
    damage: int
    range: int
    color: tuple[int, int, int]
    accuracy: int = 85
    shots: int = 1
    projectile: bool = False
    drone: bool = False
    shield_multiplier: int = 1
    shield_bypass: int = 0
    interception_piercing: int = 0
    slows: bool = False
    reload: int = 0
    versus_drones: int = 1
    versus_capitals: int = 1


BEAMS = {
    "none": Beam("Unarmed", 0, 0, (133, 151, 160)),
    "laser": Beam("Laser", 5, 6, (255, 80, 76)),
    "quantum": Beam("Quantum beam", 7, 7, (187, 113, 255)),
    "torpedo": Beam("Torpedo", 10, 8, (255, 188, 79), accuracy=75, projectile=True),
    "missile": Beam("Defense missile", 10, 8, (255, 188, 79), accuracy=75, projectile=True),
    "siege": Beam("Siege cannon", 8, 6, (229, 144, 88), accuracy=70),
    "cruiser_battery": Beam("Cruiser battery", 12, 7, (120, 196, 255)),
    "battleship_battery": Beam("Heavy battery", 18, 7, (255, 156, 88)),
    "titan_battery": Beam("Titan battery", 26, 8, (187, 113, 255)),
    "drone_beam": Beam("Drone pulse", 3, 3, (102, 220, 255), drone=True),
    "interceptor_pulse": Beam("Interceptor pulse", 2, 3, (102, 255, 216), accuracy=95, drone=True, versus_drones=4),
    "bomber_torpedo": Beam("Drone torpedo", 5, 3, (255, 169, 77), accuracy=75, projectile=True, drone=True, versus_capitals=2),
    "plasma_breath": Beam("Plasma breath", 8, 4, (104, 255, 144)),
    "crystal_ray": Beam("Crystal ray", 10, 7, (102, 220, 255)),
    "ancient_lance": Beam("Ancient lance", 12, 8, (255, 198, 104)),
    "void_ray": Beam("Void ray", 15, 5, (196, 143, 255)),
    "pulse": Beam("Pulse beam", 8, 6, (114, 222, 255), accuracy=100, shots=2),
    "plasma": Beam("Plasma beam", 24, 4, (255, 129, 54)),
    "ion": Beam("Ion beam", 8, 6, (83, 182, 255), shield_multiplier=4),
    "graviton": Beam("Graviton beam", 16, 6, (179, 130, 255), slows=True),
    "particle": Beam("Particle lance", 20, 10, (127, 244, 221)),
    "heavy_beam": Beam("Heavy beam", 30, 9, (255, 210, 126)),
    "phased": Beam("Phased beam", 16, 7, (219, 170, 255), shield_bypass=50),
    "disruptor": Beam("Disruptor", 40, 5, (238, 100, 219), reload=1),
    "fusion_torpedo": Beam("Fusion torpedo", 18, 9, (255, 200, 86), accuracy=75, projectile=True),
    "mirv": Beam("MIRV torpedo", 21, 8, (255, 155, 99), accuracy=75, shots=3, projectile=True, interception_piercing=50),
    "antimatter": Beam("Antimatter torpedo", 36, 9, (222, 146, 255), accuracy=75, projectile=True, reload=1),
}

DRONE_ROLES = {
    "assault": ("Assault drone", "drone_beam", 5),
    "interceptor": ("Interceptor", "interceptor_pulse", 6),
    "bomber": ("Bomber", "bomber_torpedo", 3),
}
CAPITAL_TARGETS = frozenset(("cruiser", "battleship", "carrier", "titan", "missile_base",
                           "space_serpent", "crystal_guardian", "ancient_sentinel", "void_leviathan",
                           "ashen_leviathan", "horizon_warden", "crown_sentinel"))
