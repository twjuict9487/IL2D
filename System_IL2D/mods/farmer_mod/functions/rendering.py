import time

import pygame

from core.functions.rendering.draw import TILE_SIZE, VIEWPORT
from core.functions.support.asset_resolver import resolve_image_candidates

from .logic import is_farm_map, plot_key, shop_rows
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
    plots = cfg.get("plots", [])
    planted = data.get("planted", {})
    now = time.time()
    grow_seconds = int(cfg.get("grow_seconds", 10))
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

        fill = (120, 85, 45, 125) if idx < owned else (35, 45, 55, 90)
        entry = planted.get(plot_key(tx, ty))
        icon = None
        if entry:
            planted_at = float(entry.get("planted_at", now))
            fill = (
                (170, 150, 65, 165)
                if now - planted_at >= grow_seconds
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
def draw_shop(screen, game, state):
    font = pygame.font.SysFont("consolas", 22)
    panel = pygame.Rect(
        screen.get_width() // 6,
        screen.get_height() // 6,
        screen.get_width() * 2 // 3,
        screen.get_height() * 2 // 3,
    )
    pygame.draw.rect(screen, (7, 24, 34), panel)
    pygame.draw.rect(screen, (140, 210, 220), panel, 2)
    screen.blit(
        font.render("Shu Farm Service", True, (230, 240, 250)),
        (panel.x + 16, panel.y + 12),
    )

    rows = shop_rows({"farmer_mod": state})
    y = panel.y + 56
    for idx, (_key, label) in enumerate(rows):
        c = (
            (255, 230, 140)
            if idx == (game.shop_selected % len(rows))
            else (210, 220, 235)
        )
        screen.blit(font.render(label, True, c), (panel.x + 16, y))
        y += font.get_height() + 10

    tiny = pygame.font.SysFont("consolas", 18)
    info = state["data"]
    footer = f"Land:{info.get('owned_land',0)}  Seeds[R:{info['seeds'].get('rice',0)} W:{info['seeds'].get('wheat',0)}]  Crops[R:{info['crops'].get('rice',0)} W:{info['crops'].get('wheat',0)}]"
    screen.blit(
        tiny.render(footer, True, (170, 200, 220)), (panel.x + 16, panel.bottom - 32)
    )


# 畫農場左側資訊面板（縮小、可讀）。
def draw_farm_panel(screen, state):
    data = state["data"]
    cfg = state["cfg"]
    panel_w = 155
    panel_h = max(220, screen.get_height() // 2)
    panel = pygame.Rect(12, (screen.get_height() - panel_h) // 2, panel_w, panel_h)
    overlay = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
    overlay.fill((8, 18, 30, 210))
    screen.blit(overlay, (panel.x, panel.y))
    pygame.draw.rect(screen, (120, 190, 220), panel, 2)

    title_font = pygame.font.SysFont("consolas", 14, bold=True)
    font = pygame.font.SysFont("consolas", 11)
    tiny = pygame.font.SysFont("consolas", 10)
    x, y = panel.x + 8, panel.y + 10
    shu_img = _load_img("头像_黍.png", (26, 26))
    if shu_img is not None:
        screen.blit(shu_img, (x, y - 2))
        title_x = x + 30
    else:
        title_x = x
    screen.blit(title_font.render("FARM", True, (235, 245, 255)), (title_x, y))
    y += 18
    screen.blit(tiny.render("I/J/K/L: Seed", True, (180, 210, 230)), (x, y))
    y += 14
    screen.blit(tiny.render("F: Plant/Harvest", True, (180, 210, 230)), (x, y))
    y += 14
    screen.blit(tiny.render("ESC: Exit", True, (180, 210, 230)), (x, y))
    y += 18

    seeds = ["rice", "wheat"]
    selected = int(data.get("panel_index", 0)) % 2
    for idx, name in enumerate(seeds):
        color = (255, 225, 120) if idx == selected else (210, 220, 235)
        txt = f"{name.upper()} seed: {int(data['seeds'].get(name, 0))}"
        surf = font.render(txt, True, color)
        row_rect = pygame.Rect(x - 3, y - 2, panel.width - 14, surf.get_height() + 4)
        if idx == selected:
            pygame.draw.rect(screen, (255, 255, 255), row_rect, 2)
        icon_name = "Amber_Rice_nobg.png" if name == "rice" else "wheat_nobg.png"
        icon = _load_img(icon_name, (12, 12))
        text_x = x
        if icon is not None:
            screen.blit(icon, (x, y))
            text_x = x + 15
        screen.blit(surf, (text_x, y))
        y += 16

    y += 6
    screen.blit(
        font.render(
            f"Land: {int(data.get('owned_land', 0))}/{len(cfg.get('plots', []))}",
            True,
            (200, 230, 230),
        ),
        (x, y),
    )
    y += 16
    screen.blit(
        font.render(
            f"Rice: {int(data['crops'].get('rice', 0))}", True, (190, 230, 210)
        ),
        (x, y),
    )
    y += 16
    screen.blit(
        font.render(
            f"Wheat: {int(data['crops'].get('wheat', 0))}", True, (210, 220, 190)
        ),
        (x, y),
    )


# 農場模組渲染入口（商店與農地 UI）。
def render(ctx, screen):
    game = ctx["game"]
    state = farm_runtime(ctx)
    if game.ui_mode == "farm_shop":
        draw_shop(screen, game, state)
    if is_farm_map(game):
        draw_farm_land_overlay(screen, game, state)
        draw_farm_panel(screen, state)
