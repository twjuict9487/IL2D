from core.mod_loader import register_hook

from .functions.hooks import on_game_key, on_render, on_update
from .functions.logic import open_shop
from .functions.state import attach_save_hook, farm_runtime, load_state


# 模組主入口；只負責初始化與掛接 hooks，不放業務邏輯。
def register_mod(ctx):
    game = ctx["game"]
    farm_runtime(ctx)
    load_state(game, ctx)
    attach_save_hook(game, ctx)

    setattr(game, "farm_open_shop", lambda: open_shop(game))
    register_hook(ctx, "on_game_key", on_game_key)
    register_hook(ctx, "on_update", on_update)
    register_hook(ctx, "on_render", on_render)
