import pygame

from core.functions.rendering.draw import TILE_SIZE, VIEWPORT
from core.functions.support.asset_resolver import resolve_image_candidates

from .logic import is_farm_map, plot_key
from .ui_actions import rows as shop_rows
from .business import normalize
from .business import COOK_POSITIONS, TABLE_POSITIONS, KITCHEN_POSITION
from .ui_actions import kitchen_rows
from .state import farm_runtime

_IMG_CACHE = {}


def _load_img(name, size):
    key = (name, int(size[0]), int(size[1]))
    if key in _IMG_CACHE:
        return _IMG_CACHE[key]
    for path in resolve_image_candidates(name):
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (int(size[0]), int(size[1])))
            _IMG_CACHE[key] = img
            return img
        except Exception:
            continue
    _IMG_CACHE[key] = None
    return None


# 將世界座標（tile）轉為畫面座標（pixel）。
def world_to_screen(game, tx, ty):
    map_view_w = VIEWPORT
    map_view_h = VIEWPORT
    tile_w = TILE_SIZE
    tile_h = TILE_SIZE
    view_w_px = map_view_w * tile_w
    view_h_px = map_view_h * tile_h
    px, py = game.player.x, game.player.y
    if hasattr(game, "get_player_draw_pos"):
        px, py = game.get_player_draw_pos()
    cam_px = px * tile_w + tile_w / 2 - view_w_px / 2
    cam_py = py * tile_h + tile_h / 2 - view_h_px / 2
    max_cam_px = max(0, game.map.w * tile_w - view_w_px)
    max_cam_py = max(0, game.map.h * tile_h - view_h_px)
    cam_px = max(0, min(max_cam_px, cam_px))
    cam_py = max(0, min(max_cam_py, cam_py))
    return int(tx * tile_w - cam_px), int(ty * tile_h - cam_py)


# 畫農地格子覆蓋層（已購、未購、生長中、可收成、目前格）。
def draw_farm_land_overlay(screen, game, state):
    data = state["data"]
    cfg = state["cfg"]
    owned = int(data.get("owned_land", 0))
    field = game.map.name == "farm_02.json"
    plots = cfg.get("field_plots", []) if field else cfg.get("plots", [])
    ownership_offset = len(cfg.get("plots", [])) if field else 0
    planted = data.get("planted", {})
    player_pos = (int(game.player.x), int(game.player.y))

    for idx, pt in enumerate(plots):
        tx, ty = int(pt[0]), int(pt[1])
        sx, sy = world_to_screen(game, tx, ty)
        if (
            sx < -TILE_SIZE
            or sy < -TILE_SIZE
            or sx > screen.get_width()
            or sy > screen.get_height()
        ):
            continue
        rect = pygame.Rect(sx, sy, TILE_SIZE, TILE_SIZE)

        fill = (120, 85, 45, 125) if idx + ownership_offset < owned else (35, 45, 55, 90)
        entry = planted.get(("field:" if field else "") + plot_key(tx, ty))
        icon = None
        if entry:
            growth = float(cfg["crops"].get(entry.get("crop"), {}).get("growth_time", 10))
            fill = (
                (170, 150, 65, 165)
                if float(entry.get("elapsed", 0.0)) >= growth
                else (60, 130, 70, 155)
            )
            crop = str(entry.get("crop", "rice"))
            icon_name = "Amber_Rice_nobg.png" if crop == "rice" else "wheat_nobg.png"
            icon = _load_img(icon_name, (int(TILE_SIZE * 0.62), int(TILE_SIZE * 0.62)))

        overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        overlay.fill(fill)
        screen.blit(overlay, (rect.x, rect.y))
        if icon is not None:
            ix = rect.x + (TILE_SIZE - icon.get_width()) // 2
            iy = rect.y + (TILE_SIZE - icon.get_height()) // 2
            screen.blit(icon, (ix, iy))
        pygame.draw.rect(screen, (80, 55, 28), rect, 1)
        if (tx, ty) == player_pos:
            pygame.draw.rect(screen, (255, 255, 255), rect, 3)


# 畫農場商店 UI。
def render(ctx, screen):
    game = ctx["game"]
    state = farm_runtime(ctx)
    name = getattr(game.map, "name", "")
    if name in ("farm_01.json", "farm_02.json") and game.ui_mode is None:
        draw_farm_land_overlay(screen, game, state)
        font = pygame.font.SysFont("microsoftjhenghei", 16)
        if name == "farm_01.json":
            x, y = world_to_screen(game, 8, 18)
            si_image = _load_img("祀_nobg.png", (48, 48))
            if si_image is not None:
                screen.blit(si_image, (x + 6, y + 4))
            else:
                pygame.draw.circle(screen, (115, 220, 250), (x + 30, y + 30), 18)
            label = font.render("祀的商店　靠近按 E 購物／開店", True, (255, 240, 185))
            screen.blit(label, (max(5, x - 55), max(5, y - 24)))
            area = font.render("購物區　南門通往餐廳", True, (230, 225, 185))
            ax, ay = world_to_screen(game, 8, 20)
            screen.blit(area, (max(5, ax - 30), max(5, ay)))
        else:
            label = font.render("緣緣莊農田　自動耕作　西側返回", True, (235, 240, 215))
            screen.blit(label, (12, 12))
    if name == "farm_restaurant.json":
        draw_restaurant_world(screen, game, state)
    if game.ui_mode == "farm_shop":
        draw_si_shop(screen, game, state)
    elif game.ui_mode == "farm_kitchen":
        draw_kitchen_panel(screen, state)
    elif game.ui_mode == "farm_result":
        draw_result_panel(screen, state)


def _management_panel(screen, width, height):
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 165))
    screen.blit(shade, (0, 0))
    panel = pygame.Rect(0, 0, min(width, screen.get_width() - 24),
                        min(height, screen.get_height() - 24))
    panel.center = screen.get_rect().center
    pygame.draw.rect(screen, (9, 27, 35), panel, border_radius=8)
    pygame.draw.rect(screen, (150, 210, 220), panel, 2, border_radius=8)
    return panel


def draw_si_shop(screen, game, state):
    panel = _management_panel(screen, 560, 450)
    title = pygame.font.SysFont("microsoftjhenghei", 24, bold=True)
    font = pygame.font.SysFont("microsoftjhenghei", 18)
    data, cfg = state["data"], state["cfg"]
    portrait = _load_img("祀_nobg.png", (66, 66))
    if portrait:
        screen.blit(portrait, (panel.x + 18, panel.y + 12))
    screen.blit(title.render("祀的商店", True, (240, 240, 215)), (panel.x + 94, panel.y + 24))
    balance = f"主貨幣：{game.money}　祀幣：{data['si_currency']}"
    screen.blit(font.render(balance, True, (255, 225, 145)),
                (panel.right - 260, panel.y + 29))
    for index, (_action, label) in enumerate(shop_rows({"farmer_mod": state})):
        y = panel.y + 94 + index * 40
        if index == game.shop_selected:
            pygame.draw.rect(screen, (49, 83, 91), (panel.x + 18, y - 3, panel.w - 36, 35), border_radius=4)
        screen.blit(font.render(label, True, (255, 230, 150) if index == game.shop_selected
                                else (225, 235, 235)), (panel.x + 28, y + 2))
    stock = "　".join(f"{cfg['crops'][crop]['name']}種 {data['seeds'][crop]}／食材 {data['crops'][crop]}"
                    for crop in cfg["crops"])
    screen.blit(font.render(stock, True, (185, 220, 190)), (panel.x + 22, panel.bottom - 62))
    hint = pygame.font.SysFont("microsoftjhenghei", 14)
    screen.blit(hint.render("W／S 選擇　Enter 確認　ESC 返回", True, (175, 205, 220)),
                (panel.x + 22, panel.bottom - 30))


def draw_restaurant_world(screen, game, state):
    data, cfg = state["data"], state["cfg"]
    restaurant = normalize(data, cfg)
    small = pygame.font.SysFont("microsoftjhenghei", 14)
    font = pygame.font.SysFont("microsoftjhenghei", 18)
    remaining = max(0, int(restaurant["remaining"]))
    status = "營業中" if restaurant["business_active"] else "未營業"
    hud = pygame.Rect(10, 10, min(screen.get_width() - 20, 575), 43)
    pygame.draw.rect(screen, (7, 24, 34), hud, border_radius=5)
    screen.blit(font.render(f"緣緣莊餐廳　{status}　{remaining // 60:02d}:{remaining % 60:02d}　收入 {restaurant['revenue']} 祀幣",
                            True, (250, 235, 190)), (hud.x + 10, hud.y + 10))
    for index, (tx, ty) in enumerate(COOK_POSITIONS):
        x, y = world_to_screen(game, tx, ty)
        cook = restaurant["cooks"][index]
        recipe_id = cook["active"] or cook["assignment"]
        recipe = cfg["recipes"][recipe_id]
        duration = max(0.1, float(recipe["cook_seconds"]))
        progress = min(1.0, float(cook["progress"]) / duration) if cook["active"] else 0.0
        pygame.draw.rect(screen, (80, 42, 25), (x + 4, y + 11, 52, 41), border_radius=5)
        pygame.draw.rect(screen, (255, 145, 62), (x + 10, y + 19, 40, 17), border_radius=4)
        screen.blit(small.render(f"爐{index + 1} {recipe['name']}", True, (255, 240, 205)), (x - 9, y - 10))
        pygame.draw.rect(screen, (60, 65, 68), (x + 6, y + 48, 48, 5))
        pygame.draw.rect(screen, (245, 210, 95), (x + 6, y + 48, round(48 * progress), 5))
    table_colors = {"EMPTY": (77, 93, 83), "OCCUPIED": (99, 80, 58),
                    "WAITING_FOR_FOOD": (145, 100, 48), "EATING": (67, 115, 81)}
    table_labels = {"EMPTY": "空桌", "OCCUPIED": "入座", "WAITING_FOR_FOOD": "候餐", "EATING": "用餐"}
    for index, (tx, ty) in enumerate(TABLE_POSITIONS):
        x, y = world_to_screen(game, tx, ty)
        table = restaurant["tables"][index]
        pygame.draw.rect(screen, table_colors.get(table["state"], (70, 70, 70)),
                         (x + 5, y + 13, 50, 34), border_radius=6)
        pygame.draw.rect(screen, (220, 185, 120), (x + 5, y + 13, 50, 34), 2, border_radius=6)
        screen.blit(small.render(f"{index + 1} {table_labels.get(table['state'], '?')}",
                                 True, (255, 245, 220)), (x + 7, y + 20))
    si = restaurant["si"]
    task = si.get("task") or {}
    target = TABLE_POSITIONS[int(task["table"])] if "table" in task else KITCHEN_POSITION
    if si["state"] == "MOVING":
        progress = 1 - max(0.0, float(si["timer"])) / max(0.1, float(cfg["si_move_seconds"]))
        sx = KITCHEN_POSITION[0] + (target[0] - KITCHEN_POSITION[0]) * progress
        sy = KITCHEN_POSITION[1] + (target[1] - KITCHEN_POSITION[1]) * progress
    elif si["state"] in ("WORKING", "COOLDOWN") and si.get("location", "").startswith("table "):
        sx, sy = TABLE_POSITIONS[int(si["location"].split()[-1]) - 1]
    else:
        sx, sy = KITCHEN_POSITION
    px, py = world_to_screen(game, sx, sy)
    portrait = _load_img("祀_nobg.png", (42, 42))
    if portrait:
        screen.blit(portrait, (px + 9, py + 1))
    else:
        pygame.draw.circle(screen, (115, 220, 250), (px + 30, py + 25), 12)
    hint = pygame.Rect(max(12, screen.get_width() - 360), screen.get_height() - 132, 348, 30)
    pygame.draw.rect(screen, (7, 24, 34), hint, border_radius=4)
    screen.blit(small.render("靠近爐台按 E：設定菜色／排程", True, (245, 240, 200)),
                (hint.x + 8, hint.y + 6))


def draw_kitchen_panel(screen, state):
    panel = _management_panel(screen, 405, 240)
    index = state["kitchen_index"]
    cook = state["data"]["restaurant"]["cooks"][index]
    cfg = state["cfg"]
    font = pygame.font.SysFont("microsoftjhenghei", 18)
    status = {"IDLE": "待命", "COOKING": "烹調中", "BLOCKED": "食材不足"}.get(cook["state"], cook["state"])
    screen.blit(font.render(f"爐台 {index + 1}　{status}　進度 {cook['progress']:.1f} 秒",
                            True, (250, 230, 180)), (panel.x + 20, panel.y + 20))
    for row, label in enumerate(kitchen_rows({"farmer_mod": state})):
        y = panel.y + 64 + row * 42
        if row == state.get("kitchen_selected", 0):
            pygame.draw.rect(screen, (49, 83, 91), (panel.x + 15, y - 3, panel.w - 30, 34), border_radius=4)
        screen.blit(font.render(label, True, (245, 240, 215)), (panel.x + 23, y + 2))
    queued = ([cook["active"]] if cook["active"] else []) + cook["queue"]
    summary = "　→　".join(cfg["recipes"][recipe]["name"] for recipe in queued) or "無排程"
    screen.blit(font.render(summary, True, (195, 220, 230)), (panel.x + 20, panel.bottom - 32))


def draw_result_panel(screen, state):
    panel = _management_panel(screen, 420, 220)
    result = state["data"]["restaurant"].get("result") or {}
    font = pygame.font.SysFont("microsoftjhenghei", 22)
    lines = ["緣緣莊營業結算", f"完成訂單：{result.get('orders', 0)}",
             f"本次收入：{result.get('revenue', 0)} 祀幣",
             f"目前餘額：{result.get('balance', state['data']['si_currency'])} 祀幣"]
    for index, line in enumerate(lines):
        screen.blit(font.render(line, True, (245, 235, 205)), (panel.x + 26, panel.y + 18 + 38 * index))
    hint = pygame.font.SysFont("microsoftjhenghei", 15)
    screen.blit(hint.render("Enter／ESC 關閉", True, (175, 205, 220)),
                (panel.x + 26, panel.bottom - 26))
