import os
import pygame
from core.functions.support.utils import CONFIG_FILE, SAVE_DIR, load_json
from core.functions.support.i18n import tr
from core.functions.gameplay.game import Game
from core.functions.rendering.draw import draw, draw_main_menu, draw_esc_menu, draw_player_ui, draw_settings_menu, draw_dev_menu, draw_continue_menu, TILE_SIZE, VIEWPORT, FPS
from core.functions.world.map import npc_data

_UI_IMG_CACHE = {}


def _get_font(size, bold=False):
    for name in ("Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC", "Noto Sans CJK SC"):
        font = pygame.font.SysFont(name, size, bold=bold)
        if font is not None:
            return font
    return pygame.font.SysFont('consolas', size, bold=bold)


def _wrap_text(font, text, max_width):
    # CJK-friendly wrapping: when no spaces are present, wrap by characters.
    if " " not in text:
        lines = []
        line = ""
        for ch in text:
            test = line + ch
            if font.size(test)[0] <= max_width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = ch
        if line:
            lines.append(line)
        return lines
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


def _set_always_on_top():
    # Windows topmost window; safe no-op on unsupported platforms.
    try:
        info = pygame.display.get_wm_info()
        hwnd = info.get("window")
        if not hwnd:
            return
        import ctypes
        HWND_TOPMOST = -1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        ctypes.windll.user32.SetWindowPos(
            int(hwnd),
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        )
    except Exception:
        pass


def init_context():
    pygame.init()
    win_w = TILE_SIZE * VIEWPORT
    win_h = TILE_SIZE * (VIEWPORT + 1)
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption('Projekt:"IL2D" Prototype')
    _set_always_on_top()
    clock = pygame.time.Clock()
    ctx = {
        "screen": screen,
        "clock": clock,
        "game": Game(),
        "running": True,
        "fullscreen": False,
        "state": "main_menu",
        "new_game_name": "",
        "cutscene_lines": [],
        "cutscene_idx": 0,
        "menu_selected": 0,
        "settings_selected": 0,
        "settings_sub": None,
        "lang_selected": 0,
        "esc_selected": 0,
        "continue_selected": 0,
        "continue_slots": [],
        "type_buffer": "",
        "dev_menu_selected": 0,
        "dev_menu_target": None,
        "dev_menu_input": "",
        "held_keys": {"w": False, "a": False, "s": False, "d": False},
        "press_time": {"w": 0.0, "a": 0.0, "s": 0.0, "d": 0.0},
        "last_move_time": 0.0,
        "move_interval": 0.133
    }
    try:
        cfg = load_json(CONFIG_FILE)
        ctx["move_interval"] = cfg.get("move_interval", ctx["move_interval"])
    except Exception:
        pass
    return ctx


def run_frame(ctx):
    dt = ctx["clock"].tick(FPS) / 1000.0
    _process_events(ctx)
    _handle_held_movement(ctx)
    _update(ctx, dt)
    _render(ctx)


def run():
    ctx = init_context()
    while ctx["running"]:
        run_frame(ctx)


def _process_events(ctx):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            ctx["running"] = False
        elif event.type == pygame.KEYDOWN:
            if _check_dev_secret(ctx, event):
                continue
            _handle_key(ctx, event)
            _update_held_keys(ctx, event, True)
        elif event.type == pygame.TEXTINPUT:
            _handle_text_input(ctx, event.text)
        elif event.type == pygame.KEYUP:
            _update_held_keys(ctx, event, False)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            _handle_mouse(ctx, event.pos)


def _handle_key(ctx, event):
    state = ctx["state"]
    if state == "main_menu":
        _handle_main_menu_key(ctx, event)
    elif state == "name_input":
        _handle_name_input_key(ctx, event)
    elif state == "opening_cutscene":
        _handle_cutscene_key(ctx, event)
    elif state == "settings":
        _handle_settings_key(ctx, event)
    elif state == "dev_menu":
        _handle_dev_menu_key(ctx, event)
    elif state == "continue_menu":
        _handle_continue_menu_key(ctx, event)
    elif state == "esc_menu":
        _handle_esc_menu_key(ctx, event)
    elif state == "game":
        _handle_game_key(ctx, event)


def _check_dev_secret(ctx, event):
    if ctx["state"] != "game":
        return False
    if not event.unicode:
        return False
    ch = event.unicode.lower()
    if not ch.isalnum():
        return False
    secret = "twjuict9487isaprogamer"
    buf = (ctx.get("type_buffer", "") + ch)[-len(secret):]
    ctx["type_buffer"] = buf
    if buf.endswith(secret):
        ctx["state"] = "dev_menu"
        ctx["dev_menu_selected"] = 0
        ctx["dev_menu_target"] = None
        ctx["dev_menu_input"] = ""
        ctx["type_buffer"] = ""
        return True
    return False


def _handle_dev_menu_key(ctx, event):
    game = ctx["game"]
    opts = ["max_hp", "max_mp", "add_money", "add_skipper", "get_dev_set", "exit"]
    if ctx["dev_menu_target"] is None:
        if event.key in (pygame.K_UP, pygame.K_w):
            ctx["dev_menu_selected"] = (ctx["dev_menu_selected"] - 1) % len(opts)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            ctx["dev_menu_selected"] = (ctx["dev_menu_selected"] + 1) % len(opts)
        elif event.key == pygame.K_RETURN:
            choice = opts[ctx["dev_menu_selected"]]
            if choice == "exit":
                ctx["state"] = "game"
            elif choice == "get_dev_set":
                game.grant_dev_set()
            else:
                ctx["dev_menu_target"] = choice
                ctx["dev_menu_input"] = ""
        elif event.key == pygame.K_ESCAPE:
            ctx["state"] = "game"
    else:
        if event.key == pygame.K_ESCAPE:
            ctx["dev_menu_target"] = None
            ctx["dev_menu_input"] = ""
            return
        if event.key == pygame.K_BACKSPACE:
            ctx["dev_menu_input"] = ctx["dev_menu_input"][:-1]
            return
        if event.key == pygame.K_RETURN:
            if ctx["dev_menu_input"].isdigit():
                val = int(ctx["dev_menu_input"])
                if ctx["dev_menu_target"] == "max_hp":
                    game.player.max_hp = max(1, val)
                    game.player.hp = game.player.max_hp
                elif ctx["dev_menu_target"] == "max_mp":
                    game.player.max_mp = max(0, val)
                    game.player.mp = game.player.max_mp
                elif ctx["dev_menu_target"] == "add_money":
                    game.money += max(0, val)
                elif ctx["dev_menu_target"] == "add_skipper":
                    game.inventory["rouge level skipper"] = game.inventory.get("rouge level skipper", 0) + max(0, val)
            ctx["dev_menu_target"] = None
            ctx["dev_menu_input"] = ""
            return
        if event.unicode and event.unicode.isdigit():
            ctx["dev_menu_input"] += event.unicode


def _handle_main_menu_key(ctx, event):
    menu_count = 5
    if event.key == pygame.K_UP:
        ctx["menu_selected"] = (ctx["menu_selected"] - 1) % menu_count
    elif event.key == pygame.K_DOWN:
        ctx["menu_selected"] = (ctx["menu_selected"] + 1) % menu_count
    elif event.key == pygame.K_RETURN:
        if ctx["menu_selected"] == 0:
            _open_new_game_name_input(ctx)
        elif ctx["menu_selected"] == 1:
            ctx["continue_slots"] = _get_save_slots()
            ctx["continue_selected"] = 0
            ctx["state"] = "continue_menu"
        elif ctx["menu_selected"] == 2:
            ctx["state"] = "settings"
        elif ctx["menu_selected"] == 3:
            ctx["running"] = False
        elif ctx["menu_selected"] == 4:
            pass


def _get_save_slots():
    slots = []
    for i in range(1, 4):
        path = os.path.join(SAVE_DIR, f"slot_{i}.json")
        slots.append({"slot": i, "exists": os.path.isfile(path)})
    return slots


def _open_new_game_name_input(ctx):
    ctx["new_game_name"] = ""
    pygame.key.start_text_input()
    ctx["state"] = "name_input"


def _handle_name_input_key(ctx, event):
    if event.key == pygame.K_ESCAPE:
        pygame.key.stop_text_input()
        ctx["state"] = "main_menu"
        return
    if event.key == pygame.K_BACKSPACE:
        ctx["new_game_name"] = ctx.get("new_game_name", "")[:-1]
        return
    if event.key == pygame.K_RETURN:
        raw_name = (ctx.get("new_game_name", "") or "").strip()
        player_name = raw_name[:20] if raw_name else "Doctor"
        game = Game()
        game.player_name = player_name
        ctx["game"] = game
        pygame.key.stop_text_input()
        ctx["cutscene_lines"] = [
            "開局:你是一位博士，因為維什戴爾用多了，導致大腦放棄思考，被凱爾西丟入洞穴中歷練"
        ]
        ctx["cutscene_idx"] = 0
        ctx["state"] = "opening_cutscene"
        return


def _handle_text_input(ctx, text):
    if ctx.get("state") != "name_input":
        return
    current = ctx.get("new_game_name", "")
    for ch in text:
        if ch.isprintable() and ch not in ("\r", "\n", "\t"):
            if len(current) >= 20:
                break
            current += ch
    ctx["new_game_name"] = current


def _handle_cutscene_key(ctx, event):
    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
        ctx["cutscene_idx"] = ctx.get("cutscene_idx", 0) + 1
        if ctx["cutscene_idx"] >= len(ctx.get("cutscene_lines", [])):
            ctx["state"] = "game"


def _handle_continue_menu_key(ctx, event):
    slots = ctx.get("continue_slots", [])
    if not slots:
        if event.key == pygame.K_ESCAPE:
            ctx["state"] = "main_menu"
        return
    if event.key in (pygame.K_UP, pygame.K_w):
        ctx["continue_selected"] = (ctx["continue_selected"] - 1) % len(slots)
    elif event.key in (pygame.K_DOWN, pygame.K_s):
        ctx["continue_selected"] = (ctx["continue_selected"] + 1) % len(slots)
    elif event.key == pygame.K_RETURN:
        slot = slots[ctx["continue_selected"]]["slot"]
        if ctx["game"].load_save(slot):
            ctx["state"] = "game"
        else:
            # stay in menu if empty
            pass
    elif event.key == pygame.K_ESCAPE:
        ctx["state"] = "main_menu"


def _handle_settings_key(ctx, event):
    if event.key == pygame.K_ESCAPE:
        if ctx["settings_sub"] == "language":
            ctx["settings_sub"] = None
        else:
            ctx["state"] = "main_menu"
        return
    if ctx["settings_sub"] == "language":
        if event.key == pygame.K_UP:
            ctx["lang_selected"] = (ctx["lang_selected"] - 1) % 2
        elif event.key == pygame.K_DOWN:
            ctx["lang_selected"] = (ctx["lang_selected"] + 1) % 2
        elif event.key == pygame.K_RETURN:
            ctx["game"].lang = "zh" if ctx["lang_selected"] == 0 else "en"
            ctx["settings_sub"] = None
        return
    if event.key == pygame.K_UP:
        ctx["settings_selected"] = (ctx["settings_selected"] - 1) % 2
    elif event.key == pygame.K_DOWN:
        ctx["settings_selected"] = (ctx["settings_selected"] + 1) % 2
    elif event.key == pygame.K_RETURN:
        if ctx["settings_selected"] == 0:
            ctx["settings_sub"] = "language"
        elif ctx["settings_selected"] == 1:
            ctx["state"] = "main_menu"


def _handle_esc_menu_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode:
        if game.ui_mode in ("equip_root", "equip", "equip_category"):
            if event.key == pygame.K_q:
                game.equip_best()
                return
            if event.key == pygame.K_r:
                game.unequip_all()
                return
        if event.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w, pygame.K_a):
            if game.ui_mode == "save":
                game.save_selected = (game.save_selected - 1) % 3
            elif game.ui_mode == "equip_root":
                game.equip_root_selected = max(0, game.equip_root_selected - 1)
            elif game.ui_mode == "equip":
                game.equip_selected = max(0, game.equip_selected - 1)
            elif game.ui_mode == "equip_category":
                game.equip_category_selected = max(0, game.equip_category_selected - 1)
            elif game.ui_mode == "item":
                game.item_selected = max(0, game.item_selected - 1)
            elif game.ui_mode == "magic":
                game.magic_selected = max(0, game.magic_selected - 1)
            elif game.ui_mode == "leave_confirm":
                game.leave_selected = max(0, game.leave_selected - 1)
            elif game.ui_mode == "level_skipper":
                game.change_level_skip_amount(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s, pygame.K_d):
            if game.ui_mode == "save":
                game.save_selected = (game.save_selected + 1) % 3
            elif game.ui_mode == "equip_root":
                game.equip_root_selected = min(2, game.equip_root_selected + 1)
            elif game.ui_mode == "equip":
                game.equip_selected = game.equip_selected + 1
            elif game.ui_mode == "equip_category":
                max_idx = len(game.get_equip_categories()) - 1
                game.equip_category_selected = min(max_idx, game.equip_category_selected + 1)
            elif game.ui_mode == "item":
                game.item_selected = game.item_selected + 1
            elif game.ui_mode == "magic":
                game.magic_selected = game.magic_selected + 1
            elif game.ui_mode == "leave_confirm":
                max_opt = 0 if game.leave_step == 2 else 1
                game.leave_selected = min(max_opt, game.leave_selected + 1)
            elif game.ui_mode == "level_skipper":
                game.change_level_skip_amount(1)
        elif event.key == pygame.K_ESCAPE:
            if game.ui_mode == "equip":
                game.ui_mode = "equip_category"
            elif game.ui_mode == "equip_category":
                game.ui_mode = "equip_root"
            elif game.ui_mode == "level_skipper":
                game.ui_mode = "item"
            else:
                game.ui_mode = None
        elif event.key == pygame.K_RETURN:
            if game.ui_mode == "save":
                game.save_game()
            elif game.ui_mode == "equip":
                game.equip_selected_item()
            elif game.ui_mode == "equip_category":
                cats = game.get_equip_categories()
                game.equip_category = cats[game.equip_category_selected % len(cats)]
                game.open_equip_items()
            elif game.ui_mode == "equip_root":
                if game.equip_root_selected == 0:
                    game.ui_mode = "equip_category"
                elif game.equip_root_selected == 1:
                    game.equip_best()
                elif game.equip_root_selected == 2:
                    game.unequip_all()
            elif game.ui_mode == "item":
                game.use_item()
            elif game.ui_mode == "magic":
                game.cast_spell()
            elif game.ui_mode == "leave_confirm":
                game.handle_leave_confirm()
            elif game.ui_mode == "level_skipper":
                game.confirm_level_skipper_use()
            if game.request_close_esc_menu:
                game.request_close_esc_menu = False
                game.ui_mode = None
                ctx["state"] = "game"
        return

    if event.key == pygame.K_UP:
        ctx["esc_selected"] = (ctx["esc_selected"] - 1) % 8
    elif event.key == pygame.K_DOWN:
        ctx["esc_selected"] = (ctx["esc_selected"] + 1) % 8
    elif event.key == pygame.K_ESCAPE:
        ctx["state"] = "game"
    elif event.key == pygame.K_RETURN:
        if ctx["esc_selected"] == 0:
            game.ui_mode = "item"
        elif ctx["esc_selected"] == 1:
            game.ui_mode = "magic"
        elif ctx["esc_selected"] == 2:
            game.open_equip()
        elif ctx["esc_selected"] == 3:
            game.ui_mode = "team"
        elif ctx["esc_selected"] == 4:
            game.ui_mode = "objective"
        elif ctx["esc_selected"] == 5:
            game.ui_mode = "status"
        elif ctx["esc_selected"] == 6:
            game.open_save()
        elif ctx["esc_selected"] == 7:
            game.open_leave_confirm()


def _handle_game_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode == "dialog":
        if event.key == pygame.K_UP:
            game.dialog_selected = max(0, game.dialog_selected - 1)
        elif event.key == pygame.K_DOWN:
            game.dialog_selected = game.dialog_selected + 1
        elif event.key == pygame.K_RETURN:
            game.dialog_choose()
        elif event.key == pygame.K_ESCAPE:
            game.close_dialog()
        return
    if game.ui_mode == "shop":
        if event.key == pygame.K_UP and game.shop_items:
            game.shop_selected = (game.shop_selected - 1) % len(game.shop_items)
        elif event.key == pygame.K_DOWN and game.shop_items:
            game.shop_selected = (game.shop_selected + 1) % len(game.shop_items)
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            game.cycle_shop_category(-1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            game.cycle_shop_category(1)
        elif event.key == pygame.K_RETURN:
            game.buy_selected_item()
        elif event.key == pygame.K_ESCAPE:
            game.close_shop()
        return

    if event.key == pygame.K_ESCAPE:
        ctx["state"] = "esc_menu"
    if event.key == pygame.K_F12:
        ctx["fullscreen"] = not ctx["fullscreen"]
        win_w = TILE_SIZE * VIEWPORT
        win_h = TILE_SIZE * (VIEWPORT + 1)
        if ctx["fullscreen"]:
            ctx["screen"] = pygame.display.set_mode((win_w, win_h), pygame.FULLSCREEN)
        else:
            ctx["screen"] = pygame.display.set_mode((win_w, win_h))
        _set_always_on_top()
    if event.key == pygame.K_w:
        _press_move(ctx, "w", 0, -1)
    elif event.key == pygame.K_s:
        _press_move(ctx, "s", 0, 1)
    elif event.key == pygame.K_a:
        _press_move(ctx, "a", -1, 0)
    elif event.key == pygame.K_d:
        _press_move(ctx, "d", 1, 0)
    elif event.key == pygame.K_e:
        game.player_interact()


def _handle_mouse(ctx, pos):
    state = ctx["state"]
    if state == "main_menu":
        _handle_mouse_main_menu(ctx, pos)
    elif state == "settings":
        _handle_mouse_settings(ctx, pos)
    elif state == "continue_menu":
        _handle_mouse_continue_menu(ctx, pos)
    elif state == "esc_menu":
        _handle_mouse_esc_menu(ctx, pos)
    elif state == "game":
        _handle_mouse_game(ctx, pos)


def _update_held_keys(ctx, event, is_down):
    if event.key == pygame.K_w:
        ctx["held_keys"]["w"] = is_down
    elif event.key == pygame.K_s:
        ctx["held_keys"]["s"] = is_down
    elif event.key == pygame.K_a:
        ctx["held_keys"]["a"] = is_down
    elif event.key == pygame.K_d:
        ctx["held_keys"]["d"] = is_down


def _press_move(ctx, key, dx, dy):
    ctx["press_time"][key] = pygame.time.get_ticks() / 1000.0
    moved = ctx["game"].request_player_move(dx, dy)
    if moved:
        ctx["last_move_time"] = ctx["press_time"][key]


def _handle_held_movement(ctx):
    if ctx["state"] != "game":
        return
    game = ctx["game"]
    if game.ui_mode:
        return
    now = pygame.time.get_ticks() / 1000.0
    if now - ctx["last_move_time"] < ctx["move_interval"]:
        return
    up = ctx["held_keys"]["w"] and now - ctx["press_time"]["w"] >= 0.2
    down = ctx["held_keys"]["s"] and now - ctx["press_time"]["s"] >= 0.2
    left = ctx["held_keys"]["a"] and now - ctx["press_time"]["a"] >= 0.2
    right = ctx["held_keys"]["d"] and now - ctx["press_time"]["d"] >= 0.2
    dx = (1 if right else 0) - (1 if left else 0)
    dy = (1 if down else 0) - (1 if up else 0)
    if dx != 0 or dy != 0:
        moved = game.request_player_move(dx, dy)
        if moved:
            ctx["last_move_time"] = now


def _handle_mouse_main_menu(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    font2 = _get_font(32)
    opts = ['new_game', 'continue', 'setting', 'leave', 'credits']
    total_height = len(opts) * 44
    start_y = screen.get_height() // 2 - total_height // 2 + 40
    for i, opt in enumerate(opts):
        label = tr(ctx["game"].lang, f"menu.{opt}")
        surf = font2.render(label, True, (255, 255, 255))
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * 44
        rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
        if rect.collidepoint(mx, my):
            ctx["menu_selected"] = i
            if i == 0:
                _open_new_game_name_input(ctx)
            elif i == 1:
                ctx["continue_slots"] = _get_save_slots()
                ctx["continue_selected"] = 0
                ctx["state"] = "continue_menu"
            elif i == 2:
                ctx["state"] = "settings"
            elif i == 3:
                ctx["running"] = False
            elif i == 4:
                pass
            break


def _handle_mouse_settings(ctx, pos):
    # keep mouse simple: click outside closes sub menu
    if ctx["settings_sub"] == "language":
        return


def _handle_mouse_continue_menu(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    slots = ctx.get("continue_slots", [])
    if not slots:
        return
    font = _get_font(22)
    start_y = 140
    item_h = font.get_height() + 10
    for i, _ in enumerate(slots):
        rect = pygame.Rect(screen.get_width() // 2 - 140, start_y + i * item_h - 4, 280, font.get_height() + 8)
        if rect.collidepoint(mx, my):
            ctx["continue_selected"] = i
            slot = slots[i]["slot"]
            if ctx["game"].load_save(slot):
                ctx["state"] = "game"
            break


def _handle_mouse_esc_menu(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    game = ctx["game"]
    menu_w = screen.get_width() // 4
    font = _get_font(16)
    item_h = font.get_height() + 6
    if mx < menu_w:
        idx = (my - 20) // item_h
        if 0 <= idx < 8:
            ctx["esc_selected"] = idx
            if idx == 0:
                game.ui_mode = "item"
            elif idx == 1:
                game.ui_mode = "magic"
            elif idx == 2:
                game.open_equip()
            elif idx == 3:
                game.ui_mode = "team"
            elif idx == 4:
                game.ui_mode = "objective"
            elif idx == 5:
                game.ui_mode = "status"
            elif idx == 6:
                game.open_save()
            elif idx == 7:
                game.open_leave_confirm()
    else:
        panel = pygame.Rect(menu_w, 0, screen.get_width() - menu_w, screen.get_height())
        font = pygame.font.SysFont('consolas', 14)
        y = panel.y + 48
        if game.ui_mode == "save":
            for i in range(3):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.save_selected = i
                    game.save_game()
                    break
                y += font.get_height() + 10
        elif game.ui_mode == "equip_category":
            cats = game.get_equip_categories()
            for i in range(len(cats)):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.equip_category_selected = i
                    game.equip_category = cats[i]
                    game.open_equip_items()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "equip_root":
            y = panel.y + 48
            for i in range(3):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.equip_root_selected = i
                    if i == 0:
                        game.ui_mode = "equip_category"
                    elif i == 1:
                        game.equip_best()
                    else:
                        game.unequip_all()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "equip":
            equipables = game.get_equipable_items()
            slot_key = "ring" if game.equip_category.startswith("ring") else game.equip_category
            filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
            for i, _ in enumerate(filtered):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.equip_selected = i
                    game.equip_selected_item()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "item":
            items = game.get_item_list()
            for i, _ in enumerate(items):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.item_selected = i
                    game.use_item()
                    if game.request_close_esc_menu:
                        game.request_close_esc_menu = False
                        game.ui_mode = None
                        ctx["state"] = "game"
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "magic":
            for i, _ in enumerate(game.spells):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.magic_selected = i
                    game.cast_spell()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "leave_confirm":
            y = panel.y + 48 + font.get_height() + 10
            options = ["yes", "no"] if game.leave_step < 2 else ["ok"]
            for i, _ in enumerate(options):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.leave_selected = i
                    game.handle_leave_confirm()
                    break
                y += font.get_height() + 6


def _handle_mouse_game(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    game = ctx["game"]
    if game.ui_mode == "dialog":
        panel_h = screen.get_height() // 3
        panel = pygame.Rect(0, screen.get_height() - panel_h - 12, screen.get_width(), panel_h)
        img_size = panel_h - 24
        font2 = pygame.font.SysFont('consolas', 14)
        responses = game.dialog_data.get(game.dialog_node, {}).get("responses", [])
        max_width = panel.width - img_size - 36
        node = game.dialog_data.get(game.dialog_node, {})
        text = node.get("text_zh", node.get("text", "")) if game.lang == "zh" else node.get("text", "")
        lines = _wrap_text(font2, text, max_width)
        text_y = panel.y + 32 + len(lines) * (font2.get_height() + 4)
        resp_y = panel.bottom - 20 - len(responses) * (font2.get_height() + 6)
        if resp_y < text_y + 8:
            resp_y = text_y + 8
        for i, resp in enumerate(responses):
            _ = resp.get("text_zh", resp.get("text", "")) if game.lang == "zh" else resp.get("text", "")
            rect = pygame.Rect(panel.x + img_size + 8, resp_y - 2, panel.width - img_size - 32, font2.get_height() + 4)
            if rect.collidepoint(mx, my):
                game.dialog_selected = i
                game.dialog_choose()
                break
            resp_y += font2.get_height() + 6
    elif game.ui_mode == "shop":
        panel = pygame.Rect(screen.get_width() // 10, screen.get_height() // 10, screen.get_width() * 8 // 10, screen.get_height() * 8 // 10)
        font2 = pygame.font.SysFont('consolas', 14)
        y = panel.y + 48
        for i, _ in enumerate(game.shop_items):
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font2.get_height() + 4)
            if rect.collidepoint(mx, my):
                game.shop_selected = i
                game.buy_selected_item()
                break
            y += font2.get_height() + 6


def _update(ctx, dt):
    game = ctx["game"]
    if ctx["state"] == "game" and getattr(game, 'death_timer', None) is not None:
        game.death_timer -= dt
        if game.death_timer <= 0:
            pygame.quit()
            ctx["running"] = False
            return
    if ctx["state"] == "game" and getattr(game, 'death_timer', None) is None:
        game.update(player_tick=False)
        game.update_time(dt)


def _draw_name_input(ctx):
    screen = ctx["screen"]
    screen.fill((5, 10, 18))
    title_font = _get_font(42, bold=True)
    body_font = _get_font(28)
    hint_font = _get_font(20)
    title = title_font.render("New Game", True, (220, 240, 255))
    prompt = body_font.render("請輸入名字 (最多20字元)", True, (185, 220, 245))
    name = ctx.get("new_game_name", "")
    box_w, box_h = screen.get_width() - 140, 58
    box_x = (screen.get_width() - box_w) // 2
    box_y = screen.get_height() // 2 - box_h // 2
    pygame.draw.rect(screen, (16, 30, 46), (box_x, box_y, box_w, box_h), border_radius=8)
    pygame.draw.rect(screen, (190, 230, 255), (box_x, box_y, box_w, box_h), 2, border_radius=8)
    display_name = name if name else "Doctor"
    name_surf = body_font.render(display_name, True, (255, 255, 255))
    hint = hint_font.render("Enter 確認 / Esc 返回", True, (150, 180, 205))
    screen.blit(title, ((screen.get_width() - title.get_width()) // 2, box_y - 100))
    screen.blit(prompt, ((screen.get_width() - prompt.get_width()) // 2, box_y - 45))
    screen.blit(name_surf, (box_x + 12, box_y + 13))
    screen.blit(hint, ((screen.get_width() - hint.get_width()) // 2, box_y + box_h + 18))


def _draw_cutscene(ctx):
    screen = ctx["screen"]
    screen.fill((0, 0, 0))
    font = _get_font(24)
    name_font = _get_font(24, bold=True)
    hint_font = _get_font(18)
    lines = ctx.get("cutscene_lines", [])
    idx = ctx.get("cutscene_idx", 0)
    text = lines[idx] if 0 <= idx < len(lines) else ""
    panel_h = screen.get_height() // 4
    panel = pygame.Rect(0, screen.get_height() - panel_h, screen.get_width(), panel_h)
    pygame.draw.rect(screen, (8, 12, 20), panel)
    pygame.draw.rect(screen, (120, 170, 215), panel, 2)

    dev_img = _load_npc_ui_image("dev", panel_h - 24)
    img_x = panel.x + 12
    img_y = panel.y + 12
    text_x = panel.x + 24
    if dev_img is not None:
        screen.blit(dev_img, (img_x, img_y))
        text_x = img_x + dev_img.get_width() + 14

    speaker = "Dev (Narrative)"
    speaker_surf = name_font.render(speaker, True, (255, 235, 180))
    screen.blit(speaker_surf, (text_x, panel.y + 10))

    wrapped = _wrap_text(font, text, panel.width - (text_x - panel.x) - 20)
    y = panel.y + 42
    for line in wrapped[:3]:
        surf = font.render(line, True, (225, 235, 245))
        screen.blit(surf, (text_x, y))
        y += font.get_height() + 6
    hint = hint_font.render("Enter 繼續", True, (165, 185, 205))
    screen.blit(hint, (panel.right - hint.get_width() - 16, panel.bottom - hint.get_height() - 10))


def _load_npc_ui_image(npc_id, size):
    data = npc_data.get(npc_id, {}) if isinstance(npc_data, dict) else {}
    filename = data.get("image")
    if not filename:
        return None
    cache_key = (filename, int(size))
    if cache_key in _UI_IMG_CACHE:
        return _UI_IMG_CACHE[cache_key]
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Pictures")
    path = os.path.join(base_dir, filename)
    stem, _ = os.path.splitext(filename)
    nobg = os.path.join(base_dir, "nobg_output", f"{stem}_nobg.png")
    if os.path.isfile(nobg):
        path = nobg
    if not os.path.isfile(path):
        _UI_IMG_CACHE[cache_key] = None
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.smoothscale(img, (int(size), int(size)))
        _UI_IMG_CACHE[cache_key] = img
        return img
    except Exception:
        _UI_IMG_CACHE[cache_key] = None
        return None


def _render(ctx):
    if ctx["state"] == "main_menu":
        draw_main_menu(ctx["screen"], ctx["menu_selected"], ctx["game"].lang)
    elif ctx["state"] == "name_input":
        _draw_name_input(ctx)
    elif ctx["state"] == "opening_cutscene":
        _draw_cutscene(ctx)
    elif ctx["state"] == "settings":
        draw_settings_menu(
            ctx["screen"],
            ctx["settings_selected"],
            ctx["settings_sub"],
            ctx["lang_selected"],
            ctx["game"].lang
        )
    elif ctx["state"] == "continue_menu":
        draw_continue_menu(ctx["screen"], ctx["continue_slots"], ctx["continue_selected"], ctx["game"].lang)
    elif ctx["state"] == "dev_menu":
        draw(ctx["game"], ctx["screen"])
        draw_player_ui(ctx["game"], ctx["screen"])
        draw_dev_menu(ctx["screen"], ctx)
    elif ctx["state"] == "esc_menu":
        draw(ctx["game"], ctx["screen"])
        draw_esc_menu(ctx["screen"], ctx["esc_selected"], ctx["game"])
    else:
        draw(ctx["game"], ctx["screen"])
        draw_player_ui(ctx["game"], ctx["screen"])
    if ctx["game"].request_quit:
        ctx["running"] = False
    pygame.display.flip()
