from .logic import is_farm_map, remove_farm_hostiles
from .ui_actions import (handle_key as handle_shop_key, farm_key as handle_farm_key,
                         handle_kitchen_key, handle_result_key)
from .npc import ensure_shu
from .rendering import render as render_ui
from .state import default_state, farm_runtime, load_state, slot_key
from .business import update_farm, update_restaurant


# 處理農場模組的按鍵 hook。
def on_game_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode == "farm_shop":
        return handle_shop_key(ctx, event)
    if game.ui_mode == "farm_kitchen":
        return handle_kitchen_key(ctx, event)
    if game.ui_mode == "farm_result":
        return handle_result_key(ctx, event)
    if is_farm_map(game):
        return handle_farm_key(ctx, event)
    return False


# 處理農場模組每幀更新 hook。
def on_update(ctx, _dt):
    game = ctx["game"]
    map_name = getattr(game.map, "name", "")
    last_map = ctx.setdefault("farmer_mod", {}).get("last_map")
    if map_name != last_map:
        ctx["farmer_mod"]["last_map"] = map_name
        labels = {"farm_01.json": "緣緣莊農場", "farm_02.json": "緣緣莊田野",
                  "farm_restaurant.json": "緣緣莊餐廳"}
        if map_name in labels and isinstance(getattr(game, "banner", None), dict):
            game.banner["text"] = f"現正進入：{labels[map_name]}"
    ensure_shu(game)
    remove_farm_hostiles(game)

    try:
        nodes = getattr(game, "world_map_nodes", {})
        structured = bool(nodes) and all(
            isinstance(meta, dict) and isinstance(meta.get("position"), list)
            for meta in nodes.values()
        )
        if isinstance(nodes, dict) and not structured:
            nodes.setdefault("farm_01.json", {"w": 16, "h": 16})
            game.world_map_nodes = nodes
        if not structured:
            edges = set(
                tuple(edge)
                for edge in (getattr(game, "world_map_edges", []) or [])
                if isinstance(edge, (list, tuple)) and len(edge) >= 2
            )
            edges.add(tuple(sorted(("map_2.json", "farm_01.json"))))
            game.world_map_edges = sorted(list(edges))
    except Exception:
        pass

    state = farm_runtime(ctx)
    loaded_slot = state.get("loaded_slot")
    slot = slot_key(game)
    if loaded_slot != slot:
        state["data"] = default_state(state["cfg"])
        load_state(game, ctx)
        state["loaded_slot"] = slot
    if getattr(game.map, "name", "") == "farm_01.json":
        game.map.grid[21][8] = "03" if state["data"]["restaurant"]["business_active"] else "02"
    if ctx.get("state") == "game":
        update_farm(state["data"], state["cfg"], _dt)
        was_open = state["data"]["restaurant"]["business_active"]
        update_restaurant(state["data"], state["cfg"], _dt)
        if was_open and not state["data"]["restaurant"]["business_active"]:
            game.push_message("緣緣莊營業結束")
            if game.ui_mode in (None, "farm_kitchen"):
                game.ui_mode = "farm_result"
                state["result_pending"] = False
            else:
                state["result_pending"] = True
        if state.get("result_pending") and game.ui_mode is None:
            game.ui_mode = "farm_result"
            state["result_pending"] = False


# 處理農場模組渲染 hook。
def on_render(ctx, screen):
    render_ui(ctx, screen)
