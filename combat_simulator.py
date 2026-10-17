"""Run `python combat_simulator.py` to configure and play standalone battles."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Orion Reach standalone combat simulator")
    parser.add_argument("--balance", type=Path, default=Path(__file__).resolve().parent/"balance.json",
                        help="balance profile shared with the game and editor")
    parser.add_argument("--data-dir", type=Path, help="simulator settings/scenarios directory")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--scenario", type=Path, help="load a saved combat scenario JSON")
    source.add_argument("--preset", type=int, choices=range(1, 8), default=1, help="built-in scenario 1–7")
    parser.add_argument("--seed", type=int, help="override the scenario's deterministic shot seed")
    parser.add_argument("--auto", action="store_true", help="start immediately with AI controlling both fleets")
    parser.add_argument("--headless", action="store_true", help="use SDL dummy video/audio drivers")
    parser.add_argument("--screenshot", type=Path, help="render one screen and exit")
    parser.add_argument("--screen", choices=("setup", "combat", "designer", "result"), default="setup")
    args = parser.parse_args()
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    from orion import balance
    from orion.combat_sandbox import ROUND_LIMIT, ScenarioError, load_scenario, preset
    try:
        balance.configure(args.balance)
        scenario = load_scenario(args.scenario) if args.scenario else preset(args.preset-1)
        if args.seed is not None:
            scenario.seed = args.seed
        scenario.validate()
        try:
            import pygame as pg
        except ImportError:
            raise SystemExit("Install the dependency first: python -m pip install -r requirements.txt")
        from orion.combat_simulator import CombatSimulator
        app = CombatSimulator(args.data_dir, scenario=scenario, capture=bool(args.screenshot))
        try:
            if args.auto or args.screen in ("combat", "result"):
                if not app.launch(args.auto):
                    raise ScenarioError(app.notice)
            elif args.screen == "designer":
                app.open_designer(scenario.designs[0].id if scenario.designs else "cruiser")
            if args.screen == "result":
                for _ in range(100_000):
                    if app.game.combat.status != "active" or app.game.combat.round > ROUND_LIMIT:
                        break
                    app.game.combat_ai_action()
                if app.game.combat.status == "active":
                    raise ScenarioError("Preview reached the battle limit; use --screen combat to inspect it.")
                app.sync_combat_selection()
            if args.screenshot:
                app.render()
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                pg.image.save(app.canvas, args.screenshot)
            else:
                app.run()
        finally:
            app.audio.close()
            pg.quit()
    except (balance.BalanceError, ScenarioError, OSError) as exc:
        raise SystemExit(f"Combat simulator: {exc}") from exc


if __name__ == "__main__":
    main()
