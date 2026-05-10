import pygame


def handle_game_key(ctx, event, press_move_fn, set_always_on_top_fn, tile_size, viewport):
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
