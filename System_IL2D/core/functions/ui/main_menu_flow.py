import pygame

from ..support.i18n import tr


def handle_main_menu_key(ctx, event, open_new_game_name_input_fn, get_save_slots_fn):
    menu_count = 5
    if event.key == pygame.K_UP:
        ctx["menu_selected"] = (ctx["menu_selected"] - 1) % menu_count
    elif event.key == pygame.K_DOWN:
        ctx["menu_selected"] = (ctx["menu_selected"] + 1) % menu_count
    elif event.key == pygame.K_RETURN:
        if ctx["menu_selected"] == 0:
            open_new_game_name_input_fn(ctx)
        elif ctx["menu_selected"] == 1:
            ctx["continue_slots"] = get_save_slots_fn()
            ctx["continue_selected"] = 0
            ctx["state"] = "continue_menu"
        elif ctx["menu_selected"] == 2:
            ctx["state"] = "settings"
        elif ctx["menu_selected"] == 3:
            ctx["running"] = False
        elif ctx["menu_selected"] == 4:
            pass


def handle_mouse_main_menu(
    ctx, pos, get_font_fn, open_new_game_name_input_fn, get_save_slots_fn
):
    mx, my = pos
    screen = ctx["screen"]
    font2 = get_font_fn(32)
    opts = ["new_game", "continue", "setting", "leave", "credits"]
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
                open_new_game_name_input_fn(ctx)
            elif i == 1:
                ctx["continue_slots"] = get_save_slots_fn()
                ctx["continue_selected"] = 0
                ctx["state"] = "continue_menu"
            elif i == 2:
                ctx["state"] = "settings"
            elif i == 3:
                ctx["running"] = False
            elif i == 4:
                pass
            break
