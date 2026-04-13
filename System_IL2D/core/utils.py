import json
import os

MAP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'map')
MOB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mob')
DIALOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'friendlymobdialogue')
SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saves')
PLAYER_FILE = os.path.join(MOB_DIR, 'player.json')
NPC_FILE = os.path.join(MOB_DIR, 'npc.json')

def load_json(path):
    # allow UTF-8 with BOM
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def clamp(val, minv, maxv):
    return max(minv, min(val, maxv))
