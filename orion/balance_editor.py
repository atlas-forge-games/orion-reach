"""Standalone pygame balance editor, using the game's existing fonts and dependency."""
from copy import deepcopy
from pathlib import Path
import math
import pygame as pg
from . import balance
from .balance_document import BalanceDocument
from .ui import text, shorten, font, panel, INK, MUTED, GOLD, CYAN, LINE, RED

SIZE = (1440, 900)
BG = (7, 14, 22)
GREEN = (134, 209, 170)


class BalanceEditor:
    def __init__(self, path=balance.DEFAULT_PATH):
        pg.display.init()
        pg.font.init()
        font.cache_clear()
        self.window = pg.display.set_mode((1280,800), pg.RESIZABLE)
        self.canvas = pg.Surface(SIZE)
        self.viewport = pg.Rect(0,0,1280,800)
        self.document = BalanceDocument(path)
        self.defaults = balance.default_profile()
        self.section = 'buildings'
        self.identifier = 'factory'
        self.mode = 'data'
        self.search = self.field_search = ''
        self.item_page = self.field_page = self.tree_page = 0
        self.selected_technology = 'automated_factories'
        self.edit_target = None
        self.edit_text = ''
        self.cursor = 0
        self.select_all = False
        self.buttons, self.drop_slots = [], []
        self.mouse = (-1,-1)
        self.drag = None
        self.last_tech_click = None
        self.modal = None
        self.message = 'Change values, then Save. New campaigns use this profile; existing saves keep their own rules.'
        self.error = False
        self.running = True
        self.errors = []
        self.refresh()

    def refresh(self):
        self.errors = balance.validate(self.document.profile)
        pg.display.set_caption('Orion Reach — Balance editor'+(' *' if self.document.dirty else ''))

    def inform(self, message, error=False):
        self.message, self.error = str(message), error

    def button(self, key, label, rect, action, enabled=True, selected=False, size=13):
        rect = pg.Rect(rect)
        hover = rect.collidepoint(self.mouse)
        panel(self.canvas, rect, (26,43,55) if selected or hover else (12,24,34), GOLD if selected else LINE)
        color = GOLD if selected else INK if enabled else (92,105,115)
        text(self.canvas, shorten(label,rect.w-18,size), (rect.x+9,rect.y+(rect.h-font(size).get_height())//2),size,color)
        self.buttons.append((key,rect,action,enabled))

    def changed(self):
        self.refresh()
        self.inform('Draft updated. Save to use these settings in new campaigns.')

    def edit_value(self, path):
        if self.document.is_derived(self.section, self.identifier, path):
            self.inform('Calculated from Ship sizes, Ship modules and ship_scaling rules. Disable ship_scaling ENABLED for manual values.')
            return
        value = self.document.get(self.section,self.identifier,path)
        if type(value) is bool:
            self.document.set(self.section,self.identifier,path,not value)
            self.changed()
        elif options := self.document.options(self.section,path):
            self.modal = {'kind':'choices','title':self.document.field_label(path),'options':options,'path':path,'query':'','page':0}
            self.start_edit(('choice_search',), '')
        else:
            self.start_edit(('field',self.section,self.identifier,path), str(value))

    def start_edit(self,target,value):
        self.edit_target, self.edit_text = target, value
        self.cursor, self.select_all = len(value), True
        pg.key.start_text_input()

    def stop_edit(self):
        self.edit_target = None
        pg.key.stop_text_input()

    def commit_edit(self):
        if self.edit_target is None: return True
        target = self.edit_target
        if target[0]=='field':
            _,section,identifier,path = target
            old = self.document.get(section,identifier,path)
            value = self.edit_text
            try:
                if type(old) in (int,float):
                    float_field = type(old) is float or path[0] in ('industry_per_worker','income_per_population')
                    value = float(value) if float_field else int(value)
                    if not math.isfinite(value): raise ValueError
                self.document.set(section,identifier,path,value)
                self.changed()
            except ValueError:
                self.inform('Enter a finite number'+(' without decimals.' if type(old) is int else '.'),True)
                return False
        elif target[0]=='name':
            self.document.rename(self.edit_text)
            self.changed()
        self.stop_edit()
        return True

    def input_changed(self):
        if self.edit_target[0]=='search':
            self.search, self.item_page = self.edit_text, 0
        elif self.edit_target[0]=='field_search':
            self.field_search, self.field_page = self.edit_text, 0
        elif self.edit_target[0]=='choice_search':
            self.modal['query'], self.modal['page'] = self.edit_text, 0
        elif self.edit_target[0]=='path':
            self.modal['value'] = self.edit_text

    def input_box(self,rect,target,value,placeholder=''):
        rect = pg.Rect(rect)
        active = self.edit_target == target
        panel(self.canvas,rect,(19,33,45),GOLD if active else LINE)
        shown = self.edit_text if active else value
        if active and self.select_all:
            pg.draw.rect(self.canvas,(55,80,103),rect.inflate(-10,-8))
        # Long entries scroll with the caret while editing; stored text is complete.
        before = shown[:self.cursor] if active else shown
        offset = max(0,font(13).size(before)[0]-(rect.w-30)) if active else 0
        old_clip=self.canvas.get_clip()
        self.canvas.set_clip(rect.inflate(-12,-4))
        text(self.canvas,shown or placeholder,(rect.x+8-offset,rect.y+7),13,INK if shown else MUTED)
        if active and pg.time.get_ticks()%1000<600:
            x=rect.x+8+font(13).size(before)[0]-offset
            pg.draw.line(self.canvas,INK,(x,rect.y+6),(x,rect.bottom-6))
        self.canvas.set_clip(old_clip)
        self.buttons.append(('input_'+str(target),rect,lambda:self.start_edit(target,value),True))

    def select_section(self,section):
        self.section=section
        self.identifier=next(iter(self.document.profile['data'][section]))
        self.item_page=self.field_page=0
        self.search=self.field_search=''
        self.mode='data'

    def select_item(self,identifier):
        self.identifier=identifier
        self.field_page=0

    def action(self,fn):
        if not self.commit_edit(): return
        try:
            fn()
        except (balance.BalanceError,OSError,ValueError) as exc:
            self.inform(exc,True)

    def history(self,redo=False):
        (self.document.redo if redo else self.document.undo)()
        self.changed()

    def save(self,path=None):
        if not self.commit_edit(): return False
        try:
            self.document.save(path)
        except (balance.BalanceError,OSError) as exc:
            self.inform(exc,True)
            return False
        self.refresh()
        self.inform(f'Saved {self.document.path.name}. Start a new campaign to use this balance. Previous file kept as .bak.')
        return True

    def path_dialog(self,kind):
        self.modal={'kind':kind,'title':'Open balance profile' if kind=='open' else 'Save profile as','value':str(self.document.path)}
        self.start_edit(('path',),str(self.document.path))

    def confirm(self,title,callback):
        self.modal={'kind':'confirm','title':title,'action':callback}

    def open_request(self):
        if self.document.dirty:
            self.confirm('Discard the unsaved draft and open another profile?',lambda:self.path_dialog('open'))
        else: self.path_dialog('open')

    def finish_path(self):
        value=self.modal['value'].strip()
        kind=self.modal['kind']
        self.stop_edit()
        if not value:
            self.inform('Enter a JSON file path.',True)
            return
        destination=Path(value).expanduser()
        if not destination.is_absolute(): destination=balance.DEFAULT_PATH.parent/destination
        try:
            if kind=='open':
                if not destination.exists(): raise balance.BalanceError('That profile does not exist.')
                document=BalanceDocument(destination)
                self.document=document
                self.select_section(self.section)
                self.refresh()
                self.inform('Opened '+str(destination))
            elif destination.exists() and destination.resolve()!=self.document.path:
                self.confirm('Replace this existing profile? A .bak copy will be kept.',lambda:self.save(destination))
                return
            elif not self.save(destination): return
            self.modal=None
        except (balance.BalanceError,OSError) as exc:
            self.inform(exc,True)

    def request_exit(self):
        if not self.commit_edit(): return
        if self.document.dirty:
            self.modal={'kind':'exit','title':'Save your balance changes before closing?'}
        else: self.running=False

    def save_exit(self):
        if self.save(): self.running=False

    def tree_mode(self):
        self.mode='tree'
        self.section='technologies'
        self.identifier=self.selected_technology

    def edit_technology(self):
        self.select_section('technologies')
        self.identifier=self.selected_technology
        keys=list(self.document.profile['data']['technologies'])
        self.item_page=keys.index(self.identifier)//14

    def data_mode(self):
        if self.mode=='tree':
            self.edit_technology()
        else:
            self.mode='data'

    def draw(self):
        self.canvas.fill(BG)
        self.buttons=[]
        self.drop_slots=[]
        text(self.canvas,'ORION REACH', (24,16),11,CYAN,'mono',2)
        text(self.canvas,'Balance editor',(24,32),25,INK,'title')
        self.input_box((570,22,560,32),('name',),self.document.profile['name'])
        text(self.canvas,'UNSAVED CHANGES' if self.document.dirty else 'PROFILE SAVED' if self.document.path.exists() else 'BUILT-IN DEFAULTS', (1416,32),11,GOLD if self.document.dirty else GREEN,'mono',right=True)
        for key,label,x,w,action in (
            ('save','Save · Ctrl+S',24,132,self.save),('save_as','Save as',168,94,lambda:self.path_dialog('save_as')),
            ('open','Open',274,80,self.open_request),('undo','Undo',366,78,self.history),('redo','Redo',456,78,lambda:self.history(True)),
            ('reset_all','Reset all',546,106,lambda:self.confirm('Reset the entire draft to the built-in balance?',lambda:(self.document.reset_all(),self.changed()))),
            ('data','Values',1026,130,self.data_mode),('tree','Research tree',1168,248,self.tree_mode)):
            self.button(key,label,(x,68,w,34),action,selected=(key=='tree' and self.mode=='tree') or (key=='data' and self.mode=='data'))
        self.button('validate','Validate',(664,68,110,34),lambda:(self.refresh(),self.inform('\n'.join(self.errors[:5]) if self.errors else 'Valid profile: all references, research tiers and value ranges are consistent.',bool(self.errors))))
        panel(self.canvas,(24,116,204,704))
        text(self.canvas,'CATALOGUES', (38,132),10,MUTED,'mono',1)
        for index,(key,label) in enumerate(balance.LABELS.items()):
            step = min(33, 650//len(balance.LABELS))
            self.button('section_'+key,label,(34,160+index*step,184,step-3),lambda k=key:self.select_section(k),selected=self.section==key,size=12)
        if self.mode=='tree': self.draw_tree()
        else: self.draw_data()
        text(self.canvas,shorten(self.message.replace('\n',' · '),1376,13),(24,838),13,RED if self.error else INK)
        status=f'{len(self.errors)} validation issue(s): {self.errors[0]}' if self.errors else 'Valid profile · Restart or start a new game to apply · Existing campaigns retain their saved balance'
        text(self.canvas,shorten(status,1376,11),(24,864),11,RED if self.errors else GREEN)
        if self.modal: self.draw_modal()

    def draw_data(self):
        entries=self.document.profile['data'][self.section]
        filtered=[key for key,v in entries.items() if self.search.casefold() in (key+' '+v.get('name',v.get('traits',''))).casefold()]
        self.item_page=min(self.item_page,max(0,(len(filtered)-1)//14))
        panel(self.canvas,(244,116,320,704))
        text(self.canvas,balance.LABELS[self.section],(260,132),19,INK)
        self.input_box((260,170,288,32),('search',),self.search,'Find an item…')
        for index,key in enumerate(filtered[self.item_page*14:self.item_page*14+14]):
            name=entries[key].get('name',key.replace('_',' ').title())
            changed=entries[key]!=self.defaults['data'][self.section][key]
            self.button('item_'+key,('• ' if changed else '')+name,(260,214+index*38,288,33),lambda k=key:self.select_item(k),selected=key==self.identifier,size=12)
        self.button('items_previous','←',(260,769,46,32),lambda:setattr(self,'item_page',max(0,self.item_page-1)),enabled=self.item_page>0)
        text(self.canvas,f'{self.item_page+1} / {max(1,math.ceil(len(filtered)/14))} · {len(filtered)} items',(317,779),11,MUTED)
        self.button('items_next','→',(502,769,46,32),lambda:setattr(self,'item_page',self.item_page+1),enabled=(self.item_page+1)*14<len(filtered))
        panel(self.canvas,(580,116,836,704))
        entry=self.document.entry(self.section,self.identifier)
        text(self.canvas,shorten(entry.get('name',self.identifier.replace('_',' ').title()),770,25),(600,130),25,INK)
        text(self.canvas,self.identifier+' · Click a value to edit · Enter applies · Esc cancels',(600,168),11,MUTED)
        self.input_box((600,194,794,32),('field_search',),self.field_search,'Filter fields, e.g. cost, damage, effects…')
        rows=self.document.fields(self.section,self.identifier,self.field_search)
        self.field_page=min(self.field_page,max(0,(len(rows)-1)//14))
        for index,(path,value) in enumerate(rows[self.field_page*14:self.field_page*14+14]):
            y=242+index*36
            label=self.document.field_label(path)
            text(self.canvas,shorten(label,306,12),(600,y+9),12,MUTED)
            target=('field',self.section,self.identifier,path)
            if self.edit_target==target:
                self.input_box((922,y,472,31),target,str(value))
            else:
                shown='On' if value is True else 'Off' if value is False else 'No requirement' if value is None else str(value)
                options=self.document.options(self.section,path)
                if options: shown=dict(options).get(value,shown)+'  ▾'
                self.button('field_'+'.'.join(map(str,path)),shown,(922,y,472,31),lambda p=path:self.edit_value(p),size=12)
        self.button('fields_previous','←',(600,769,46,32),lambda:setattr(self,'field_page',max(0,self.field_page-1)),enabled=self.field_page>0)
        text(self.canvas,f'Fields {self.field_page+1}/{max(1,math.ceil(len(rows)/14))}',(658,779),11,MUTED)
        self.button('fields_next','→',(754,769,46,32),lambda:setattr(self,'field_page',self.field_page+1),enabled=(self.field_page+1)*14<len(rows))
        if self.section=='branches':
            self.button('branch_earlier','Move earlier',(826,769,134,32),lambda:(self.document.reorder_branch(self.identifier,-1),self.changed()))
            self.button('branch_later','Move later',(970,769,128,32),lambda:(self.document.reorder_branch(self.identifier,1),self.changed()))
        elif self.section=='technologies':
            self.button('show_tree','Move in tree',(826,769,160,32),lambda:(setattr(self,'selected_technology',self.identifier),self.tree_mode()))
            text(self.canvas,'Cost override 0 = tier cost',(996,781),10,MUTED)
        self.button('reset_item','Reset item',(1236,769,158,32),lambda:(self.document.reset_entry(self.section,self.identifier),self.changed()))

    def draw_tree(self):
        panel(self.canvas,(244,116,1172,704))
        text(self.canvas,'Research tree',(262,130),25,INK,'title')
        text(self.canvas,'Drag a technology to another slot. Occupied slots swap. Double-click to edit values.',(262,168),12,MUTED)
        branches=self.document.profile['branch_order']
        data=self.document.profile['data']
        self.tree_page=min(self.tree_page,(len(branches)-1)//3)
        self.button('tree_previous','←',(1140,127,45,32),lambda:setattr(self,'tree_page',max(0,self.tree_page-1)),enabled=self.tree_page>0)
        text(self.canvas,f'{self.tree_page+1} / 3',(1200,137),12,MUTED)
        self.button('tree_next','→',(1254,127,45,32),lambda:setattr(self,'tree_page',self.tree_page+1),enabled=self.tree_page<2)
        self.button('edit_technology','Edit selected',(1260,164,138,30),self.edit_technology)
        for column,branch in enumerate(branches[self.tree_page*3:self.tree_page*3+3]):
            x=324+column*364
            text(self.canvas,shorten(data['branches'][branch]['name'],332,17),(x+8,214),17,GOLD)
            for tier in range(1,9):
                y=248+(tier-1)*69
                panel(self.canvas,(x,y,352,65),(10,22,32))
                ids=self.document.choices(branch,tier)
                for slot in range(2):
                    rect=pg.Rect(x+7,y+5+slot*28,338,25)
                    self.drop_slots.append((rect,branch,tier,slot))
                    if slot<len(ids):
                        key=ids[slot]
                        entry=data['technologies'][key]
                        cost=entry['cost_override'] or data['research_costs'][str(tier)]['cost']
                        self.button('tech_'+key,entry['name'],rect,lambda k=key:setattr(self,'selected_technology',k),selected=key==self.selected_technology,size=11)
                        # Cost is intentionally in the selected-node caption below, not over the name.
                    else:
                        text(self.canvas,'Empty slot',(rect.x+7,rect.y+7),10,(67,84,99))
                    if self.drag and rect.collidepoint(self.mouse): pg.draw.rect(self.canvas,CYAN,rect,2)
                if column==0:
                    text(self.canvas,str(tier),(266,y+10),19,INK)
                    text(self.canvas,str(data['research_costs'][str(tier)]['cost'])+' RP',(260,y+38),10,MUTED)
        chosen=data['technologies'][self.selected_technology]
        cost=chosen['cost_override'] or data['research_costs'].get('ascension' if self.selected_technology=='ascension_theory' else str(chosen['tier']),{}).get('cost','?')
        self.message=f'{chosen["name"]} · {chosen["branch"]} · tier {chosen["tier"]} · {cost} RP · Ascension remains the separate finale.' if not self.error else self.message

    def close_modal(self):
        self.stop_edit()
        self.modal=None

    def choose_option(self,value):
        path=self.modal['path']
        self.document.set(self.section,self.identifier,path,value)
        self.close_modal()
        self.changed()

    def draw_modal(self):
        fade=pg.Surface(SIZE,pg.SRCALPHA)
        fade.fill((0,0,0,175))
        self.canvas.blit(fade,(0,0))
        self.buttons=[]
        modal=self.modal
        if modal['kind']=='choices':
            panel(self.canvas,(318,140,804,612),(12,24,35),GOLD)
            text(self.canvas,modal['title'],(342,159),24,INK)
            self.input_box((342,204,756,32),('choice_search',),modal['query'],'Search options…')
            options=[(k,v) for k,v in modal['options'] if modal['query'].casefold() in (str(k)+' '+v).casefold()]
            modal['page']=min(modal['page'],max(0,(len(options)-1)//11))
            for index,(value,label) in enumerate(options[modal['page']*11:modal['page']*11+11]):
                self.button('choice_'+str(value),label,(342,250+index*37,756,32),lambda v=value:self.choose_option(v))
            self.button('choice_previous','←',(342,688,50,35),lambda:modal.update(page=max(0,modal['page']-1)),enabled=modal['page']>0)
            self.button('choice_next','→',(406,688,50,35),lambda:modal.update(page=modal['page']+1),enabled=(modal['page']+1)*11<len(options))
            self.button('modal_cancel','Cancel',(966,688,132,35),self.close_modal)
        else:
            panel(self.canvas,(270,298,900,268),(12,24,35),GOLD)
            text(self.canvas,shorten(modal['title'],846,22),(296,320),22,INK)
            if modal['kind'] in ('open','save_as'):
                self.input_box((296,385,846,36),('path',),modal['value'])
                text(self.canvas,'Full path, or a path relative to the game folder. Profiles are JSON files.',(296,438),12,MUTED)
                self.button('modal_apply','Open' if modal['kind']=='open' else 'Save',(830,496,140,40),self.finish_path)
            elif modal['kind']=='exit':
                self.button('modal_save','Save and close',(632,496,174,40),self.save_exit)
                self.button('modal_discard','Discard',(820,496,140,40),lambda:setattr(self,'running',False))
            else:
                def confirm():
                    callback=modal['action']
                    self.close_modal()
                    callback()
                self.button('modal_confirm','Continue',(830,496,140,40),confirm)
            self.button('modal_cancel','Cancel',(994,496,148,40),self.close_modal)

    def coordinates(self,pos):
        return ((pos[0]-self.viewport.x)*1440/self.viewport.w,(pos[1]-self.viewport.y)*900/self.viewport.h)

    def handle_event(self,event):
        if event.type==pg.QUIT:
            self.request_exit()
        elif event.type==pg.MOUSEMOTION:
            self.mouse=self.coordinates(event.pos)
        elif event.type==pg.TEXTINPUT and self.edit_target:
            value=''.join(c for c in event.text if c.isprintable())
            if self.select_all: self.edit_text,self.cursor='',0
            self.edit_text=self.edit_text[:self.cursor]+value+self.edit_text[self.cursor:]
            self.cursor+=len(value)
            self.select_all=False
            self.input_changed()
        elif event.type==pg.KEYDOWN:
            self.key(event)
        elif event.type==pg.MOUSEWHEEL:
            if self.modal:
                if self.modal['kind']=='choices': self.modal['page']=max(0,self.modal['page']-event.y)
            elif self.mode=='tree': self.tree_page=max(0,min(2,self.tree_page-event.y))
            elif self.mouse[0]<570: self.item_page=max(0,self.item_page-event.y)
            else: self.field_page=max(0,self.field_page-event.y)
        elif event.type==pg.MOUSEBUTTONDOWN and event.button==1:
            self.mouse=self.coordinates(event.pos)
            if not self.commit_edit(): return
            for key,rect,action,enabled in reversed(self.buttons):
                if enabled and rect.collidepoint(self.mouse):
                    if key.startswith('tech_') and not self.modal:
                        self.selected_technology=key[5:]
                        now=pg.time.get_ticks()
                        double=(self.last_tech_click is not None and self.last_tech_click[0]==key
                                and now-self.last_tech_click[1]<400)
                        self.last_tech_click=(key,now)
                        if double or getattr(event,'clicks',1)>1:
                            self.drag=None
                            self.edit_technology()
                        else: self.drag=(key[5:],self.mouse)
                    else: self.action(action)
                    break
        elif event.type==pg.MOUSEBUTTONUP and event.button==1 and self.drag:
            identifier,start=self.drag
            self.drag=None
            self.mouse=self.coordinates(event.pos)
            if math.dist(start,self.mouse)>6:
                self.last_tech_click=None
                for rect,branch,tier,slot in self.drop_slots:
                    if rect.collidepoint(self.mouse):
                        self.action(lambda:(self.document.move_technology(identifier,branch,tier,slot),self.changed()))
                        break

    def key(self,event):
        ctrl=bool(event.mod & pg.KMOD_CTRL)
        if self.edit_target:
            if ctrl and event.key==pg.K_a: self.select_all=True
            elif event.key==pg.K_ESCAPE:
                self.stop_edit()
                if self.modal and self.modal['kind']=='choices': self.close_modal()
            elif event.key in (pg.K_RETURN,pg.K_KP_ENTER):
                if self.modal and self.modal['kind'] in ('open','save_as'): self.finish_path()
                else: self.commit_edit()
            elif event.key==pg.K_TAB: self.commit_edit()
            elif event.key in (pg.K_BACKSPACE,pg.K_DELETE):
                if self.select_all: self.edit_text,self.cursor='',0
                elif event.key==pg.K_BACKSPACE and self.cursor:
                    self.edit_text=self.edit_text[:self.cursor-1]+self.edit_text[self.cursor:]
                    self.cursor-=1
                elif event.key==pg.K_DELETE: self.edit_text=self.edit_text[:self.cursor]+self.edit_text[self.cursor+1:]
                self.select_all=False
                self.input_changed()
            elif event.key in (pg.K_LEFT,pg.K_RIGHT,pg.K_HOME,pg.K_END):
                self.cursor=0 if event.key==pg.K_HOME else len(self.edit_text) if event.key==pg.K_END else max(0,min(len(self.edit_text),self.cursor+(-1 if event.key==pg.K_LEFT else 1)))
                self.select_all=False
            elif ctrl and event.key in (pg.K_c,pg.K_v):
                try:
                    if event.key==pg.K_c: pg.scrap.put_text(self.edit_text)
                    else: self.handle_event(pg.event.Event(pg.TEXTINPUT,text=pg.scrap.get_text()))
                except (pg.error,AttributeError): pass
            elif ctrl and event.key==pg.K_s and not self.modal: self.save()
            return
        if event.key==pg.K_ESCAPE:
            if self.modal: self.close_modal()
            else: self.request_exit()
        elif self.modal: return
        elif ctrl and event.key==pg.K_s:
            self.path_dialog('save_as') if event.mod & pg.KMOD_SHIFT else self.save()
        elif ctrl and event.key==pg.K_o: self.open_request()
        elif ctrl and event.key==pg.K_z: self.history()
        elif ctrl and event.key==pg.K_y: self.history(True)

    def present(self):
        w,h=self.window.get_size()
        scale=min(w/1440,h/900)
        self.viewport=pg.Rect(0,0,max(1,round(1440*scale)),max(1,round(900*scale)))
        self.viewport.center=(w//2,h//2)
        self.window.fill((0,0,0))
        self.window.blit(pg.transform.smoothscale(self.canvas,self.viewport.size),self.viewport)
        pg.display.flip()

    def run(self):
        clock=pg.time.Clock()
        self.draw()
        self.present()
        while self.running:
            for event in pg.event.get():
                self.handle_event(event)
                self.draw()
            self.draw()
            self.present()
            clock.tick(30)
