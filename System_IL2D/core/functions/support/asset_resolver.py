import json
import os
import tempfile
import time
from collections import defaultdict


_STATE = {
    "system_root": None,
    "index_path": None,
    "index": None,
    "primed": False,
}

_IMAGE_EXTS = {".png", ".webp", ".jpg", ".jpeg", ".bmp"}
_JSON_EXTS = {".json"}
_SKIP_DIRS = {".git", ".venv", "__pycache__"}


def _norm(path):
    return os.path.normcase(os.path.normpath(path))


def _safe_rel(path, root):
    rel = os.path.relpath(path, root)
    return rel.replace("\\", "/")


def _is_mod_rel(rel):
    return rel.startswith("mods/")


def _mod_name_from_rel(rel):
    if not _is_mod_rel(rel):
        return "core"
    parts = rel.split("/")
    if len(parts) < 2:
        return "mods"
    return parts[1]


def _index_file_path(system_root):
    saves = os.path.join(system_root, "saves")
    os.makedirs(saves, exist_ok=True)
    return os.path.join(saves, "resource_index.json")


def _entry(abs_path, rel_path):
    return {
        "path": abs_path,
        "rel": rel_path,
        "is_mod": _is_mod_rel(rel_path),
        "mod_name": _mod_name_from_rel(rel_path),
    }


def _sort_entries(entries):
    # mod first, then stable path ordering
    return sorted(entries, key=lambda e: (0 if e.get("is_mod") else 1, e.get("mod_name", ""), e.get("rel", "")))


def _put(by_kind, kind, key, ent):
    if not key:
        return
    by_kind[kind][key].append(ent)


def _classify_file(by_kind, abs_path, rel_path):
    lower_name = os.path.basename(rel_path).lower()
    stem, ext = os.path.splitext(lower_name)
    ent = _entry(abs_path, rel_path)
    rel_lower = rel_path.lower()

    # universal buckets
    _put(by_kind, "file", lower_name, ent)
    _put(by_kind, "file_stem", stem, ent)

    # images
    if ext in _IMAGE_EXTS:
        _put(by_kind, "image", lower_name, ent)
        _put(by_kind, "image", stem, ent)
        if "/atlas/" in rel_lower:
            _put(by_kind, "atlas", lower_name, ent)
            _put(by_kind, "atlas", stem, ent)
        return

    # json
    if ext in _JSON_EXTS:
        _put(by_kind, "json", lower_name, ent)
        _put(by_kind, "json", stem, ent)
        if "/dialogue/" in rel_lower:
            _put(by_kind, "dialog", stem, ent)
            _put(by_kind, "dialog", lower_name, ent)

        if "/map/" in rel_lower or "/maps/" in rel_lower:
            _put(by_kind, "map", lower_name, ent)
            _put(by_kind, "map", stem, ent)

        if "/atlas/" in rel_lower:
            _put(by_kind, "atlas", lower_name, ent)
            _put(by_kind, "atlas", stem, ent)


def _build_index_dict(system_root):
    by_kind = defaultdict(lambda: defaultdict(list))
    folders = defaultdict(list)
    diagnostics = {"scan_errors": []}

    for root, dirs, files in os.walk(system_root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        dirs.sort()
        files.sort()

        rel_dir = _safe_rel(root, system_root)
        if rel_dir == ".":
            rel_dir = ""
        dir_ent = {
            "path": root,
            "rel": rel_dir,
            "is_mod": rel_dir.startswith("mods/"),
            "mod_name": _mod_name_from_rel(rel_dir) if rel_dir else "core",
        }
        key = os.path.basename(root).lower()
        if key:
            folders[key].append(dir_ent)

        for fname in files:
            try:
                abs_path = os.path.join(root, fname)
                rel = _safe_rel(abs_path, system_root)
                _classify_file(by_kind, abs_path, rel)
            except Exception as exc:
                diagnostics["scan_errors"].append(str(exc))

    serial_by_kind = {}
    for kind, mapping in by_kind.items():
        serial_by_kind[kind] = {}
        for key, entries in mapping.items():
            serial_by_kind[kind][key] = _sort_entries(entries)

    serial_folders = {k: _sort_entries(v) for k, v in folders.items()}

    return {
        "version": 1,
        "generated_at": int(time.time()),
        "scan_root": system_root,
        "by_kind": serial_by_kind,
        "folders": serial_folders,
        "diagnostics": diagnostics,
    }


def _atomic_write_json(path, data):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="resource_index_", suffix=".json", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _set_state(system_root, index_path, index_obj):
    _STATE["system_root"] = system_root
    _STATE["index_path"] = index_path
    _STATE["index"] = index_obj
    _STATE["primed"] = True


def prime_asset_index(system_root):
    root = os.path.abspath(system_root)
    index_path = _index_file_path(root)
    index_obj = _build_index_dict(root)
    _atomic_write_json(index_path, index_obj)
    _set_state(root, index_path, index_obj)


def ensure_primed_from_file(module_file):
    if _STATE["primed"]:
        return
    system_root = os.path.abspath(os.path.join(os.path.dirname(module_file), "..", "..", ".."))
    try:
        prime_asset_index(system_root)
    except Exception:
        # fail-open: keep runtime alive with minimal empty index
        _set_state(system_root, _index_file_path(system_root), {
            "version": 1,
            "generated_at": int(time.time()),
            "scan_root": system_root,
            "by_kind": {},
            "folders": {},
            "diagnostics": {"scan_errors": ["prime_failed"]},
        })


def get_index_path():
    return _STATE.get("index_path")


def get_index():
    return _STATE.get("index") or {}


def _candidates(kind, key):
    idx = get_index()
    by_kind = idx.get("by_kind", {})
    mapping = by_kind.get(kind, {})
    return mapping.get((key or "").lower(), [])


def resolve_candidates(kind, name):
    entries = _candidates(kind, (name or "").lower())
    return [e.get("path") for e in entries if e.get("path")]


def resolve(kind, name):
    cand = resolve_candidates(kind, name)
    return cand[0] if cand else None


def resolve_image_candidates(filename):
    if not filename:
        return []
    lower = filename.lower()
    stem, ext = os.path.splitext(lower)
    out = []
    seen = set()

    def _push_many(paths):
        for p in paths:
            n = _norm(p)
            if n in seen:
                continue
            seen.add(n)
            out.append(p)

    # 1) exact filename
    _push_many(resolve_candidates("image", lower))
    # 2) transparent variant
    _push_many(resolve_candidates("image", f"{stem}_nobg"))
    _push_many(resolve_candidates("image", f"{stem}_nobg.png"))
    # 3) stem-any-ext
    _push_many(resolve_candidates("image", stem))
    # 4) extension fallback
    if ext == ".webp":
        for alt in (".png", ".jpg", ".jpeg"):
            _push_many(resolve_candidates("image", stem + alt))
    return out


def resolve_map_candidates(map_name):
    if not map_name:
        return []
    name = map_name.lower()
    stem, ext = os.path.splitext(name)
    out = []
    seen = set()

    def _push(paths):
        for p in paths:
            n = _norm(p)
            if n in seen:
                continue
            seen.add(n)
            out.append(p)

    _push(resolve_candidates("map", name))
    if ext:
        _push(resolve_candidates("map", stem))
    else:
        _push(resolve_candidates("map", name + ".json"))
    return out


def resolve_dialog_candidates(npc_id):
    if not npc_id:
        return []
    name = str(npc_id).lower()
    out = []
    seen = set()

    def _push(paths):
        for p in paths:
            n = _norm(p)
            if n in seen:
                continue
            seen.add(n)
            out.append(p)

    _push(resolve_candidates("dialog", name))
    _push(resolve_candidates("dialog", f"{name}.json"))
    return out


def iter_all_map_files():
    idx = get_index()
    mapping = idx.get("by_kind", {}).get("map", {})
    seen = set()
    for key, entries in mapping.items():
        if not key.endswith(".json"):
            continue
        for ent in entries:
            p = ent.get("path")
            if not p:
                continue
            n = _norm(p)
            if n in seen:
                continue
            seen.add(n)
            yield p


def resolve_atlas_candidates(name):
    if not name:
        return []
    lower = str(name).lower()
    stem, ext = os.path.splitext(lower)
    out = []
    seen = set()

    def _push(paths):
        for p in paths:
            n = _norm(p)
            if n in seen:
                continue
            seen.add(n)
            out.append(p)

    _push(resolve_candidates("atlas", lower))
    if ext:
        # keep extension-specific matching first; avoid returning json for png lookup
        exact = [p for p in resolve_candidates("atlas", lower) if os.path.splitext(p.lower())[1] == ext]
        if exact:
            out = []
            seen = set()
            for p in exact:
                n = _norm(p)
                if n in seen:
                    continue
                seen.add(n)
                out.append(p)
            return out
        _push([p for p in resolve_candidates("atlas", stem) if os.path.splitext(p.lower())[1] == ext])
    else:
        _push(resolve_candidates("atlas", lower + ".json"))
        _push(resolve_candidates("atlas", lower + ".png"))
    return out


def resolve_folder_candidates(folder_name):
    if not folder_name:
        return []
    idx = get_index() or {}
    folders = idx.get("folders", {})
    entries = folders.get(str(folder_name).lower(), [])
    out = []
    seen = set()
    for ent in entries:
        p = ent.get("path")
        if not p:
            continue
        n = _norm(p)
        if n in seen:
            continue
        seen.add(n)
        out.append(p)
    return out
