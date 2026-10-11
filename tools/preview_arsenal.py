"""Reproduce the arsenal research, designer, combat, drones and effects previews."""

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg
from orion.app import App
from orion.combat_effects import CombatAnimation
from orion.designs import MODULES, ShipDesign
from orion.model import new_game, Ship
from orion.research import BRANCHES, TECHNOLOGIES, choices
from orion.ui import GOLD, INK, MUTED, panel, paragraph, text
from orion.weapons import BEAMS


def discover(game, identifiers, owner="player"):
    picks = {(TECHNOLOGIES[t].branch, TECHNOLOGIES[t].tier): t for t in identifiers}
    state = game.research_state(owner)
    for branch in BRANCHES:
        last = max((tier for b, tier in picks if b == branch), default=0)
        for tier in range(1, last+1):
            if tier in state.completed_tiers(branch):
                continue
            identifier = picks.get((branch, tier), choices(branch, tier)[0].id)
            game._empire(owner).research += TECHNOLOGIES[identifier].cost
            game.choose_research(identifier, owner=owner)


def campaign():
    game = new_game(seed=2408, random_starts=False, with_tombs=False, with_guardians=False, fog_of_war=False)
    game.credits = game.resources = 5000
    game.headquarters()[1].scientists = 2
    game.ships.clear(); game.next_ship_id = 1
    return game


def encounter(game, left, right):
    game.ships = [Ship(1, left.kind, 0, design=left), Ship(2, right.kind, 0, owner="rival", design=right)]
    game.next_ship_id = 3
    game.start_combat(0)
    game.combat.ship(1).x, game.combat.ship(1).y = 5, 4
    game.combat.ship(2).x, game.combat.ship(2).y = 9, 4


def main():
    output = ROOT/"screenshots"
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        def capture(name):
            app.notice = ""; app.render()
            pg.image.save(app.canvas, str(output/f"arsenal_{name}.png"))
        try:
            game = app.game = campaign()
            discover(game, ["quantum_optics", "plasma_beams"])
            game.research = 164; game.choose_research("graviton_beams")
            app.go("galaxy"); app.open_research(); app.show_research_technology("graviton_beams")
            capture("research")
            game.research = TECHNOLOGIES["graviton_beams"].cost-164; game.advance_research()
            discover(game, ["cruiser_hulls", "antimatter_torpedoes", "regenerative_shields",
                            "advanced_flak", "automated_damage_control"])
            design = game.save_design("Peregrine", "cruiser", ["graviton", "antimatter", "regenerative_shield", "damage_control"])
            app.open_designer(); app.load_design(design); app.filter_design_modules("weapon")
            capture("designer")
            discover(game, ["cruiser_hulls", "hardened_shields", "ion_drives"], "rival")
            defender = ShipDesign("design_1", "Citadel", "cruiser", ("laser", "hardened_shield", "hardened_shield", "hardened_shield", "armor", "engine"))
            encounter(game, design, defender)
            app.go("combat"); app.combat_ship_id = 1; app.combat_target_id = 2
            app.combat_action("fire")
            app.combat_animation.elapsed = .16
            capture("combat")

            game = app.game = campaign()
            discover(game, ["pulse_beams", "drone_carriers", "interceptor_drones", "bomber_drones"])
            carrier = game.save_design("Aegis", "carrier", ["interceptor_bay", "bomber_bay", "pulse"])
            discover(game, ["battleship_hulls"], "rival")
            enemy = ShipDesign("design_1", "Ironclad", "battleship", ("torpedo", "laser", "armor"))
            encounter(game, carrier, enemy)
            game.combat_launch_drones(1, role="interceptor")
            game.combat_end_turn(); game.combat_end_turn("rival")
            game.combat_launch_drones(1, role="bomber")
            app.combat_animation = None
            app.go("combat"); app.combat_ship_id = 1; app.combat_target_id = 2
            capture("drones")

            catalogue = pg.Surface((1600, 1050))
            catalogue.fill((7, 17, 24))
            text(catalogue, "THE EXPANDED ARSENAL", (52, 35), 33, INK, "title")
            text(catalogue, "Eleven new weapons · Distinct tactical effects · Original in-game animations", (54, 85), 16, MUTED)
            names = ("pulse", "plasma", "ion", "graviton", "particle", "heavy_beam", "phased", "disruptor", "fusion_torpedo", "mirv", "antimatter")
            for index, name in enumerate(names):
                x, y = 52+(index % 3)*506, 130+(index // 3)*216
                module, beam = MODULES[name], BEAMS[name]
                panel(catalogue, (x, y, 484, 198), (12, 28, 37))
                text(catalogue, beam.name, (x+18, y+17), 23, beam.color)
                text(catalogue, f"{module.space} {'SPACE' if module.space == 1 else 'SPACES'}", (x+465, y+25), 11, GOLD, "mono", right=True)
                effect = CombatAnimation("fire", 1, ((x+30, y+96), (x+375, y+96)), 2, name, module.damage, weapons=(name,), elapsed=.16)
                effect.draw(catalogue, lambda p: p)
                paragraph(catalogue, module.description, (x+19, y+142), 447, 13, MUTED, 21)
            text(catalogue, "Research unlocks equipment. Fit modules in the ship designer; existing ships retain their blueprints.", (54, 1018), 14, GOLD)
            pg.image.save(catalogue, str(output/"arsenal_weapons.png"))
        finally:
            app.audio.close(); pg.quit()
    print("Created five arsenal previews in", output)


if __name__ == "__main__":
    main()
