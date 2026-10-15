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
    coalition_target: str | None = None
    coalition_turn: int = 0
    cooperation_turns: int = 0
    broken_promises: dict[str, int] = field(default_factory=dict)
    last_breach: dict[str, int] = field(default_factory=dict)
    last_defeat: dict[str, int] = field(default_factory=dict)
    coercion: dict[str, int] = field(default_factory=dict)

    @property
    def at_war(self):
        return self.relations < -30 and not (self.trade_active or self.research_active or self.non_aggression_active or self.coalition_target)

    def end_agreements(self):
        self.trade_active = self.research_active = False
        self.non_aggression_active = self.friendship_active = False
        self.coalition_target, self.coalition_turn = None, 0

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
    def from_dict(cls, data, turn, *, version=44):
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
        new = ('coalition_target', 'coalition_turn', 'cooperation_turns', 'broken_promises', 'last_breach', 'last_defeat', 'coercion')
        if version < 44:
            data = {k: v for k, v in data.items() if k not in new}
        else:
            if (data['coalition_target'] is not None and not isinstance(data['coalition_target'], str)
                    or not integer(data['coalition_turn'], 0, turn)
                    or bool(data['coalition_target']) != bool(data['coalition_turn'])
                    or not integer(data['cooperation_turns'], 0, turn)):
                raise ValueError('Invalid coalition or cooperation history')
            for key, upper in (('broken_promises', 100), ('last_breach', turn), ('last_defeat', turn), ('coercion', 100)):
                if (not isinstance(data[key], dict) or len(data[key]) > 2
                        or any(not isinstance(o, str) or not integer(v, 1, upper) for o, v in data[key].items())):
                    raise ValueError('Invalid diplomatic memory')
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


def acceptance_threshold(game, action, target, proposer='player'):
    base = {"trade": TRADE_THRESHOLD, "non_aggression": NON_AGGRESSION_THRESHOLD,
            "friendship": FRIENDSHIP_THRESHOLD,
            "research": RACES[game._empire(target).race_id].research_threshold}[action]
    if action == 'trade':
        return base  # The universal +10 trade threshold remains unchanged.
    from .diplomatic_preferences import profile
    state = game.diplomacy_between(proposer, target)
    nature = profile(game, target)
    return min(100, base+min(40, state.broken_promises.get(proposer, 0)*nature.memory))


def ai_treaty_orders(game, owner):
    """Public priorities select mutually acceptable treaties between AI empires."""
    if game.turn < 6 or game.turn % 6 or game.strategy_error(owner):
        return
    from . import coalitions
    from .diplomatic_preferences import profile
    nature = profile(game, owner)
    offers = []
    for other in game.opponents:
        if other == owner or not game.colony_systems(other) or not first_contact.known(game, owner, other):
            continue
        state = game.diplomacy_between(owner, other)
        if state.at_war or game.turn < state.offer_ready_turn:
            continue
        for action, priority in (('trade', nature.trade), ('research', nature.research),
                                 ('friendship', nature.friendship), ('non_aggression', nature.friendship)):
            if not priority or getattr(state, action+'_active'):
                continue
            if action in ('friendship', 'non_aggression') and coalitions.treaty_conflict(game, owner, other):
                continue
            if state.relations < max(acceptance_threshold(game, action, other, owner), acceptance_threshold(game, action, owner, other)):
                continue
            benefit = trade_income(game, owner, other) if action == 'trade' else 0
            if action == 'trade' and not benefit:
                continue
            offers.append((priority*10+min(9, benefit)+(2 if action == 'friendship' else 0), other, action))
    if not offers:
        return
    _, other, action = max(offers)
    state = game.diplomacy_between(owner, other)
    setattr(state, action+'_active', True)
    if action == 'friendship':
        state.trade_active = state.non_aggression_active = True
    state.offer_ready_turn = game.turn+OFFER_COOLDOWN
    message = f'{game.empire_name_for(owner)} and {game.empire_name_for(other)} agreed to a {TREATIES[action].lower()}.'
    state.record(game.turn, message)
    coalitions.notify(game, (owner, other), message)


def economic_strength(game, owner):
    """Gross colony credits, including trade goods, excluding treaty income.

    Measuring before maintenance avoids penalizing a large developed economy
    for its upkeep. Never use empire_rates_for: that would compound pact income.
    """
    from .research import colony_yields, colony_maintenance
    bonuses = game.bonuses_for(owner)
    return sum(max(0, colony_yields(p, bonuses)[1]+colony_maintenance(p, bonuses))
               for _, p in game.settlements(owner))


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
    from .motherships import center, ship_for
    positions = [center(game, ship_for(game, p)) if p.habitat else s for s, p in homes]
    factor = 1/(1+distance_ly(*positions)/TRADE_DISTANCE_LY)
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
    state = game.diplomacy_between(first, second)
    if state.coalition_target:
        return "A coalition agreement protects this empire. Declare war in Diplomacy before attacking."
    if state.non_aggression_active:
        return "A non-aggression pact protects this empire. Declare war in Diplomacy before attacking."
    return None


def remember_breach(game, offender, other):
    state = game.diplomacy_between(offender, other)
    state.broken_promises[offender] = min(100, state.broken_promises.get(offender, 0)+1)
    state.last_breach[offender] = game.turn


def record_defeat(game, loser, winner):
    if loser in game.owners and winner in game.owners and loser != winner:
        game.diplomacy_between(loser, winner).last_defeat[loser] = game.turn


def start_war(game, first, second, *, defensive=False):
    """All declarations and acts of war use the same treaty teardown."""
    first_contact.establish(game, first, second)
    state = game.diplomacy_between(first, second)
    new_war = not state.at_war
    if any((state.trade_active, state.research_active, state.non_aggression_active, state.coalition_target)):
        remember_breach(game, first, second)
    state.end_agreements()
    state.relations = -100
    state.offer_ready_turn = max(state.offer_ready_turn, game.turn+OFFER_COOLDOWN)
    if new_war and not defensive:
        from .coalitions import defend
        defend(game, first, second)
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
    if action in ('friendship', 'non_aggression'):
        from .coalitions import treaty_conflict
        if treaty_conflict(game, 'player', target):
            return 'An active coalition opposes this empire. Leave that coalition first.'
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
        remember_breach(game, 'player', target)
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
    from . import coalitions, tribute
    coalitions.normalize(game)
    tribute.normalize(game)
    for i, first in enumerate(game.owners):
        for second in game.owners[i+1:]:
            state = game.diplomacy_between(first, second)
            if not first_contact.known(game, first, second):
                continue
            if not game.colony_systems(first) or not game.colony_systems(second):
                state.end_agreements()
                continue
            for offender, recipient in ((first, second), (second, first)):
                interval = personality(game, recipient).forgiveness*5
                elapsed = game.turn+1-state.last_breach.get(offender, game.turn+1)
                if (game._empire(recipient).race_id != 'lithar' and interval and elapsed >= interval
                        and offender in state.broken_promises):
                    state.broken_promises[offender] -= 1
                    if not state.broken_promises[offender]:
                        del state.broken_promises[offender]
                        del state.last_breach[offender]
                    else:
                        state.last_breach[offender] = game.turn
            if state.relations < 0 and not state.friendship_active and (state.trade_active or state.research_active):
                state.trade_active = state.research_active = False
                state.record(game.turn+1, f"{game.empire_name_for(second)} ended remaining agreements because relations fell below 0.")
                # A foreign clan replies; never put words in the player's mouth.
                for speaker in (first, second):
                    reply = diplomatic_reply(game, speaker, "agreements_ended") if speaker != "player" else None
                    if reply:
                        state.record(game.turn+1, f'“{reply}”')
            cooperative = any((state.trade_active, state.research_active, state.non_aggression_active, state.coalition_target))
            state.cooperation_turns = min(game.turn, state.cooperation_turns+1) if cooperative else 0
            state.improve(int(state.trade_active)+int(state.research_active)+int(state.non_aggression_active)+int(bool(state.coalition_target)))
            # Past grievances can thaw toward shared values; alignment itself never decays.
            # Declared wars remain hostile.
            intervals = (personality(game, first).forgiveness, personality(game, second).forgiveness)
            interval = max(intervals)
            baseline = alignment.between(game, first, second)
            if (-30 <= state.relations < baseline and all(intervals) and (game.turn+1) % interval == 0):
                state.improve(1)
