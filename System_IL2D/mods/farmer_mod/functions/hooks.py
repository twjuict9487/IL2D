from .logic import handle_farm_key, handle_shop_key, is_farm_map, remove_farm_hostiles
from .npc import ensure_shu
from .rendering import render as render_ui
from .state import default_state, farm_runtime, load_state, slot_key


# 處理農場模組的按鍵 hook。
def on_game_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode == "farm_shop":
        return handle_shop_key(ctx, event)
    if is_farm_map(game):
        return handle_farm_key(ctx, event)
    return False


# 處理農場模組每幀更新 hook。
def on_update(ctx, _dt):
    game = ctx["game"]
    ensure_shu(game)
    remove_farm_hostiles(game)

    try:
        nodes = getattr(game, "world_map_nodes", {})
        if isinstance(nodes, dict):
            nodes.setdefault("farm_01.json", {"w": 16, "h": 16})
            game.world_map_nodes = nodes
        edges = set(tuple(e) for e in (getattr(game, "world_map_edges", []) or []))
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


# 處理農場模組渲染 hook。
def on_render(ctx, screen):
    render_ui(ctx, screen)
