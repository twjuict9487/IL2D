import json
import os

MAP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'map')
MOB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mob')
DIALOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'friendlymobdialogue')
SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saves')

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def clamp(val, minv, maxv):
    return max(minv, min(val, maxv))
