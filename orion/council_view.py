"""Galactic Council census, public ballots and the accept-or-defy decision."""

from .council import settled_systems, solar_systems
from . import council as council_balance
from .race_art import draw_race_portrait
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text


def council_summary(game):
    if "council" not in game.victory_conditions:
        return "Galactic Council victory is disabled for this campaign."
    state = game.council
    if not state.formed_turn:
        return "Forms when half the solar systems have a colony."
    election = state.election
    if election is None:
        return "The first council is awaiting the end of combat."
    if state.pending:
        return "Your vote is required." if election.status == "voting" else "Accept or defy the elected emperor."
    if election.status == "defied":
        return "Emperor defied. Elections have ended."
    if election.status == "accepted":
        return "The council has elected an emperor."
    return f"Next election: turn {state.next_vote_turn}."


def draw_council(app):
    surface, game = app.canvas, app.game
    state, election = game.council, game.council.election
    app.chrome("GALACTIC COUNCIL")
    text(surface, "Emperor of the Universe", (64, 137), 38, INK, "title")
    text(surface, "One colonized world, one vote. Every surviving empire may stand for election.", (66, 190), 15, MUTED)
    text(surface, f"TURN {game.turn:03}", (1376, 152), 12, GOLD, "mono", right=True)
    panel(surface, (64, 225, 1312, 82))
    if election is None:
        text(surface, "The council has not convened yet." if "council" in game.victory_conditions else "Council disabled in galaxy setup.", (88, 243), 23, GOLD)
        text(surface, council_summary(game), (89, 279), 13, MUTED)
        paragraph(surface, f"The first election opens after at least half the galaxy's solar systems are settled. "
                  f"One colony is enough to count a system as settled. If nobody wins, the council votes again after {council_balance.ELECTION_INTERVAL} turns.",
                  (88, 357), 1170, 22, INK, 35)
        paragraph(surface, "A candidate must receive at least half of all eligible votes and hold a unique lead. "
                  "Abstentions still count toward the total; an exact 50–50 tie elects nobody. "
                  "You may refuse a foreign emperor, continuing the campaign at war with every surviving computer empire.",
                  (88, 496), 1170, 19, MUTED, 31)
        if "council" in game.victory_conditions and (not game.fog_of_war or game.is_observer):
            text(surface, f"{settled_systems(game)} / {solar_systems(game)} solar systems settled", (88, 695), 21, CYAN)
    else:
        title = (f"Your delegation controls {election.weights['player']} votes. Choose an empire below." if election.status == "voting" else
                 f"{game.empire_name_for(election.winner)} has been elected." if election.winner else
                 f"No emperor elected. Next council: turn {state.next_vote_turn}.")
        text(surface, shorten(title, 1260, 22), (88, 241), 22, GOLD)
        text(surface, f"Election turn {election.turn} · {election.total_votes} votes in total · {election.votes_needed} needed, with a unique lead",
             (89, 279), 13, MUTED)
        for label, x in (("CIVILIZATION", 88), ("WORLD VOTES", 508), ("DELEGATION SUPPORTS", 656), ("VOTES RECEIVED", 1044)):
            text(surface, label, (x, 325), 10, GOLD, "mono", 1)
        tally = election.tally
        for index, owner in enumerate(sorted(election.weights, key=lambda o: (-election.weights[o], o))):
            y = 348+index*56
            color = app.empire_color(owner)
            panel(surface, (64, y, 1312, 50), border=color if owner == election.winner else LINE)
            draw_race_portrait(surface, game._empire(owner).race_id, (76, y+5, 40, 40))
            text(surface, shorten(game.empire_name_for(owner), 350, 17), (129, y+6), 17, INK)
            text(surface, "YOUR EMPIRE" if owner == "player" else "COMPUTER EMPIRE", (131, y+30), 8, color, "mono", 1)
            text(surface, str(election.weights[owner]), (558, y+15), 19, color)
            candidate = election.ballots.get(owner)
            choice = ("Awaiting your vote" if owner not in election.ballots else
                      "Abstains" if candidate is None else game.empire_name_for(candidate))
            text(surface, shorten(choice, 362, 15), (656, y+17), 15, MUTED)
            text(surface, str(tally[owner]), (1096, y+15), 19, GOLD if owner == election.winner else INK)
            if election.status == "voting":
                app.button(f"council_vote_{owner}", "Vote", (1222, y+8, 132, 34),
                           lambda candidate=owner: app.cast_council_vote(candidate))
        if election.status == "decision":
            paragraph(surface, "Accept the ruling to end the campaign. Defy it to continue: every surviving computer empire will declare war on you, "
                      "all your treaties with them will end, and there will be no further elections.",
                      (66, 757), 1310, 14, RED, 23)
        elif election.status == "defied":
            text(surface, "You defied the emperor. Every surviving computer empire declared war. Conquest and Ascension remain possible.",
                 (66, 770), 14, RED)
        else:
            text(surface, "AI empires back themselves, or a larger friendly empire. A tie does not elect an emperor.",
                 (66, 770), 14, MUTED)
    app.button("council_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("council_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    if election and election.status == "voting":
        app.button("council_abstain", "Abstain", (1081, 834, 295, 45), lambda: app.cast_council_vote(None), "ghost")
    elif election and election.status == "decision":
        app.button("council_accept", "Accept the ruling", (760, 834, 295, 45), lambda: app.decide_council(True), "primary")
        app.button("council_defy", "Defy the emperor", (1081, 834, 295, 45), lambda: app.decide_council(False))
    else:
        app.button("council_back", "Return to galaxy", (1081, 834, 295, 45), lambda: app.go("galaxy"), "primary")
