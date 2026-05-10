import pygame

from ..support.i18n import tr


def build_tutorial_lines(lang, mode="start"):
    if mode == "manual":
        keys = [
            "manual.step.1",
            "manual.step.2",
            "manual.step.3",
            "manual.step.4",
            "manual.step.5",
            "manual.step.6",
        ]
    else:
        keys = [
            "tutorial.step.1",
            "tutorial.step.2",
            "tutorial.step.3",
            "tutorial.step.4",
            "tutorial.step.5",
            "tutorial.step.6",
        ]
    return [tr(lang, k) for k in keys]


def handle_tutorial_key(ctx, event, mark_seen_fn):
    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
        ctx["tutorial_idx"] = ctx.get("tutorial_idx", 0) + 1
        if ctx["tutorial_idx"] >= len(ctx.get("tutorial_lines", [])):
            if ctx.get("tutorial_mode", "start") == "start":
                mark_seen_fn()
            ctx["state"] = ctx.get("tutorial_return_state", "game")
        return
    if event.key == pygame.K_ESCAPE:
        if ctx.get("tutorial_mode", "start") == "start":
            mark_seen_fn()
        ctx["state"] = ctx.get("tutorial_return_state", "game")


def handle_tutorial_mouse(ctx, mark_seen_fn):
    ctx["tutorial_idx"] = ctx.get("tutorial_idx", 0) + 1
    if ctx["tutorial_idx"] >= len(ctx.get("tutorial_lines", [])):
        if ctx.get("tutorial_mode", "start") == "start":
            mark_seen_fn()
        ctx["state"] = ctx.get("tutorial_return_state", "game")
