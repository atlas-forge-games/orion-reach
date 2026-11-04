"""Stable empire identifiers and map colors, independent of race and UI."""

from .races import RACES

PLAYER, RIVAL = "player", "rival"
# Observer campaigns need one computer empire for every playable civilization.
MAX_RIVALS = len(RACES)
RIVAL_IDS = (RIVAL, *(f"rival_{i}" for i in range(2, MAX_RIVALS+1)))
# Keep a spare identity for a Remnant enclave emerging during a campaign.
CAMPAIGN_RIVAL_IDS = (*RIVAL_IDS, f"rival_{MAX_RIVALS+1}")
EMPIRE_IDS = (PLAYER, *CAMPAIGN_RIVAL_IDS)
DEFAULT_PALETTE = "blue"
PLAYER_PALETTES = {"blue": (44, 164, 255), "turquoise": (0, 218, 225)}
COLORS = (PLAYER_PALETTES[DEFAULT_PALETTE], (250, 168, 111), (203, 169, 255),
          (145, 223, 126), (249, 207, 116), (245, 151, 200), (203, 213, 239),
          (70, 218, 187), (239, 119, 140), (173, 193, 92), (142, 158, 255),
          (244, 151, 61), (218, 123, 241), (112, 204, 242), (216, 209, 164))


def max_rivals(race_id):
    """The player's civilization takes one slot; the Observer takes none."""
    return MAX_RIVALS if race_id == "observer" else MAX_RIVALS-1


def empire_color(owner, palette=DEFAULT_PALETTE):
    """Resolve display colors without changing campaign state or global colors."""
    if owner == "pirates":
        return (243, 132, 99)
    if owner == PLAYER:
        return PLAYER_PALETTES.get(palette, PLAYER_PALETTES[DEFAULT_PALETTE])
    return COLORS[EMPIRE_IDS.index(owner)] if owner in EMPIRE_IDS else (172, 172, 172)


def relation_key(first, second):
    return "|".join(sorted((first, second)))
