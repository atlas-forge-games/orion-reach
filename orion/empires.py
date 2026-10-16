"""Stable empire identifiers and map colors, independent of race and UI."""

PLAYER, RIVAL = "player", "rival"
MAX_RIVALS = 5
RIVAL_IDS = (RIVAL, *(f"rival_{i}" for i in range(2, MAX_RIVALS+1)))
# A Remnant enclave can emerge even when all five setup slots are occupied.
CAMPAIGN_RIVAL_IDS = (*RIVAL_IDS, "rival_6")
EMPIRE_IDS = (PLAYER, *CAMPAIGN_RIVAL_IDS)
DEFAULT_PALETTE = "blue"
PLAYER_PALETTES = {"blue": (44, 164, 255), "turquoise": (0, 218, 225)}
COLORS = (PLAYER_PALETTES[DEFAULT_PALETTE], (250, 168, 111), (203, 169, 255),
          (145, 223, 126), (249, 207, 116), (245, 151, 200), (203, 213, 239))


def empire_color(owner, palette=DEFAULT_PALETTE):
    """Resolve display colors without changing campaign state or global colors."""
    if owner == "pirates":
        return (243, 132, 99)
    if owner == PLAYER:
        return PLAYER_PALETTES.get(palette, PLAYER_PALETTES[DEFAULT_PALETTE])
    return COLORS[EMPIRE_IDS.index(owner)] if owner in EMPIRE_IDS else (172, 172, 172)


def relation_key(first, second):
    return "|".join(sorted((first, second)))
