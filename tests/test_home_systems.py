"""Home identities through generation, exploration, repeated races and loading."""

from dataclasses import asdict
import unittest
from unittest.mock import patch

from orion import tomb_worlds
from orion.exploration import record_survey
from orion.model import GameState, new_game
from orion.races import RACES


class HomeSystemTests(unittest.TestCase):
    def test_player_and_ai_homes_use_their_civilization_names(self):
        for race in RACES.values():
            for random_starts in (False, True):
                with self.subTest(race=race.id, random_starts=random_starts):
                    game = new_game(seed=2408, race_id=race.id, rival_count=5,
                                    random_starts=random_starts)
                    self.assertEqual(game.systems[0].name, race.home_system)
                    self.assertEqual([p.name for p in game.systems[0].worlds],
                                     [*race.home_neighbors[:2], race.homeworld, race.home_neighbors[2]])
                    for owner, empire in game.opponents.items():
                        system = game.systems[empire.home_system]
                        home = game.planet_at(system.id, empire.home_planet)
                        names = RACES[empire.race_id]
                        self.assertEqual((system.name, home.name), (names.home_system, names.homeworld))
                        self.assertIn(home.name, empire.events[0].message)
                        self.assertEqual(game.known_system(system.id, owner).worlds[home.id].name, home.name)
                    self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_naming_preserves_generated_properties_positions_guardians_and_tombs(self):
        for size in ("Compact", "Expansive"):
            with patch("orion.model.name_home"):
                before = new_game(seed=101, galaxy_size=size, race_id="varkesh", rival_count=5)
            after = new_game(seed=101, galaxy_size=size, race_id="varkesh", rival_count=5)
            for old, new in zip(before.systems, after.systems):
                a, b = asdict(old), asdict(new)
                a.pop("name"); b.pop("name")
                for planets in (a["worlds"], b["worlds"]):
                    for planet in planets:
                        planet.pop("name")
                self.assertEqual(a, b)
            self.assertEqual((before.ships, before.guardians, before.tomb_worlds),
                             (after.ships, after.guardians, after.tomb_worlds))

    def test_duplicate_races_get_unique_home_system_and_planet_names(self):
        for race in ("terran", "varkesh", "remnant"):
            for random_starts in (False, True):
                game = new_game(seed=2408, race_id=race, rival_race_id=race,
                                random_starts=random_starts, rival_count=1)
                system, planet = game.headquarters("rival")
                self.assertEqual((system.name, planet.name),
                                 (RACES[race].home_system+" 2", RACES[race].homeworld+" 2"))
                systems = [s.name for s in game.systems]
                planets = [p.name for s in game.systems for p in s.worlds]
                self.assertEqual(len(systems), len(set(systems)))
                self.assertEqual(len(planets), len(set(planets)))
                self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_adding_a_rival_updates_survey_names_without_revealing_colony_changes(self):
        game = new_game(seed=2408, rival_count=0, random_starts=False, with_guardians=False, with_tombs=False)
        system, home = game.opponent_home()
        record_survey(game, system.id, "player")
        before = game.exploration.survey(system.id).worlds[home.id].copy()
        game.add_opponent("nexus")
        surveyed = game.known_system(system.id).worlds[home.id]
        self.assertEqual((system.name, home.name, home.owner), ("Axiom", "Origin", "rival"))
        self.assertEqual(surveyed.name, "Origin")
        self.assertEqual((surveyed.owner, surveyed.population), (before["owner"], before["population"]))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_remnant_emerging_from_a_tomb_keeps_the_charted_world_name(self):
        game = new_game(seed=2408, race_id="varkesh", rival_count=0, with_tombs=False)
        before = [(s.name, [p.name for p in s.worlds]) for s in game.systems]
        tomb = tomb_worlds.TombWorld(0, 3)
        game.tomb_worlds.append(tomb)
        tomb_worlds.awaken(game, tomb)
        self.assertEqual(before, [(s.name, [p.name for p in s.worlds]) for s in game.systems])
        self.assertEqual(game.planet_at(0, 3).name, "Kreth")
        self.assertEqual(game, GameState.from_dict(game.to_dict()))


if __name__ == "__main__":
    unittest.main()
