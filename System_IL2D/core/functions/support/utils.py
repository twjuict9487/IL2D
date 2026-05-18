import json
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
CORE_DIR = os.path.join(_BASE_DIR, 'core')
DATA_DIR = os.path.join(CORE_DIR, 'Pre_coded_data')
MODS_DIR = os.path.join(_BASE_DIR, 'mods')
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
    for base in (DATA_DIR, MODS_DIR):
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs.sort()
            files.sort()
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

BLOCKTYPE_FILE = _resolve_file([
    os.path.join('map', 'blocktype.json'),
], fallback_name='blocktype.json')

MOBS_FILE = _resolve_file([
    os.path.join('entity', 'mob_related', 'mobs.json'),
], fallback_name='mobs.json')

def load_json(path):
    # allow UTF-8 with BOM
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def _iter_mod_map_dirs():
    if not os.path.isdir(MODS_DIR):
        return
    for root, dirs, _files in os.walk(MODS_DIR):
        for d in dirs:
            if d == "maps":
                yield os.path.join(root, d)


def _iter_mod_dialog_dirs():
    if not os.path.isdir(MODS_DIR):
        return
    for root, dirs, _files in os.walk(MODS_DIR):
        for d in dirs:
            if d == "dialogue":
                yield os.path.join(root, d)


def resolve_map_file(map_name):
    primary = os.path.join(MAP_DIR, map_name)
    if os.path.isfile(primary):
        return primary
    for map_dir in _iter_mod_map_dirs():
        candidate = os.path.join(map_dir, map_name)
        if os.path.isfile(candidate):
            return candidate
    return primary


def iter_all_map_files():
    seen = set()
    if os.path.isdir(MAP_DIR):
        for fname in os.listdir(MAP_DIR):
            if not fname.lower().endswith(".json"):
                continue
            fpath = os.path.join(MAP_DIR, fname)
            if os.path.isfile(fpath):
                key = _norm_path(fpath)
                if key not in seen:
                    seen.add(key)
                    yield fpath
    for map_dir in _iter_mod_map_dirs():
        for fname in os.listdir(map_dir):
            if not fname.lower().endswith(".json"):
                continue
            fpath = os.path.join(map_dir, fname)
            if os.path.isfile(fpath):
                key = _norm_path(fpath)
                if key not in seen:
                    seen.add(key)
                    yield fpath


def resolve_dialog_file(npc_id):
    filename = f"{npc_id}.json"
    primary = os.path.join(DIALOG_DIR, filename)
    if os.path.isfile(primary):
        return primary
    for dialog_dir in _iter_mod_dialog_dirs():
        candidate = os.path.join(dialog_dir, filename)
        if os.path.isfile(candidate):
            return candidate
    return primary

def clamp(val, minv, maxv):
    return max(minv, min(val, maxv))
