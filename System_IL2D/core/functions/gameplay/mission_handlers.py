import math
import time

from ..support.utils import BLOCKTYPE_FILE, MOBS_FILE, load_json, resolve_map_file

MOBS_DATA = load_json(MOBS_FILE)
BLOCKTYPES = load_json(BLOCKTYPE_FILE)
_MAP_GRID_CACHE = {}

TYPE_ALIASES = {
    "CM": {"CM", "complete_missions", "mission_complete"},
    "KE": {"KE", "kill_enemy", "kill", "kill_any", "kill_specific"},
    "KEE": {"KEE", "kill_elite_enemy", "kill_elite"},
    "CI": {"CI", "collect_item"},
    "CD": {"CD", "collect_data"},
    "UD": {"UD", "upload_data"},
    "CA": {"CA", "clear_area"},
    "SA": {"SA", "survey_area", "stay_area"},
}


def start_runtime(game, mission):
    """Initialize runtime fields for every objective present in this mission."""
    _ensure_mission_spawns(game, mission)
    if _mission_has_type(mission, "SA"):
        _start_sa(game, mission)
    if _mission_has_type(mission, "CD"):
        _start_cd(game, mission)
    if _mission_has_type(mission, "UD"):
        _start_ud(game, mission)
    if _mission_has_type(mission, "CI"):
        _start_ci(game, mission)
    if _mission_has_type(mission, "KE"):
        _start_ke(game, mission)
    if _mission_has_type(mission, "KEE"):
        _start_kee(game, mission)
    if _mission_has_type(mission, "CA"):
        _start_ca(game, mission)
    if _mission_has_type(mission, "CM"):
        _start_cm(game, mission)
    return mission


def ensure_active_mission_spawns(game, restore_missing=False):
    """Restore data-defined mission waves after map changes or save loading."""
    for mission in _active(game):
        _ensure_mission_spawns(game, mission, restore_missing=restore_missing)


def _find_mission_spawn_tile(game, position, radius=3):
    try:
        x, y = int(position[0]), int(position[1])
    except Exception:
        return None
    candidates = [(x, y)]
    for step in range(1, max(1, int(radius)) + 1):
        for dx in range(-step, step + 1):
            for dy in range(-step, step + 1):
                if abs(dx) != step and abs(dy) != step:
                    continue
                candidates.append((x + dx, y + dy))
    for cx, cy in candidates:
        if game.can_spawn_entity_at_size(cx, cy):
            return cx, cy
    return None


def _ensure_mission_spawns(game, mission, restore_missing=False):
    waves = mission.get("enemy_spawns", []) or []
    if not isinstance(waves, list) or not waves:
        return 0
    runtime = mission.setdefault("runtime", {})
    mission_id = _clean(mission.get("id"))
    spawned = 0
    errors = []
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        target_map = _clean(wave.get("map") or _ca_target_map(mission))
        if target_map and not _same_map_name(_current_map_name(game), target_map):
            continue
        group = _clean(wave.get("group") or "default")
        related_objectives = [
            obj
            for obj in mission.get("objectives", []) or []
            if isinstance(obj, dict)
            and _canon_type(obj.get("type")) == "CA"
            and _clean(obj.get("spawn_group") or "default") == group
        ]
        if related_objectives and all(bool(obj.get("done")) for obj in related_objectives):
            continue
        existing = [
            ent
            for ent in getattr(game, "entities", []) or []
            if getattr(ent, "hp", 0) > 0
            and _clean(getattr(ent, "mission_owner_id", "")) == mission_id
            and _clean(getattr(ent, "mission_spawn_group", "")) == group
        ]
        if existing:
            continue
        if runtime.get("mission_spawns_initialized") and not restore_missing:
            continue
        mob_id = _clean(wave.get("mob"))
        for index, position in enumerate(wave.get("positions", []) or []):
            tile = _find_mission_spawn_tile(game, position)
            if tile is None:
                errors.append(f"{group}:{index}")
                continue
            ent = game.create_hostile_entity(
                mob_id,
                tile[0],
                tile[1],
                extra_flags={
                    "mission_owner_id": mission_id,
                    "mission_spawn_group": group,
                },
            )
            if ent is None:
                errors.append(f"{group}:{mob_id}")
                continue
            game.entities.append(ent)
            spawned += 1
    runtime["mission_spawns_initialized"] = True
    runtime["mission_spawn_errors"] = errors
    return spawned

def on_enemy_death(game, enemy_id):
    for mission in _active(game):
        if _mission_is_ready(mission):
            continue
        if _mission_has_type(mission, "KE"):
            _ke_enemy_death(game, mission, enemy_id)
        if _mission_has_type(mission, "KEE"):
            _kee_enemy_death(game, mission, enemy_id)
        if _mission_has_type(mission, "CA"):
            _ca_enemy_death(game, mission, enemy_id)

def on_player_interact(game):
    for mission in _active(game):
        if _mission_is_ready(mission):
            continue
        if _mission_has_type(mission, "CD"):
            _cd_interact(game, mission)
        if _mission_has_type(mission, "UD"):
            _ud_interact(game, mission)

def on_player_update(game):
    for mission in _active(game):
        if _mission_is_ready(mission):
            continue
        if _mission_has_type(mission, "SA"):
            _sa_update(game, mission)
        if _mission_has_type(mission, "CA"):
            _ca_update(game, mission)


def on_item_gain(game, item_name=None, amount=1, source=None):
    for mission in _active(game):
        if _mission_is_ready(mission):
            continue
        if _mission_has_type(mission, "CI"):
            _ci_item_gain(game, mission, item_name=item_name, amount=amount, source=source)


def on_mission_complete(game, mission_id=None):
    for mission in _active(game):
        if _mission_is_ready(mission):
            continue
        if _mission_has_type(mission, "CM"):
            _cm_mission_complete(game, mission, mission_id=mission_id)

def _clean(value):
    return str(value or "").strip()


def _bool_value(value, default=False):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return bool(value)

def _canon_type(value):
    raw = _clean(value)
    upper = raw.upper()
    for canonical, aliases in TYPE_ALIASES.items():
        if raw in aliases or upper in aliases:
            return canonical
    return upper

def _mt(mission):
    if not isinstance(mission, dict):
        return ""
    mt = (
        mission.get("MT")
        or mission.get("mt")
        or mission.get("type")
        or mission.get("mission_type")
        or ""
    )
    if isinstance(mt, dict):
        mt = mt.get("primary") or mt.get("id") or ""
    return _canon_type(mt)

def _objective_types(mission):
    out = []
    if not isinstance(mission, dict):
        return out
    primary = _mt(mission)
    if primary:
        out.append(primary)
    for obj in mission.get("objectives", []) or []:
        if isinstance(obj, dict):
            typ = _canon_type(obj.get("type"))
            if typ:
                out.append(typ)
    return out

def _mission_has_type(mission, typ):
    return _canon_type(typ) in _objective_types(mission)

def _mission_is_ready(mission):
    return _clean(mission.get("status")).lower() in {
        "ready",
        "ready_to_return",
        "completed",
    }

def _active(game):
    if hasattr(game, "get_active_missions"):
        return game.get_active_missions()
    return getattr(game, "active_missions", []) or []

def _params(mission):
    params = mission.get("params")
    return params if isinstance(params, dict) else {}

def _get_param(mission, *keys, default=None):
    params = _params(mission)
    for key in keys:
        if key in mission and mission.get(key) not in (None, ""):
            return mission.get(key)
        if key in params and params.get(key) not in (None, ""):
            return params.get(key)
    for obj in mission.get("objectives", []) or []:
        if not isinstance(obj, dict):
            continue
        for key in keys:
            if key in obj and obj.get(key) not in (None, ""):
                return obj.get(key)
    return default


def _objective_node(mission, typ):
    wanted_type = _canon_type(typ)
    for obj in mission.get("objectives", []) or []:
        if not isinstance(obj, dict):
            continue
        if _canon_type(obj.get("type")) == wanted_type:
            return obj
    return {}


def _get_param_for_type(mission, typ, *keys, default=None):
    obj = _objective_node(mission, typ)
    for key in keys:
        if key in obj and obj.get(key) not in (None, ""):
            return obj.get(key)
    if _mt(mission) == _canon_type(typ):
        return _get_param(mission, *keys, default=default)
    return default

def _mission_amount(mission, default=1, typ=None):
    wanted_type = _canon_type(typ or _mt(mission))

    for obj in mission.get("objectives", []) or []:
        if not isinstance(obj, dict):
            continue

        obj_type = _canon_type(obj.get("type"))
        if wanted_type and obj_type != wanted_type:
            continue

        return max(
            1,
            int(
                obj.get("target", obj.get("amount", obj.get("count", default)))
                or default
            ),
        )

    return max(
        1,
        int(mission.get("amount", mission.get("count", default)) or default),
    )

def _objective_progress(mission, typ, default=0):
    wanted_type = _canon_type(typ)
    for obj in mission.get("objectives", []) or []:
        if not isinstance(obj, dict):
            continue
        if _canon_type(obj.get("type")) != wanted_type:
            continue
        try:
            return max(0, int(obj.get("progress", default) or default))
        except Exception:
            return default
    return default

def _same_map_name(a, b):
    a = _clean(a)
    b = _clean(b)
    if not a or not b:
        return False
    return a == b or a.removesuffix(".json") == b.removesuffix(".json")

def _mission_map_matches(game, mission, typ=None):
    if typ:
        map_name = _clean(
            _get_param_for_type(mission, typ, "map", "map_id", "target_map")
        )
    else:
        map_name = _clean(_get_param(mission, "map", "map_id", "target_map"))
    current_map = _current_map_name(game)
    return not map_name or map_name == "*" or _same_map_name(map_name, current_map)

def _current_map_name(game):
    return _clean(getattr(getattr(game, "map", None), "name", ""))

def _player_pos(game):
    player = getattr(game, "player", None)
    if player is None:
        return None
    return (int(getattr(player, "x", -1)), int(getattr(player, "y", -1)))


def _target_pos(target):
    if not isinstance(target, dict):
        return None
    try:
        return (int(target.get("x", -1)), int(target.get("y", -1)))
    except Exception:
        return None


def _canonical_item_name(game, name):
    text = _clean(name)
    if not text:
        return ""
    if hasattr(game, "canonical_item_name"):
        try:
            return _clean(game.canonical_item_name(text))
        except Exception:
            return text
    return text


def _enemy_class(enemy_id):
    mob_def = MOBS_DATA.get(str(enemy_id), {}) if isinstance(MOBS_DATA, dict) else {}
    return _clean(mob_def.get("enemy_class")).lower()


def _enemy_is_elite(enemy_id):
    return _enemy_class(enemy_id) in {"elite", "boss"}


def _mission_area_rect(mission, typ=None):
    if typ:
        area = _get_param_for_type(mission, typ, "area", "target_area")
    else:
        area = _get_param(mission, "area", "target_area")
    if isinstance(area, dict):
        corners = area.get("corners")
        if isinstance(corners, list) and len(corners) >= 4:
            xs = []
            ys = []
            for point in corners:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                try:
                    xs.append(int(point[0]))
                    ys.append(int(point[1]))
                except Exception:
                    continue
            if xs and ys:
                return (min(xs), min(ys), max(xs), max(ys))
        try:
            return (
                int(area.get("x1")),
                int(area.get("y1")),
                int(area.get("x2")),
                int(area.get("y2")),
            )
        except Exception:
            return None
    if isinstance(area, (list, tuple)) and len(area) >= 4:
        try:
            return (int(area[0]), int(area[1]), int(area[2]), int(area[3]))
        except Exception:
            return None
    x1 = _get_param(mission, "x1")
    y1 = _get_param(mission, "y1")
    x2 = _get_param(mission, "x2")
    y2 = _get_param(mission, "y2")
    if x1 in (None, "") or y1 in (None, "") or x2 in (None, "") or y2 in (None, ""):
        return None
    try:
        return (int(x1), int(y1), int(x2), int(y2))
    except Exception:
        return None


def _objective_area_rect(objective):
    if not isinstance(objective, dict):
        return None
    area = objective.get("area", objective.get("target_area"))
    if isinstance(area, dict):
        corners = area.get("corners")
        if isinstance(corners, list) and len(corners) >= 4:
            points = [point for point in corners if isinstance(point, (list, tuple)) and len(point) >= 2]
            if points:
                try:
                    xs = [int(point[0]) for point in points]
                    ys = [int(point[1]) for point in points]
                    return min(xs), min(ys), max(xs), max(ys)
                except (TypeError, ValueError):
                    return None
        try:
            return int(area["x1"]), int(area["y1"]), int(area["x2"]), int(area["y2"])
        except (KeyError, TypeError, ValueError):
            return None
    if isinstance(area, (list, tuple)) and len(area) >= 4:
        try:
            return tuple(int(value) for value in area[:4])
        except (TypeError, ValueError):
            return None
    return None


def _objective_map_matches(game, objective):
    map_name = _clean(objective.get("map") or objective.get("map_id") or objective.get("target_map"))
    return not map_name or map_name == "*" or _same_map_name(map_name, _current_map_name(game))


def _normalize_grid(raw_grid):
    grid = []
    for row in raw_grid or []:
        if isinstance(row, str):
            grid.append([t for t in row.replace(",", " ").split() if t])
        else:
            grid.append(list(row))
    return grid


def _map_grid(map_name, game=None):
    map_name = _clean(map_name)
    current = getattr(game, "map", None)
    if current is not None and _same_map_name(getattr(current, "name", ""), map_name):
        return getattr(current, "grid", []) or []
    key = map_name.removesuffix(".json")
    if key in _MAP_GRID_CACHE:
        return _MAP_GRID_CACHE[key]
    path = resolve_map_file(map_name)
    if not path:
        _MAP_GRID_CACHE[key] = []
        return []
    try:
        data = load_json(path)
        grid = _normalize_grid(data.get("grid") or [])
    except Exception:
        grid = []
    _MAP_GRID_CACHE[key] = grid
    return grid


def _is_walkable_at(map_name, x, y, game=None):
    current = getattr(game, "map", None)
    if current is not None and _same_map_name(getattr(current, "name", ""), map_name):
        try:
            return bool(current.is_walkable(int(x), int(y)))
        except Exception:
            return False
    grid = _map_grid(map_name, game=game)
    try:
        x = int(x)
        y = int(y)
    except Exception:
        return False
    if y < 0 or x < 0 or y >= len(grid) or not grid or x >= len(grid[y]):
        return False
    return bool((BLOCKTYPES.get(grid[y][x], {}) or {}).get("walkable", False))


def _walkable_tiles_in_rect(map_name, rect, game=None):
    if not map_name or not rect:
        return []
    x1, y1, x2, y2 = rect
    left = min(x1, x2)
    right = max(x1, x2)
    top = min(y1, y2)
    bottom = max(y1, y2)
    out = []
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            if _is_walkable_at(map_name, x, y, game=game):
                out.append((x, y))
    return out


def _area_contains_walkable_tile(game, mission, pos=None, typ=None):
    pos = pos or _player_pos(game)
    rect = _mission_area_rect(mission, typ=typ)
    map_name = _clean(
        _get_param_for_type(mission, typ, "map", "map_id", "target_map")
        if typ
        else _get_param(mission, "map", "map_id", "target_map")
    )
    if not rect or not map_name or pos is None or not _mission_map_matches(game, mission, typ=typ):
        return False
    if not _rect_contains(rect, pos):
        return False
    return _is_walkable_at(map_name, pos[0], pos[1], game=game)


def _sanitize_area_rect(game, mission, typ=None):
    rect = _mission_area_rect(mission, typ=typ)
    map_name = _clean(
        _get_param_for_type(mission, typ, "map", "map_id", "target_map")
        if typ
        else _get_param(mission, "map", "map_id", "target_map")
    )
    if not rect or not map_name:
        return rect
    tiles = _walkable_tiles_in_rect(map_name, rect, game=game)
    if not tiles:
        return None
    xs = [p[0] for p in tiles]
    ys = [p[1] for p in tiles]
    return (min(xs), min(ys), max(xs), max(ys))


def _rect_contains(rect, pos):
    if not rect or pos is None:
        return False
    x1, y1, x2, y2 = rect
    px, py = pos
    return min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2)


def _target_in_rect(target, rect):
    return _rect_contains(rect, _target_pos(target))


def _mission_target_id(mission, typ=None):
    return _clean(
        (
            _get_param_for_type(
                mission,
                typ,
                "target_id",
                "data_target_id",
                "interaction_id",
                "terminal_id",
            )
            if typ
            else _get_param(
                mission, "target_id", "data_target_id", "interaction_id", "terminal_id"
            )
        )
    )

def _target_key(target):
    target_id = _clean(target.get("target_id") or target.get("id"))
    if target_id:
        return target_id
    try:
        return f"{int(target.get('x', -1))}:{int(target.get('y', -1))}"
    except Exception:
        return None

def _nearby_mission_targets(game):
    pos = _player_pos(game)
    if pos is None:
        return []
    px, py = pos
    out = []
    game_map = getattr(game, "map", None)
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        target = None
        if hasattr(game_map, "get_mission_target"):
            target = game_map.get_mission_target(px + dx, py + dy)
        if isinstance(target, dict):
            out.append(target)
    return out

def _matching_interaction_target(game, mission, allowed_kinds, typ=None):
    if not _mission_map_matches(game, mission, typ=typ):
        return None
    mission_target_id = _mission_target_id(mission, typ=typ)
    mission_target_group = _clean(
        _get_param_for_type(mission, typ, "target_group", default="")
        if typ
        else _get_param(mission, "target_group", default="")
    )
    for target in _nearby_mission_targets(game):
        kind = _clean(target.get("kind")).lower()
        if allowed_kinds and kind not in allowed_kinds:
            continue
        target_id = _clean(target.get("target_id") or target.get("id"))
        target_group = _clean(target.get("target_group") or target.get("group"))
        if mission_target_group and target_group != mission_target_group:
            continue
        if (
            mission_target_id
            and mission_target_id != "*"
            and target_id != mission_target_id
        ):
            continue
        return target
    return None


def _matching_objective_target(game, objective, allowed_kinds):
    if not _objective_map_matches(game, objective):
        return None
    desired = _clean(objective.get("target_id") or objective.get("interaction_id"))
    desired_group = _clean(objective.get("target_group") or objective.get("group"))
    rect = _objective_area_rect(objective)
    pos = _player_pos(game)
    for target in _nearby_mission_targets(game):
        kind = _clean(target.get("kind")).lower()
        target_id = _clean(target.get("target_id") or target.get("id"))
        target_group = _clean(target.get("target_group") or target.get("group"))
        if allowed_kinds and kind not in allowed_kinds:
            continue
        if desired_group and target_group != desired_group:
            continue
        if desired and desired != "*" and target_id != desired:
            continue
        if rect and not (_target_in_rect(target, rect) or _rect_contains(rect, pos)):
            continue
        return target
    return None

def _sync_objective(mission, typ, progress=None, target=None, done=None, **extra):
    typ = _canon_type(typ)
    touched = False
    objectives = mission.setdefault("objectives", [])
    for obj in objectives:
        if not isinstance(obj, dict):
            continue
        if _canon_type(obj.get("type")) != typ:
            continue
        if target is not None:
            obj["target"] = max(1, int(target or 1))
        if progress is not None:
            obj["progress"] = max(0, int(progress or 0))
        if done is not None:
            obj["done"] = bool(done)
        for key, value in extra.items():
            if value not in (None, ""):
                obj[key] = value
        touched = True
    if not touched:
        obj = {"type": typ, "target": int(target or 1), "progress": int(progress or 0)}
        if done is not None:
            obj["done"] = bool(done)
        for key, value in extra.items():
            if value not in (None, ""):
                obj[key] = value
        objectives.append(obj)

def _all_non_return_objectives_done(mission):
    objectives = [o for o in mission.get("objectives", []) or [] if isinstance(o, dict)]
    if not objectives:
        return bool(mission.get("done"))
    for obj in objectives:
        typ = _canon_type(obj.get("type"))
        if typ in {"RETURN", "TURN_IN"}:
            continue
        if not bool(obj.get("done", False)):
            return False
    return True

def _all_objectives_done(mission):
    objectives = mission.get("objectives", []) or []
    meaningful = [
        obj
        for obj in objectives
        if isinstance(obj, dict)
        and _canon_type(obj.get("type")) not in ("", "RETURN", "TURN_IN")
    ]
    if not meaningful:
        return bool(mission.get("done", False))
    return all(bool(obj.get("done", False)) for obj in meaningful)

def _mark_done(game, mission, typ=None):
    wanted_type = _canon_type(typ or _mt(mission))

    if wanted_type:
        for obj in mission.get("objectives", []) or []:
            if not isinstance(obj, dict):
                continue
            if _canon_type(obj.get("type")) != wanted_type:
                continue
            obj["done"] = True
            obj["progress"] = int(obj.get("target", obj.get("progress", 1)) or 1)

    if _all_objectives_done(mission):
        mission["done"] = True
        mission["status"] = "ready_to_return"
    else:
        mission["done"] = False
        mission["status"] = "active"

    if hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

def _finish_node(game, mission, typ, progress_key, done_key, target=None, **extra):
    runtime = mission.setdefault("runtime", {})
    target = target or _mission_amount(mission, typ=typ)
    progress = int(runtime.get(progress_key, 0) or 0)
    _sync_objective(
        mission, typ, progress=progress, target=target, done=progress >= target, **extra
    )
    if progress >= target:
        runtime[done_key] = True
        if _all_non_return_objectives_done(mission):
            _mark_done(game, mission)
        elif hasattr(game, "_normalize_mission_state"):
            game._normalize_mission_state()

# SA

def _push_runtime_message(game, text):
    text = _clean(text)
    if not text:
        return
    if hasattr(game, "push_message"):
        try:
            game.push_message(text)
            return
        except Exception:
            pass
    if hasattr(game, "add_message"):
        try:
            game.add_message(text)
        except Exception:
            pass


def _sa_sync_objective(mission, text, progress, target, done=False):
    _sync_objective(
        mission,
        "SA",
        progress=max(0, int(progress or 0)),
        target=max(1, int(target or 1)),
        done=done,
        text=text,
        map=_get_param(mission, "map", "map_id", "target_map"),
    )


def _structured_sa_objectives(mission):
    return [
        obj
        for obj in mission.get("objectives", []) or []
        if isinstance(obj, dict)
        and _canon_type(obj.get("type")) == "SA"
        and _objective_area_rect(obj) is not None
    ]

def _start_sa(game, mission):
    structured = _structured_sa_objectives(mission)
    if structured:
        for obj in structured:
            required = max(0.1, float(obj.get("seconds", obj.get("duration", 2.0)) or 2.0))
            obj["target"] = max(1, int(math.ceil(required)))
            obj["progress"] = max(0, int(obj.get("progress", 0) or 0))
            obj["done"] = bool(obj.get("done", False))
        return mission
    runtime = mission.setdefault("runtime", {})
    started_at = runtime.get("search_started_at", runtime.get("sa_started_at"))
    done = bool(runtime.get("search_done", runtime.get("sa_done", False)))
    progress = runtime.get("search_progress", runtime.get("sa_progress", 0))
    runtime["search_started_at"] = started_at
    runtime["search_done"] = done
    runtime["search_progress"] = max(0, int(progress or 0))
    try:
        runtime["search_required_seconds"] = float(
            _get_param(mission, "seconds", default=5) or 5
        )
    except Exception:
        runtime["search_required_seconds"] = 5.0
    required = max(1, int(runtime.get("search_required_seconds", 5.0) or 5))
    if runtime["search_done"] or _mission_is_ready(mission):
        _sa_sync_objective(
            mission,
            "Return and report your findings.",
            1,
            1,
            done=True,
        )
    else:
        _sa_sync_objective(
            mission,
            "Search the target map.",
            int(runtime.get("search_progress", 0) or 0),
            required,
            done=False,
        )
    return mission


def _sa_update(game, mission):
    structured = _structured_sa_objectives(mission)
    if structured:
        now = time.time()
        pos = _player_pos(game)
        changed = False
        for obj in structured:
            if obj.get("done"):
                continue
            rect = _objective_area_rect(obj)
            inside = _objective_map_matches(game, obj) and _rect_contains(rect, pos)
            if not inside:
                if obj.pop("entered_at", None) is not None or obj.get("progress"):
                    obj["progress"] = 0
                    changed = True
                continue
            started = obj.get("entered_at")
            if started is None:
                obj["entered_at"] = now
                started = now
                changed = True
            required = max(0.1, float(obj.get("seconds", obj.get("duration", 2.0)) or 2.0))
            elapsed = max(0.0, now - float(started))
            progress = min(max(1, int(math.ceil(required))), int(elapsed))
            if progress != int(obj.get("progress", 0) or 0):
                obj["progress"] = progress
                changed = True
            if elapsed >= required:
                obj["done"] = True
                obj["progress"] = max(1, int(math.ceil(required)))
                changed = True
        if all(bool(obj.get("done")) for obj in structured):
            if _all_non_return_objectives_done(mission):
                _mark_done(game, mission)
            elif hasattr(game, "_normalize_mission_state"):
                game._normalize_mission_state()
        elif changed and hasattr(game, "_normalize_mission_state"):
            game._normalize_mission_state()
        return
    runtime = mission.setdefault("runtime", {})
    if runtime.get("search_done", runtime.get("sa_done")):
        return

    required = float(runtime.get("search_required_seconds", 5.0) or 5.0)
    target = max(1, int(required))

    if not _mission_map_matches(game, mission):
        had_progress = int(runtime.get("search_progress", runtime.get("sa_progress", 0)) or 0) > 0
        runtime["search_started_at"] = None
        runtime["search_progress"] = 0
        runtime["sa_started_at"] = None
        runtime["sa_progress"] = 0
        if had_progress:
            _push_runtime_message(game, "Search interrupted.")
        _sa_sync_objective(
            mission,
            "Search the target map.",
            0,
            target,
            done=False,
        )
        if hasattr(game, "_normalize_mission_state"):
            game._normalize_mission_state()
        return

    if runtime.get("search_started_at") is None:
        runtime["search_started_at"] = time.time()
    elapsed = time.time() - float(runtime.get("search_started_at", time.time()))
    progress = min(max(0, int(elapsed)), target)
    runtime["search_progress"] = progress
    runtime["sa_started_at"] = runtime.get("search_started_at")
    runtime["sa_progress"] = progress

    if elapsed >= required:
        runtime["search_done"] = True
        runtime["sa_done"] = True
        runtime["search_progress"] = target
        runtime["sa_progress"] = target
        _sa_sync_objective(
            mission,
            "Return and report your findings.",
            1,
            1,
            done=True,
        )
        _push_runtime_message(game, "Area search complete.")
        _mark_done(game, mission, "SA")
        return

    _sa_sync_objective(
        mission,
        "Searching map...",
        progress,
        target,
        done=False,
    )
    if hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

# CD

def _start_cd(game, mission):
    runtime = mission.setdefault("runtime", {})
    objectives = [
        obj
        for obj in mission.get("objectives", []) or []
        if isinstance(obj, dict) and _canon_type(obj.get("type")) == "CD"
    ]
    if len(objectives) > 1:
        for obj in objectives:
            obj["target"] = max(1, int(obj.get("target", obj.get("amount", 1)) or 1))
            obj["progress"] = max(0, int(obj.get("progress", 0) or 0))
            obj["done"] = bool(obj.get("done", False))
            obj.setdefault("collected_targets", [])
        runtime["has_data"] = all(bool(obj.get("done")) for obj in objectives)
        runtime["data_collected"] = runtime["has_data"]
        return mission
    runtime.setdefault("has_data", bool(runtime.get("data_collected", False)))
    runtime.setdefault("data_collected", bool(runtime.get("has_data", False)))
    runtime.setdefault("data_progress", _objective_progress(mission, "CD", default=0))
    _sync_objective(
        mission,
        "CD",
        progress=runtime["data_progress"],
        target=_mission_amount(mission, typ="CD"),
        done=runtime["has_data"],
    )
    return mission

def _cd_interact(game, mission):
    runtime = mission.setdefault("runtime", {})
    objectives = [
        obj
        for obj in mission.get("objectives", []) or []
        if isinstance(obj, dict) and _canon_type(obj.get("type")) == "CD"
    ]
    if len(objectives) > 1:
        for obj in objectives:
            if obj.get("done"):
                continue
            target = _matching_objective_target(
                game, obj, {"data", "collect_data", "terminal"}
            )
            if not target:
                continue
            key = _target_key(target)
            seen = obj.setdefault("collected_targets", [])
            if key and key in seen:
                continue
            if key:
                seen.append(key)
            target_amount = max(1, int(obj.get("target", obj.get("amount", 1)) or 1))
            obj["target"] = target_amount
            obj["progress"] = min(
                target_amount, int(obj.get("progress", 0) or 0) + 1
            )
            obj["done"] = obj["progress"] >= target_amount
            break
        all_done = all(bool(obj.get("done")) for obj in objectives)
        runtime["has_data"] = all_done
        runtime["data_collected"] = all_done
        if all_done and _all_non_return_objectives_done(mission):
            _mark_done(game, mission)
        elif hasattr(game, "_normalize_mission_state"):
            game._normalize_mission_state()
        return
    if runtime.get("has_data") or runtime.get("data_collected"):
        return
    if not _mission_map_matches(game, mission, typ="CD"):
        return

    rect = _sanitize_area_rect(game, mission, typ="CD") or _mission_area_rect(mission, typ="CD")
    pos = _player_pos(game)
    target_id = _mission_target_id(mission, typ="CD")
    target = _matching_interaction_target(game, mission, {"data", "collect_data"}, typ="CD")
    if target and rect and not (_target_in_rect(target, rect) or _rect_contains(rect, pos)):
        target = None
    if not target and rect and _area_contains_walkable_tile(game, mission, pos=pos, typ="CD"):
        px, py = pos or (-1, -1)
        next_index = int(runtime.get("data_progress", 0) or 0) + 1
        target = {
            "target_id": target_id or f"{_current_map_name(game)}:{px}:{py}:{next_index}",
            "x": px,
            "y": py,
            "generated_area_target": True,
        }
    if not target:
        return

    seen = runtime.setdefault("collected_targets", [])
    key = _target_key(target)
    if key and key in seen and not bool(target.get("generated_area_target")):
        return
    if key:
        seen.append(key)

    runtime["data_target_id"] = key
    runtime["data_target_map"] = _current_map_name(game)
    runtime["data_progress"] = min(
        _mission_amount(mission, typ="CD"),
        int(runtime.get("data_progress", 0) or 0) + 1,
    )

    target_amount = _mission_amount(mission, typ="CD")
    if runtime["data_progress"] >= target_amount:
        runtime["has_data"] = True
        runtime["data_collected"] = True

    _sync_objective(
        mission,
        "CD",
        progress=runtime["data_progress"],
        target=target_amount,
        done=runtime.get("has_data", False),
        target_id=key,
        map=_current_map_name(game),
    )

    requires_upload = _bool_value(
        _get_param_for_type(mission, "CD", "requires_upload", default=False), default=False
    ) or _mission_has_type(mission, "UD")
    if runtime.get("has_data") and not requires_upload:
        _mark_done(game, mission, "CD")
    elif hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

# UD

def _start_ud(game, mission):
    runtime = mission.setdefault("runtime", {})
    runtime.setdefault("uploaded", False)
    runtime.setdefault("upload_progress", _objective_progress(mission, "UD", default=0))
    _sync_objective(
        mission,
        "UD",
        progress=runtime["upload_progress"],
        target=_mission_amount(mission, typ="UD"),
        done=runtime["uploaded"],
    )
    return mission

def _ud_interact(game, mission):
    runtime = mission.setdefault("runtime", {})
    if runtime.get("uploaded"):
        return

    requires_data = _bool_value(
        _get_param_for_type(mission, "UD", "requires_data", default=False), default=False
    ) or _mission_has_type(mission, "CD")
    if requires_data and not (runtime.get("has_data") or runtime.get("data_collected")):
        return
    if not _mission_map_matches(game, mission, typ="UD"):
        return

    rect = _sanitize_area_rect(game, mission, typ="UD") or _mission_area_rect(mission, typ="UD")
    pos = _player_pos(game)
    target_id = _mission_target_id(mission, typ="UD")
    target = _matching_interaction_target(game, mission, {"terminal", "upload_data"}, typ="UD")
    if target and rect and not (_target_in_rect(target, rect) or _rect_contains(rect, pos)):
        target = None
    if not target and rect and _area_contains_walkable_tile(game, mission, pos=pos, typ="UD"):
        px, py = pos or (-1, -1)
        target = {
            "target_id": target_id or f"{_current_map_name(game)}:{px}:{py}",
            "x": px,
            "y": py,
        }
    if not target:
        return

    seen = runtime.setdefault("used_terminals", [])
    key = _target_key(target)
    if key and key in seen:
        return
    if key:
        seen.append(key)

    runtime["upload_target_id"] = key
    runtime["upload_target_map"] = _current_map_name(game)
    runtime["upload_progress"] = int(runtime.get("upload_progress", 0) or 0) + 1

    target_amount = _mission_amount(mission, typ="UD")
    _sync_objective(
        mission,
        "UD",
        progress=runtime["upload_progress"],
        target=target_amount,
        done=runtime["upload_progress"] >= target_amount,
        target_id=key,
        map=_current_map_name(game),
    )

    if runtime["upload_progress"] >= target_amount:
        runtime["uploaded"] = True
        _mark_done(game, mission, "UD")
    elif hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

# CI

def _start_ci(game, mission):
    runtime = mission.setdefault("runtime", {})
    objectives = [
        obj
        for obj in mission.get("objectives", []) or []
        if isinstance(obj, dict) and _canon_type(obj.get("type")) == "CI"
    ]
    if len(objectives) > 1:
        for obj in objectives:
            obj["target"] = max(1, int(obj.get("target", obj.get("amount", 1)) or 1))
            obj["progress"] = max(0, int(obj.get("progress", 0) or 0))
            obj["done"] = bool(obj.get("done", False))
        runtime["collected"] = all(bool(obj.get("done")) for obj in objectives)
        return mission
    runtime.setdefault("collected", False)
    runtime.setdefault("collect_progress", _objective_progress(mission, "CI", default=0))
    _sync_objective(
        mission,
        "CI",
        progress=runtime["collect_progress"],
        target=_mission_amount(mission, typ="CI"),
        done=runtime["collected"],
    )
    return mission

def _ci_item_gain(game, mission, item_name=None, amount=1, source=None):
    runtime = mission.setdefault("runtime", {})
    objectives = [
        obj
        for obj in mission.get("objectives", []) or []
        if isinstance(obj, dict) and _canon_type(obj.get("type")) == "CI"
    ]
    if len(objectives) > 1:
        try:
            gained = max(0, int(amount or 0))
        except Exception:
            gained = 0
        gained_item = _canonical_item_name(game, item_name)
        if gained <= 0:
            return
        changed = False
        for obj in objectives:
            if obj.get("done"):
                continue
            target_item = _canonical_item_name(
                game,
                obj.get("item_id")
                or obj.get("item_name")
                or obj.get("target_id")
                or "*",
            )
            if target_item not in ("", "*", "any") and gained_item != target_item:
                continue
            source_filter = obj.get("source_filter")
            if source_filter not in (None, "") and _clean(source_filter) != _clean(source):
                continue
            target_amount = max(1, int(obj.get("target", obj.get("amount", 1)) or 1))
            obj["target"] = target_amount
            obj["progress"] = min(
                target_amount, int(obj.get("progress", 0) or 0) + gained
            )
            obj["done"] = obj["progress"] >= target_amount
            changed = True
            break
        if not changed:
            return
        all_done = all(bool(obj.get("done")) for obj in objectives)
        runtime["collected"] = all_done
        if all_done and _all_non_return_objectives_done(mission):
            _mark_done(game, mission)
        elif hasattr(game, "_normalize_mission_state"):
            game._normalize_mission_state()
        return
    if runtime.get("collected"):
        return

    try:
        gained = max(0, int(amount or 0))
    except Exception:
        gained = 0
    if gained <= 0:
        return

    target_item = _canonical_item_name(
        game,
        _get_param(mission, "item_id", "item_name", "target_id", "required_key", default="*"),
    )
    gained_item = _canonical_item_name(game, item_name)
    if target_item not in ("", "*", "any") and gained_item != target_item:
        return

    source_filter = _get_param(mission, "source_filter")
    if source_filter not in (None, ""):
        if isinstance(source_filter, (list, tuple, set)):
            allowed = {_clean(v) for v in source_filter if _clean(v)}
            if allowed and _clean(source) not in allowed:
                return
        elif _clean(source_filter) != _clean(source):
            return

    target_amount = _mission_amount(mission, typ="CI")
    runtime["collect_progress"] = min(
        target_amount,
        int(runtime.get("collect_progress", 0) or 0) + gained,
    )
    _sync_objective(
        mission,
        "CI",
        progress=runtime["collect_progress"],
        target=target_amount,
        done=runtime["collect_progress"] >= target_amount,
        item_id=target_item or gained_item or "*",
    )

    if runtime["collect_progress"] >= target_amount:
        runtime["collected"] = True
        _mark_done(game, mission, "CI")
    elif hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

# KE

def _start_ke(game, mission):
    runtime = mission.setdefault("runtime", {})
    runtime.setdefault("kills", 0)
    _sync_objective(
        mission,
        "KE",
        progress=runtime["kills"],
        target=_mission_amount(mission, typ="KE"),
        done=False,
    )
    return mission

def _ke_enemy_death(game, mission, enemy_id):
    target_enemy = _clean(
        _get_param_for_type(
            mission, "KE", "enemy_id", "target_id", "mob_id", "mob", default="*"
        )
    )
    if target_enemy not in ("", "*", "any") and str(enemy_id) != target_enemy:
        return
    if _enemy_is_elite(enemy_id):
        return

    target_amount = _mission_amount(mission, typ="KE")
    current = _objective_progress(mission, "KE", default=0)
    new_progress = min(target_amount, current + 1)

    runtime = mission.setdefault("runtime", {})
    runtime["kills"] = new_progress

    _sync_objective(
        mission,
        "KE",
        progress=new_progress,
        target=target_amount,
        done=new_progress >= target_amount,
        enemy_id=target_enemy,
    )
    if new_progress >= target_amount:
        _mark_done(game, mission, "KE")
    elif hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

# KEE

def _start_kee(game, mission):
    runtime = mission.setdefault("runtime", {})
    runtime.setdefault("elite_kills", 0)
    _sync_objective(
        mission,
        "KEE",
        progress=runtime["elite_kills"],
        target=_mission_amount(mission, typ="KEE"),
        done=False,
    )
    return mission

def _kee_enemy_death(game, mission, enemy_id):
    mission_enemy_id = _clean(
        _get_param_for_type(
            mission, "KEE", "enemy_id", "target_id", "mob_id", default=""
        )
    )
    if (
        mission_enemy_id
        and mission_enemy_id not in ("*", "any")
        and mission_enemy_id != str(enemy_id)
    ):
        return

    enemy_is_elite = _enemy_is_elite(enemy_id)
    if not enemy_is_elite and mission_enemy_id and mission_enemy_id == str(enemy_id):
        enemy_is_elite = _bool_value(
            _get_param(mission, "elite_only", "elite", "is_elite", "boss", default=False),
            default=False,
        )
    if not enemy_is_elite:
        return

    runtime = mission.setdefault("runtime", {})
    target_amount = _mission_amount(mission, typ="KEE")
    runtime["elite_kills"] = min(
        target_amount,
        int(runtime.get("elite_kills", 0) or 0) + 1,
    )
    _sync_objective(
        mission,
        "KEE",
        progress=runtime["elite_kills"],
        target=target_amount,
        done=runtime["elite_kills"] >= target_amount,
        enemy_id=mission_enemy_id or "*",
    )
    if runtime["elite_kills"] >= target_amount:
        _mark_done(game, mission, "KEE")
    elif hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

# CA

def _ca_target_map(mission):
    target = _get_param(mission, "map", "target_map", "map_id", "target_map_id")
    if isinstance(target, (list, tuple)):
        target = target[0] if target else ""
    target = _clean(target)
    if target and target != "rogue" and not target.endswith(".json"):
        target += ".json"
    return target

def _start_ca(game, mission):
    runtime = mission.setdefault("runtime", {})
    runtime.setdefault("cleared", False)
    runtime.setdefault("started", False)
    target_map_id = _ca_target_map(mission) or _clean(runtime.get("target_map_id"))
    runtime["target_map_id"] = target_map_id
    objectives = [
        obj
        for obj in mission.get("objectives", []) or []
        if isinstance(obj, dict) and _canon_type(obj.get("type")) == "CA"
    ]
    for obj in objectives:
        obj["target"] = 1
        obj.setdefault("progress", 1 if obj.get("done") else 0)
        obj.setdefault("done", False)
    runtime["cleared"] = bool(objectives) and all(
        bool(obj.get("done")) for obj in objectives
    )
    return mission


def _count_ca_hostiles(game, mission, objective):
    group = _clean(objective.get("spawn_group"))
    rect = _objective_area_rect(objective)
    mission_id = _clean(mission.get("id"))
    count = 0
    for ent in getattr(game, "entities", []) or []:
        if getattr(ent, "eid", None) == "player" or getattr(ent, "hp", 0) <= 0:
            continue
        mob_def = MOBS_DATA.get(str(getattr(ent, "eid", "")), {})
        if not isinstance(mob_def, dict) or _clean(mob_def.get("ai_type")).lower() != "hostile":
            continue
        if group:
            if _clean(getattr(ent, "mission_owner_id", "")) != mission_id:
                continue
            if _clean(getattr(ent, "mission_spawn_group", "")) != group:
                continue
        elif rect and not _rect_contains(rect, (getattr(ent, "x", -1), getattr(ent, "y", -1))):
            continue
        count += 1
    return count


def _ca_update(game, mission):
    runtime = mission.setdefault("runtime", {})
    if runtime.get("cleared"):
        return
    _ensure_mission_spawns(game, mission)
    objectives = [
        obj
        for obj in mission.get("objectives", []) or []
        if isinstance(obj, dict) and _canon_type(obj.get("type")) == "CA"
    ]
    if not objectives:
        return
    runtime["started"] = True
    total_remaining = 0
    for obj in objectives:
        if obj.get("done") or not _objective_map_matches(game, obj):
            continue
        remaining = _count_ca_hostiles(game, mission, obj)
        obj["hostiles_remaining"] = remaining
        obj["target"] = 1
        obj["progress"] = 0 if remaining else 1
        obj["done"] = remaining <= 0
        total_remaining += remaining
    runtime["hostiles_remaining"] = total_remaining
    runtime["cleared"] = all(bool(obj.get("done")) for obj in objectives)
    if runtime["cleared"]:
        _mark_done(game, mission, "CA")
    elif hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()

def _ca_enemy_death(game, mission, enemy_id):
    _ca_update(game, mission)

def _count_hostile_mobs(game):
    if hasattr(game, "count_hostile_mobs"):
        return int(game.count_hostile_mobs())

    count = 0
    for ent in getattr(game, "entities", []) or []:
        if getattr(ent, "eid", None) == "player":
            continue
        if getattr(ent, "hp", 0) <= 0:
            continue
        mob_def = MOBS_DATA.get(str(getattr(ent, "eid", "")), {}) if isinstance(MOBS_DATA, dict) else {}
        if _clean(mob_def.get("ai_type")).lower() != "hostile":
            continue
        count += 1

    return count

# CM

def _start_cm(game, mission):
    runtime = mission.setdefault("runtime", {})
    runtime.setdefault(
        "completed_missions_progress", _objective_progress(mission, "CM", default=0)
    )
    _sync_objective(
        mission,
        "CM",
        progress=runtime["completed_missions_progress"],
        target=_mission_amount(mission, typ="CM"),
        done=runtime["completed_missions_progress"] >= _mission_amount(mission, typ="CM"),
    )
    return mission


def _cm_mission_complete(game, mission, mission_id=None):
    if str(mission.get("id") or "") == str(mission_id or ""):
        return
    runtime = mission.setdefault("runtime", {})
    target_amount = _mission_amount(mission, typ="CM")
    runtime["completed_missions_progress"] = min(
        target_amount,
        int(runtime.get("completed_missions_progress", 0) or 0) + 1,
    )
    _sync_objective(
        mission,
        "CM",
        progress=runtime["completed_missions_progress"],
        target=target_amount,
        done=runtime["completed_missions_progress"] >= target_amount,
    )
    if runtime["completed_missions_progress"] >= target_amount:
        _mark_done(game, mission, "CM")
    elif hasattr(game, "_normalize_mission_state"):
        game._normalize_mission_state()
