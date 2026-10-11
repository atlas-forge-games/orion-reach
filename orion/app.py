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
from .planet_view import draw_planet_overview, draw_production, worker_row_rect, worker_selection_count
from .colony_view import draw_colony, turn_label
from .empire import COLONIES_PER_PAGE, FILTERS, SORT_KEYS, colony_rows
from .empire_view import draw_empire
from .rival_view import draw_rival
from .diplomacy_view import draw_diplomacy
from .contact_view import draw_contact
from .council_view import draw_council
from . import first_contact
from .personalities import personality
from .research_view import draw_research, draw_technology_info
from .research import BRANCHES, TECHNOLOGIES, branch_tiers
from .combat import retreat_destination
from .combat_view import VISIBLE_ROWS, draw_combat
from .combat_effects import CombatAnimation
from .victory import CONDITIONS, colonies
from .victory_view import draw_objectives, draw_result
from .ground_view import draw_ground
from .news_view import NEWS_PER_PAGE, draw_news
from . import news as news_rules
from . import defenses, sensors, black_holes, black_hole_view
from .sensor_view import draw_coverage, draw_contacts, draw_contact_panel
from .production import PROJECTS, SHIP_TYPES
from .designs import loadout_error
from .designer_view import draft, draw_designer
from .setup_view import draw_race_select, draw_setup
from .races import SETUP_RACES as RACES
from .observer_view import draw_observer, draw_observer_header
from .empires import PLAYER_PALETTES, empire_color
from .diplomacy import BREAK_PENALTY, OFFER_COOLDOWN
from .fleet_views import FLEETS_PER_PAGE, QUEUE_PER_PAGE, draw_fleets, draw_shipyard
from .fleets import fleet_containing
from .galaxy_fleet_view import FLEET_SHIPS_PER_PAGE, draw_fleet, draw_fleet_popup, draw_fuel_range, draw_map_fleets, draw_map_guardians, draw_order_panel, guardian_markers, star_label_rects
from .galaxy_system_view import PLANETS_PER_PAGE, SYSTEM_PANEL, draw_system_panel
from .galaxy_hud import draw_galaxy_header, draw_galaxy_commands
from .galaxy_background import draw_galaxy_background
from .galaxy_labels import draw_system_label
from .encyclopedia import CATEGORIES, category_articles
from .encyclopedia_view import ARTICLES_PER_PAGE, INDEX_RECT, article_body_rect, draw_info, scroll_article, selected_article
from .exploration import known_rival_colonies
from .exploration_view import FINDS_PER_PAGE, draw_exploration, draw_system_intelligence
from .ui import (Button, CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED, RIVAL_COLOR,
                 arrow, emblem, font, panel, paragraph, shorten, text, text_image, wrapped_lines)

STAR_COLORS={"Yellow dwarf":(230,207,141), "Blue star":(113,181,231),
             "Red dwarf":(221,124,108), "White star":(217,228,239), "Orange dwarf":(235,170,106)}
MAP=pg.Rect(64,180,962,573)
GAME_SCREENS=("galaxy", "system", "planet", "production", "colony", "empire", "shipyard", "fleets", "fleet", "rival", "diplomacy", "research", "combat", "ground", "objectives", "result", "exploration", "designer", "news", "contact", "observer", "council")


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
        self.technology_regions=[]
        self.focus=None
        self.keyboard_mode=False
        self.mouse=(-1,-1)
        self.pressed=None
        self.time=0.0
        self.splash_started=0.0
        self.dialog=None
        self.contact_owner=None
        self.contact_return="galaxy"
        self.contact_replay=False
        self.notice=""
        self.notice_until=0.0
        self.notice_error=False
        self.empire="Terran Union"
        self.seed=""
        self.size="Standard"
        self.race_id="terran"
        self.rival_count=1
        self.observer_tab="empires"
        self.observer_page=0
        self.rival_id=RIVAL
        self.fog_of_war=True
        self.victory_conditions=CONDITIONS
        self.field=None
        self.select_all=False
        self.settings_return="menu"
        self.pause_return="galaxy"
        self.campaign_view="galaxy"
        self.info_return="galaxy"
        self.info_focus=None
        self.info_category="basics"
        self.info_article="welcome"
        self.info_page=0
        self.info_scroll=0
        self.colony_slot=None
        self.colony_build_page=0
        self.clear_worker_selection()
        self.production_page=0
        self.catalog_page=0
        self.designer_return="fleets"
        self.design_campaign=None
        self.design_location=(0,2)
        self.design_page=0
        self.new_design()
        self.reset_empire_view()
        self.reset_fleet_view()
        self.reset_combat_view()
        self.reset_ground_view()
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
        if self.game and self.game.is_observer:
            tabs={"empire":"empires", "diplomacy":"diplomacy", "research":"research", "fleets":"fleets",
                  "objectives":"objectives", "designer":"fleets", "exploration":"empires"}
            if screen in tabs:
                self.observer_tab=tabs[screen]
                self.observer_page=0
                screen="observer"
        if self.game and self.ground_reports and screen in GAME_SCREENS and screen!="contact":
            screen="ground"
        elif self.game and self.game.result is not None and screen in GAME_SCREENS and screen not in ("news","contact"):
            screen="result"
        elif self.game and self.game.combat is not None and screen in GAME_SCREENS and screen!="contact":
            screen="combat"
        elif self.game and self.game.council.pending and screen in GAME_SCREENS:
            screen="council"
        elif screen in ("combat","result"):
            screen="galaxy"
        if screen=="ground" and not self.ground_reports and self.ground_target is None:
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
        self.clear_worker_selection()
        self.buttons=[]
        self.technology_regions=[]
        self.focus=None
        self.pressed=None
        self.field=None
        self.select_all=False
        pg.key.stop_text_input()
        if screen in GAME_SCREENS and screen!="contact":
            self.campaign_view=screen
        if screen=="contact":
            self.focus="contact_continue"
        if screen=="galaxy":
            self.focus=f"star_{self.game.selected_system}"
        if screen=="race_select":
            self.focus=f"race_{self.race_id}"
        if screen=="setup":
            self.focus="empire"
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
        if screen=="news":
            news_rules.mark_read(self.game)
            self.focus="news_back"
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
        if screen=="council":
            election=self.game.council.election
            self.focus="council_abstain" if election and election.status=="voting" else "council_accept" if self.game.council.pending else "council_back"
        if screen=="ground":
            self.focus="ground_continue" if self.ground_reports else "ground_launch"
        if screen=="combat":
            self.sync_combat_selection()
            self.combat_ai_due=self.time+.8
            self.combat_last_update=self.time
            self.focus="combat_continue" if self.game.combat.status!="active" else "combat_auto" if self.combat_auto else "combat_end_turn"
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
        self.prompt_idle_research()

    def update_splash(self):
        if (self.screen=="splash" and not self.dialog
                and self.time-self.splash_started>=SPLASH_SECONDS):
            self.go("menu")

    def open_system(self,system_id):
        if self.game is None or not 0 <= system_id < len(self.game.systems):
            return
        if not black_holes.charted(self.game,self.game.systems[system_id]):
            return
        if self.game.selected_system != system_id:
            self.game.selected_planet=None
        self.game.selected_system=system_id
        self.go("galaxy" if black_holes.at(self.game,system_id) else "system")

    def open_planet(self,planet_id):
        if not self.game.system_explored(self.game.selected_system):
            self.go("system")
            return
        worlds=self.game.systems[self.game.selected_system].worlds
        if not 0 <= planet_id < len(worlds):
            return
        if self.screen in ("galaxy","system"):
            self.planet_return=self.screen
        self.game.selected_planet=planet_id
        self.colony_slot=None
        self.shipyard_page=0
        self.shipyard_catalog_page=0
        self.go("planet")

    def close_planet(self):
        self.go(self.planet_return)
        if self.screen=="galaxy" and self.game.selected_planet is not None:
            self.galaxy_planet_page=self.game.selected_planet//PLANETS_PER_PAGE
            self.focus=f"galaxy_world_{self.game.selected_planet}"

    def change_galaxy_planet_page(self,delta):
        known=self.game.known_system(self.game.selected_system)
        if known is None or not known.worlds:
            return
        last=(len(known.worlds)-1)//PLANETS_PER_PAGE
        self.galaxy_planet_page=max(0,min(last,self.galaxy_planet_page+delta))
        self.focus=f"galaxy_world_{known.worlds[self.galaxy_planet_page*PLANETS_PER_PAGE].id}"

    def reset_fleet_view(self):
        self.planet_return="system"
        self.galaxy_planet_page=0
        self.galaxy_page_system=None
        self.fleet_return="galaxy"
        self.fleet_return_selection=(0,None)
        self.fleet_page=0
        self.shipyard_page=0
        self.shipyard_catalog_page=0
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
        self.news_page=0
        self.show_sensors=False
        self.sensor_contact_id=None

    def toggle_sensors(self):
        if self.game.is_observer:
            return
        self.show_sensors=not self.show_sensors
        if self.show_sensors and not sensors.centers(self.game):
            self.toast("Research Deep-space Radar to scan around your colonies.")

    def open_sensor_map(self,system_id):
        self.close_fleet_popup()
        self.route_ship_id=None
        self.game.selected_system=system_id
        self.game.selected_planet=None
        self.sensor_contact_id=None
        self.show_sensors=True
        self.go("galaxy")

    def open_sensor_contact(self,identifier):
        self.close_fleet_popup()
        self.route_ship_id=None
        self.sensor_contact_id=identifier
        self.focus="sensor_close"

    def close_sensor_contact(self):
        self.sensor_contact_id=None
        self.focus="sensor_overlay"

    def bombard_request(self):
        game=self.game
        sid,pid=game.selected_system,game.selected_planet
        reason=game.bombardment_error(sid,pid)
        if reason:
            self.toast(reason,True)
            return
        planet=game.planet_at(sid,pid)
        shield_loss,troop_loss=defenses.bombardment_forecast(game,sid,pid)
        def execute():
            try:
                report=game.bombard(sid,pid)
                self.save_game(autosave=True)
                self.toast(report.message)
            except RuleError as exc:
                self.toast(exc,True)
        self.confirm("Bombard "+planet.name+"?",
                     f"Expected losses: {shield_loss} shield points and {troop_loss} defending troops. "
                     f"The shield currently has {planet.shield_points} points and absorbs fire before troops take damage. "
                     "Civilian population is unaffected. Each armed ship can bombard once per turn. "
                     "This ends treaties and sets relations to -100.","Bombard defenses",execute)

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
        self.sensor_contact_id=None
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
            for guardian, rect, _ in reversed(guardian_markers(self,MAP)):
                if rect.collidepoint(self.mouse):
                    return guardian.system_id
            for system in reversed(black_holes.chart_systems(self.game)):
                x,y=self.star_pos(system)
                rect=black_hole_view.hit_rect((x,y)) if system.kind==black_holes.KIND else pg.Rect(int(x)-18,int(y)-18,36,36)
                if rect.collidepoint(self.mouse):
                    return system.id
        return self.game.selected_system

    def send_map_fleet(self,destination,accept_black_hole_risk=False):
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
            elif first.departure_pending and destination==first.destination:
                # Re-clicking an existing route keeps its saved speed and fuel authorization.
                self.game.selected_system=destination
                self.toast(f"Departure already queued · {turn_label(first.turns_remaining)} to {self.game.systems[destination].name}.")
                return
            else:
                warning=black_holes.risk(self.game,destination)
                if warning and not accept_black_hole_risk and self.game.within_fuel_range(destination):
                    self.confirm("Unsafe black-hole expedition",f"{count} ships → {self.game.systems[destination].name}. "+warning,
                                 "Send anyway",lambda:self.send_map_fleet(destination,True))
                    return
                duration=self.game.send_ships(identifiers,destination,accept_black_hole_risk=accept_black_hole_risk)
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
        if self.screen not in ("planet","colony","shipyard","production"):
            self.planet_return="galaxy" if self.screen=="galaxy" else "system"
        self.game.selected_system=system_id
        self.game.selected_planet=planet_id
        self.shipyard_page=0
        self.shipyard_catalog_page=0
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
        if not black_holes.charted(self.game,self.game.systems[system_id]):
            return
        self.sensor_contact_id=None
        if self.map_order_ids:
            self.send_map_fleet(system_id)
        elif self.fleet_popup:
            ships=self.viewed_fleet()
            if ships and ships[0].owner==PLAYER and not ships[0].in_transit:
                self.toast("Select at least one ship, or close the popup to inspect a system.")
            else:
                self.close_fleet_popup()
                self.select_star(system_id)
        elif self.route_ship_id is None:
            if self.game.selected_system != system_id:
                self.game.selected_planet=None
                self.galaxy_planet_page=0
            self.game.selected_system=system_id
            known=self.game.known_system(system_id)
            worlds=known.worlds if known else []
            self.focus="open_system"
            if worlds:
                first=next((p.id for p in worlds if p.colonized),0)
                chosen=self.game.selected_planet if self.game.selected_planet is not None else first
                self.galaxy_page_system=system_id
                self.galaxy_planet_page=chosen//PLANETS_PER_PAGE
                self.focus=f"galaxy_world_{chosen}"
        else:
            self.game.selected_system=system_id
            self.game.selected_planet=None
            self.focus="send_course"

    def send_course(self,accept_black_hole_risk=False):
        try:
            ship=self.game.ship_at(self.route_ship_id)
            destination=self.game.selected_system
            warning=black_holes.risk(self.game,destination)
            if warning and not accept_black_hole_risk and self.game.within_fuel_range(destination):
                self.confirm("Unsafe black-hole expedition",f"{ship.name} → {self.game.systems[destination].name}. "+warning,
                             "Send anyway",lambda:self.send_course(True))
                return
            duration=self.game.send_ship(ship.id,destination,accept_black_hole_risk=accept_black_hole_risk)
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
                self.toast(f"{self.game.project_spec(kind).name} queued · {planet.construction_queue[-1].resource_cost} RES on start")
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
        self.research_tier=1
        self.research_overview=True
        self.research_prompt_pending=False
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
                     f"Reserve 500 Resources when work begins on {planet.name}, then complete 300 work. Supply 10 energy while charging for five turns without opposing ships in orbit. "
                     "Capturing this colony destroys the gate.","Build gate",build)

    def invade_request(self):
        system_id,planet_id=self.game.selected_system,self.game.selected_planet
        error=self.game.invasion_error(system_id,planet_id)
        if error:
            self.toast(error,True)
            return
        self.ground_target=(system_id,planet_id)
        self.ground_return="planet"
        self.ground_page=0
        self.go("ground")

    def reset_ground_view(self):
        self.ground_target=None
        self.ground_reports=[]
        self.ground_return="galaxy"
        self.ground_page=0

    def launch_ground_assault(self):
        if self.ground_target is None or self.ground_reports:
            return
        try:
            report=self.game.invade(*self.ground_target)
        except RuleError as exc:
            self.toast(exc,True)
            return
        self.ground_reports.append(report)
        if report.cause=="raid":
            self.ground_return="news"
        self.ground_target=None
        self.colony_slot=None
        self.go("ground")
        self.save_game(autosave=True)

    def close_ground(self):
        if self.ground_reports:
            self.ground_reports.pop(0)
        self.ground_target=None
        self.ground_page=0
        self.go("ground" if self.ground_reports else self.ground_return)
        self.show_first_contact()

    def open_research(self):
        if self.screen=="research":
            self.close_research()
        elif self.screen in GAME_SCREENS:
            self.research_return=self.screen
            self.research_return_selection=(self.game.selected_system,self.game.selected_planet)
            self.research_overview=True
            self.research_prompt_pending=False
            self.go("research")

    def needs_research_choice(self):
        return (self.game is not None and not self.game.is_observer and self.game.result is None
                and self.game.technology.active is None
                and any(self.game.technology.status(t)=="available"
                        and (t!="ascension_theory" or "science" in self.game.victory_conditions) for t in TECHNOLOGIES))

    def prompt_idle_research(self, *, allow_news=False):
        """Show the turn's reminder once, after battles, greetings and news."""
        if not self.research_prompt_pending:
            return
        if not self.needs_research_choice():
            self.research_prompt_pending=False
            return
        if (self.screen not in GAME_SCREENS or self.screen in ("contact","combat","ground","result","council")
                or (self.screen=="news" and not allow_news)
                or self.dialog or self.game.combat is not None or self.ground_reports
                or first_contact.pending(self.game)):
            return
        self.research_prompt_pending=False
        if self.screen=="research":
            self.show_research_overview()
        else:
            self.open_research()

    def show_research_overview(self):
        self.research_overview=True
        self.focus=f"research_branch_{self.research_branch}"

    def close_research(self):
        self.game.selected_system,self.game.selected_planet=self.research_return_selection
        self.go(self.research_return)

    def select_research_branch(self,identifier):
        self.research_overview=False
        self.research_branch=identifier
        self.research_tier=self.game.technology.next_tier(identifier)
        self.focus=f"research_branch_{identifier}"

    def select_research_tier(self,tier):
        self.research_tier=max(1,min(branch_tiers(self.research_branch)[-1],tier))
        self.focus=f"research_tier_{self.research_tier}"

    def change_research_tier(self,delta):
        if not self.research_overview:
            self.select_research_tier(self.research_tier+delta)

    def show_research_technology(self,identifier):
        technology=TECHNOLOGIES[identifier]
        if technology.branch not in BRANCHES:
            self.open_objectives()
            return
        self.select_research_branch(technology.branch)
        self.select_research_tier(technology.tier)

    def research_request(self,identifier):
        error=self.game.research_error(identifier)
        if error:
            self.toast(error,True)
            return
        technology=TECHNOLOGIES[identifier]
        transferred=self.game.technology.progress
        try:
            discovered=self.game.choose_research(identifier)
            if discovered:
                self.research_tier=self.game.technology.next_tier(self.research_branch)
            if self.save_game(autosave=True):
                message=f"Discovered {discovered.name}." if discovered else f"Research started: {technology.name}."
                if transferred:
                    message+=f" {transferred} RP transferred."
                self.toast(message)
        except RuleError as exc:
            self.toast(exc,True)

    def technology_info_region(self,identifier,rect):
        self.technology_regions.append((identifier,pg.Rect(rect)))

    def show_technology_info(self,identifier):
        if self.dialog or identifier not in TECHNOLOGIES:
            return
        self.dialog={"technology":identifier,"return_focus":self.focus}
        self.focus="dialog_close"
        self.keyboard_mode=True
        self.pressed=None
        self.buttons=[]

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
        self.planet_return="system"
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
        last=max(0,(len(known_rival_colonies(self.game,self.selected_rival_id()))-1)//5)
        self.rival_page=min(max(0,self.rival_page+delta),last)

    def selected_rival_id(self):
        owners=first_contact.known_opponents(self.game)
        if self.rival_id not in owners:
            self.rival_id=next(iter(owners),None)
        return self.rival_id

    def change_rival(self,delta,system_id=None):
        owners=self.game.opponents_at(system_id) if system_id is not None else first_contact.known_opponents(self.game)
        if owners:
            index=owners.index(self.rival_id) if self.rival_id in owners else 0
            self.rival_id=owners[(index+delta)%len(owners)]
            self.rival_page=0

    def open_rival(self):
        if self.screen=="planet" and self.game.selected_planet is not None:
            planet=self.game.known_system(self.game.selected_system).worlds[self.game.selected_planet]
            if planet.owner in self.game.opponents:
                self.rival_id=planet.owner
        self.rival_return=self.screen if self.screen in ("diplomacy","planet") else "observer" if self.game.is_observer else "empire"
        self.go("rival")

    def open_observer_tab(self,tab):
        self.observer_tab=tab
        self.observer_page=0
        self.go("observer")

    def open_observed_empire(self,owner):
        self.rival_id=owner
        self.rival_return="observer"
        self.go("rival")

    def change_observer_page(self,delta):
        self.observer_page=max(0,self.observer_page+delta)

    def open_diplomacy(self):
        if self.screen=="diplomacy":
            self.close_diplomacy()
        elif self.screen in GAME_SCREENS:
            self.diplomacy_return=self.screen
            self.diplomacy_return_selection=(self.game.selected_system,self.game.selected_planet)
            self.go("diplomacy")

    def show_first_contact(self, return_screen=None):
        pending=first_contact.pending(self.game)
        if not pending or self.screen=="contact" or self.game.result is not None or self.game.council.pending:
            return False
        self.contact_return=return_screen or self.screen
        self.contact_owner=pending[0]
        self.contact_replay=False
        self.go("contact")
        return True

    def replay_greeting(self):
        owner=self.selected_rival_id()
        if owner is not None:
            self.contact_owner=owner
            self.contact_return="diplomacy"
            self.contact_replay=True
            self.go("contact")

    def finish_contact(self):
        if self.contact_replay:
            self.contact_replay=False
            self.go(self.contact_return)
            return
        first_contact.acknowledge(self.game,self.contact_owner)
        pending=first_contact.pending(self.game)
        if pending:
            self.contact_owner=pending[0]
            self.go("contact")
        else:
            self.go(self.contact_return)
        self.save_game(autosave=True)

    def skip_contacts(self):
        for owner in first_contact.pending(self.game):
            first_contact.acknowledge(self.game,owner)
        self.go(self.contact_return)
        self.save_game(autosave=True)

    def draw_contact(self):
        draw_contact(self)

    def open_council(self):
        self.go("council")

    def cast_council_vote(self,candidate):
        try:
            self.game.council_vote(candidate)
            self.go("council")
            self.save_game(autosave=True)
        except RuleError as exc:
            self.toast(exc,True)

    def decide_council(self,accept):
        try:
            self.game.council_ruling(accept)
            self.go("result" if self.game.result else "news")
            self.save_game(autosave=True)
        except RuleError as exc:
            self.toast(exc,True)

    def draw_council(self):
        draw_council(self)

    def close_diplomacy(self):
        self.game.selected_system,self.game.selected_planet=self.diplomacy_return_selection
        self.go(self.diplomacy_return)

    def diplomatic_action(self,action):
        target=self.selected_rival_id()
        def perform():
            try:
                response=self.game.diplomacy_action(action,target)
                if self.save_game(autosave=True):
                    self.toast(response)
                    self.notice_until=self.time+7
            except RuleError as exc:
                self.toast(exc,True)
        if action in ("end_trade","end_research"):
            title="trade pact" if action=="end_trade" else "research agreement"
            self.confirm(f"End the {title}?",
                         f"Its benefits stop immediately for both empires. Relations fall by {personality(self.game,target).breach} and new treaty offers wait {OFFER_COOLDOWN} turns. "
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
            self.show_first_contact()
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
        self.shipyard_catalog_page=0
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

    def empire_color(self,owner):
        return empire_color(owner,self.settings["galaxy_palette"])

    def set_galaxy_palette(self,palette):
        if palette not in PLAYER_PALETTES:
            return
        self.settings["galaxy_palette"]=palette
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
                               race_id=self.race_id,rival_count=self.rival_count,fog_of_war=self.fog_of_war,
                               victory_conditions=self.victory_conditions)
        except (ValueError,SaveError) as exc:
            self.toast(str(exc),True)
            return
        self.colony_slot=None
        self.reset_empire_view()
        self.reset_fleet_view()
        self.reset_combat_view()
        self.reset_ground_view()
        self.go("galaxy")
        self.save_game(autosave=True)
        self.show_first_contact()

    def toggle_fog_of_war(self):
        self.fog_of_war=not self.fog_of_war

    def toggle_victory_condition(self,condition):
        self.victory_conditions=tuple(c for c in CONDITIONS if (c in self.victory_conditions) != (c==condition))
        self.field=None
        pg.key.stop_text_input()

    def open_exploration(self):
        if self.screen=="exploration":
            self.close_exploration()
        elif self.screen in GAME_SCREENS:
            self.exploration_return=self.screen
            self.exploration_return_selection=(self.game.selected_system,self.game.selected_planet)
            self.go("exploration")

    def open_news(self):
        self.news_page=0
        self.go("galaxy" if self.screen=="news" else "news")

    def open_info(self):
        if self.dialog or self.field:
            return
        if self.screen=="info":
            self.close_info()
        elif self.game is not None and self.screen in (*GAME_SCREENS,"pause"):
            self.info_return,self.info_focus=self.screen,self.focus
            # A read-only overlay must not trigger go()'s order resets, news
            # read markers, research prompts or other screen-entry actions.
            self.screen="info"
            self.buttons=[]
            self.technology_regions=[]
            self.pressed=None
            self.focus="info_article_"+self.info_article

    def close_info(self):
        if self.screen!="info":
            return
        self.screen,self.focus=self.info_return,self.info_focus
        self.buttons=[]
        self.technology_regions=[]
        self.pressed=None
        if self.screen=="combat":
            self.combat_last_update=self.time
            self.combat_ai_due=self.time+.8

    def select_info_category(self,category):
        if category not in CATEGORIES:
            return
        self.info_category=category
        self.info_page=self.info_scroll=0
        self.info_article=category_articles(category)[0].id

    def select_info_article(self,identifier):
        entries=category_articles(self.info_category)
        for index,article in enumerate(entries):
            if article.id==identifier:
                self.info_article=identifier
                self.info_page=index//ARTICLES_PER_PAGE
                self.info_scroll=0
                self.focus="info_article_"+identifier
                return

    def change_info_page(self,delta):
        entries=category_articles(self.info_category)
        page=max(0,min((len(entries)-1)//ARTICLES_PER_PAGE,self.info_page+delta))
        if page!=self.info_page:
            self.select_info_article(entries[page*ARTICLES_PER_PAGE].id)

    def change_news_page(self,delta):
        last=max(0,(len(news_rules.entries(self.game))-1)//NEWS_PER_PAGE)
        self.news_page=min(max(0,self.news_page+delta),last)

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
                self.toast("Game saved. Find this save under Load Game.")
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
        self.design_campaign=None
        self.colony_slot=None
        self.reset_empire_view()
        self.reset_fleet_view()
        self.reset_combat_view()
        self.reset_ground_view()
        self.go("galaxy")
        self.toast(f"Welcome back, {state.empire_name}.")
        if self.show_first_contact() and self.game.combat is None and news_rules.unread_count(self.game):
            self.contact_return="news"

    def advance_turn(self):
        if self.screen=="contact":
            return
        if self.ground_reports or self.screen=="ground":
            self.go("ground")
            return
        if self.game.result is not None:
            self.go("result")
            return
        if self.game.combat is not None:
            self.go("combat")
            self.toast("Resolve the battle before advancing the campaign.",True)
            return
        if self.game.council.pending:
            self.go("council")
            return
        # An unissued map order is a UI selection, never an automatic next-turn order.
        self.clear_worker_selection()
        self.close_fleet_popup()
        report=self.game.advance_turn()
        if self.game.is_observer:
            if self.game.result is not None:
                self.go("result")
            if self.save_game(autosave=True):
                alive=sum(bool(self.game.colony_systems(o)) for o in self.game.owners)
                self.toast(f"Turn {self.game.turn} · {alive} empires remain · Galaxy updated · Autosaved")
            return
        self.research_prompt_pending=self.needs_research_choice()
        if report.discoveries:
            self.research_tier=self.game.technology.next_tier(self.research_branch)
        new_news=news_rules.unread_count(self.game)>0
        if report.ground_battles:
            self.ground_reports.extend(report.ground_battles)
            self.ground_return="news" if new_news else "galaxy"
            self.ground_page=0
            self.go("ground")
        elif self.game.result is not None:
            self.go("result")
        elif self.game.combat is not None:
            self.reset_combat_view()
            self.go("combat")
        elif self.game.council.pending:
            self.go("council")
        elif new_news:
            self.news_page=0
            if not self.show_first_contact("news"):
                self.go("news")
        if self.screen=="empire":
            self.focus_empire_row()
        self.show_first_contact()
        self.prompt_idle_research(allow_news=not new_news)
        if self.save_game(autosave=True):
            message=f"Turn {self.game.turn} · {report.income:+} CR net · +{report.research} RP · {report.resources:+} RES"
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
        self.combat_auto=False
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
        targets=battle.fleet(battle.enemy(PLAYER))
        if not any(s.id==self.combat_ship_id for s in ready):
            self.combat_ship_id=ready[0].id if ready else None
        if not any(s.id==self.combat_target_id for s in targets):
            self.combat_target_id=targets[0].id if targets else None
        if battle.active_owner==PLAYER and self.combat_ship_id is not None:
            self.reveal_combat_row(battle.ship(self.combat_ship_id).y)

    def combat_input_ready(self):
        return (self.screen=="combat" and not self.dialog and not self.combat_auto and self.game is not None
                and self.game.combat is not None and self.game.combat.status=="active"
                and self.game.combat.active_owner==PLAYER and self.combat_animation is None)

    def toggle_combat_auto(self):
        if (self.screen!="combat" or self.dialog or self.field or self.game is None
                or self.game.combat is None or self.game.combat.status!="active"):
            return
        self.combat_auto=not self.combat_auto
        self.combat_ai_due=self.time+.4
        # Taking control stops future orders; an already applied action still
        # finishes its animation and keeps its spent movement / weapon use.
        if not self.combat_auto and self.combat_animation is None:
            self.sync_combat_selection()
        self.focus="combat_auto"

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

    def engage_request(self,system_id,target=None):
        opponents=self.game.opponents_at(system_id)
        target=target or (self.rival_id if self.rival_id in opponents else opponents[0] if opponents else None)
        error=self.game.engagement_error(system_id,target=target)
        if error:
            self.toast(error,True)
            return
        own=len(self.game.fleet_at(system_id))+len(defenses.bases(self.game,system_id,PLAYER))
        rival=len(self.game.fleet_at(system_id,target))+len(defenses.bases(self.game,system_id,target))
        def engage():
            try:
                self.game.start_combat(system_id,target=target)
                self.reset_combat_view()
                self.go("combat")
                self.save_game(autosave=True)
                self.show_first_contact()
            except RuleError as exc:
                self.toast(exc,True)
        from .monsters import alive_at
        guardian=alive_at(self.game,system_id)
        if guardian:
            self.confirm("Face the system guardian?",
                         f"Your {own} ships face the {guardian.spec.name}. Prize: {guardian.spec.reward}. "
                         "Your fleet acts first. Fight or retreat; ship losses are permanent.",
                         "Face guardian",engage)
            return
        self.confirm("Engage the opposing fleet?",
                     f"Commit your {own} ships and defense units against {rival} units of {self.game.empire_name_for(target)} at {self.game.systems[system_id].name}. "
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
            self.focus="combat_fire"

    def after_combat_action(self,event):
        battle=self.game.combat
        ship=battle.ship(event.get("ship_id"))
        if self.combat_auto and ship is not None and ship.owner==PLAYER:
            self.combat_ship_id=ship.id
            if event.get("target_id") is not None:
                self.combat_target_id=event["target_id"]
        if battle.status!="active":
            self.combat_auto=False
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
        self.focus=("combat_continue" if battle.status!="active" and not self.combat_animation
                    else "combat_auto" if self.combat_auto else "combat_end_turn")

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
                target=self.game.combat.ship(self.combat_target_id)
                ship=self.game.combat.ship(self.combat_ship_id)
                weapons=tuple(dict.fromkeys(w for w,_ in ship.volley(target))) if ship and target else ()
                shields=target.shields if target else 0
                damage=self.game.combat_fire(self.combat_ship_id,self.combat_target_id)
                event.update(ship_id=self.combat_ship_id,target_id=self.combat_target_id,damage=damage,
                             missed=damage==0 and target.shields==shields,weapons=weapons)
            elif action=="launch":
                drones=self.game.combat_launch_drones(self.combat_ship_id,role=getattr(self,"combat_drone_role",None))
                event.update(ship_id=self.combat_ship_id,drone_ids=drones)
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
        if self.game.combat.status!="active":
            self.combat_auto=False
        if self.combat_animation:
            self.combat_animation.elapsed+=delta
            if self.combat_animation.finished:
                self.combat_animation=None
                self.sync_combat_selection()
                self.combat_ai_due=self.time+.35
                self.focus=("combat_continue" if self.game.combat.status!="active"
                            else "combat_auto" if self.combat_auto else "combat_end_turn")
            return
        if (self.game.combat.status=="active" and (self.combat_auto or self.game.combat.active_owner!=PLAYER)
                and self.time>=self.combat_ai_due):
            self.after_combat_action(self.game.combat_ai_action())

    def finish_combat(self):
        if self.combat_animation:
            return
        try:
            system_id=self.game.finish_combat()
            self.reset_combat_view()
            if news_rules.unread_count(self.game):
                self.news_page=0
                if not self.show_first_contact("news"):
                    self.go("news")
            else:
                self.open_system(system_id)
            self.save_game(autosave=True)
            self.show_first_contact()
        except RuleError as exc:
            self.toast(exc,True)

    def select_colony_slot(self,index):
        self.colony_slot=index

    def clear_worker_selection(self):
        self.worker_source=None
        self.worker_count=0

    def adjust_worker_selection(self,delta):
        planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
        available=getattr(planet,self.worker_source)
        if available:
            self.worker_count=max(1,min(available,self.worker_count+delta))
        else:
            self.clear_worker_selection()

    def select_worker_role(self,role):
        planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
        if planet.owner!=PLAYER or self.game.strategy_error():
            return
        if self.worker_source==role:
            self.clear_worker_selection()
        elif self.worker_source is None:
            if getattr(planet,role)>0:
                self.worker_source=role
                x=self.mouse[0] if not self.keyboard_mode and worker_row_rect(role).collidepoint(self.mouse) else None
                self.worker_count=worker_selection_count(getattr(planet,role),x)
        else:
            try:
                self.game.move_worker(self.game.selected_system,self.game.selected_planet,self.worker_source,role,count=self.worker_count)
                self.clear_worker_selection()
                self.save_game(autosave=True)
            except RuleError as exc:
                self.clear_worker_selection()
                self.toast(exc,True)

    def open_production(self):
        self.production_page=0
        self.catalog_page=0
        self.go("production")

    def open_designer(self):
        if not self.game or self.game.strategy_error():
            return
        if self.design_campaign != self.game.campaign_id:
            self.new_design()
            self.design_page=0
            self.design_campaign=self.game.campaign_id
        self.designer_return=self.screen if self.screen in GAME_SCREENS and self.screen!="designer" else "fleets"
        self.design_location=(self.game.selected_system,self.game.selected_planet)
        self.go("designer")

    def new_design(self):
        self.design_id=None
        self.design_name=""
        self.design_kind="frigate"
        self.design_modules=["laser","armor"]
        self.design_module_filter="all"
        self.design_module_page=0

    def load_design(self,design):
        self.design_id,self.design_name,self.design_kind=design.id,design.name,design.kind
        self.design_modules=list(design.modules)
        self.field=None
        pg.key.stop_text_input()

    def choose_design_hull(self,kind):
        self.design_kind=kind

    def change_design_module(self,identifier,amount):
        if amount<0:
            if identifier in self.design_modules:
                self.design_modules.remove(identifier)
        elif not loadout_error(self.design_kind,[*self.design_modules,identifier],self.game.technology.completed,require_weapon=False,legacy_hulls=self.game.technology.legacy_starships):
            self.design_modules.append(identifier)

    def design_page_change(self,delta):
        self.design_page=max(0,min(max(0,(len(self.game.designs)-1)//7),self.design_page+delta))

    def filter_design_modules(self,category):
        self.design_module_filter=category
        self.design_module_page=0

    def design_module_page_change(self,delta):
        self.design_module_page=max(0,self.design_module_page+delta)

    def auto_fit_design(self):
        from .auto_designs import auto_design
        state=self.game.technology
        design=auto_design(self.design_kind,tuple(sorted(state.completed)),state.legacy_starships)
        if design:
            self.design_modules=list(design.modules)
        else:
            self.toast("Research this hull before fitting its equipment.",True)

    def design_colony(self):
        colonies=[(s,p) for s in self.game.systems for p in s.worlds if p.owner==PLAYER]
        return next(((s,p) for s,p in colonies if (s.id,p.id)==self.design_location), colonies[0] if colonies else None)

    def cycle_design_colony(self,delta):
        colonies=[(s.id,p.id) for s in self.game.systems for p in s.worlds if p.owner==PLAYER]
        colony=self.design_colony()
        if colony:
            index=colonies.index((colony[0].id,colony[1].id))
            self.design_location=colonies[(index+delta)%len(colonies)]

    def save_ship_design(self,copy=False):
        try:
            design=self.game.save_design(self.design_name,self.design_kind,self.design_modules,None if copy else self.design_id)
            self.load_design(design)
            self.design_page=self.game.designs.index(design)//7
            if self.save_game(autosave=True):
                self.toast(f"{design.name} saved · Existing ships and orders retain their equipment")
        except RuleError as exc:
            self.toast(exc,True)

    def build_ship_design(self):
        colony=self.design_colony()
        saved=self.game.design_for(self.design_id)
        if colony is None or saved!=draft(self):
            self.toast("Save your design and select a colony first.",True)
            return
        try:
            self.game.queue_ship(colony[0].id,colony[1].id,saved.id)
            if self.save_game(autosave=True):
                self.toast(f"{saved.name} queued at {colony[1].name}")
        except RuleError as exc:
            self.toast(exc,True)

    def change_production_page(self,delta):
        planet=self.game.planet_at(self.game.selected_system,self.game.selected_planet)
        self.production_page=max(0,min(max(0,(len(planet.construction_queue)-1)//6),self.production_page+delta))

    def choose_production(self,item_id):
        try:
            self.game.change_production(self.game.selected_system,self.game.selected_planet,item_id)
            self.go("planet")
            if self.save_game(autosave=True):
                self.toast(f"Now building {self.game.project_spec(item_id).name} · Previous projects remain queued")
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
        name=project.spec.name
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
                     f"Also reserves {project.needs_resources} Resources if not already reserved. Other queued projects are kept.","Buy",buy)

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
                self.toast(f"{BUILDINGS[building_id].name} queued · {planet.construction_queue[-1].resource_cost} RES on start")
        except RuleError as exc:
            self.toast(exc,True)

    def cancel_construction(self,index):
        try:
            refund=self.game.cancel_construction(self.game.selected_system,self.game.selected_planet,index)
            self.colony_slot=None
            if self.save_game(autosave=True):
                self.toast(f"Project cancelled · {refund} refunded")
        except RuleError as exc:
            self.toast(exc,True)

    def toggle_building(self,index):
        try:
            self.game.toggle_building(self.game.selected_system,self.game.selected_planet,index)
            if self.save_game(autosave=True):
                self.toast("Power allocation updated · Credit maintenance still applies")
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
        focus=self.dialog.get("return_focus") if self.dialog else None
        self.dialog=None
        self.buttons=[]
        self.focus=focus

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
        if event.type==pg.MOUSEBUTTONUP and event.button==3:
            self.mouse=self.logical_pos(event.pos)
            self.pressed=None
            if self.dialog:
                if "technology" in self.dialog:
                    self.cancel_dialog()
            else:
                identifier=next((t for t,r in reversed(self.technology_regions) if r.collidepoint(self.mouse)),None)
                if identifier:
                    self.show_technology_info(identifier)
            return
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
            else:
                pressed=self.pressed
                self.pressed=None
                if hovered and hovered.key==pressed:
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
        elif (event.type==pg.MOUSEWHEEL and self.screen=="galaxy" and not self.dialog and event.y
              and not self.map_order_ids and self.sensor_contact_id is None and self.route_ship_id is None and SYSTEM_PANEL.collidepoint(self.mouse)):
            self.change_galaxy_planet_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="exploration" and not self.dialog and event.y:
            self.change_exploration_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="observer" and not self.dialog and event.y:
            self.change_observer_page(-1 if event.y>0 else 1)
        if event.type==pg.MOUSEWHEEL and self.screen=="info" and not self.dialog and event.y:
            if INDEX_RECT.collidepoint(self.mouse):
                self.change_info_page(-1 if event.y>0 else 1)
            else:
                scroll_article(self,-event.y*72)
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
        if event.key==pg.K_F1 and not self.dialog:
            self.open_info()
            return
        if event.key==pg.K_ESCAPE:
            if self.dialog:
                self.cancel_dialog()
            elif self.field:
                self.field=None
                pg.key.stop_text_input()
            elif self.screen=="info":
                self.close_info()
            elif self.screen=="contact":
                self.finish_contact()
            elif self.screen=="galaxy":
                if self.sensor_contact_id is not None:
                    self.close_sensor_contact()
                elif self.fleet_popup or self.map_order_ids:
                    self.cancel_map_order()
                else:
                    self.go("fleets") if self.route_ship_id is not None else self.pause()
            elif self.screen=="fleet":
                self.go("galaxy")
            elif self.screen=="designer":
                self.go(self.designer_return)
            elif self.screen=="setup":
                self.go("race_select")
            elif self.screen=="exploration":
                self.close_exploration()
            elif self.screen=="news":
                self.go("galaxy")
            elif self.screen=="observer":
                self.go("galaxy")
            elif self.screen=="system":
                self.go("galaxy")
            elif self.screen=="planet":
                if self.worker_source:
                    self.clear_worker_selection()
                else:
                    self.close_planet()
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
            elif self.screen in ("combat","council"):
                self.pause()
            elif self.screen=="ground":
                self.close_ground()
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
        elif self.screen=="info" and not self.dialog:
            if event.key in (pg.K_LEFT,pg.K_RIGHT):
                self.change_info_page(1 if event.key==pg.K_RIGHT else -1)
            elif event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                height=article_body_rect(selected_article(self)).h
                scroll_article(self,(height-24)*(1 if event.key==pg.K_PAGEDOWN else -1))
        elif self.screen in ("combat","ground","result","contact","council") and not self.dialog:
            if event.key==pg.K_F5:
                self.save_game()
            elif self.screen=="result" and event.key==pg.K_n:
                self.open_news()
            elif self.screen=="combat":
                if event.key==pg.K_a:
                    self.toggle_combat_auto()
                elif event.key==pg.K_e:
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
            elif event.key==pg.K_s and self.screen=="galaxy":
                self.toggle_sensors()
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
            elif event.key==pg.K_n:
                self.open_news()
            elif self.screen=="news" and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_news_page(1 if event.key==pg.K_PAGEDOWN else -1)
            elif self.screen=="observer" and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_observer_page(1 if event.key==pg.K_PAGEDOWN else -1)
            elif (self.screen=="galaxy" and not self.fleet_popup and not self.map_order_ids
                  and self.route_ship_id is None and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN)):
                self.change_galaxy_planet_page(1 if event.key==pg.K_PAGEDOWN else -1)
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
            elif self.screen=="research" and event.key in (pg.K_PAGEUP,pg.K_PAGEDOWN):
                self.change_research_tier(1 if event.key==pg.K_PAGEDOWN else -1)
            elif self.screen=="planet" and self.worker_source and event.key in (pg.K_LEFT,pg.K_RIGHT):
                self.adjust_worker_selection(1 if event.key==pg.K_RIGHT else -1)
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

    def button(self,key,label,rect,action,style="normal",subtitle="",enabled=True,*,icon="",shortcut="",badge=""):
        b=Button(key,label,pg.Rect(rect),action,subtitle,style,enabled,icon,shortcut,badge)
        self.buttons.append(b)
        active=self.is_active(b)
        b.draw(self.canvas,active,active and self.pressed==key)
        return b

    def chrome(self,section="COMMAND",back=None):
        emblem(self.canvas,77,64,.62)
        text(self.canvas,"ORION REACH",(110,46),18,INK,spacing=2)
        text(self.canvas,section,(111,73),10,MUTED,"mono",2)
        if self.screen in GAME_SCREENS and self.screen not in ("empire","combat","ground","result","council"):
            self.button("open_empire","Empire",(998,31,179,64),self.open_empire,"command",icon="empire",shortcut="I")
        if self.screen in GAME_SCREENS and self.screen not in ("fleets","combat","ground","result","council"):
            self.button("open_fleets","Fleets",(807,31,177,64),self.open_fleets,"command",icon="fleets",shortcut="F")
        if self.screen in GAME_SCREENS and self.screen not in ("diplomacy","combat","ground","result","council"):
            self.button("open_diplomacy","Diplomacy",(590,31,203,64),self.open_diplomacy,"command",icon="diplomacy",shortcut="D")
        if self.screen in GAME_SCREENS and self.screen not in ("research","combat","ground","result","council"):
            self.button("open_research","Research",(395,31,181,64),self.open_research,"command",icon="research",shortcut="R")
        if self.screen in GAME_SCREENS and self.screen not in ("combat","ground","result","council"):
            self.button("open_objectives","Objectives",(1191,31,185,64),self.open_objectives,"command",icon="objectives",shortcut="V")
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
            self.button("new","New Game",(88,523,417,64),lambda:self.go("race_select"),"menu")
            self.button("load","Load Game",(88,592,417,64),lambda:self.go("load"),"menu")
            self.button("settings","Settings",(88,661,417,60),lambda:self.show_settings(),"menu")
            self.button("quit","Quit",(88,726,417,60),self.quit_request,"menu")
        else:
            self.button("new","New Game",(88,454,417,66),lambda:self.go("race_select"),"primary")
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
        if race_id=="observer":
            self.rival_count=max(3,self.rival_count)
        self.field=None
        pg.key.stop_text_input()

    def choose_rival_count(self,count):
        self.rival_count=count
        self.field=None
        pg.key.stop_text_input()

    def draw_setup(self):
        draw_setup(self)

    def draw_race_select(self):
        draw_race_select(self)

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
            self.button("empty_new","Start a new game",(548,594,345,60),lambda:self.go("race_select"),"primary")
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
                 ("galaxy_background","Galaxy background","Nebula artwork behind the galaxy map."),
                 ("sound","Interface sounds","A quiet tone when you activate a control."),
                 ("music","Background music",self.audio.music_description)]
        for i,(key,label,description) in enumerate(options):
            y=302+i*64
            panel(self.canvas,(256,y,928,60))
            text(self.canvas,label,(280,y+7),21,INK)
            text(self.canvas,description,(280,y+36),14,MUTED)
            self.button(key,"ON" if self.settings[key] else "OFF",(1020,y+8,135,44),lambda k=key:self.toggle_setting(k))
            if self.settings[key]:
                pg.draw.circle(self.canvas,CYAN,(1132,y+30),4)
        volume=self.settings["music_volume"]
        muted=not self.settings["music"] or volume==0
        panel(self.canvas,(256,625,928,66))
        text(self.canvas,"Music volume"+(" · Muted" if muted else ""),(280,632),21,INK)
        text(self.canvas,"Use − / + to adjust in 10% steps.",(280,666),14,MUTED)
        self.button("music_quieter","−",(880,635,52,46),lambda:self.change_music_volume(-10),enabled=volume>0)
        label=f"{volume}%"
        text(self.canvas,label,(1018-font(23).size(label)[0]//2,643),23,CYAN)
        self.button("music_louder","+",(1104,635,52,46),lambda:self.change_music_volume(10),enabled=volume<100)
        panel(self.canvas,(256,697,928,98))
        text(self.canvas,"Galaxy colors",(280,709),21,INK)
        text(self.canvas,"Your empire's color. Neutral systems stay gray.",(280,746),14,MUTED)
        text(self.canvas,"Blue is the default.",(280,769),12,MUTED)
        for index,(palette,label) in enumerate((("blue","Saturated blue"),("turquoise","Saturated turquoise"))):
            x=724+index*221
            selected=self.settings["galaxy_palette"]==palette
            self.button("galaxy_palette_"+palette,label,(x,727,209,44),
                        lambda value=palette:self.set_galaxy_palette(value),"tab_active" if selected else "tab")
            pg.draw.line(self.canvas,PLAYER_PALETTES[palette],(x+12,775),(x+197,775),3)
        text(self.canvas,"Music and interface sounds have separate controls.",(256,834),14,MUTED)
        self.button("settings_done","Done",(933,817,251,52),lambda:self.go(self.settings_return),"primary")

    def star_pos(self,system):
        return (MAP.x+40+system.x*(MAP.w-80),MAP.y+32+system.y*(MAP.h-64))

    def draw_galaxy(self):
        state=self.game
        if state is None:
            self.go("menu")
            return
        (draw_observer_header if state.is_observer else draw_galaxy_header)(self)
        draw_galaxy_background(self.canvas,MAP,self.settings["galaxy_background"])
        # A sparse coordinate grid makes the map legible without implying travel lanes.
        for x in range(MAP.x+44,MAP.right,76):
            pg.draw.line(self.canvas,(14,29,38),(x,MAP.y+1),(x,MAP.bottom-1))
        for y in range(MAP.y+40,MAP.bottom,70):
            pg.draw.line(self.canvas,(14,29,38),(MAP.x+1,y),(MAP.right-1,y))
        text(self.canvas,"SECTOR 01 / LOCAL CLUSTER",(MAP.x+22,MAP.y+18),10,FAINT,"mono",1)
        draw_coverage(self,MAP)
        draw_fuel_range(self,MAP)
        labels=star_label_rects(self,MAP)
        preview=self.fleet_route_target() if self.map_order_ids else state.selected_system
        for star in black_holes.chart_systems(state):
            x,y=self.star_pos(star)
            selected=star.id==preview
            if star.kind==black_holes.KIND:
                black_hole_view.draw_marker(self,star,selected)
                label=labels[star.id]
                if abs(label.x-(x+34))+abs(label.y-(y-9))>12:
                    tip=(min(max(int(x),label.left),label.right),min(max(int(y),label.top),label.bottom))
                    pg.draw.line(self.canvas,LINE,(int(x),int(y)),tip)
                draw_system_label(self.canvas,state,star,label.topleft,selected,self.settings["galaxy_palette"])
                continue
            known=state.known_system(star.id)
            color=STAR_COLORS[star.kind] if known else tuple(c//3 for c in STAR_COLORS[star.kind])
            pg.draw.circle(self.canvas,tuple(c//8 for c in color),(int(x),int(y)),14)
            pg.draw.circle(self.canvas,tuple(c//3 for c in color),(int(x),int(y)),8)
            pg.draw.circle(self.canvas,color,(int(x),int(y)),4)
            pg.draw.circle(self.canvas,INK,(int(x),int(y)),1)
            if selected:
                ordering=bool(self.map_order_ids or self.route_ship_id is not None)
                queued=next((s for s in state.ships if s.id in self.map_order_ids and s.departure_pending and s.destination==star.id),None)
                selection_color=RED if ordering and not queued and not state.within_fuel_range(star.id) else GOLD
                pg.draw.circle(self.canvas,selection_color,(int(x),int(y)),19,1)
                for dx,dy in ((-25,0),(25,0),(0,-25),(0,25)):
                    pg.draw.circle(self.canvas,selection_color,(int(x+dx),int(y+dy)),1)
            owners={p.owner for p in known.worlds if p.colonized} if known else set()
            if PLAYER in owners:
                pg.draw.circle(self.canvas,self.empire_color(PLAYER),(int(x),int(y)),11,2)
            for index,owner in enumerate(o for o in state.opponents if o in owners):
                pg.draw.circle(self.canvas,self.empire_color(owner),(int(x),int(y)),(15 if PLAYER in owners else 11)+4*index,2)
            label=labels[star.id]
            if abs(label.x-(x+17))+abs(label.y-(y-9))>12:
                tip=(min(max(int(x),label.left),label.right),min(max(int(y),label.top),label.bottom))
                pg.draw.line(self.canvas,LINE,(int(x),int(y)),tip)
            draw_system_label(self.canvas,state,star,label.topleft,selected,self.settings["galaxy_palette"])
            self.button(f"star_{star.id}","",(int(x)-18,int(y)-18,36,36),
                        lambda s=star.id:self.select_star(s),"hotspot")
        draw_map_fleets(self,MAP)
        draw_map_guardians(self,MAP)
        if not state.is_observer and not self.fleet_popup and not self.map_order_ids and self.route_ship_id is None:
            draw_contacts(self,MAP)
            self.button("sensor_overlay", "Sensors on · S" if self.show_sensors else "Sensor range · S",
                        (824,187,188,28),self.toggle_sensors,"primary" if self.show_sensors else "normal")
        star=state.systems[preview]
        if not self.fleet_popup and not self.map_order_ids:
            if self.sensor_contact_id is not None:
                draw_contact_panel(self)
            elif self.route_ship_id is None:
                draw_system_panel(self,star)
            else:
                draw_system_intelligence(self,star)
        if self.map_order_ids:
            if not self.fleet_popup:
                draw_order_panel(self,star)
            hint=f"{len(self.map_order_ids)} {'SHIP' if len(self.map_order_ids)==1 else 'SHIPS'} SELECTED · Click a destination, or the origin to cancel departure."
        elif self.route_ship_id is None:
            hint=("OBSERVING · Click stars, planets and fleets to inspect. End turn advances every computer empire." if state.is_observer else
                  "Select a star, then a planet on the right. Click a fleet to send ships.")
        else:
            ship=state.ship_at(self.route_ship_id)
            duration=state.travel_turns(state.systems[ship.system_id],star)
            blocked=not state.within_fuel_range(star.id)
            label="Out of fuel range" if blocked else f"Send ship · {turn_label(duration)}" if duration else "Current system"
            self.button("send_course",label,(1075,692,277,43),self.send_course,"command",enabled=duration>0 and not blocked,icon="course")
            known=state.known_system(star.id)
            targets=sum(not p.colonized and state.can_settle(p) for p in known.worlds) if known else 0
            detail=f"{targets} potential colony worlds in the last survey." if known else "Planets unknown until arrival."
            if black_holes.at(state,star.id):
                detail="FATAL APPROACH: this ship will be lost." if black_holes.risk(state,star.id) else "Safe approach unlocked. Guardian combat possible."
            hint=(f"{ship.name}: {state.supply_distance(star.id):.1f} ly from nearest colony · Range {state.fuel_range()} ly. "
                  +("Colonize closer worlds or research fuel tanks." if blocked else detail))
        ordering=self.fleet_popup or self.map_order_ids or self.route_ship_id is not None
        text(self.canvas,shorten(hint,765 if ordering else 944,13),(64,775),13,MUTED)
        text(self.canvas,f"{state.galaxy_size.upper()}   ·   SEED {state.seed}",(1376,778),10,FAINT,"mono",right=True)
        if self.fleet_popup or self.map_order_ids:
            self.button("cancel_fleet_course","Close",(848,763,178,32),self.cancel_map_order,"command",icon="close",shortcut="Esc")
        elif self.route_ship_id is not None:
            self.button("cancel_course","Cancel",(848,763,178,32),lambda:self.go("fleets"),"command",icon="close",shortcut="Esc")
        draw_galaxy_commands(self)
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
        self.button("save","Save game",(505,438,430,54),self.save_game)
        self.button("settings","Settings",(505,504,430,54),lambda:self.show_settings("pause"))
        self.button("main_menu","Return to main menu",(505,570,430,54),self.to_menu)
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

    def draw_designer(self):
        draw_designer(self)

    def draw_fleets(self):
        draw_fleets(self)

    def draw_fleet(self):
        draw_fleet(self)

    def draw_exploration(self):
        draw_exploration(self)

    def draw_news(self):
        draw_news(self)

    def draw_info(self):
        draw_info(self)

    def draw_observer(self):
        draw_observer(self)

    def draw_combat(self):
        draw_combat(self)

    def draw_ground(self):
        draw_ground(self)

    def draw_objectives(self):
        draw_objectives(self)

    def draw_result(self):
        draw_result(self)

    def draw_about(self):
        self.chrome("ABOUT",lambda:self.go("menu"))
        self.heading("A FIRST STEP INTO A LARGER GALAXY","Orion Reach", "An original Python prototype inspired by classic space strategy games.")
        panel(self.canvas,(256,335,928,387))
        text(self.canvas,"WHAT YOU CAN DO",(282,364),11,GOLD,"mono",1)
        paragraph(self.canvas,"Lead an empire, research technologies and negotiate with rival civilizations. Fight fleet battles and invade colonies. Win by conquest, build the Ascension Gate, or win a Galactic Council election.",
                  (282,403),840,20,INK,34)
        text(self.canvas,"WHAT COMES NEXT",(282,513),11,GOLD,"mono",1)
        paragraph(self.canvas,"Food shipments, more empires, shields and advanced weapons. Assign colony workers to farming, industry, research or mining, manage construction, and grow toward each world's population limit.",
                  (282,552),840,18,MUTED,32)
        text(self.canvas,"Original procedural artwork · DejaVu fonts · pygame-ce",(282,673),13,MUTED)
        text(self.canvas,"Music: Distant Stars · alexander_kies · Created with Suno",(282,699),12,MUTED)
        text(self.canvas,"CONTROLS",(256,764),11,GOLD,"mono",1)
        text(self.canvas,"Mouse / Tab / ↑ ↓ + Enter    Esc: back or pause    F11: fullscreen",(256,795),15,INK)

    def draw_dialog(self):
        self.backdrop.dim(self.canvas)
        self.buttons=[]
        if "technology" in self.dialog:
            draw_technology_info(self,self.dialog["technology"])
            return
        height=max(312,199+27*len(wrapped_lines(self.dialog["body"],526,16)))
        top=(SIZE[1]-height)//2
        panel(self.canvas,(422,top,596,height),PANEL,GOLD)
        text(self.canvas,self.dialog["title"],(454,top+31),29,INK,"title")
        paragraph(self.canvas,self.dialog["body"],(454,top+84),526,16,MUTED,27)
        self.button("dialog_cancel","Cancel",(454,top+height-97,180,57),self.cancel_dialog)
        self.button("dialog_ok",self.dialog["label"],(650,top+height-97,336,57),self.accept_dialog,"primary")

    def render(self):
        if self.game and self.screen in ("planet","colony","shipyard","production"):
            if not self.game.system_explored(self.game.selected_system):
                self.go("system")
            elif self.screen in ("colony","shipyard","production") and not self.game.system_visible(self.game.selected_system):
                self.go("planet")
            elif self.screen=="production" and self.game.planet_at(self.game.selected_system,self.game.selected_planet).owner!=PLAYER:
                self.go("planet")
        self.buttons=[]
        self.technology_regions=[]
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
