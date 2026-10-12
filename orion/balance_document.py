"""Editor document operations, independent of the window and active campaign."""
from copy import deepcopy
from pathlib import Path
from . import balance


class BalanceDocument:
    def __init__(self, path=balance.DEFAULT_PATH):
        self.path = Path(path).expanduser().resolve()
        self.profile = balance.read_profile(self.path, missing_ok=True)
        self.saved = deepcopy(self.profile)
        self.disk_text = self.path.read_text(encoding='utf-8') if self.path.exists() else ''
        self.undo_stack, self.redo_stack = [], []

    @property
    def dirty(self):
        return self.profile != self.saved

    def checkpoint(self):
        self.undo_stack.append(deepcopy(self.profile))
        del self.undo_stack[:-100]
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.profile)
            self.profile = self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.profile)
            self.profile = self.redo_stack.pop()

    def entry(self, section, identifier):
        return self.profile['data'][section][identifier]

    def get(self, section, identifier, path):
        value = self.entry(section, identifier)
        for key in path:
            value = value.get(key, 0) if isinstance(value, dict) else value[key]
        return value

    def set(self, section, identifier, path, value):
        if self.get(section, identifier, path) == value:
            return
        self.checkpoint()
        entry = self.entry(section, identifier)
        for key in path[:-1]: entry = entry[key]
        entry[path[-1]] = value

    def reset_entry(self, section, identifier):
        self.checkpoint()
        self.profile['data'][section][identifier] = balance.default_profile()['data'][section][identifier]

    def reset_all(self):
        self.checkpoint()
        self.profile = balance.default_profile()

    def rename(self, name):
        if not name.strip() or name == self.profile['name']: return
        self.checkpoint()
        self.profile['name'] = name.strip()

    def choices(self, branch, tier):
        entries = self.profile['data']['technologies']
        return sorted((key for key,v in entries.items() if v['branch']==branch and v['tier']==tier), key=lambda key: entries[key]['order'])

    def move_technology(self, identifier, branch, tier, slot=0):
        if identifier == 'ascension_theory' or branch not in self.profile['branch_order'] or type(tier) is not int or not 1 <= tier <= 8 or slot not in (0,1):
            raise balance.BalanceError('Choose a normal research branch, tier 1–8 and one of its two slots.')
        item = self.entry('technologies', identifier)
        source = (item['branch'], item['tier'], self.choices(item['branch'],item['tier']).index(identifier))
        targets = self.choices(branch, tier)
        target = targets[slot] if slot < len(targets) else None
        if target == identifier: return
        self.checkpoint()
        # Original catalogues use equal order values and stable dictionary order.
        # Assign both cells explicit slot numbers before swapping their entries.
        for cell in ((source[0],source[1]),(branch,tier)):
            for position,key in enumerate(self.choices(*cell)):
                self.entry('technologies',key)['order']=position
        if target is not None:
            other = self.entry('technologies', target)
            other['branch'], other['tier'], other['order'] = source
        item['branch'], item['tier'], item['order'] = branch, tier, slot

    def reorder_branch(self, identifier, direction):
        order = self.profile['branch_order']
        index = order.index(identifier)
        target = index+direction
        if 0 <= target < len(order):
            self.checkpoint()
            order[index], order[target] = order[target], order[index]

    def fields(self, section, identifier, query=''):
        rows = []
        for key,value in self.entry(section,identifier).items():
            if section == 'buildings' and key == 'unique':
                continue  # Legacy save metadata; one per planet is now a fixed rule.
            if (section == 'hulls' and key in ('capacity', 'weapon', 'defense', 'support')
                    or section == 'modules' and key == 'space'):
                continue  # Only retained to validate legacy blueprints.
            if key == 'effects':
                rows.extend((('effects',effect),value.get(effect,0)) for effect in balance.effect_keys())
            elif isinstance(value,list):
                rows.extend(((key,index),item) for index,item in enumerate(value))
            else: rows.append(((key,),value))
        return [(p,v) for p,v in rows if query.casefold() in self.field_label(p).casefold()]

    @staticmethod
    def field_label(path):
        return ' / '.join(str(p+1) if type(p) is int else p.replace('_',' ').title() for p in path)

    def options(self, section, path):
        field = path[0]
        data = self.profile['data']
        if field == 'technology': return [(None,'Available from the start')]+[(k,v['name']) for k,v in data['technologies'].items()]
        if field == 'branch': return [(k,data['branches'][k]['name']) for k in self.profile['branch_order']]+[('ascension','Ascension finale')]
        if field == 'category': return [(v,v.title()) for v in ('weapon','defense','support')]
        if field == 'module_size': return [(v,v.title()) for v in ('small','medium','heavy')]
        if field == 'weapon' and section not in ('hulls',): return [(k,v['name']) for k,v in data['weapons'].items()]
        if field == 'development': return [(k,v['name']) for k,v in data['buildings'].items()]
        if field == 'research_priority': return [(k,data['branches'][k]['name']) for k in self.profile['branch_order']]
        return None

    def save(self, path=None):
        destination = Path(path).expanduser().resolve() if path is not None else self.path
        expected = self.disk_text if destination == self.path else None
        content = balance.write_profile(destination,self.profile,expected=expected)
        self.path, self.disk_text = destination, content
        self.saved = deepcopy(self.profile)
