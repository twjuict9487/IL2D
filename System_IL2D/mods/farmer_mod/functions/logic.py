"""Map entry and existing NPC integration for 緣緣莊."""

from .state import farm_runtime


def enter_farm(game, ctx):
    data = farm_runtime(ctx)["data"]
    data["prev_map_name"] = game.map.name
    data["prev_pos"] = [int(game.player.x), int(game.player.y)]
    game.load_map("farm_01.json")
    game.player.x, game.player.y = game.map.spawn
    game.ui_mode = None
    game.push_message("已進入緣緣莊；南側可找祀購物或開店")


def exit_farm(game, ctx):
    data = farm_runtime(ctx)["data"]
    previous = data.get("prev_map_name") or "map_1.json"
    position = data.get("prev_pos")
    game.load_map(previous)
    if isinstance(position, list) and len(position) == 2:
        game.player.x, game.player.y = int(position[0]), int(position[1])
    game.ui_mode = None
    game.push_message("已離開緣緣莊")


def open_shop(game):
    if game.ui_mode == "dialog":
        game.close_dialog()
    if not is_farm_map(game):
        enter_farm(game, game.runtime_context)
    elif (game.map.name == "farm_01.json" and
          abs(int(game.player.x) - 8) + abs(int(game.player.y) - 18) <= 2):
        game.ui_mode = "farm_shop"
        game.shop_selected = 0
    else:
        game.ui_mode = None
        game.push_message("請到南側購物區找祀")


def plot_key(x, y):
    return f"{int(x)},{int(y)}"


def is_farm_map(game):
    return (getattr(game, "map", None) is not None and
            game.map.name in {"farm_01.json", "farm_02.json", "farm_restaurant.json"})


def remove_farm_hostiles(game):
    if not is_farm_map(game):
        return
    kept = []
    for entity in list(getattr(game, "entities", [])):
        if getattr(entity, "eid", "") == "player":
            kept.append(entity)
            continue
        definition = game.get_entity_def(entity.eid) if hasattr(game, "get_entity_def") else {}
        if definition.get("ai_type") in ("hostile", "enemy"):
            continue
        kept.append(entity)
    game.entities = kept
