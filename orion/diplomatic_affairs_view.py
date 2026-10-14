"""Coalition proposals, explainable fear, tribute and public racial priorities."""
from . import coalitions, tribute, first_contact, diplomatic_preferences as preferences
from .model import RuleError
from .races import RACES
from .ui import panel, text, paragraph, shorten, GOLD, CYAN, INK, MUTED, RED, PANEL, LINE


def select_tab(app, tab):
    app.dialog['affairs_tab'] = tab
    app.focus = 'dialog_close'


def perform(app, action, owner, target=None, kind='money'):
    try:
        if action == 'form':
            result = coalitions.form(app.game, 'player', owner, target, join_war=True)
        elif action == 'leave':
            result = coalitions.leave(app.game, 'player', owner)
        elif action in ('accept', 'refuse'):
            result = tribute.respond(app.game, owner, action == 'accept')
        else:
            result = tribute.demand(app.game, 'player', owner, kind)
        if app.save_game(autosave=True):
            app.toast(result)
            app.notice_until = app.time+8
    except RuleError as exc:
        app.toast(exc, True)
    app.show_diplomatic_affairs('coalitions' if action in ('form', 'leave') else 'tribute', owner)


def request_coalition(app, owner, target):
    joining = coalitions.war_participants(app.game, 'player', owner, target)
    body = ('This agreement includes mutual non-aggression and +1 relations per turn. '
            'If the named target starts a war against either partner, the other joins in defence. '
            'Starting an offensive war does not enlist your partner. ')
    if joining:
        body += 'CONFIRM WAR ENTRY: '+', '.join(app.game.empire_name_for(o) for o in joining)+' will join the existing war against '+app.game.empire_name_for(target)+'.'
    app.confirm('Form this coalition?', body, 'Agree and join war' if joining else 'Propose coalition',
                lambda: perform(app, 'form', owner, target))


def request_tribute(app, owner, kind):
    amount = tribute.quote(app.game, 'player', owner, kind)
    what = f'{amount} credits' if kind == 'money' else 'one population unit as slaves'
    ready = app.game.turn+tribute.COOLDOWN
    body = (f'Demand {what}. Relations fall by {tribute.RELATION_PENALTY}, bounded at -30 outside war. '
            f'Your next demand against any empire will be available on turn {ready}, even if this one is refused. '
            'The victim remembers intimidation and may seek a coalition. Refusal does not declare war.')
    app.confirm('Demand tribute?', body, 'Send demand', lambda: perform(app, 'demand', owner, kind=kind))


def draw(app):
    surface, game = app.canvas, app.game
    owner = app.dialog['affairs_owner']
    panel(surface, (160, 90, 1120, 720), PANEL, GOLD)
    text(surface, 'Diplomatic agreements & demands', (194, 116), 28, INK, 'title')
    text(surface, shorten(game.empire_name_for(owner), 490, 14), (1247, 125), 14, MUTED, right=True)
    tab = app.dialog.get('affairs_tab', 'coalitions')
    for index, (key, label) in enumerate((('coalitions', 'Coalitions'), ('tribute', 'Tribute & fear'), ('priorities', 'Racial priorities'))):
        app.button('dialog_tab_'+key, label, (194+index*356, 169, 340, 38), lambda k=key: select_tab(app, k),
                   'primary' if tab == key else 'ghost')
    if tab == 'coalitions':
        draw_coalitions(app, owner)
    elif tab == 'tribute':
        draw_tribute(app, owner)
    else:
        draw_priorities(app, owner)
    app.button('dialog_close', 'Close', (1000, 747, 246, 42), app.cancel_dialog, 'primary')


def draw_coalitions(app, owner):
    game, surface = app.game, app.canvas
    state = game.diplomacy_between('player', owner)
    if state.coalition_target:
        target = state.coalition_target
        text(surface, 'ACTIVE COALITION AGREEMENT', (196, 239), 12, CYAN, 'mono')
        text(surface, 'Against '+game.empire_name_for(target), (196, 278), 25, INK, 'title')
        paragraph(surface, 'Mutual non-aggression. +1 relations per turn. The partners defend each other against this target. '
                  'Offensive wars require a separate commitment; no scanner sharing is included.', (196, 332), 970, 18, MUTED, 29)
        for index, member in enumerate(('player', owner)):
            war = game.diplomacy_between(member, target).at_war
            text(surface, game.empire_name_for(member)+(' — at war with the target' if war else ' — deterrence'),
                 (196, 450+index*36), 17, RED if war else CYAN)
        text(surface, f'Agreement began on turn {state.coalition_turn}. It ends when a member leaves or an empire is eliminated.',
             (196, 550), 14, MUTED)
        paragraph(surface, 'Leaving damages relations and is remembered as a broken promise. Other treaties stay in place. '
                  'Existing wars continue.', (196, 585), 970, 15, MUTED, 24)
        app.button('dialog_leave_coalition', 'Leave coalition', (906, 671, 340, 43),
                   lambda: app.confirm('Leave this coalition?', 'This breaks your promise of protection. Relations fall and the partner remembers the breach. Existing wars continue.',
                                       'Leave coalition', lambda: perform(app, 'leave', owner)),
                   enabled=game.strategy_error('player') is None)
        return
    options = [o for o in game.owners if o not in ('player', owner) and game.colony_systems(o)
               and first_contact.known(game, 'player', o) and first_contact.known(game, owner, o)]
    text(surface, 'PROPOSE AGAINST', (196, 239), 12, GOLD, 'mono')
    if not options:
        paragraph(surface, 'Both prospective partners must know a third, living empire. Explore or establish more contacts first.',
                  (196, 285), 960, 19, MUTED, 30)
        return
    target = app.dialog.get('coalition_choice')
    if target not in options:
        target = options[0]
        app.dialog['coalition_choice'] = target
    for i, other in enumerate(options):
        app.button('dialog_target_'+other, shorten(game.empire_name_for(other), 290, 15), (196, 274+i*49, 330, 40),
                   lambda o=other: app.dialog.update(coalition_choice=o), 'primary' if other == target else 'ghost')
    report, accepted = coalitions.willingness(game, owner, 'player', target)
    error = coalitions.proposal_error(game, 'player', owner, target)
    text(surface, 'WILL ACCEPT' if accepted and not error else 'NOT READY TO AGREE', (566, 239), 13,
         CYAN if accepted and not error else GOLD, 'mono')
    text(surface, f'Willingness {report.score:+} / requires {coalitions.ACCEPTANCE}', (566, 274), 22, INK)
    for i, (label, value) in enumerate(report.reasons):
        y = 319+i*28
        text(surface, label, (566, y), 15, MUTED)
        text(surface, f'{value:+}', (1238, y), 16, CYAN if value >= 0 else RED, 'mono', right=True)
    mine, theirs = (preferences.threat(game, o, target).score for o in ('player', owner))
    text(surface, f'Threat assessments: you {mine} · partner {theirs} · each needs {coalitions.MIN_THREAT}', (566, 533), 14, GOLD)
    reasons = preferences.threat(game, 'player', target).reasons
    detail = 'Your concerns: '+('; '.join(f'{label} +{value}' for label, value in reasons if value) or 'none confirmed')+'.'
    paragraph(surface, detail, (196, 581), 1040, 13, MUTED, 20)
    joining = coalitions.war_participants(game, 'player', owner, target)
    text(surface, 'WAR ENTRY REQUIRED — confirmation follows.' if joining else 'Defensive agreement. Offensive wars do not automatically enlist partners.',
         (196, 639), 14, RED if joining else CYAN)
    if error:
        paragraph(surface, error, (196, 677), 675, 14, GOLD, 21)
    app.button('dialog_form_coalition', 'Propose coalition', (906, 671, 340, 43),
               lambda: request_coalition(app, owner, target), enabled=error is None)


def draw_tribute(app, owner):
    game, surface = app.game, app.canvas
    report = preferences.fear(game, owner, 'player')
    text(surface, 'THEIR FEAR OF YOU', (196, 240), 12, GOLD, 'mono')
    text(surface, f'{report.score} / 100', (196, 272), 34, CYAN if report.score >= tribute.FEAR_THRESHOLD else INK, 'title')
    text(surface, f'AI accepts affordable demands at fear {tribute.FEAR_THRESHOLD}.', (196, 324), 14, MUTED)
    for i, (label, value) in enumerate(report.reasons):
        text(surface, label.replace('your colonies', 'their colonies'), (196, 365+i*32), 14, MUTED)
        text(surface, f'{value:+}', (650, 365+i*32), 15, GOLD, 'mono', right=True)
    paragraph(surface, 'Fear uses observed strength and proximity, recent defeats and allied protection. '
              'It does not change the relationship score. Unseen fleets are not counted.', (196, 550), 468, 14, MUTED, 23)
    ready = game.tribute_ready.get('player', 1)
    text(surface, f'Your next demand: turn {ready}' if ready > game.turn else 'Your tribute demand is ready.', (196, 660), 17, CYAN)
    paragraph(surface, f'{tribute.COOLDOWN} turns between demands, across all targets and tribute types.', (196, 695), 480, 12, MUTED, 18)
    pending = next((d for d in game.tribute_demands if d.sender == owner), None)
    if pending:
        panel(surface, (707, 239, 539, 467), border=RED)
        text(surface, 'THEY DEMAND TRIBUTE FROM YOU', (728, 263), 12, RED, 'mono')
        paragraph(surface, tribute.describe(pending), (728, 310), 486, 27, INK, 37)
        paragraph(surface, 'You choose whether to comply. Refusing does not automatically declare war. '
                  'The relations penalty was applied when the demand arrived.', (728, 412), 478, 16, MUTED, 26)
        error = game.strategy_error('player') or tribute.payment_error(game, pending)
        if error:
            paragraph(surface, error, (728, 542), 478, 13, GOLD, 20)
        app.button('dialog_tribute_accept', 'Pay tribute', (728, 635, 230, 45),
                   lambda: app.confirm('Pay this tribute?', 'Transfer '+tribute.describe(pending)+' to '+game.empire_name_for(owner)+'.',
                                       'Pay tribute', lambda: perform(app, 'accept', owner)), enabled=error is None)
        app.button('dialog_tribute_refuse', 'Refuse', (978, 635, 246, 45),
                   lambda: app.confirm('Refuse tribute?', 'No payment is made and no war is declared automatically.',
                                       'Refuse', lambda: perform(app, 'refuse', owner)), enabled=game.strategy_error('player') is None)
        return
    for i, kind in enumerate(('money', 'population')):
        y = 239+i*239
        panel(surface, (707, y, 539, 221))
        text(surface, 'Money tribute' if kind == 'money' else 'Varkesh population tribute', (728, y+20), 21, INK)
        amount = tribute.quote(game, 'player', owner, kind)
        text(surface, f'{amount} CR' if kind == 'money' else '1 population unit → enslaved at your homeworld', (728, y+60), 16, GOLD)
        detail = (f'{tribute.INCOME_TURNS} turns of gross colony income, capped by available treasury.' if kind == 'money' else
                  'Only Varkesh may demand this. The donor keeps at least one citizen; slave capacity applies.')
        paragraph(surface, detail, (728, y+93), 486, 13, MUTED, 19)
        error = tribute.demand_error(game, 'player', owner, kind)
        hint = error or ('Will accept' if report.score >= tribute.FEAR_THRESHOLD else 'Will refuse; sending still uses your cooldown.')
        paragraph(surface, hint, (728, y+148), 295, 12, MUTED, 18)
        app.button('dialog_demand_'+kind, 'Demand', (1076, y+165, 149, 37), lambda k=kind: request_tribute(app, owner, k), enabled=error is None)


def draw_priorities(app, owner):
    surface, game = app.canvas, app.game
    text(surface, 'Priorities guide treaty choices, coalition interests and responses to intimidation.', (196, 237), 15, MUTED)
    for i, (race, nature) in enumerate(preferences.PROFILES.items()):
        y = 279+i*31
        text(surface, RACES[race].name, (196, y), 15, RACES[race].color)
        text(surface, shorten(nature.summary, 866, 14), (378, y), 14, INK)
    state = game.diplomacy_between('player', owner)
    breaches = state.broken_promises.get('player', 0)
    text(surface, f'This partner remembers {breaches} broken promises by you. Current cooperation: {state.cooperation_turns} turns.',
         (196, 649), 14, GOLD)
    text(surface, 'Lithar betrayal memory never decays. Trade remains available at +10; trust affects other treaty thresholds.',
         (196, 681), 13, MUTED)
    text(surface, 'No direct resource, technology or colony trading. Access and mediation are priorities, not separate actions.',
         (196, 708), 13, MUTED)
