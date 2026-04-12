import os
import math
import pygame
from core.utils import clamp
from core.map import mobs_data

TILE_SIZE = 48
VIEWPORT = 10
FPS = 60

_IMAGE_CACHE = {}


def _load_image(filename, size=None):
    if not filename:
        return None
    if filename in _IMAGE_CACHE:
        return _IMAGE_CACHE[filename]
    base_dir = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base_dir, filename)
    if not os.path.isfile(path):
        _IMAGE_CACHE[filename] = None
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        _IMAGE_CACHE[filename] = img
        return img
    except Exception:
        _IMAGE_CACHE[filename] = None
        return None


def _flicker_color():
    t = pygame.time.get_ticks() / 500.0
    s = (math.sin(t) + 1.0) / 2.0
    intensity = 140 + int(115 * s)
    return (intensity, intensity, intensity)


def draw_main_menu(screen, selected):
    # tech grey background
    pygame.draw.rect(screen, (70, 78, 86), screen.get_rect())
    font = pygame.font.SysFont('consolas', 48, bold=True)
    font2 = pygame.font.SysFont('consolas', 32)
    font3 = pygame.font.SysFont('consolas', 24)
    title = font.render('Project: IL2D', True, (255, 255, 255))
    title_y = screen.get_height() // 2 - 140
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, title_y))
    opts = ['new game', 'continue', 'leave', 'credits']
    total_height = len(opts) * 44
    start_y = screen.get_height() // 2 - total_height // 2 + 40
    for i, opt in enumerate(opts):
        color = (255, 255, 0) if i == selected else (200, 200, 200)
        surf = font2.render(opt, True, color)
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * 44
        screen.blit(surf, (x, y))
        if i == selected:
            rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)
    credits = font3.render('2026 by twjui', True, (120, 120, 120))
    screen.blit(credits, (screen.get_width() // 2 - credits.get_width() // 2, screen.get_height() - 36))


def draw_esc_menu(screen, selected, game=None):
    font = pygame.font.SysFont('consolas', 16)
    font2 = pygame.font.SysFont('consolas', 14)
    opts = ['item', 'magic', 'equipments', 'objective', 'status', 'save', 'leave']
    # ocean blue base
    screen.fill((18, 60, 92))
    menu_w = screen.get_width() // 4
    menu_h = screen.get_height()
    x = 0
    y = 0
    # left panel
    left_rect = pygame.Rect(x, y, menu_w, menu_h)
    pygame.draw.rect(screen, (12, 42, 70), left_rect)
    pygame.draw.rect(screen, (190, 230, 255), left_rect, 2)
    item_h = font.get_height() + 6
    for i, opt in enumerate(opts):
        is_selected = i == selected
        color = (255, 255, 0) if is_selected else (220, 220, 220)
        surf = font.render(opt, True, color)
        item_rect = pygame.Rect(x + 12, y + 20 + i * item_h, menu_w - 24, item_h)
        if is_selected:
            pygame.draw.rect(screen, (255, 255, 255), item_rect, 2, border_radius=4)
        else:
            pygame.draw.rect(screen, (90, 140, 170), item_rect, 1, border_radius=4)
        screen.blit(surf, (item_rect.x + (item_rect.width - surf.get_width()) // 2, item_rect.y + 2))

    right_x = menu_w
    right_w = screen.get_width() - menu_w
    right_h = screen.get_height()
    panel = pygame.Rect(right_x, y, right_w, right_h)
    pygame.draw.rect(screen, (16, 70, 110), panel)
    pygame.draw.rect(screen, (190, 230, 255), panel, 2)

    if game is None:
        return

    # header bar (top)
    header_h = 72
    header_rect = pygame.Rect(panel.x + 8, panel.y + 8, panel.width - 16, header_h)
    pygame.draw.rect(screen, (10, 50, 90), header_rect)
    pygame.draw.rect(screen, (200, 240, 255), header_rect, 2)
    title = opts[selected]
    title_surf = font.render(title, True, (255, 255, 255))
    screen.blit(title_surf, (header_rect.x + 12, header_rect.y + 10))

    # main content panel
    content_rect = pygame.Rect(panel.x + 8, header_rect.bottom + 8, panel.width - 16, panel.height - header_h - 24 - 64)
    pygame.draw.rect(screen, (12, 58, 96), content_rect)
    pygame.draw.rect(screen, (200, 240, 255), content_rect, 2)
    # footer info panel (bottom-right)
    info_rect = pygame.Rect(panel.right - 220, panel.bottom - 60, 210, 52)
    pygame.draw.rect(screen, (10, 50, 90), info_rect)
    pygame.draw.rect(screen, (200, 240, 255), info_rect, 2)
    info_font = pygame.font.SysFont('consolas', 12)
    info_text = info_font.render("now", True, (200, 220, 220))
    screen.blit(info_text, (info_rect.x + 8, info_rect.y + 6))

    if game.ui_mode in ("save", "equip", "equip_category", "item", "magic", "objective", "status", "leave_confirm"):
        draw_menu_detail(screen, content_rect, game)
    else:
        draw_menu_preview(screen, content_rect, game, selected)


def draw_menu_preview(screen, panel, game, selected):
    font = pygame.font.SysFont('consolas', 14)
    opts = ['item', 'magic', 'equipments', 'objective', 'status', 'save', 'leave']
    label = opts[selected]
    lines = []
    if label == "item":
        lines.append("Inventory preview")
        for name, count in list(game.inventory.items())[:4]:
            lines.append(f"{name} x{count}")
    elif label == "magic":
        lines.append("Spells")
        for sp in game.spells:
            lines.append(f"{sp['name']} ({sp['mp_cost']} MP)")
    elif label == "equipments":
        lines.append("Current")
        lines.append(f"Weapon: {game.equipment.get('weapon') or 'none'}")
        lines.append(f"Armor: {game.equipment.get('armor') or 'none'}")
    elif label == "objective":
        lines.append("Objectives")
        lines.extend(game.objectives[:4])
    elif label == "status":
        lines.append("Stats")
        lines.append(f"HP {game.player.hp}/{game.player.max_hp}")
        lines.append(f"MP {game.player.mp}/{game.player.max_mp}")
        lines.append(f"ATK {game.player.attack}")
        lines.append(f"DEF {game.player.defence}%")
    elif label == "save":
        lines.append("Press Enter to save")
        if game.last_saved:
            lines.append(f"Last slot: {game.last_save_slot}")
    elif label == "leave":
        lines.append("Press Enter to leave")
    y = panel.y + 48
    for line in lines:
        surf = font.render(line, True, (230, 230, 230))
        screen.blit(surf, (panel.x + 20, y))
        y += font.get_height() + 6


def draw_menu_detail(screen, panel, game):
    font = pygame.font.SysFont('consolas', 14)
    y = panel.y + 48
    if game.ui_mode == "item":
        items = game.get_item_list()
        if not items:
            surf = font.render("no items", True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        selected = game.item_selected % len(items)
        for i, name in enumerate(items):
            count = game.inventory.get(name, 0)
            line = f"{name} x{count}"
            surf = font.render(line, True, (230, 230, 230))
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "magic":
        if not game.spells:
            surf = font.render("no spells", True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        selected = game.magic_selected % len(game.spells)
        for i, sp in enumerate(game.spells):
            line = f"{sp['name']} ({sp['mp_cost']} MP)"
            surf = font.render(line, True, (230, 230, 230))
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "equip":
        equipables = game.get_equipable_items()
        filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == game.equip_category]
        if not filtered:
            surf = font.render("no equipment in inventory", True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        selected = game.equip_selected % len(filtered)
        for i, name in enumerate(filtered):
            color = (255, 255, 0) if i == selected else (230, 230, 230)
            surf = font.render(name, True, color)
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "equip_category":
        categories = ["weapon", "armor"]
        for i, name in enumerate(categories):
            color = (255, 255, 0) if i == game.equip_category_selected else (230, 230, 230)
            surf = font.render(name, True, color)
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == game.equip_category_selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "objective":
        for line in game.objectives:
            surf = font.render(line, True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            y += font.get_height() + 6
    elif game.ui_mode == "status":
        lines = [
            f"HP {game.player.hp}/{game.player.max_hp}",
            f"MP {game.player.mp}/{game.player.max_mp}",
            f"Attack {game.player.attack}",
            f"Defence {game.player.defence}%"
        ]
        for line in lines:
            surf = font.render(line, True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            y += font.get_height() + 6
    elif game.ui_mode == "save":
        slots = 3
        for i in range(slots):
            color = (255, 255, 0) if i == game.save_selected else (230, 230, 230)
            line = f"slot {i + 1}"
            surf = font.render(line, True, color)
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            if i == game.save_selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font.get_height() + 10
        hint = font.render("Enter to save, ESC to back", True, (200, 200, 200))
        screen.blit(hint, (panel.x + 20, panel.bottom - 30))
    elif game.ui_mode == "leave_confirm":
        prompt, options = get_leave_prompt(game)
        surf = font.render(prompt, True, (230, 230, 230))
        screen.blit(surf, (panel.x + 20, y))
        y += font.get_height() + 10
        for i, opt in enumerate(options):
            color = (255, 255, 0) if i == game.leave_selected else (230, 230, 230)
            opt_surf = font.render(opt, True, color)
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            if i == game.leave_selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(opt_surf, (panel.x + 24, y))
            y += font.get_height() + 6


def get_leave_prompt(game):
    if game.leave_step == 0:
        return "did you saved?", ["yes", "no"]
    if game.leave_step == 1:
        return "are you going to leave?", ["yes", "no"]
    return "you better go back and save your current file", ["ok"]


def draw_player_ui(game, screen):
    font = pygame.font.SysFont('consolas', 18)
    player = getattr(game, 'player', None)
    if player is not None:
        hp = getattr(player, 'hp', 0)
        max_hp = getattr(player, 'max_hp', hp)
        mp = getattr(player, 'mp', 0)
        max_mp = getattr(player, 'max_mp', mp)
        hp_text = f"health point: {hp}/{max_hp}"
        mp_text = f"magic point: {mp}/{max_mp}"
        bar_h = 48
        bar_rect = pygame.Rect(0, screen.get_height() - bar_h, screen.get_width(), bar_h)
        pygame.draw.rect(screen, (60, 60, 60), bar_rect)
        surf_hp = font.render(hp_text, True, (255, 80, 80))
        surf_mp = font.render(mp_text, True, (80, 80, 255))
        screen.blit(surf_hp, (16, screen.get_height() - bar_h + 8))
        screen.blit(surf_mp, (16, screen.get_height() - bar_h + 8 + surf_hp.get_height() + 4))


def draw_messages(game, screen):
    if not game.message_queue:
        return
    font = pygame.font.SysFont('consolas', 14)
    messages = list(game.message_queue)[-3:]
    y = screen.get_height() - 60
    for msg in reversed(messages):
        surf = font.render(msg["text"], True, (255, 255, 255))
        x = screen.get_width() - surf.get_width() - 16
        screen.blit(surf, (x, y))
        y -= font.get_height() + 4


def draw_dialog(game, screen):
    if game.ui_mode != "dialog" or not game.dialog_data or not game.dialog_node:
        return
    panel_h = screen.get_height() // 3
    panel = pygame.Rect(0, screen.get_height() - panel_h - 12, screen.get_width(), panel_h)
    pygame.draw.rect(screen, (30, 30, 40), panel)
    pygame.draw.rect(screen, (200, 200, 200), panel, 2)
    font = pygame.font.SysFont('consolas', 16)
    font2 = pygame.font.SysFont('consolas', 14)
    npc_id = game.active_npc or "npc"
    npc_name = npc_id
    node = game.dialog_data.get(game.dialog_node, {})
    text = node.get("text", "")
    responses = node.get("responses", [])

    img_size = panel_h - 24
    img = _load_image(mobs_data.get(npc_id, {}).get("image"), (img_size, img_size))
    img_x = panel.x + 12
    img_y = panel.y + 12
    if img:
        screen.blit(img, (img_x, img_y))
    else:
        pygame.draw.rect(screen, (80, 80, 90), (img_x, img_y, img_size, img_size))

    screen.blit(font.render(npc_name, True, (255, 255, 0)), (img_x + img_size + 12, panel.y + 8))

    text_y = panel.y + 32
    max_width = panel.width - img_size - 36
    lines = _wrap_text(font2, text, max_width)
    for line in lines:
        surf = font2.render(line, True, (230, 230, 230))
        screen.blit(surf, (img_x + img_size + 12, text_y))
        text_y += font2.get_height() + 4

    resp_y = panel.bottom - 20 - len(responses) * (font2.get_height() + 6)
    if resp_y < text_y + 8:
        resp_y = text_y + 8
    for i, resp in enumerate(responses):
        color = (255, 255, 0) if i == game.dialog_selected else (200, 200, 200)
        surf = font2.render(resp.get("text", ""), True, color)
        rect = pygame.Rect(img_x + img_size + 8, resp_y - 2, panel.width - img_size - 32, font2.get_height() + 4)
        if i == game.dialog_selected:
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
        screen.blit(surf, (img_x + img_size + 12, resp_y))
        resp_y += font2.get_height() + 6


def draw_shop(game, screen):
    if game.ui_mode != "shop":
        return
    panel = pygame.Rect(screen.get_width() // 10, screen.get_height() // 10, screen.get_width() * 8 // 10, screen.get_height() * 8 // 10)
    pygame.draw.rect(screen, (30, 30, 40), panel)
    pygame.draw.rect(screen, (200, 200, 200), panel, 2)
    font = pygame.font.SysFont('consolas', 16)
    font2 = pygame.font.SysFont('consolas', 14)
    title = font.render("shop", True, (255, 255, 255))
    screen.blit(title, (panel.x + 12, panel.y + 12))
    money = font2.render(f"robux: {game.money}", True, (200, 200, 200))
    screen.blit(money, (panel.right - money.get_width() - 12, panel.y + 14))
    y = panel.y + 48
    for i, item in enumerate(game.shop_items):
        color = (255, 255, 0) if i == game.shop_selected else (230, 230, 230)
        line = f"{item['name']} - {item['price']} robux"
        surf = font2.render(line, True, color)
        rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font2.get_height() + 4)
        if i == game.shop_selected:
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
        screen.blit(surf, (panel.x + 24, y))
        y += font2.get_height() + 6
    hint = font2.render("Enter to buy, ESC to close", True, (200, 200, 200))
    screen.blit(hint, (panel.x + 20, panel.bottom - 24))


def _wrap_text(font, text, max_width):
    words = text.split(' ')
    lines = []
    line = ''
    for word in words:
        test = (line + ' ' + word).strip()
        if font.size(test)[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw(game, screen):
    screen.fill((0, 0, 0))
    cx, cy = game.camera_x, game.camera_y
    map_view_h = VIEWPORT
    map_view_w = VIEWPORT
    tile_h = TILE_SIZE
    tile_w = TILE_SIZE
    left = clamp(cx - map_view_w // 2, 0, game.map.w - map_view_w)
    top = clamp(cy - map_view_h // 2, 0, game.map.h - map_view_h)
    for y in range(map_view_h):
        for x in range(map_view_w):
            mx, my = left + x, top + y
            if 0 <= mx < game.map.w and 0 <= my < game.map.h:
                bt = game.map.get_block(mx, my)
                color = (100, 200, 100) if bt == 'grass' else (80, 80, 80) if bt == 'wall' else (200, 200, 0)
                pygame.draw.rect(screen, color, (x * tile_w, y * tile_h, tile_w, tile_h))
    for ent in game.entities:
        if left <= ent.x < left + map_view_w and top <= ent.y < top + map_view_h:
            ex, ey = ent.x - left, ent.y - top
            draw_x = ex * tile_w + 4
            draw_y = ey * tile_h + 4
            size = tile_w - 8, tile_h - 8
            img = _load_image(mobs_data.get(ent.eid, {}).get("image"), size)
            if img:
                screen.blit(img, (draw_x, draw_y))
            else:
                if ent.eid == 'player':
                    color = (0, 0, 255)
                elif mobs_data.get(ent.eid, {}).get('ai_type') == 'friendly':
                    color = (255, 200, 0)
                else:
                    color = (255, 0, 0)
                pygame.draw.rect(screen, color, (draw_x + 4, draw_y + 4, tile_w - 16, tile_h - 16))

    if game.blackout:
        s = pygame.Surface(screen.get_size())
        s.set_alpha(game.black_alpha)
        s.fill((0, 0, 0))
        screen.blit(s, (0, 0))

    draw_messages(game, screen)
    draw_dialog(game, screen)
    draw_shop(game, screen)
