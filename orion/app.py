"""Screen controller and event loop. Gameplay rules live in model.py."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pygame as pg

from .art import Backdrop, SIZE
from .audio import Audio
from .branding import SPLASH_SECONDS, StudioBrand
from . import __version__
from .model import GALAXY_SIZES, PLAYER, RIVAL, RuleError, SaveError, new_game
from .buildings import BUILDINGS
from .storage import Storage
from .system_views import draw_system
from .planet_view import draw_planet_overview, draw_production
from .colony_view import draw_colony, turn_label
from .empire import COLONIES_PER_PAGE, FILTERS, SORT_KEYS, colony_rows
from .empire_view import draw_empire
from .rival_view import draw_rival
from .diplomacy_view import draw_diplomacy
from .research_view import draw_research
from .research import BRANCHES, TECHNOLOGIES, choices
from .combat import retreat_destination
from .combat_view import VISIBLE_ROWS, draw_combat
from .combat_effects import CombatAnimation
from .victory import colonies, invasion_strength, troop_transports
from .victory_view import draw_objectives, draw_result
from .production import PROJECTS, SHIP_TYPES
from .setup_view import draw_setup
from .races import RACES, default_rival_race
from .diplomacy import BREAK_PENALTY, OFFER_COOLDOWN
from .fleet_views import FLEETS_PER_PAGE, QUEUE_PER_PAGE, draw_fleets, draw_shipyard
from .fleets import fleet_containing
from .galaxy_fleet_view import FLEET_SHIPS_PER_PAGE, draw_fleet, draw_fleet_popup, draw_map_fleets, draw_order_panel
from .exploration import known_rival_colonies
from .exploration_view import FINDS_PER_PAGE, draw_exploration, draw_system_intelligence
from .ui import (Button, CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED, RIVAL_COLOR,
                 arrow, emblem, font, panel, paragraph, shorten, text, text_image)

STAR_COLORS={"Yellow dwarf":(230,207,141), "Blue star":(113,181,231),
             "Red dwarf":(221,124,108), "White star":(217,228,239), "Orange dwarf":(235,170,106)}
MAP=pg.Rect(64,180,962,573)
GAME_SCREENS=("galaxy", "system", "planet", "production", "colony", "empire", "shipyard", "fleets", "fleet", "rival", "diplomacy", "research", "combat", "objectives", "result", "exploration")


class App:
    def __init__(self,data_dir: Path | None=None,capture=False,skip_intro=False):
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
        self.brand=StudioBrand()
        self.clock=pg.time.Clock()
        self.running=True
        self.screen="menu" if capture or skip_intro else "splash"
        self.game=None
        self.buttons=[]
        self.focus=None
        self.keyboard_mode=False
        self.mouse=(-1,-1)
        self.pressed=None
        self.time=0.0
        self.splash_started=0.0
        self.dialog=None
        self.notice=""
        self.notice_until=0.0
        self.notice_error=False
        self.empire="Terran Union"
        self.seed=""
        self.size="Standard"
        self.race_id="terran"
        self.rival_race_id="kharuun"
        self.fog_of_war=True
        self.field=None
        self.select_all=False
        self.settings_return="menu"
        self.pause_return="galaxy"
        self.campaign_view="galaxy"
        self.colony_slot=None
        self.worker_source=None
        self.production_page=0
        self.reset_empire_view()
        self.reset_fleet_view()
        self.reset_combat_view()
        self.load_rows=[]
        self.load_page=0
        self.audio=Audio(enabled=not capture)
        self.audio.apply_music(self.settings["music"],self.settings["music_volume"])
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
        if self.game and self.game.result is not None and screen in GAME_SCREENS:
            screen="result"
        elif self.game and self.game.combat is not None and screen in GAME_SCREENS:
            screen="combat"
        elif screen in ("combat","result"):
            screen="galaxy"
        if screen in ("planet","colony","shipyard","production") and self.game.selected_planet is None:
            screen="system"
        if screen in ("planet","colony","shipyard","production") and not self.game.system_explored(self.game.selected_system):
            screen="system"
        if screen in ("colony","shipyard","production") and not self.game.system_visible(self.game.selected_system):
            screen="planet"
        if screen=="production" and self.game.planet_at(self.game.selected_system,self.game.selected_planet).owner!=PLAYER:
            screen="planet"
        if screen not in ("galaxy","pause","settings"):
            self.route_ship_id=None
            self.map_order_ids=()
            self.fleet_popup=False
        self.screen=screen
        self.worker_source=None
        self.buttons=[]
        self.focus=None
        self.pressed=None
        self.field=None
        self.select_all=False
        pg.key.stop_text_input()
        if screen in GAME_SCREENS:
            self.campaign_view=screen
        if screen=="galaxy":
            self.focus=f"star_{self.game.selected_system}"
        if screen=="colony":
            self.focus="build_factory"
        if screen=="shipyard":
            self.focus="build_colony_ship"
        if screen=="fleets":
            self.change_fleet_page(0)
        if screen=="fleet":
            self.change_manifest_page(0)
        if screen=="exploration":
            self.focus="exploration_back"
        if screen=="empire":
            self.focus_empire_row()
        if screen=="rival":
            self.focus="rival_back" if self.game.opponent else "add_rival"
        if screen=="diplomacy":
            self.focus="diplomacy_back"
        if screen=="research":
            self.focus=f"research_branch_{self.research_branch}"
        if screen=="objectives":
            self.focus="objectives_back"
        if screen=="result":
            self.focus="result_menu"
        if screen=="combat":
            self.sync_combat_selection()
            self.combat_ai_due=self.time+.8
            self.combat_last_update=self.time
            self.focus="combat_continue" if self.game.combat.status!="active" else "combat_end_turn"
        if screen=="system":
            known=self.game.known_system(self.game.selected_system)
            worlds=known.worlds if known else []
            self.focus="system_back"
            if worlds:
                first=next((p.id for p in worlds if p.colonized),0)
                chosen=self.game.selected_planet if self.game.selected_planet is not None else first
                self.focus=f"world_{chosen}"
        if screen=="load":
            self.load_rows=self.storage.list_saves()
            self.load_page=0
        if screen=="splash":
            self.splash_started=self.time

    def update_splash(self):
        if (self.screen=="splash" and not self.dialog
                and self.time-self.splash_started>=SPLASH_SECONDS):
            self.go("menu")

    def open_system(self,system_id):
        if self.game is None or not 0 <= system_id < len(self.game.systems):
            return
        if self.game.selected_system != system_id:
            self.game.selected_planet=None
        self.game.selected_system=system_id
        self.go("system")

    def open_planet(self,planet_id):
        if not self.game.system_explored(self.game.selected_system):
            self.go("system")
            return
        worlds=self.game.systems[self.game.selected_system].worlds
        if not 0 <= planet_id < len(worlds):
            return
        self.game.selected_planet=planet_id
        self.colony_slot=None
        self.shipyard_page=0
        self.go("planet")

    def reset_fleet_view(self):
        self.fleet_return="galaxy"
        self.fleet_return_selection=(0,None)
        self.fleet_page=0
        self.shipyard_page=0
        self.route_ship_id=None
        self.fleet_anchor_id=None
        self.fleet_selected_ids=set()
        self.manifest_page=0
        self.map_order_ids=()
        self.fleet_popup=False
        self.fleet_popup_rect=None
        self.exploration_return="galaxy"
        self.exploration_return_selection=(0,None)
        self.exploration_page=0

    def viewed_fleet(self):
        return fleet_containing(self.game.visible_ships(),self.fleet_anchor_id)

    def sync_fleet_selection(self):
        ships=self.viewed_fleet()
        eligible={s.id for s in ships if s.owner==PLAYER and not s.in_transit}
        self.fleet_selected_ids.intersection_update(eligible)
        last=max(0,(len(ships)-1)//FLEET_SHIPS_PER_PAGE)
        self.manifest_page=min(self.manifest_page,last)
        return ships

    def open_map_fleet(self,ship_id):
        ships=fleet_containing(self.game.visible_ships(),ship_id)
        if not ships:
            self.toast("That fleet is no longer available.",True)
            return
        self.fleet_anchor_id=ship_id
        self.fleet_selected_ids={s.id for s in ships if s.owner==PLAYER and not s.in_transit}
        self.manifest_page=0
        self.game.selected_system=ships[0].system_id
        self.game.selected_planet=None
        self.route_ship_id=None
        self.go("galaxy")
        self.fleet_popup=True
        self.map_order_ids=tuple(sorted(self.fleet_selected_ids))
        self.focus=f"fleet_select_{ships[0].id}" if self.fleet_selected_ids else "fleet_popup_close"

    def close_fleet_popup(self):
        # Closing a selector does not revoke a course that was already issued.
        self.fleet_popup=False
        self.fleet_popup_rect=None
        self.map_order_ids=()
        self.fleet_selected_ids.clear()
        self.focus=f"star_{self.game.selected_system}" if self.game else None

    def toggle_fleet_ship(self,ship_id):
        ships=self.sync_fleet_selection()
        if not any(s.id==ship_id and s.owner==PLAYER and not s.in_transit for s in ships):
            return
        if ship_id in self.fleet_selected_ids:
            self.fleet_selected_ids.remove(ship_id)
        else:
            self.fleet_selected_ids.add(ship_id)
        if self.fleet_popup:
            self.map_order_ids=tuple(sorted(self.fleet_selected_ids))
        self.focus=f"fleet_select_{ship_id}"

    def select_fleet_ships(self,all_ships=True):
        ships=self.sync_fleet_selection()
        self.fleet_selected_ids=({s.id for s in ships if s.owner==PLAYER and not s.in_transit}
                                 if all_ships else set())
        if self.fleet_popup:
            self.map_order_ids=tuple(sorted(self.fleet_selected_ids))

    def change_manifest_page(self,delta):
        ships=self.sync_fleet_selection()
        last=max(0,(len(ships)-1)//FLEET_SHIPS_PER_PAGE)
        self.manifest_page=min(max(0,self.manifest_page+delta),last)
        visible=ships[self.manifest_page*FLEET_SHIPS_PER_PAGE:]
        self.focus=f"fleet_select_{visible[0].id}" if visible and visible[0].owner==PLAYER and not visible[0].in_transit else "fleet_popup_close" if self.fleet_popup else "fleet_back"

    def plot_fleet_course(self):
        ships=self.sync_fleet_selection()
        if not ships or not self.fleet_selected_ids:
            self.toast("Select at least one ship to send.",True)
            return
        if self.game.strategy_error():
            self.toast(self.game.strategy_error(),True)
            return
        self.route_ship_id=None
        self.map_order_ids=tuple(sorted(self.fleet_selected_ids))
        self.game.selected_system=ships[0].system_id
        self.game.selected_planet=None
        self.go("galaxy")
        self.fleet_popup=True
        self.keyboard_mode=False
        self.mouse=(-1,-1)

    def cancel_map_order(self):
        self.close_fleet_popup()

    def fleet_route_target(self):
        if not self.keyboard_mode:
            # Match the click handler's topmost-first hit testing in dense clusters.
            for system in reversed(self.game.systems):
                x,y=self.star_pos(system)
                if pg.Rect(int(x)-18,int(y)-18,36,36).collidepoint(self.mouse):
                    return system.id
        return self.game.selected_system

    def send_map_fleet(self,destination):
        try:
            identifiers=self.map_order_ids
            count=len(identifiers)
            first=self.game.ship_at(identifiers[0])
            origin=first.system_id
            if destination==origin:
                if not first.departure_pending:
                    self.toast("These ships are already here. Click another star to set a course.")
                    return
                self.game.cancel_departures(identifiers)
                message=f"Departure cancelled · {count} {'ship remains' if count==1 else 'ships remain'} at {self.game.systems[origin].name}."
            else:
                duration=self.game.send_ships(identifiers,destination)
                message=f"Course set to {self.game.systems[destination].name} · {turn_label(duration)} · Click {self.game.systems[origin].name} to cancel before End Turn."
            self.fleet_anchor_id=identifiers[0]
            self.fleet_selected_ids=set(identifiers)
            self.manifest_page=0
            self.game.selected_system=destination
            self.game.selected_planet=None
            self.fleet_popup=True
            if self.save_game(autosave=True):
                self.toast(message)
        except RuleError as exc:
            self.toast(exc,True)

    def open_fleets(self):
        if self.screen=="fleets":
            self.close_fleets()
        elif self.screen in GAME_SCREENS:
            self.fleet_return=self.screen
            self.fleet_return_selection=(self.game.selected_system,self.game.selected_planet)
            self.go("fleets")

    def close_fleets(self):
        self.game.selected_system,self.game.selected_planet=self.fleet_return_selection
        self.go(self.fleet_return)

    def open_shipyard(self,system_id,planet_id):
        self.game.planet_at(system_id,planet_id)
        self.game.selected_system=system_id
        self.game.selected_planet=planet_id
        self.shipyard_page=0
        self.go("shipyard")

    def change_fleet_page(self,delta):
        ships=self.game.ships_owned_by()
        last=max(0,(len(ships)-1)//FLEETS_PER_PAGE)
        self.fleet_page=min(max(0,self.fleet_page+delta),last)
        visible=ships[self.fleet_page*FLEETS_PER_PAGE:(self.fleet_page+1)*FLEETS_PER_PAGE]
        if visible:
            ship=visible[0]
            self.focus=f"ship_view_{ship.id}" if ship.in_transit else f"ship_send_{ship.id}"
        else:
            self.focus="fleet_build_first"

    def change_shipyard_page(self,delta):
        planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
        last=max(0,(len(planet.construction_queue)-1)//QUEUE_PER_PAGE)
        self.shipyard_page=min(max(0,self.shipyard_page+delta),last)

    def plot_course(self,ship_id):
        try:
            ship=self.game.ship_at(ship_id)
            if ship.in_transit:
                raise RuleError("Wait for this ship to arrive before assigning a new course.")
            self.route_ship_id=ship_id
            self.map_order_ids=()
            self.game.selected_system=ship.system_id
            self.game.selected_planet=None
            self.go("galaxy")
        except RuleError as exc:
            self.toast(exc,True)

    def select_star(self,system_id):
        if self.map_order_ids:
            self.send_map_fleet(system_id)
        elif self.fleet_popup:
            ships=self.viewed_fleet()
            if ships and ships[0].owner==PLAYER and not ships[0].in_transit:
                self.toast("Select at least one ship, or close the popup to open a system.")
            else:
                self.close_fleet_popup()
                self.open_system(system_id)
        elif self.route_ship_id is None:
            self.open_system(system_id)
        else:
            self.game.selected_system=system_id
            self.game.selected_planet=None
            self.focus="send_course"

    def send_course(self):
        try:
            ship=self.game.ship_at(self.route_ship_id)
            destination=self.game.selected_system
            duration=self.game.send_ship(ship.id,destination)
            self.go("fleets")
            if self.save_game(autosave=True):
                self.toast(f"{ship.name} en route to {self.game.systems[destination].name} · {turn_label(duration)}")
        except RuleError as exc:
            self.toast(exc,True)

    def queue_colony_ship(self):
        self.queue_ship("colony_ship")

    def queue_ship(self,kind):
        try:
            self.game.queue_ship(self.game.selected_system,self.game.selected_planet,kind)
            planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
            self.shipyard_page=(len(planet.construction_queue)-1)//QUEUE_PER_PAGE
            if self.save_game(autosave=True):
                self.toast(f"{SHIP_TYPES[kind].name} queued · {planet.construction_queue[-1].paid_credits} CR paid")
        except RuleError as exc:
            self.toast(exc,True)

    def colonize_request(self):
        system_id,planet_id=self.game.selected_system,self.game.selected_planet
        error=self.game.colonize_error(system_id,planet_id)
        if error:
            self.toast(error,True)
            return
        ship=self.game.colony_ships_at(system_id)[0]
        planet=self.game.planet_at(system_id,planet_id)
        def settle():
            try:
                self.game.colonize(ship.id,system_id,planet_id)
                self.colony_slot=None
                self.go("planet")
                if self.save_game(autosave=True):
                    self.toast(f"Colony established on {planet.name} · {planet.population} B inhabitants · Welcome to your empire")
            except RuleError as exc:
                self.toast(exc,True)
        self.confirm(f"Settle {shorten(planet.name,370,29,'title')}?",
                     f"Use {ship.name} to found a colony with {self.game.starting_colonists()} B inhabitants. The ship is consumed; the new colony can construct buildings and ships.",
                     "Establish colony",settle)

    def reset_empire_view(self):
        self.empire_return="galaxy"
        self.empire_filter="all"
        self.empire_sort="name"
        self.empire_descending=False
        self.empire_page=0
        self.rival_page=0
        self.rival_return="empire"
        self.diplomacy_return="galaxy"
        self.diplomacy_return_selection=(0,None)
        self.research_return="galaxy"
        self.research_return_selection=(0,None)
        self.research_branch="construction"
        self.objectives_return="galaxy"
        self.gate_colony_index=0

    def open_objectives(self):
        if self.screen=="objectives":
            self.close_objectives()
        elif self.screen in GAME_SCREENS:
            self.objectives_return=self.screen
            self.go("objectives")

    def close_objectives(self):
        self.go(self.objectives_return)

    def change_gate_colony(self,delta):
        self.gate_colony_index=min(max(0,self.gate_colony_index+delta),max(0,len(colonies(self.game,PLAYER))-1))

    def gate_request(self,system_id,planet_id):
        error=self.game.gate_error(system_id,planet_id)
        if error:
            self.toast(error,True)
            return
        planet=self.game.planet_at(system_id,planet_id)
        def build():
            try:
                self.game.queue_gate(system_id,planet_id)
                if self.save_game(autosave=True):
                    self.toast(f"Ascension Gate queued on {planet.name}. Protect it until activation.")
            except RuleError as exc:
                self.toast(exc,True)
        self.confirm("Build the Ascension Gate?",
                     f"Pay 500 CR to queue 300 work on {planet.name}. Then charge for five turns with no opposing ships in orbit. "
                     "Capturing this colony destroys the gate.","Build gate",build)

    def invade_request(self):
        system_id,planet_id=self.game.selected_system,self.game.selected_planet
        error=self.game.invasion_error(system_id,planet_id)
        if error:
            self.toast(error,True)
            return
        planet=self.game.planet_at(system_id,planet_id)
        attack,defence=invasion_strength(self.game,system_id,planet_id)
        count=len(troop_transports(self.game,system_id))
        def invade():
            try:
                report=self.game.invade(system_id,planet_id)
                self.colony_slot=None
                self.go("result" if self.game.result else "planet")
                if self.save_game(autosave=True):
                    self.toast(f"{'Captured' if report.captured else 'Invasion failed at'} {planet.name} · {count} transports consumed",not report.captured)
            except RuleError as exc:
                self.toast(exc,True)
        outcome="Capture predicted." if attack>defence else "Defeat predicted; bring more transports."
        self.confirm("Invade this colony?",
                     f"{attack} attack vs {defence} defence. {outcome} All {count} transports are consumed. "
                     "Invasion ends treaties and sets relations to -100. Capture destroys any Ascension Gate.",
                     "Invade colony",invade)

    def open_research(self):
        if self.screen=="research":
            self.close_research()
        elif self.screen in GAME_SCREENS:
            self.research_return=self.screen
            self.research_return_selection=(self.game.selected_system,self.game.selected_planet)
            if self.game.technology.active:
                branch=TECHNOLOGIES[self.game.technology.active].branch
                if branch in BRANCHES:
                    self.research_branch=branch
            self.go("research")

    def close_research(self):
        self.game.selected_system,self.game.selected_planet=self.research_return_selection
        self.go(self.research_return)

    def select_research_branch(self,identifier):
        self.research_branch=identifier
        self.focus=f"research_branch_{identifier}"

    def research_request(self,identifier):
        error=self.game.research_error(identifier)
        if error:
            self.toast(error,True)
            return
        technology=TECHNOLOGIES[identifier]
        alternative=next((t for t in choices(technology.branch,technology.tier) if t.id!=identifier),None)
        def choose():
            try:
                discovered=self.game.choose_research(identifier)
                if self.save_game(autosave=True):
                    self.toast(f"Discovered {discovered.name}." if discovered else f"Research started: {technology.name}.")
            except RuleError as exc:
                self.toast(exc,True)
        body=(f"Research {technology.name} for {technology.cost} RP. {alternative.name} becomes unavailable. "
              "This choice is permanent; banked points are applied immediately." if alternative else
              "Research Ascension Theory for 500 RP to unlock the Ascension Gate. Banked points are applied immediately; "
              "your normal research output supplies the rest.")
        self.confirm("Commit to this technology?",body,"Start research",choose)

    def focus_empire_row(self):
        rows=colony_rows(self.game,self.empire_filter,self.empire_sort,self.empire_descending)
        self.empire_page=min(max(0,self.empire_page),max(0,(len(rows)-1)//COLONIES_PER_PAGE))
        if rows:
            system,planet=rows[self.empire_page*COLONIES_PER_PAGE]
            self.focus=f"empire_colony_{system.id}_{planet.id}"
        else:
            self.focus="empire_filter_all"

    def open_empire(self):
        if self.screen=="empire":
            self.close_empire()
        elif self.screen=="rival":
            self.go("empire")
        elif self.screen in GAME_SCREENS:
            self.empire_return=self.screen
            self.go("empire")

    def close_empire(self):
        self.go(self.empire_return)

    def open_empire_colony(self,system_id,planet_id):
        self.game.planet_at(system_id,planet_id)
        self.game.selected_system=system_id
        self.game.selected_planet=planet_id
        self.colony_slot=None
        self.go("planet")

    def set_empire_filter(self,filter_by):
        if filter_by not in FILTERS:
            return
        self.empire_filter=filter_by
        self.empire_page=0
        self.focus_empire_row()

    def sort_empire(self,key):
        if key not in SORT_KEYS:
            return
        self.empire_descending=not self.empire_descending if key==self.empire_sort else key!="name"
        self.empire_sort=key
        self.empire_page=0
        self.focus_empire_row()

    def change_empire_page(self,delta):
        self.empire_page+=delta
        self.focus_empire_row()

    def change_rival_page(self,delta):
        last=max(0,(len(known_rival_colonies(self.game))-1)//5)
        self.rival_page=min(max(0,self.rival_page+delta),last)

    def open_rival(self):
        self.rival_return=self.screen if self.screen in ("diplomacy","planet") else "empire"
        self.go("rival")

    def open_diplomacy(self):
        if self.screen=="diplomacy":
            self.close_diplomacy()
        elif self.screen in GAME_SCREENS:
            self.diplomacy_return=self.screen
            self.diplomacy_return_selection=(self.game.selected_system,self.game.selected_planet)
            self.go("diplomacy")

    def close_diplomacy(self):
        self.game.selected_system,self.game.selected_planet=self.diplomacy_return_selection
        self.go(self.diplomacy_return)

    def diplomatic_action(self,action):
        def perform():
            try:
                response=self.game.diplomacy_action(action)
                if self.save_game(autosave=True):
                    self.toast(response)
                    self.notice_until=self.time+7
            except RuleError as exc:
                self.toast(exc,True)
        if action in ("end_trade","end_research"):
            title="trade pact" if action=="end_trade" else "research agreement"
            self.confirm(f"End the {title}?",
                         f"Its benefits stop immediately for both empires. Relations fall by {BREAK_PENALTY} and new treaty offers wait {OFFER_COOLDOWN} turns. "
                         "If relations fall below zero, the rival ends other agreements on the next End Turn.",
                         "End agreement",perform)
        else:
            perform()

    def add_rival(self):
        try:
            planet=self.game.add_opponent()
            if self.save_game(autosave=True):
                location="Explore to locate its worlds" if self.game.fog_of_war else f"Established on {planet.name}"
                self.toast(f"Helios Directorate · {location} · Autosaved")
        except RuleError as exc:
            self.toast(exc,True)

    def survey_rival_colony(self,system_id,planet_id):
        self.open_system(system_id)
        self.open_planet(planet_id)

    def cycle_system(self,delta):
        self.game.selected_system=(self.game.selected_system+delta)%len(self.game.systems)
        self.game.selected_planet=None
        if self.screen=="system":
            self.go("system")
        else:
            self.focus=f"star_{self.game.selected_system}"
            self.keyboard_mode=True

    def cycle_planet(self,delta):
        known=self.game.known_system(self.game.selected_system)
        worlds=known.worlds if known else []
        if not worlds:
            return
        current=self.game.selected_planet
        if current is None:
            current=-1 if delta>0 else 0
        self.game.selected_planet=(current+delta)%len(worlds)
        self.colony_slot=None
        self.shipyard_page=0
        if self.screen in ("planet","colony","shipyard"):
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
        self.audio.play_click(self.settings["sound"])

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
        if key=="music":
            self.audio.apply_music(self.settings["music"],self.settings["music_volume"])
        self.save_preferences()

    def change_music_volume(self,delta):
        self.settings["music_volume"]=max(0,min(100,self.settings["music_volume"]+delta))
        self.audio.apply_music(self.settings["music"],self.settings["music_volume"])
        self.save_preferences()

    def save_preferences(self):
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
            self.game=new_game(self.empire,self.size,int(self.seed) if self.seed else None,
                               race_id=self.race_id,rival_race_id=self.rival_race_id,fog_of_war=self.fog_of_war)
        except (ValueError,SaveError) as exc:
            self.toast(str(exc),True)
            return
        self.colony_slot=None
        self.reset_empire_view()
        self.reset_fleet_view()
        self.reset_combat_view()
        self.go("galaxy")
        self.save_game(autosave=True)

    def toggle_fog_of_war(self):
        self.fog_of_war=not self.fog_of_war

    def open_exploration(self):
        if self.screen=="exploration":
            self.close_exploration()
        elif self.screen in GAME_SCREENS:
            self.exploration_return=self.screen
            self.exploration_return_selection=(self.game.selected_system,self.game.selected_planet)
            self.go("exploration")

    def close_exploration(self):
        self.game.selected_system,self.game.selected_planet=self.exploration_return_selection
        self.go(self.exploration_return)

    def change_exploration_page(self,delta):
        count=sum(d.owner==PLAYER for d in self.game.exploration.discoveries)
        last=max(0,(count-1)//FINDS_PER_PAGE)
        self.exploration_page=min(max(0,self.exploration_page+delta),last)

    def open_scout_shipyard(self):
        home=self.game.headquarters()
        if home:
            self.open_shipyard(home[0].id,home[1].id)
            self.focus="build_scout"
            self.keyboard_mode=True

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
        self.reset_empire_view()
        self.reset_fleet_view()
        self.reset_combat_view()
        self.go("galaxy")
        self.toast(f"Welcome back, {state.empire_name}.")

    def advance_turn(self):
        if self.game.result is not None:
            self.go("result")
            return
        if self.game.combat is not None:
            self.go("combat")
            self.toast("Resolve the battle before advancing the campaign.",True)
            return
        # An unissued map order is a UI selection, never an automatic next-turn order.
        self.close_fleet_popup()
        report=self.game.advance_turn()
        if self.game.result is not None:
            self.go("result")
        elif self.game.combat is not None:
            self.reset_combat_view()
            self.go("combat")
        if self.screen=="empire":
            self.focus_empire_row()
        if self.save_game(autosave=True):
            message=f"Turn {self.game.turn} · +{report.income} CR · +{report.research} RP"
            if self.game.combat is not None:
                message+=" · Enemy fleet engaged at "+self.game.systems[self.game.combat.system_id].name
            if report.discoveries:
                message+=" · Discovered: "+", ".join(report.discoveries)
            if report.completed:
                message+=" · Completed: "+", ".join(report.completed)
            if report.arrivals:
                message+=" · Arrived: "+", ".join(report.arrivals)
            if report.alerts:
                message=" · ".join(report.alerts)+" · "+message
            if report.exploration:
                message=" · ".join(report.exploration)+" · Exploration log: X · "+message
            if report.population:
                message=" · ".join(report.population)+" · "+message
            self.toast(message+" · Autosaved")
            if report.completed or report.arrivals or report.discoveries or report.alerts or report.exploration or report.population:
                self.notice_until=self.time+7

    def reset_combat_view(self):
        self.combat_ship_id=None
        self.combat_target_id=None
        self.combat_camera_row=0
        self.combat_animation=None
        self.combat_last_update=self.time
        self.combat_ai_due=self.time+.8

    def sync_combat_selection(self):
        battle=self.game.combat
        if battle is None:
            return
        ready=battle.ready(PLAYER) if battle.status=="active" else []
        targets=battle.fleet(RIVAL)
        if not any(s.id==self.combat_ship_id for s in ready):
            self.combat_ship_id=ready[0].id if ready else None
        if not any(s.id==self.combat_target_id for s in targets):
            self.combat_target_id=targets[0].id if targets else None
        if battle.active_owner==PLAYER and self.combat_ship_id is not None:
            self.reveal_combat_row(battle.ship(self.combat_ship_id).y)

    def combat_input_ready(self):
        return (self.screen=="combat" and not self.dialog and self.game is not None
                and self.game.combat is not None and self.game.combat.status=="active"
                and self.game.combat.active_owner==PLAYER and self.combat_animation is None)

    def pan_combat(self,delta):
        last=max(0,self.game.combat.rows-VISIBLE_ROWS)
        self.combat_camera_row=min(last,max(0,self.combat_camera_row+delta))

    def reveal_combat_row(self,row):
        if not self.combat_camera_row<=row<self.combat_camera_row+VISIBLE_ROWS:
            last=max(0,self.game.combat.rows-VISIBLE_ROWS)
            self.combat_camera_row=min(last,max(0,row-VISIBLE_ROWS//2))

    def next_combat_ship(self):
        if not self.combat_input_ready():
            return
        ready=self.game.combat.ready(PLAYER)
        if ready:
            identifiers=[s.id for s in ready]
            index=identifiers.index(self.combat_ship_id) if self.combat_ship_id in identifiers else -1
            self.combat_ship_id=identifiers[(index+1)%len(identifiers)]
            self.reveal_combat_row(self.game.combat.ship(self.combat_ship_id).y)

    def engage_request(self,system_id):
        error=self.game.engagement_error(system_id)
        if error:
            self.toast(error,True)
            return
        own=len(self.game.fleet_at(system_id))
        rival=len(self.game.fleet_at(system_id,RIVAL))
        def engage():
            try:
                self.game.start_combat(system_id)
                self.reset_combat_view()
                self.go("combat")
                self.save_game(autosave=True)
            except RuleError as exc:
                self.toast(exc,True)
        self.confirm("Engage the opposing fleet?",
                     f"Commit your {own} ships against {rival} rival ships at {self.game.systems[system_id].name}. "
                     "Combat ends trade and research agreements and sets relations to -100. Ship losses are permanent.",
                     "Engage fleet",engage)

    def select_combat_ship(self,owner,ship_id):
        if not self.combat_input_ready():
            return
        ship=self.game.combat.ship(ship_id)
        if ship is None or ship.hull<=0 or ship.owner!=owner:
            return
        if owner==PLAYER:
            self.combat_ship_id=ship_id
        else:
            self.combat_target_id=ship_id
            self.combat_action("fire")

    def after_combat_action(self,event):
        self.combat_animation=CombatAnimation.from_action(self.game.combat,event)
        self.combat_last_update=self.time
        if self.combat_animation:
            rows=[point[1] for point in self.combat_animation.path]
            if min(rows)<self.combat_camera_row or max(rows)>=self.combat_camera_row+VISIBLE_ROWS:
                last=max(0,self.game.combat.rows-VISIBLE_ROWS)
                self.combat_camera_row=min(last,max(0,(min(rows)+max(rows))//2-VISIBLE_ROWS//2))
        else:
            self.sync_combat_selection()
        self.combat_ai_due=self.time+.4
        self.save_game(autosave=True)
        self.focus="combat_end_turn"

    def move_combat_ship(self,x,y):
        if not self.combat_input_ready():
            return
        try:
            path=self.game.combat_move(self.combat_ship_id,x,y)
            self.after_combat_action({"kind":"move","ship_id":self.combat_ship_id,"path":path})
        except RuleError as exc:
            self.toast(exc,True)

    def combat_action(self,action):
        if not self.combat_input_ready():
            return
        try:
            event={"kind":action}
            if action=="fire":
                damage=self.game.combat_fire(self.combat_ship_id,self.combat_target_id)
                event.update(ship_id=self.combat_ship_id,target_id=self.combat_target_id,damage=damage)
            elif action=="hold":
                self.game.combat_hold(self.combat_ship_id)
            elif action=="retreat":
                self.game.combat_retreat()
            elif action=="end_turn":
                self.game.combat_end_turn()
            else:
                return
            self.after_combat_action(event)
        except RuleError as exc:
            self.toast(exc,True)

    def retreat_request(self):
        if not self.combat_input_ready():
            return
        destination=retreat_destination(self.game)
        if destination is None:
            self.toast("No safe retreat destination is available.",True)
            return
        duration=self.game.travel_turns(self.game.systems[self.game.combat.system_id],destination)
        self.confirm("Withdraw the whole fleet?",
                     f"All surviving ships will retreat to {destination.name}, arriving in {turn_label(duration)}. "
                     "Damage is retained and the opposing fleet holds this system's orbit.",
                     "Retreat fleet",lambda:self.combat_action("retreat"))

    def update_combat(self):
        delta=max(0,self.time-self.combat_last_update)
        self.combat_last_update=self.time
        if self.screen!="combat" or self.dialog or self.game is None or self.game.combat is None:
            return
        if self.combat_animation:
            self.combat_animation.elapsed+=delta
            if self.combat_animation.finished:
                self.combat_animation=None
                self.sync_combat_selection()
                self.combat_ai_due=self.time+.35
                self.focus="combat_continue" if self.game.combat.status!="active" else "combat_end_turn"
            return
        if (self.game.combat.status=="active" and self.game.combat.active_owner==RIVAL
                and self.time>=self.combat_ai_due):
            self.after_combat_action(self.game.combat_ai_action())

    def finish_combat(self):
        if self.combat_animation:
            return
        try:
            system_id=self.game.finish_combat()
            self.reset_combat_view()
            self.open_system(system_id)
            self.save_game(autosave=True)
        except RuleError as exc:
            self.toast(exc,True)

    def select_colony_slot(self,index):
        self.colony_slot=index

    def select_worker_role(self,role):
        planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
        if planet.owner!=PLAYER or self.game.strategy_error():
            return
        if self.worker_source==role:
            self.worker_source=None
        elif self.worker_source is None:
            if getattr(planet,role)>0:
                self.worker_source=role
        else:
            try:
                self.game.move_worker(self.game.selected_system,self.game.selected_planet,self.worker_source,role)
                self.worker_source=None
                self.save_game(autosave=True)
            except RuleError as exc:
                self.worker_source=None
                self.toast(exc,True)

    def open_production(self):
        self.production_page=0
        self.go("production")

    def change_production_page(self,delta):
        planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
        self.production_page=max(0,min(max(0,(len(planet.construction_queue)-1)//6),self.production_page+delta))

    def choose_production(self,item_id):
        try:
            self.game.change_production(self.game.selected_system,self.game.selected_planet,item_id)
            self.go("planet")
            if self.save_game(autosave=True):
                self.toast(f"Now building {PROJECTS[item_id].name} · Previous projects remain queued")
        except RuleError as exc:
            self.toast(exc,True)

    def prioritize_production(self,index):
        try:
            self.game.prioritize_construction(self.game.selected_system,self.game.selected_planet,index)
            self.go("planet")
            self.save_game(autosave=True)
        except RuleError as exc:
            self.toast(exc,True)

    def buy_production_request(self):
        sid,pid=self.game.selected_system,self.game.selected_planet
        error=self.game.buy_construction_error(sid,pid)
        if error:
            self.toast(error,True)
            return
        project=self.game.planet_at(sid,pid).construction_queue[0]
        name=PROJECTS[project.item_id].name
        price=self.game.buy_construction_cost(sid,pid)
        def buy():
            try:
                queue=self.game.planet_at(sid,pid).construction_queue
                if not queue or queue[0] is not project:
                    raise RuleError("The current project changed. Please review its new price.")
                self.game.buy_construction(sid,pid)
                if self.save_game(autosave=True):
                    self.toast(f"{name} completed · {price} CR paid")
            except RuleError as exc:
                self.toast(exc,True)
        self.confirm("Buy current production?",f"Finish {name} immediately for {price} credits (2 CR per remaining work). "
                     "This is additional to the price already paid. Other queued projects are kept.","Buy",buy)

    def inspect_surface_building(self,index):
        self.colony_slot=index
        self.go("colony")
        self.focus=f"colony_slot_{index}"

    def queue_building(self,building_id):
        try:
            self.game.queue_building(self.game.selected_system,self.game.selected_planet,building_id)
            planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
            self.colony_slot=planet.used_slots-1
            if self.save_game(autosave=True):
                self.toast(f"{BUILDINGS[building_id].name} queued · {planet.construction_queue[-1].paid_credits} CR paid")
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
        self.audio.close()
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
        if self.screen=="splash" and not self.dialog:
            if event.type==pg.KEYDOWN:
                if event.key==pg.K_F11:
                    self.toggle_setting("fullscreen")
                self.go("menu")
                return
            if event.type==pg.MOUSEBUTTONDOWN and event.button==1:
                self.go("menu")
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
                    if self.screen=="galaxy" and self.fleet_popup and not self.dialog:
                        self.close_fleet_popup()
                    self.field=None
                    pg.key.stop_text_input()
            elif hovered and hovered.key==self.pressed:
                self.pressed=None
                self.activate(hovered)
        if event.type==pg.MOUSEWHEEL and self.screen=="load" and not self.dialog:
            self.change_load_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="empire" and not self.dialog and event.y:
            self.change_empire_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen in ("fleets","shipyard") and not self.dialog and event.y:
            change=self.change_fleet_page if self.screen=="fleets" else self.change_shipyard_page
            change(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="fleet" and not self.dialog and event.y:
            self.change_manifest_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="galaxy" and self.fleet_popup and not self.dialog and event.y:
            self.change_manifest_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="exploration" and not self.dialog and event.y:
            self.change_exploration_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="combat" and not self.dialog and event.y:
            self.pan_combat(-event.y*2)
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
                if self.fleet_popup or self.map_order_ids:
                    self.cancel_map_order()
                else:
                    self.go("fleets") if self.route_ship_id is not None else self.pause()
            elif self.screen=="fleet":
                self.go("galaxy")
            elif self.screen=="exploration":
                self.close_exploration()
            elif self.screen=="system":
                self.go("galaxy")
            elif self.screen=="planet":
                if self.worker_source:
                    self.worker_source=None
                else:
                    self.go("system")
            elif self.screen in ("colony","shipyard","production"):
                self.go("planet")
            elif self.screen=="fleets":
                self.close_fleets()
            elif self.screen=="empire":
                self.close_empire()
            elif self.screen=="rival":
                self.go(self.rival_return)
            elif self.screen=="diplomacy":
                self.close_diplomacy()
            elif self.screen=="research":
                self.close_research()
            elif self.screen=="objectives":
                self.close_objectives()
            elif self.screen=="result":
                self.to_menu()
            elif self.screen=="combat":
                self.pause()
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
        elif self.screen in ("combat","result") and not self.dialog:
            if event.key==pg.K_F5:
                self.save_game()
            elif self.screen=="combat":
                if event.key==pg.K_e:
                    self.combat_action("end_turn")
                elif event.key==pg.K_n:
                    self.next_combat_ship()
                elif event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                    self.pan_combat(-3 if event.key==pg.K_PAGEUP else 3)
        elif self.screen in GAME_SCREENS and not self.dialog:
            if event.key==pg.K_F5:
                self.save_game()
            elif event.key==pg.K_e:
                self.advance_turn()
            elif event.key==pg.K_p:
                self.pause()
            elif event.key==pg.K_i:
                self.open_empire()
            elif event.key==pg.K_f:
                self.open_fleets()
            elif event.key==pg.K_d:
                self.open_diplomacy()
            elif event.key==pg.K_r:
                self.open_research()
            elif event.key==pg.K_v:
                self.open_objectives()
            elif event.key==pg.K_x:
                self.open_exploration()
            elif self.screen=="empire" and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_empire_page(1 if event.key==pg.K_PAGEDOWN else -1)
            elif self.screen in ("fleets","shipyard") and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                change=self.change_fleet_page if self.screen=="fleets" else self.change_shipyard_page
                change(1 if event.key==pg.K_PAGEDOWN else -1)
            elif self.screen=="fleet" and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_manifest_page(1 if event.key==pg.K_PAGEDOWN else -1)
            elif self.screen=="galaxy" and self.fleet_popup and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_manifest_page(1 if event.key==pg.K_PAGEDOWN else -1)
            elif self.screen=="exploration" and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_exploration_page(1 if event.key==pg.K_PAGEDOWN else -1)
            elif self.screen=="production" and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_production_page(1 if event.key==pg.K_PAGEDOWN else -1)
            elif event.key in (pg.K_LEFT,pg.K_RIGHT):
                delta=1 if event.key==pg.K_RIGHT else -1
                if self.screen=="galaxy":
                    self.cycle_system(delta)
                elif self.screen=="empire":
                    self.change_empire_page(delta)
                elif self.screen=="fleets":
                    self.change_fleet_page(delta)
                elif self.screen=="fleet":
                    self.change_manifest_page(delta)
                elif self.screen=="exploration":
                    self.change_exploration_page(delta)
                elif self.screen=="rival":
                    self.change_rival_page(delta)
                elif self.screen=="research":
                    branches=tuple(BRANCHES)
                    self.select_research_branch(branches[(branches.index(self.research_branch)+delta)%len(branches)])
                elif self.screen in ("system","planet","colony","shipyard"):
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
        if self.screen in GAME_SCREENS and self.screen not in ("empire","combat","result"):
            self.button("open_empire","Empire · I",(998,39,179,46),self.open_empire)
        if self.screen in GAME_SCREENS and self.screen not in ("fleets","combat","result"):
            self.button("open_fleets","Fleets · F",(807,39,177,46),self.open_fleets)
        if self.screen in GAME_SCREENS and self.screen not in ("diplomacy","combat","result"):
            self.button("open_diplomacy","Diplomacy · D",(590,39,203,46),self.open_diplomacy)
        if self.screen in GAME_SCREENS and self.screen not in ("research","combat","result"):
            self.button("open_research","Research · R",(395,39,181,46),self.open_research)
        if self.screen in GAME_SCREENS and self.screen not in ("combat","result"):
            self.button("open_objectives","Objectives · V",(1191,39,185,46),self.open_objectives)
        else:
            text(self.canvas,f"PROTOTYPE  /  {__version__.rsplit('.',1)[0]}",(1376,58),11,MUTED,"mono",right=True)
        pg.draw.line(self.canvas,LINE,(64,107),(1376,107))
        if back:
            self.button("back","←  Back",(62,126,118,46),back,"ghost")

    def draw_splash(self):
        self.brand.draw_splash(self.canvas,self.time-self.splash_started,self.settings["animated_background"])

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
        self.brand.draw_menu_credit(self.canvas)
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

    def choose_race(self,race_id):
        if self.empire==RACES[self.race_id].default_empire:
            self.empire=RACES[race_id].default_empire
        self.race_id=race_id
        if self.rival_race_id==race_id:
            self.rival_race_id=default_rival_race(race_id)
        self.field=None
        pg.key.stop_text_input()

    def choose_rival_race(self,race_id):
        self.rival_race_id=race_id
        self.field=None
        pg.key.stop_text_input()

    def draw_setup(self):
        draw_setup(self)

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
                 ("sound","Interface sounds","A quiet tone when you activate a control."),
                 ("music","Background music",self.audio.music_description)]
        for i,(key,label,description) in enumerate(options):
            y=322+i*94
            panel(self.canvas,(256,y,928,82))
            text(self.canvas,label,(280,y+12),21,INK)
            text(self.canvas,description,(280,y+47),14,MUTED)
            self.button(key,"ON" if self.settings[key] else "OFF",(1020,y+18,135,46),lambda k=key:self.toggle_setting(k))
            if self.settings[key]:
                pg.draw.circle(self.canvas,CYAN,(1132,y+41),4)
        volume=self.settings["music_volume"]
        muted=not self.settings["music"] or volume==0
        panel(self.canvas,(256,698,928,85))
        text(self.canvas,"Music volume"+(" · Muted" if muted else ""),(280,711),21,INK)
        text(self.canvas,"Use − / + to adjust in 10% steps.",(280,748),14,MUTED)
        self.button("music_quieter","−",(880,714,52,46),lambda:self.change_music_volume(-10),enabled=volume>0)
        label=f"{volume}%"
        text(self.canvas,label,(1018-font(23).size(label)[0]//2,722),23,CYAN)
        self.button("music_louder","+",(1104,714,52,46),lambda:self.change_music_volume(10),enabled=volume<100)
        text(self.canvas,"Music and interface sounds have separate controls.",(256,834),14,MUTED)
        self.button("settings_done","Done",(933,817,251,52),lambda:self.go(self.settings_return),"primary")

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
        preview=self.fleet_route_target() if self.map_order_ids else state.selected_system
        for star in state.systems:
            x,y=self.star_pos(star)
            selected=star.id==preview
            known=state.known_system(star.id)
            color=STAR_COLORS[star.kind] if known else tuple(c//3 for c in STAR_COLORS[star.kind])
            pg.draw.circle(self.canvas,tuple(c//8 for c in color),(int(x),int(y)),14)
            pg.draw.circle(self.canvas,tuple(c//3 for c in color),(int(x),int(y)),8)
            pg.draw.circle(self.canvas,color,(int(x),int(y)),4)
            pg.draw.circle(self.canvas,INK,(int(x),int(y)),1)
            if selected:
                pg.draw.circle(self.canvas,GOLD,(int(x),int(y)),19,1)
                for dx,dy in ((-25,0),(25,0),(0,-25),(0,25)):
                    pg.draw.circle(self.canvas,GOLD,(int(x+dx),int(y+dy)),1)
            owners={p.owner for p in known.worlds if p.colonized} if known else set()
            if PLAYER in owners:
                pg.draw.circle(self.canvas,CYAN,(int(x),int(y)),11,1)
            if RIVAL in owners:
                pg.draw.circle(self.canvas,RIVAL_COLOR,(int(x),int(y)),15 if PLAYER in owners else 11,1)
            text(self.canvas,star.name.upper(),(x+11,y-10),11,INK if selected else MUTED if known else FAINT,"mono")
            self.button(f"star_{star.id}","",(int(x)-18,int(y)-18,36,36),
                        lambda s=star.id:self.select_star(s),"hotspot")
        draw_map_fleets(self,MAP)
        star=state.systems[preview]
        if not self.fleet_popup:
            draw_system_intelligence(self,star)
        if self.map_order_ids:
            if not self.fleet_popup:
                draw_order_panel(self,star)
            hint=f"{len(self.map_order_ids)} {'SHIP' if len(self.map_order_ids)==1 else 'SHIPS'} SELECTED · Click a destination, or the origin to cancel departure."
        elif self.route_ship_id is None:
            if not self.fleet_popup:
                self.button("open_system","Open system →",(1075,692,277,43),
                            lambda:self.open_system(self.game.selected_system))
            hint="Click a fleet to send ships. Dim stars need a visit." if state.fog_of_war else "Click a star to survey it, or a fleet badge to inspect its ships."
        else:
            ship=state.ship_at(self.route_ship_id)
            duration=state.travel_turns(state.systems[ship.system_id],star)
            self.button("send_course",f"Send ship · {turn_label(duration)}" if duration else "Current system",(1075,692,277,43),
                        self.send_course,enabled=duration>0)
            known=state.known_system(star.id)
            targets=sum(not p.colonized and state.can_settle(p) for p in known.worlds) if known else 0
            detail=f"{targets} potential colony worlds in the last survey." if known else "Planets unknown until arrival."
            hint=f"{ship.name}: choose a star, then Send. {detail}"
        text(self.canvas,shorten(hint,748,13),(64,775),13,MUTED)
        self.button("open_exploration","Exploration · X",(828,763,198,38),self.open_exploration)
        text(self.canvas,f"{state.galaxy_size.upper()}   ·   SEED {state.seed}",(1376,778),10,FAINT,"mono",right=True)
        if self.fleet_popup or self.map_order_ids:
            self.button("cancel_fleet_course","Close · Esc",(64,820,186,54),self.cancel_map_order)
        elif self.route_ship_id is None:
            self.button("pause","Menu  ·  Esc",(64,820,186,54),self.pause)
        else:
            self.button("cancel_course","Cancel · Esc",(64,820,186,54),lambda:self.go("fleets"))
        self.button("save","Save game  ·  F5",(264,820,229,54),self.save_game)
        text(self.canvas,"EMPIRE ECONOMY",(585,821),10,GOLD,"mono",2)
        income,research=state.empire_rates
        text(self.canvas,f"+{income} credits · +{research} research / turn",(585,844),12,MUTED)
        self.button("end_turn","End turn  ·  E",(1081,813,295,61),self.advance_turn,"primary")
        if self.fleet_popup:
            draw_fleet_popup(self)

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

    def draw_production(self):
        draw_production(self)

    def draw_colony(self):
        draw_colony(self)

    def draw_empire(self):
        draw_empire(self)

    def draw_rival(self):
        draw_rival(self)

    def draw_diplomacy(self):
        draw_diplomacy(self)

    def draw_research(self):
        draw_research(self)

    def draw_shipyard(self):
        draw_shipyard(self)

    def draw_fleets(self):
        draw_fleets(self)

    def draw_fleet(self):
        draw_fleet(self)

    def draw_exploration(self):
        draw_exploration(self)

    def draw_combat(self):
        draw_combat(self)

    def draw_objectives(self):
        draw_objectives(self)

    def draw_result(self):
        draw_result(self)

    def draw_about(self):
        self.chrome("ABOUT",lambda:self.go("menu"))
        self.heading("A FIRST STEP INTO A LARGER GALAXY","Orion Reach", "An original Python prototype inspired by classic space strategy games.")
        panel(self.canvas,(256,335,928,387))
        text(self.canvas,"WHAT YOU CAN DO",(282,364),11,GOLD,"mono",1)
        paragraph(self.canvas,"Choose a race, build an empire, research technologies, and negotiate with an expanding AI rival. Fight fleet battles and invade colonies, or build the Ascension Gate to win through science.",
                  (282,403),840,20,INK,34)
        text(self.canvas,"WHAT COMES NEXT",(282,513),11,GOLD,"mono",1)
        paragraph(self.canvas,"Food shipments, more empires, shields and advanced weapons. Assign colony workers to farming, industry or science, manage construction, and grow toward each world's population limit.",
                  (282,552),840,18,MUTED,32)
        text(self.canvas,"Original procedural artwork · DejaVu fonts · pygame-ce",(282,673),13,MUTED)
        text(self.canvas,"Music: Distant Stars · alexander_kies · Created with Suno",(282,699),12,MUTED)
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
        if self.game and self.screen in ("planet","colony","shipyard","production"):
            if not self.game.system_explored(self.game.selected_system):
                self.go("system")
            elif self.screen in ("colony","shipyard","production") and not self.game.system_visible(self.game.selected_system):
                self.go("planet")
            elif self.screen=="production" and self.game.planet_at(self.game.selected_system,self.game.selected_planet).owner!=PLAYER:
                self.go("planet")
        self.buttons=[]
        if self.screen!="splash":
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
            self.update_splash()
            self.update_combat()
            self.render()
            self.present()
