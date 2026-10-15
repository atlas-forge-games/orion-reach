"""Infrequent coercive demands. Human recipients always choose their response."""
from dataclasses import dataclass
from . import diplomatic_preferences as preferences, first_contact, raiding, population, exploration
from .coalitions import notify

COOLDOWN = 100
FEAR_THRESHOLD = 75
INCOME_TURNS = 3
RELATION_PENALTY = 15


@dataclass(frozen=True)
class Demand:
    sender: str
    recipient: str
    kind: str
    amount: int
    turn: int


def donor_world(game, target):
    worlds = [(s, p) for s, p in game.settlements(target) if p.population > 1]
    return max(worlds, key=lambda row: (row[1].population, -row[0].id, -row[1].id), default=None)


def quote(game, sender, target, kind='money'):
    from .diplomacy import economic_strength
    if kind == 'population':
        return int(raiding.is_varkesh(game, sender) and raiding.capacity_left(game, sender) > 0 and donor_world(game, target) is not None)
    if kind == 'money':
        return max(0, min(INCOME_TURNS*economic_strength(game, target), game.treasury_for(target),
                          1_000_000_000-game.treasury_for(sender)))
    return 0


def demand_error(game, sender, target, kind='money'):
    if game.strategy_error(sender):
        return game.strategy_error(sender)
    if sender == target or sender not in game.owners or target not in game.owners:
        return 'Choose a foreign empire.'
    if not first_contact.known(game, sender, target):
        return 'Establish first contact before demanding tribute.'
    if not game.colony_systems(sender) or not game.colony_systems(target):
        return 'An eliminated empire cannot give or demand tribute.'
    if kind not in ('money', 'population'):
        return 'Choose money or Varkesh population tribute.'
    if kind == 'population' and not raiding.is_varkesh(game, sender):
        return 'Only the Varkesh can demand enslaved population.'
    ready = game.tribute_ready.get(sender, 1)
    if game.turn < ready:
        return f'Next tribute demand available on turn {ready}, across all targets.'
    if not quote(game, sender, target, kind):
        return ('No transferable population or no free space on the Varkesh homeworld.' if kind == 'population'
                else 'No affordable money tribute is available.')
    return None


def record_pressure(game, sender, target):
    state = game.diplomacy_between(sender, target)
    war = state.at_war
    state.improve(-RELATION_PENALTY)
    if not war:
        state.relations = max(-30, state.relations)  # Coercion alone never declares war.
    state.coercion[sender] = min(100, state.coercion.get(sender, 0)+1)


def payment_error(game, demand):
    if not all(game.colony_systems(o) for o in (demand.sender, demand.recipient)):
        return 'An empire involved in this demand has been eliminated.'
    if demand.kind == 'money':
        if game.treasury_for(demand.recipient) < demand.amount:
            return 'Your treasury cannot cover this demand. You can refuse it.'
        if game.treasury_for(demand.sender)+demand.amount > 1_000_000_000:
            return 'The demanding empire cannot receive this payment.'
    elif raiding.capacity_left(game, demand.sender) < 1 or donor_world(game, demand.recipient) is None:
        return 'Population cannot be transferred without emptying a colony or exceeding slave capacity.'
    return None


def transfer(game, demand):
    from .model import RuleError
    error = payment_error(game, demand)
    if error:
        raise RuleError(error)
    if demand.kind == 'money':
        game._empire(demand.recipient).credits -= demand.amount
        game._empire(demand.sender).credits += demand.amount
    else:
        system, world = donor_world(game, demand.recipient)
        home = raiding.homeworld(game, demand.sender)
        world.population -= 1
        home.slaves += 1
        population.clamp_workforce(world)
        population.clamp_workforce(home)
        exploration.record_survey(game, system.id, demand.recipient)
        exploration.record_survey(game, raiding.home_location(game, demand.sender)[0], demand.sender)
        game.check_victory(convene=False)


def describe(demand):
    return f'{demand.amount} CR' if demand.kind == 'money' else '1 population unit as slaves'


def result_message(game, demand, accepted):
    message = (f'{game.empire_name_for(demand.recipient)} '+('paid ' if accepted else 'refused ')+
               f'{describe(demand)} in tribute to {game.empire_name_for(demand.sender)}.')
    game.diplomacy_between(demand.sender, demand.recipient).record(game.turn, message)
    notify(game, (demand.sender, demand.recipient), message)
    return message


def demand(game, sender, target, kind='money'):
    from .model import RuleError
    error = demand_error(game, sender, target, kind)
    if error:
        raise RuleError(error)
    request = Demand(sender, target, kind, quote(game, sender, target, kind), game.turn)
    accepted = preferences.fear(game, target, sender).score >= FEAR_THRESHOLD
    game.tribute_ready[sender] = game.turn+COOLDOWN
    record_pressure(game, sender, target)
    if target == 'player':
        game.tribute_demands.append(request)
        message = f'{game.empire_name_for(sender)} demands {describe(request)}. Open Diplomacy to accept or refuse.'
        game.diplomacy_between(sender, target).record(game.turn, message)
        notify(game, (sender, target), message)
        return message
    if accepted:
        transfer(game, request)
    return result_message(game, request, accepted)


def respond(game, sender, accept):
    from .model import RuleError
    if type(accept) is not bool:
        raise RuleError('Choose accept or refuse.')
    if game.strategy_error('player'):
        raise RuleError(game.strategy_error('player'))
    request = next((d for d in game.tribute_demands if d.sender == sender), None)
    if request is None:
        raise RuleError('This demand is no longer pending.')
    if accept:
        transfer(game, request)
    game.tribute_demands.remove(request)
    return result_message(game, request, accept)


def normalize(game):
    game.tribute_demands[:] = [d for d in game.tribute_demands
                              if all(game.colony_systems(o) for o in (d.sender, d.recipient))]


def ai_orders(game, owner):
    if game.turn < 12 or game.turn % 6 or game.turn < game.tribute_ready.get(owner, 1):
        return
    candidates = []
    for target in game.owners:
        if target == owner or not first_contact.known(game, owner, target):
            continue
        if game.diplomacy_between(owner, target).relations > 0:
            continue
        # Evaluate only what the recipient knows; this is the same advertised acceptance rule.
        fear = preferences.fear(game, target, owner).score
        if fear < FEAR_THRESHOLD:
            continue
        kind = 'population' if raiding.is_varkesh(game, owner) and quote(game, owner, target, 'population') else 'money'
        if not demand_error(game, owner, target, kind):
            candidates.append((fear, target, kind))
    if candidates:
        _, target, kind = max(candidates)
        demand(game, owner, target, kind)


def load(game, data, version):
    if version < 44:
        return
    ready, demands = data['tribute_ready'], data['tribute_demands']
    if (not isinstance(ready, dict) or not set(ready) <= set(game.owners)
            or any(type(t) is not int or not 1 <= t <= game.turn+COOLDOWN for t in ready.values())
            or not isinstance(demands, list) or len(demands) > len(game.opponents)):
        raise ValueError('Invalid tribute cooldowns or demands')
    game.tribute_ready = ready.copy()
    senders = set()
    for row in demands:
        if (not isinstance(row, dict) or set(row) != {'sender', 'recipient', 'kind', 'amount', 'turn'}
                or row['sender'] not in game.opponents or row['recipient'] != 'player' or game.is_observer
                or row['sender'] in senders or row['kind'] not in ('money', 'population')
                or type(row['turn']) is not int or not 1 <= row['turn'] <= game.turn
                or ready.get(row['sender']) != row['turn']+COOLDOWN
                or type(row['amount']) is not int or not 1 <= row['amount'] <= 1_000_000_000
                or not first_contact.known(game, 'player', row['sender'])
                or (row['kind'] == 'population' and (row['amount'] != 1 or not raiding.is_varkesh(game, row['sender'])))):
            raise ValueError('Invalid pending tribute demand')
        senders.add(row['sender'])
        game.tribute_demands.append(Demand(**row))
