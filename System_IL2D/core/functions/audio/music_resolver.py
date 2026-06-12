RITC_MUSIC = "pixel time.mp3"
ROGUE_MUSIC = "無機物.mp3.mp3"
FALLBACK_MUSIC = "短兵相接.mp3.mp3"

REGION_MUSIC = {
    "RITC": RITC_MUSIC,
}


def _current_map(game):
    return getattr(game, "map", None)


def resolve_current_region(game):
    map_obj = _current_map(game)
    if map_obj is None:
        return ""
    return str(getattr(map_obj, "region", "") or "").strip().upper()


def is_rogue_mode(game):
    map_obj = _current_map(game)
    if map_obj is None:
        return False
    if resolve_current_region(game) == "ROGUE":
        return True
    name = str(getattr(map_obj, "name", "") or "").strip().lower()
    if name in {"rogue", "rouge", "rogue.json", "rouge.json", "rouge_options.json"}:
        return True
    try:
        if int(getattr(game, "rogue_layer", 0) or 0) > 0 and name in {
            "rogue",
            "rouge",
            "rouge_options.json",
        }:
            return True
    except Exception:
        pass
    return False


def resolve_current_music(game):
    map_obj = _current_map(game)
    if map_obj is None:
        return None
    if is_rogue_mode(game):
        return ROGUE_MUSIC
    region = resolve_current_region(game)
    if region in REGION_MUSIC:
        return REGION_MUSIC[region]
    override = getattr(map_obj, "music_override", None)
    if override:
        return override
    return FALLBACK_MUSIC
