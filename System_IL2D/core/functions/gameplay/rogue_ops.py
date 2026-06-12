import os
import random
import time
from collections import deque

from ..models.entity import Entity
from ..support.i18n import tr
from ..world.map import GameMap, mobs_data
from ..support.utils import MAP_DIR, clamp, resolve_map_file


def get_mob_enemy_class(mob_id):
    mob = mobs_data.get(str(mob_id), {})
    if not isinstance(mob, dict):
        return "normal"
    return str(mob.get("enemy_class", "normal") or "normal").strip().lower()


def apply_rogue_special_boss_modifiers(entity, layer):
    layer = max(1, int(layer or 1))
    hp_multiplier = 1.5 + layer * 0.03
    attack_multiplier = 1.2 + layer * 0.02
    defence_multiplier = 1.1 + layer * 0.015
    reward_multiplier = 1.0 + layer * 0.02
    exp_multiplier = 1.0 + layer * 0.025
    entity.max_hp = max(1, int(entity.max_hp * hp_multiplier))
    entity.hp = entity.max_hp
    entity.attack = max(1, int(entity.attack * attack_multiplier))
    entity.defence = max(0, int(entity.defence * defence_multiplier))
    if hasattr(entity, "magic_attack"):
        entity.magic_attack = max(1, int(getattr(entity, "magic_attack", entity.attack) * attack_multiplier))
    if hasattr(entity, "magic_defense"):
        entity.magic_defense = float(getattr(entity, "magic_defense", 0) * defence_multiplier)
    entity.rogue_special_boss = True
    entity.rogue_reward_multiplier = reward_multiplier
    entity.reward_multiplier = reward_multiplier
    entity.rogue_exp_multiplier = exp_multiplier
    entity.exp_multiplier = exp_multiplier
    entity.width = 2
    entity.height = 2
    entity.size = 2
    return entity


def enter_rogue_layer(game, new_entry=False):
    if new_entry:
        game.rogue_layer = 0
        game.environment_difficulty = 0.0
        game.rogue_difficulty = 0.0
    game.rogue_layer += 1
    if hasattr(game, "record_legacy_mission_layer"):
        game.record_legacy_mission_layer(game.rogue_layer)
    cfg = getattr(game, "rogue_cfg", {})
    special_layer = max(1, int(cfg.get("special_layer", 15)))
    special_map = cfg.get("special_map", "rouge_options.json")
    if game.rogue_layer > 0 and game.rogue_layer % special_layer == 0:
        game.map = GameMap(resolve_map_file(special_map))
        if hasattr(game, "mark_map_explored"):
            game.mark_map_explored(game.map.name)
        if hasattr(game, "record_mission_map_explore"):
            try:
                game.record_mission_map_explore(game.map.name)
            except Exception:
                pass
        game.map_max_h_mob = game.map.mob_limit
        game.player.x, game.player.y = game.map.spawn
        game.entities = [
            e
            for e in game.entities
            if e.eid == "player"
            or e.ai_type == "team"
            or mobs_data.get(e.eid, {}).get("ai_type") in ("friendly", "neutral")
            or e.immortal
        ]
        game.place_npcs_for_map()
        game.teleport_team_to_player()
        game.set_objectives_for_map()
        game.show_enter_banner(special_map)
        game.rogue_rest_intro_done = False
        game.open_rogue_rest_intro()
        return

    boss_every = cfg.get("boss_every", 5)
    game.rogue_is_boss = game.rogue_layer % boss_every == 0
    size = (
        cfg.get("boss_size", [10, 15])
        if game.rogue_is_boss
        else cfg.get("normal_size", [20, 20])
    )
    w, h = size[0], size[1]
    data = generate_rogue_map(game, w, h)
    game.map = GameMap.from_data("rogue", data)
    if hasattr(game, "mark_map_explored"):
        game.mark_map_explored(game.map.name)
    if hasattr(game, "record_mission_map_explore"):
        try:
            game.record_mission_map_explore(game.map.name)
        except Exception:
            pass
    game.map_max_h_mob = game.map.mob_limit
    game.player.x, game.player.y = game.map.spawn
    game.place_npcs_for_map()
    game.teleport_team_to_player()
    game.set_objectives_for_map()
    if game.rogue_is_boss:
        layer_label = tr(game.lang, "banner.boss_layer", layer=game.rogue_layer)
    else:
        layer_label = tr(game.lang, "banner.layer", layer=game.rogue_layer)
    game.banner = {
        "text": tr(game.lang, "banner.now_entering", where=layer_label),
        "created": time.time(),
        "duration": 3.0,
    }
    if new_entry:
        retreat_name = cfg.get("retreat_item", "retreat item")
        game.inventory[retreat_name] = game.inventory.get(retreat_name, 0) + 1
    else:
        core = getattr(game, "tutorial_core", None)
        if (
            core
            and getattr(core, "active", False)
            and getattr(core, "current_id", lambda: None)() == "rogue_intro"
        ):
            retreat_name = cfg.get("retreat_item", "retreat item")
            if game.inventory.get(retreat_name, 0) <= 0:
                game.inventory[retreat_name] = game.inventory.get(retreat_name, 0) + 1
    spawn_rogue_mobs(game)


def enter_next_rogue_layer(game):
    enter_rogue_layer(game, new_entry=False)


def open_level_skipper_ui(game):
    available = game.inventory.get("rogue level skipper", 0)
    if available <= 0:
        game.push_message(tr(game.lang, "msg.no_items"))
        return
    if game.map.name not in ("rogue", "rouge_options.json"):
        game.push_message(tr(game.lang, "msg.skipper_only_rogue"))
        return
    game.level_skip_amount = 1
    game.ui_mode = "level_skipper"


def change_level_skip_amount(game, delta):
    available = max(1, game.inventory.get("rogue level skipper", 0))
    game.level_skip_amount = clamp(game.level_skip_amount + delta, 1, available)


def confirm_level_skipper_use(game):
    available = game.inventory.get("rogue level skipper", 0)
    if available <= 0:
        game.ui_mode = "item"
        game.push_message(tr(game.lang, "msg.no_items"))
        return
    if game.map.name not in ("rogue", "rouge_options.json"):
        game.ui_mode = "item"
        game.push_message(tr(game.lang, "msg.skipper_only_rogue"))
        return
    use_count = int(clamp(game.level_skip_amount, 1, available))
    game.inventory["rogue level skipper"] = max(0, available - use_count)
    diff = max(0.0, float(getattr(game, "environment_difficulty", 0.0)))
    diff = min(1.2, diff + (0.2 * use_count))
    game.environment_difficulty = diff
    # Keep legacy field in sync for backward compatibility.
    game.rogue_difficulty = diff
    game.rogue_layer = max(0, game.rogue_layer + use_count - 1)
    enter_next_rogue_layer(game)
    game.ui_mode = "item"
    game.push_message(tr(game.lang, "msg.skipper_used", count=use_count))


def use_level_skipper_hotbar(game):
    available = game.inventory.get("rogue level skipper", 0)
    if available <= 0:
        game.push_message(tr(game.lang, "msg.no_items"))
        return
    if game.map.name not in ("rogue", "rouge_options.json"):
        game.push_message(tr(game.lang, "msg.skipper_only_rogue"))
        return
    game.inventory["rogue level skipper"] = max(0, available - 1)
    diff = max(0.0, float(getattr(game, "environment_difficulty", 0.0)))
    diff = min(1.2, diff + 0.2)
    game.environment_difficulty = diff
    # Keep legacy field in sync for backward compatibility.
    game.rogue_difficulty = diff
    game.rogue_layer = max(0, game.rogue_layer)
    enter_next_rogue_layer(game)
    game.push_message(tr(game.lang, "msg.skipper_used", count=1))


def generate_rogue_map(game, w, h):
    grid = [["01" for _ in range(w)] for _ in range(h)]
    for x in range(w):
        grid[0][x] = "02"
        grid[h - 1][x] = "02"
    for y in range(h):
        grid[y][0] = "02"
        grid[y][w - 1] = "02"

    start = (2, h - 2) if h <= 15 else (1, h - 2)
    exit_pos = (w - 2, 1)

    def neighbors(cx, cy):
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h:
                yield nx, ny

    def is_block(tile_code):
        return tile_code in ("02", "05", "06", "07")

    def reachable_from_start():
        seen = set()
        q = deque([start])
        while q:
            cx, cy = q.popleft()
            if (cx, cy) in seen:
                continue
            if is_block(grid[cy][cx]):
                continue
            seen.add((cx, cy))
            for nx, ny in neighbors(cx, cy):
                if (nx, ny) not in seen and not is_block(grid[ny][nx]):
                    q.append((nx, ny))
        return seen

    reserved = {start, exit_pos}
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            sx, sy = start[0] + ox, start[1] + oy
            ex, ey = exit_pos[0] + ox, exit_pos[1] + oy
            if 1 <= sx < w - 1 and 1 <= sy < h - 1:
                reserved.add((sx, sy))
            if 1 <= ex < w - 1 and 1 <= ey < h - 1:
                reserved.add((ex, ey))
    if h > 13:
        reserved.add((1, 12))
        reserved.add((1, 13))

    interior = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1)]
    interior_count = len(interior)
    max_blockades = int(interior_count * 0.20)
    target_blockades = max(0, int(interior_count * 0.16))
    target_blockades = min(target_blockades, max_blockades)

    candidates = [p for p in interior if p not in reserved]
    random.shuffle(candidates)
    placed = 0
    for x, y in candidates:
        if placed >= target_blockades:
            break
        old = grid[y][x]
        grid[y][x] = random.choice(["05", "06"])
        reachable = reachable_from_start()
        walkable_tiles = {
            (ix, iy) for (ix, iy) in interior if not is_block(grid[iy][ix])
        }
        if exit_pos not in reachable or not walkable_tiles.issubset(reachable):
            grid[y][x] = old
            continue
        placed += 1

    # Add walkable decoration (flowers) without affecting connectivity.
    flower_target = max(0, int(interior_count * 0.08))
    flower_cells = [
        p for p in interior if p not in reserved and grid[p[1]][p[0]] == "01"
    ]
    random.shuffle(flower_cells)
    for x, y in flower_cells[:flower_target]:
        grid[y][x] = "09"

    exit_x, exit_y = exit_pos
    grid[exit_y][exit_x] = "04"
    return {
        "region": "ROGUE",
        "grid": grid,
        "spawn": [start[0], start[1]],
        "mob_limit": getattr(game, "rogue_cfg", {}).get("mob_limit_normal", 10),
        "portals": [],
    }


def spawn_rogue_mobs(game):
    game.entities = [
        e
        for e in game.entities
        if e.eid == "player"
        or e.ai_type == "team"
        or e.immortal
        or mobs_data.get(e.eid, {}).get("ai_type") in ("friendly", "neutral")
    ]
    if game.rogue_is_boss:
        spawn_rogue_boss(game)
        game.rogue_target_mobs = 1
        return
    game.rogue_target_mobs = getattr(game, "rogue_cfg", {}).get("mob_limit_normal", 10)
    count = game.count_hostile_mobs()
    target = game.rogue_target_mobs
    while count < target:
        if not game.spawn_random_hostile():
            break
        count = game.count_hostile_mobs()


def spawn_rogue_boss(game):
    boss_ids = [
        mob_id
        for mob_id, mob in mobs_data.items()
        if isinstance(mob, dict)
        and mob.get("ai_type") == "hostile"
        and get_mob_enemy_class(mob_id) == "boss"
    ]
    if not boss_ids:
        return
    random.shuffle(boss_ids)
    env_mult = 1.0 + max(0.0, float(getattr(game, "environment_difficulty", 0.0)))
    for base_id in boss_ids:
        max_x = max(0, game.map.w - 2)
        max_y = max(0, game.map.h - 2)
        bx, by = max_x // 2, max_y // 2
        if not game.can_spawn_entity_at_size(bx, by, 2, 2):
            placed = False
            for _ in range(100):
                tx = random.randint(0, max_x)
                ty = random.randint(0, max_y)
                if game.can_spawn_entity_at_size(tx, ty, 2, 2):
                    bx, by = tx, ty
                    placed = True
                    break
            if not placed:
                continue
        boss = game.create_hostile_entity(
            base_id,
            bx,
            by,
            width=2,
            height=2,
            hp_multiplier=env_mult,
            attack_multiplier=env_mult,
            defence_multiplier=env_mult,
            extra_flags={
                "rogue_boss_class": True,
                "enemy_class": "boss",
            },
        )
        if boss is None:
            continue
        apply_rogue_special_boss_modifiers(boss, getattr(game, "rogue_layer", 1))
        game.entities.append(boss)
        return
