"""Review offers and their actual decision reasons in the diplomacy console."""
from . import negotiations as rules, diplomacy, coalitions
from .diplomacy import Proposal
from .model import RuleError
from .pagination import page_rows
from .ui import CYAN, GOLD, INK, MUTED, RED, panel, paragraph, shorten, text


def open_panel(app, owner=None, *, reasons=False, action=None):
    app.show_diplomatic_affairs('reasons' if reasons else 'negotiations', owner)
    if app.dialog and action:
        app.dialog['reason_action'] = action


def perform(app, owner, callback):
    try:
        callback()
        app.save_game(autosave=True)
    except RuleError as exc:
        app.toast(exc, True)
    app.show_diplomatic_affairs('negotiations', owner)


def request_response(app, owner, accept):
    p = app.game.diplomacy_between('player', owner).proposal
    if not p:
        return
    detail = rules.describe(app.game, p) if accept else 'No commitment will be made.'
    if p.kind == 'territory':
        detail += (' Colonizing during the promise costs 15 relations and is remembered as a breach.' if accept else
                   ' Refusing a territorial demand costs 3 relations, but creates no breach or automatic war.')
    app.confirm('Accept proposal?' if accept else 'Refuse proposal?', detail,
                'Accept agreement' if accept else 'Refuse',
                lambda: perform(app, owner, lambda: rules.respond(app.game, owner, accept, created_turn=p.created_turn)))


def request_offer(app, owner, kind, **terms):
    p = Proposal('player', owner, kind, app.game.turn, app.game.turn+rules.PROPOSAL_TURNS, **terms)
    app.confirm('Propose peace?' if kind == 'peace' else 'Request territorial promise?',
                rules.describe(app.game, p)+(' A refusal costs 3 relations; it does not start a war.' if kind == 'territory' else ''),
                'Send proposal', lambda: perform(app, owner, lambda: rules.offer(app.game, 'player', owner, kind, **terms)))


def draw(app, owner):
    game, surface = app.game, app.canvas
    state = game.diplomacy_between('player', owner)
    panel(surface, (194, 230, 514, 495))
    panel(surface, (726, 230, 520, 495))
    p = state.proposal
    if p and p.expires_turn > game.turn:
        text(surface, 'INCOMING PROPOSAL', (214, 248), 12, GOLD, 'mono')
        paragraph(surface, rules.describe(game, p), (214, 283), 470, 20, INK, 29)
        text(surface, f'Reply before turn {p.expires_turn} · {p.expires_turn-game.turn} turns left', (214, 414), 14, GOLD)
        terms = dict(system_id=p.system_id, target=p.target, payment=p.payment)
        error = rules.proposal_error(game, owner, 'player', p.kind, responding=True, **terms)
        if error:
            paragraph(surface, error, (214, 449), 470, 14, MUTED, 22)
        else:
            paragraph(surface, 'Accepting makes this commitment binding. You may also refuse or let the proposal expire.',
                      (214, 449), 470, 15, MUTED, 24)
        app.button('dialog_proposal_accept', 'Accept', (214, 539, 224, 44),
                   lambda: request_response(app, owner, True), 'primary', enabled=error is None)
        app.button('dialog_proposal_refuse', 'Refuse', (454, 539, 232, 44),
                   lambda: request_response(app, owner, False), enabled=game.strategy_error('player') is None)
        paragraph(surface, 'Offers expire without creating a promise. A direct territorial refusal costs 3 relations; breaking an accepted promise costs 15.',
                  (214, 614), 470, 14, MUTED, 22)
    elif state.at_war:
        text(surface, 'NEGOTIATE PEACE', (214, 248), 12, GOLD, 'mono')
        paragraph(surface, 'Keep current territorial holdings. A 20-turn ceasefire prevents attacks and war declarations.',
                  (214, 283), 470, 18, INK, 28)
        quote = rules.reparation_quote(game, 'player')
        for i, payment in enumerate((0, quote)):
            y = 383+i*121
            report, accepted = rules.peace_assessment(game, owner, 'player', payment)
            error = rules.proposal_error(game, 'player', owner, 'peace', payment=payment)
            label = 'No reparations' if not i else f'Offer {payment} CR reparations'
            text(surface, label, (214, y), 18, INK)
            text(surface, 'Will accept' if accepted and not error else 'Will decline' if not error else 'Unavailable',
                 (214, y+34), 14, CYAN if accepted and not error else GOLD)
            app.button('dialog_peace_'+str(i), 'Propose', (545, y+25, 140, 38),
                       lambda value=payment: request_offer(app, owner, 'peace', payment=value),
                       enabled=error is None and (not i or payment > 0))
        error = rules.proposal_error(game, 'player', owner, 'peace')
        paragraph(surface, error or 'Payment transfers only if peace is accepted. Decision reasons show how war duration, losses and military danger affect willingness.',
                  (214, 632), 470, 14, MUTED, 22)
    else:
        text(surface, 'TERRITORIAL PROMISE', (214, 248), 12, GOLD, 'mono')
        paragraph(surface, 'Ask this empire to leave one unsettled system uncolonized for 20 turns.',
                  (214, 283), 470, 18, INK, 28)
        options = rules.territorial_candidates(game, 'player', owner)
        sid = app.dialog.get('territory_choice')
        if sid not in options:
            sid = options[0] if options else None
            app.dialog['territory_choice'] = sid
        if options:
            for i, candidate in enumerate(page_rows(app, options, 3, 'territories', (214, 501, 470, 34), state=app.dialog)):
                app.button('dialog_territory_'+str(candidate), shorten(game.system_name(candidate), 435, 17),
                           (214, 365+i*43, 470, 35), lambda value=candidate: app.dialog.update(territory_choice=value),
                           'primary' if candidate == sid else 'ghost')
            report, accepted = rules.territorial_assessment(game, 'player', owner, sid)
            error = rules.proposal_error(game, 'player', owner, 'territory', system_id=sid)
            paragraph(surface, error or ('Will accept this request.' if accepted else 'Will refuse; sending costs 3 relations.'),
                      (214, 560), 470, 14, GOLD if error or not accepted else CYAN, 22)
            app.button('dialog_request_territory', 'Request promise', (214, 643, 470, 44),
                       lambda: request_offer(app, owner, 'territory', system_id=sid), enabled=error is None)
        else:
            paragraph(surface, 'No eligible system. Both empires must have surveyed an unsettled system, be able to reach and colonize it, and it must be near your border.',
                      (214, 377), 470, 17, MUTED, 28)
    text(surface, 'COMMITMENTS & RELIABILITY', (746, 248), 12, CYAN, 'mono')
    ceasefire = f'Ceasefire: {state.ceasefire_until-game.turn} turns left (until T{state.ceasefire_until})' if state.ceasefire_until > game.turn else 'No active ceasefire'
    text(surface, ceasefire, (746, 283), 17, INK)
    active = [p for p in state.territorial_promises if p.until_turn > game.turn]
    if not active:
        text(surface, 'No active territorial promises', (746, 324), 16, MUTED)
    for i, promise in enumerate(active):
        who = 'You' if promise.promisor == 'player' else 'They'
        paragraph(surface, f'{who}: no colonization at {game.system_name(promise.system_id)} until T{promise.until_turn}.',
                  (746, 324+i*65), 478, 16, GOLD, 24)
    for i, (subject, key) in enumerate((('Your record', 'player'), ('Their record', owner))):
        text(surface, subject, (746, 468+i*58), 15, INK)
        text(surface, f"{state.honoured_promises.get(key, 0)} promises honoured · {state.broken_promises.get(key, 0)} breaches remembered",
             (746, 493+i*58), 14, MUTED)
    paragraph(surface, '◇ marks promised systems on the map. Honour a promise for +5 relations. Lithar never forget betrayal. Peace continues after a ceasefire expires.',
              (746, 599), 478, 14, MUTED, 23)
    app.button('dialog_show_reasons', 'View decision reasons', (746, 673, 478, 33),
               lambda: app.dialog.update(affairs_tab='reasons'), 'ghost')


def draw_reasons(app, owner):
    game, surface = app.game, app.canvas
    state = game.diplomacy_between('player', owner)
    options = list(diplomacy.TREATIES)+['peace', 'territory']
    action = app.dialog.get('reason_action', 'peace' if state.at_war else 'trade')
    if action not in options:
        action = 'trade'
    labels = {**diplomacy.TREATIES, 'peace': 'Peace agreement', 'territory': 'Territorial promise'}
    for i, key in enumerate(options):
        app.button('dialog_reason_'+key, labels[key], (194, 239+i*51, 310, 41),
                   lambda value=key: app.dialog.update(reason_action=value), 'primary' if key == action else 'ghost')
    terms = {}
    if action == 'territory':
        candidates = rules.territorial_candidates(game, 'player', owner)
        sid = app.dialog.get('territory_choice')
        if sid not in candidates:
            sid = candidates[0] if candidates else None
        if sid is None:
            paragraph(surface, 'No eligible contested system. Select a mutually surveyed frontier system in Negotiations when one becomes available.',
                      (547, 275), 680, 20, MUTED, 32)
            return
        terms['system_id'] = sid
    report, accepted = rules.assessment(game, 'player', owner, action, **terms)
    error = rules.proposal_error(game, 'player', owner, action, **terms)
    text(surface, labels[action], (547, 239), 26, INK, 'title')
    text(surface, 'UNAVAILABLE' if error else 'WILL ACCEPT' if accepted else 'WILL DECLINE',
         (1244, 284), 15, GOLD if error or not accepted else CYAN, 'mono', right=True)
    if action == 'territory':
        text(surface, shorten(game.system_name(terms['system_id']), 680, 17), (547, 284), 17, MUTED)
    for i, (label, value) in enumerate(report.reasons):
        y = 332+i*36
        text(surface, label, (547, y), 16, MUTED)
        text(surface, f'{value:+}', (1244, y), 17, CYAN if value >= 0 else RED, 'mono', right=True)
    threshold = rules.PEACE_THRESHOLD if action == 'peace' else rules.TERRITORY_THRESHOLD if action == 'territory' else 0
    text(surface, f'Willingness {report.score:+} · needs {threshold:+}', (547, 610), 20, INK)
    detail = error or ('Trade always requires +10 relations. Other treaties account for this civilization and remembered breaches.'
                      if action in diplomacy.TREATIES else 'These are the same reasons used when the AI decides your offer.')
    paragraph(surface, detail, (547, 652), 680, 15, MUTED, 24)
    app.button('dialog_back_negotiations', 'Negotiations', (194, 670, 310, 41),
               lambda: app.dialog.update(affairs_tab='negotiations'), 'ghost')
