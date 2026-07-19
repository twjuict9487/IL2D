import pygame


def handle_dev_menu_key(ctx, event, replay_opening_fn=None):
    game = ctx["game"]
    opts = [
        "pre_dev_set",
        "max_hp",
        "max_mp",
        "add_money",
        "add_skipper",
        "get_dev_set",
        "skip_story_mission",
        "skip_to_stage_5",
        "replay_opening",
        "exit",
    ]
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
            elif choice == "replay_opening":
                game.opening_showcase_completed = False
                if callable(replay_opening_fn):
                    replay_opening_fn(ctx, game, force=True)
            elif choice == "skip_story_mission":
                options = game.get_dev_story_skip_options()
                if options:
                    ctx["dev_menu_target"] = "story_skip"
                    ctx["dev_story_selected"] = max(
                        0,
                        min(len(options) - 1, int(ctx.get("dev_story_selected", 0) or 0)),
                    )
            elif choice == "skip_to_stage_5":
                if game.dev_skip_to_stage_5_transition():
                    ctx["state"] = "game"
            else:
                ctx["dev_menu_target"] = choice
                ctx["dev_menu_input"] = ""
        elif event.key == pygame.K_ESCAPE:
            ctx["state"] = "game"
    else:
        if ctx["dev_menu_target"] == "story_skip":
            options = game.get_dev_story_skip_options()
            if not options:
                ctx["dev_menu_target"] = None
                return
            selected = int(ctx.get("dev_story_selected", 0) or 0) % len(options)
            if event.key in (pygame.K_UP, pygame.K_w):
                selected = (selected - 1) % len(options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                selected = (selected + 1) % len(options)
            elif event.key == pygame.K_PAGEUP:
                selected = max(0, selected - 9)
            elif event.key == pygame.K_PAGEDOWN:
                selected = min(len(options) - 1, selected + 9)
            elif event.key == pygame.K_HOME:
                selected = 0
            elif event.key == pygame.K_END:
                selected = len(options) - 1
            elif event.key == pygame.K_ESCAPE:
                ctx["dev_menu_target"] = None
                return
            elif event.key == pygame.K_RETURN:
                target = options[selected]
                if game.dev_skip_story_to(target.get("id")):
                    ctx["state"] = "game"
                    ctx["dev_menu_target"] = None
                return
            ctx["dev_story_selected"] = selected
            return
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
                    game.inventory["rogue level skipper"] = game.inventory.get(
                        "rogue level skipper", 0
                    ) + max(0, val)
            ctx["dev_menu_target"] = None
            ctx["dev_menu_input"] = ""
            return
        if event.unicode and event.unicode.isdigit():
            ctx["dev_menu_input"] += event.unicode
