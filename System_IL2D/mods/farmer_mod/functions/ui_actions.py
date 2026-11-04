"""祀的商店、開店對話與餐廳爐台操作。"""

import pygame

from .business import COOK_POSITIONS, assign_recipe, buy_ingredients, buy_seed, queue_dish, start_business
from .state import farm_runtime


def rows(ctx):
    state = farm_runtime(ctx)
    cfg, data = state["cfg"], state["data"]
    result = [("start", "請祀開始營業（03:00）")]
    total = len(cfg.get("plots", [])) + len(cfg.get("field_plots", []))
    if int(data.get("owned_land", 0)) < total:
        result.append(("land", f"購買農地 +1　{cfg.get('land_price', 20)} 祀幣"))
    for crop, definition in cfg["crops"].items():
        result.append((f"seed:{crop}", f"購買{definition['name']}種子 +1　{definition['seed_price']} 祀幣"))
    for crop, definition in cfg["crops"].items():
        result.append((f"ingredient:{crop}",
                       f"購買{definition['name']}食材 +{definition['ingredient_pack_size']}　{definition['ingredient_pack_price']} 主貨幣"))
    result.append(("leave", "返回"))
    return result


def handle_key(ctx, event):
    game = ctx["game"]
    options = rows(ctx)
    if event.key in (pygame.K_UP, pygame.K_w):
        game.shop_selected = (game.shop_selected - 1) % len(options)
        return True
    if event.key in (pygame.K_DOWN, pygame.K_s):
        game.shop_selected = (game.shop_selected + 1) % len(options)
        return True
    if event.key == pygame.K_ESCAPE:
        game.ui_mode = None
        return True
    if event.key not in (pygame.K_RETURN, pygame.K_f, pygame.K_SPACE):
        return True
    action = options[game.shop_selected % len(options)][0]
    state = farm_runtime(ctx)
    data, cfg = state["data"], state["cfg"]
    if action == "start":
        if start_business(data, cfg):
            game.load_map("farm_restaurant.json")
            game.player.x, game.player.y = game.map.spawn
            if isinstance(getattr(game, "banner", None), dict):
                game.banner["text"] = "現正進入：緣緣莊餐廳"
            game.ui_mode = None
            game.push_message("營業開始：請到爐台按 E 指派菜色與排程")
        else:
            game.push_message("目前正在營業")
    elif action == "land":
        price = int(cfg.get("land_price", 20))
        total = len(cfg.get("plots", [])) + len(cfg.get("field_plots", []))
        if data["owned_land"] < total and data["si_currency"] >= price:
            data["si_currency"] -= price
            data["owned_land"] += 1
            game.push_message(f"農地已擴充至 {data['owned_land']}/{total}")
        else:
            game.push_message("祀幣不足")
    elif action.startswith("seed:"):
        crop = action.split(":", 1)[1]
        name = cfg["crops"][crop]["name"]
        game.push_message(f"已購買{name}種子" if buy_seed(data, cfg, crop) else "祀幣不足")
    elif action.startswith("ingredient:"):
        crop = action.split(":", 1)[1]
        name = cfg["crops"][crop]["name"]
        cost = buy_ingredients(data, cfg, crop, int(game.money))
        if cost is None:
            game.push_message("主貨幣不足")
        else:
            game.money -= cost
            game.push_message(f"已購買{name}食材 +{cfg['crops'][crop]['ingredient_pack_size']}")
    else:
        game.ui_mode = None
    return True


def kitchen_rows(ctx):
    state = farm_runtime(ctx)
    cook = state["data"]["restaurant"]["cooks"][state["kitchen_index"]]
    recipe = state["cfg"]["recipes"][cook["assignment"]]["name"]
    queued = len(cook["queue"]) + int(cook["active"] is not None)
    return [f"切換菜色：{recipe}", f"加入烹調佇列（{queued}/3）", "返回"]


def handle_kitchen_key(ctx, event):
    game = ctx["game"]
    state = farm_runtime(ctx)
    if event.key in (pygame.K_UP, pygame.K_w):
        state["kitchen_selected"] = (state.get("kitchen_selected", 0) - 1) % 3
        return True
    if event.key in (pygame.K_DOWN, pygame.K_s):
        state["kitchen_selected"] = (state.get("kitchen_selected", 0) + 1) % 3
        return True
    if event.key == pygame.K_ESCAPE:
        game.ui_mode = None
        return True
    if event.key not in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_f):
        return True
    choice = state.get("kitchen_selected", 0)
    index = state["kitchen_index"]
    data, cfg = state["data"], state["cfg"]
    cook = data["restaurant"]["cooks"][index]
    if choice == 0:
        recipes = list(cfg["recipes"])
        next_recipe = recipes[(recipes.index(cook["assignment"]) + 1) % len(recipes)]
        assign_recipe(data, cfg, index, next_recipe)
        game.push_message(f"廚師 {index + 1} 改做{cfg['recipes'][next_recipe]['name']}")
    elif choice == 1:
        game.push_message("已加入烹調佇列" if queue_dish(data, cfg, index) else "佇列已滿")
    else:
        game.ui_mode = None
    return True


def handle_result_key(ctx, event):
    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_f):
        ctx["game"].ui_mode = None
    return True


def farm_key(ctx, event):
    game = ctx["game"]
    name = game.map.name
    if event.key == pygame.K_ESCAPE:
        if name == "farm_02.json":
            game.load_map("farm_01.json")
            game.player.x, game.player.y = 14, 8
        elif name == "farm_restaurant.json":
            game.load_map("farm_01.json")
            game.player.x, game.player.y = 8, 20
        else:
            from .logic import exit_farm
            exit_farm(game, ctx)
        return True
    if event.key not in (pygame.K_e, pygame.K_f):
        return False
    if name == "farm_01.json" and abs(int(game.player.x) - 8) + abs(int(game.player.y) - 18) <= 2:
        game.ui_mode = "farm_shop"
        game.shop_selected = 0
        return True
    if name == "farm_restaurant.json":
        for index, (x, y) in enumerate(COOK_POSITIONS):
            if abs(int(game.player.x) - x) + abs(int(game.player.y) - y) <= 2:
                state = farm_runtime(ctx)
                state["kitchen_index"] = index
                state["kitchen_selected"] = 0
                game.ui_mode = "farm_kitchen"
                return True
    return False
