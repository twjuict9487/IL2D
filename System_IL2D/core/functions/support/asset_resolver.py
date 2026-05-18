import os
from collections import defaultdict


_STATE = {
    "root": None,
    "clips_dir": None,
    "by_name": defaultdict(list),
    "by_stem": defaultdict(list),
    "primed": False,
}


def prime_asset_index(system_root):
    root = os.path.abspath(system_root)
    clips_dir = os.path.join(root, "clips")
    by_name = defaultdict(list)
    by_stem = defaultdict(list)

    if os.path.isdir(clips_dir):
        for base, _dirs, files in os.walk(clips_dir):
            for fname in files:
                lower = fname.lower()
                path = os.path.join(base, fname)
                by_name[lower].append(path)
                stem = os.path.splitext(lower)[0]
                by_stem[stem].append(path)

    _STATE["root"] = root
    _STATE["clips_dir"] = clips_dir
    _STATE["by_name"] = by_name
    _STATE["by_stem"] = by_stem
    _STATE["primed"] = True


def ensure_primed_from_file(module_file):
    if _STATE["primed"]:
        return
    system_root = os.path.abspath(os.path.join(os.path.dirname(module_file), "..", "..", ".."))
    prime_asset_index(system_root)


def resolve_image_candidates(filename):
    if not filename:
        return []
    lower = filename.lower()
    stem, ext = os.path.splitext(lower)
    by_name = _STATE["by_name"]
    by_stem = _STATE["by_stem"]
    candidates = []
    seen = set()

    def _push(path):
        if not path:
            return
        if path in seen:
            return
        seen.add(path)
        candidates.append(path)

    # 1) exact filename
    for p in by_name.get(lower, []):
        _push(p)
    # 2) preferred transparent variant
    for p in by_name.get(f"{stem}_nobg.png", []):
        _push(p)
    # 3) same stem any extension
    for p in by_stem.get(stem, []):
        _push(p)
    # 4) webp fallback by common raster extensions
    if ext == ".webp":
        for alt in (".png", ".jpg", ".jpeg"):
            for p in by_name.get(stem + alt, []):
                _push(p)
    return candidates
