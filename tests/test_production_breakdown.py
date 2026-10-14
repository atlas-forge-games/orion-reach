import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import unittest
import tempfile
from pathlib import Path
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion.production_breakdown import describe, KINDS, ROLES
from orion.planet_view import worker_row_rect
from orion.fleet_art import load_ship_art

class BreakdownTests(unittest.TestCase):
    def setUp(self):
        self.game=new_game(seed=12,random_starts=False,with_ai=False,with_guardians=False,with_tombs=False,with_black_holes=False)
        self.planet=self.game.planet_at(0,2)

    def test_empty_colony_explains_all_four_outputs(self):
        p=self.planet
        p.buildings=[]
        p.farmers,p.scientists,p.miners=2,1,1
        expected={'industry':4,'research':2,'mining':4,'food':10}
        for kind,total in expected.items():
            with self.subTest(kind=kind):
                result=describe(self.game,p,kind)
                self.assertEqual(result.total,total)
                self.assertIn(f'TOTAL ',result.lines[-1])
                self.assertTrue(any('After strain:' in x for x in result.lines))

    def test_unpowered_facilities_do_not_contribute(self):
        p=self.planet
        p.buildings=['factory','research_lab','mine']
        p.disabled_buildings=[0,1,2]
        for kind in KINDS:
            result=describe(self.game,p,kind)
            self.assertTrue(any('excluded from output' in x for x in result.lines))
        self.assertFalse(any('Factory (incl.' in x for x in describe(self.game,p,'industry').lines))

    def test_frontier_rounding_matches_live_economy(self):
        from test_administration import settle
        from orion import economy, research
        sid=next(s.id for s in self.game.systems[1:] if s.worlds)
        p=settle(self.game,sid,ly=21)
        p.population=8
        p.farmers,p.scientists,p.miners=2,1,1
        p.buildings=['factory','mine','research_lab','solar_array']
        p.richness='Rich'
        b=self.game.bonuses_for(p.owner)
        gross=research.gross_colony_yields(p,b)
        expected={'industry':gross[0],'credits':gross[1],'research':gross[2],
                  'food':self.game.population_report(p).produced,'mining':economy.mining_output(p,b)}
        for kind,value in expected.items():
            with self.subTest(kind=kind):
                rows=describe(self.game,p,kind).lines
                after=next(x for x in rows if x.startswith('After strain:'))
                self.assertEqual(float(after.rsplit(' = ',1)[1]),value)
                self.assertTrue(any('distance 36.00%' in x for x in rows))

    def test_outpost_has_real_art(self):
        image=load_ship_art('outpost_ship')
        self.assertIsNotNone(image)
        self.assertGreater(image.get_height(),image.get_width())

    def test_rightclick_rows_and_totals_preserves_assignments(self):
        with tempfile.TemporaryDirectory() as folder:
            app=App(Path(folder),capture=True)
            try:
                app.game=self.game
                app.open_planet(2)
                before=self.game.to_dict()
                targets=[(worker_row_rect(role).center,kind) for role,kind in ROLES.items()]
                targets += [((310+i*124,100),kind) for i,kind in enumerate(KINDS)]
                for pos,kind in targets:
                    v=app.viewport
                    pos=(round(v.x+pos[0]*v.w/1440),round(v.y+pos[1]*v.h/900))
                    app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP,button=3,pos=pos))
                    self.assertEqual(app.dialog['output_breakdown'],describe(self.game,self.planet,kind))
                    app.render()
                    app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP,button=3,pos=pos))
                    self.assertIsNone(app.dialog)
                self.assertEqual(self.game.to_dict(),before)
            finally:
                app.audio.close()
                pg.quit()
