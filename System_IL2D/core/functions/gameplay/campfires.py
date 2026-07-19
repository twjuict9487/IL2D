import math
import time

from ..support.i18n import tr
from ..support.utils import load_json, resolve_map_file


ATTRACTION_RADIUS = 92.0
RELEASE_COOLDOWN = 1.5
MARKER_OFFSET_Y = -52.0


def normalize_definitions(raw):
    definitions = []
    seen = set()
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        campfire_id = str(row.get("id", "") or "").strip()
        arrival = row.get("arrival")
        if not campfire_id or campfire_id in seen:
            continue
        if not isinstance(arrival, (list, tuple)) or len(arrival) < 2:
            continue
        try:
            campfire = {
                "id": campfire_id,
                "x": int(row.get("x")),
                "y": int(row.get("y")),
                "arrival": [int(arrival[0]), int(arrival[1])],
                "opens_save": bool(row.get("opens_save", False)),
            }
        except (TypeError, ValueError):
            continue
        seen.add(campfire_id)
        definitions.append(campfire)
    return definitions


def rebuild_registry(game):
    registry = {}
    for node_id, node in (getattr(game, "world_map_nodes", {}) or {}).items():
        if not isinstance(node, dict):
            continue
        map_name = str(node.get("map") or node_id or "").strip()
        position = node.get("position")
        if not map_name or not isinstance(position, list) or len(position) < 2:
            continue
        map_path = resolve_map_file(map_name)
        try:
            data = load_json(map_path)
        except Exception:
            continue
        for definition in normalize_definitions(data.get("campfires", [])):
            campfire_id = definition["id"]
            if campfire_id in registry:
                print(f"[campfire] duplicate stable id ignored: {campfire_id}")
                continue
            row = dict(definition)
            row.update(
                {
                    "map": map_name,
                    "node_id": node_id,
                    "world_position": [
                        float(position[0]),
                        float(position[1]) + MARKER_OFFSET_Y,
                    ],
                    "label_en": str(node.get("label_en") or map_name),
                    "label_zh": str(node.get("label_zh") or node.get("label_en") or map_name),
                }
            )
            registry[campfire_id] = row
    game.campfire_registry = registry
    return registry


def state_for(game, definition):
    campfire_id = str(definition.get("id", "") or "")
    if campfire_id in getattr(game, "activated_campfires", set()):
        return "activated_lit"
    map_name = str(definition.get("map") or getattr(getattr(game, "map", None), "name", ""))
    node_id = str(definition.get("node_id") or "")
    explored = set(getattr(game, "explored_maps", set()) or set())
    if map_name in explored or node_id in explored:
        return "discovered_unlit"
    return "undiscovered"


def current_definitions(game):
    return list(getattr(getattr(game, "map", None), "campfires", []) or [])


def campfire_at(game, x, y):
    for row in current_definitions(game):
        if int(row.get("x", -1)) == int(x) and int(row.get("y", -1)) == int(y):
            return row
    return None


def blocks_tile(game, x, y):
    return campfire_at(game, x, y) is not None


def nearby(game, include_current=True):
    px = int(getattr(game.player, "x", -999))
    py = int(getattr(game.player, "y", -999))
    max_distance = 1 if include_current else 0
    rows = []
    for row in current_definitions(game):
        distance = abs(int(row["x"]) - px) + abs(int(row["y"]) - py)
        if distance <= max_distance:
            rows.append((distance, row))
    rows.sort(key=lambda item: (item[0], item[1]["id"]))
    return rows[0][1] if rows else None


def activate_nearby(game):
    definition = nearby(game)
    if not definition:
        return False
    campfire_id = definition["id"]
    activated = getattr(game, "activated_campfires", None)
    if not isinstance(activated, set):
        activated = set(activated or [])
        game.activated_campfires = activated
    if campfire_id in activated:
        try:
            from . import missions as game_missions

            game_missions.update_on_key_interact(game, campfire_id)
        except Exception as exc:
            print(f"[campfire] mission event failed: {exc}")
        game.push_message(tr(game.lang, "campfire.already_lit"))
        return True
    activated.add(campfire_id)
    try:
        from . import missions as game_missions

        game_missions.update_on_key_interact(game, campfire_id)
    except Exception as exc:
        print(f"[campfire] mission event failed: {exc}")
    game.push_message(tr(game.lang, "campfire.activated"))
    audio = getattr(game, "audio", None)
    if audio:
        audio.play_sfx("level_up")
    return True


def visible_markers(game):
    rows = []
    for definition in (getattr(game, "campfire_registry", {}) or {}).values():
        state = state_for(game, definition)
        if state == "undiscovered":
            continue
        row = dict(definition)
        row["state"] = state
        rows.append(row)
    return rows


def reset_reticle(game):
    nodes = getattr(game, "world_map_nodes", {}) or {}
    current_map = str(getattr(getattr(game, "map", None), "name", "") or "")
    current = nodes.get(current_map)
    if not current:
        current = next(
            (
                node
                for node in nodes.values()
                if isinstance(node, dict) and str(node.get("map") or "") == current_map
            ),
            None,
        )
    canvas = getattr(game, "world_map_canvas", {}) or {}
    position = (current or {}).get(
        "position",
        [float(canvas.get("width", 0)) / 2, float(canvas.get("height", 0)) / 2],
    )
    game.world_map_reticle_x = float(position[0])
    game.world_map_reticle_y = float(position[1])
    game.world_map_reticle_state = "FREE"
    game.world_map_reticle_target = None
    game.world_map_reticle_blocked = None
    game.world_map_reticle_release_until = 0.0
    game.world_map_pan_initialized = True


def release_reticle(game):
    target_id = getattr(game, "world_map_reticle_target", None)
    game.world_map_reticle_state = "RELEASED"
    game.world_map_reticle_blocked = target_id
    game.world_map_reticle_target = None
    game.world_map_reticle_release_until = time.monotonic() + RELEASE_COOLDOWN


def move_reticle(game, dx, dy, step=72.0):
    state = str(getattr(game, "world_map_reticle_state", "FREE") or "FREE")
    if state in {"ATTRACTING", "SNAPPED"}:
        release_reticle(game)
    canvas = getattr(game, "world_map_canvas", {}) or {}
    width = max(0.0, float(canvas.get("width", 0) or 0))
    height = max(0.0, float(canvas.get("height", 0) or 0))
    game.world_map_reticle_x = max(
        0.0,
        min(width, float(getattr(game, "world_map_reticle_x", width / 2)) + dx * step),
    )
    game.world_map_reticle_y = max(
        0.0,
        min(height, float(getattr(game, "world_map_reticle_y", height / 2)) + dy * step),
    )
    return True


def update_reticle(game, dt, now=None):
    now = time.monotonic() if now is None else float(now)
    state = str(getattr(game, "world_map_reticle_state", "FREE") or "FREE")
    x = float(getattr(game, "world_map_reticle_x", 0.0))
    y = float(getattr(game, "world_map_reticle_y", 0.0))
    markers = {
        row["id"]: row
        for row in visible_markers(game)
        if row.get("state") == "activated_lit"
    }

    if state == "RELEASED":
        blocked_id = getattr(game, "world_map_reticle_blocked", None)
        blocked = markers.get(blocked_id)
        if blocked:
            bx, by = blocked["world_position"]
            if math.hypot(x - bx, y - by) > ATTRACTION_RADIUS + 12:
                game.world_map_reticle_blocked = None
        else:
            game.world_map_reticle_blocked = None
        if now >= float(getattr(game, "world_map_reticle_release_until", 0.0)) and not getattr(
            game, "world_map_reticle_blocked", None
        ):
            game.world_map_reticle_state = "FREE"
        return

    if state == "ATTRACTING":
        target_id = getattr(game, "world_map_reticle_target", None)
        marker = markers.get(target_id)
        if not marker:
            release_reticle(game)
            return
        tx, ty = marker["world_position"]
        factor = min(0.35, max(0.0, float(dt)) * 6.0)
        x += (tx - x) * factor
        y += (ty - y) * factor
        game.world_map_reticle_x = x
        game.world_map_reticle_y = y
        if math.hypot(x - tx, y - ty) <= 2.0:
            game.world_map_reticle_x = float(tx)
            game.world_map_reticle_y = float(ty)
            game.world_map_reticle_state = "SNAPPED"
        return

    if state != "FREE" or now < float(getattr(game, "world_map_reticle_release_until", 0.0)):
        return
    nearest = None
    nearest_distance = ATTRACTION_RADIUS + 1.0
    for marker in markers.values():
        mx, my = marker["world_position"]
        distance = math.hypot(x - mx, y - my)
        if distance <= ATTRACTION_RADIUS and distance < nearest_distance:
            nearest = marker
            nearest_distance = distance
    if nearest:
        game.world_map_reticle_target = nearest["id"]
        game.world_map_reticle_state = "ATTRACTING"


def fast_travel(game, campfire_id):
    campfire_id = str(campfire_id or "")
    definition = (getattr(game, "campfire_registry", {}) or {}).get(campfire_id)
    if not definition or campfire_id not in getattr(game, "activated_campfires", set()):
        game.push_message(tr(game.lang, "campfire.travel_locked"))
        return False
    target_map = definition["map"]
    arrival = tuple(definition["arrival"])

    def do_load():
        game.load_map(target_map)
        if not game.map.is_walkable(*arrival) or blocks_tile(game, *arrival):
            game.push_message(tr(game.lang, "campfire.arrival_blocked"))
            return
        game.player.x, game.player.y = arrival
        game.teleport_team_to_player()
        game.push_message(tr(game.lang, "campfire.travel_complete"))

    audio = getattr(game, "audio", None)
    if audio:
        audio.play_sfx("confirm")
    game.start_transition(do_load)
    return True
