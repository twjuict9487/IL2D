import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), 'Pre_coded_data')
MAP_DIR = os.path.join(DATA_DIR, 'map')
MOB_DIR = os.path.join(DATA_DIR, 'mob_related')
DIALOG_DIR = os.path.join(DATA_DIR, 'npc_related', 'dialogue')
GAME_DATA_DIR = os.path.join(DATA_DIR, 'game_data')
SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saves')
PLAYER_FILE = os.path.join(MOB_DIR, 'player.json')
NPC_FILE = os.path.join(MOB_DIR, 'npc.json')
ITEMS_FILE = os.path.join(GAME_DATA_DIR, 'items.json')
SHOP_FILE = os.path.join(GAME_DATA_DIR, 'shop.json')
SPELLS_FILE = os.path.join(GAME_DATA_DIR, 'spells.json')
OBJECTIVES_FILE = os.path.join(GAME_DATA_DIR, 'objectives.json')
ROGUE_FILE = os.path.join(GAME_DATA_DIR, 'rogue.json')
CONFIG_FILE = os.path.join(GAME_DATA_DIR, 'config.json')

def load_json(path):
    # allow UTF-8 with BOM
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def clamp(val, minv, maxv):
    return max(minv, min(val, maxv))
