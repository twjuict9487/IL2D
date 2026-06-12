import pygame

from core.functions.audio.audio_manager import AudioManager
from ..gameplay.game import Game


def open_new_game_name_input(ctx):
    ctx["new_game_name"] = ""
    pygame.key.start_text_input()
    ctx["state"] = "name_input"


def handle_name_input_key(
    ctx, event, has_seen_tutorial_fn, build_tutorial_lines_fn, start_lore_intro_fn=None
):
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

        try:
            pygame.mixer.init()
        except Exception as exc:
            print(f"[audio] mixer init failed: {exc}")

        game.audio = AudioManager(sfx_volume=0.7, bgm_volume=0.4)
        game.refresh_music()
        game.audio.play_sfx("confirm")

        game.start_new_player_tutorial()
        ctx["game"] = game
        pygame.key.stop_text_input()

        if callable(start_lore_intro_fn):
            start_lore_intro_fn(ctx, game)
        else:
            ctx["state"] = "game"


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
