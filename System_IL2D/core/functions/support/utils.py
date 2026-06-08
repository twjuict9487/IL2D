import json
import os
from .asset_resolver import (
    ensure_primed_from_file,
    resolve,
    resolve_candidates,
    resolve_map_candidates,
    resolve_dialog_candidates,
    iter_all_map_files as _iter_indexed_map_files,
    get_index,
)


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
CORE_DIR = os.path.join(_BASE_DIR, 'core')
MODS_DIR = os.path.join(_BASE_DIR, 'mods')
SAVE_DIR = os.path.join(_BASE_DIR, 'saves')

ensure_primed_from_file(__file__)


def _norm_path(path):
    return os.path.normcase(os.path.normpath(path))


def _first_existing(paths):
    for p in paths or []:
        if p and os.path.isfile(p):
            return p
    return None


def _first_or_empty(paths):
    return paths[0] if paths else ""


def _folder_for_file(path):
    return os.path.dirname(path) if path else ""


def _resolve_json_prefer(name_stem):
    cands = resolve_candidates("json", f"{name_stem}.json") + resolve_candidates("json", name_stem)
    return _first_existing(cands) or _first_or_empty(cands)


def _resolve_json_prefer_many(*name_stems):
    cands = []
    for stem in name_stems:
        cands.extend(resolve_candidates("json", f"{stem}.json"))
        cands.extend(resolve_candidates("json", stem))
    return _first_existing(cands) or _first_or_empty(cands)


def _resolve_dir_by_key(dir_key):
    idx = get_index() or {}
    folder_map = idx.get("folders", {})
    entries = folder_map.get((dir_key or "").lower(), [])
    for ent in entries:
        p = ent.get("path")
        if p and os.path.isdir(p):
            return p
    return ""


MAP_DIR = _resolve_dir_by_key("map")
MOB_DIR = _resolve_dir_by_key("mob_related")
DIALOG_DIR = _resolve_dir_by_key("dialogue")
GAME_DATA_DIR = _resolve_dir_by_key("game_data")

PLAYER_FILE = _resolve_json_prefer("player")
NPC_FILE = _resolve_json_prefer("npc")
ITEMS_FILE = _resolve_json_prefer("items")
SHOP_FILE = _resolve_json_prefer("shop")
SPELLS_FILE = _resolve_json_prefer("spells")
MAGICS_FILE = _resolve_json_prefer("magics")
OBJECTIVES_FILE = _resolve_json_prefer("objectives")
MISSIONS_FILE = _resolve_json_prefer("missions")
MISSION_TYPES_FILE = _resolve_json_prefer_many("mission_types", "MTS")
MISSION_RUNTIME_REGISTRY_FILE = _resolve_json_prefer_many("mission_runtime_registry", "MRER")
MISSIONS_TYPE_FILE = MISSION_RUNTIME_REGISTRY_FILE
LORE_ARCHIVE_FILE = _resolve_json_prefer("lore_archive")
ROGUE_FILE = _resolve_json_prefer("rogue")
CONFIG_FILE = _resolve_json_prefer("config")
BLOCKTYPE_FILE = _resolve_json_prefer("blocktype")
MOBS_FILE = _resolve_json_prefer("mobs")


def load_json(path):
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
    candidates = resolve_map_candidates(map_name)
    if candidates:
        return candidates[0]
    if MAP_DIR:
        primary = os.path.join(MAP_DIR, map_name)
        if os.path.isfile(primary):
            return primary
        return primary
    return ""


def iter_all_map_files():
    yielded = set()
    for fpath in _iter_indexed_map_files():
        key = _norm_path(fpath)
        if key in yielded:
            continue
        yielded.add(key)
        yield fpath
    if not yielded and MAP_DIR and os.path.isdir(MAP_DIR):
        for fname in os.listdir(MAP_DIR):
            if not fname.lower().endswith(".json"):
                continue
            fpath = os.path.join(MAP_DIR, fname)
            if os.path.isfile(fpath):
                key = _norm_path(fpath)
                if key not in yielded:
                    yielded.add(key)
                    yield fpath


def resolve_dialog_file(npc_id):
    candidates = resolve_dialog_candidates(npc_id)
    if candidates:
        return candidates[0]
    filename = f"{npc_id}.json"
    if DIALOG_DIR:
        primary = os.path.join(DIALOG_DIR, filename)
        if os.path.isfile(primary):
            return primary
        return primary
    return ""


def clamp(val, minv, maxv):
    return max(minv, min(val, maxv))
