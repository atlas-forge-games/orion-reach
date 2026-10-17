"""Bilateral coalition commitments against a named empire, and public dispatches."""
from dataclasses import dataclass
from . import first_contact, diplomatic_preferences as preferences

ACCEPTANCE = 40
MIN_THREAT = 10


@dataclass(frozen=True)
class Dispatch:
    id: int
    turn: int
    message: str


def notify(game, participants, message):
    """Publish only a decision involving the player or entirely known empires."""
    if game.is_observer or all(p == 'player' or first_contact.known(game, 'player', p) for p in participants):
        identifier = game.diplomatic_news[-1].id+1 if game.diplomatic_news else 1
        game.diplomatic_news.append(Dispatch(identifier, game.turn, message))
        game.diplomatic_news[:] = game.diplomatic_news[-200:]


def agreements(game):
    return [(a, b, game.diplomacy_between(a, b)) for i, a in enumerate(game.owners)
            for b in game.owners[i+1:] if game.diplomacy_between(a, b).coalition_target]


def targets(game, owner):
    return {state.coalition_target for a, b, state in agreements(game) if owner in (a, b)}


def protects(game, a, b):
    return bool(game.diplomacy_between(a, b).coalition_target)


def treaty_conflict(game, owner, other):
    return other in targets(game, owner) or owner in targets(game, other)


def proposal_error(game, proposer, partner, target):
    if game.strategy_error(proposer):
        return game.strategy_error(proposer)
    if len({proposer, partner, target}) != 3 or any(o not in game.owners for o in (proposer, partner, target)):
        return 'Choose two different partners and a third empire as the target.'
    if any(game._empire(o).race_id == "skirr" for o in (proposer, partner)):
        return "The Skirr Swarm does not join coalitions."
    if partner == 'player':
        return 'The player must propose and confirm their own coalition commitments.'
    if not all(game.colony_systems(o) for o in (proposer, partner, target)):
        return 'An eliminated empire cannot participate in a coalition.'
    if not all(first_contact.known(game, a, b) for a, b in ((proposer, partner), (proposer, target), (partner, target))):
        return 'Both prospective partners must have contact with the target.'
    state = game.diplomacy_between(proposer, partner)
    if state.coalition_target:
        return 'A coalition agreement with this partner is already active.'
    if state.at_war:
        return 'You cannot form a coalition with an empire you are fighting.'
    if game.turn < state.offer_ready_turn:
        return f'Available on turn {state.offer_ready_turn}.'
    for member in (proposer, partner):
        pact = game.diplomacy_between(member, target)
        if pact.non_aggression_active or pact.friendship_active or pact.coalition_target:
            return 'A member has a protection agreement with the target. End it first.'
    if treaty_conflict(game, proposer, partner):
        return 'An existing coalition commitment opposes this prospective partner.'
    return None


def willingness(game, owner, partner, target):
    state = game.diplomacy_between(owner, partner)
    nature = preferences.profile(game, owner)
    own = preferences.threat(game, owner, target).score
    shared = preferences.threat(game, partner, target).score
    trade = game.diplomacy_between(owner, target).trade_active
    loyalty = min(10, state.cooperation_turns*nature.loyalty//10)
    memory = min(40, state.broken_promises.get(partner, 0)*nature.memory)
    reasons = (('Their assessment of the target', min(50, own)), ('Your shared concerns', min(25, shared//2)),
               ('Relations with the partner', state.relations//3), ('Pragmatism', nature.pragmatism),
               ('Years of cooperation', loyalty), ('Broken promises', -memory),
               ('Trade at risk', -nature.trade*3 if trade else 0))
    score = sum(v for _, v in reasons)
    return preferences.Assessment(score, reasons), own >= MIN_THREAT and shared >= MIN_THREAT and score >= ACCEPTANCE


def war_participants(game, first, second, target):
    return [o for o in (first, second) if not game.diplomacy_between(o, target).at_war] if any(
        game.diplomacy_between(o, target).at_war for o in (first, second)) else []


def form(game, proposer, partner, target, *, join_war=False):
    from .model import RuleError
    from .diplomacy import OFFER_COOLDOWN, start_war
    error = proposal_error(game, proposer, partner, target)
    if error:
        raise RuleError(error)
    joining = war_participants(game, proposer, partner, target)
    if joining and not join_war:
        raise RuleError('This agreement joins an existing war. Explicitly confirm joining that war.')
    state = game.diplomacy_between(proposer, partner)
    report, accepted = willingness(game, partner, proposer, target)
    # An AI proposer must find the agreement worthwhile too; never decide for the player.
    if proposer != 'player':
        accepted = accepted and willingness(game, proposer, partner, target)[1]
    state.offer_ready_turn = game.turn+OFFER_COOLDOWN
    if not accepted:
        message = f'Coalition declined: shared danger and willingness of {ACCEPTANCE} are required (score {report.score}).'
        state.record(game.turn, message)
        return message
    state.coalition_target, state.coalition_turn = target, game.turn
    message = f'{game.empire_name_for(proposer)} and {game.empire_name_for(partner)} formed a coalition against {game.empire_name_for(target)}.'
    state.record(game.turn, message)
    notify(game, (proposer, partner, target), message)
    for member in joining:
        start_war(game, member, target, defensive=True)
    return message


def leave(game, owner, partner):
    from .model import RuleError
    from .diplomacy import remember_breach, OFFER_COOLDOWN
    from .personalities import personality
    if game.strategy_error(owner):
        raise RuleError(game.strategy_error(owner))
    if owner not in game.owners or partner not in game.owners or owner == partner:
        raise RuleError('Choose a coalition partner.')
    state = game.diplomacy_between(owner, partner)
    if not state.coalition_target:
        raise RuleError('No coalition agreement is active with this empire.')
    target = state.coalition_target
    remember_breach(game, owner, partner)
    state.coalition_target, state.coalition_turn = None, 0
    state.improve(-personality(game, partner).breach)
    state.relations = max(-30, state.relations)
    state.offer_ready_turn = max(state.offer_ready_turn, game.turn+OFFER_COOLDOWN)
    message = f'{game.empire_name_for(owner)} left the coalition with {game.empire_name_for(partner)}. Existing wars continue.'
    state.record(game.turn, message)
    notify(game, (owner, partner, target), message)
    return message


def defend(game, aggressor, victim):
    """Follow only the defensive commitments against the original aggressor.

    An offensive declaration does not enlist the attacker's coalition partners.
    Defensive responses cannot recursively trigger unrelated alliances.
    """
    from .diplomacy import start_war
    members = {victim}
    changed = True
    while changed:
        changed = False
        for a, b, state in agreements(game):
            if state.coalition_target == aggressor and members.intersection((a, b)):
                for member in (a, b):
                    if member not in members and game.colony_systems(member):
                        members.add(member)
                        changed = True
    for member in sorted(members-{victim}):
        if not game.diplomacy_between(member, aggressor).at_war:
            start_war(game, member, aggressor, defensive=True)
            message = f'{game.empire_name_for(member)} entered the war against {game.empire_name_for(aggressor)} to defend its coalition partner.'
            game.diplomacy_between(member, victim).record(game.turn, message)
            notify(game, (member, victim, aggressor), message)


def normalize(game):
    for a, b, state in agreements(game):
        target = state.coalition_target
        if not all(game.colony_systems(o) for o in (a, b, target)):
            state.coalition_target, state.coalition_turn = None, 0
            message = 'Coalition dissolved because a member or its target was eliminated. No betrayal penalty.'
            state.record(game.turn, message)
            notify(game, (a, b, target), message)


def ai_orders(game, owner):
    """AI empires can agree with each other; the human must choose their commitments."""
    if game.turn < 6 or game.turn % 6 or game.strategy_error(owner):
        return
    candidates = []
    for partner in game.opponents:
        if partner == owner:
            continue
        for target in game.owners:
            if proposal_error(game, owner, partner, target):
                continue
            a, yes_a = willingness(game, owner, partner, target)
            b, yes_b = willingness(game, partner, owner, target)
            if yes_a and yes_b:
                candidates.append((a.score+b.score, partner, target))
    if candidates:
        _, partner, target = max(candidates)
        form(game, owner, partner, target, join_war=True)


def validate(game):
    """Cross-reference saved diplomatic state after all empires have loaded."""
    for i, a in enumerate(game.owners):
        for b in game.owners[i+1:]:
            state = game.diplomacy_between(a, b)
            for memory in (state.broken_promises, state.last_breach, state.last_defeat, state.coercion):
                if not set(memory) <= {a, b}:
                    raise ValueError('Diplomatic memory names a nonparticipant')
            if set(state.broken_promises) != set(state.last_breach):
                raise ValueError('Broken promises need a dated record')
            target = state.coalition_target
            if target is not None:
                if (target not in game.owners or target in (a, b)
                        or not all(first_contact.known(game, x, y) for x, y in ((a, b), (a, target), (b, target)))):
                    raise ValueError('Invalid coalition membership')
                if any(game.diplomacy_between(o, target).non_aggression_active or
                       game.diplomacy_between(o, target).coalition_target for o in (a, b)):
                    raise ValueError('Conflicting coalition commitments')


def load_news(game, data, version):
    if version < 44:
        return
    rows = data['diplomatic_news']
    read = data['diplomatic_news_read']
    if not isinstance(rows, list) or len(rows) > 200 or type(read) is not int or read < 0:
        raise ValueError('Invalid diplomatic dispatches')
    last = 0
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'turn', 'message'}
                or type(row['id']) is not int or row['id'] <= last
                or type(row['turn']) is not int or not 1 <= row['turn'] <= game.turn
                or not isinstance(row['message'], str) or not 0 < len(row['message']) <= 240
                or not row['message'].isprintable()):
            raise ValueError('Invalid diplomatic dispatch')
        last = row['id']
        game.diplomatic_news.append(Dispatch(**row))
    if read > last:
        raise ValueError('Invalid diplomatic news cursor')
    game.diplomatic_news_read = read
