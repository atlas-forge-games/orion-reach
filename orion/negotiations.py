"""Finite diplomatic offers, observable motives, territorial promises and peace.

Human responses are never inferred from relation scores. AI decisions use the
same assessment displayed by the interface, and only intelligence it can see.
"""
from . import coalitions, diplomacy, first_contact, diplomatic_preferences as preferences
from .diplomacy import Proposal, TerritorialPromise
from .production import distance_ly

PROMISE_TURNS = CEASEFIRE_TURNS = 20
PROPOSAL_TURNS = 5
INITIATIVE_COOLDOWN = 20
PEACE_THRESHOLD = 50
TERRITORY_THRESHOLD = 10
BREAK_PENALTY, REFUSAL_PENALTY, HONOUR_BONUS = 15, 3, 5
KINDS = (*diplomacy.TREATIES, 'coalition', 'territory', 'peace')
STATE_FIELDS = ('proposal', 'territorial_promises', 'honoured_promises',
                'initiative_ready_turn', 'ceasefire_until', 'war_started_turn')


def pairs(game):
    for i, a in enumerate(game.owners):
        for b in game.owners[i+1:]:
            yield a, b, game.diplomacy_between(a, b)


def incoming(game, recipient='player'):
    return [s.proposal for _, _, s in pairs(game) if s.proposal
            and s.proposal.recipient == recipient and s.proposal.expires_turn > game.turn
            and game.colony_systems(s.proposal.sender) and game.colony_systems(recipient)]


def system_promises(game, system_id):
    """Only player commitments are public on the player's chart."""
    return [p for a, b, state in pairs(game) if 'player' in (a, b)
            for p in state.territorial_promises if p.system_id == system_id and p.until_turn > game.turn
            and game.colony_systems(p.promisor) and game.colony_systems(p.beneficiary)]


def promises_at(game, owner, system_id):
    return [p for _, _, s in pairs(game) for p in s.territorial_promises
            if p.promisor == owner and p.system_id == system_id and p.until_turn > game.turn
            and game.colony_systems(p.beneficiary)]


def settlement_warning(game, owner, system_id):
    promises = promises_at(game, owner, system_id)
    if not promises:
        return ''
    names = ', '.join(game.empire_name_for(p.beneficiary) for p in promises)
    return (f'BREAKS YOUR PROMISE to {names}: relations -{BREAK_PENALTY} and a remembered breach. '
            'No war is declared automatically. ')


def log(game, a, b, message, *, quiet=True, others=()):
    game.diplomacy_between(a, b).record(game.turn, message[:180])
    coalitions.notify(game, (a, b, *others), message[:240], quiet=quiet)


def treaty_assessment(game, action, target, proposer='player'):
    state = game.diplomacy_between(proposer, target)
    threshold = diplomacy.acceptance_threshold(game, action, target, proposer)
    base = {'trade': 10, 'non_aggression': 0, 'friendship': 30,
            'research': diplomacy.RACES[game._empire(target).race_id].research_threshold}[action]
    report = preferences.Assessment(state.relations-threshold, (
        ('Current relations', state.relations), ('Required by this civilization', -base),
        ('Remembered treaty breaches', -(threshold-base))))
    return report, state.relations >= threshold and not state.at_war


def territorial_candidates(game, issuer, recipient):
    """Neutral, mutually surveyed, reachable systems near the issuer's colonies."""
    if any(game._empire(o).race_id in ('skirr', 'varkesh', 'wanderers') for o in (issuer, recipient)):
        return []
    homes = game.colony_systems(issuer)
    result = []
    for system in game.systems:
        known = [game.known_system(system.id, o) for o in (issuer, recipient)]
        if not all(known) or not homes:
            continue
        if any(p.owner or p.outpost_owner or p.orbital_station for s in known for p in s.worlds):
            continue
        if not all(game.within_fuel_range(system.id, o) for o in (issuer, recipient)):
            continue
        if not all(any(not p.is_gas_giant and game.can_settle(p, o) for p in s.worlds)
                   for o, s in zip((issuer, recipient), known)):
            continue
        if min(distance_ly(system, h) for h in homes) > 30:
            continue
        result.append(system.id)
    return sorted(result, key=lambda sid: (min(distance_ly(game.systems[sid], h) for h in homes), sid))


def territorial_assessment(game, issuer, recipient, system_id):
    state = game.diplomacy_between(issuer, recipient)
    nature = preferences.profile(game, recipient)
    system = game.systems[system_id]
    # Own routes and ships are known. Never inspect the other empire's orders.
    committed = any(s.kind == 'colony_ship' and (s.destination == system_id if s.has_course else s.system_id == system_id)
                    for s in game.ships_owned_by(recipient))
    nearby = any(distance_ly(system, h) <= 15 for h in game.colony_systems(recipient))
    reasons = (('Relations', state.relations//3), ('Racial pragmatism', nature.pragmatism),
               ('Fear of the requesting empire', preferences.fear(game, recipient, issuer).score//2),
               ('Own colony expedition', -30 if committed else 0),
               ('Near own colonies', -nature.frontier*5 if nearby else 0),
               ('Broken promises by requester', -min(30, state.broken_promises.get(issuer, 0)*nature.memory)))
    report = preferences.Assessment(sum(v for _, v in reasons), reasons)
    return report, report.score >= TERRITORY_THRESHOLD


def peace_assessment(game, recipient, sender, payment=0):
    state = game.diplomacy_between(sender, recipient)
    age = max(0, game.turn-(state.war_started_turn or state.contact_turn or game.turn))
    defeated = state.last_defeat.get(recipient, 0)
    victorious = state.last_defeat.get(sender, 0)
    reasons = (('Interest in ending the war', 20), ('Duration of the war', min(40, age*2)),
               ('Recent military defeat', 25 if defeated and game.turn-defeated <= 10 else 0),
               ('Observed military danger', preferences.fear(game, recipient, sender).score//2),
               ('Recent victory', -15 if victorious and game.turn-victorious <= 10 else 0),
               ('Racial resolve', -preferences.profile(game, recipient).resolve),
               ('Offered reparations', min(30, payment//10)))
    report = preferences.Assessment(sum(v for _, v in reasons), reasons)
    return report, report.score >= PEACE_THRESHOLD


def reparation_quote(game, sender):
    return min(max(0, game._empire(sender).credits), max(25, diplomacy.economic_strength(game, sender)*5))


def proposal_error(game, sender, recipient, kind, *, system_id=None, target=None, payment=0, responding=False):
    if sender == recipient or any(o not in game.owners for o in (sender, recipient)):
        return 'Choose two different empires.'
    actor = recipient if responding else sender
    if error := game.strategy_error(actor):
        return error
    if not all(game.colony_systems(o) for o in (sender, recipient)):
        return 'An empire has been eliminated.'
    if not first_contact.known(game, sender, recipient):
        return 'Establish first contact first.'
    if kind not in KINDS:
        return 'Unknown diplomatic proposal.'
    if any(game._empire(o).race_id == 'skirr' for o in (sender, recipient)):
        return 'The Skirr Swarm rejects negotiated agreements.'
    state = game.diplomacy_between(sender, recipient)
    if type(payment) is not int or payment < 0 or payment > max(0, game._empire(sender).credits):
        return 'The offering empire cannot afford these reparations.'
    if (kind != 'peace' and payment or kind != 'territory' and system_id is not None
            or kind != 'coalition' and target is not None):
        return 'These terms do not belong to this proposal.'
    if not responding and state.proposal:
        return 'Answer the pending proposal from this empire first.'
    if game.turn < state.offer_ready_turn:
        return f'Available on turn {state.offer_ready_turn}.'
    if kind == 'peace':
        if not state.at_war:
            return 'You are not at war with this empire.'
        if coalitions.treaty_conflict(game, sender, recipient):
            return 'Leave coalitions against this empire before negotiating separate peace.'
    elif state.at_war:
        return 'Negotiate peace before making other agreements.'
    if kind in diplomacy.TREATIES:
        if getattr(state, kind+'_active'):
            return 'This agreement is already active.'
        if kind in ('friendship', 'non_aggression') and coalitions.treaty_conflict(game, sender, recipient):
            return 'An active coalition opposes this empire.'
    if kind == 'coalition':
        a, b = ('player', sender) if recipient == 'player' else (sender, recipient)
        return coalitions.proposal_error(game, a, b, target)
    if kind == 'territory':
        if type(system_id) is not int or system_id not in territorial_candidates(game, sender, recipient):
            return 'Choose a mutually surveyed, unsettled system near your border and within both empires\' range.'
        if any(p.promisor == recipient and p.until_turn > game.turn for p in state.territorial_promises):
            return 'This empire already has an active territorial promise to you.'
    return None


def assessment(game, sender, recipient, kind, *, system_id=None, target=None, payment=0):
    if kind in diplomacy.TREATIES:
        return treaty_assessment(game, kind, recipient, sender)
    if kind == 'coalition':
        return coalitions.willingness(game, recipient, sender, target)
    if kind == 'territory':
        return territorial_assessment(game, sender, recipient, system_id)
    return peace_assessment(game, recipient, sender, payment)


def describe(game, proposal):
    kind = proposal.kind
    if kind == 'territory':
        return f'Do not colonize {game.system_name(proposal.system_id)} for {PROMISE_TURNS} turns after accepting.'
    if kind == 'coalition':
        joining = coalitions.war_participants(game, proposal.sender, proposal.recipient, proposal.target)
        suffix = ' Accepting joins the existing war.' if joining else ' This is a defensive agreement.'
        return f'Coalition against {game.empire_name_for(proposal.target)}.'+suffix
    if kind == 'peace':
        extra = (f' {game.empire_name_for(proposal.sender)} pays {proposal.payment} CR to '
                 f'{game.empire_name_for(proposal.recipient)}.') if proposal.payment else ' No reparations.'
        return f'Peace with current territorial holdings and a {CEASEFIRE_TURNS}-turn ceasefire.'+extra
    return diplomacy.TREATIES[kind]+(' including trade, non-aggression and shared scanners.' if kind == 'friendship' else '.')


def apply_agreement(game, sender, recipient, kind, *, system_id=None, target=None, payment=0):
    """Private commit step; callers validate legality, willingness and funds first."""
    state = game.diplomacy_between(sender, recipient)
    if kind == 'coalition':
        a, b = ('player', sender) if recipient == 'player' else (sender, recipient)
        return coalitions.form(game, a, b, target, join_war=True)
    if kind in diplomacy.TREATIES:
        setattr(state, kind+'_active', True)
        if kind == 'friendship':
            state.trade_active = state.non_aggression_active = True
            from . import sensors
            sensors.refresh(game)
            first_contact.refresh(game)
        message = f'{diplomacy.TREATIES[kind]} accepted.'
    elif kind == 'territory':
        state.territorial_promises[:] = [p for p in state.territorial_promises if p.promisor != recipient]
        state.territorial_promises.append(TerritorialPromise(recipient, sender, system_id, game.turn, game.turn+PROMISE_TURNS))
        message = f'{game.empire_name_for(recipient)} promises not to colonize {game.system_name(system_id)} until turn {game.turn+PROMISE_TURNS}.'
    else:
        game._empire(sender).credits -= payment
        game._empire(recipient).credits += payment
        state.relations = max(-30, state.relations)
        state.war_started_turn = 0
        state.ceasefire_until = game.turn+CEASEFIRE_TURNS
        message = f'Peace agreed. Current holdings remain; ceasefire until turn {state.ceasefire_until}.'
        if payment:
            message += f' {game.empire_name_for(sender)} pays {payment} CR.'
    state.offer_ready_turn = game.turn+diplomacy.OFFER_COOLDOWN
    log(game, sender, recipient, message)
    return message


def offer(game, sender, recipient, kind, *, system_id=None, target=None, payment=0):
    from .model import RuleError
    terms = dict(system_id=system_id, target=target, payment=payment)
    if error := proposal_error(game, sender, recipient, kind, **terms):
        raise RuleError(error)
    state = game.diplomacy_between(sender, recipient)
    if recipient == 'player':
        if game.turn < state.initiative_ready_turn:
            raise RuleError('This empire is waiting before approaching you again.')
        state.proposal = Proposal(sender, recipient, kind, game.turn, game.turn+PROPOSAL_TURNS, **terms)
        state.initiative_ready_turn = game.turn+INITIATIVE_COOLDOWN
        message = f'{game.empire_name_for(sender)}: {describe(game, state.proposal)} Reply before turn {state.proposal.expires_turn} in Diplomacy.'
        log(game, sender, recipient, message, quiet=False, others=(target,) if target else ())
        return message
    _, accepted = assessment(game, sender, recipient, kind, **terms)
    if accepted:
        return apply_agreement(game, sender, recipient, kind, **terms)
    state.offer_ready_turn = game.turn+diplomacy.OFFER_COOLDOWN
    if kind == 'territory':
        state.relations = max(-30, state.relations-REFUSAL_PENALTY)
    message = 'Proposal declined. No agreement was made.'
    log(game, sender, recipient, message)
    return message


def respond(game, sender, accept, *, created_turn=None):
    from .model import RuleError
    if type(accept) is not bool or sender not in game.opponents:
        raise RuleError('Choose a valid proposal and response.')
    state = game.diplomacy_between(sender, 'player')
    p = state.proposal
    if (p is None or p.recipient != 'player' or p.expires_turn <= game.turn
            or created_turn is not None and p.created_turn != created_turn):
        raise RuleError('This proposal is no longer available.')
    if error := game.strategy_error('player'):
        raise RuleError(error)
    if accept:
        terms = dict(system_id=p.system_id, target=p.target, payment=p.payment)
        if error := proposal_error(game, sender, 'player', p.kind, responding=True, **terms):
            raise RuleError(error)
        # Recheck the AI's commitment if the strategic situation changed.
        # Territorial demands ask for a human choice, not a human AI score.
        if p.kind in diplomacy.TREATIES:
            willing = treaty_assessment(game, p.kind, sender, 'player')[1]
        elif p.kind == 'coalition':
            willing = coalitions.willingness(game, sender, 'player', p.target)[1]
        elif p.kind == 'peace':
            willing = peace_assessment(game, sender, 'player')[1]
        else:
            willing = True
        if not willing:
            raise RuleError('The situation changed; this empire is no longer willing to agree. You can dismiss the offer.')
        message = apply_agreement(game, sender, 'player', p.kind, **terms)
    else:
        if p.kind == 'territory':
            state.relations = max(-30, state.relations-REFUSAL_PENALTY)
        message = 'Proposal refused. No commitment was made.'
        log(game, sender, 'player', message)
    state.proposal = None
    return message


def record_settlement(game, owner, system_id):
    for p in promises_at(game, owner, system_id):
        state = game.diplomacy_between(owner, p.beneficiary)
        state.territorial_promises.remove(p)
        diplomacy.remember_breach(game, owner, p.beneficiary)
        state.relations = max(-100 if state.at_war else -30, state.relations-BREAK_PENALTY)
        log(game, owner, p.beneficiary,
            f'{game.empire_name_for(owner)} broke its territorial promise at {game.system_name(system_id)}. Relations -{BREAK_PENALTY}; breach remembered.')


def advance(game):
    """Run at the start and end of a turn; deadlines use an exclusive end turn."""
    for a, b, state in pairs(game):
        alive = all(game.colony_systems(o) for o in (a, b))
        if not alive:
            state.proposal = None
            state.territorial_promises.clear()
            state.ceasefire_until = 0
            continue
        if state.ceasefire_until and game.turn >= state.ceasefire_until:
            state.ceasefire_until = 0
            log(game, a, b, 'Ceasefire period completed. Peace continues; war is not automatic.')
        p = state.proposal
        redundant = bool(p and (p.kind in diplomacy.TREATIES and getattr(state, p.kind+'_active')
                               or p.kind == 'coalition' and state.coalition_target))
        if p and (game.turn >= p.expires_turn or (p.kind == 'peace') != state.at_war or redundant):
            state.proposal = None
            log(game, a, b, 'Diplomatic proposal expired or was overtaken by events. No commitment was made.')
        for promise in state.territorial_promises[:]:
            if game.turn >= promise.until_turn:
                state.territorial_promises.remove(promise)
                state.honoured_promises[promise.promisor] = min(100, state.honoured_promises.get(promise.promisor, 0)+1)
                before = state.relations
                state.relations = min(-31 if state.at_war else 100, state.relations+HONOUR_BONUS)
                log(game, a, b, f'{game.empire_name_for(promise.promisor)} honoured its promise at {game.system_name(promise.system_id)}. Relations +{state.relations-before}.')


def ai_orders(game, owner):
    """At most one new human-facing proposal per turn, with three pending total."""
    if game.is_observer or game.strategy_error(owner) or game.turn < 4 or game.turn % 4:
        return
    if not first_contact.known(game, owner, 'player'):
        return
    state = game.diplomacy_between(owner, 'player')
    if (state.proposal or game.turn < state.initiative_ready_turn
            or game.turn < state.contact_turn+3 or len(incoming(game)) >= 3
            or any(s.proposal and s.proposal.created_turn == game.turn for _, _, s in pairs(game))):
        return
    candidates = []
    if state.at_war:
        if peace_assessment(game, owner, 'player')[1]:
            candidates.append((1000, 'peace', {}))
    else:
        nature = preferences.profile(game, owner)
        for target in game.owners:
            if target in (owner, 'player'):
                continue
            if not coalitions.proposal_error(game, 'player', owner, target):
                report, yes = coalitions.willingness(game, owner, 'player', target)
                if yes:
                    candidates.append((500+report.score, 'coalition', {'target': target}))
        for sid in territorial_candidates(game, owner, 'player'):
            # Only a visible colony expedition can trigger a territorial demand.
            # A hidden destination is never read, even for a visible ship.
            if any(s.owner == 'player' and s.kind == 'colony_ship' and not s.in_transit and s.system_id == sid
                   for s in game.visible_ships(owner)):
                candidates.append((300+nature.frontier, 'territory', {'system_id': sid}))
                break
        for action, priority in (('trade', nature.trade), ('research', nature.research),
                                 ('friendship', nature.friendship), ('non_aggression', nature.friendship)):
            if priority and treaty_assessment(game, action, owner, 'player')[1]:
                if action != 'trade' or diplomacy.trade_income(game, owner, 'player'):
                    candidates.append((priority*10+(2 if action == 'friendship' else 0), action, {}))
    for _, kind, terms in sorted(candidates, key=lambda row: -row[0]):
        if not proposal_error(game, owner, 'player', kind, **terms):
            offer(game, owner, 'player', kind, **terms)
            return


def load_state(data, turn, version):
    if not isinstance(data, dict):
        raise ValueError('Invalid diplomatic state')
    result = dict(data)
    if version < 65:
        return {k: v for k, v in result.items() if k not in STATE_FIELDS}
    def integer(value, lo, hi):
        return type(value) is int and lo <= value <= hi
    for key, lo, hi in (('initiative_ready_turn', 1, turn+INITIATIVE_COOLDOWN),
                        ('ceasefire_until', 0, turn+CEASEFIRE_TURNS), ('war_started_turn', 0, turn)):
        if not integer(result[key], lo, hi):
            raise ValueError('Invalid diplomacy deadline')
    honoured = result['honoured_promises']
    if not isinstance(honoured, dict) or len(honoured) > 2 or any(not isinstance(k, str) or not integer(v, 1, 100) for k, v in honoured.items()):
        raise ValueError('Invalid promise history')
    p = result['proposal']
    if p is not None:
        if not isinstance(p, dict):
            raise ValueError('Invalid proposal')
        p = Proposal(**p)
        if (not isinstance(p.sender, str) or not isinstance(p.recipient, str) or p.kind not in KINDS
                or not integer(p.created_turn, 1, turn) or type(p.expires_turn) is not int
                or p.expires_turn != p.created_turn+PROPOSAL_TURNS or not integer(p.payment, 0, 1_000_000_000)
                or p.kind != 'peace' and p.payment
                or (p.kind == 'territory') != (p.system_id is not None)
                or p.system_id is not None and not integer(p.system_id, 0, 10000)
                or (p.kind == 'coalition') != (p.target is not None)
                or p.target is not None and not isinstance(p.target, str)):
            raise ValueError('Invalid proposal terms')
        result['proposal'] = p
    promises = result['territorial_promises']
    if not isinstance(promises, list) or len(promises) > 2:
        raise ValueError('Invalid territorial promises')
    parsed = []
    for row in promises:
        if not isinstance(row, dict):
            raise ValueError('Invalid territorial promise')
        promise = TerritorialPromise(**row)
        if (not isinstance(promise.promisor, str) or not isinstance(promise.beneficiary, str)
                or not integer(promise.system_id, 0, 10000) or not integer(promise.started_turn, 1, turn)
                or type(promise.until_turn) is not int or promise.until_turn != promise.started_turn+PROMISE_TURNS):
            raise ValueError('Invalid territorial promise')
        parsed.append(promise)
    if len({p.promisor for p in parsed}) != len(parsed):
        raise ValueError('Duplicate territorial promises')
    result['territorial_promises'] = parsed
    return result


def validate(game):
    for a, b, state in pairs(game):
        if not set(state.honoured_promises) <= {a, b}:
            raise ValueError('Promise history names a nonparticipant')
        p = state.proposal
        if p:
            if ({p.sender, p.recipient} != {a, b} or p.recipient != 'player'
                    or not first_contact.known(game, a, b)
                    or p.system_id is not None and p.system_id >= len(game.systems)
                    or p.target is not None and (p.target not in game.owners or p.target in (a, b)
                        or not first_contact.known(game, a, p.target) or not first_contact.known(game, b, p.target))):
                raise ValueError('Invalid proposal participants')
        for promise in state.territorial_promises:
            if ({promise.promisor, promise.beneficiary} != {a, b} or promise.system_id >= len(game.systems)
                    or not first_contact.known(game, a, b)):
                raise ValueError('Invalid territorial commitment')
        if state.ceasefire_until > game.turn and state.at_war:
            raise ValueError('A ceasefire cannot coexist with war')
