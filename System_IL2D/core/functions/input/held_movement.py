import pygame


def update_held_keys(ctx, event, is_down):
    if event.key == pygame.K_w:
        ctx["held_keys"]["w"] = is_down
    elif event.key == pygame.K_s:
        ctx["held_keys"]["s"] = is_down
    elif event.key == pygame.K_a:
        ctx["held_keys"]["a"] = is_down
    elif event.key == pygame.K_d:
        ctx["held_keys"]["d"] = is_down


def press_move(ctx, key, dx, dy):
    now = pygame.time.get_ticks() / 1000.0
    ctx["press_time"][key] = now
    moved = False
    held = ctx["held_keys"]
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


def handle_held_movement(ctx):
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
                idx = max(0, idx - 2) if delta < 0 else min(len(items) - 1, idx + 2)
                game.item_selected = idx
        elif game.ui_mode == "hotbar":
            stage = getattr(game, "hotbar_stage", "type")
            if stage == "type":
                game.hotbar_type_selected = 1 - int(getattr(game, "hotbar_type_selected", 0))
            elif stage == "slot":
                game.hotbar_slot_selected = max(0, game.hotbar_slot_selected - 1) if delta < 0 else min(9, game.hotbar_slot_selected + 1)
            else:
                if game.hotbar_mode == "item":
                    items = game.get_item_list()
                    if items:
                        idx = game.hotbar_list_selected % len(items)
                        game.hotbar_list_selected = max(0, idx - 1) if delta < 0 else min(len(items) - 1, idx + 1)
                elif game.spells:
                    idx = game.hotbar_list_selected % len(game.spells)
                    game.hotbar_list_selected = max(0, idx - 1) if delta < 0 else min(len(game.spells) - 1, idx + 1)
        elif game.ui_mode == "skill_tree":
            game.skill_tree_selected = max(0, game.skill_tree_selected + delta) if delta < 0 else game.skill_tree_selected + 1
        elif game.ui_mode == "leave_confirm":
            game.leave_selected = max(0, game.leave_selected - 1) if delta < 0 else min(2, game.leave_selected + 1)
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
        if not moved and dx != 0 and dy != 0:
            moved = game.request_player_move(dx, 0)
            if not moved:
                moved = game.request_player_move(0, dy)
        if moved:
            ctx["last_move_time"] = now
