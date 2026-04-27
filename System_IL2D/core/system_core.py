import os
import pygame
from core.functions.support.utils import CONFIG_FILE, SAVE_DIR, load_json
from core.functions.support.i18n import tr
from core.functions.gameplay.game import Game
from core.functions.rendering.draw import draw, draw_main_menu, draw_esc_menu, draw_player_ui, draw_settings_menu, draw_dev_menu, draw_continue_menu, TILE_SIZE, VIEWPORT, FPS
from core.functions.world.map import npc_data

_UI_IMG_CACHE = {}


def _get_font(size, bold=False):
    # Prefer explicit CJK font files on Windows to avoid missing glyphs.
    for font_path in (
        r"C:\Windows\Fonts\msjh.ttc",  # Microsoft JhengHei
        r"C:\Windows\Fonts\msyh.ttc",  # Microsoft YaHei
        r"C:\Windows\Fonts\mingliu.ttc",
    ):
        if os.path.isfile(font_path):
            try:
                return pygame.font.Font(font_path, size)
            except Exception:
                pass
    for name in ("Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC", "Noto Sans CJK SC"):
        try:
            matched = pygame.font.match_font(name)
            if matched:
                return pygame.font.Font(matched, size)
        except Exception:
            pass
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
        "tutorial_lines": [],
        "tutorial_idx": 0,
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
        "move_interval": 0.133,
        "hold_repeat_delay": 0.08,
    }
    try:
        cfg = load_json(CONFIG_FILE)
        ctx["move_interval"] = cfg.get("move_interval", ctx["move_interval"])
        ctx["hold_repeat_delay"] = cfg.get("hold_repeat_delay", ctx["hold_repeat_delay"])
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
    elif state == "tutorial":
        _handle_tutorial_key(ctx, event)
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
    opts = ["pre_dev_set", "max_hp", "max_mp", "add_money", "add_skipper", "get_dev_set", "exit"]
    if ctx["dev_menu_target"] is None:
        if event.key in (pygame.K_UP, pygame.K_w):
            ctx["dev_menu_selected"] = (ctx["dev_menu_selected"] - 1) % len(opts)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            ctx["dev_menu_selected"] = (ctx["dev_menu_selected"] + 1) % len(opts)
        elif event.key == pygame.K_RETURN:
            choice = opts[ctx["dev_menu_selected"]]
            if choice == "exit":
                ctx["state"] = "game"
            elif choice == "pre_dev_set":
                game.grant_pre_dev_set()
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
                    game.inventory["rogue level skipper"] = game.inventory.get("rogue level skipper", 0) + max(0, val)
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
        ctx["tutorial_lines"] = _build_tutorial_lines(game.lang)
        ctx["tutorial_idx"] = 0
        ctx["state"] = "tutorial"
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


def _build_tutorial_lines(lang):
    return [
        tr(lang, "tutorial.step.1"),
        tr(lang, "tutorial.step.2"),
        tr(lang, "tutorial.step.3"),
        tr(lang, "tutorial.step.4"),
        tr(lang, "tutorial.step.5"),
        tr(lang, "tutorial.step.6"),
    ]


def _handle_tutorial_key(ctx, event):
    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
        ctx["tutorial_idx"] = ctx.get("tutorial_idx", 0) + 1
        if ctx["tutorial_idx"] >= len(ctx.get("tutorial_lines", [])):
            ctx["state"] = "game"
        return
    if event.key == pygame.K_ESCAPE:
        # Allow quick skip for repeat runs while keeping default flow instructional.
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


def _handle_hotbar_menu_key(game, event):
    if event.key == pygame.K_i:
        game.hotbar_mode = "magic" if game.hotbar_mode == "item" else "item"
        game.hotbar_list_selected = 0
        return
    if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
        if game.hotbar_mode == "item":
            game.item_hotbar_slots[game.hotbar_slot_selected] = None
        else:
            game.magic_hotbar_slots[game.hotbar_slot_selected] = None
        return

    stage = getattr(game, "hotbar_stage", "grid")
    if stage not in ("grid", "pick"):
        stage = "grid"
        game.hotbar_stage = "grid"

    if stage == "grid":
        if event.key in (pygame.K_UP, pygame.K_w):
            game.hotbar_slot_selected = max(0, game.hotbar_slot_selected - 1)
            return
        if event.key in (pygame.K_DOWN, pygame.K_s):
            game.hotbar_slot_selected = min(9, game.hotbar_slot_selected + 1)
            return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            game.hotbar_mode = "item"
            return
        if event.key in (pygame.K_RIGHT, pygame.K_d):
            game.hotbar_mode = "magic"
            return
        if event.key == pygame.K_RETURN:
            game.hotbar_stage = "pick"
            game.hotbar_list_selected = 0
            return
        if event.key == pygame.K_ESCAPE:
            game.ui_mode = None
            return
        return

    # stage == "pick"
    src = game.get_item_list() if game.hotbar_mode == "item" else [sp.get("name") for sp in game.spells]
    if event.key in (pygame.K_LEFT, pygame.K_a):
        game.hotbar_mode = "item"
        game.hotbar_list_selected = 0
        return
    if event.key in (pygame.K_RIGHT, pygame.K_d):
        game.hotbar_mode = "magic"
        game.hotbar_list_selected = 0
        return
    if event.key in (pygame.K_UP, pygame.K_w):
        if src:
            game.hotbar_list_selected = max(0, game.hotbar_list_selected - 1)
        return
    if event.key in (pygame.K_DOWN, pygame.K_s):
        if src:
            game.hotbar_list_selected = min(len(src) - 1, game.hotbar_list_selected + 1)
        return
    if event.key == pygame.K_RETURN:
        if src:
            picked = src[game.hotbar_list_selected % len(src)]
            if game.hotbar_mode == "item":
                game.item_hotbar_slots[game.hotbar_slot_selected] = picked
            else:
                game.magic_hotbar_slots[game.hotbar_slot_selected] = picked
        return
    if event.key == pygame.K_ESCAPE:
        game.hotbar_stage = "grid"
        return


def _handle_esc_menu_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode:
        if game.ui_mode == "hotbar":
            _handle_hotbar_menu_key(game, event)
            if game.request_close_esc_menu:
                game.request_close_esc_menu = False
                game.ui_mode = None
                ctx["state"] = "game"
            return
        if game.ui_mode == "team":
            members = game.get_team_member_ids() if hasattr(game, "get_team_member_ids") else []
            if event.key in (pygame.K_UP, pygame.K_w) and members:
                game.team_selected = (game.team_selected - 1) % len(members)
                return
            if event.key in (pygame.K_DOWN, pygame.K_s) and members:
                game.team_selected = (game.team_selected + 1) % len(members)
                return
            if event.key == pygame.K_RETURN and members:
                game.open_team_equip(game.team_selected)
                return
            if event.key == pygame.K_ESCAPE:
                game.ui_mode = None
                return
            return
        if game.ui_mode in ("equip_root", "equip", "equip_category"):
            if event.key == pygame.K_q:
                game.equip_best()
                return
            if event.key == pygame.K_r:
                game.unequip_all()
                return
        if game.ui_mode in ("team_equip_root", "team_equip", "team_equip_category"):
            if event.key == pygame.K_q:
                game.team_equip_best()
                return
            if event.key == pygame.K_r:
                game.team_unequip_all()
                return
        if game.ui_mode == "hotbar":
            if event.key == pygame.K_i:
                game.hotbar_mode = "magic" if game.hotbar_mode == "item" else "item"
                game.hotbar_list_selected = 0
                return
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if game.hotbar_mode == "item":
                    game.item_hotbar_slots[game.hotbar_slot_selected] = None
                else:
                    game.magic_hotbar_slots[game.hotbar_slot_selected] = None
                return
        if event.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w, pygame.K_a):
            if game.ui_mode == "save":
                game.save_selected = (game.save_selected - 1) % 3
            elif game.ui_mode == "equip_root":
                game.equip_root_selected = max(0, game.equip_root_selected - 1)
            elif game.ui_mode == "team_equip_root":
                game.team_equip_root_selected = max(0, game.team_equip_root_selected - 1)
            elif game.ui_mode == "equip":
                focus = getattr(game, "equip_focus", "tabs")
                if focus == "tabs":
                    game.equip_root_selected = max(0, game.equip_root_selected - 1)
                elif focus == "slots":
                    cats = game.get_equip_categories()
                    if cats:
                        idx = game.equip_category_selected % len(cats)
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            idx = max(0, idx - 1)
                        else:
                            idx = max(0, idx - 2)
                        game.equip_category_selected = idx
                        game.equip_category = cats[idx]
                        game.equip_selected = 0
                else:  # items
                    equipables = game.get_equipable_items()
                    slot_key = "ring" if game.equip_category.startswith("ring") else game.equip_category
                    filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
                    if not filtered:
                        return
                    idx = game.equip_selected % len(filtered)
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        idx = max(0, idx - 1)
                    else:
                        idx = max(0, idx - 2)
                    game.equip_selected = idx
            elif game.ui_mode == "team_equip":
                focus = getattr(game, "team_equip_focus", "tabs")
                if focus == "tabs":
                    game.team_equip_root_selected = max(0, game.team_equip_root_selected - 1)
                elif focus == "slots":
                    cats = game.get_team_equip_categories()
                    if cats:
                        idx = game.team_equip_slot_selected % len(cats)
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            idx = max(0, idx - 1)
                        else:
                            idx = max(0, idx - 2)
                        game.team_equip_slot_selected = idx
                        game.team_equip_category = cats[idx]
                        game.team_equip_item_selected = 0
                else:
                    equipables = game.get_team_equipable_items()
                    slot_key = "ring" if game.team_equip_category.startswith("ring") else game.team_equip_category
                    filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
                    if not filtered:
                        return
                    idx = game.team_equip_item_selected % len(filtered)
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        idx = max(0, idx - 1)
                    else:
                        idx = max(0, idx - 2)
                    game.team_equip_item_selected = idx
            elif game.ui_mode == "equip_category":
                game.equip_category_selected = max(0, game.equip_category_selected - 1)
            elif game.ui_mode == "team_equip_category":
                game.team_equip_slot_selected = max(0, game.team_equip_slot_selected - 1)
            elif game.ui_mode == "item":
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    game.cycle_item_category(-1)
                else:
                    items = game.get_item_list()
                    if items:
                        idx = game.item_selected % len(items)
                        idx = max(0, idx - 2)
                        game.item_selected = idx
            elif game.ui_mode == "objective":
                missions = game.get_trackable_missions() if hasattr(game, "get_trackable_missions") else []
                if missions:
                    game.objective_selected = max(0, game.objective_selected - 1)
            elif game.ui_mode == "hotbar":
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    game.hotbar_slot_selected = max(0, game.hotbar_slot_selected - 1)
                else:
                    game.hotbar_list_selected = max(0, game.hotbar_list_selected - 1)
            elif game.ui_mode == "skill_tree":
                game.skill_tree_selected = max(0, game.skill_tree_selected - 1)
            elif game.ui_mode == "leave_confirm":
                game.leave_selected = max(0, game.leave_selected - 1)
            elif game.ui_mode == "level_skipper":
                game.change_level_skip_amount(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s, pygame.K_d):
            if game.ui_mode == "save":
                game.save_selected = (game.save_selected + 1) % 3
            elif game.ui_mode == "equip_root":
                game.equip_root_selected = min(2, game.equip_root_selected + 1)
            elif game.ui_mode == "team_equip_root":
                game.team_equip_root_selected = min(2, game.team_equip_root_selected + 1)
            elif game.ui_mode == "equip":
                focus = getattr(game, "equip_focus", "tabs")
                if focus == "tabs":
                    game.equip_root_selected = min(2, game.equip_root_selected + 1)
                elif focus == "slots":
                    cats = game.get_equip_categories()
                    if cats:
                        idx = game.equip_category_selected % len(cats)
                        if event.key in (pygame.K_RIGHT, pygame.K_d):
                            idx = min(len(cats) - 1, idx + 1)
                        else:
                            idx = min(len(cats) - 1, idx + 2)
                        game.equip_category_selected = idx
                        game.equip_category = cats[idx]
                        game.equip_selected = 0
                else:  # items
                    equipables = game.get_equipable_items()
                    slot_key = "ring" if game.equip_category.startswith("ring") else game.equip_category
                    filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
                    if not filtered:
                        return
                    idx = game.equip_selected % len(filtered)
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        idx = min(len(filtered) - 1, idx + 1)
                    else:
                        idx = min(len(filtered) - 1, idx + 2)
                    game.equip_selected = idx
            elif game.ui_mode == "team_equip":
                focus = getattr(game, "team_equip_focus", "tabs")
                if focus == "tabs":
                    game.team_equip_root_selected = min(2, game.team_equip_root_selected + 1)
                elif focus == "slots":
                    cats = game.get_team_equip_categories()
                    if cats:
                        idx = game.team_equip_slot_selected % len(cats)
                        if event.key in (pygame.K_RIGHT, pygame.K_d):
                            idx = min(len(cats) - 1, idx + 1)
                        else:
                            idx = min(len(cats) - 1, idx + 2)
                        game.team_equip_slot_selected = idx
                        game.team_equip_category = cats[idx]
                        game.team_equip_item_selected = 0
                else:
                    equipables = game.get_team_equipable_items()
                    slot_key = "ring" if game.team_equip_category.startswith("ring") else game.team_equip_category
                    filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
                    if not filtered:
                        return
                    idx = game.team_equip_item_selected % len(filtered)
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        idx = min(len(filtered) - 1, idx + 1)
                    else:
                        idx = min(len(filtered) - 1, idx + 2)
                    game.team_equip_item_selected = idx
            elif game.ui_mode == "equip_category":
                max_idx = len(game.get_equip_categories()) - 1
                game.equip_category_selected = min(max_idx, game.equip_category_selected + 1)
            elif game.ui_mode == "team_equip_category":
                max_idx = len(game.get_team_equip_categories()) - 1
                game.team_equip_slot_selected = min(max_idx, game.team_equip_slot_selected + 1)
            elif game.ui_mode == "item":
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    game.cycle_item_category(1)
                else:
                    items = game.get_item_list()
                    if items:
                        idx = game.item_selected % len(items)
                        idx = min(len(items) - 1, idx + 2)
                        game.item_selected = idx
            elif game.ui_mode == "objective":
                missions = game.get_trackable_missions() if hasattr(game, "get_trackable_missions") else []
                if missions:
                    game.objective_selected = min(len(missions) - 1, game.objective_selected + 1)
            elif game.ui_mode == "hotbar":
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    game.hotbar_slot_selected = min(9, game.hotbar_slot_selected + 1)
                else:
                    game.hotbar_list_selected = game.hotbar_list_selected + 1
            elif game.ui_mode == "skill_tree":
                game.skill_tree_selected = game.skill_tree_selected + 1
            elif game.ui_mode == "leave_confirm":
                game.leave_selected = min(2, game.leave_selected + 1)
            elif game.ui_mode == "level_skipper":
                game.change_level_skip_amount(1)
        elif event.key == pygame.K_ESCAPE:
            if game.ui_mode == "equip":
                focus = getattr(game, "equip_focus", "tabs")
                if focus == "items":
                    game.equip_focus = "slots"
                elif focus == "slots":
                    game.equip_focus = "tabs"
                else:
                    game.ui_mode = None
            elif game.ui_mode == "team_equip":
                focus = getattr(game, "team_equip_focus", "tabs")
                if focus == "items":
                    game.team_equip_focus = "slots"
                elif focus == "slots":
                    game.team_equip_focus = "tabs"
                else:
                    game.ui_mode = "team"
            elif game.ui_mode == "equip_category":
                game.ui_mode = None
            elif game.ui_mode == "team_equip_category":
                game.ui_mode = "team"
            elif game.ui_mode == "team_equip_root":
                game.ui_mode = "team"
            elif game.ui_mode == "level_skipper":
                game.ui_mode = "item"
            else:
                game.ui_mode = None
        elif event.key == pygame.K_RETURN:
            if game.ui_mode == "save":
                game.save_game()
            elif game.ui_mode == "equip":
                focus = getattr(game, "equip_focus", "tabs")
                if focus == "tabs":
                    if game.equip_root_selected == 0:
                        game.equip_focus = "slots"
                    elif game.equip_root_selected == 1:
                        game.equip_best()
                    elif game.equip_root_selected == 2:
                        game.unequip_all()
                elif focus == "slots":
                    game.equip_focus = "items"
                    game.equip_selected = 0
                else:
                    game.equip_selected_item()
            elif game.ui_mode == "team_equip":
                focus = getattr(game, "team_equip_focus", "tabs")
                if focus == "tabs":
                    if game.team_equip_root_selected == 0:
                        game.team_equip_focus = "slots"
                    elif game.team_equip_root_selected == 1:
                        game.team_equip_best()
                    elif game.team_equip_root_selected == 2:
                        game.team_unequip_all()
                elif focus == "slots":
                    game.team_equip_focus = "items"
                    game.team_equip_item_selected = 0
                else:
                    game.team_equip_selected_item()
            elif game.ui_mode == "equip_category":
                cats = game.get_equip_categories()
                game.equip_category = cats[game.equip_category_selected % len(cats)]
                game.open_equip_items()
            elif game.ui_mode == "team_equip_category":
                cats = game.get_team_equip_categories()
                game.team_equip_category = cats[game.team_equip_slot_selected % len(cats)]
                game.open_team_equip_items()
            elif game.ui_mode == "equip_root":
                if game.equip_root_selected == 0:
                    game.ui_mode = "equip_category"
                elif game.equip_root_selected == 1:
                    game.equip_best()
                elif game.equip_root_selected == 2:
                    game.unequip_all()
            elif game.ui_mode == "team_equip_root":
                if game.team_equip_root_selected == 0:
                    game.ui_mode = "team_equip_category"
                elif game.team_equip_root_selected == 1:
                    game.team_equip_best()
                elif game.team_equip_root_selected == 2:
                    game.team_unequip_all()
            elif game.ui_mode == "item":
                game.use_item()
            elif game.ui_mode == "objective":
                if hasattr(game, "set_tracked_selected_mission"):
                    game.set_tracked_selected_mission()
            elif game.ui_mode == "hotbar":
                if game.hotbar_mode == "item":
                    items = game.get_item_list()
                    if items:
                        item = items[game.hotbar_list_selected % len(items)]
                        game.item_hotbar_slots[game.hotbar_slot_selected] = item
                else:
                    if game.spells:
                        sp = game.spells[game.hotbar_list_selected % len(game.spells)]
                        game.magic_hotbar_slots[game.hotbar_slot_selected] = sp.get("name")
            elif game.ui_mode == "skill_tree":
                game.unlock_selected_skill()
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
        ctx["esc_selected"] = (ctx["esc_selected"] - 1) % 9
    elif event.key == pygame.K_DOWN:
        ctx["esc_selected"] = (ctx["esc_selected"] + 1) % 9
    elif event.key == pygame.K_ESCAPE:
        ctx["state"] = "game"
    elif event.key == pygame.K_RETURN:
        if ctx["esc_selected"] == 0:
            game.ui_mode = "item"
        elif ctx["esc_selected"] == 1:
            game.ui_mode = "hotbar"
            game.hotbar_stage = "grid"
            game.hotbar_slot_selected = 0
            game.hotbar_list_selected = 0
        elif ctx["esc_selected"] == 2:
            game.open_equip()
        elif ctx["esc_selected"] == 3:
            game.ui_mode = "team"
        elif ctx["esc_selected"] == 4:
            ctx["tutorial_lines"] = _build_tutorial_lines(game.lang)
            ctx["tutorial_idx"] = 0
            game.ui_mode = None
            ctx["state"] = "tutorial"
        elif ctx["esc_selected"] == 5:
            game.ui_mode = "objective"
            game.objective_selected = 0
        elif ctx["esc_selected"] == 6:
            game.ui_mode = "skill_tree"
        elif ctx["esc_selected"] == 7:
            game.open_save()
        elif ctx["esc_selected"] == 8:
            game.open_leave_confirm()


def _handle_game_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode == "death_menu":
        if game.death_no_save_notice:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                game.request_quit = True
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            game.death_menu_selected = max(0, game.death_menu_selected - 1)
            return
        if event.key in (pygame.K_DOWN, pygame.K_s):
            game.death_menu_selected = min(1, game.death_menu_selected + 1)
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            game.handle_death_menu_confirm()
            return
        return
    if game.ui_mode == "level_stat_choice":
        options = game.get_level_stat_options() if hasattr(game, "get_level_stat_options") else []
        if not options:
            game.ui_mode = None
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            game.level_stat_selected = (game.level_stat_selected - 1) % len(options)
            return
        if event.key in (pygame.K_DOWN, pygame.K_s):
            game.level_stat_selected = (game.level_stat_selected + 1) % len(options)
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            game.choose_level_stat(game.level_stat_selected)
            return
        return
    if event.key == pygame.K_i and game.ui_mode is None:
        game.active_hotbar = "magic" if game.active_hotbar == "item" else "item"
    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0):
        if game.ui_mode is None:
            slot = 9 if event.key == pygame.K_0 else (event.key - pygame.K_1)
            if game.active_hotbar == "item":
                name = game.item_hotbar_slots[slot]
                if name:
                    game.use_item_by_name(name)
            else:
                name = game.magic_hotbar_slots[slot]
                if name:
                    game.cast_spell_by_name(name)
        return
    if game.ui_mode == "interact_pick":
        if event.key in (pygame.K_UP, pygame.K_w):
            if game.interact_candidates:
                game.interact_selected = (game.interact_selected - 1) % len(game.interact_candidates)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            if game.interact_candidates:
                game.interact_selected = (game.interact_selected + 1) % len(game.interact_candidates)
        elif event.key == pygame.K_RETURN:
            game.confirm_interact_choice()
        elif event.key == pygame.K_ESCAPE:
            game.cancel_interact_choice()
        return
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
    if game.ui_mode == "hotbar":
        if event.key == pygame.K_i:
            game.hotbar_mode = "magic" if game.hotbar_mode == "item" else "item"
            game.hotbar_type_selected = 0 if game.hotbar_mode == "item" else 1
            game.hotbar_list_selected = 0
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if game.hotbar_mode == "item":
                game.item_hotbar_slots[game.hotbar_slot_selected] = None
            else:
                game.magic_hotbar_slots[game.hotbar_slot_selected] = None
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
    elif state == "tutorial":
        _handle_tutorial_mouse(ctx)
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
    now = pygame.time.get_ticks() / 1000.0
    ctx["press_time"][key] = now
    moved = False
    held = ctx["held_keys"]
    # Allow instant diagonal step when two directions are held.
    if key in ("w", "s"):
        side_dx = (1 if held["d"] else 0) - (1 if held["a"] else 0)
        if side_dx != 0:
            moved = ctx["game"].request_player_move(side_dx, dy)
    elif key in ("a", "d"):
        side_dy = (1 if held["s"] else 0) - (1 if held["w"] else 0)
        if side_dy != 0:
            moved = ctx["game"].request_player_move(dx, side_dy)
    if not moved:
        moved = ctx["game"].request_player_move(dx, dy)
    if moved:
        ctx["last_move_time"] = now


def _handle_held_movement(ctx):
    now = pygame.time.get_ticks() / 1000.0
    if now - ctx["last_move_time"] < ctx["move_interval"]:
        return
    if ctx["state"] == "esc_menu":
        game = ctx["game"]
        if not game.ui_mode:
            return
        hold_delay = ctx.get("hold_repeat_delay", 0.08)
        up = ctx["held_keys"]["w"] and now - ctx["press_time"]["w"] >= hold_delay
        down = ctx["held_keys"]["s"] and now - ctx["press_time"]["s"] >= hold_delay
        if not up and not down:
            return
        delta = -1 if up else 1
        if game.ui_mode == "item":
            items = game.get_item_list()
            if items:
                idx = game.item_selected % len(items)
                if delta < 0:
                    idx = max(0, idx - 2)
                else:
                    idx = min(len(items) - 1, idx + 2)
                game.item_selected = idx
        elif game.ui_mode == "hotbar":
            stage = getattr(game, "hotbar_stage", "type")
            if stage == "type":
                game.hotbar_type_selected = 1 - int(getattr(game, "hotbar_type_selected", 0))
            elif stage == "slot":
                if delta < 0:
                    game.hotbar_slot_selected = max(0, game.hotbar_slot_selected - 1)
                else:
                    game.hotbar_slot_selected = min(9, game.hotbar_slot_selected + 1)
            else:
                if game.hotbar_mode == "item":
                    items = game.get_item_list()
                    if items:
                        idx = game.hotbar_list_selected % len(items)
                        idx = max(0, idx - 1) if delta < 0 else min(len(items) - 1, idx + 1)
                        game.hotbar_list_selected = idx
                else:
                    if game.spells:
                        idx = game.hotbar_list_selected % len(game.spells)
                        idx = max(0, idx - 1) if delta < 0 else min(len(game.spells) - 1, idx + 1)
                        game.hotbar_list_selected = idx
        elif game.ui_mode == "skill_tree":
            game.skill_tree_selected = max(0, game.skill_tree_selected + delta) if delta < 0 else game.skill_tree_selected + 1
        elif game.ui_mode == "leave_confirm":
            if delta < 0:
                game.leave_selected = max(0, game.leave_selected - 1)
            else:
                game.leave_selected = min(2, game.leave_selected + 1)
        elif game.ui_mode == "save":
            game.save_selected = (game.save_selected + delta) % 3
        ctx["last_move_time"] = now
        return
    if ctx["state"] != "game":
        return
    game = ctx["game"]
    if game.ui_mode:
        return
    hold_delay = ctx.get("hold_repeat_delay", 0.08)
    up = ctx["held_keys"]["w"] and now - ctx["press_time"]["w"] >= hold_delay
    down = ctx["held_keys"]["s"] and now - ctx["press_time"]["s"] >= hold_delay
    left = ctx["held_keys"]["a"] and now - ctx["press_time"]["a"] >= hold_delay
    right = ctx["held_keys"]["d"] and now - ctx["press_time"]["d"] >= hold_delay
    dx = (1 if right else 0) - (1 if left else 0)
    dy = (1 if down else 0) - (1 if up else 0)
    if dx != 0 or dy != 0:
        moved = game.request_player_move(dx, dy)
        # QOL: if diagonal blocked, try axis slide.
        if not moved and dx != 0 and dy != 0:
            moved = game.request_player_move(dx, 0)
            if not moved:
                moved = game.request_player_move(0, dy)
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
        if 0 <= idx < 9:
            ctx["esc_selected"] = idx
            if idx == 0:
                game.ui_mode = "item"
            elif idx == 1:
                game.ui_mode = "hotbar"
                game.hotbar_stage = "grid"
                game.hotbar_slot_selected = 0
                game.hotbar_list_selected = 0
            elif idx == 2:
                game.open_equip()
            elif idx == 3:
                game.ui_mode = "team"
            elif idx == 4:
                ctx["tutorial_lines"] = _build_tutorial_lines(game.lang)
                ctx["tutorial_idx"] = 0
                game.ui_mode = None
                ctx["state"] = "tutorial"
            elif idx == 5:
                game.ui_mode = "objective"
            elif idx == 6:
                game.ui_mode = "skill_tree"
            elif idx == 7:
                game.open_save()
            elif idx == 8:
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
            tabs_y = panel.y + 48
            tab_w = (panel.width - 40) // 3
            tabs = []
            for i in range(3):
                rx = panel.x + 16 + i * (tab_w + 4)
                tabs.append(pygame.Rect(rx, tabs_y - 2, tab_w, font.get_height() + 8))
            for i, r in enumerate(tabs):
                if r.collidepoint(mx, my):
                    game.equip_root_selected = i
                    if i == 0:
                        game.equip_focus = "items"
                    elif i == 1:
                        game.equip_best()
                    else:
                        game.unequip_all()
                    return

            cats = game.get_equip_categories()
            non_rings = [c for c in cats if not c.startswith("ring")]
            rings = sorted([c for c in cats if c.startswith("ring")], key=lambda s: int(s[4:]) if s[4:].isdigit() else 99)
            cats = non_rings + rings
            if not cats:
                return
            pair_w = (panel.width - 40) // 2
            pair_gap = 8
            slot_w = max(60, int(pair_w * 0.35))
            val_w = pair_w - slot_w - pair_gap
            row_h = font.get_height() + 8
            cat_rows = (len(cats) + 1) // 2
            cats_y = tabs_y + font.get_height() + 14

            for r in range(cat_rows):
                for c in range(2):
                    idx = r * 2 + c
                    if idx >= len(cats):
                        continue
                    base_x = panel.x + 16 + c * (pair_w + 8)
                    ry = cats_y + r * row_h
                    slot_rect = pygame.Rect(base_x, ry - 2, slot_w, font.get_height() + 6)
                    val_rect = pygame.Rect(base_x + slot_w + pair_gap, ry - 2, val_w, font.get_height() + 6)
                    if slot_rect.collidepoint(mx, my) or val_rect.collidepoint(mx, my):
                        game.equip_category_selected = idx
                        game.equip_category = cats[idx]
                        game.equip_selected = 0
                        game.equip_focus = "items"
                        return

            game.equip_category_selected = game.equip_category_selected % len(cats)
            game.equip_category = cats[game.equip_category_selected]
            equipables = game.get_equipable_items()
            slot_key = "ring" if game.equip_category.startswith("ring") else game.equip_category
            filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
            if not filtered:
                return
            list_y = cats_y + cat_rows * row_h + 10
            col_w = (panel.width - 40) // 2
            row_h2 = font.get_height() + 8
            selected = game.equip_selected % len(filtered)
            max_rows = max(1, (panel.bottom - list_y - 10) // row_h2)
            per_page = max_rows * 2
            page = selected // per_page
            start = page * per_page
            end = min(len(filtered), start + per_page)
            for i in range(start, end):
                li = i - start
                col = li % 2
                row = li // 2
                rx = panel.x + 16 + col * (col_w + 8)
                ry = list_y + row * row_h2
                rect = pygame.Rect(rx, ry - 2, col_w, font.get_height() + 6)
                if rect.collidepoint(mx, my):
                    game.equip_selected = i
                    game.equip_focus = "items"
                    game.equip_selected_item()
                    return
        elif game.ui_mode == "item":
            cats = game.get_item_categories() if hasattr(game, "get_item_categories") else ["item", "gift", "equipment", "special"]
            tab_h = font.get_height() + 8
            tab_gap = 6
            tab_w = max(80, (panel.width - 32 - (len(cats) - 1) * tab_gap) // max(1, len(cats)))
            tab_y = panel.y + 48
            for i, cat in enumerate(cats):
                rx = panel.x + 16 + i * (tab_w + tab_gap)
                rect = pygame.Rect(rx, tab_y - 2, tab_w, tab_h)
                if rect.collidepoint(mx, my):
                    game.item_category = cat
                    game.item_selected = 0
                    return

            items = game.get_item_list()
            row_h = font.get_height() + 8
            list_start_y = tab_y + tab_h + 10
            max_rows = max(1, (panel.bottom - list_start_y - 10) // row_h)
            col_w = (panel.width - 40) // 2
            selected = game.item_selected % len(items) if items else 0
            per_page = max_rows * 2
            page = selected // per_page if per_page > 0 else 0
            start = page * per_page
            end = min(len(items), start + per_page)
            for i in range(start, end):
                li = i - start
                row = li // 2
                col = li % 2
                rx = panel.x + 16 + col * (col_w + 8)
                ry = list_start_y + row * row_h
                rect = pygame.Rect(rx, ry - 2, col_w, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.item_selected = i
                    game.use_item()
                    if game.request_close_esc_menu:
                        game.request_close_esc_menu = False
                        game.ui_mode = None
                        ctx["state"] = "game"
                    break
        elif game.ui_mode == "hotbar":
            # minimal mouse support: click top half selects slot, bottom half selects source and assigns.
            mode = game.hotbar_mode
            tab_y = panel.y + 48
            tab_w = (panel.width - 36) // 2
            item_tab = pygame.Rect(panel.x + 16, tab_y - 2, tab_w, font.get_height() + 8)
            magic_tab = pygame.Rect(panel.x + 20 + tab_w, tab_y - 2, tab_w, font.get_height() + 8)
            if item_tab.collidepoint(mx, my):
                game.hotbar_mode = "item"
                return
            if magic_tab.collidepoint(mx, my):
                game.hotbar_mode = "magic"
                return
        elif game.ui_mode == "skill_tree":
            nodes = game.get_skill_tree_nodes()
            for i, _ in enumerate(nodes):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.skill_tree_selected = i
                    game.unlock_selected_skill()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "team":
            members = game.get_team_member_ids() if hasattr(game, "get_team_member_ids") else []
            for i, _ in enumerate(members):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 6)
                if rect.collidepoint(mx, my):
                    game.team_selected = i
                    game.open_team_equip(i)
                    break
                y += font.get_height() + 8
        elif game.ui_mode == "team_equip_root":
            for i in range(3):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.team_equip_root_selected = i
                    if i == 0:
                        game.ui_mode = "team_equip_category"
                    elif i == 1:
                        game.team_equip_best()
                    else:
                        game.team_unequip_all()
                    return
                y += font.get_height() + 6
        elif game.ui_mode == "team_equip_category":
            cats = game.get_team_equip_categories()
            for i in range(len(cats)):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.team_equip_slot_selected = i
                    game.team_equip_category = cats[i]
                    game.open_team_equip_items()
                    return
                y += font.get_height() + 6
        elif game.ui_mode == "team_equip":
            tabs_y = panel.y + 48 + font.get_height() + 10
            tab_w = (panel.width - 40) // 3
            tabs = []
            for i in range(3):
                rx = panel.x + 16 + i * (tab_w + 4)
                tabs.append(pygame.Rect(rx, tabs_y - 2, tab_w, font.get_height() + 8))
            for i, r in enumerate(tabs):
                if r.collidepoint(mx, my):
                    game.team_equip_root_selected = i
                    if i == 0:
                        game.team_equip_focus = "slots"
                    elif i == 1:
                        game.team_equip_best()
                    else:
                        game.team_unequip_all()
                    return
            cats = game.get_team_equip_categories()
            if not cats:
                return
            pair_w = (panel.width - 40) // 2
            pair_gap = 8
            slot_w = max(60, int(pair_w * 0.35))
            val_w = pair_w - slot_w - pair_gap
            row_h = font.get_height() + 8
            cat_rows = (len(cats) + 1) // 2
            cats_y = tabs_y + font.get_height() + 14

            for r in range(cat_rows):
                for c in range(2):
                    idx = r * 2 + c
                    if idx >= len(cats):
                        continue
                    base_x = panel.x + 16 + c * (pair_w + 8)
                    ry = cats_y + r * row_h
                    slot_rect = pygame.Rect(base_x, ry - 2, slot_w, font.get_height() + 6)
                    val_rect = pygame.Rect(base_x + slot_w + pair_gap, ry - 2, val_w, font.get_height() + 6)
                    if slot_rect.collidepoint(mx, my) or val_rect.collidepoint(mx, my):
                        game.team_equip_slot_selected = idx
                        game.team_equip_category = cats[idx]
                        game.team_equip_item_selected = 0
                        game.team_equip_focus = "items"
                        return

            game.team_equip_slot_selected = game.team_equip_slot_selected % len(cats)
            game.team_equip_category = cats[game.team_equip_slot_selected]
            equipables = game.get_team_equipable_items()
            slot_key = "ring" if game.team_equip_category.startswith("ring") else game.team_equip_category
            filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
            if not filtered:
                return
            list_y = cats_y + cat_rows * row_h + 10
            col_w = (panel.width - 40) // 2
            row_h2 = font.get_height() + 8
            selected = game.team_equip_item_selected % len(filtered)
            max_rows = max(1, (panel.bottom - list_y - 10) // row_h2)
            per_page = max_rows * 2
            page = selected // per_page
            start = page * per_page
            end = min(len(filtered), start + per_page)
            for i in range(start, end):
                li = i - start
                col = li % 2
                row = li // 2
                rx = panel.x + 16 + col * (col_w + 8)
                ry = list_y + row * row_h2
                rect = pygame.Rect(rx, ry - 2, col_w, font.get_height() + 6)
                if rect.collidepoint(mx, my):
                    game.team_equip_item_selected = i
                    game.team_equip_focus = "items"
                    game.team_equip_selected_item()
                    return
        elif game.ui_mode == "leave_confirm":
            y = panel.y + 48 + font.get_height() + 10
            options = ["starter menu", "leave game", "go back"]
            for i, _ in enumerate(options):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.leave_selected = i
                    game.handle_leave_confirm()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "objective":
            y = panel.y + 48
            # Skip default objective lines area, click only on mission tracking list.
            y += (font.get_height() + 6) * len(game.get_objective_lines())
            y += 8 + font.get_height() + 6
            missions = game.get_trackable_missions() if hasattr(game, "get_trackable_missions") else []
            for i, _ in enumerate(missions):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 6)
                if rect.collidepoint(mx, my):
                    game.objective_selected = i
                    if hasattr(game, "set_tracked_selected_mission"):
                        game.set_tracked_selected_mission()
                    break
                y += font.get_height() + 8


def _handle_mouse_game(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    game = ctx["game"]
    if game.ui_mode == "death_menu":
        menu_w = min(680, screen.get_width() - 120)
        menu_h = 240
        panel = pygame.Rect((screen.get_width() - menu_w) // 2, (screen.get_height() - menu_h) // 2, menu_w, menu_h)
        if game.death_no_save_notice:
            ok_rect = pygame.Rect(panel.x + panel.width // 2 - 90, panel.bottom - 54, 180, 34)
            if ok_rect.collidepoint(mx, my):
                game.request_quit = True
            return
        row_h = 36
        start_y = panel.y + 96
        for i in range(2):
            rect = pygame.Rect(panel.x + 24, start_y + i * (row_h + 10), panel.width - 48, row_h)
            if rect.collidepoint(mx, my):
                game.death_menu_selected = i
                game.handle_death_menu_confirm()
                return
        return
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


def _handle_tutorial_mouse(ctx):
    ctx["tutorial_idx"] = ctx.get("tutorial_idx", 0) + 1
    if ctx["tutorial_idx"] >= len(ctx.get("tutorial_lines", [])):
        ctx["state"] = "game"


def _draw_name_input(ctx):
    screen = ctx["screen"]
    screen.fill((5, 10, 18))
    title_font = _get_font(42, bold=True)
    body_font = _get_font(28)
    hint_font = _get_font(20)
    title = title_font.render("新遊戲", True, (220, 240, 255))
    prompt = body_font.render("請輸入角色名稱（最多 20 字）", True, (185, 220, 245))
    name = ctx.get("new_game_name", "")
    box_w, box_h = screen.get_width() - 140, 58
    box_x = (screen.get_width() - box_w) // 2
    box_y = screen.get_height() // 2 - box_h // 2
    pygame.draw.rect(screen, (16, 30, 46), (box_x, box_y, box_w, box_h), border_radius=8)
    pygame.draw.rect(screen, (190, 230, 255), (box_x, box_y, box_w, box_h), 2, border_radius=8)
    display_name = name if name else "Doctor"
    name_surf = body_font.render(display_name, True, (255, 255, 255))
    hint = hint_font.render("Enter 確認 / Esc 取消", True, (150, 180, 205))
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
    hint_text = "Enter 繼續" if ctx["game"].lang == "zh" else "Press Enter to continue"
    hint = hint_font.render(hint_text, True, (165, 185, 205))
    screen.blit(hint, (panel.right - hint.get_width() - 16, panel.bottom - hint.get_height() - 10))


def _draw_tutorial(ctx):
    screen = ctx["screen"]
    screen.fill((4, 9, 16))
    title_font = _get_font(28, bold=True)
    body_font = _get_font(24)
    hint_font = _get_font(18)

    lines = ctx.get("tutorial_lines", [])
    idx = ctx.get("tutorial_idx", 0)
    total = max(1, len(lines))
    text = lines[idx] if 0 <= idx < len(lines) else ""

    panel = pygame.Rect(60, 90, screen.get_width() - 120, screen.get_height() - 180)
    pygame.draw.rect(screen, (12, 22, 35), panel, border_radius=10)
    pygame.draw.rect(screen, (130, 180, 220), panel, 2, border_radius=10)

    title_text = tr(ctx["game"].lang, "tutorial.title")
    step_text = tr(ctx["game"].lang, "tutorial.progress", now=idx + 1, total=total)
    title = title_font.render(title_text, True, (230, 245, 255))
    step = hint_font.render(step_text, True, (170, 205, 230))
    screen.blit(title, (panel.x + 20, panel.y + 16))
    screen.blit(step, (panel.right - step.get_width() - 20, panel.y + 20))

    wrapped = _wrap_text(body_font, text, panel.width - 40)
    y = panel.y + 72
    for row in wrapped:
        surf = body_font.render(row, True, (230, 238, 248))
        screen.blit(surf, (panel.x + 20, y))
        y += body_font.get_height() + 10

    hint_text = tr(ctx["game"].lang, "tutorial.hint")
    hint = hint_font.render(hint_text, True, (165, 190, 210))
    screen.blit(hint, (panel.right - hint.get_width() - 20, panel.bottom - hint.get_height() - 16))


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
    elif ctx["state"] == "tutorial":
        _draw_tutorial(ctx)
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
        # Keep dialog text readable: hide bottom status/hotbar while dialog is open.
        if getattr(ctx["game"], "ui_mode", None) != "dialog":
            draw_player_ui(ctx["game"], ctx["screen"])
    if ctx["game"].request_main_menu:
        ctx["game"].request_main_menu = False
        ctx["game"].ui_mode = None
        ctx["state"] = "main_menu"
    if ctx["game"].request_quit:
        ctx["running"] = False
    pygame.display.flip()
