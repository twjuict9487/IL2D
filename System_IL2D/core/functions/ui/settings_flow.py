import pygame


def handle_settings_key(ctx, event):
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


def handle_mouse_settings(ctx, pos):
    # keep mouse simple: click outside closes sub menu
    if ctx["settings_sub"] == "language":
        return
