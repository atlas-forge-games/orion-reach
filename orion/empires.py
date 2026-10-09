"""Stable empire identifiers and map colors, independent of race and UI."""

PLAYER, RIVAL = "player", "rival"
MAX_RIVALS = 5
RIVAL_IDS = (RIVAL, *(f"rival_{i}" for i in range(2, MAX_RIVALS+1)))
# A Remnant enclave can emerge even when all five setup slots are occupied.
CAMPAIGN_RIVAL_IDS = (*RIVAL_IDS, "rival_6")
EMPIRE_IDS = (PLAYER, *CAMPAIGN_RIVAL_IDS)
COLORS = ((119, 194, 207), (226, 145, 100), (178, 151, 231),
          (128, 194, 117), (231, 191, 107), (219, 131, 179), (179, 185, 208))


def empire_color(owner):
    return COLORS[EMPIRE_IDS.index(owner)] if owner in EMPIRE_IDS else (133, 151, 160)


def relation_key(first, second):
    return "|".join(sorted((first, second)))
