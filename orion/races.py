"""Original prototype races; diplomatic traits never change local production."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RaceSpec:
    id: str
    name: str
    focus: str
    description: str
    default_empire: str
    color: tuple[int, int, int]
    trade_threshold: int
    research_threshold: int
    envoy_bonus: int = 0
    trade_bonus: int = 0
    research_bonus: int = 0
    development: tuple[str, ...] = ("factory", "trade_center", "research_lab", "mine")

    @property
    def trait(self):
        if self.envoy_bonus:
            return f"Envoys: +{self.envoy_bonus} extra relations"
        if self.trade_bonus:
            return f"Trade pact: +{self.trade_bonus} extra credit / turn"
        return f"Research pact: +{self.research_bonus} extra RP / turn"


RACES = {
    "terran": RaceSpec(
        "terran", "Terrans", "Adaptable diplomats",
        "Human explorers whose diverse societies value negotiation, exchange and new frontiers.",
        "Terran Union", (119, 194, 207), 20, 30, envoy_bonus=4),
    "kharuun": RaceSpec(
        "kharuun", "Kharuun", "Crystalline builders",
        "Mineral-bodied engineers who measure trust through reliable exchange and lasting works.",
        "Kharuun Assembly", (231, 150, 100), 15, 45, trade_bonus=1,
        development=("factory", "trade_center", "mine", "research_lab")),
    "aelari": RaceSpec(
        "aelari", "Aelari", "Amphibious scholars",
        "Ocean-born archivists who build alliances around shared discovery and patient inquiry.",
        "Aelari Concord", (164, 163, 229), 30, 15, research_bonus=1,
        development=("factory", "research_lab", "trade_center", "mine")),
}


def default_rival_race(player_race):
    return "aelari" if player_race == "kharuun" else "kharuun"
