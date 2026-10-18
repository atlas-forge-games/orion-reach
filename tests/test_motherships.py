"""Mobile settlements: travel, economy, survival, migration and actual UI controls."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from orion.model import new_game, GameState, SaveError, RuleError, Ship
from orion import motherships, population, council, combat, exploration, sensors, tribute
from orion.empire import summarize_empire
from orion.production import distance_ly
from orion.storage import Storage


def campaign(**kwargs):
    args=dict(seed=12, race_id='wanderers', random_starts=False, with_ai=False,
              with_guardians=False,with_tombs=False,with_black_holes=False)
    args.update(kwargs)
    return new_game(**args)


def target(game, distance=6):
    origin, dest=game.systems[0],game.systems[1]
    dest.x, dest.y=origin.x+distance/140,origin.y
    return dest


def advance(game):
    with patch('orion.ai.run_ai',return_value=[]):
        return game.advance_turn()


class HabitatRulesTests(unittest.TestCase):
    def test_player_and_ai_start_on_mobile_homes_and_real_planets_are_empty(self):
        game=campaign(with_ai=True,rival_race_id='wanderers')
        for owner in game.owners:
            home=motherships.homes(game,owner)[0]
            self.assertEqual((home.habitat.population,game.population_report(home.habitat).capacity),(8,50))
            self.assertFalse(any(p.owner==owner for s in game.systems for p in s.worlds))
            self.assertEqual(sorted(s.kind for s in game.ships_owned_by(owner)),['mothership','scout','scout'])
            self.assertEqual(game.headquarters(owner)[1],home.habitat)
        self.assertEqual(GameState.from_dict(game.to_dict()),game)

    def test_population_limit_is_fifty_even_with_capacity_bonuses(self):
        game=campaign();home=game.headquarters()[1]
        home.population,home.farmers,home.miners=49,30,0
        home.growth_progress=99
        report=population.report(home,{'capacity_percent':200})
        population.advance(home,report)
        self.assertEqual(home.population,50)
        for _ in range(10):
            population.advance(home,population.report(home,{'capacity_percent':200}))
        self.assertEqual(home.population,50)

    def test_only_wanderers_can_build_homes_and_they_cannot_settle_planets(self):
        game=campaign();home=game.headquarters()[1]
        self.assertIsNone(game.ship_build_error(0,home.id,'mothership'))
        self.assertIsNotNone(game.ship_build_error(0,home.id,'colony_ship'))
        self.assertIsNotNone(game.colonize_error(0,2))
        self.assertFalse(game.can_settle(game.planet_at(0,2)))
        other=campaign(race_id='terran')
        self.assertIn('Wanderers',other.ship_build_error(0,2,'mothership'))
        self.assertIsNotNone(game.build_error(0,home.id,'missile_base'))

    def test_purchased_home_has_its_own_population_and_workforce(self):
        game=campaign();home=game.headquarters()[1]
        game.resources=game.credits=10000
        game.queue_ship(0,home.id,'mothership');game.buy_construction(0,home.id)
        homes=motherships.homes(game)
        self.assertEqual(len(homes),2)
        self.assertNotEqual(homes[0].habitat.id,homes[1].habitat.id)
        self.assertEqual(homes[1].habitat.population,game.starting_colonists())
        self.assertEqual(summarize_empire(game).population,8+game.starting_colonists())
        self.assertEqual(GameState.from_dict(game.to_dict()),game)

    def test_home_and_selected_escorts_travel_at_quarter_speed_and_arrive_together(self):
        game=campaign();dest=target(game)
        ordinary=game.travel_turns(game.systems[0],dest)
        ids=[s.id for s in game.ships]
        duration=game.send_ships(ids,dest.id)
        self.assertEqual(duration,ordinary*4)
        self.assertEqual({s.travel_total for s in game.ships},{duration})
        game.cancel_departures(ids)
        self.assertTrue(all(not s.has_course for s in game.ships))
        game.send_ships(ids,dest.id)
        for _ in range(duration):advance(game)
        self.assertEqual({s.system_id for s in game.ships},{dest.id})
        self.assertTrue(all(not s.has_course for s in game.ships))
        self.assertEqual(GameState.from_dict(game.to_dict()),game)

    def test_supply_sensors_and_visibility_follow_the_mobile_home(self):
        game=campaign();ship=motherships.homes(game)[0];dest=target(game)
        game.ships[:]=[ship]
        game.send_ship(ship.id,dest.id)
        advance(game);advance(game)
        center=motherships.center(game,ship)
        self.assertAlmostEqual(game.supply_distance(dest.id),distance_ly(center,dest))
        self.assertLess(game.supply_distance(dest.id),distance_ly(game.systems[0],dest))
        self.assertFalse(game.system_visible(0))
        self.assertTrue(game.system_explored(0))
        self.assertTrue(game.colony_systems())
        with patch.object(game,'bonuses_for',return_value={'sensor_range':10}):
            coverage=sensors.local_centers(game)
        self.assertAlmostEqual(coverage[0][0].x,center.x)

    def test_inflight_economy_and_jobs_work_but_ship_launch_waits_for_arrival(self):
        game=campaign();ship=motherships.homes(game)[0];home=ship.habitat
        game.resources=10000
        game.set_workforce(0,home.id,2,2,1)
        game.queue_ship(0,home.id,'scout')
        game.ships[:]=[ship]
        dest=target(game)
        game.send_ship(ship.id,dest.id)
        income,research=game.empire_rates
        before=game.credits
        advance(game)
        self.assertEqual(game.credits,before+income)
        self.assertEqual(game.research,research)
        self.assertEqual(home.construction_queue[0].progress,0)
        self.assertIn('arrives',game.buy_construction_error(0,home.id))
        self.assertIn('arrives',game.ship_build_error(0,home.id,'scout'))
        game.set_workforce(0,home.id,2,1,2)
        for _ in range(ship.turns_remaining):advance(game)
        self.assertGreater(home.construction_queue[0].progress,0)
        game.credits=10000;game.buy_construction(dest.id,home.id)
        self.assertEqual(game.ships[-1].system_id,dest.id)

    def test_buildings_can_finish_during_flight(self):
        game=campaign();ship=motherships.homes(game)[0];home=ship.habitat
        game.resources=10000;game.queue_building(0,home.id,'factory')
        home.construction_queue[0].progress=home.construction_queue[0].spec.work_cost-1
        game.send_ship(ship.id,target(game).id);advance(game)
        self.assertTrue(ship.in_transit);self.assertIn('factory',home.buildings)

    def test_pending_and_inflight_saves_keep_selected_home_and_all_economy(self):
        game=campaign();ship=motherships.homes(game)[0];home=ship.habitat
        game.selected_planet=home.id
        game.send_ship(ship.id,target(game).id)
        with tempfile.TemporaryDirectory() as folder:
            storage=Storage(folder)
            self.assertEqual(storage.load(storage.save(game))[0],game)
            advance(game)
            self.assertEqual(storage.load(storage.save(game))[0],game)
        self.assertEqual(council.world_votes(game),{'player':1})

    def test_losing_one_home_keeps_empire_alive_but_last_home_loss_eliminates_it(self):
        game=campaign(with_ai=True,rival_race_id='terran')
        first=motherships.homes(game,'player')[0]
        second=motherships.create(game,0,'player')
        game.ships.remove(first);game.eliminate_defeated()
        self.assertIsNone(game.check_victory(convene=False))
        game.ships.remove(second);game.eliminate_defeated()
        self.assertEqual(game.check_victory(convene=False).winner,'rival')

    def test_legacy_colonies_move_people_buildings_work_and_selection_to_habitats(self):
        game=campaign(race_id='terran')
        home=game.planet_at(0,2);home.buildings=['factory','mine']
        game.queue_building(0,2,'research_lab')
        home.construction_queue[0].progress=5
        home.construction_queue[0].paid_resources=home.construction_queue[0].resource_cost
        game.selected_planet=2
        game.race_id='wanderers'
        old=game.to_dict();original=copy.deepcopy(old)
        loaded=GameState.from_dict(old,version=44)
        self.assertEqual(old,original)
        migrated=loaded.planet_at(0,loaded.selected_planet)
        self.assertTrue(migrated.habitat)
        self.assertEqual(migrated.buildings,home.buildings)
        self.assertEqual(migrated.construction_queue[0].progress,5)
        self.assertEqual(sum(p.population for _,p in loaded.settlements()),home.population+1)
        self.assertFalse(loaded.planet_at(0,2).colonized)
        self.assertEqual(GameState.from_dict(loaded.to_dict()),loaded)

    def test_malformed_habitats_are_rejected(self):
        game=campaign();raw=game.to_dict()
        index=next(i for i,s in enumerate(raw['ships']) if s['kind']=='mothership')
        for change in ({'population':51},{'population':0},{'owner':'rival'},{'id':-999},{'habitat':False}):
            broken=copy.deepcopy(raw);broken['ships'][index]['habitat'].update(change)
            with self.subTest(change=change),self.assertRaises(SaveError):GameState.from_dict(broken)
        broken=copy.deepcopy(raw);broken['ships'][index]['habitat']=None
        with self.assertRaises(SaveError):GameState.from_dict(broken)

    def test_ai_builds_and_relocates_additional_homes(self):
        from orion.ai import run_ai
        game=campaign(race_id='terran',with_ai=True,rival_race_id='wanderers')
        ship=motherships.homes(game,'rival')[0];home=ship.habitat
        home.population=30;home.buildings=['factory','research_lab','hydroponic_farm','barracks']
        game.opponent.resources=5000;game.opponent.credits=5000
        with patch('orion.ai.scouting_orders'),patch('orion.ai.military_orders'):
            run_ai(game,'rival')
        self.assertTrue(any(q.item_id=='mothership' for q in home.construction_queue))
        second=motherships.create(game,ship.system_id,'rival')
        dest=next(s for s in game.systems if s.id!=ship.system_id)
        origin=game.systems[ship.system_id];dest.x,dest.y=origin.x+.02,origin.y
        exploration.record_survey(game,dest.id,'rival')
        motherships.ai_orders(game,'rival')
        self.assertTrue(ship.has_course or second.has_course)

    def test_tribute_can_take_population_from_a_mobile_home_without_emptying_it(self):
        game=campaign(with_ai=True,rival_race_id='varkesh')
        home=game.headquarters()[1];home.population=2
        tribute.transfer(game,tribute.Demand('rival','player','population',1,game.turn))
        self.assertEqual(home.population,1)
        self.assertIsNone(tribute.donor_world(game,'player'))

    def test_space_combat_disables_habitat_and_finished_battle_can_be_saved(self):
        game=campaign(with_ai=True,rival_race_id='terran')
        home=motherships.homes(game,'player')[0]
        attacker=Ship(game.next_ship_id,'frigate',0,owner='rival')
        game.next_ship_id+=1;game.ships=[home,attacker]
        game.selected_planet=home.habitat.id
        game.start_combat(0,owner='rival',target='player')
        victim=game.combat.ship(home.id);victim.hull=victim.shields=0
        combat.check_losses(game)
        self.assertEqual(home.disabled_turns,3)
        self.assertEqual(home.hull,1)
        self.assertEqual(game.selected_planet,home.habitat.id)
        self.assertEqual(GameState.from_dict(game.to_dict()),game)
        game.finish_combat()
        self.assertIsNone(game.result)
        from orion import boarding
        boarding.assault(game,home.id,'destroy',owner='rival')
        self.assertEqual(game.result.winner,'rival')
        self.assertEqual(GameState.from_dict(game.to_dict()),game)

    def test_legacy_active_battle_is_preserved_until_home_conversion_is_safe(self):
        game=campaign(race_id='terran',with_ai=True,rival_race_id='kharuun')
        game.race_id='wanderers'
        enemy=Ship(game.next_ship_id,'frigate',0,owner='rival')
        game.next_ship_id+=1;game.ships.append(enemy)
        game.start_combat(0,owner='rival',target='player')
        loaded=GameState.from_dict(game.to_dict(),version=44)
        self.assertTrue(loaded.wanderer_migration_pending)
        self.assertEqual(loaded.combat,game.combat)
        loaded=GameState.from_dict(loaded.to_dict())
        # Complete a real tactical result, then apply the postponed migration.
        for ship in loaded.combat.ships:
            if ship.owner=='player':ship.hull=ship.shields=0
        combat.check_losses(loaded);loaded.finish_combat()
        self.assertFalse(loaded.wanderer_migration_pending)
        self.assertTrue(loaded.headquarters()[1].habitat)
        self.assertFalse(loaded.planet_at(0,2).colonized)
        self.assertEqual(GameState.from_dict(loaded.to_dict()),loaded)

    def test_ascension_gate_cannot_charge_while_home_is_in_transit(self):
        from orion.victory import advance_gates
        game=campaign();ship=motherships.homes(game)[0];home=ship.habitat
        game.victory_conditions=("science",)  # Historical charging helper only.
        home.ascension_gate=True
        home.buildings=['fusion_plant']
        game.send_ship(ship.id,target(game).id)
        ship.departure_pending=False
        advance_gates(game,[(0,home.id,'player')])
        self.assertEqual(home.gate_charge,0)
        ship.system_id=ship.destination;game._clear_course(ship)
        advance_gates(game,[(0,home.id,'player')])
        self.assertEqual(home.gate_charge,1)


class HabitatInterfaceTests(unittest.TestCase):
    def test_home_buttons_controls_and_inflight_screens_render(self):
        import pygame as pg
        from orion.app import App
        from orion.galaxy_fleet_view import fleet_markers
        from orion.app import MAP
        with tempfile.TemporaryDirectory() as folder:
            app=App(Path(folder),capture=True)
            try:
                app.game=game=campaign();ship=motherships.homes(game)[0]
                app.dialog=None;app.go('galaxy');app.open_map_fleet(ship.id);app.render()
                markers=[r for ships,r,_ in fleet_markers(app,MAP) if ship in ships]
                self.assertGreaterEqual(markers[0].height,40)
                button=next(b for b in app.buttons if b.key==f'mothership_open_{ship.id}')
                self.assertTrue(button.enabled)
                app.present()
                v=app.viewport;x,y=button.rect.center
                pos=(round(v.x+x*v.w/1440),round(v.y+y*v.h/900))
                for event in (pg.MOUSEBUTTONDOWN,pg.MOUSEBUTTONUP):
                    app.handle_event(pg.event.Event(event,button=1,pos=pos));app.render()
                app.dialog=None
                self.assertEqual(app.screen,'planet')
                self.assertEqual(game.selected_planet,ship.habitat.id)
                app.select_worker_role('workers');app.select_worker_role('scientists')
                self.assertEqual(ship.habitat.scientists,1)
                for kind in ('industry','mining','research','food'):
                    app.show_output_breakdown(kind);app.render();app.dialog=None
                game.ships[:]=[ship];game.send_ship(ship.id,target(game).id);advance(game)
                for screen in ('planet','colony','production','shipyard','empire','fleets'):
                    app.open_mothership(ship.id);app.go(screen);app.dialog=None;app.render()
                    self.assertEqual(app.screen,screen)
                self.assertEqual(GameState.from_dict(game.to_dict()),game)
            finally:
                app.audio.close();pg.quit()
