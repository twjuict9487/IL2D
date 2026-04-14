import os
import math
import time
import pygame
from core.utils import clamp
from core.map import mobs_data, npc_data, blocktypes
from core.i18n import tr

TILE_SIZE = 48
VIEWPORT = 10
FPS = 60

_IMAGE_CACHE = {}


def _load_image(filename, size=None):
    if not filename:
        return None
    cache_key = (filename, size)
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]
    base_dir = os.path.dirname(os.path.dirname(__file__))
    pictures_dir = os.path.join(base_dir, "Pictures")
    path = os.path.join(pictures_dir, filename)
    if not os.path.isfile(path):
        _IMAGE_CACHE[cache_key] = None
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        _IMAGE_CACHE[cache_key] = img
        return img
    except Exception:
        _IMAGE_CACHE[cache_key] = None
        return None


def _flicker_color():
    t = pygame.time.get_ticks() / 500.0
    s = (math.sin(t) + 1.0) / 2.0
    intensity = 140 + int(115 * s)
    return (intensity, intensity, intensity)


def _get_font(size, bold=False):
    for name in ("Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC", "Noto Sans CJK SC"):
        font = pygame.font.SysFont(name, size, bold=bold)
        if font is not None:
            return font
    return pygame.font.SysFont('consolas', size, bold=bold)


def _draw_text_outline(screen, font, text, color, outline_color, pos):
    x, y = pos
    base = font.render(text, True, color)
    outline = font.render(text, True, outline_color)
    for ox, oy in [(1, 0), (0, 1)]:
        screen.blit(outline, (x + ox, y + oy))
    screen.blit(base, (x, y))


def _tr_item_name(game, name):
    key = f"item.{name}"
    label = tr(game.lang, key)
    return name if label == key else label


def _tr_spell_name(game, name):
    key = f"spell.{name}"
    label = tr(game.lang, key)
    return name if label == key else label


def draw_main_menu(screen, selected, lang="en"):
    # tech grey background
    pygame.draw.rect(screen, (70, 78, 86), screen.get_rect())
    font = _get_font(48, bold=True)
    font2 = _get_font(32)
    font3 = _get_font(24)
    title = font.render('Project: IL2D', True, (255, 255, 255))
    title_y = screen.get_height() // 2 - 140
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, title_y))
    opts = ['new_game', 'continue', 'setting', 'leave', 'credits']
    total_height = len(opts) * 44
    start_y = screen.get_height() // 2 - total_height // 2 + 40
    for i, opt in enumerate(opts):
        color = (255, 255, 0) if i == selected else (200, 200, 200)
        surf = font2.render(tr(lang, f"menu.{opt}"), True, color)
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * 44
        screen.blit(surf, (x, y))
        if i == selected:
            rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)
    credits = font3.render('2026 by twjui', True, (120, 120, 120))
    screen.blit(credits, (screen.get_width() // 2 - credits.get_width() // 2, screen.get_height() - 36))


def draw_continue_menu(screen, slots, selected, lang="en"):
    pygame.draw.rect(screen, (70, 78, 86), screen.get_rect())
    font = _get_font(36, bold=True)
    font2 = _get_font(22)
    title = font.render(tr(lang, "menu.continue"), True, (255, 255, 255))
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, 60))
    if not slots:
        hint = font2.render(tr(lang, "continue.empty"), True, (200, 200, 200))
        screen.blit(hint, (screen.get_width() // 2 - hint.get_width() // 2, 140))
        return
    start_y = 140
    for i, slot in enumerate(slots):
        exists = slot.get("exists", False)
        status = tr(lang, "continue.exists") if exists else tr(lang, "continue.empty")
        label = f"{tr(lang, 'continue.slot', slot=slot.get('slot', i + 1))} - {status}"
        color = (255, 255, 0) if i == selected else (220, 220, 220)
        surf = font2.render(label, True, color)
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * (font2.get_height() + 12)
        screen.blit(surf, (x, y))
        if i == selected:
            rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)
    hint = font2.render(tr(lang, "continue.hint"), True, (180, 180, 180))
    screen.blit(hint, (screen.get_width() // 2 - hint.get_width() // 2, screen.get_height() - 40))


def draw_dev_menu(screen, ctx):
    panel_w = screen.get_width() * 2 // 3
    panel_h = screen.get_height() * 2 // 3
    panel = pygame.Rect(screen.get_width() // 2 - panel_w // 2, screen.get_height() // 2 - panel_h // 2, panel_w, panel_h)
    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    bg.fill((10, 12, 16, 220))
    screen.blit(bg, panel.topleft)
    pygame.draw.rect(screen, (220, 220, 220), panel, 2)
    font = _get_font(22, bold=True)
    font2 = _get_font(18)
    title = font.render("DEV MENU", True, (255, 255, 255))
    screen.blit(title, (panel.x + 16, panel.y + 12))
    opts = ["max_hp", "max_mp", "add_money", "exit"]
    labels = {
        "max_hp": "Set Max HP",
        "max_mp": "Set Max MP",
        "add_money": "Add Money",
        "exit": "Exit"
    }
    y = panel.y + 60
    for i, key in enumerate(opts):
        color = (255, 255, 0) if i == ctx["dev_menu_selected"] else (200, 200, 200)
        surf = font2.render(labels[key], True, color)
        rect = pygame.Rect(panel.x + 16, y - 4, panel.width - 32, font2.get_height() + 8)
        if i == ctx["dev_menu_selected"]:
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)
        screen.blit(surf, (panel.x + 24, y))
        y += font2.get_height() + 12

    if ctx["dev_menu_target"]:
        prompt = f"Input {ctx['dev_menu_target']}: {ctx['dev_menu_input']}"
        surf = font2.render(prompt, True, (230, 230, 230))
        screen.blit(surf, (panel.x + 16, panel.bottom - 40))


def draw_settings_menu(screen, selected, sub_mode, lang_selected, lang="en"):
    pygame.draw.rect(screen, (70, 78, 86), screen.get_rect())
    font = _get_font(32, bold=True)
    font2 = _get_font(22)
    title = font.render(tr(lang, "menu.setting"), True, (255, 255, 255))
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, 40))
    opts = ["setting.language", "setting.back"]
    start_y = 120
    for i, key in enumerate(opts):
        color = (255, 255, 0) if i == selected else (200, 200, 200)
        label = tr(lang, key)
        surf = font2.render(label, True, color)
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * 40
        screen.blit(surf, (x, y))
        if i == selected:
            rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)

    if sub_mode == "language":
        box_w = 320
        box_h = 140
        box = pygame.Rect(screen.get_width() // 2 - box_w // 2, screen.get_height() // 2 - box_h // 2, box_w, box_h)
        pygame.draw.rect(screen, (20, 24, 30), box)
        pygame.draw.rect(screen, (220, 220, 220), box, 2)
        langs = [("zh", tr(lang, "lang.zh")), ("en", tr(lang, "lang.en"))]
        for i, (_, label) in enumerate(langs):
            color = (255, 255, 0) if i == lang_selected else (220, 220, 220)
            surf = font2.render(label, True, color)
            x = box.x + 24
            y = box.y + 24 + i * 36
            screen.blit(surf, (x, y))
            if i == lang_selected:
                rect = pygame.Rect(x - 8, y - 4, surf.get_width() + 16, surf.get_height() + 8)
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)


def draw_esc_menu(screen, selected, game=None):
    font = _get_font(16)
    font2 = _get_font(14)
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
        surf = font.render(tr(game.lang, f"esc.{opt}"), True, color)
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
    title_surf = font.render(tr(game.lang, f"esc.{title}"), True, (255, 255, 255))
    screen.blit(title_surf, (header_rect.x + 12, header_rect.y + 10))

    # main content panel
    content_rect = pygame.Rect(panel.x + 8, header_rect.bottom + 8, panel.width - 16, panel.height - header_h - 24 - 64)
    pygame.draw.rect(screen, (12, 58, 96), content_rect)
    pygame.draw.rect(screen, (200, 240, 255), content_rect, 2)
    # footer info panel (bottom-right)
    info_rect = pygame.Rect(panel.right - 220, panel.bottom - 60, 210, 52)
    pygame.draw.rect(screen, (10, 50, 90), info_rect)
    pygame.draw.rect(screen, (200, 240, 255), info_rect, 2)
    info_font = _get_font(12)
    info_text = info_font.render(tr(game.lang, "label.now"), True, (200, 220, 220))
    screen.blit(info_text, (info_rect.x + 8, info_rect.y + 6))

    # header right: player info
    if game is not None:
        name = getattr(game, "player_name", "player")
        hp = f"{tr(game.lang, 'label.hp')} {game.player.hp}/{game.player.max_hp}"
        mp = f"{tr(game.lang, 'label.mp')} {game.player.mp}/{game.player.max_mp}"
        name_surf = font.render(name, True, (255, 255, 255))
        hp_surf = font2.render(hp, True, (255, 200, 200))
        mp_surf = font2.render(mp, True, (200, 200, 255))
        right_x = header_rect.right - 12
        _draw_text_outline(screen, font, name, (255, 255, 255), (0, 0, 0), (right_x - name_surf.get_width(), header_rect.y + 10))
        _draw_text_outline(screen, font2, hp, (255, 200, 200), (255, 255, 255), (right_x - hp_surf.get_width(), header_rect.y + 32))
        _draw_text_outline(screen, font2, mp, (200, 200, 255), (255, 255, 255), (right_x - mp_surf.get_width(), header_rect.y + 48))

    # left lower: currency box
    if game is not None:
        money_rect = pygame.Rect(left_rect.x + 8, left_rect.bottom - 72, left_rect.width - 16, 56)
        pygame.draw.rect(screen, (10, 50, 90), money_rect)
        pygame.draw.rect(screen, (200, 240, 255), money_rect, 2)
        money_text = f"{tr(game.lang, 'label.robux')}: {game.money}"
        _draw_text_outline(screen, font2, money_text, (230, 230, 230), (255, 255, 255), (money_rect.x + 8, money_rect.y + 18))

    if game.ui_mode in ("save", "equip", "equip_category", "item", "magic", "objective", "status", "leave_confirm"):
        draw_menu_detail(screen, content_rect, game)
    else:
        draw_menu_preview(screen, content_rect, game, selected)


def draw_menu_preview(screen, panel, game, selected):
    font = _get_font(14)
    opts = ['item', 'magic', 'equipments', 'objective', 'status', 'save', 'leave']
    label = opts[selected]
    lines = []
    if label == "item":
        lines.append(tr(game.lang, "preview.inventory"))
        for name, count in list(game.inventory.items())[:4]:
            lines.append(f"{_tr_item_name(game, name)} x{count}")
    elif label == "magic":
        lines.append(tr(game.lang, "preview.spells"))
        for sp in game.spells:
            sname = _tr_spell_name(game, sp['name'])
            lines.append(f"{sname} ({sp['mp_cost']} MP)")
    elif label == "equipments":
        lines.append(tr(game.lang, "preview.current"))
        lines.append(f"{tr(game.lang, 'preview.weapon')}: {game.equipment.get('weapon') or 'none'}")
        lines.append(f"{tr(game.lang, 'preview.armor')}: {game.equipment.get('armor') or 'none'}")
    elif label == "objective":
        lines.append(tr(game.lang, "preview.objectives"))
        lines.extend(game.objectives[:4])
    elif label == "status":
        lines.append(tr(game.lang, "preview.stats"))
        lines.append(f"{tr(game.lang, 'label.hp')} {game.player.hp}/{game.player.max_hp}")
        lines.append(f"{tr(game.lang, 'label.mp')} {game.player.mp}/{game.player.max_mp}")
        lines.append(f"{tr(game.lang, 'label.attack')} {game.player.attack}")
        lines.append(f"{tr(game.lang, 'label.defence')} {game.player.defence}%")
    elif label == "save":
        lines.append(tr(game.lang, "preview.save"))
        if game.last_saved:
            lines.append(f"Last slot: {game.last_save_slot}")
    elif label == "leave":
        lines.append(tr(game.lang, "preview.leave"))
    y = panel.y + 48
    for line in lines:
        _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
        y += font.get_height() + 6


def draw_menu_detail(screen, panel, game):
    font = _get_font(14)
    y = panel.y + 48
    if game.ui_mode == "item":
        items = game.get_item_list()
        if not items:
            surf = font.render(tr(game.lang, "msg.no_items"), True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        selected = game.item_selected % len(items)
        for i, name in enumerate(items):
            count = game.inventory.get(name, 0)
            line = f"{_tr_item_name(game, name)} x{count}"
            surf = font.render(line, True, (230, 230, 230))
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "magic":
        if not game.spells:
            surf = font.render(tr(game.lang, "msg.no_spells"), True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        selected = game.magic_selected % len(game.spells)
        for i, sp in enumerate(game.spells):
            sname = _tr_spell_name(game, sp['name'])
            line = f"{sname} ({sp['mp_cost']} MP)"
            surf = font.render(line, True, (230, 230, 230))
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "equip":
        categories = game.get_equip_categories()
        col_w = (panel.width - 40) // 2
        # top buttons
        top_y = panel.y + 8
        btn_w = 140
        btn_h = 24
        btn1 = pygame.Rect(panel.x + 16, top_y, btn_w, btn_h)
        btn2 = pygame.Rect(panel.x + 16 + btn_w + 12, top_y, btn_w, btn_h)
        pygame.draw.rect(screen, (40, 40, 50), btn1)
        pygame.draw.rect(screen, (200, 200, 200), btn1, 1)
        pygame.draw.rect(screen, (40, 40, 50), btn2)
        pygame.draw.rect(screen, (200, 200, 200), btn2, 1)
        _draw_text_outline(screen, font, tr(game.lang, "equip.change"), (230, 230, 230), (255, 255, 255), (btn1.x + 8, btn1.y + 4))
        _draw_text_outline(screen, font, tr(game.lang, "equip.put_down_all"), (230, 230, 230), (255, 255, 255), (btn2.x + 8, btn2.y + 4))
        y = panel.y + 48
        # left categories with equipped
        for i, name in enumerate(categories):
            is_sel = i == game.equip_category_selected
            color = (255, 255, 0) if is_sel else (230, 230, 230)
            label = tr(game.lang, f"label.{name}") if name in ("weapon", "armor") else name
            left_rect = pygame.Rect(panel.x + 16, y - 2, col_w, font.get_height() + 4)
            right_rect = pygame.Rect(panel.x + 24 + col_w, y - 2, col_w, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), left_rect, 1, border_radius=4)
            pygame.draw.rect(screen, (255, 255, 255), right_rect, 1, border_radius=4)
            if is_sel:
                pygame.draw.rect(screen, _flicker_color(), left_rect, 2, border_radius=4)
            equipped = game.equipment.get(name) if name in game.equipment else None
            equip_label = _tr_item_name(game, equipped) if equipped else "none"
            _draw_text_outline(screen, font, label, color, (255, 255, 255), (left_rect.x + 8, y))
            _draw_text_outline(screen, font, equip_label, (230, 230, 230), (255, 255, 255), (right_rect.x + 8, y))
            y += font.get_height() + 6

        # right list: filtered items for selected category
        equipables = game.get_equipable_items()
        slot_key = "ring" if game.equip_category.startswith("ring") else game.equip_category
        filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
        if not filtered:
            surf = font.render(tr(game.lang, "msg.no_items_category"), True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        list_x = panel.x + 16
        list_y = panel.bottom - 88
        selected = game.equip_selected % len(filtered)
        for i, name in enumerate(filtered[:3]):
            color = (255, 255, 0) if i == selected else (230, 230, 230)
            label = _tr_item_name(game, name)
            rect = pygame.Rect(list_x, list_y + i * (font.get_height() + 6) - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            _draw_text_outline(screen, font, label, color, (255, 255, 255), (list_x + 8, list_y + i * (font.get_height() + 6)))
    elif game.ui_mode == "equip_category":
        categories = game.get_equip_categories()
        col_w = (panel.width - 40) // 2
        # top buttons
        top_y = panel.y + 8
        btn_w = 140
        btn_h = 24
        btn1 = pygame.Rect(panel.x + 16, top_y, btn_w, btn_h)
        btn2 = pygame.Rect(panel.x + 16 + btn_w + 12, top_y, btn_w, btn_h)
        pygame.draw.rect(screen, (40, 40, 50), btn1)
        pygame.draw.rect(screen, (200, 200, 200), btn1, 1)
        pygame.draw.rect(screen, (40, 40, 50), btn2)
        pygame.draw.rect(screen, (200, 200, 200), btn2, 1)
        _draw_text_outline(screen, font, tr(game.lang, "equip.change"), (230, 230, 230), (255, 255, 255), (btn1.x + 8, btn1.y + 4))
        _draw_text_outline(screen, font, tr(game.lang, "equip.put_down_all"), (230, 230, 230), (255, 255, 255), (btn2.x + 8, btn2.y + 4))
        y = panel.y + 48
        for i, name in enumerate(categories):
            is_sel = i == game.equip_category_selected
            color = (255, 255, 0) if is_sel else (230, 230, 230)
            label = tr(game.lang, f"label.{name}") if name in ("weapon", "armor") else name
            left_rect = pygame.Rect(panel.x + 16, y - 2, col_w, font.get_height() + 4)
            right_rect = pygame.Rect(panel.x + 24 + col_w, y - 2, col_w, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), left_rect, 1, border_radius=4)
            pygame.draw.rect(screen, (255, 255, 255), right_rect, 1, border_radius=4)
            if is_sel:
                pygame.draw.rect(screen, _flicker_color(), left_rect, 2, border_radius=4)
            equipped = game.equipment.get(name) if name in game.equipment else None
            equip_label = _tr_item_name(game, equipped) if equipped else "none"
            _draw_text_outline(screen, font, label, color, (255, 255, 255), (left_rect.x + 8, y))
            _draw_text_outline(screen, font, equip_label, (230, 230, 230), (255, 255, 255), (right_rect.x + 8, y))
            y += font.get_height() + 6
        # bottom list (3 rows)
        items = game.get_item_list()
        bottom_y = panel.bottom - 88
        for i in range(3):
            if i >= len(items):
                break
            name = items[i]
            count = game.inventory.get(name, 0)
            line = f"{_tr_item_name(game, name)} x{count}"
            _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 16, bottom_y + i * (font.get_height() + 6)))
    elif game.ui_mode == "objective":
        for line in game.objectives:
            _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
            y += font.get_height() + 6
    elif game.ui_mode == "status":
        lines = [
            f"{tr(game.lang, 'label.hp')} {game.player.hp}/{game.player.max_hp}",
            f"{tr(game.lang, 'label.mp')} {game.player.mp}/{game.player.max_mp}",
            f"{tr(game.lang, 'label.attack')} {game.player.attack}",
            f"{tr(game.lang, 'label.defence')} {game.player.defence}%"
        ]
        for line in lines:
            _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
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
        hint = font.render(tr(game.lang, "hint.save"), True, (200, 200, 200))
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
        return tr(game.lang, "leave.saved"), ["yes", "no"]
    if game.leave_step == 1:
        return tr(game.lang, "leave.confirm"), ["yes", "no"]
    return tr(game.lang, "leave.warn"), ["ok"]


def draw_player_ui(game, screen):
    font = _get_font(18)
    player = getattr(game, 'player', None)
    if player is not None:
        hp = getattr(player, 'hp', 0)
        max_hp = getattr(player, 'max_hp', hp)
        mp = getattr(player, 'mp', 0)
        max_mp = getattr(player, 'max_mp', mp)
        hp_text = f"{tr(game.lang, 'label.hp')}: {hp}/{max_hp}"
        mp_text = f"{tr(game.lang, 'label.mp')}: {mp}/{max_mp}"
        bar_h = 56
        bar_rect = pygame.Rect(0, screen.get_height() - bar_h, screen.get_width(), bar_h)
        pygame.draw.rect(screen, (20, 24, 28), bar_rect)
        pygame.draw.rect(screen, (180, 200, 220), bar_rect, 2)
        surf_hp = font.render(hp_text, True, (255, 200, 200))
        surf_mp = font.render(mp_text, True, (200, 220, 255))
        shadow_hp = font.render(hp_text, True, (0, 0, 0))
        shadow_mp = font.render(mp_text, True, (0, 0, 0))
        y0 = screen.get_height() - bar_h + 6
        _draw_text_outline(screen, font, hp_text, (255, 200, 200), (255, 255, 255), (16, y0))
        _draw_text_outline(screen, font, mp_text, (200, 220, 255), (255, 255, 255), (16, y0 + surf_hp.get_height() + 4))


def draw_messages(game, screen):
    if not game.message_queue:
        return
    font = _get_font(14)
    messages = list(game.message_queue)[-3:]
    bar_h = 48
    y = screen.get_height() - bar_h - 16
    now = time.time()
    for msg in reversed(messages):
        created = msg.get("created", now)
        age = now - created
        alpha = 255
        if age > game.message_show_time:
            fade_age = min(age - game.message_show_time, game.message_fade_time)
            alpha = int(255 * (1 - fade_age / game.message_fade_time))
        lines = msg.get("lines")
        if not lines:
            lines = [msg.get("text", "")]
        # background box for readability
        max_w = 0
        total_h = len(lines) * (font.get_height() + 4)
        for line in lines:
            max_w = max(max_w, font.size(line)[0])
        box_w = max_w + 16
        box_h = total_h + 10
        box_x = screen.get_width() - box_w - 12
        box_y = y - box_h + 6
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill((10, 12, 16, min(200, alpha)))
        screen.blit(bg, (box_x, box_y))
        for line in reversed(lines):
            surf = font.render(line, True, (255, 255, 255))
            surf.set_alpha(alpha)
            x = screen.get_width() - surf.get_width() - 16
            y -= font.get_height() + 4
            screen.blit(surf, (x, y))
        y -= 6


def draw_dialog(game, screen):
    if game.ui_mode != "dialog" or not game.dialog_data or not game.dialog_node:
        return
    panel_h = screen.get_height() // 4
    bar_h = 48
    panel_bottom = screen.get_height() - bar_h
    panel = pygame.Rect(0, panel_bottom - panel_h, screen.get_width(), panel_h)
    pygame.draw.rect(screen, (30, 30, 40), panel)
    pygame.draw.rect(screen, (200, 200, 200), panel, 2)
    font = _get_font(16)
    font2 = _get_font(14)
    npc_id = game.active_npc or "npc"
    npc_name = npc_id
    node = game.dialog_data.get(game.dialog_node, {})
    text = node.get("text_zh", node.get("text", "")) if game.lang == "zh" else node.get("text", "")
    responses = game.get_dialog_responses(node)

    img_size = int(panel_h * 0.7)
    ent_def = mobs_data.get(npc_id, None)
    if ent_def is None:
        ent_def = npc_data.get(npc_id, {})
    img = _load_image(ent_def.get("image"), (img_size, img_size))
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
        if resp.get("next") == "gift":
            rtext = tr(game.lang, "dialog.gift")
        else:
            rtext = resp.get("text_zh", resp.get("text", "")) if game.lang == "zh" else resp.get("text", "")
        surf = font2.render(rtext, True, color)
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
    font = _get_font(16)
    font2 = _get_font(14)
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
    map_view_h = VIEWPORT
    map_view_w = VIEWPORT
    tile_h = TILE_SIZE
    tile_w = TILE_SIZE
    view_w_px = map_view_w * tile_w
    view_h_px = map_view_h * tile_h
    if hasattr(game, "get_player_draw_pos"):
        px, py = game.get_player_draw_pos()
    else:
        px, py = game.player.x, game.player.y
    cam_px = px * tile_w + tile_w / 2 - view_w_px / 2
    cam_py = py * tile_h + tile_h / 2 - view_h_px / 2
    max_cam_px = max(0, game.map.w * tile_w - view_w_px)
    max_cam_py = max(0, game.map.h * tile_h - view_h_px)
    cam_px = clamp(cam_px, 0, max_cam_px)
    cam_py = clamp(cam_py, 0, max_cam_py)
    left = int(cam_px // tile_w)
    top = int(cam_py // tile_h)
    offset_x = -(cam_px - left * tile_w)
    offset_y = -(cam_py - top * tile_h)
    portal_set = set()
    if getattr(game.map, "portals", None):
        for p in game.map.portals:
            portal_set.add((p.get("x"), p.get("y")))
    tiles_x = map_view_w + 2
    tiles_y = map_view_h + 2
    for y in range(tiles_y):
        for x in range(tiles_x):
            mx, my = left + x, top + y
            if 0 <= mx < game.map.w and 0 <= my < game.map.h:
                bt = game.map.get_block(mx, my)
                base_bt = blocktypes.get(bt, {}).get("base")
                if base_bt == "01" or bt == "01":
                    color = (70, 120, 70)
                elif bt == "02":
                    color = (60, 60, 60)
                elif bt == "04":
                    color = (200, 160, 60)
                else:
                    color = (160, 160, 80)
                tile_x = x * tile_w + offset_x
                tile_y = y * tile_h + offset_y
                pygame.draw.rect(screen, color, (tile_x, tile_y, tile_w, tile_h))
                if bt == "04":
                    # pulsating highlight for exit
                    t = pygame.time.get_ticks() / 1000.0
                    alpha = int(120 + 80 * (0.5 + 0.5 * math.sin(t * 2.0)))
                    overlay = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
                    overlay.fill((255, 230, 120, alpha))
                    screen.blit(overlay, (tile_x, tile_y))
                bt_img = blocktypes.get(bt, {}).get("image")
                if bt_img:
                    size = int(tile_w * 0.9), int(tile_h * 0.9)
                    img = _load_image(bt_img, size)
                    if img:
                        ox = tile_x + (tile_w - size[0]) // 2
                        oy = tile_y + (tile_h - size[1]) // 2
                        screen.blit(img, (ox, oy))
                if (mx, my) in portal_set:
                    overlay = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
                    overlay.fill((180, 60, 220, 160))
                    screen.blit(overlay, (tile_x, tile_y))
    view_rect = pygame.Rect(cam_px, cam_py, view_w_px, view_h_px)
    for ent in game.entities:
        ent_size = getattr(ent, "size", 1)
        ent_px = ent.x * tile_w
        ent_py = ent.y * tile_h
        ent_rect = pygame.Rect(ent_px, ent_py, ent_size * tile_w, ent_size * tile_h)
        if not ent_rect.colliderect(view_rect):
            continue
        if ent.eid == 'player':
            ex, ey = px, py
        else:
            ex, ey = ent.x, ent.y
        draw_x = ex * tile_w - cam_px + 4
        draw_y = ey * tile_h - cam_py + 4
        ent_size = getattr(ent, "size", 1)
        size = tile_w * ent_size - 8, tile_h * ent_size - 8
        ent_def = mobs_data.get(ent.eid, None)
        if ent_def is None:
            ent_def = npc_data.get(ent.eid, {})
        img = _load_image(ent_def.get("image"), size)
        if img:
            screen.blit(img, (int(draw_x), int(draw_y)))
        else:
            if ent.eid == 'player':
                color = (0, 0, 255)
            elif ent_def.get('ai_type') == 'friendly':
                color = (255, 200, 0)
            else:
                color = (255, 0, 0)
            pygame.draw.rect(screen, color, (int(draw_x) + 4, int(draw_y) + 4, size[0] - 8, size[1] - 8))

    if getattr(game, "transition_active", False):
        t = game.transition_timer / max(game.transition_duration, 0.001)
        if t <= 0.5:
            alpha = int(255 * (t * 2))
        else:
            alpha = int(255 * (1 - (t - 0.5) * 2))
        s = pygame.Surface(screen.get_size())
        s.set_alpha(max(0, min(255, alpha)))
        s.fill((0, 0, 0))
        screen.blit(s, (0, 0))
    elif game.blackout:
        s = pygame.Surface(screen.get_size())
        s.set_alpha(game.black_alpha)
        s.fill((0, 0, 0))
        screen.blit(s, (0, 0))

    draw_messages(game, screen)
    draw_dialog(game, screen)
    draw_shop(game, screen)

    if getattr(game, "banner", None):
        banner = game.banner
        now = time.time()
        age = now - banner.get("created", now)
        dur = banner.get("duration", 3.0)
        if age <= dur:
            alpha = int(255 * (1 - age / dur))
            text = banner.get("text", "")
            font = _get_font(20, bold=True)
            surf = font.render(text, True, (255, 255, 255))
            box_w = surf.get_width() + 40
            box_h = surf.get_height() + 20
            box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            box.fill((18, 60, 92, min(200, alpha)))
            x = screen.get_width() // 2 - box_w // 2
            y = screen.get_height() // 2 - box_h // 2
            screen.blit(box, (x, y))
            surf.set_alpha(alpha)
            screen.blit(surf, (x + 20, y + 10))
        else:
            game.banner = None

    if getattr(game, "map", None) is not None and game.map.name == "rogue":
        # mission bar top-right
        total = 1 if game.rogue_is_boss else getattr(game, "rogue_cfg", {}).get("mob_limit_normal", 10)
        left = game.count_hostile_mobs()
        text = f"mob left: {left}/{total}"
        font = _get_font(14)
        surf = font.render(text, True, (255, 255, 255))
        box_w = surf.get_width() + 20
        box_h = surf.get_height() + 10
        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill((10, 12, 16, 200))
        x = screen.get_width() - box_w - 12
        y = 12
        screen.blit(box, (x, y))
        screen.blit(surf, (x + 10, y + 5))
