from __future__ import annotations
import re
import warnings
from collections import OrderedDict
from typing import TYPE_CHECKING
from .base import BaseHelper
if TYPE_CHECKING:
    from typing import Optional, Dict, List, Any
    from brkraw.api.analyzer import BaseAnalyzer

class Recipe(BaseHelper):
    def __init__(self, target: 'BaseAnalyzer', recipe: dict, legacy: bool = False, 
                 startup_scripts:Optional[List[str]] = None):
        self.target = target
        self.recipe = recipe
        self.results = OrderedDict()
        self.backward_comp = legacy
        self.startup_scripts = startup_scripts
        self._parse_recipe()
        
    def _parse_recipe(self):
        for key, value in self.recipe.items():
            self.results[key] = self._eval_value(value)
    
    def _eval_value(self, value: Any):
        if isinstance(value, str):
            value = self._process_str(value)
        elif isinstance(value, list):
            value = self._process_list(value)
        elif isinstance(value, dict):
            value = self._process_dict(value)
        return value
    
    def _legacy_parser(self, param_key: str):
        for pars in ['acqp', 'method', 'visu_pars']:
            value = getattr(self.target, pars).get(param_key)
            if value is not None:
                return value
        return param_key
    
    def _process_str(self, str_obj: str):
        if self.backward_comp:
            return self._legacy_parser(str_obj)
        ptrn = r'(?P<attr>^[a-zA-Z][a-zA-Z0-9_]*)\.(?P<key>[a-zA-Z][a-zA-Z0-9_]*)'
        if matched := re.match(ptrn, str_obj):
            attr = getattr(self.target, matched['attr'])
            return attr.get(matched['key'], None)
        else:
            return str_obj
    
    def _process_list(self, list_obj: List):
        for c in list_obj:
            processed = self._eval_value(c)
            if processed is not None:
                return processed
        return None
    
    def _process_dict(self, dict_obj: Dict):
        script_cmd = 'Equation' if self.backward_comp else 'script'
        if script_cmd in dict_obj.keys():
            return self._process_dict_case_script(dict_obj, script_cmd)
        elif 'key' in dict_obj.keys():
            return self._process_dict_case_pick_from_list(dict_obj)
        else:
            processed = {}
            for key, value in dict_obj.items():
                processed[key] = self._eval_value(value)
            return processed
        
    def _process_dict_case_script(self, dict_obj: Dict, script_cmd: List[str]):
        script = dict_obj.pop(script_cmd)
        if self.startup_scripts:
            for s in self.startup_scripts:
                exec(s)
        for key, value in dict_obj.items():
            value = self._eval_value(value)
            if value == None:
                return None
            exec(f'global {key}')
            exec(f'{key} = {value}')
        exec(f"output = {script}", globals(), locals())
        return locals()['output']
    
    def _process_dict_case_pick_from_list(self, dict_obj: Dict):
        key = dict_obj.pop('key')
        value = self._process_str(key)
        if not isinstance(value, list):
            warnings.warn(f"The value returned from '{key}' is not of type 'list'.", UserWarning)
            return None
        if 'where' in dict_obj.keys():
            hint = self._eval_value(dict_obj.pop('where'))
            return value.index(hint) if hint in value else None
        elif 'idx' in dict_obj.keys():
            idx = self._eval_value(dict_obj.pop('idx'))
            return value[idx] if idx < len(value) else None
    
    def get(self):
        return self.results