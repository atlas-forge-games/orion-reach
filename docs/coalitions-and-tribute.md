# Coalitions, fear and tribute — v0.63

## Using the controls

Select an empire in Diplomacy, then open **Coalitions & tribute**. The three tabs
show coalition proposals, tribute/fear, and the public racial priorities. Only
mutually contacted, living third empires appear as coalition targets.

An incoming tribute demand appears in Turn news with **Answer tribute demand**.
Ending the turn also opens any unresolved demand. Closing the dialog postpones
the decision; it does not pay or refuse. Pending demands survive save/load.

## Coalition agreements

An agreement connects two empires against one named target. A pair can have one
such agreement at a time; an empire may have several partners. There is no
automatic expiry. Elimination of a member or target dissolves the agreement
without a breach. Leaving voluntarily applies the recipient's existing breach
penalty and records a broken promise. Leaving alone does not start a war and does
not end independent treaties. Existing wars continue.

Members cannot attack one another without explicitly declaring war and breaking
their agreement. They gain +1 relations per turn. Coalitions provide no income
or scanner sharing; the existing trade/research/friendship rules provide those.

A new war declared by the target calls the victim's connected coalition partners
against that target into defence. Defensive responses do not cascade through
unrelated alliances. If a member starts an offensive war, its partners stay out.
Fighting further battles in that same war does not convert it into a defensive
call. When a prospective member is already fighting the target, formation joins
the other member to that war and requires explicit confirmation.

A member cannot form a coalition against an empire protected by its friendship,
non-aggression or another coalition agreement. The reverse conflict is blocked
when proposing new protection treaties. Trade or research with a peaceful target
can continue, but trade at risk reduces coalition willingness. Entering war ends
all treaties with that target.

### Acceptance

Each partner needs a threat assessment of at least **10**. The receiving AI needs
at least **40** willingness; an AI proposer must also meet the same conditions.
Human proposers choose their own willingness. A proposal uses the normal
three-turn bilateral offer cooldown, including a declined proposal.

Threat assessment includes:

- Existing war: 40 points.
- Known nearby target colonies within 30 light-years of the observer's colonies:
  5 × racial frontier weight per system, capped at 30.
- Competing racial interests at nearby known worlds: 3 × goal weight per match,
  capped at 25. Examples include lush ecosystems, blue/white stars, industry,
  research facilities and profitable worlds. The Serevan Union also considers attacks on
  its known friends; Remnant considers reported awakenings and known archaeology sites.
- Remembered tribute demands: 10 per demand, capped at 25.
- Military fear divided by four, plus a known ascension project when that victory
  condition is enabled. The final threat assessment is capped at 100.

Willingness combines own threat (capped at 50), half the partner's threat (capped
at 25), one-third of relations, racial pragmatism, cooperation/loyalty (up to 10),
broken promises (up to -40), and trade at risk. The dialog lists each contribution.

Surveys can be stale. Territorial pressure describes known nearby holdings;
it is not a claim that the AI has secretly observed a recent settlement.

## Fear and tribute

Fear is directional and ranges from 0 to 100. Known military superiority is
discounted by distance to the threatened empire's colonies. Actual visible ships
use their combat strength and remaining hull. Scanner-only fleets use estimates
from the reported count/classes; identified civilian ships do not intimidate.
An unobserved navy contributes nothing. The proximity discount is weighted by
each observed force, so a nearby scout cannot make a distant navy coercive.

Nearby military forces add 15. A recent battle/ground defeat adds up to 15,
falling by one per turn. Known friends and coalition protection against the
specific demanding empire reduce fear; racial resolve also modifies the result.
If no opposing force is observed, fear remains zero. These are conservative
intelligence-based estimates, not access to an opponent's hidden fleet or fuel tech.

At fear **75**, an AI accepts a valid tribute demand; below that it refuses.
The displayed amount is a diplomatic quote, not a general treasury/intelligence
report. All races can demand money. Only Varkesh can demand population:

| Tribute | Payment |
| --- | --- |
| Money | Three turns of the recipient's gross colony credit output, capped by its available treasury and the sender's treasury capacity. Credits are transferred, not created. |
| Population | One citizen from the recipient's largest eligible colony. It must retain at least one citizen. The citizen becomes one slave on the Varkesh homeworld, subject to existing capacity and mortality rules. |

There is no choice of arbitrary demand sizes, recurring tribute or exchange of
resources/technology. Both tribute types share one **100-turn cooldown per
demanding empire, across every target**. Refusals consume it too. Invalid actions
and cancelling a confirmation do not consume it.

Each issued demand reduces relations by 15 and is remembered as coercion.
Outside an existing war, the penalty cannot push relations below -30, preventing
an implicit declaration of war. Payment does not guarantee protection or end an
existing war. Refusal does not automatically start one. AI recipients pay
immediately; human recipients always choose. If circumstances change and a human
can no longer pay, refusal remains available. Eliminated parties' pending demands
are withdrawn without resetting the demanding empire's cooldown.

## Racial priorities and promises

The eleven public profiles appear in the game and balance editor. Their frontier,
goal, pragmatism, loyalty, memory, resolve, trade, research and friendship weights
affect coalition evaluation, fear and AI treaty selection. This is layered on the
existing alignment matrix and strategic personalities; it does not replace their
military/economic behavior or grant new access, mediation or integration actions.

Breaking a treaty or declaring war on a protected partner records the offender.
Ending bundled friendship counts as one breach. Lithar never erase these records.
Other recipients with a positive forgiveness interval forgive one breach after
five times that interval; each further breach restarts the wait. Recipients whose
existing personality never forgives retain their records too.

Remembered breaches increase non-aggression, friendship and research acceptance
thresholds according to racial memory, capped at an additional 40. The universal
trade threshold remains +10. Long cooperation favors future coalitions, particularly
for Lithar; profitable trade favors Kharuun, and research cooperation favors Aelari/Nexus.

## Save and editor compatibility

Version 44 saves validate coalition targets, participants, commitment dates,
directional memories, global cooldowns and pending demands. Versions 1–43 migrate
with empty new fields, retaining existing relations, treaties and histories.
Current saves retain pending responses and cooldowns exactly.

Balance profile 10 adds **Diplomatic priorities**, **Global rules → coalitions**
and **Global rules → tribute**. Older profiles retain other custom settings. The
editor permits a longer tribute cooldown but enforces a minimum of 100 turns.
