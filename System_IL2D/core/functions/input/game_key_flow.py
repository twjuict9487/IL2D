import time

import pygame

from ..support.i18n import tr


def _set_mission_feedback(game, reason_key, mission_id=None):
    reason_key = str(reason_key or "").strip()
    if not reason_key:
        return
    text = tr(getattr(game, "lang", "en"), reason_key)
    if not text or text == reason_key:
        text = reason_key.replace(".", " ").title()
    payload = {
        "text": text,
        "reason": reason_key,
        "mission_id": mission_id,
        "created": time.time(),
        "duration": 2.5,
    }
    game.mission_feedback = payload
    if hasattr(game, "banner"):
        game.banner = {
            "text": text,
            "created": payload["created"],
            "duration": payload["duration"],
        }
    if hasattr(game, "push_message"):
        try:
            game.push_message(text)
        except Exception:
            pass


def handle_game_key(ctx, event, press_move_fn, set_always_on_top_fn, tile_size, viewport):
    game = ctx["game"]
    def _settle_blackjack_if_needed():
        st_local = getattr(game, "blackjack_ui_state", {}) or {}
        if not bool(st_local.get("finished", False)):
            return
        if bool(getattr(game, "blackjack_round_settled", False)):
            return
        bet_local = int(st_local.get("bet", 0) or 0)
        payout_local = int(st_local.get("payout", 0) or 0)
        game.money = max(0, int(getattr(game, "money", 0)) - bet_local + payout_local)
        game.blackjack_round_settled = True
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
                if hasattr(game, "interact_scroll"):
                    game.interact_scroll = max(0, game.interact_scroll - 1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            if game.interact_candidates:
                game.interact_selected = (game.interact_selected + 1) % len(game.interact_candidates)
                if hasattr(game, "interact_scroll"):
                    game.interact_scroll = min(game.interact_scroll + 1, max(0, len(game.interact_candidates) - 1))
        elif event.key in (pygame.K_PAGEUP, pygame.K_HOME):
            if hasattr(game, "interact_scroll"):
                game.interact_scroll = max(0, int(getattr(game, "interact_scroll", 0)) - 3)
        elif event.key in (pygame.K_PAGEDOWN, pygame.K_END):
            if hasattr(game, "interact_scroll"):
                game.interact_scroll = min(max(0, len(game.interact_candidates) - 1), int(getattr(game, "interact_scroll", 0)) + 3)
        elif event.key == pygame.K_RETURN:
            game.confirm_interact_choice()
        elif event.key == pygame.K_ESCAPE:
            game.cancel_interact_choice()
        return
    if game.ui_mode == "dialog":
        if event.key == pygame.K_UP:
            game.dialog_selected = max(0, game.dialog_selected - 1)
            if hasattr(game, "dialog_scroll"):
                game.dialog_scroll = max(0, int(getattr(game, "dialog_scroll", 0)) - 1)
        elif event.key == pygame.K_DOWN:
            game.dialog_selected = game.dialog_selected + 1
            if hasattr(game, "dialog_scroll"):
                game.dialog_scroll = max(0, int(getattr(game, "dialog_scroll", 0)) + 1)
        elif event.key == pygame.K_PAGEUP:
            if hasattr(game, "dialog_scroll"):
                game.dialog_scroll = max(0, int(getattr(game, "dialog_scroll", 0)) - 3)
        elif event.key == pygame.K_PAGEDOWN:
            if hasattr(game, "dialog_scroll"):
                game.dialog_scroll = max(0, int(getattr(game, "dialog_scroll", 0)) + 3)
        elif event.key == pygame.K_RETURN:
            game.dialog_choose()
        elif event.key == pygame.K_ESCAPE:
            if hasattr(game, "close_dialog"):
                game.close_dialog()
            else:
                game.ui_mode = None
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
    if game.ui_mode == "blackjack_bet":
        if event.key == pygame.K_ESCAPE:
            game.ui_mode = None
            return
        if event.key == pygame.K_BACKSPACE:
            game.blackjack_bet_input = getattr(game, "blackjack_bet_input", "")[:-1]
            game.blackjack_bet_error = ""
            return
        if event.key == pygame.K_RETURN:
            txt = (getattr(game, "blackjack_bet_input", "") or "").strip()
            if not txt.isdigit():
                game.blackjack_bet_error = "invalid"
                return
            amount = int(txt)
            money = int(getattr(game, "money", 0))
            if amount <= 0 or amount > money:
                game.blackjack_bet_error = "range"
                return
            game.blackjack_session_bank = amount
            game.blackjack_ui_state = game.blackjack_start(amount)
            game.blackjack_ui_selected = 0
            game.blackjack_round_settled = False
            game.blackjack_bet_error = ""
            game.ui_mode = "blackjack"
            return
        if event.unicode and event.unicode.isdigit():
            raw = getattr(game, "blackjack_bet_input", "")
            if len(raw) < 9:
                game.blackjack_bet_input = raw + event.unicode
                game.blackjack_bet_error = ""
            return
        return
    if game.ui_mode == "blackjack":
        st = getattr(game, "blackjack_ui_state", {}) or {}
        finished = bool(st.get("finished", False))
        _settle_blackjack_if_needed()
        option_count = 2 if finished else 3
        if event.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
            game.blackjack_ui_selected = (getattr(game, "blackjack_ui_selected", 0) - 1) % option_count
            return
        if event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
            game.blackjack_ui_selected = (getattr(game, "blackjack_ui_selected", 0) + 1) % option_count
            return
        if event.key == pygame.K_ESCAPE:
            game.ui_mode = None
            return
        if event.key == pygame.K_RETURN:
            sel = int(getattr(game, "blackjack_ui_selected", 0))
            if finished:
                if sel == 0 and hasattr(game, "blackjack_start"):
                    bet = int(st.get("bet", 10) or 10)
                    bet = min(max(1, bet), int(getattr(game, "money", 0)))
                    if bet <= 0:
                        game.ui_mode = None
                        return
                    game.blackjack_ui_state = game.blackjack_start(bet)
                    game.blackjack_ui_selected = 0
                    game.blackjack_round_settled = False
                else:
                    game.ui_mode = None
                return
            if sel == 0 and hasattr(game, "blackjack_hit"):
                game.blackjack_ui_state = game.blackjack_hit()
                game.blackjack_ui_selected = 0
                _settle_blackjack_if_needed()
                return
            if sel == 1 and hasattr(game, "blackjack_stand"):
                game.blackjack_ui_state = game.blackjack_stand()
                game.blackjack_ui_selected = 0
                _settle_blackjack_if_needed()
                return
            game.ui_mode = None
            return
        return
    if game.ui_mode == "mission_board":
        missions = game.get_mission_board_entries(getattr(game, "mission_board_giver", None)) if hasattr(game, "get_mission_board_entries") else []
        if event.key in (pygame.K_UP, pygame.K_w):
            if missions:
                game.mission_board_selected = max(0, game.mission_board_selected - 1)
                if hasattr(game, "mission_detail_scroll"):
                    game.mission_detail_scroll = 0
                if hasattr(game, "mission_board_scroll"):
                    game.mission_board_scroll = max(0, int(getattr(game, "mission_board_scroll", 0)) - 1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            if missions:
                game.mission_board_selected = min(len(missions) - 1, game.mission_board_selected + 1)
                if hasattr(game, "mission_detail_scroll"):
                    game.mission_detail_scroll = 0
                if hasattr(game, "mission_board_scroll"):
                    game.mission_board_scroll = min(max(0, len(missions) - 1), int(getattr(game, "mission_board_scroll", 0)) + 1)
        elif event.key in (pygame.K_PAGEUP, pygame.K_LEFT):
            if hasattr(game, "mission_detail_scroll"):
                game.mission_detail_scroll = max(0, int(getattr(game, "mission_detail_scroll", 0)) - 4)
        elif event.key in (pygame.K_PAGEDOWN, pygame.K_RIGHT):
            if hasattr(game, "mission_detail_scroll"):
                game.mission_detail_scroll = max(0, int(getattr(game, "mission_detail_scroll", 0)) + 4)
        elif event.key == pygame.K_RETURN:
            giver = getattr(game, "mission_board_giver", None)
            missions = game.get_mission_board_entries(giver) if giver and hasattr(game, "get_mission_board_entries") else []
            if missions:
                idx = max(0, min(len(missions) - 1, int(getattr(game, "mission_board_selected", 0))))
                row = missions[idx]
                status = row.get("status")
                if status == "available":
                    if hasattr(game, "accept_mission"):
                        game.accept_mission(row.get("id"))
                elif status == "ready":
                    if hasattr(game, "turn_in_mission"):
                        game.turn_in_mission(row.get("id"))
                elif status == "active":
                    game.tracked_mission = row.get("id")
                else:
                    giver = getattr(game, "mission_board_giver", None)
                    reason = ""
                    try:
                        from ..gameplay import missions as game_missions
                        reason = game_missions.mission_acceptance_reason(game, row.get("id"), giver_id=giver)
                    except Exception:
                        reason = str(status or "mission.locked")
                    _set_mission_feedback(game, reason or "mission.locked", mission_id=row.get("id"))
        elif event.key == pygame.K_ESCAPE:
            if hasattr(game, "close_mission_board"):
                game.close_mission_board()
            else:
                game.close_dialog()
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
        win_w = tile_size * viewport
        win_h = tile_size * (viewport + 1)
        if ctx["fullscreen"]:
            ctx["screen"] = pygame.display.set_mode((win_w, win_h), pygame.FULLSCREEN)
        else:
            ctx["screen"] = pygame.display.set_mode((win_w, win_h))
        set_always_on_top_fn()
    if event.key == pygame.K_w:
        press_move_fn(ctx, "w", 0, -1)
    elif event.key == pygame.K_s:
        press_move_fn(ctx, "s", 0, 1)
    elif event.key == pygame.K_a:
        press_move_fn(ctx, "a", -1, 0)
    elif event.key == pygame.K_d:
        press_move_fn(ctx, "d", 1, 0)
    elif event.key == pygame.K_e:
        game.player_interact()
