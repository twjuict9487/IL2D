import time

import pygame

from core.functions.world.map import GameMap

from .state import farm_runtime, farm_map_path


# 回傳目前選中的種子種類。
def active_seed(state_data):
    return ["rice", "wheat"][state_data.get("panel_index", 0) % 2]


# 進入農場地圖，並記錄回程位置。
def enter_farm(game, ctx):
    state = farm_runtime(ctx)
    data = state["data"]
    if int(data.get("owned_land", 0)) <= 0:
        game.push_message("need land first")
        return
    data["prev_map_name"] = game.map.name
    data["prev_pos"] = [int(game.player.x), int(game.player.y)]
    game.map = GameMap(farm_map_path())
    game.player.x, game.player.y = game.map.spawn
    game.ui_mode = None
    game.push_message("farmer mode on")


# 離開農場並回到先前地圖與位置。
def exit_farm(game, ctx):
    state = farm_runtime(ctx)
    data = state["data"]
    prev_map = data.get("prev_map_name") or "map_1.json"
    prev_pos = data.get("prev_pos")
    game.load_map(prev_map)
    if isinstance(prev_pos, list) and len(prev_pos) == 2:
        game.player.x = int(prev_pos[0])
        game.player.y = int(prev_pos[1])
    game.ui_mode = None
    game.push_message("farmer mode off")


# 打開農場商店 UI。
def open_shop(game):
    if game.ui_mode == "dialog":
        game.close_dialog()
    game.ui_mode = "farm_shop"
    game.shop_selected = 0


# 產生農場商店選單項目。
def shop_rows(ctx):
    state = farm_runtime(ctx)
    cfg = state["cfg"]
    land_price = int(cfg.get("land_price", 100))
    rice_seed = int(cfg["crops"]["rice"]["seed_price"])
    wheat_seed = int(cfg["crops"]["wheat"]["seed_price"])
    return [
        ("buy_land", f"Buy Land (+1) - {land_price} RBX"),
        ("buy_rice_seed", f"Buy Rice Seed (+1) - {rice_seed} RBX"),
        ("buy_wheat_seed", f"Buy Wheat Seed (+1) - {wheat_seed} RBX"),
        ("sell_crops", "Sell All Crops"),
        ("enter_farm", "Enter Farmland"),
        ("leave", "Back"),
    ]


# 處理農場商店鍵盤操作與交易邏輯。
def handle_shop_key(ctx, event):
    game = ctx["game"]
    rows = shop_rows(ctx)
    if event.key in (pygame.K_UP, pygame.K_w):
        game.shop_selected = (game.shop_selected - 1) % len(rows)
        return True
    if event.key in (pygame.K_DOWN, pygame.K_s):
        game.shop_selected = (game.shop_selected + 1) % len(rows)
        return True
    if event.key == pygame.K_ESCAPE:
        game.ui_mode = None
        return True
    if event.key not in (pygame.K_RETURN, pygame.K_f):
        return True

    action = rows[game.shop_selected % len(rows)][0]
    state = farm_runtime(ctx)
    cfg = state["cfg"]
    data = state["data"]
    if action == "buy_land":
        price = int(cfg.get("land_price", 100))
        max_land = len(cfg.get("plots", []))
        if data.get("owned_land", 0) >= max_land:
            game.push_message("land maxed")
        elif game.money < price:
            game.push_message("not enough RBX")
        else:
            game.money -= price
            data["owned_land"] = int(data.get("owned_land", 0)) + 1
            game.push_message("land +1")
    elif action == "buy_rice_seed":
        price = int(cfg["crops"]["rice"]["seed_price"])
        if game.money < price:
            game.push_message("not enough RBX")
        else:
            game.money -= price
            data["seeds"]["rice"] = int(data["seeds"].get("rice", 0)) + 1
            game.push_message("rice seed +1")
    elif action == "buy_wheat_seed":
        price = int(cfg["crops"]["wheat"]["seed_price"])
        if game.money < price:
            game.push_message("not enough RBX")
        else:
            game.money -= price
            data["seeds"]["wheat"] = int(data["seeds"].get("wheat", 0)) + 1
            game.push_message("wheat seed +1")
    elif action == "sell_crops":
        total = 0
        for crop in ("rice", "wheat"):
            count = int(data["crops"].get(crop, 0))
            if count <= 0:
                continue
            total += count * int(cfg["crops"][crop]["sell_price"])
            data["crops"][crop] = 0
        if total > 0:
            game.money += total
            game.push_message(f"sell +{total} RBX")
        else:
            game.push_message("no crops to sell")
    elif action == "enter_farm":
        enter_farm(game, ctx)
    else:
        game.ui_mode = None
    return True


# 產生地塊座標鍵值（x,y）。
def plot_key(x, y):
    return f"{int(x)},{int(y)}"


# 判斷目前是否在農場地圖。
def is_farm_map(game):
    return getattr(game, "map", None) is not None and game.map.name == "farm_01.json"


# 在農場地圖移除敵對怪，避免干擾農耕流程。
def remove_farm_hostiles(game):
    if not is_farm_map(game):
        return
    kept = []
    for ent in list(getattr(game, "entities", [])):
        if getattr(ent, "eid", "") == "player":
            kept.append(ent)
            continue
        ent_def = (
            game.get_entity_def(ent.eid) if hasattr(game, "get_entity_def") else {}
        )
        if ent_def.get("ai_type") in ("hostile", "enemy"):
            continue
        kept.append(ent)
    game.entities = kept


# 處理農地內快捷鍵（選種、播種、收成、離開）。
def handle_farm_key(ctx, event):
    game = ctx["game"]
    state = farm_runtime(ctx)
    data = state["data"]
    if event.key == pygame.K_ESCAPE:
        exit_farm(game, ctx)
        return True
    if event.key == pygame.K_i:
        data["panel_index"] = (int(data.get("panel_index", 0)) - 1) % 2
        return True
    if event.key == pygame.K_k:
        data["panel_index"] = (int(data.get("panel_index", 0)) + 1) % 2
        return True
    if event.key in (pygame.K_j, pygame.K_l):
        data["panel_index"] = 1 - (int(data.get("panel_index", 0)) % 2)
        return True
    if event.key != pygame.K_f:
        return False

    px, py = int(game.player.x), int(game.player.y)
    plots = state["cfg"].get("plots", [])
    plot_index = None
    for i, pt in enumerate(plots):
        if int(pt[0]) == px and int(pt[1]) == py:
            plot_index = i
            break
    if plot_index is None:
        game.push_message("stand on a farm tile")
        return True
    if plot_index >= int(data.get("owned_land", 0)):
        game.push_message("land not owned")
        return True

    key = plot_key(px, py)
    planted = data.setdefault("planted", {})
    now = time.time()
    grow_seconds = int(state["cfg"].get("grow_seconds", 10))
    entry = planted.get(key)
    if entry:
        planted_at = float(entry.get("planted_at", now))
        if now - planted_at >= grow_seconds:
            crop = entry.get("crop", "rice")
            data["crops"][crop] = int(data["crops"].get(crop, 0)) + 1
            planted.pop(key, None)
            game.push_message(f"harvest {crop} +1")
            return True
        game.push_message("not ready")
        return True

    crop = active_seed(data)
    if int(data["seeds"].get(crop, 0)) <= 0:
        game.push_message(f"no {crop} seed")
        return True
    data["seeds"][crop] = int(data["seeds"].get(crop, 0)) - 1
    planted[key] = {"crop": crop, "planted_at": now}
    game.push_message(f"plant {crop}")
    return True
