"""Bilateral diplomacy, transparent AI decisions and mutually beneficial treaties."""

from dataclasses import dataclass, field

from .races import RACES
from . import first_contact
from .personalities import envoy_gain, gift_gain, personality

ENVOY_COST, ENVOY_RELATIONS, ENVOY_COOLDOWN = 10, 8, 3
GIFT_COST, GIFT_RELATIONS, GIFT_COOLDOWN = 50, 15, 5
OFFER_COOLDOWN = 3
TRADE_INCOME, RESEARCH_INCOME = 5, 3
BREAK_PENALTY = 15
ACTIONS = ("envoy", "gift", "trade", "research", "end_trade", "end_research")


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
    def from_dict(cls, data, turn, *, version=26):
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


def make_contact(turn, name, race_id):
    state = DiplomacyState()
    state.record(turn, "Diplomatic channel awaiting first contact.")
    return state


def agreement_yields(game, owner):
    if owner not in game.owners:
        return 0, 0
    race = RACES[game._empire(owner).race_id]
    bonuses = game.bonuses_for(owner)
    states = [game.diplomacy_between(owner, other) for other in game.owners if other != owner]
    return (sum(TRADE_INCOME+race.trade_bonus+bonuses.get("pact_income", 0) for state in states if state.trade_active),
            sum(RESEARCH_INCOME+race.research_bonus+bonuses.get("pact_research", 0) for state in states if state.research_active))


def action_error(game, action, target="rival"):
    if game.strategy_error():
        return game.strategy_error()
    if action not in ACTIONS:
        return "Unknown diplomatic action."
    if target not in game.opponents:
        return "Add a rival empire to establish diplomatic contact."
    if not first_contact.known(game, "player", target):
        return "Explore or detect a fleet to establish first contact."
    state = game.diplomacy_between("player", target)
    if not game.colony_systems(target):
        return "This empire has been eliminated."
    if action in ("trade", "research") and getattr(state, f"{action}_active"):
        return "This agreement is already active."
    if action in ("end_trade", "end_research"):
        if not getattr(state, f"{action[4:]}_active"):
            return "This agreement is not active."
        return None
    cooldown = (state.envoy_ready_turn if action == "envoy" else
                state.gift_ready_turn if action == "gift" else state.offer_ready_turn)
    if game.turn < cooldown:
        return f"Available on turn {cooldown}."
    cost = ENVOY_COST if action == "envoy" else GIFT_COST if action == "gift" else 0
    if cost and game.credits < cost:
        return f"Requires {cost} credits."
    if state.relations == 100 and action in ("envoy", "gift"):
        return "Relations are already at their maximum."
    return None


def take_action(game, action, target="rival"):
    from .model import RuleError
    error = action_error(game, action, target)
    if error:
        raise RuleError(error)
    state, rival = game.diplomacy_between("player", target), game._empire(target)
    if action == "envoy":
        game.credits -= ENVOY_COST
        gain = envoy_gain(game, "player", target)
        before = state.relations
        state.improve(gain)
        state.envoy_ready_turn = game.turn+ENVOY_COOLDOWN
        message = f"Envoy welcomed. Relations +{state.relations-before}; {ENVOY_COST} CR spent."
    elif action == "gift":
        game.credits -= GIFT_COST
        rival.credits += GIFT_COST
        before = state.relations
        state.improve(gift_gain(game, target))
        state.gift_ready_turn = game.turn+GIFT_COOLDOWN
        message = f"Gift of {GIFT_COST} CR delivered. Relations +{state.relations-before}."
    elif action in ("trade", "research"):
        threshold = getattr(RACES[rival.race_id], f"{action}_threshold")
        state.offer_ready_turn = game.turn+OFFER_COOLDOWN
        title = "Trade pact" if action == "trade" else "Research agreement"
        if state.relations >= threshold:
            setattr(state, f"{action}_active", True)
            message = f"{title} accepted. Benefits begin on the next End Turn."
        else:
            message = f"{title} declined. {rival.name} requires relations of {threshold:+}; currently {state.relations:+}."
    else:
        setattr(state, f"{action[4:]}_active", False)
        before = state.relations
        state.improve(-personality(game, target).breach)
        state.offer_ready_turn = max(state.offer_ready_turn, game.turn+OFFER_COOLDOWN)
        title = "Trade pact" if action == "end_trade" else "Research agreement"
        message = f"{title} ended. Relations -{before-state.relations}; its benefits stop immediately."
    state.record(game.turn, message)
    return message


def advance_diplomacy(game):
    """Resolve distrust before collecting yields, then build trust through treaties."""
    for i, first in enumerate(game.owners):
        for second in game.owners[i+1:]:
            state = game.diplomacy_between(first, second)
            if not first_contact.known(game, first, second):
                continue
            if state.relations < 0 and (state.trade_active or state.research_active):
                state.trade_active = state.research_active = False
                state.record(game.turn+1, f"{game.empire_name_for(second)} ended remaining agreements because relations fell below 0.")
            state.improve(int(state.trade_active)+int(state.research_active))
            # A wary peace can thaw. Wars still require active diplomacy to end.
            intervals = (personality(game, first).forgiveness, personality(game, second).forgiveness)
            interval = max(intervals)
            if (-30 <= state.relations < 0 and all(intervals) and (game.turn+1) % interval == 0):
                state.improve(1)
