import json
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
CORE_DIR = os.path.join(_BASE_DIR, 'core')
DATA_DIR = os.path.join(CORE_DIR, 'Pre_coded_data')
SAVE_DIR = os.path.join(_BASE_DIR, 'saves')


def _norm_path(path):
    return os.path.normcase(os.path.normpath(path))


def _resolve_dir(candidates):
    for rel in candidates:
        p = os.path.join(DATA_DIR, rel)
        if os.path.isdir(p):
            return p
    return None


def _find_file_by_name(name):
    for root, _, files in os.walk(DATA_DIR):
        if name in files:
            return os.path.join(root, name)
    return None


def _resolve_file(candidates, fallback_name=None):
    for rel in candidates:
        p = os.path.join(DATA_DIR, rel)
        if os.path.isfile(p):
            return p
    if fallback_name:
        p = _find_file_by_name(fallback_name)
        if p:
            return p
    # keep deterministic path even if file missing (caller will raise when reading)
    if candidates:
        return os.path.join(DATA_DIR, candidates[0])
    return os.path.join(DATA_DIR, fallback_name or "")


MAP_DIR = _resolve_dir([
    'map',
]) or os.path.join(DATA_DIR, 'map')

MOB_DIR = _resolve_dir([
    os.path.join('entity', 'mob_related'),
    'mob_related',
]) or os.path.join(DATA_DIR, os.path.join('entity', 'mob_related'))

DIALOG_DIR = _resolve_dir([
    os.path.join('entity', 'npc_related', 'dialogue'),
    os.path.join('npc_related', 'dialogue'),
]) or os.path.join(DATA_DIR, os.path.join('entity', 'npc_related', 'dialogue'))

GAME_DATA_DIR = _resolve_dir([
    'game_data',
]) or os.path.join(DATA_DIR, 'game_data')

PLAYER_FILE = _resolve_file([
    os.path.join('entity', 'player_related', 'player.json'),
    os.path.join('mob_related', 'player.json'),
    os.path.join('entity', 'mob_related', 'player.json'),
], fallback_name='player.json')

NPC_FILE = _resolve_file([
    os.path.join('entity', 'npc_related', 'npc.json'),
    os.path.join('mob_related', 'npc.json'),
    os.path.join('entity', 'npc.json'),
], fallback_name='npc.json')

ITEMS_FILE = _resolve_file([
    os.path.join('game_data', 'items.json'),
], fallback_name='items.json')

SHOP_FILE = _resolve_file([
    os.path.join('game_data', 'shop.json'),
], fallback_name='shop.json')

SPELLS_FILE = _resolve_file([
    os.path.join('game_data', 'spells.json'),
], fallback_name='spells.json')

OBJECTIVES_FILE = _resolve_file([
    os.path.join('game_data', 'objectives.json'),
], fallback_name='objectives.json')

ROGUE_FILE = _resolve_file([
    os.path.join('game_data', 'rogue.json'),
], fallback_name='rogue.json')

CONFIG_FILE = _resolve_file([
    os.path.join('game_data', 'config.json'),
], fallback_name='config.json')

def load_json(path):
    # allow UTF-8 with BOM
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def clamp(val, minv, maxv):
    return max(minv, min(val, maxv))
