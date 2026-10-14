"""Bilateral diplomacy, transparent AI decisions and mutually beneficial treaties."""

from dataclasses import dataclass, field
import math

from .races import RACES
from . import first_contact, alignment
from .personalities import diplomatic_reply, personality

# Retained only to validate cooldowns in existing saves.
ENVOY_COOLDOWN, GIFT_COOLDOWN = 3, 5
OFFER_COOLDOWN = 3
RESEARCH_INCOME = 3
TRADE_THRESHOLD, NON_AGGRESSION_THRESHOLD, FRIENDSHIP_THRESHOLD = 10, 0, 30
TRADE_SHARE_PERCENT, TRADE_DISTANCE_LY = 25, 50
BREAK_PENALTY = 15
TREATIES = {"trade": "Trade pact", "research": "Research agreement",
            "non_aggression": "Non-aggression pact", "friendship": "Friendship declaration"}
ACTIONS = (*TREATIES, *(f"end_{key}" for key in TREATIES), "declare_war")


@dataclass
class DiplomaticEvent:
    turn: int
    message: str


@dataclass
class DiplomacyState:
    relations: int = 0
    trade_active: bool = False
    research_active: bool = False
    envoy_ready_turn: int = 1
    gift_ready_turn: int = 1
    offer_ready_turn: int = 1
    events: list[DiplomaticEvent] = field(default_factory=list)
    contact_turn: int = 0
    introduced: bool = False
    non_aggression_active: bool = False
    friendship_active: bool = False

    @property
    def at_war(self):
        return self.relations < -30 and not (self.trade_active or self.research_active or self.non_aggression_active)

    def end_agreements(self):
        self.trade_active = self.research_active = False
        self.non_aggression_active = self.friendship_active = False

    @property
    def attitude(self):
        if self.relations >= 60:
            return "Warm"
        if self.relations >= 25:
            return "Friendly"
        if self.relations >= 0:
            return "Neutral"
        return "Wary" if self.relations >= -30 else "Hostile"

    def record(self, turn, message):
        self.events.append(DiplomaticEvent(turn, message))
        self.events = self.events[-12:]

    def improve(self, amount):
        self.relations = min(100, max(-100, self.relations+amount))

    @classmethod
    def from_dict(cls, data, turn, *, version=43):
        def integer(value, lower, upper):
            return type(value) is int and lower <= value <= upper
        if not isinstance(data, dict) or not integer(data["relations"], -100, 100):
            raise ValueError
        if version >= 26:
            if (not integer(data["contact_turn"], 0, turn) or type(data["introduced"]) is not bool
                    or (data["introduced"] and not data["contact_turn"])):
                raise ValueError("Invalid first-contact state")
        else:
            data = {k: v for k, v in data.items() if k not in ("contact_turn", "introduced")}
        for key in ("trade_active", "research_active"):
            if type(data[key]) is not bool:
                raise ValueError
        if version >= 43:
            if any(type(data[key]) is not bool for key in ("non_aggression_active", "friendship_active")):
                raise ValueError("Invalid diplomatic treaty")
            if data["friendship_active"] and not (data["trade_active"] and data["non_aggression_active"]):
                raise ValueError("Friendship requires trade and non-aggression")
        else:
            data = {k: v for k, v in data.items() if k not in ("non_aggression_active", "friendship_active")}
            # Retired actions no longer need a pending cooldown after migration.
            data.update(envoy_ready_turn=1, gift_ready_turn=1)
        for key, cooldown in (("envoy_ready_turn", ENVOY_COOLDOWN), ("gift_ready_turn", GIFT_COOLDOWN),
                              ("offer_ready_turn", OFFER_COOLDOWN)):
            if not integer(data[key], 1, turn+cooldown):
                raise ValueError
        if not isinstance(data["events"], list) or len(data["events"]) > 12:
            raise ValueError
        events = []
        for event in data["events"]:
            if not isinstance(event, dict) or not integer(event["turn"], 1, turn):
                raise ValueError
            message = event["message"]
            if (not isinstance(message, str) or not 0 < len(message) <= 180
                    or not message.strip() or not message.isprintable()):
                raise ValueError
            events.append(DiplomaticEvent(**event))
        if any(a.turn > b.turn for a, b in zip(events, events[1:])):
            raise ValueError
        return cls(**{**data, "events": events})


def make_contact(turn, name, race_id, other_race_id=None):
    # The optional argument is absent only when upgrading legacy saves.
    initial = alignment.score(other_race_id, race_id) if other_race_id is not None else 0
    state = DiplomacyState(relations=initial)
    state.record(turn, "Diplomatic channel awaiting first contact.")
    return state


def acceptance_threshold(game, action, target):
    return {"trade": TRADE_THRESHOLD, "non_aggression": NON_AGGRESSION_THRESHOLD,
            "friendship": FRIENDSHIP_THRESHOLD,
            "research": RACES[game._empire(target).race_id].research_threshold}[action]


def economic_strength(game, owner):
    """Gross colony credits, including trade goods, excluding treaty income.

    Measuring before maintenance avoids penalizing a large developed economy
    for its upkeep. Never use empire_rates_for: that would compound pact income.
    """
    from .research import colony_yields, colony_maintenance
    bonuses = game.bonuses_for(owner)
    return sum(max(0, colony_yields(p, bonuses)[1]+colony_maintenance(p, bonuses))
               for s in game.colony_systems(owner) for p in s.worlds if p.owner == owner)


def trade_income(game, owner, partner, *, strengths=None):
    """Each partner earns a share of their joint economy, attenuated by distance."""
    from .production import distance_ly
    if owner == partner or owner not in game.owners or partner not in game.owners:
        return 0
    homes = game.headquarters(owner), game.headquarters(partner)
    if not all(homes):
        return 0
    strength = strengths if strengths is not None else {
        o: economic_strength(game, o) for o in (owner, partner)}
    if not strength[owner] or not strength[partner]:
        return 0
    joint = math.sqrt(strength[owner]*strength[partner])*TRADE_SHARE_PERCENT/100
    bonus = RACES[game._empire(owner).race_id].trade_bonus+game.bonuses_for(owner).get("pact_income", 0)
    factor = 1/(1+distance_ly(homes[0][0], homes[1][0])/TRADE_DISTANCE_LY)
    return max(0, math.floor((joint+bonus)*factor+0.5))


def agreement_yields(game, owner):
    if owner not in game.owners:
        return 0, 0
    agreements = [(other, game.diplomacy_between(owner, other)) for other in game.owners if other != owner]
    agreements = [(other, state) for other, state in agreements if state.trade_active or state.research_active]
    if not agreements or not game.colony_systems(owner):
        return 0, 0
    race = RACES[game._empire(owner).race_id]
    bonuses = game.bonuses_for(owner)
    partners = [(other, state) for other, state in agreements
                if game.colony_systems(other) and first_contact.known(game, owner, other)]
    traders = [other for other, state in partners if state.trade_active]
    strengths = {o: economic_strength(game, o) for o in (owner, *traders)} if traders else {}
    return (sum(trade_income(game, owner, other, strengths=strengths) for other in traders),
            sum(RESEARCH_INCOME+race.research_bonus+bonuses.get("pact_research", 0)
                for _, state in partners if state.research_active))


def aggression_error(game, first, second):
    if game.diplomacy_between(first, second).non_aggression_active:
        return "A non-aggression pact protects this empire. Declare war in Diplomacy before attacking."
    return None


def start_war(game, first, second):
    """All declarations and acts of war use the same treaty teardown."""
    first_contact.establish(game, first, second)
    state = game.diplomacy_between(first, second)
    state.end_agreements()
    state.relations = -100
    state.offer_ready_turn = max(state.offer_ready_turn, game.turn+OFFER_COOLDOWN)
    # Retain old sightings, but never leave a former friend's feed live.
    from . import sensors
    sensors.refresh(game)


def action_error(game, action, target="rival"):
    if game.strategy_error("player"):
        return game.strategy_error("player")
    if action not in ACTIONS:
        return "Unknown diplomatic action."
    if target not in game.opponents:
        return "Add a rival empire to establish diplomatic contact."
    if not first_contact.known(game, "player", target):
        return "Explore or detect a fleet to establish first contact."
    state = game.diplomacy_between("player", target)
    if not game.colony_systems(target):
        return "This empire has been eliminated."
    if action == "declare_war":
        return "You are already at war with this empire." if state.at_war else None
    if action in TREATIES and getattr(state, f"{action}_active"):
        return "This agreement is already active."
    if action.startswith("end_"):
        if not getattr(state, f"{action[4:]}_active"):
            return "This agreement is not active."
        if state.friendship_active and action in ("end_trade", "end_non_aggression"):
            return "Included in friendship. End the friendship declaration first."
        return None
    if game.turn < state.offer_ready_turn:
        return f"Available on turn {state.offer_ready_turn}."
    return None


def take_action(game, action, target="rival"):
    from .model import RuleError
    error = action_error(game, action, target)
    if error:
        raise RuleError(error)
    state, rival = game.diplomacy_between("player", target), game._empire(target)
    outcome = action
    if action == "declare_war":
        start_war(game, "player", target)
        message = f"War declared on {rival.name}. All agreements ended; relations are now -100."
    elif action in TREATIES:
        threshold = acceptance_threshold(game, action, target)
        state.offer_ready_turn = game.turn+OFFER_COOLDOWN
        title = TREATIES[action]
        if state.relations >= threshold:
            setattr(state, f"{action}_active", True)
            if action == "friendship":
                state.trade_active = state.non_aggression_active = True
            outcome = f"{action}_accepted"
            message = (f"{title} accepted. Trade, non-aggression and shared scanners are active." if action == "friendship"
                       else f"{title} accepted. Attacks are blocked; trust grows on End Turn." if action == "non_aggression"
                       else f"{title} accepted. Income and trust grow on End Turn.")
        else:
            outcome = f"{action}_declined"
            message = f"{title} declined. {rival.name} requires relations of {threshold:+}; currently {state.relations:+}."
    else:
        setattr(state, f"{action[4:]}_active", False)
        if action == "end_friendship":
            state.trade_active = state.non_aggression_active = False
        before = state.relations
        state.improve(-personality(game, target).breach)
        state.offer_ready_turn = max(state.offer_ready_turn, game.turn+OFFER_COOLDOWN)
        title = TREATIES[action[4:]]
        message = f"{title} ended. Relations -{before-state.relations}; its benefits stop immediately."
    state.record(game.turn, message)
    reply = diplomatic_reply(game, target, outcome)
    if reply:
        state.record(game.turn, f'“{reply}”')
    if action in ("friendship", "end_friendship"):
        from . import sensors
        sensors.refresh(game)
        first_contact.refresh(game)
    return message


def advance_diplomacy(game):
    """Resolve distrust before collecting yields, then build trust through treaties."""
    for i, first in enumerate(game.owners):
        for second in game.owners[i+1:]:
            state = game.diplomacy_between(first, second)
            if not first_contact.known(game, first, second):
                continue
            if not game.colony_systems(first) or not game.colony_systems(second):
                state.end_agreements()
                continue
            if state.relations < 0 and not state.friendship_active and (state.trade_active or state.research_active):
                state.trade_active = state.research_active = False
                state.record(game.turn+1, f"{game.empire_name_for(second)} ended remaining agreements because relations fell below 0.")
                # A foreign clan replies; never put words in the player's mouth.
                for speaker in (first, second):
                    reply = diplomatic_reply(game, speaker, "agreements_ended") if speaker != "player" else None
                    if reply:
                        state.record(game.turn+1, f'“{reply}”')
            state.improve(int(state.trade_active)+int(state.research_active)+int(state.non_aggression_active))
            # Past grievances can thaw toward shared values; alignment itself never decays.
            # Declared wars remain hostile.
            intervals = (personality(game, first).forgiveness, personality(game, second).forgiveness)
            interval = max(intervals)
            baseline = alignment.between(game, first, second)
            if (-30 <= state.relations < baseline and all(intervals) and (game.turn+1) % interval == 0):
                state.improve(1)
