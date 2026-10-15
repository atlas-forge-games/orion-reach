"""World-weighted galactic elections, saved ballots and a human right of defiance."""

from dataclasses import dataclass, field

ELECTION_INTERVAL = 50
MAX_EVENTS = 48


@dataclass
class Election:
    turn: int
    weights: dict[str, int]
    ballots: dict[str, str | None] = field(default_factory=dict)
    status: str = "voting"
    winner: str | None = None

    @property
    def total_votes(self):
        return sum(self.weights.values())

    @property
    def votes_needed(self):
        return (self.total_votes+1)//2

    @property
    def tally(self):
        result = dict.fromkeys(self.weights, 0)
        for voter, candidate in self.ballots.items():
            if candidate is not None:
                result[candidate] += self.weights[voter]
        return result


@dataclass(frozen=True)
class CouncilEvent:
    id: int
    turn: int
    message: str


@dataclass
class CouncilState:
    formed_turn: int = 0
    next_vote_turn: int = 0
    election: Election | None = None
    events: list[CouncilEvent] = field(default_factory=list)
    next_event_id: int = 1
    news_read: int = 0

    @property
    def pending(self):
        return self.election is not None and self.election.status in ("voting", "decision")

    def record(self, turn, message):
        self.events.append(CouncilEvent(self.next_event_id, turn, message))
        self.next_event_id += 1
        self.events[:] = self.events[-MAX_EVENTS:]


def world_votes(game):
    return {owner: count for owner in game.owners
            if (count := len(game.settlements(owner)))}


def settled_systems(game):
    return len({s.id for s, _ in game.settlements()})


def solar_systems(game):
    from .black_holes import KIND
    return sum(s.kind != KIND for s in game.systems)


def schedule(game):
    """Check the formation threshold at the end of a completed strategic turn."""
    if "council" not in game.victory_conditions:
        return
    state = game.council
    if (not state.formed_turn and game.result is None and len(world_votes(game)) >= 2
            and 2*settled_systems(game) >= solar_systems(game)):
        state.formed_turn = state.next_vote_turn = game.turn
        state.record(game.turn, "Half the galaxy's solar systems are settled. The Galactic Council has been formed.")


def ai_choice(game, owner, weights):
    """Back a larger friendly empire, otherwise retain the delegation's own votes."""
    friends = [candidate for candidate in weights if weights[candidate] > weights[owner]
               and game.diplomacy_between(owner, candidate).relations >= 25]
    return min(friends, key=lambda c: (-game.diplomacy_between(owner, c).relations, -weights[c], c)) if friends else owner


def elected(election):
    tally = election.tally
    leaders = [owner for owner, votes in tally.items() if votes == max(tally.values())]
    return leaders[0] if len(leaders) == 1 and tally[leaders[0]] >= election.votes_needed else None


def convene_due(game):
    """Wait for tactical battles to finish before freezing this election's census."""
    from .first_contact import establish
    state = game.council
    if ("council" not in game.victory_conditions or game.result is not None or game.combat is not None or state.pending
            or not state.next_vote_turn or game.turn < state.next_vote_turn):
        return
    weights = world_votes(game)
    if len(weights) < 2:
        return
    for i, first in enumerate(weights):
        for second in list(weights)[i+1:]:
            establish(game, first, second)
    election = state.election = Election(game.turn, weights)
    state.next_vote_turn = game.turn+ELECTION_INTERVAL
    election.ballots = {owner: ai_choice(game, owner, weights) for owner in weights if owner != "player"}
    state.record(game.turn, f"The Galactic Council convenes: {election.total_votes} votes from colonized worlds. "
                 f"At least {election.votes_needed} votes and a unique lead elect the Emperor of the Universe.")
    if game.is_observer:
        resolve(game)


def resolve(game):
    state, election = game.council, game.council.election
    election.winner = elected(election)
    if election.winner is None:
        election.status = "failed"
        state.record(game.turn, f"No emperor was elected. No candidate reached half the votes with a unique lead. "
                     f"The next election is on turn {state.next_vote_turn}.")
        return
    state.next_vote_turn = 0
    election.status = "accepted" if game.is_observer or election.winner == "player" else "decision"
    state.record(game.turn, f"{game.empire_name_for(election.winner)} elected Emperor of the Universe: "
                 f"{election.tally[election.winner]} of {election.total_votes} votes. "
                 + ("The human empire must accept or defy the ruling." if election.status == "decision" else "The council grants a diplomatic victory."))


def cast_vote(game, candidate):
    from .model import RuleError
    election = game.council.election
    if ("council" not in game.victory_conditions or game.is_observer or game.result is not None or game.combat is not None or election is None
            or election.status != "voting" or "player" not in election.weights):
        raise RuleError("No council election is waiting for your vote.")
    if candidate is not None and (not isinstance(candidate, str) or candidate not in election.weights):
        raise RuleError("Choose a surviving council member, or abstain.")
    election.ballots["player"] = candidate
    resolve(game)
    game.check_victory()


def accept_ruling(game, accept):
    from .model import RuleError
    from .first_contact import establish
    state, election = game.council, game.council.election
    if ("council" not in game.victory_conditions or type(accept) is not bool or game.is_observer or game.result is not None or game.combat is not None
            or election is None or election.status != "decision"):
        raise RuleError("No council ruling is waiting for your decision.")
    if accept:
        election.status = "accepted"
        state.record(game.turn, f"{game.empire_name} accepts the council ruling. "
                     f"{game.empire_name_for(election.winner)} wins a diplomatic victory.")
    else:
        election.status = "defied"
        for owner in game.opponents:
            if not game.colony_systems(owner):
                continue
            establish(game, "player", owner)
            relations = game.diplomacy_between("player", owner)
            relations.end_agreements()
            relations.relations = -100
            relations.offer_ready_turn = max(relations.offer_ready_turn, game.turn+3)
            message = "The council ruling was defied. All surviving computer empires declare war on your empire."
            relations.record(game.turn, message)
            game.rival_event(message, turn=game.turn, owner=owner)
        state.record(game.turn, f"{game.empire_name} defies the elected emperor. All surviving computer empires declare war; "
                     "all their treaties with the human empire end. Elections cease. The campaign continues.")
    game.check_victory()


def load(game, data, version):
    """Old campaigns start with an unformed council; validate current snapshots."""
    from .model import _integer, _name
    if version < 32:
        return
    row = data["council"]
    if not isinstance(row, dict) or set(row) != {"formed_turn", "next_vote_turn", "election", "events", "next_event_id", "news_read"}:
        raise ValueError("Invalid council state")
    formed, next_turn = row["formed_turn"], row["next_vote_turn"]
    if not _integer(formed, 0, game.turn) or not _integer(next_turn, 0, game.turn+ELECTION_INTERVAL):
        raise ValueError("Invalid election schedule")
    if formed and "council" not in game.victory_conditions:
        raise ValueError("A disabled council cannot have elections")
    state = CouncilState(formed, next_turn)
    if not _integer(row["next_event_id"], 1, 1_000_000_000) or not _integer(row["news_read"], 0, row["next_event_id"]-1):
        raise ValueError("Invalid council news cursor")
    state.next_event_id, state.news_read = row["next_event_id"], row["news_read"]
    if not isinstance(row["events"], list) or len(row["events"]) > MAX_EVENTS:
        raise ValueError("Invalid council journal")
    for event in row["events"]:
        if (not isinstance(event, dict) or set(event) != {"id", "turn", "message"}
                or not _integer(event["id"], 1, state.next_event_id-1)
                or not _integer(event["turn"], max(1, formed), game.turn) or not _name(event["message"], 400)):
            raise ValueError("Invalid council event")
        state.events.append(CouncilEvent(**event))
    if ([e.id for e in state.events] != list(range(max(1, state.next_event_id-MAX_EVENTS), state.next_event_id))
            or any(a.turn > b.turn for a, b in zip(state.events, state.events[1:]))):
        raise ValueError("Invalid council event sequence")
    if not formed:
        if row != {"formed_turn": 0, "next_vote_turn": 0, "election": None, "events": [], "next_event_id": 1, "news_read": 0}:
            raise ValueError("An unformed council cannot have votes or news")
    elif not state.events:
        raise ValueError("Missing council formation report")
    raw = row["election"]
    if raw is None:
        if formed and next_turn != formed:
            raise ValueError("Missing council election")
    else:
        if (not formed or not isinstance(raw, dict) or set(raw) != {"turn", "weights", "ballots", "status", "winner"}
                or not _integer(raw["turn"], formed, game.turn)):
            raise ValueError("Invalid council election")
        weights, ballots = raw["weights"], raw["ballots"]
        # Historical ballots may include habitats destroyed since the vote.
        capacity = sum(len(s.worlds) for s in game.systems)+min(10000, game.next_ship_id-1)
        if (not isinstance(weights, dict) or not 2 <= len(weights) <= len(game.owners)
                or any(owner not in game.owners or not _integer(count, 1, capacity) for owner, count in weights.items())
                or sum(weights.values()) > capacity or not isinstance(ballots, dict)
                or any(voter not in weights or (candidate is not None and (not isinstance(candidate, str) or candidate not in weights))
                       for voter, candidate in ballots.items())):
            raise ValueError("Invalid council ballots")
        election = state.election = Election(raw["turn"], weights.copy(), ballots.copy(), raw["status"], raw["winner"])
        if election.status not in ("voting", "decision", "failed", "accepted", "defied"):
            raise ValueError("Invalid council phase")
        if election.winner is not None and (not isinstance(election.winner, str) or election.winner not in weights):
            raise ValueError("Invalid elected emperor")
        if election.status == "voting":
            if (game.is_observer or "player" not in weights or set(ballots) != set(weights)-{"player"}
                    or election.winner is not None):
                raise ValueError("Invalid pending player ballot")
        elif set(ballots) != set(weights) or election.winner != elected(election):
            raise ValueError("Election outcome does not match ballots")
        if (election.status == "failed" and election.winner is not None
                or election.status in ("decision", "accepted", "defied") and election.winner is None):
            raise ValueError("Invalid election outcome")
        if election.status in ("decision", "defied") and (game.is_observer or "player" not in weights or election.winner == "player"):
            raise ValueError("Only the human empire may defy a foreign emperor")
        expected_next = election.turn+ELECTION_INTERVAL if election.status in ("voting", "failed") else 0
        if next_turn != expected_next:
            raise ValueError("Election interval must be 50 turns")
        if (state.pending or election.status == "accepted") and (election.turn != game.turn or weights != world_votes(game) or game.combat is not None):
            raise ValueError("The current election census does not match the galaxy")
    game.council = state
