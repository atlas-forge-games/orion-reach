"""Diplomatic contact, race identity, treaty offers and the AI's response."""

import pygame as pg

from . import diplomacy as diplomacy_balance
from .race_art import draw_race_portrait
from .races import RACES
from .personalities import PERSONALITIES, envoy_gain, gift_gain, personality
from .rival_selector import draw_rival_selector
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text


def draw_contact_profile(surface, race, empire_name):
    panel(surface, (64, 289, 338, 388))
    draw_race_portrait(surface, race.id, (129, 305, 208, 208))
    text(surface, shorten(empire_name, 291, 23, "title"), (87, 532), 23, INK, "title")
    text(surface, race.focus, (89, 570), 12, race.color)
    paragraph(surface, PERSONALITIES[race.id].traits, (89, 597), 290, 13, MUTED, 18)


def draw_diplomacy(app):
    surface, game = app.canvas, app.game
    own_race = RACES[game.race_id]
    owner = app.selected_rival_id()
    selected = game.opponents.get(owner)
    app.chrome("DIPLOMATIC CHANNEL")
    app.button("diplomacy_back", "← Back · D", (64, 124, 205, 46), app.close_diplomacy, "ghost")
    app.button("diplomacy_galaxy", "Galaxy map", (284, 124, 172, 46), lambda: app.go("galaxy"), "ghost")
    app.button("diplomacy_intelligence", "Rival report", (472, 124, 209, 46), app.open_rival)
    draw_rival_selector(app)
    text(surface, "Diplomacy", (64, 190), 43, INK, "title")
    text(surface, "Learn their character. Establish terms. Shape your relationship.", (66, 252), 14, MUTED)

    # Your own identity remains visible while dealing with another empire.
    panel(surface, (64, 688, 338, 90))
    draw_race_portrait(surface, game.race_id, (77, 701, 64, 64))
    text(surface, "YOUR EMPIRE", (155, 698), 9, MUTED, "mono", 1)
    text(surface, shorten(game.empire_name, 229, 15), (154, 715), 15, INK)
    text(surface, own_race.name, (155, 738), 11, own_race.color)
    text(surface, own_race.trait, (155, 755), 10, MUTED)

    if selected is None:
        draw_contact_profile(surface, own_race, game.empire_name)
        panel(surface, (427, 289, 949, 489))
        text(surface, "No foreign contact yet.", (456, 331), 30, INK, "title")
        paragraph(surface, ("Explore with your ships or detect a foreign fleet to establish a communications channel. "
                  "Civilizations will introduce themselves when contact is confirmed." if game.opponents else
                  "This campaign has no rival empire. Add one from Rival report to open a diplomatic channel."),
                  (458, 394), 836, 18, MUTED, 31)
        app.button("diplomacy_add_rival", "Open Rival report", (457, 592, 318, 51), app.open_rival, "primary")
    else:
        rival, state = selected, game.diplomacy_between("player", owner)
        race = RACES[rival.race_id]
        draw_contact_profile(surface, race, rival.name)
        app.button("diplomacy_greeting", "Replay first-contact greeting", (87, 632, 292, 31), app.replay_greeting, "ghost")

        panel(surface, (427, 289, 949, 89))
        color = CYAN if state.relations >= 25 else RED if state.relations < 0 else GOLD
        text(surface, "RELATIONS", (449, 303), 9, MUTED, "mono", 1)
        text(surface, f"{state.attitude}  {state.relations:+}", (449, 328), 24, color)
        pg.draw.line(surface, LINE, (754, 329), (1348, 329), 5)
        pg.draw.line(surface, MUTED, (1051, 324), (1051, 334), 1)
        pg.draw.circle(surface, color, (round(754+(state.relations+100)/200*594), 329), 6)
        text(surface, "HOSTILE  -100", (754, 350), 9, FAINT, "mono")
        text(surface, "WARM  +100", (1348, 350), 9, FAINT, "mono", right=True)

        for action, title, x, unit, base, bonus in (
            ("trade", "Trade pact", 427, "CR", diplomacy_balance.TRADE_INCOME, "trade_bonus"),
            ("research", "Research agreement", 912, "RP", diplomacy_balance.RESEARCH_INCOME, "research_bonus"),
        ):
            panel(surface, (x, 397, 464, 155))
            active = getattr(state, f"{action}_active")
            threshold = getattr(race, f"{action}_threshold")
            text(surface, title, (x+22, 413), 21, INK)
            text(surface, "ACTIVE" if active else "AVAILABLE", (x+441, 422), 9, CYAN if active else FAINT, "mono", right=True)
            effect = "pact_income" if action == "trade" else "pact_research"
            own_yield = base+getattr(own_race, bonus)+game.bonuses_for().get(effect, 0)
            rival_yield = base+getattr(race, bonus)+game.bonuses_for(owner).get(effect, 0)
            returns = (f"Your empire: +{own_yield} {unit}/turn" if game.fog_of_war else
                       f"You: +{own_yield} {unit}/turn · Rival: +{rival_yield} {unit}/turn")
            text(surface, returns,
                 (x+23, 448), 13, race.color)
            caption = "+1 relations each End Turn while active" if active else f"Accepted at {threshold:+} relations · Current: {state.relations:+}"
            text(surface, caption, (x+23, 474), 12, MUTED)
            command = f"end_{action}" if active else action
            reason = game.diplomacy_error(command, owner)
            hint = f"End: -{personality(game,owner).breach} relations" if active else (reason or ("Will accept" if state.relations >= threshold else "Will decline"))
            text(surface, shorten(hint, 238, 11), (x+23, 520), 11, GOLD if active else MUTED)
            app.button(f"diplomacy_{command}", "End agreement" if active else "Propose", (x+275, 505, 168, 35),
                       lambda a=command: app.diplomatic_action(a), enabled=reason is None)

        for action, title, x, caption in (
            ("envoy", f"Send envoy · {diplomacy_balance.ENVOY_COST} CR", 427,
             f"+{envoy_gain(game,'player',owner)} relations · Every {diplomacy_balance.ENVOY_COOLDOWN} turns"),
            ("gift", f"Gift {diplomacy_balance.GIFT_COST} CR", 721,
             f"+{gift_gain(game,owner)} relations · Every {diplomacy_balance.GIFT_COOLDOWN} turns"),
        ):
            reason = game.diplomacy_error(action, owner)
            app.button(f"diplomacy_{action}", title, (x, 574, 278, 43),
                       lambda a=action: app.diplomatic_action(a), enabled=reason is None)
            text(surface, reason or caption, (x+1, 625), 11, GOLD if reason else MUTED)
        paragraph(surface, f"Offers: {diplomacy_balance.OFFER_COOLDOWN}-turn cooldown. Agreements end below 0 relations; rival fleets may attack below -30. Combat sets relations to -100.",
                  (1020, 574), 348, 12, MUTED, 20)

        panel(surface, (427, 651, 949, 127))
        text(surface, "RECENT EXCHANGES", (449, 670), 10, GOLD, "mono", 1)
        for i, event in enumerate(reversed(state.events[-3:])):
            y = 700+i*25
            text(surface, f"T{event.turn:03}", (450, y), 10, FAINT, "mono")
            text(surface, shorten(event.message, 834, 12), (516, y-1), 12, INK)

    text(surface, "Agreements benefit both empires. Attacking a rival breaks your treaties.", (65, 798), 13, MUTED)
    app.button("diplomacy_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("diplomacy_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, "D: diplomacy · I: empire · E: advance one turn", (400, 848), 12, MUTED)
    app.button("diplomacy_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn, "primary")
