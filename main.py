"""Launch the prototype. Run `python main.py --help` for capture options."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

GUARDIAN_PREVIEWS = {
    "guarded": ("space_serpent", "system"),
    "monster": ("space_serpent", "combat"),
    "crystal": ("crystal_guardian", "combat"),
    "sentinel": ("ancient_sentinel", "combat"),
    "leviathan": ("void_leviathan", "combat"),
    "ruins": ("ancient_sentinel", "system"),
    "leviathan_system": ("void_leviathan", "system"),
    "guardian_map": ("void_leviathan", "galaxy"),
    "gaia": ("space_serpent", "planet"),
}


def main():
    parser = argparse.ArgumentParser(description="Orion Reach — Python space strategy prototype")
    parser.add_argument("--data-dir", type=Path, help="override the user save/settings directory")
    parser.add_argument("--headless", action="store_true", help="use SDL's dummy video/audio drivers")
    parser.add_argument("--skip-intro", action="store_true", help="go straight to the menu without the studio splash")
    parser.add_argument("--screenshot", type=Path, help="render one screen to PNG, then exit")
    parser.add_argument("--screen", choices=("splash", "menu", "race_select", "setup", "load", "settings", "galaxy", "system", "unexplored", "exploration", "planet", "production", "colony", "empire", "shipyard", "fleets", "fleet", "fleet_course", "rival", "diplomacy", "research", "combat", "designer", "design_combat", *GUARDIAN_PREVIEWS, "objectives", "result", "about"), default="menu")
    args = parser.parse_args()
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    try:
        import pygame
    except ImportError:
        raise SystemExit("Install the dependency first: python -m pip install -r requirements.txt")
    from orion.app import App
    app = App(args.data_dir, capture=bool(args.screenshot), skip_intro=args.skip_intro)
    try:
        if args.screenshot:
            if args.screen in ("galaxy", "system", "unexplored", "exploration", "planet", "production", "colony", "empire", "shipyard", "fleets", "fleet", "fleet_course", "rival", "diplomacy", "research", "combat", "designer", "design_combat", *GUARDIAN_PREVIEWS, "objectives", "result"):
                from orion.model import new_game
                # Seed 5 naturally has a reachable neighbor for the course preview.
                preview_seed = 5 if args.screen in ("fleet", "fleet_course") else 2408
                app.game = new_game(seed=preview_seed, random_starts=False)
                if args.screen in ("planet", "production", "colony", "shipyard"):
                    app.game.selected_planet = 2
                if args.screen == "unexplored":
                    app.game.selected_system = 1
                if args.screen == "exploration":
                    from orion.model import Ship
                    from orion.exploration import DISCOVERIES, discovery_at, refresh
                    for kind in DISCOVERIES:
                        system = next(s for s in app.game.systems if discovery_at(app.game, s.id) == kind
                                      and s.id != app.game.opponent.home_system)
                        app.game.ships.append(Ship(app.game.next_ship_id, "scout", system.id))
                        app.game.next_ship_id += 1
                    refresh(app.game, recover=True)
                if args.screen == "combat":
                    from orion.model import RIVAL, Ship
                    # A local screenshot fixture, independent of a campaign's starting fleet.
                    app.game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0), Ship(3, "colony_ship", 0),
                                      Ship(4, "frigate", 0, owner=RIVAL), Ship(5, "frigate", 0, owner=RIVAL),
                                      Ship(6, "colony_ship", 0, owner=RIVAL)]
                    app.game.next_ship_id = 7
                    app.game.start_combat(0)
                    app.game.combat_move(1, 7, 4)
                    app.game.combat_fire(1, 4)
                    app.game.combat_move(2, 7, 5)
                if args.screen in ("designer", "design_combat"):
                    from orion.model import Ship, RIVAL
                    game = app.game
                    game.technology.completed = ["ion_drives", "radiation_shields", "research_networks"]
                    lancer = game.save_design("Lancer", "frigate", ["torpedo", "shield", "scanner"])
                    aegis = game.save_design("Aegis", "cruiser", ["laser", "laser", "torpedo", "armor", "shield", "point_defense", "engine"])
                    game.credits = 750
                    if args.screen == "design_combat":
                        game.ships = [Ship(1, "cruiser", 0, design=aegis), Ship(2, "frigate", 0, design=lancer),
                                      Ship(3, "frigate", 0, owner=RIVAL), Ship(4, "frigate", 0, owner=RIVAL)]
                        game.next_ship_id = 5
                        game.start_combat(0)
                        game.combat_move(1, 7, 4)
                        game.combat_move(2, 7, 5)
                if args.screen in GUARDIAN_PREVIEWS:
                    from orion.model import Ship
                    from orion.exploration import refresh
                    game = app.game
                    kind, screen = GUARDIAN_PREVIEWS[args.screen]
                    guardian = next(g for g in game.guardians if g.kind == kind)
                    game.selected_system = guardian.system_id
                    game.fog_of_war = False
                    if screen == "combat":
                        count = (guardian.spec.hull*5+79)//80
                        identifiers = list(range(game.next_ship_id, game.next_ship_id+count))
                        game.ships.extend(Ship(i, "frigate", guardian.system_id) for i in identifiers)
                        game.next_ship_id += count
                        game.start_combat(guardian.system_id)
                        game.combat_move(identifiers[0], 7, 4)
                        game.combat_fire(identifiers[0], guardian.combat_id)
                        game.combat_move(identifiers[1], 7, 5)
                    elif args.screen == "gaia":
                        # Preview an established colony after its guardian was defeated.
                        guardian.hull = 0
                        planet = game.planet_at(guardian.system_id, guardian.planet_id)
                        planet.colonized, planet.owner, planet.population = True, "player", 9
                        planet.scientists = 2
                        planet.buildings = ["factory", "mine", "research_lab", "hydroponic_farm"]
                        game.selected_planet = planet.id
                    refresh(game)
                if args.screen == "result":
                    from orion.research import BRANCHES, choices
                    # Preview a science result without altering a real campaign.
                    game = app.game
                    game.research = 1620
                    for branch in BRANCHES:
                        for tier in (1, 2):
                            game.choose_research(choices(branch, tier)[0].id)
                    game.choose_research("ascension_theory")
                    earth = game.planet_at(0, 2)
                    earth.ascension_gate, earth.gate_charge = True, 5
                    game.check_victory()
            preview_screen = {"fleet_course": "galaxy", "unexplored": "system", "design_combat": "combat",
                              **{name: screen for name, (_, screen) in GUARDIAN_PREVIEWS.items()}}
            app.go(preview_screen.get(args.screen, args.screen))
            if args.screen == "designer":
                app.design_campaign = app.game.campaign_id
                app.load_design(aegis)
            if args.screen in ("fleet", "fleet_course"):
                app.open_map_fleet(1)
                app.toggle_fleet_ship(2)
                if args.screen == "fleet_course":
                    game = app.game
                    target = min((s for s in game.systems[1:] if game.within_fuel_range(s.id)),
                                 key=lambda s: (game.travel_turns(game.systems[0], s), s.id))
                    game.send_ships(app.map_order_ids, target.id)
                    game.selected_system = target.id
                    app.focus = f"star_{target.id}"
                    app.keyboard_mode = True
            app.time = 1.0 if args.screen == "splash" else 3.0
            app.render()
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(app.canvas, args.screenshot)
            print(f"Screenshot: {args.screenshot}")
        else:
            app.run()
    finally:
        app.audio.close()
        pygame.quit()


if __name__ == "__main__":
    main()
