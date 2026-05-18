import os
import pygame
from core.functions.support.utils import CONFIG_FILE, SAVE_DIR, load_json
from core.functions.support.asset_resolver import prime_asset_index
from core.functions.support.i18n import tr
from core.functions.gameplay.game import Game
from core.functions.rendering.draw import draw, draw_main_menu, draw_esc_menu, draw_player_ui, draw_settings_menu, draw_dev_menu, draw_continue_menu, TILE_SIZE, VIEWPORT, FPS
from core.functions.world.map import npc_data
from core.functions.ui.tutorial_flow import (
    build_tutorial_lines as _ui_build_tutorial_lines,
    handle_tutorial_key as _ui_handle_tutorial_key,
    handle_tutorial_mouse as _ui_handle_tutorial_mouse,
)
from core.functions.ui.continue_flow import (
    get_save_slots as _ui_get_save_slots,
    handle_continue_menu_key as _ui_handle_continue_menu_key,
    handle_mouse_continue_menu as _ui_handle_mouse_continue_menu,
)
from core.functions.ui.main_menu_flow import (
    handle_main_menu_key as _ui_handle_main_menu_key,
    handle_mouse_main_menu as _ui_handle_mouse_main_menu,
)
from core.functions.ui.settings_flow import (
    handle_settings_key as _ui_handle_settings_key,
    handle_mouse_settings as _ui_handle_mouse_settings,
)
from core.functions.ui.name_input_flow import (
    open_new_game_name_input as _ui_open_new_game_name_input,
    handle_name_input_key as _ui_handle_name_input_key,
    handle_text_input as _ui_handle_text_input,
)
from core.functions.ui.dev_menu_flow import handle_dev_menu_key as _ui_handle_dev_menu_key
from core.functions.input.held_movement import (
    update_held_keys as _input_update_held_keys,
    press_move as _input_press_move,
    handle_held_movement as _input_handle_held_movement,
)
from core.functions.input.game_key_flow import handle_game_key as _input_handle_game_key
from core.mod_loader import load_mods as _load_mods, invoke_hooks as _invoke_mod_hooks

_UI_IMG_CACHE = {}
_TUTORIAL_STATE_FILE = os.path.join(SAVE_DIR, "tutorial_state.json")


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


def _has_seen_start_tutorial():
    try:
        if not os.path.isfile(_TUTORIAL_STATE_FILE):
            return False
        data = load_json(_TUTORIAL_STATE_FILE)
        return bool(data.get("start_tutorial_seen", False)) if isinstance(data, dict) else False
    except Exception:
        return False


def _mark_start_tutorial_seen():
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(_TUTORIAL_STATE_FILE, "w", encoding="utf-8") as f:
            import json
            json.dump({"start_tutorial_seen": True}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def init_context():
    pygame.init()
    system_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    prime_asset_index(system_root)
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
        "tutorial_return_state": "game",
        "tutorial_mode": "start",
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
        "world_tick_interval": 0.5,
        "world_tick_accum": 0.0,
        "loaded_mods": [],
        "mod_errors": [],
    }
    try:
        cfg = load_json(CONFIG_FILE)
        ctx["move_interval"] = cfg.get("move_interval", ctx["move_interval"])
        ctx["hold_repeat_delay"] = cfg.get("hold_repeat_delay", ctx["hold_repeat_delay"])
    except Exception:
        pass
    mods_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mods")
    _load_mods(ctx, mods_dir)
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
    _ui_handle_dev_menu_key(ctx, event)


def _handle_main_menu_key(ctx, event):
    _ui_handle_main_menu_key(ctx, event, _open_new_game_name_input, _get_save_slots)


def _get_save_slots():
    return _ui_get_save_slots()


def _open_new_game_name_input(ctx):
    _ui_open_new_game_name_input(ctx)


def _handle_name_input_key(ctx, event):
    _ui_handle_name_input_key(ctx, event, _has_seen_start_tutorial, _build_tutorial_lines)


def _handle_text_input(ctx, text):
    _ui_handle_text_input(ctx, text)


def _handle_cutscene_key(ctx, event):
    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
        ctx["cutscene_idx"] = ctx.get("cutscene_idx", 0) + 1
        if ctx["cutscene_idx"] >= len(ctx.get("cutscene_lines", [])):
            ctx["state"] = "game"


def _build_tutorial_lines(lang, mode="start"):
    return _ui_build_tutorial_lines(lang, mode=mode)


def _handle_tutorial_key(ctx, event):
    _ui_handle_tutorial_key(ctx, event, _mark_start_tutorial_seen)


def _handle_continue_menu_key(ctx, event):
    _ui_handle_continue_menu_key(ctx, event)


def _handle_settings_key(ctx, event):
    _ui_handle_settings_key(ctx, event)


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
                focus = getattr(game, "item_focus", "tabs")
                if focus == "tabs":
                    game.cycle_item_category(-1)
                else:
                    items = game.get_item_list()
                    if items:
                        idx = game.item_selected % len(items)
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            idx = max(0, idx - 1)
                        else:
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
                focus = getattr(game, "item_focus", "tabs")
                if focus == "tabs":
                    game.cycle_item_category(1)
                else:
                    items = game.get_item_list()
                    if items:
                        idx = game.item_selected % len(items)
                        if event.key in (pygame.K_RIGHT, pygame.K_d):
                            idx = min(len(items) - 1, idx + 1)
                        else:
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
            elif game.ui_mode == "item":
                if getattr(game, "item_focus", "tabs") == "items":
                    game.item_focus = "tabs"
                else:
                    game.ui_mode = None
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
                if getattr(game, "item_focus", "tabs") == "tabs":
                    game.item_focus = "items"
                    game.item_selected = 0
                else:
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
        ctx["esc_selected"] = (ctx["esc_selected"] - 1) % 10
    elif event.key == pygame.K_DOWN:
        ctx["esc_selected"] = (ctx["esc_selected"] + 1) % 10
    elif event.key == pygame.K_ESCAPE:
        ctx["state"] = "game"
    elif event.key == pygame.K_RETURN:
        if ctx["esc_selected"] == 0:
            game.ui_mode = "item"
            game.item_focus = "tabs"
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
            ctx["tutorial_mode"] = "manual"
            ctx["tutorial_lines"] = _build_tutorial_lines(game.lang, mode="manual")
            ctx["tutorial_idx"] = 0
            ctx["tutorial_return_state"] = "esc_menu"
            game.ui_mode = None
            ctx["state"] = "tutorial"
        elif ctx["esc_selected"] == 5:
            game.ui_mode = "map"
        elif ctx["esc_selected"] == 6:
            game.ui_mode = "objective"
            game.objective_selected = 0
        elif ctx["esc_selected"] == 7:
            game.ui_mode = "skill_tree"
        elif ctx["esc_selected"] == 8:
            game.open_save()
        elif ctx["esc_selected"] == 9:
            game.open_leave_confirm()


def _handle_game_key(ctx, event):
    if _invoke_mod_hooks(ctx, "on_game_key", event, stop_on_true=True):
        return
    _input_handle_game_key(ctx, event, _press_move, _set_always_on_top, TILE_SIZE, VIEWPORT)


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
    _input_update_held_keys(ctx, event, is_down)


def _press_move(ctx, key, dx, dy):
    _input_press_move(ctx, key, dx, dy)


def _handle_held_movement(ctx):
    _input_handle_held_movement(ctx)


def _handle_mouse_main_menu(ctx, pos):
    _ui_handle_mouse_main_menu(ctx, pos, _get_font, _open_new_game_name_input, _get_save_slots)


def _handle_mouse_settings(ctx, pos):
    _ui_handle_mouse_settings(ctx, pos)


def _handle_mouse_continue_menu(ctx, pos):
    _ui_handle_mouse_continue_menu(ctx, pos, _get_font)


def _handle_mouse_esc_menu(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    game = ctx["game"]
    menu_w = screen.get_width() // 4
    # Must match draw_esc_menu() left list metrics exactly.
    font = _get_font(18, bold=True)
    item_h = font.get_height() + 10
    if mx < menu_w:
        hit_idx = None
        for i in range(10):
            rect = pygame.Rect(12, 20 + i * item_h, menu_w - 24, item_h)
            if rect.collidepoint(mx, my):
                hit_idx = i
                break
        if hit_idx is not None:
            idx = hit_idx
            ctx["esc_selected"] = idx
            if idx == 0:
                game.ui_mode = "item"
                game.item_focus = "tabs"
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
                ctx["tutorial_mode"] = "manual"
                ctx["tutorial_lines"] = _build_tutorial_lines(game.lang, mode="manual")
                ctx["tutorial_idx"] = 0
                ctx["tutorial_return_state"] = "esc_menu"
                game.ui_mode = None
                ctx["state"] = "tutorial"
            elif idx == 5:
                game.ui_mode = "map"
            elif idx == 6:
                game.ui_mode = "objective"
            elif idx == 7:
                game.ui_mode = "skill_tree"
            elif idx == 8:
                game.open_save()
            elif idx == 9:
                game.open_leave_confirm()
            return
    else:
        panel = pygame.Rect(menu_w, 0, screen.get_width() - menu_w, screen.get_height())
        # Clicking inside right panel should enter current sublayer when not yet entered.
        if game.ui_mode is None and panel.collidepoint(mx, my):
            idx = int(ctx.get("esc_selected", 0))
            if idx == 0:
                game.ui_mode = "item"
                game.item_focus = "tabs"
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
                ctx["tutorial_mode"] = "manual"
                ctx["tutorial_lines"] = _build_tutorial_lines(game.lang, mode="manual")
                ctx["tutorial_idx"] = 0
                ctx["tutorial_return_state"] = "esc_menu"
                game.ui_mode = None
                ctx["state"] = "tutorial"
            elif idx == 5:
                game.ui_mode = "map"
            elif idx == 6:
                game.ui_mode = "objective"
            elif idx == 7:
                game.ui_mode = "skill_tree"
            elif idx == 8:
                game.open_save()
            elif idx == 9:
                game.open_leave_confirm()
            return
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
                    game.item_focus = "tabs"
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
                    game.item_focus = "items"
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
    _invoke_mod_hooks(ctx, "on_update", dt)
    if ctx["state"] == "game" and getattr(game, 'death_timer', None) is not None:
        game.death_timer -= dt
        if game.death_timer <= 0:
            pygame.quit()
            ctx["running"] = False
            return
    if ctx["state"] == "game" and getattr(game, 'death_timer', None) is None:
        ctx["world_tick_accum"] = float(ctx.get("world_tick_accum", 0.0)) + float(dt)
        tick_interval = float(ctx.get("world_tick_interval", 0.5))
        max_step = 4
        step_count = 0
        while ctx["world_tick_accum"] >= tick_interval and step_count < max_step:
            game.update(player_tick=True)
            ctx["world_tick_accum"] -= tick_interval
            step_count += 1
        game.update(player_tick=False)
        game.update_time(dt)


def _handle_tutorial_mouse(ctx):
    _ui_handle_tutorial_mouse(ctx, _mark_start_tutorial_seen)


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

    mode = ctx.get("tutorial_mode", "start")
    title_key = "manual.title" if mode == "manual" else "tutorial.title"
    progress_key = "manual.progress" if mode == "manual" else "tutorial.progress"
    hint_key = "manual.hint" if mode == "manual" else "tutorial.hint"
    title_text = tr(ctx["game"].lang, title_key)
    step_text = tr(ctx["game"].lang, progress_key, now=idx + 1, total=total)
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

    hint_text = tr(ctx["game"].lang, hint_key)
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
        _invoke_mod_hooks(ctx, "on_render", ctx["screen"])
    if ctx["game"].request_main_menu:
        ctx["game"].request_main_menu = False
        ctx["game"].ui_mode = None
        ctx["state"] = "main_menu"
    if ctx["game"].request_quit:
        ctx["running"] = False
    pygame.display.flip()
