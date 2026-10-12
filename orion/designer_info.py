"""Read-only, hull-specific equipment help and blueprint research requirements."""

from .designs import DRONE_BAYS, HULLS, MODULE_SIZES, fitted_module, missing_research
from .research import TECHNOLOGIES
from .weapons import BEAMS, DRONE_ROLES
from .ui import CYAN, GOLD, INK, MUTED, PANEL, panel, shorten, text, wrapped_lines


def research_sections(kind, modules, state):
    missing = missing_research(kind, modules, state.completed, legacy_hulls=state.legacy_starships)
    if not missing:
        return [("RESEARCH", "All hull and equipment research requirements are met. Construction still requires a valid saved design and an owned colony.")]
    sections = [("PLANNING", "You can edit and save this blueprint now. Construction becomes available automatically once all required technologies are discovered.")]
    for identifier in missing:
        technology = TECHNOLOGIES[identifier]
        status = state.status(identifier)
        label = {"available": "Available to research", "active": "Research in progress",
                 "excluded": "Excluded by your research choice", "locked": "Earlier research needed"}[status]
        detail = state.choice_error(identifier) if status in ("locked", "excluded") else ""
        cost = state.project_cost if status == "active" else technology.cost
        sections.append((technology.name.upper(), f"{label}. {cost} RP."+(f" {detail}" if detail else "")))
    return sections


def module_sections(kind, identifier, state):
    """Derive help from active balance values, not the catalogue's brief labels."""
    hull, module = HULLS[kind], fitted_module(kind, identifier)
    slot = {"weapon": "offensive", "defense": "defensive", "support": "support"}[module.category]
    sections = [("FITTING", f"Uses 1 {slot} slot. Values shown for a {hull.name}. Adds {module.resource_cost} resources and "
                 f"{module.work_cost} production work before empire discounts. Each copy has the effects below.")]
    effects = []
    if module.damage:
        beam = BEAMS[module.weapon]
        effects.append(f"Fires {beam.shots} shot{'s' if beam.shots != 1 else ''} for {module.damage} total damage per volley "
                       f"before defenses and research bonuses. Each shot rolls to hit separately. Range: {module.range} cells before scanners.")
        effects.append(f"Base accuracy: {beam.accuracy}%. Actual hit chance also depends on range, target evasion and research bonuses.")
        if hull.tracking_penalty:
            size = MODULE_SIZES[hull.module_size]
            examples = ", ".join(f"{max(0, size-target)*hull.tracking_penalty} vs {name}" for target, name in
                                 ((1, "small hulls"), (2, "medium hulls"), (3, "heavy hulls / bases")))
            effects.append(f"Large mounts turn slowly: lose {hull.tracking_penalty} accuracy percentage points per smaller target size "
                           f"({examples}). Scouts and drones are one size below small hulls.")
        else:
            effects.append("Fast tracking: no accuracy penalty for firing at smaller targets. Range and evasion still matter.")
        if beam.projectile or beam.drone:
            effects.append("Point defense reduces damage from this weapon."+(f" Ignores {beam.interception_piercing}% of the target's interception." if beam.interception_piercing else ""))
        else:
            effects.append("Point defense cannot intercept this weapon.")
        if beam.shield_multiplier != 1:
            effects.append(f"Deals {beam.shield_multiplier} times normal damage to shields; the extra damage does not carry over to hull.")
        if beam.shield_bypass:
            effects.append(f"{beam.shield_bypass}% of damage bypasses shields and hits hull directly. Hardened shields reduce this penetration.")
        if beam.slows:
            effects.append("A hit slows a surviving mobile target by 1 movement cell until the end of its next turn, to a minimum of 1. Multiple hits do not stack.")
        if beam.reload:
            effects.append(f"After firing, this weapon type must wait {beam.reload} of your combat turns before it can fire again. Other ready weapons may still fire.")
        if module.weapon == "siege":
            effects.append("Deals triple damage to planetary bases and their shields.")
    if module.hull_bonus:
        effects.append(f"Adds {module.hull_bonus} maximum hull points. Multiple armor plates add together.")
    if module.shields:
        effects.append(f"Adds {module.shields} shield points, restored at the start of each battle. Shields absorb ordinary damage before hull; multiple generators add together.")
    if module.shield_regeneration:
        effects.append(f"Restores up to {module.shield_regeneration} missing shield points at the start of each of your combat turns. Regeneration from multiple modules adds together.")
    if module.shield_hardening:
        effects.append(f"Reduces shield-bypassing damage by {module.shield_hardening}% while shields remain. Only the strongest hardening effect applies; it does not stack.")
    if module.repair_rate:
        effects.append(f"Repairs up to {module.repair_rate} hull at the start of each of your combat turns, with {module.repair_capacity} repair points available per battle. "
                       "Repairs only damage taken in that battle. Multiple modules add repair speed and reserves.")
    if module.interception:
        effects.append(f"Reduces incoming torpedo and drone damage by {module.interception}%. Shipboard interception adds together up to the best fitted cap "
                       f"({module.interception_cap}% for this module). Escort interceptors can raise total protection to 90%. Beam damage is unaffected.")
    if module.range_bonus:
        effects.append(f"Adds {module.range_bonus} cells to every fitted weapon's range. Only one combat scanner per ship. Does not change strategic fuel range.")
    if module.movement_bonus:
        effects.append(f"Changes tactical movement by {module.movement_bonus:+} cells per turn. Bonuses and penalties add together, with a minimum movement of 1. Does not change travel speed between stars.")
    if identifier in DRONE_BAYS:
        role = DRONE_BAYS[identifier]
        name, weapon, movement = DRONE_ROLES[role]
        beam = BEAMS[weapon]
        effects.append("Carrier only; at most 2 drone bays in total. Each bay supports 2 active drones and 4 launches per battle. Launching uses the carrier's weapon action; drones then act independently.")
        effects.append(f"Launches {name.lower()}s: {beam.damage} damage, range {beam.range}, {movement} movement cells. "
                       "Drones are temporary and are lost when their carrier is destroyed. Larger bays do not increase drone counts or strength.")
        if role == "interceptor":
            effects.append(f"Deals {beam.versus_drones} times damage to drones. Each interceptor gives other friendly ships within 2 cells +20% interception, capped at +40% from escorts.")
        elif role == "bomber":
            effects.append(f"Deals {beam.versus_capitals} times damage to cruisers, carriers, battleships, Titans, planetary bases and guardians.")
    sections += [("EFFECTS" if index == 0 else "", effect) for index, effect in enumerate(effects or [module.description])]
    if not module.technology:
        sections.append(("EQUIPMENT RESEARCH", "Basic equipment: no technology required for this module."))
    elif module.technology in state.completed:
        sections.append(("EQUIPMENT RESEARCH", f"{TECHNOLOGIES[module.technology].name} is already discovered."))
    sections += research_sections(kind, (identifier,), state)
    return sections


def draw_designer_info(app):
    dialog, surface = app.dialog, app.canvas
    kind = dialog["kind"]
    if "module" in dialog:
        module = fitted_module(kind, dialog["module"])
        title, subtitle = module.name, f"{HULLS[kind].name} fitting · Per module · Current campaign balance"
        sections = module_sections(kind, dialog["module"], app.game.technology)
    else:
        title, subtitle = "Research requirements", "Blueprint planning · Required hull and equipment technologies"
        sections = research_sections(kind, dialog["modules"], app.game.technology)
    rows = []
    for heading, body in sections:
        if heading:
            rows.extend((line, GOLD) for line in wrapped_lines(heading, 840, 15))
        rows.extend((line, INK) for line in wrapped_lines(body, 840, 15))
        rows.append(("", MUTED))
    per_page = 21
    last = max(0, (len(rows)-1)//per_page)
    dialog["info_page"] = min(last, max(0, dialog["info_page"]))
    page = dialog["info_page"]
    panel(surface, (260, 80, 920, 740), PANEL, GOLD)
    text(surface, "SHIP EQUIPMENT", (294, 105), 11, GOLD, "mono", 1)
    text(surface, shorten(title, 840, 28, "title"), (292, 129), 28, INK, "title")
    text(surface, subtitle, (294, 173), 13, CYAN)
    for index, (line, color) in enumerate(rows[page*per_page:(page+1)*per_page]):
        text(surface, line, (294, 209+index*24), 15, color)
    app.button("dialog_info_prev", "←", (294, 749, 49, 40), lambda: app.change_designer_info_page(-1), enabled=page > 0)
    text(surface, f"{page+1} / {last+1}", (363, 762), 12, MUTED)
    app.button("dialog_info_next", "→", (420, 749, 49, 40), lambda: app.change_designer_info_page(1), enabled=page < last)
    text(surface, "Information only · Esc or right-click to close", (493, 763), 11, MUTED)
    app.button("dialog_close", "Close · Esc", (944, 747, 202, 44), app.cancel_dialog)
