import pygame

K = {pygame.K_w: "w", pygame.K_s: "s", pygame.K_a: "a", pygame.K_d: "d"}


def update_held_keys(c, e, d):
    k = K.get(e.key)
    if k:
        c["held_keys"][k] = d


def press_move(c, k, dx, dy):
    n = pygame.time.get_ticks() / 1000
    c["press_time"][k] = n
    h = c["held_keys"]
    g = c["game"]
    m = 0
    if k in "ws":
        x = h["d"] - h["a"]
        if x:
            m = g.request_player_move(x, dy)
    elif k in "ad":
        y = h["s"] - h["w"]
        if y:
            m = g.request_player_move(dx, y)
    if not m:
        m = g.request_player_move(dx, dy)
    if m:
        c["last_move_time"] = n


def handle_held_movement(c):
    n = pygame.time.get_ticks() / 1000
    if n - c["last_move_time"] < c["move_interval"]:
        return
    h = c["held_keys"]
    p = c["press_time"]
    D = c.get("hold_repeat_delay", 0.08)
    u = h["w"] and n - p["w"] >= D
    d = h["s"] and n - p["s"] >= D
    l = h["a"] and n - p["a"] >= D
    r = h["d"] and n - p["d"] >= D
    if c["state"] == "esc_menu":
        g = c["game"]
        if not g.ui_mode or not (u or d):
            return
        q = -1 if u else 1
        m = g.ui_mode
        if m == "item":
            a = g.get_item_list()
            if a:
                g.item_selected = (
                    max(0, g.item_selected % len(a) - 2)
                    if q < 0
                    else min(len(a) - 1, g.item_selected % len(a) + 2)
                )
        elif m == "hotbar":
            s = getattr(g, "hotbar_stage", "type")
            if s == "type":
                g.hotbar_type_selected = 1 - int(getattr(g, "hotbar_type_selected", 0))
            elif s == "slot":
                g.hotbar_slot_selected = (
                    max(0, g.hotbar_slot_selected - 1)
                    if q < 0
                    else min(9, g.hotbar_slot_selected + 1)
                )
            else:
                a = g.get_item_list() if g.hotbar_mode == "item" else g.spells
                if a:
                    g.hotbar_list_selected = (
                        max(0, g.hotbar_list_selected % len(a) - 1)
                        if q < 0
                        else min(len(a) - 1, g.hotbar_list_selected % len(a) + 1)
                    )
        elif m == "skill_tree":
            g.skill_tree_selected = (
                max(0, g.skill_tree_selected + q)
                if q < 0
                else g.skill_tree_selected + 1
            )
        elif m == "leave_confirm":
            g.leave_selected = (
                max(0, g.leave_selected - 1) if q < 0 else min(2, g.leave_selected + 1)
            )
        elif m == "save":
            g.save_selected = (g.save_selected + q) % 3
        c["last_move_time"] = n
        return
    if c["state"] != "game":
        return
    g = c["game"]
    if g.ui_mode:
        return
    x = r - l
    y = d - u
    if x or y:
        m = g.request_player_move(x, y)
        if not m and x and y:
            m = g.request_player_move(x, 0) or g.request_player_move(0, y)
        if m:
            c["last_move_time"] = n
