"""Civilization character, diplomatic preferences and strategic inclinations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Personality:
    traits: str
    summary: str
    greeting: str
    envoy: int = 0
    gift: int = 0
    breach: int = 15
    forgiveness: int = 8  # Turns per point of recovery from wary relations; 0 never thaws.
    fleet_bonus: int = 0
    military_turn: int = 12
    conquest_ratio: int = 0  # Required visible strength advantage, in percent; 0 defensive.
    protective: bool = False


PERSONALITIES = {
    "terran": Personality(
        "Open · Pragmatic · Ambitious",
        "Welcome exchange and new frontiers. Rebuild trust readily, but may challenge a weaker, unfriendly neighbour.",
        "We crossed the dark wondering who we would find. May this meeting open a better future for both our peoples.",
        envoy=2, gift=1, forgiveness=4, conquest_ratio=180),
    "kharuun": Personality(
        "Practical · Honourable · Reserved",
        "Value reliable exchange and lasting agreements. Trust grows through deeds; broken promises are slow to heal.",
        "Fine words are easily shaped. Let us see whether your promises endure.",
        forgiveness=12),
    "aelari": Personality(
        "Curious · Cooperative · Cautious",
        "Seek shared discoveries and research partners. Prefer peaceful development and defend their own worlds.",
        "A new voice in the cosmos. What might we learn from one another?",
        envoy=3, gift=-2, forgiveness=5, protective=True),
    "lithar": Personality(
        "Patient · Territorial · Steadfast",
        "Build strong defences and seldom begin wars. Their worlds are enduring commitments, and their grudges endure too.",
        "We have endured the passing of suns. Tread gently upon our worlds, and we shall endure beside you.",
        envoy=-2, gift=-3, breach=25, forgiveness=20, protective=True),
    "varkesh": Personality(
        "Brutal · Predatory · Intimidating",
        "Strike at weak colonies for slaves and plunder. Respect strength; active agreements stay their raiding fleets.",
        "We are the Varkesh. Your wealth will fill our vaults. Your people will fill our slave holds. Resist, and your worlds will burn.",
        envoy=-3, gift=3, breach=10, forgiveness=6, fleet_bonus=2, military_turn=6),
    "wanderers": Personality(
        "Friendly · Independent · Adventurous",
        "Welcome travellers and trade. Prefer exploration and quick reconciliation to prolonged territorial wars.",
        "Another light along the road. May our paths cross in friendship, and our horizons remain open.",
        envoy=2, gift=2, forgiveness=3),
    "xenonflora": Personality(
        "Protective · Communal · Watchful",
        "Guard their living communities with shields and fortifications. Trust grows slowly after harm or betrayal.",
        "We hear your voice beyond the roots. Do you come to nurture, or to consume?",
        envoy=-1, gift=-2, breach=25, forgiveness=15, fleet_bonus=1, protective=True),
    "nexus": Personality(
        "Calculating · Unemotional · Methodical",
        "Evaluate exchange through practical benefit. May expand by force against an unfriendly neighbour when the odds favour success.",
        "Independent intelligence confirmed. Mutually beneficial exchange is possible. State your priorities.",
        envoy=-2, gift=2, forgiveness=8, fleet_bonus=1, conquest_ratio=160),
    "aetheri": Personality(
        "Mysterious · Contemplative · Detached",
        "Value patient dialogue and knowledge over material gifts. Avoid conquest and invest in protective fields.",
        "Another voice reaches us across the silence. We are listening.",
        envoy=1, gift=-5, forgiveness=10, protective=True),
    "concord": Personality(
        "Assimilating · Relentless · Collective",
        "One will seeks to absorb every independent civilization. Build invasion fleets early; agreements postpone assimilation.",
        "We are the Dominion of One. Your separation is temporary. Your knowledge, your worlds, your voices will become ours.",
        envoy=-6, gift=-10, breach=20, forgiveness=0, fleet_bonus=3, military_turn=6, conquest_ratio=120),
    "serevan": Personality(
        "Welcoming · Pluralistic · Persuasive",
        "Build lasting partnerships and sponsor voluntary accession on dissatisfied frontier worlds. Respect local cultures and defend members.",
        "Many peoples, many voices, one shared future. There is a place for your civilization in our Union.",
        envoy=4, gift=2, forgiveness=5, protective=True),
    "skirr": Personality(
        "Invasive · Voracious · Uncompromising",
        "Multiply, settle new breeding grounds and replace rival populations. Reject treaties and prepare invasion fleets early.",
        "Your worlds will hatch. Your cities will fall silent. Only the brood will remain.",
        envoy=-10, gift=-10, forgiveness=0, fleet_bonus=4, military_turn=4, conquest_ratio=100),
    "remnant": Personality(
        "Proud · Secretive · Possessive",
        "Guard lost knowledge and ancient claims. Slow to forgive, and willing to confront a weaker, unfriendly neighbour.",
        "You name these stars as though they have never belonged to anyone. We remember otherwise.",
        envoy=-2, gift=-4, breach=25, forgiveness=20, fleet_bonus=1, conquest_ratio=150, protective=True),
}


DIPLOMATIC_REPLIES = {
    "varkesh": {
        "envoy": "Your envoy may speak. Our raiders are harder to persuade.",
        "gift": "Tribute. Good. Your wealth is more useful than your excuses.",
        "trade_accepted": "Our pact holds. Break it, and we will collect in chains.",
        "trade_declined": "You have earned nothing. Our raiders will name their price.",
        "research_accepted": "Share your knowledge. We will forge it into weapons.",
        "research_declined": "You want our secrets? Prove you are worth more than a slave.",
        "end_trade": "Your pact is ash. Guard your vaults. We are coming for them.",
        "end_research": "Remember what we taught you. The next lesson will hurt.",
        "agreements_ended": "Your promises are worthless. The clans owe you no restraint.",
    },
}


def diplomatic_reply(game, owner, outcome):
    """Optional in-character reply, separate from the action's rules summary."""
    return DIPLOMATIC_REPLIES.get(game._empire(owner).race_id, {}).get(outcome)


def personality(game, owner):
    return PERSONALITIES[game._empire(owner).race_id]


def envoy_gain(game, sender, recipient):
    from .races import RACES
    return max(1, 8+RACES[game._empire(sender).race_id].envoy_bonus+personality(game, recipient).envoy)


def gift_gain(game, recipient):
    return max(1, 15+personality(game, recipient).gift)

