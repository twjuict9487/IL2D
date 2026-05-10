import pygame

from ..gameplay.game import Game


def open_new_game_name_input(ctx):
    ctx["new_game_name"] = ""
    pygame.key.start_text_input()
    ctx["state"] = "name_input"


def handle_name_input_key(ctx, event, has_seen_tutorial_fn, build_tutorial_lines_fn):
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
        if has_seen_tutorial_fn():
            ctx["state"] = "game"
        else:
            ctx["tutorial_mode"] = "start"
            ctx["tutorial_lines"] = build_tutorial_lines_fn(game.lang, mode="start")
            ctx["tutorial_idx"] = 0
            ctx["tutorial_return_state"] = "game"
            ctx["state"] = "tutorial"


def handle_text_input(ctx, text):
    if ctx.get("state") != "name_input":
        return
    current = ctx.get("new_game_name", "")
    for ch in text:
        if ch.isprintable() and ch not in ("\r", "\n", "\t"):
            if len(current) >= 20:
                break
            current += ch
    ctx["new_game_name"] = current
