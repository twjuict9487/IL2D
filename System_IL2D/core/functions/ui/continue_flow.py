import os
import pygame

from ..support.utils import SAVE_DIR
from ..audio.audio_manager import AudioManager


def get_save_slots():
    slots = []
    for i in range(1, 4):
        path = os.path.join(SAVE_DIR, f"slot_{i}.json")
        slots.append({"slot": i, "exists": os.path.isfile(path)})
    return slots


def handle_continue_menu_key(ctx, event):
    slots = ctx.get("continue_slots", [])
    if not slots:
        if event.key == pygame.K_ESCAPE:
            ctx["state"] = "main_menu"
        return
    if event.key in (pygame.K_UP, pygame.K_w):
        ctx["continue_selected"] = (ctx["continue_selected"] - 1) % len(slots)
    elif event.key in (pygame.K_DOWN, pygame.K_s):
        ctx["continue_selected"] = (ctx["continue_selected"] + 1) % len(slots)
    elif event.key == pygame.K_RETURN:
        slot = slots[ctx["continue_selected"]]["slot"]
        if ctx["game"].load_save(slot):
            if not hasattr(ctx["game"], "audio"):
                ctx["game"].audio = AudioManager()
            ctx["game"].refresh_music()
            ctx["state"] = "game"
    elif event.key == pygame.K_ESCAPE:
        ctx["state"] = "main_menu"


def handle_mouse_continue_menu(ctx, pos, get_font_fn):
    mx, my = pos
    screen = ctx["screen"]
    slots = ctx.get("continue_slots", [])
    if not slots:
        return
    font = get_font_fn(22)
    start_y = 140
    item_h = font.get_height() + 10
    for i, _ in enumerate(slots):
        rect = pygame.Rect(
            screen.get_width() // 2 - 140,
            start_y + i * item_h - 4,
            280,
            font.get_height() + 8,
        )
        if rect.collidepoint(mx, my):
            ctx["continue_selected"] = i
            slot = slots[i]["slot"]
            if ctx["game"].load_save(slot):
                if not hasattr(ctx["game"], "audio"):
                    ctx["game"].audio = AudioManager()
                ctx["game"].refresh_music()
                ctx["state"] = "game"
            break
