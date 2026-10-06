"""Screen controller and event loop. Gameplay rules live in model.py."""

from __future__ import annotations

from array import array
from datetime import datetime
import math
from pathlib import Path
import pygame as pg

from .art import Backdrop, SIZE
from . import __version__
from .model import GALAXY_SIZES, RuleError, SaveError, new_game
from .buildings import BUILDINGS
from .storage import Storage
from .system_views import draw_system, draw_planet_overview
from .colony_view import draw_colony
from .ui import (Button, CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED,
                 arrow, emblem, font, panel, paragraph, shorten, text, text_image)

STAR_COLORS={"Yellow dwarf":(230,207,141), "Blue star":(113,181,231),
             "Red dwarf":(221,124,108), "White star":(217,228,239), "Orange dwarf":(235,170,106)}
MAP=pg.Rect(64,180,962,573)
GAME_SCREENS=("galaxy", "system", "planet", "colony")


class App:
    def __init__(self,data_dir: Path | None=None,capture=False):
        pg.display.init()
        pg.font.init()
        # App can be re-created in an interpreter after pygame.quit().
        font.cache_clear()
        text_image.cache_clear()
        self.storage=Storage(data_dir)
        self.settings=self.storage.load_settings()
        self.capture=capture
        self.windowed_size=(1280,800)
        self.window=pg.display.set_mode(self.windowed_size,pg.RESIZABLE)
        pg.display.set_caption("Orion Reach | Space Strategy Prototype")
        self.canvas=pg.Surface(SIZE).convert()
        self.viewport=pg.Rect(0,0,*self.windowed_size)
        self.backdrop=Backdrop()
        self.clock=pg.time.Clock()
        self.running=True
        self.screen="menu"
        self.game=None
        self.buttons=[]
        self.focus=None
        self.keyboard_mode=False
        self.mouse=(-1,-1)
        self.pressed=None
        self.time=0.0
        self.dialog=None
        self.notice=""
        self.notice_until=0.0
        self.notice_error=False
        self.empire="Terran Union"
        self.seed=""
        self.size="Standard"
        self.field=None
        self.select_all=False
        self.settings_return="menu"
        self.pause_return="galaxy"
        self.campaign_view="galaxy"
        self.colony_slot=None
        self.load_rows=[]
        self.load_page=0
        self.sound=None
        if not capture:
            try:
                pg.mixer.init(frequency=22050,size=-16,channels=1,buffer=512)
                samples=array("h",(int(2600*math.sin(2*math.pi*660*i/22050)*(1-i/1654)**2)
                                   for i in range(1654)))
                self.sound=pg.mixer.Sound(buffer=samples)
            except pg.error:
                pass
        if self.settings["fullscreen"] and not capture:
            self.set_fullscreen(True)
        self.render()

    def toast(self,message,error=False):
        self.notice=str(message)
        self.notice_until=self.time+(7 if error else 4)
        self.notice_error=error

    def go(self,screen):
        if screen in GAME_SCREENS and self.game is None:
            screen="menu"
        if screen in ("planet","colony") and self.game.selected_planet is None:
            screen="system"
        self.screen=screen
        self.buttons=[]
        self.focus=None
        self.pressed=None
        self.field=None
        self.select_all=False
        pg.key.stop_text_input()
        if screen in GAME_SCREENS:
            self.campaign_view=screen
        if screen=="colony":
            self.focus="build_factory"
        if screen=="system":
            worlds=self.game.systems[self.game.selected_system].worlds
            if worlds:
                first=next((p.id for p in worlds if p.colonized),0)
                chosen=self.game.selected_planet if self.game.selected_planet is not None else first
                self.focus=f"world_{chosen}"
        if screen=="load":
            self.load_rows=self.storage.list_saves()
            self.load_page=0

    def open_system(self,system_id):
        if self.game is None or not 0 <= system_id < len(self.game.systems):
            return
        if self.game.selected_system != system_id:
            self.game.selected_planet=None
        self.game.selected_system=system_id
        self.go("system")

    def open_planet(self,planet_id):
        worlds=self.game.systems[self.game.selected_system].worlds
        if not 0 <= planet_id < len(worlds):
            return
        self.game.selected_planet=planet_id
        self.colony_slot=None
        self.go("planet")

    def cycle_system(self,delta):
        self.game.selected_system=(self.game.selected_system+delta)%len(self.game.systems)
        self.game.selected_planet=None
        if self.screen=="system":
            self.go("system")
        else:
            self.focus=f"star_{self.game.selected_system}"
            self.keyboard_mode=True

    def cycle_planet(self,delta):
        worlds=self.game.systems[self.game.selected_system].worlds
        if not worlds:
            return
        current=self.game.selected_planet
        if current is None:
            current=-1 if delta>0 else 0
        self.game.selected_planet=(current+delta)%len(worlds)
        self.colony_slot=None
        if self.screen in ("planet","colony"):
            self.go(self.screen)
        else:
            self.focus=f"world_{self.game.selected_planet}"
            self.keyboard_mode=True

    def pause(self):
        if self.screen in GAME_SCREENS:
            self.pause_return=self.screen
        self.go("pause")

    def resume(self):
        self.go(self.pause_return)

    def click_sound(self):
        if self.sound is not None and self.settings["sound"]:
            self.sound.play()

    def set_fullscreen(self,enabled):
        try:
            if enabled:
                if not self.window.get_flags() & pg.FULLSCREEN:
                    self.windowed_size=self.window.get_size()
                self.window=pg.display.set_mode((0,0),pg.FULLSCREEN)
            else:
                self.window=pg.display.set_mode(self.windowed_size,pg.RESIZABLE)
            self.settings["fullscreen"]=enabled
        except pg.error:
            self.settings["fullscreen"]=False
            self.window=pg.display.set_mode(self.windowed_size,pg.RESIZABLE)
            self.toast("Fullscreen is unavailable on this display.",True)

    def toggle_setting(self,key):
        if key=="fullscreen":
            self.set_fullscreen(not self.settings[key])
        else:
            self.settings[key]=not self.settings[key]
        try:
            self.storage.save_settings(self.settings)
        except SaveError as exc:
            self.toast(exc,True)

    def show_settings(self,return_to="menu"):
        self.settings_return=return_to
        self.go("settings")

    def edit_field(self,name):
        self.field=name
        self.select_all=True
        pg.key.start_text_input()

    def start_game(self):
        try:
            self.game=new_game(self.empire,self.size,int(self.seed) if self.seed else None)
        except (ValueError,SaveError) as exc:
            self.toast(str(exc),True)
            return
        self.colony_slot=None
        self.go("galaxy")
        self.save_game(autosave=True)

    def save_game(self,autosave=False):
        if self.game is None:
            return True
        try:
            self.storage.save(self.game,autosave=autosave)
            if not autosave:
                self.toast("Game saved. Find this snapshot under Load Game.")
            return True
        except SaveError as exc:
            self.toast(exc,True)
            return False

    def load_game(self,path):
        try:
            state,_=self.storage.load(path)
        except SaveError as exc:
            self.toast(exc,True)
            return
        self.game=state
        self.colony_slot=None
        self.go("galaxy")
        self.toast(f"Welcome back, {state.empire_name}.")

    def advance_turn(self):
        report=self.game.advance_turn()
        if self.save_game(autosave=True):
            message=f"Turn {self.game.turn} · +{report.income} CR · +{report.research} RP"
            if report.completed:
                message+=" · Completed: "+", ".join(report.completed)
            self.toast(message+" · Autosaved")
            if report.completed:
                self.notice_until=self.time+7

    def select_colony_slot(self,index):
        self.colony_slot=index

    def queue_building(self,building_id):
        try:
            self.game.queue_building(self.game.selected_system,self.game.selected_planet,building_id)
            planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
            self.colony_slot=planet.used_slots-1
            if self.save_game(autosave=True):
                self.toast(f"{BUILDINGS[building_id].name} queued · {BUILDINGS[building_id].credit_cost} CR paid")
        except RuleError as exc:
            self.toast(exc,True)

    def cancel_construction(self,index):
        try:
            refund=self.game.cancel_construction(self.game.selected_system,self.game.selected_planet,index)
            self.colony_slot=None
            if self.save_game(autosave=True):
                self.toast(f"Project cancelled · {refund} CR refunded")
        except RuleError as exc:
            self.toast(exc,True)

    def demolish_request(self,index):
        system_id,planet_id=self.game.selected_system,self.game.selected_planet
        planet=self.game.planet_at(system_id,planet_id)
        if not 0 <= index < len(planet.buildings):
            return
        name=BUILDINGS[planet.buildings[index]].name
        def remove():
            try:
                self.game.demolish_building(system_id,planet_id,index)
                self.colony_slot=None
                if self.save_game(autosave=True):
                    self.toast(f"{name} demolished · One slot is now available")
            except RuleError as exc:
                self.toast(exc,True)
        self.confirm(f"Demolish {name.lower()}?", "Its output will stop immediately and its slot will become available. Construction costs are not refunded.",
                     "Demolish",remove)

    def to_menu(self):
        if self.save_game(autosave=True):
            self.go("menu")
        else:
            self.confirm("Could not save", "You can stay here and try again, or return to the menu. Your campaign remains in memory.",
                         "Return to menu",lambda:self.go("menu"))

    def confirm(self,title,body,label,action):
        self.dialog={"title":title,"body":body,"label":label,"action":action}
        self.focus="dialog_cancel"
        self.keyboard_mode=True
        self.buttons=[]
        self.field=None
        pg.key.stop_text_input()

    def cancel_dialog(self):
        self.dialog=None
        self.buttons=[]
        self.focus=None

    def accept_dialog(self):
        action=self.dialog["action"]
        self.cancel_dialog()
        action()

    def quit_request(self):
        self.confirm("Leave the stars?", "Your current campaign will be autosaved before the game closes." if self.game else
                     "You can return whenever you are ready to begin your expedition.","Quit game",self.quit_saved)

    def quit_saved(self):
        if not self.save_game(autosave=True):
            self.confirm("Save failed", "The latest progress could not be written. Cancel to keep playing or exit without saving.",
                         "Exit without saving",self.quit_now)
        else:
            self.quit_now()

    def quit_now(self):
        self.running=False

    def logical_pos(self,pos):
        if not self.viewport.collidepoint(pos):
            return (-1,-1)
        return ((pos[0]-self.viewport.x)*SIZE[0]/self.viewport.w,
                (pos[1]-self.viewport.y)*SIZE[1]/self.viewport.h)

    def activate(self,button):
        if not button.enabled:
            return
        self.click_sound()
        button.action()

    def handle_event(self,event):
        if event.type==pg.QUIT:
            self.quit_request()
            return
        if event.type==pg.WINDOWFOCUSLOST:
            self.pressed=None
        if event.type==pg.MOUSEMOTION:
            self.mouse=self.logical_pos(event.pos)
            self.keyboard_mode=False
        if event.type in (pg.MOUSEBUTTONDOWN,pg.MOUSEBUTTONUP) and event.button==1:
            self.mouse=self.logical_pos(event.pos)
            self.keyboard_mode=False
            hovered=next((b for b in reversed(self.buttons) if b.enabled and b.rect.collidepoint(self.mouse)),None)
            if event.type==pg.MOUSEBUTTONDOWN:
                self.pressed=hovered.key if hovered else None
                if hovered is None:
                    self.field=None
                    pg.key.stop_text_input()
            elif hovered and hovered.key==self.pressed:
                self.pressed=None
                self.activate(hovered)
        if event.type==pg.MOUSEWHEEL and self.screen=="load" and not self.dialog:
            self.change_load_page(-1 if event.y>0 else 1)
        if event.type==pg.TEXTINPUT and self.field and not self.dialog:
            current=getattr(self,self.field)
            if self.select_all:
                current=""
                self.select_all=False
            incoming="".join(c for c in event.text if c.isprintable())
            if self.field=="seed":
                incoming="".join(c for c in incoming if c in "0123456789")
            setattr(self,self.field,(current+incoming)[:9 if self.field=="seed" else 28])
        if event.type!=pg.KEYDOWN:
            return
        if event.key==pg.K_F11 and not self.dialog:
            self.toggle_setting("fullscreen")
            return
        if event.key==pg.K_ESCAPE:
            if self.dialog:
                self.cancel_dialog()
            elif self.field:
                self.field=None
                pg.key.stop_text_input()
            elif self.screen=="galaxy":
                self.pause()
            elif self.screen=="system":
                self.go("galaxy")
            elif self.screen=="planet":
                self.go("system")
            elif self.screen=="colony":
                self.go("planet")
            elif self.screen=="pause":
                self.resume()
            elif self.screen=="settings":
                self.go(self.settings_return)
            elif self.screen=="menu":
                self.quit_request()
            else:
                self.go("menu")
            return
        if self.field:
            if event.key==pg.K_a and event.mod & (pg.KMOD_CTRL|pg.KMOD_META):
                self.select_all=True
            elif event.key==pg.K_BACKSPACE:
                value=getattr(self,self.field)
                setattr(self,self.field,"" if self.select_all else value[:-1])
                self.select_all=False
            elif event.key in (pg.K_RETURN,pg.K_KP_ENTER):
                self.field=None
                pg.key.stop_text_input()
                return
            elif event.key==pg.K_TAB:
                self.focus=self.field
                self.field=None
                pg.key.stop_text_input()
            else:
                return
        enabled=[b for b in self.buttons if b.enabled]
        if event.key in (pg.K_TAB,pg.K_DOWN,pg.K_UP):
            if not enabled:
                return
            keys=[b.key for b in enabled]
            direction=-1 if event.key==pg.K_UP or (event.key==pg.K_TAB and event.mod & pg.KMOD_SHIFT) else 1
            index=keys.index(self.focus) if self.focus in keys else (-1 if direction>0 else 0)
            self.focus=keys[(index+direction)%len(keys)]
            self.keyboard_mode=True
        elif event.key in (pg.K_RETURN,pg.K_KP_ENTER,pg.K_SPACE):
            selected=next((b for b in enabled if b.key==self.focus),enabled[0] if enabled else None)
            if selected:
                self.activate(selected)
        elif self.screen in GAME_SCREENS and not self.dialog:
            if event.key==pg.K_F5:
                self.save_game()
            elif event.key==pg.K_e:
                self.advance_turn()
            elif event.key in (pg.K_LEFT,pg.K_RIGHT):
                delta=1 if event.key==pg.K_RIGHT else -1
                if self.screen=="galaxy":
                    self.cycle_system(delta)
                else:
                    self.cycle_planet(delta)

    def is_active(self,button):
        if self.dialog and not button.key.startswith("dialog_"):
            return False
        return ((self.keyboard_mode and self.focus==button.key) or
                (not self.keyboard_mode and button.rect.collidepoint(self.mouse)))

    def button(self,key,label,rect,action,style="normal",subtitle="",enabled=True):
        b=Button(key,label,pg.Rect(rect),action,subtitle,style,enabled)
        self.buttons.append(b)
        b.draw(self.canvas,self.is_active(b))
        return b

    def chrome(self,section="COMMAND",back=None):
        emblem(self.canvas,77,64,.62)
        text(self.canvas,"ORION REACH",(110,46),18,INK,spacing=2)
        text(self.canvas,section,(111,73),10,MUTED,"mono",2)
        text(self.canvas,f"PROTOTYPE  /  {__version__.rsplit('.',1)[0]}",(1376,58),11,MUTED,"mono",right=True)
        pg.draw.line(self.canvas,LINE,(64,107),(1376,107))
        if back:
            self.button("back","←  Back",(62,126,118,46),back,"ghost")

    def draw_menu(self):
        self.chrome("A TURN-BASED SPACE STRATEGY")
        text(self.canvas,"THE GALAXY IS WAITING",(88,166),11,GOLD,"mono",3)
        text(self.canvas,"ORION",(80,201),92,INK,"title",6)
        text(self.canvas,"R E A C H",(88,311),39,INK,"sans",5)
        pg.draw.line(self.canvas,GOLD,(88,389),(131,389),2)
        text(self.canvas,"One world. A thousand possibilities.",(149,377),16,MUTED)
        if self.game:
            self.button("resume","Continue",(88,444,417,66),lambda:self.go(self.campaign_view),"primary")
            self.button("new","New Game",(88,523,417,64),lambda:self.go("setup"),"menu")
            self.button("load","Load Game",(88,592,417,64),lambda:self.go("load"),"menu")
            self.button("settings","Settings",(88,661,417,60),lambda:self.show_settings(),"menu")
            self.button("quit","Quit",(88,726,417,60),self.quit_request,"menu")
        else:
            self.button("new","New Game",(88,454,417,66),lambda:self.go("setup"),"primary")
            self.button("load","Load Game",(88,535,417,70),lambda:self.go("load"),"menu","Return to your empire")
            self.button("settings","Settings",(88,618,417,66),lambda:self.show_settings(),"menu")
            self.button("quit","Quit",(88,697,417,66),self.quit_request,"menu")
        pg.draw.line(self.canvas,LINE,(64,835),(1376,835))
        text(self.canvas,"01  /  A NEW HORIZON",(742,799),10,GOLD,"mono",2)
        text(self.canvas,"SOL SYSTEM   ·   TERRAN HOMEWORLD",(1110,801),9,MUTED,"mono",right=True)
        text(self.canvas,"MOUSE OR ↑ ↓ + ENTER",(88,857),10,FAINT,"mono",1)
        self.button("about","About the prototype",(1143,845,235,40),lambda:self.go("about"),"ghost")

    def heading(self,kicker,title,description):
        text(self.canvas,kicker,(256,174),11,GOLD,"mono",2)
        text(self.canvas,title,(252,201),42,INK,"title")
        text(self.canvas,description,(256,262),16,MUTED)

    def input_box(self,key,label,value,rect,placeholder):
        r=pg.Rect(rect)
        text(self.canvas,label,(r.x,r.y-31),12,MUTED,"mono",1)
        b=self.button(key,"",r,lambda:self.edit_field(key))
        if self.field==key:
            pg.draw.rect(self.canvas,GOLD,r,1)
            if self.select_all and value:
                pg.draw.rect(self.canvas,(46,72,85),(r.x+16,r.y+13,min(r.w-32,font(20).size(value)[0]+3),29))
        shown=value if value else placeholder
        text(self.canvas,shorten(shown,r.w-46,20),(r.x+18,r.y+15),20,INK if value else FAINT)
        if self.field==key and not self.select_all and self.time%1 < .55:
            x=r.x+18+font(20).size(shorten(value,r.w-46,20))[0]
            pg.draw.line(self.canvas,GOLD,(x,r.y+14),(x,r.y+40))

    def choose_size(self,size):
        self.size=size
        self.field=None
        pg.key.stop_text_input()

    def draw_setup(self):
        self.chrome("NEW EXPEDITION",lambda:self.go("menu"))
        self.heading("01  /  FOUND YOUR EMPIRE","Every empire starts somewhere.","Name your civilization and chart a new galaxy.")
        self.input_box("empire","EMPIRE NAME",self.empire,(256,343,590,62),"Your civilization")
        text(self.canvas,"GALAXY SIZE",(256,445),12,MUTED,"mono",1)
        for i,(size,count) in enumerate(GALAXY_SIZES.items()):
            r=pg.Rect(256+i*199,479,190,99)
            self.button("size_"+size,"",r,lambda s=size:self.choose_size(s))
            if self.size==size:
                pg.draw.rect(self.canvas,GOLD,r,1)
                pg.draw.circle(self.canvas,GOLD,(r.right-19,r.y+21),3)
            text(self.canvas,size,(r.x+17,r.y+19),18,GOLD if self.size==size else INK)
            text(self.canvas,f"{count} star systems",(r.x+17,r.y+56),12,MUTED)
        self.input_box("seed","GALAXY SEED · OPTIONAL",self.seed,(256,650,340,60),"Random")
        paragraph(self.canvas,"The same seed and size create the same stars.",(620,662),235,13,MUTED,21)
        self.button("launch","Begin expedition",(256,760,590,62),self.start_game,"primary")
        panel(self.canvas,(939,340,252,368))
        emblem(self.canvas,1065,405,1.25)
        text(self.canvas,"YOUR FIRST CHAPTER",(961,477),10,GOLD,"mono",1)
        paragraph(self.canvas,"A homeworld at Sol. An uncharted future.",(961,510),208,20,INK,31)
        paragraph(self.canvas,"This prototype lets you explore the map and save your campaign.",(961,602),208,13,MUTED,22)

    def change_load_page(self,delta):
        pages=max(1,(len(self.load_rows)+3)//4)
        self.load_page=max(0,min(pages-1,self.load_page+delta))
        self.focus=None

    def draw_load(self):
        self.chrome("CAMPAIGN ARCHIVE",lambda:self.go("menu"))
        self.heading("02  /  RETURN TO THE STARS","Load a campaign.","Your autosave and manual snapshots appear here.")
        if not self.load_rows:
            panel(self.canvas,(256,334,928,354))
            emblem(self.canvas,720,421,1.3)
            text(self.canvas,"Your story is still unwritten.",(511,490),25,INK,"title")
            text(self.canvas,"Begin a new expedition to create your first save.",(498,540),15,MUTED)
            self.button("empty_new","Start a new game",(548,594,345,60),lambda:self.go("setup"),"primary")
            return
        for i,row in enumerate(self.load_rows[self.load_page*4:self.load_page*4+4]):
            y=325+i*108
            r=pg.Rect(256,y,928,96)
            if "error" in row:
                panel(self.canvas,r)
                text(self.canvas,"Unavailable save",(280,y+15),20,RED)
                text(self.canvas,shorten(row["error"],780,14),(280,y+54),14,MUTED)
                continue
            state,meta=row["state"],row["meta"]
            self.button("load_"+str(i),"",r,lambda p=row["path"]:self.load_game(p))
            label="AUTOSAVE" if meta.get("autosave") else "MANUAL SAVE"
            text(self.canvas,label,(279,y+17),9,GOLD,"mono",1)
            text(self.canvas,shorten(state.empire_name,435,22),(279,y+39),22,INK)
            stamp=datetime.fromisoformat(meta["saved_at"]).astimezone().strftime("%d %b %Y  %H:%M")
            text(self.canvas,f"TURN {state.turn}   ·   {state.year}",(825,y+21),12,CYAN,"mono")
            text(self.canvas,f"{len(state.systems)} systems   ·   {stamp}",(825,y+52),11,MUTED)
            arrow(self.canvas,(1150,y+47))
        pages=max(1,(len(self.load_rows)+3)//4)
        text(self.canvas,f"PAGE {self.load_page+1} / {pages}",(640,792),11,MUTED,"mono",1)
        self.button("prev","← Previous",(256,776,175,48),lambda:self.change_load_page(-1),enabled=self.load_page>0)
        self.button("next","Next →",(1009,776,175,48),lambda:self.change_load_page(1),enabled=self.load_page<pages-1)

    def draw_settings(self):
        self.chrome("PREFERENCES",lambda:self.go(self.settings_return))
        self.heading("03  /  MAKE IT YOURS","Set your course.","Changes take effect immediately and are saved automatically.")
        options=[("fullscreen","Fullscreen","Use the entire display. F11 also toggles this setting."),
                 ("animated_background","Animated background","Moving ships and softly twinkling stars."),
                 ("sound","Interface sounds","A quiet tone when you activate a control.")]
        for i,(key,label,description) in enumerate(options):
            y=340+i*128
            panel(self.canvas,(256,y,928,106))
            text(self.canvas,label,(280,y+17),22,INK)
            text(self.canvas,description,(280,y+59),14,MUTED)
            self.button(key,"ON" if self.settings[key] else "OFF",(1020,y+26,135,53),lambda k=key:self.toggle_setting(k))
            if self.settings[key]:
                pg.draw.circle(self.canvas,CYAN,(1132,y+52),4)
        text(self.canvas,"The window can also be resized. The interface scales to fit.",(256,755),14,MUTED)
        self.button("settings_done","Done",(933,760,251,60),lambda:self.go(self.settings_return),"primary")

    def star_pos(self,system):
        return (MAP.x+40+system.x*(MAP.w-80),MAP.y+32+system.y*(MAP.h-64))

    def draw_galaxy(self):
        state=self.game
        if state is None:
            self.go("menu")
            return
        self.chrome("GALAXY OVERVIEW")
        text(self.canvas,shorten(state.empire_name,490,29),(64,127),29,INK,"title")
        text(self.canvas,f"YEAR {state.year}   /   TURN {state.turn}",(725,139),13,CYAN,"mono")
        text(self.canvas,f"{state.credits:,} CR  ·  {state.research:,} RP",(1376,132),19,GOLD,"mono",right=True)
        panel(self.canvas,MAP,(7,17,25))
        # A sparse coordinate grid makes the map legible without implying travel lanes.
        for x in range(MAP.x+44,MAP.right,76):
            pg.draw.line(self.canvas,(14,29,38),(x,MAP.y+1),(x,MAP.bottom-1))
        for y in range(MAP.y+40,MAP.bottom,70):
            pg.draw.line(self.canvas,(14,29,38),(MAP.x+1,y),(MAP.right-1,y))
        text(self.canvas,"SECTOR 01 / LOCAL CLUSTER",(MAP.x+22,MAP.y+18),10,FAINT,"mono",1)
        for star in state.systems:
            x,y=self.star_pos(star)
            selected=star.id==state.selected_system
            color=STAR_COLORS[star.kind]
            pg.draw.circle(self.canvas,tuple(c//8 for c in color),(int(x),int(y)),14)
            pg.draw.circle(self.canvas,tuple(c//3 for c in color),(int(x),int(y)),8)
            pg.draw.circle(self.canvas,color,(int(x),int(y)),4)
            pg.draw.circle(self.canvas,INK,(int(x),int(y)),1)
            if selected:
                pg.draw.circle(self.canvas,GOLD,(int(x),int(y)),19,1)
                for dx,dy in ((-25,0),(25,0),(0,-25),(0,25)):
                    pg.draw.circle(self.canvas,GOLD,(int(x+dx),int(y+dy)),1)
            if star.id==0:
                pg.draw.circle(self.canvas,CYAN,(int(x),int(y)),11,1)
            text(self.canvas,star.name.upper(),(x+11,y-10),11,INK if selected else MUTED,"mono")
            self.button(f"star_{star.id}","",(int(x)-18,int(y)-18,36,36),
                        lambda s=star.id:self.open_system(s),"hotspot")
        star=state.systems[state.selected_system]
        panel(self.canvas,(1051,180,325,573))
        text(self.canvas,"SYSTEM INTELLIGENCE",(1075,203),10,GOLD,"mono",1)
        text(self.canvas,star.name,(1075,245),31,INK,"title")
        text(self.canvas,star.kind,(1075,290),14,MUTED)
        # A schematic star/planet orbital inset.
        center=(1213,390)
        pg.draw.ellipse(self.canvas,LINE,(1108,352,208,80),1)
        pg.draw.ellipse(self.canvas,LINE,(1131,362,161,60),1)
        pg.draw.circle(self.canvas,tuple(c//4 for c in STAR_COLORS[star.kind]),center,24)
        pg.draw.circle(self.canvas,STAR_COLORS[star.kind],center,13)
        if star.planets:
            pg.draw.circle(self.canvas,CYAN,(1131,388),6)
        text(self.canvas,"HOME SYSTEM" if star.id==0 else "SURVEY DATA",(1075,462),10,CYAN,"mono",1)
        lines=[("Planets",str(star.planets)),("Primary world",star.biome if star.planets else "None"),
               ("Minerals",star.richness if star.planets else "—"),
               ("Allegiance","Your empire" if star.id==0 else "Unclaimed")]
        for i,(label,value) in enumerate(lines):
            y=500+i*44
            text(self.canvas,label,(1075,y),13,MUTED)
            text(self.canvas,value,(1352,y),13,INK,right=True)
            pg.draw.line(self.canvas,LINE,(1075,y+30),(1352,y+30))
        self.button("open_system","Open system →",(1075,692,277,43),
                    lambda:self.open_system(self.game.selected_system))
        text(self.canvas,"Click a star to open its solar-system overview.",(64,775),14,MUTED)
        text(self.canvas,f"{state.galaxy_size.upper()}   ·   SEED {state.seed}",(1376,778),10,FAINT,"mono",right=True)
        self.button("pause","Menu  ·  Esc",(64,820,186,54),self.pause)
        self.button("save","Save game  ·  F5",(264,820,229,54),self.save_game)
        text(self.canvas,"EMPIRE ECONOMY",(585,821),10,GOLD,"mono",2)
        income,research=state.empire_rates
        text(self.canvas,f"+{income} credits · +{research} research / turn",(585,844),12,MUTED)
        self.button("end_turn","End turn  ·  E",(1081,813,295,61),self.advance_turn,"primary")

    def draw_pause(self):
        getattr(self,"draw_"+self.pause_return)()
        self.backdrop.dim(self.canvas)
        self.buttons=[]
        panel(self.canvas,(459,218,522,487))
        text(self.canvas,"EXPEDITION PAUSED",(505,257),11,GOLD,"mono",2)
        text(self.canvas,"The stars can wait.",(502,290),34,INK,"title")
        self.button("resume","Resume campaign",(505,365,430,58),self.resume,"primary")
        self.button("save","Save a snapshot",(505,438,430,54),self.save_game)
        self.button("settings","Settings",(505,504,430,54),lambda:self.show_settings("pause"))
        self.button("main_menu","Save & return to main menu",(505,570,430,54),self.to_menu)
        self.button("quit","Quit game",(505,637,430,45),self.quit_request,"ghost")

    def draw_system(self):
        draw_system(self)

    def draw_planet(self):
        draw_planet_overview(self)

    def draw_colony(self):
        draw_colony(self)

    def draw_about(self):
        self.chrome("ABOUT",lambda:self.go("menu"))
        self.heading("A FIRST STEP INTO A LARGER GALAXY","Orion Reach", "An original Python prototype inspired by classic space strategy games.")
        panel(self.canvas,(256,335,928,387))
        text(self.canvas,"WHAT YOU CAN DO",(282,364),11,GOLD,"mono",1)
        paragraph(self.canvas,"Explore solar systems and planets, build up your colony, manage a construction queue and grow industry, income and research. Save and resume your campaigns.",
                  (282,403),840,20,INK,34)
        text(self.canvas,"WHAT COMES NEXT",(282,513),11,GOLD,"mono",1)
        paragraph(self.canvas,"Colonization, population growth, fleets, a research tree, diplomacy and tactical combat. The current colony is a foundation for those systems.",
                  (282,552),840,18,MUTED,32)
        text(self.canvas,"Original procedural artwork · DejaVu fonts · pygame-ce",(282,673),13,MUTED)
        text(self.canvas,"CONTROLS",(256,764),11,GOLD,"mono",1)
        text(self.canvas,"Mouse / Tab / ↑ ↓ + Enter    Esc: back or pause    F11: fullscreen",(256,795),15,INK)

    def draw_dialog(self):
        self.backdrop.dim(self.canvas)
        self.buttons=[]
        panel(self.canvas,(422,290,596,312),PANEL,GOLD)
        text(self.canvas,self.dialog["title"],(454,321),29,INK,"title")
        paragraph(self.canvas,self.dialog["body"],(454,374),526,16,MUTED,27)
        self.button("dialog_cancel","Cancel",(454,505,180,57),self.cancel_dialog)
        self.button("dialog_ok",self.dialog["label"],(650,505,336,57),self.accept_dialog,"primary")

    def render(self):
        self.buttons=[]
        full=self.screen not in (*GAME_SCREENS,"pause")
        self.backdrop.draw(self.canvas,self.time,self.settings["animated_background"],full)
        if self.screen not in ("menu",*GAME_SCREENS,"pause"):
            self.backdrop.dim(self.canvas)
        getattr(self,"draw_"+self.screen)()
        if self.dialog:
            self.draw_dialog()
        if self.notice and self.time<self.notice_until:
            message=shorten(self.notice,1160,16)
            width=min(1224,font(16).size(message)[0]+54)
            r=pg.Rect((1440-width)//2,16,width,47)
            panel(self.canvas,r,(24,33,39),RED if self.notice_error else CYAN)
            text(self.canvas,message,(r.x+27,r.y+13),16,RED if self.notice_error else INK)

    def present(self):
        width,height=self.window.get_size()
        scale=min(width/SIZE[0],height/SIZE[1])
        size=(max(1,round(SIZE[0]*scale)),max(1,round(SIZE[1]*scale)))
        self.viewport=pg.Rect((width-size[0])//2,(height-size[1])//2,*size)
        self.window.fill((2,5,9))
        self.window.blit(pg.transform.smoothscale(self.canvas,size),self.viewport.topleft)
        pg.display.flip()

    def run(self):
        self.present()
        while self.running:
            self.time+=min(self.clock.tick(60)/1000,.1)
            for event in pg.event.get():
                self.handle_event(event)
                # Screen transitions must update hit regions before the next queued event.
                self.render()
            self.render()
            self.present()
