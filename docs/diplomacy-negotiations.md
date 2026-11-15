# Diplomacy update — v0.97.0

This update adds player-facing negotiations to the existing diplomacy system:
visible reasons for decisions, AI proposals, territorial promises and peace.
It preserves the racial priorities, coalition rules, +10 trade threshold,
100-turn tribute cooldown and permanent Lithar betrayal memory.

## Installation and controls

Close the game. Extract this update into the repository directory containing
`main.py`, merging `orion`, `tests`, `tools`, `docs` and `screenshots` and replacing
the included files. It can be applied to v0.96.3 or v0.96.4; the route-start fix
is included. Start the game normally with `python main.py`.

Press **D** and choose a civilization. **Proposals & promises** (or **Negotiate
peace** during war) opens its negotiations. **Diplomatic affairs** also contains
Negotiations, Coalitions, Tribute & fear, Decision reasons and Racial priorities.
Each ordinary treaty has a **Why?** button. Incoming proposals can be opened
directly through **Review proposal** in Diplomacy or Turn news.

## Incoming proposals

The AI considers player-facing offers every four turns, after at least three
turns of contact. It prioritizes an acceptable peace, a coalition against an
observed shared threat, a territorial dispute, then treaties according to its
racial preferences. An incoming territorial demand requires a player colony
ship visible at the disputed system; hidden ships and destinations are not read.

There is a 20-turn initiative cooldown per diplomatic pair, at most one new
proposal in a game turn, at most three pending offers to the player, and at most
one pending proposal per pair. Proposals expire five turns after creation.
They never automatically bind the player and do not block End Turn. Normal
three-turn treaty-offer cooldowns still apply. Tribute remains separate.

Accept and Refuse both use explicit confirmation. Acceptance rechecks legality,
payment affordability and the AI's willingness. Coalition acceptance clearly
states when it would enter an existing war. Cancellation, refusal and an expired
offer never silently create a treaty or declare a war.

## Territorial commitments

Eligible systems must be surveyed by both empires, unsettled in their known
surveys, within both empires' fuel range, colonizable by each, and within 30 LY
of the requester's colonies. One active promise per direction and pair is
allowed. Varkesh and Wanderers do not participate in planetary-colonization
promises; the Skirr reject negotiated agreements.

An accepted promise prevents **planetary colonization** by the promising empire
for 20 turns. It does not prohibit travel or outposts. AI planning excludes the
system while its promise is active. Players may still choose to colonize: the
ordinary colony confirmation names the promise and its cost before commitment.
The rule also applies through the direct game API, so it cannot be bypassed by
another interface.

- Honoured promise: +5 relations (capped at 100), recorded in reliability history.
- Broken promise: -15 relations, plus the existing remembered-breach penalty.
- Direct refusal of a territorial request: -3 relations, no remembered breach.
- Ignoring a proposal until it expires: no agreement or penalty.

Relations penalties are bounded at -30 outside war, so a disagreement cannot
silently start a war. Honour bonuses cannot silently end an existing war.
Territorial promises remain applicable during war and end on fulfilment,
colonization in breach, or elimination of either participant. The commitment
list shows the system and expiry. A **◇** marks systems with a player-involving
promise on the galaxy map, without revealing undiscovered names.

## Peace and enforcement

Peace retains all current territorial holdings. It can be proposed without
reparations or with a quoted one-time credit payment from proposer to recipient.
Payment is affordable, conserved and transferred only on acceptance.

Willingness depends on war duration, recent defeats/victories, observed military
danger, racial resolve and offered reparations. The decision screen displays the
same arithmetic used by the rules. Some aggressive races need military pressure
or reparations even after a long war. The Skirr do not negotiate peace.

Peace moves relations to at least -30 and establishes a 20-turn ceasefire.
Declarations, fleet combat, invasions, raids, bombardment, outpost attacks,
station attacks and mothership boarding use the existing shared aggression
guard, extended to enforce this protection in both directions. AI targeting and
war planning also respect it. Coalition entry cannot bypass a ceasefire. A
member must leave coalitions against its intended peace partner before making
separate peace.

Expiry is exclusive: an agreement made on turn 10 lasts while the turn is below
30. Expiring a ceasefire does **not** restart the war. Normal diplomatic rules
apply again. Existing unrelated wars continue.

## Saved games and implementation

Save format 65 adds typed proposals, territorial promises, honoured-promise
counts, initiative deadlines, ceasefires and war-start timestamps to each
bilateral diplomacy state. Format 64 migration gives these fields empty or
neutral defaults without changing colonies or ships. Existing earlier-format
migration remains in place. New fields and their cross-references are validated.

Rules live in `orion/negotiations.py`; the dialog is in
`orion/negotiation_view.py`. They integrate with the shared diplomacy state,
AI planning, colonization, turn advancement, news and saving. The update uses
the existing game dependency (`pygame-ce`); no additional dependency is needed.

## Verification

The dedicated negotiation suite covers real mouse actions and autosaves,
human acceptance, refusal, expiry, proposal throttling, fog-aware warnings,
colonization consequences, AI promise compliance, peace and credit conservation,
combat protection, corrupt-save rejection and deterministic save/resume across
deadlines. The existing coalition/tribute suite is also run. Full-suite results
are recorded separately in `docs/diplomacy-validation.txt`.

```bash
python -m unittest discover -s tests -p "test_negotiations.py" -v
python -m unittest discover -s tests -p "test_coalitions_tribute.py" -v
python tools/preview_negotiations.py
```

The preview script renders the actual game screens. No mock UI is used.

## Commit locally

After extracting the update, review the changes with `git status` and `git diff`.
From the repository root:

```bash
git add README.md orion/__init__.py orion/ai.py orion/app.py orion/coalitions.py orion/diplomacy.py orion/diplomacy_view.py orion/diplomatic_affairs_view.py orion/galaxy_labels.py orion/model.py orion/news_view.py orion/storage.py orion/negotiations.py orion/negotiation_view.py tests/test_negotiations.py tools/preview_negotiations.py docs/diplomacy-negotiations.md docs/diplomacy-validation.txt screenshots/diplomacy_negotiations.png screenshots/diplomacy_promises.png screenshots/diplomacy_peace.png screenshots/diplomacy_reasons.png
git add orion/galaxy_fleet_view.py tests/test_galaxy_fleet_icons.py tests/test_galaxy_route_preview.py tools/preview_route_departure.py docs/compact-faction-fleets.md docs/route-departure-position.md screenshots/route_departure_progress.png
git commit -m "Add diplomatic proposals, territorial promises and negotiated peace (v0.97.0)"
git push
```

The second `git add` also stages the included route-start fix if it has not
already been committed. No commit or push is performed by this update itself.
