import pygame


def handle_dev_menu_key(ctx, event):
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
