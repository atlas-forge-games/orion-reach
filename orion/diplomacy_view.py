"""Treaties, shared intelligence and a selectable portrait overview of relations."""

import pygame as pg

from . import alignment, diplomacy as rules, first_contact
from .race_art import draw_race_portrait
from .races import RACES
from .personalities import PERSONALITIES, personality
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text


def relation_color(score):
    return CYAN if score >= 25 else RED if score < 0 else GOLD


def select_contact(app, owner):
    app.rival_id, app.rival_page = owner, 0


def draw_relations_strip(app):
    game, surface = app.game, app.canvas
    owners, selected = first_contact.known_opponents(game), app.selected_rival_id()
    panel(surface, (64, 186, 1312, 126))
    text(surface, "RELATIONS TO YOU", (80, 198), 9, MUTED, "mono", 1)
    draw_race_portrait(surface, game.race_id, (80, 220, 40, 40))
    text(surface, shorten(game.empire_name, 105, 11), (129, 224), 11, INK)
    text(surface, f"{len(owners)} contacts", (129, 244), 10, FAINT)
    app.button("contact_previous", "←", (80, 274, 46, 27), lambda: app.change_rival(-1), enabled=len(owners)>1)
    app.button("contact_next", "→", (137, 274, 46, 27), lambda: app.change_rival(1), enabled=len(owners)>1)
    if not owners:
        text(surface, "Explore to meet other civilizations. Their portraits and relations will appear here.", (266, 240), 15, MUTED)
        return
    # Eleven portraits fit at once; the arrows page through larger galaxies.
    start = (owners.index(selected)//11)*11
    for index, owner in enumerate(owners[start:start+11]):
        x = 246+index*102
        state, race = game.diplomacy_between("player", owner), RACES[game._empire(owner).race_id]
        panel(surface, (x, 193, 96, 111), border=GOLD if selected == owner else LINE)
        draw_race_portrait(surface, race.id, (x+21, 198, 54, 54))
        text(surface, shorten(race.name, 86, 10), (x+5, 258), 10, race.color)
        text(surface, f"{state.relations:+}", (x+25, 278), 17, relation_color(state.relations), "mono")
        app.button(f"diplomacy_contact_{owner}", "", (x, 193, 96, 111),
                   lambda target=owner: select_contact(app, target), "hotspot")


def draw_contact_profile(surface, race, empire_name):
    panel(surface, (64, 330, 338, 450))
    draw_race_portrait(surface, race.id, (145, 347, 176, 176))
    text(surface, shorten(empire_name, 291, 23, "title"), (87, 537), 23, INK, "title")
    text(surface, race.focus, (89, 575), 12, race.color)
    paragraph(surface, PERSONALITIES[race.id].traits, (89, 603), 290, 13, MUTED, 18)


def draw_treaty(app, owner, state, action, x, y):
    game, surface = app.game, app.canvas
    active = getattr(state, f"{action}_active")
    threshold = rules.acceptance_threshold(game, action, owner)
    included = state.friendship_active and action in ("trade", "non_aggression")
    panel(surface, (x, y, 464, 132))
    text(surface, rules.TREATIES[action], (x+18, y+11), 19, INK)
    text(surface, "INCLUDED" if included else "ACTIVE" if active else "OFFER", (x+445, y+17), 9,
         CYAN if active else FAINT, "mono", right=True)
    if action == "trade":
        effect = f"Your empire: +{rules.trade_income(game, 'player', owner)} CR/turn · +1 relations/turn"
        detail = "Both economies, reduced by distance between capitals."
    elif action == "research":
        gain = rules.RESEARCH_INCOME+RACES[game.race_id].research_bonus+game.bonuses_for().get("pact_research", 0)
        effect = f"Your empire: +{gain} RP/turn · +1 relations/turn"
        detail = "Both empires gain research while the agreement holds."
    elif action == "non_aggression":
        effect = "Blocks attacks, raids and bombardment."
        detail = "+1 relations/turn. Declare war before attacking."
    else:
        effect = "Trade + non-aggression + shared scanners."
        detail = "Live fleet contacts; the included pacts give +2 relations/turn."
    text(surface, effect, (x+18, y+41), 13, CYAN if active else GOLD)
    text(surface, detail, (x+18, y+65), 11, MUTED)
    command = f"end_{action}" if active else action
    reason = game.diplomacy_error(command, owner)
    caption = ("Part of your friendship declaration" if included else
               f"Active · End: -{personality(game, owner).breach} relations" if active else
               f"Accepted at {threshold:+} · Current {state.relations:+}")
    text(surface, caption, (x+18, y+88), 11, MUTED)
    hint = reason or ("" if active else "Will accept" if state.relations >= threshold else "Will decline")
    text(surface, shorten(hint, 278, 10), (x+18, y+111), 10, FAINT)
    app.button(f"diplomacy_{command}", "Included" if included else "End pact" if active else "Propose",
               (x+315, y+90, 132, 29), lambda a=command: app.diplomatic_action(a), enabled=reason is None)


def draw_diplomacy(app):
    surface, game = app.canvas, app.game
    owner = app.selected_rival_id()
    selected = game.opponents.get(owner)
    app.chrome("DIPLOMATIC CHANNEL")
    app.button("diplomacy_back", "← Back · D", (64, 124, 205, 46), app.close_diplomacy, "ghost")
    app.button("diplomacy_galaxy", "Galaxy map", (284, 124, 172, 46), lambda: app.go("galaxy"), "ghost")
    app.button("diplomacy_intelligence", "Rival report", (472, 124, 184, 46), app.open_rival)
    app.button("diplomacy_statistics", "Statistics", (672, 124, 130, 46), app.open_statistics)
    app.button("diplomacy_alignment_matrix", "Race alignment matrix", (818, 124, 558, 46), app.show_alignment)
    draw_relations_strip(app)
    if selected is None:
        draw_contact_profile(surface, RACES[game.race_id], game.empire_name)
        panel(surface, (427, 330, 949, 450))
        text(surface, "No foreign contact yet.", (456, 370), 30, INK, "title")
        paragraph(surface, ("Explore with your ships or detect a foreign fleet to establish a communications channel. "
                  "Civilizations will introduce themselves when contact is confirmed." if game.opponents else
                  "This campaign has no rival empire. Add one from Rival report to open a diplomatic channel."),
                  (458, 430), 836, 18, MUTED, 31)
        app.button("diplomacy_add_rival", "Open Rival report", (457, 620, 318, 51), app.open_rival, "primary")
    else:
        state, race = game.diplomacy_between("player", owner), RACES[selected.race_id]
        draw_contact_profile(surface, race, selected.name)
        app.button("diplomacy_greeting", "Replay first-contact greeting", (87, 647, 292, 31), app.replay_greeting, "ghost")
        reason = game.diplomacy_error("declare_war", owner)
        app.button("diplomacy_declare_war", "At war" if state.at_war else "Declare war", (87, 699, 292, 39),
                   lambda: app.diplomatic_action("declare_war"), enabled=reason is None)
        text(surface, "War ends all pacts and sets relations to -100.", (87, 751), 11, RED)
        panel(surface, (427, 330, 949, 78))
        color = relation_color(state.relations)
        app.button("diplomacy_alignment", "Values & history", (1144, 337, 208, 24), lambda: app.show_alignment(owner), "ghost")
        breakdown = alignment.relationship(game, "player", owner)
        text(surface, "RELATIONS", (449, 341), 9, MUTED, "mono", 1)
        text(surface, f"{'At war' if state.at_war else state.attitude}  {state.relations:+}", (449, 358), 22, color)
        text(surface, f"Values {breakdown.alignment:+} · History {breakdown.history:+}", (449, 388), 11, MUTED)
        pg.draw.line(surface, LINE, (754, 373), (1348, 373), 5)
        pg.draw.line(surface, MUTED, (1051, 368), (1051, 378), 1)
        pg.draw.circle(surface, color, (round(754+(state.relations+100)/200*594), 373), 6)
        text(surface, "HOSTILE  -100", (754, 390), 9, FAINT, "mono")
        text(surface, "WARM  +100", (1348, 390), 9, FAINT, "mono", right=True)
        for action, x, y in (("trade", 427, 424), ("research", 912, 424),
                             ("non_aggression", 427, 569), ("friendship", 912, 569)):
            draw_treaty(app, owner, state, action, x, y)
        panel(surface, (427, 714, 949, 66))
        text(surface, "RECENT EXCHANGES", (445, 723), 9, GOLD, "mono", 1)
        for index, event in enumerate(reversed(state.events[-2:])):
            y = 740+index*19
            text(surface, f"T{event.turn:03}", (445, y), 10, FAINT, "mono")
            text(surface, shorten(event.message, 849, 11), (506, y), 11, INK)
    text(surface, f"Offers: {rules.OFFER_COOLDOWN}-turn cooldown. Kept pacts build trust. Friendship shares direct scanner contacts.", (65, 798), 13, MUTED)
    app.button("diplomacy_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("diplomacy_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, "D: diplomacy · I: empire · E: advance one turn", (400, 848), 12, MUTED)
    app.button("diplomacy_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn, "primary")
