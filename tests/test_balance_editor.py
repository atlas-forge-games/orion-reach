"""Profile validation, real balance effects, save isolation and editor input."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')

from orion import balance
from orion.balance_document import BalanceDocument
from orion.model import new_game, GameState, PLAYER, Ship, SaveError
from orion.storage import Storage


def game():
    return new_game(seed=2408,with_ai=False,with_guardians=False,with_tombs=False,random_starts=False)


class BalanceTestCase(unittest.TestCase):
    def setUp(self):
        self.previous=balance.active_profile()
        self.configured=balance._configured_path
        balance._configured_path=None
        balance.activate(balance.default_profile())
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda:setattr(balance,'_configured_path',self.configured))
        self.addCleanup(lambda:balance.activate(self.previous))


class BalanceTests(BalanceTestCase):
    def test_standard_research_prices_are_quadrupled_but_saved_profiles_keep_their_prices(self):
        from orion.research import TECHNOLOGIES
        old_costs = (40, 100, 120, 220, 360, 540, 760, 1040)
        for tech in TECHNOLOGIES.values():
            self.assertEqual(tech.cost, 20000 if tech.id == 'ascension_theory' else 4*old_costs[tech.tier-1])
        old = balance.default_profile()
        for entry in old['data']['research_costs'].values():
            entry['cost'] //= 4
        balance.activate(old)
        g = game()
        g.research = 39
        g.choose_research('civil_engineering')
        path = Storage(self.root).save(g)
        balance.activate(balance.default_profile())
        restored, _ = Storage(self.root).load(path)
        self.assertEqual((restored.technology.progress, restored.technology.project_cost), (39, 40))
        restored.research = 1
        restored.advance_research()
        self.assertIn('civil_engineering', restored.technology.completed)
        doc = BalanceDocument(self.root/'new-profile.json')
        self.assertEqual(doc.entry('research_costs', '1')['cost'], 160)
        self.assertNotIn(('unique',), [path for path, _ in doc.fields('buildings', 'factory')])

    def test_defaults_and_catalogue_changes_reach_construction_races_and_modules(self):
        from orion.buildings import BUILDINGS
        from orion.production import PROJECTS, HULL_TECHNOLOGIES
        from orion.races import SETUP_RACES
        from orion.designs import ShipDesign
        before=balance.default_profile()
        profile=copy.deepcopy(before)
        profile['data']['buildings']['factory']['industry']=19
        profile['data']['buildings']['factory']['resource_cost']=37
        profile['data']['races']['terran']['name']='Test Terrans'
        profile['data']['ships']['cruiser']['technology']='ion_drives'
        profile['data']['modules']['armor']['hull_bonus']=21
        profile['data']['modules']['scanner']['range_bonus']=4
        profile['data']['rules']['economy']['STARTING_CREDITS']=777
        profile['data']['rules']['economy']['STARTING_RESOURCES']=321
        self.assertFalse(balance.validate(profile))
        balance.activate(profile)
        g=game()
        self.assertEqual((g.credits,g.resources),(777,321))
        self.assertIs(PROJECTS['factory'],BUILDINGS['factory'])
        self.assertEqual(g.project_price('factory'),37)
        self.assertEqual(SETUP_RACES['terran'].name,'Test Terrans')
        self.assertEqual(HULL_TECHNOLOGIES['cruiser'],'ion_drives')
        ship=ShipDesign('design_1','Test','frigate',('laser','armor','scanner'))
        self.assertEqual((ship.hull,ship.weapon_range),(41,10))
        from orion.combat import CombatShip
        tactical=CombatShip(1,'frigate','player',ship.hull,ship.hull,design=ship)
        self.assertEqual(tactical.ready_range,10)
        self.assertEqual(balance.default_profile(),before)

    def test_global_rules_apply_after_modules_have_been_imported(self):
        from orion import production, navigation, research, economy, victory, council_view
        profile=balance.default_profile()
        profile['data']['rules']['production'].update(SHIP_SPEED=.037,BASE_FUEL_RANGE=31,TRADE_GOODS_PERCENT=47,TROOP_STRENGTH=13,GATE_CHARGE_TURNS=9)
        profile['data']['rules']['council']['ELECTION_INTERVAL']=22
        balance.activate(profile)
        g=game()
        earth=g.planet_at(0,2)
        base=g.planet_yields(earth)[1]
        g.set_trade_goods(0,2)
        industry=g.planet_yields(earth)[0]
        self.assertEqual(g.planet_yields(earth)[1]-base,industry*47//100)
        self.assertEqual(g.fuel_range(),31)
        self.assertTrue(all(s.cruise_speed==.037 for s in g.ships))
        self.assertEqual(production.travel_turns(g.systems[0],g.systems[1]),navigation.duration(g.systems[0],g.systems[1]))
        self.assertEqual(victory.production_balance.TROOP_STRENGTH,13)
        self.assertEqual(council_view.council_balance.ELECTION_INTERVAL,22)

    def test_research_swaps_branch_order_custom_costs_and_reachable_finale(self):
        doc=BalanceDocument(self.root/'profile.json')
        doc.move_technology('ion_drives','construction',1,0)
        doc.reorder_branch('power',-1)
        doc.set('technologies','ion_drives',('cost_override',),17)
        doc.set('research_costs','2',('cost',),123)
        self.assertFalse(balance.validate(doc.profile))
        balance.activate(doc.profile)
        from orion.research import BRANCHES,TECHNOLOGIES,ResearchState,choices,branch_tiers
        self.assertEqual(next(iter(BRANCHES)),'power')
        self.assertEqual(choices('construction',1)[0].id,'ion_drives')
        self.assertEqual(TECHNOLOGIES['ion_drives'].cost,17)
        self.assertEqual(choices('power',2)[0].cost,123)
        state=ResearchState()
        for branch in BRANCHES:
            for tier in branch_tiers(branch):
                chosen=choices(branch,tier)[0]
                self.assertIsNone(state.choice_error(chosen.id))
                state.active=chosen.id
                bank,done=state.spend(chosen.cost)
                self.assertEqual(bank,0)
                self.assertEqual(done,chosen)
        self.assertEqual(state.status('ascension_theory'),'available')

    def test_invalid_profiles_are_atomic_and_explain_bad_values_and_trees(self):
        before=balance.active_profile()
        for section,key,path,value in (
            ('buildings','factory','work_cost',0),('weapons','laser','accuracy',101),
            ('modules','laser','technology','missing'),('technologies','ion_drives','tier',8),
            ('rules','production','SHIP_SPEED',float('nan')),('buildings','factory','unique',1),
            ('rules','tomb_worlds','AWAKENING_CHANCE',0)):
            profile=balance.default_profile()
            profile['data'][section][key][path]=value
            with self.subTest(key=key,path=path):
                self.assertTrue(balance.validate(profile))
                with self.assertRaises(balance.BalanceError): balance.activate(profile)
                self.assertEqual(balance.active_profile(),before)
        profile=balance.default_profile()
        profile['data']['technologies']['ion_drives']['effects']['does_not_exist']=1
        self.assertTrue(balance.validate(profile))

    def test_json_save_backup_conflict_and_undo_redo(self):
        path=self.root/'balance.json'
        doc=BalanceDocument(path)
        doc.set('buildings','factory',('resource_cost',),60)
        doc.save()
        first=path.read_text()
        doc.set('buildings','factory',('resource_cost',),75)
        doc.undo()
        self.assertFalse(doc.dirty)
        doc.redo()
        doc.save()
        self.assertEqual(path.with_suffix('.json.bak').read_text(),first)
        self.assertEqual(balance.read_profile(path),doc.profile)
        path.write_text(first)
        with self.assertRaises(balance.BalanceError): doc.save()
        self.assertEqual(path.read_text(),first)
        doc.set('buildings','factory',('work_cost',),0)
        with self.assertRaises(balance.BalanceError): doc.save(self.root/'bad.json')
        self.assertFalse((self.root/'bad.json').exists())

    def test_saved_balance_survives_later_edits_and_browsing_other_saves(self):
        profile=balance.default_profile()
        profile['name']='Old campaign balance'
        profile['data']['buildings']['factory']['work_cost']=19
        profile['data']['rules']['production']['SHIP_SPEED']=.031
        profile['data']['rules']['economy']['STARTING_CREDITS']=543
        profile['data']['technologies']['ion_drives']['effects']['ship_speed']=33
        balance.activate(profile)
        g=game()
        from orion.research import TECHNOLOGIES
        g.research=TECHNOLOGIES['ion_drives'].cost
        g.choose_research('ion_drives')
        g.ships=[Ship(1,'scout',0)]
        g.next_ship_id=2
        g.systems[1].x,g.systems[1].y=g.systems[0].x+.04,g.systems[0].y
        g.send_ships([1],1)
        g.queue_building(0,2,'factory')
        store=Storage(self.root)
        first=store.save(g)
        balance.activate(balance.default_profile())
        normal=game()
        second=store.save(normal)
        normal_profile=balance.active_profile()
        rows=store.list_saves()
        self.assertEqual(len(rows),2)
        self.assertTrue(all('state' in row for row in rows))
        self.assertEqual(balance.active_profile(),normal_profile)
        restored,meta=store.load(first)
        self.assertEqual(restored,g)
        self.assertEqual(balance.active_profile()['name'],'Old campaign balance')
        self.assertEqual(restored.planet_at(0,2).construction_queue[0].spec.work_cost,19)
        self.assertEqual(restored.ships[0].speed_bonus,33)
        self.assertEqual(store.load(store.save(restored))[0],restored)
        clone=GameState.from_dict(restored.to_dict())
        self.assertEqual(balance.profile_for(clone),profile)
        self.assertEqual(store.load(store.save(clone))[0],clone)
        payload=json.loads(second.read_text())
        payload['version']=35
        payload.pop('balance')
        old=self.root/'legacy.json'
        old.write_text(json.dumps(payload))
        restored,_=store.load(old)
        self.assertEqual(restored,normal)
        self.assertEqual(balance.active_profile(),balance.legacy_profile())

    def test_failed_load_restores_active_balance_and_does_not_rewrite_save(self):
        store=Storage(self.root)
        path=store.save(game())
        payload=json.loads(path.read_text())
        payload['balance']['data']['buildings']['factory']['industry']=20
        payload['game']['turn']=-1
        path.write_text(json.dumps(payload))
        before=path.read_bytes()
        with self.assertRaises(SaveError): store.load(path)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(balance.active_profile(),balance.default_profile())

    def test_moved_research_is_loaded_with_its_saved_prerequisites(self):
        doc=BalanceDocument(self.root/'custom.json')
        doc.move_technology('fusion_drives','construction',1,0)
        balance.activate(doc.profile)
        g=game()
        from orion.research import TECHNOLOGIES
        g.research=TECHNOLOGIES['fusion_drives'].cost
        self.assertIsNotNone(g.choose_research('fusion_drives'))
        store=Storage(self.root)
        path=store.save(g)
        balance.activate(balance.default_profile())
        with self.assertRaises(SaveError): GameState.from_dict(g.to_dict())
        restored,_=store.load(path)
        self.assertEqual(restored,g)
        self.assertEqual(restored.technology.completed_tiers('construction'),{1})

    def test_profile_is_reread_for_new_games_and_rejected_new_game_restores_previous_rules(self):
        path=self.root/'configured.json'
        profile=balance.default_profile()
        balance.write_profile(path,profile)
        balance.configure(path)
        old=game()
        profile['data']['rules']['economy']['STARTING_CREDITS']=444
        profile['data']['rules']['economy']['STARTING_POPULATION']=1
        profile['data']['galaxy_sizes']['Compact']['star_count']=26
        balance.write_profile(path,profile)
        with self.assertRaises(SaveError): new_game(galaxy_size='not a size')
        self.assertEqual(balance.active_profile(),balance.profile_for(old))
        g=new_game(galaxy_size='Compact',seed=3,with_guardians=False,with_tombs=False,random_starts=False)
        self.assertEqual((len(g.systems),g.credits,g.planet_at(0,2).population),(26,444,1))
        self.assertLessEqual(g.planet_at(0,2).farmers+g.planet_at(0,2).miners,1)
        store=Storage(self.root)
        self.assertEqual(store.load(store.save(g))[0],g)

    def test_growth_threshold_and_defense_changes_roundtrip(self):
        profile=balance.default_profile()
        profile['data']['rules']['population'].update(GROWTH_THRESHOLD=10,GROWTH_LIMIT=30)
        profile['data']['rules']['defenses'].update(BASE_HULL=75,SHIELD_CAPACITY=300)
        balance.activate(profile)
        g=game()
        p=g.planet_at(0,2)
        p.buildings=['missile_base','planetary_shield']
        p.battery_hull,p.shield_points=75,300
        p.growth_progress=9
        from orion.population import PopulationReport,advance
        advance(p,PopulationReport(p.population,16,30,9,True,growth_limit=30))
        self.assertTrue(0<=p.growth_progress<10)
        store=Storage(self.root)
        self.assertEqual(store.load(store.save(g))[0],g)


class EditorInterfaceTests(BalanceTestCase):
    def setUp(self):
        super().setUp()
        import pygame as pg
        from orion.balance_editor import BalanceEditor
        self.addCleanup(pg.quit)
        self.editor=BalanceEditor(self.root/'balance.json')
        self.editor.draw()
        self.editor.present()

    def click(self,key):
        import pygame as pg
        e=self.editor
        e.draw()
        _,rect,_,enabled=next(b for b in e.buttons if b[0]==key)
        self.assertTrue(enabled)
        pos=self.window_pos(rect.center)
        for event in (pg.MOUSEBUTTONDOWN,pg.MOUSEBUTTONUP):
            e.handle_event(pg.event.Event(event,button=1,pos=pos))
            e.draw()

    def window_pos(self,point):
        v=self.editor.viewport
        return (v.x+round(point[0]*v.w/1440),v.y+round(point[1]*v.h/900))

    def test_click_edit_save_filter_and_unsaved_close(self):
        import pygame as pg
        e=self.editor
        self.click('field_resource_cost')
        e.handle_event(pg.event.Event(pg.TEXTINPUT,text='63'))
        self.click('save')
        self.assertEqual(balance.read_profile(e.document.path)['data']['buildings']['factory']['resource_cost'],63)
        self.click('field_work_cost')
        e.handle_event(pg.event.Event(pg.TEXTINPUT,text='0'))
        self.click('save')
        self.assertTrue(e.error)
        self.assertEqual(balance.read_profile(e.document.path)['data']['buildings']['factory']['work_cost'],24)
        e.request_exit()
        self.assertEqual(e.modal['kind'],'exit')
        self.click('modal_cancel')
        self.assertTrue(e.running)
        self.click('undo')
        self.assertFalse(e.document.dirty)

    def test_real_drag_swaps_research_and_modes_and_dropdowns_work(self):
        import pygame as pg
        e=self.editor
        self.click('tree')
        source=next(b[1] for b in e.buttons if b[0]=='tech_ion_drives').center
        target=next(r.center for r,b,t,s in e.drop_slots if (b,t,s)==('construction',1,0))
        e.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN,button=1,pos=self.window_pos(source)))
        e.handle_event(pg.event.Event(pg.MOUSEMOTION,pos=self.window_pos(target),rel=(0,0),buttons=(1,0,0)))
        e.handle_event(pg.event.Event(pg.MOUSEBUTTONUP,button=1,pos=self.window_pos(target)))
        e.draw()
        self.assertEqual(e.document.entry('technologies','ion_drives')['branch'],'construction')
        self.assertFalse(e.errors)
        self.click('data')
        self.assertEqual(e.identifier,'ion_drives')
        self.click('field_branch')
        self.assertEqual(e.modal['kind'],'choices')
        self.click('choice_power')
        self.assertEqual(e.document.entry('technologies','ion_drives')['branch'],'power')
        self.assertTrue(e.errors)  # Three alternatives: save must be blocked.
        self.click('undo')
        self.assertFalse(e.errors)
        self.click('save')
        self.assertTrue(e.document.path.exists())

    def test_double_click_opens_values_without_platform_click_metadata(self):
        e=self.editor
        self.click('tree')
        self.click('tech_ion_drives')
        self.click('tech_ion_drives')
        self.assertEqual((e.mode,e.section,e.identifier),('data','technologies','ion_drives'))


if __name__=='__main__':
    unittest.main()
