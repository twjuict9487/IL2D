import math
import os
from bisect import bisect_right

import pygame

from ..support.asset_resolver import resolve_image_candidates
from ..support.utils import load_json


_PRESENTATION_FILE = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "Pre_coded_data",
        "game_data",
        "prologue_presentation.json",
    )
)
_ACTOR_IMAGE_CACHE = {}
_DEFAULTS = {
    "narrator_speed": 9.0,
    "dialogue_speed": 8.0,
    "thought_speed": 7.5,
    "heavy_speed": 6.75,
    "pre_delay": 0.15,
    "post_delay": 0.55,
    "speaker_transition": 0.5,
    "finish_fade": 0.6,
}
_PUNCTUATION_DELAYS = {
    "，": 0.12,
    "。": 0.28,
    "？": 0.32,
    "！": 0.28,
    "…": 0.22,
}


def load_prologue_presentation(path=None):
    source = path or _PRESENTATION_FILE
    try:
        data = load_json(source)
    except Exception as exc:
        print(f"[prologue presentation] load failed: {source}: {exc}")
        return {"actors": [], "lines": []}
    if not isinstance(data, dict):
        print(f"[prologue presentation] invalid root object: {source}")
        return {"actors": [], "lines": []}
    data.setdefault("actors", [])
    data.setdefault("lines", [])
    return data


def start_prologue_presentation(ctx, config=None, force=False, purpose="prologue"):
    data = config if isinstance(config, dict) else load_prologue_presentation()
    game = ctx.get("game")
    if not force and bool(getattr(game, "opening_showcase_completed", False)):
        return False
    actors = [actor for actor in data.get("actors", []) if isinstance(actor, dict)]
    lines = [line for line in data.get("lines", []) if isinstance(line, dict)]
    if not actors:
        return False
    transitions = data.get("transitions", {})
    if not isinstance(transitions, dict):
        transitions = {}
    scenes = data.get("scenes", {})
    if not isinstance(scenes, dict):
        scenes = {}
    initial_scene = str(data.get("initial_scene", "")).strip()
    if initial_scene not in scenes:
        initial_scene = next(iter(scenes), "")
    defaults = dict(_DEFAULTS)
    configured_defaults = data.get("defaults", {})
    if isinstance(configured_defaults, dict):
        for key in defaults:
            if key in configured_defaults:
                defaults[key] = max(0.0, float(configured_defaults[key]))
    ctx["prologue_presentation"] = {
        "purpose": str(purpose or "prologue"),
        "actors": actors,
        "lines": lines,
        "opening_phase": "FADE_TO_BLACK",
        "phase": "PRE_DELAY",
        "phase_elapsed": 0.0,
        "fade_to_black_duration": max(
            0.1, float(transitions.get("fade_to_black", 1.0))
        ),
        "character_reveal_duration": max(
            0.1, float(transitions.get("character_reveal", 2.2))
        ),
        "reveal_hold_duration": max(
            0.0, float(transitions.get("reveal_hold", 0.8))
        ),
        "scene_fade_out_duration": max(
            0.1, float(transitions.get("scene_fade_out", 0.8))
        ),
        "scene_fade_in_duration": max(
            0.1, float(transitions.get("scene_fade_in", 1.0))
        ),
        "previous_frame": ctx["screen"].copy(),
        "defaults": defaults,
        "scenes": scenes,
        "current_scene": initial_scene,
        "pending_scene": None,
        "scene_transition_phase": None,
        "scene_transition_elapsed": 0.0,
        "line_index": 0,
        "line_elapsed": 0.0,
        "visible_chars": 0,
        "scene": "stage",
        "characters_visible": True,
        "finished": False,
    }
    ctx["state"] = "prologue_presentation"
    return True


def update_prologue_presentation(ctx, dt):
    try:
        return _update_prologue_presentation(ctx, dt)
    except Exception as exc:
        state = ctx.get("prologue_presentation") or {}
        state["error"] = str(exc)
        state["finished"] = True
        print(f"[prologue presentation] update failed: {exc}")
        return True


def _update_prologue_presentation(ctx, dt):
    state = ctx.get("prologue_presentation") or {}
    if _update_scene_transition(state, dt):
        return False
    opening_phase = state.get("opening_phase")
    phase_elapsed = float(state.get("phase_elapsed", 0.0)) + max(
        0.0, float(dt)
    )
    if opening_phase == "FADE_TO_BLACK":
        if phase_elapsed < float(state.get("fade_to_black_duration", 1.0)):
            state["phase_elapsed"] = phase_elapsed
            return False
        state["opening_phase"] = "CHARACTER_REVEAL"
        state["phase_elapsed"] = 0.0
        return False
    if opening_phase == "CHARACTER_REVEAL":
        if phase_elapsed < float(state.get("character_reveal_duration", 2.2)):
            state["phase_elapsed"] = phase_elapsed
            return False
        state["opening_phase"] = "REVEAL_HOLD"
        state["phase_elapsed"] = 0.0
        return False
    if opening_phase == "REVEAL_HOLD":
        if phase_elapsed < float(state.get("reveal_hold_duration", 0.8)):
            state["phase_elapsed"] = phase_elapsed
            return False
        state["opening_phase"] = None
        state["phase_elapsed"] = 0.0

    lines = state.get("lines", [])
    index = int(state.get("line_index", 0))
    if not lines:
        state["phase"] = "FINISHED"
    elif index >= len(lines):
        index = len(lines) - 1
        state["line_index"] = index
        state["phase"] = "FINISHED"

    phase = state.get("phase", "PRE_DELAY")
    elapsed = float(state.get("line_elapsed", 0.0)) + max(0.0, float(dt))
    line = _resolved_line(lines[index], ctx) if lines else {}
    defaults = state.get("defaults", _DEFAULTS)

    if phase == "PRE_DELAY":
        state["visible_chars"] = 0
        if elapsed >= _line_setting(line, "pre_delay", defaults):
            state["phase"] = "TYPEWRITING"
            elapsed = 0.0
    elif phase == "TYPEWRITING":
        reveal_times = character_reveal_times(line, defaults)
        state["visible_chars"] = bisect_right(reveal_times, elapsed)
        if elapsed >= typing_duration(line, defaults):
            state["visible_chars"] = len(_line_text(line, "zh"))
            state["phase"] = "POST_DELAY"
            elapsed = 0.0
    elif phase == "POST_DELAY":
        state["visible_chars"] = len(_line_text(line, "zh"))
        if elapsed >= _line_setting(line, "post_delay", defaults):
            state["phase"] = "NEXT_LINE"
            elapsed = 0.0
    elif phase == "NEXT_LINE":
        if elapsed >= _speaker_transition(lines, index, defaults):
            next_index = index + 1
            if next_index >= len(lines):
                state["phase"] = "FINISHED"
            else:
                state["line_index"] = next_index
                state["visible_chars"] = 0
                _apply_line_action(state, lines[next_index])
                state["phase"] = "PRE_DELAY"
            elapsed = 0.0
    elif phase == "FINISHED":
        state["finished"] = True
        state["line_elapsed"] = elapsed
        return elapsed >= float(defaults.get("finish_fade", 0.6))

    state["line_elapsed"] = elapsed
    return False


def _update_scene_transition(state, dt):
    phase = state.get("scene_transition_phase")
    if not phase:
        return False
    elapsed = float(state.get("scene_transition_elapsed", 0.0)) + max(
        0.0, float(dt)
    )
    if phase == "FADE_OUT":
        duration = float(state.get("scene_fade_out_duration", 0.8))
        if elapsed >= duration:
            state["current_scene"] = state.get("pending_scene")
            state["scene_transition_phase"] = "FADE_IN"
            state["scene_transition_elapsed"] = 0.0
        else:
            state["scene_transition_elapsed"] = elapsed
        return True
    if phase == "FADE_IN":
        duration = float(state.get("scene_fade_in_duration", 1.0))
        if elapsed >= duration:
            state["scene_transition_phase"] = None
            state["scene_transition_elapsed"] = 0.0
            state["pending_scene"] = None
            state["line_elapsed"] = 0.0
        else:
            state["scene_transition_elapsed"] = elapsed
        return True
    state["scene_transition_phase"] = None
    state["pending_scene"] = None
    return False


def character_reveal_times(line, defaults=None):
    return _typing_timeline(line, defaults)[0]


def typing_duration(line, defaults=None):
    return _typing_timeline(line, defaults)[1]


def _typing_timeline(line, defaults=None):
    defaults = defaults or _DEFAULTS
    text = _line_text(line, "zh")
    speed = max(0.1, _typing_speed(line, defaults))
    times = []
    elapsed = 0.0
    previous = ""
    for char in text:
        elapsed += 1.0 / speed
        times.append(elapsed)
        elapsed += _PUNCTUATION_DELAYS.get(char, 0.0)
        if char == "—" and previous == "—":
            elapsed += 0.40
        previous = char
    return times, elapsed


def line_duration(line, defaults=None):
    defaults = defaults or _DEFAULTS
    return (
        _line_setting(line, "pre_delay", defaults)
        + typing_duration(line, defaults)
        + _line_setting(line, "post_delay", defaults)
    )


def draw_prologue_presentation(ctx):
    screen = ctx["screen"]
    game = ctx.get("game")
    lang = getattr(game, "lang", "zh")
    state = ctx.get("prologue_presentation") or {}
    lines = state.get("lines", [])
    index = int(state.get("line_index", 0))
    line = _resolved_line(lines[index], ctx) if 0 <= index < len(lines) else {}
    speaker_id = str(line.get("speaker", "")).strip().lower()
    elapsed = float(state.get("line_elapsed", 0.0))
    phase = state.get("phase", "PRE_DELAY")
    opening_phase = state.get("opening_phase")

    if opening_phase == "FADE_TO_BLACK":
        previous = state.get("previous_frame")
        if isinstance(previous, pygame.Surface):
            screen.blit(previous, (0, 0))
        else:
            screen.fill((0, 0, 0))
        duration = max(0.1, float(state.get("fade_to_black_duration", 1.0)))
        alpha = min(255, round(255 * float(state.get("phase_elapsed", 0.0)) / duration))
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, alpha))
        screen.blit(veil, (0, 0))
        return

    if state.get("scene", "stage") == "black":
        screen.fill((0, 0, 0))
    else:
        _draw_backdrop(screen)
    panel_h = max(180, screen.get_height() // 4)
    panel = pygame.Rect(0, screen.get_height() - panel_h, screen.get_width(), panel_h)
    stage_bottom = panel.y + 20
    target_h = max(220, panel.y - 34)

    actors = state.get("actors", [])
    actor_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    scene_transition_phase = state.get("scene_transition_phase")
    in_dialogue = (
        opening_phase is None and not scene_transition_phase and bool(lines)
    )
    active_actor_ids = _active_actor_ids(state)
    for actor in actors:
        actor_id = str(actor.get("id", "")).strip().lower()
        if active_actor_ids is not None and actor_id not in active_actor_ids:
            continue
        image = _load_actor_image(actor, target_h)
        if image is None:
            _draw_missing_actor(actor_layer, actor, lang, stage_bottom, target_h)
            continue
        speaking = in_dialogue and speaker_id != "narrator" and actor_id == speaker_id
        shown = _actor_effect(image, actor, speaking)
        x_ratio = float(actor.get("x", 0.5))
        x = int(screen.get_width() * x_ratio - shown.get_width() / 2)
        y = stage_bottom - shown.get_height()
        if speaking:
            y += _talking_offset(elapsed, _line_text(line, lang))
        actor_layer.blit(shown, (x, y))

    if not bool(state.get("characters_visible", True)):
        actor_layer.set_alpha(0)
    elif opening_phase == "CHARACTER_REVEAL":
        duration = max(0.1, float(state.get("character_reveal_duration", 2.2)))
        actor_layer.set_alpha(
            min(255, round(255 * float(state.get("phase_elapsed", 0.0)) / duration))
        )
    screen.blit(actor_layer, (0, 0))

    if scene_transition_phase:
        transition_veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        transition_elapsed = float(state.get("scene_transition_elapsed", 0.0))
        if scene_transition_phase == "FADE_OUT":
            duration = max(0.1, float(state.get("scene_fade_out_duration", 0.8)))
            alpha = round(255 * min(1.0, transition_elapsed / duration))
        else:
            duration = max(0.1, float(state.get("scene_fade_in_duration", 1.0)))
            alpha = round(255 * (1.0 - min(1.0, transition_elapsed / duration)))
        transition_veil.fill((0, 0, 0, alpha))
        screen.blit(transition_veil, (0, 0))

    if in_dialogue:
        dialogue_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        _draw_dialogue_panel(dialogue_layer, panel, state, line, lang)
        if phase == "FINISHED":
            duration = max(
                0.1, float(state.get("defaults", {}).get("finish_fade", 0.6))
            )
            dialogue_layer.set_alpha(
                max(0, 255 - round(255 * min(1.0, elapsed / duration)))
            )
        screen.blit(dialogue_layer, (0, 0))


def _draw_backdrop(screen):
    screen.fill((8, 11, 15))
    height = max(1, screen.get_height())
    for y in range(0, height, 8):
        ratio = y / height
        color = (
            int(12 + 14 * ratio),
            int(17 + 18 * ratio),
            int(22 + 20 * ratio),
        )
        pygame.draw.rect(screen, color, (0, y, screen.get_width(), 8))
    pygame.draw.line(
        screen,
        (74, 81, 88),
        (screen.get_width() // 10, height - height // 4 - 1),
        (screen.get_width() * 9 // 10, height - height // 4 - 1),
        1,
    )


def _draw_dialogue_panel(screen, panel, state, line, lang):
    veil = pygame.Surface(panel.size, pygame.SRCALPHA)
    veil.fill((7, 10, 14, 238))
    screen.blit(veil, panel.topleft)
    pygame.draw.line(screen, (154, 166, 174), panel.topleft, panel.topright, 2)

    name_font = _font(24, bold=True)
    body_font = _font(22)
    small_font = _font(15)
    speaker_id = str(line.get("speaker", "")).strip().lower()
    speaker = _speaker_name(state.get("actors", []), line, lang)
    text = _line_text(line, lang)
    visible = text[: min(len(text), int(state.get("visible_chars", 0)))]

    if speaker_id != "narrator":
        name_surface = name_font.render(speaker, True, (238, 231, 210))
        screen.blit(name_surface, (panel.x + 34, panel.y + 20))
    y = panel.y + 62
    for row in _wrap_text(body_font, visible, panel.width - 68)[:4]:
        surface = body_font.render(row, True, (232, 235, 237))
        screen.blit(surface, (panel.x + 34, y))
        y += body_font.get_height() + 7

    progress = f"{int(state.get('line_index', 0)) + 1} / {max(1, len(state.get('lines', [])))}"
    progress_surface = small_font.render(progress, True, (133, 143, 151))
    screen.blit(
        progress_surface,
        (panel.right - progress_surface.get_width() - 24, panel.bottom - 26),
    )


def _draw_missing_actor(screen, actor, lang, stage_bottom, target_h):
    if str(actor.get("id", "")).strip().lower() == "exit_light":
        _draw_exit_light(screen, actor, stage_bottom, target_h)
        return
    width = max(90, screen.get_width() // 7)
    height = max(180, int(target_h * float(actor.get("scale", 1.0))))
    x = int(screen.get_width() * float(actor.get("x", 0.5)) - width / 2)
    rect = pygame.Rect(x, stage_bottom - height, width, height)
    pygame.draw.rect(screen, (24, 27, 31), rect)
    pygame.draw.rect(screen, (155, 93, 88), rect, 2)
    name = str(
        actor.get(f"name_{lang}") or actor.get("name") or actor.get("id", "?")
    )
    font = _font(15, bold=True)
    for index, label in enumerate((name, "[missing image]")):
        surface = font.render(label, True, (216, 164, 157))
        screen.blit(
            surface,
            (rect.centerx - surface.get_width() // 2, rect.centery + index * 22 - 18),
        )


def _draw_exit_light(screen, actor, stage_bottom, target_h):
    center_x = int(screen.get_width() * float(actor.get("x", 0.82)))
    center_y = stage_bottom - int(target_h * 0.48)
    glow = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    for radius, alpha in ((180, 18), (130, 28), (86, 48), (48, 90)):
        pygame.draw.circle(glow, (220, 238, 245, alpha), (center_x, center_y), radius)
    pygame.draw.ellipse(
        glow,
        (238, 247, 250, 225),
        (center_x - 23, center_y - 96, 46, 192),
    )
    pygame.draw.ellipse(
        glow,
        (255, 255, 255, 245),
        (center_x - 8, center_y - 82, 16, 164),
    )
    screen.blit(glow, (0, 0))


def _load_actor_image(actor, target_h):
    filename = str(actor.get("image", "")).strip()
    scale = max(0.2, float(actor.get("scale", 1.0)))
    wanted_h = max(1, int(target_h * scale))
    cache_key = (filename.lower(), wanted_h)
    if cache_key in _ACTOR_IMAGE_CACHE:
        return _ACTOR_IMAGE_CACHE[cache_key]
    path = next(
        (candidate for candidate in resolve_image_candidates(filename) if os.path.isfile(candidate)),
        None,
    )
    if not path:
        print(f"[prologue presentation] missing actor image: {filename}")
        _ACTOR_IMAGE_CACHE[cache_key] = None
        return None
    try:
        source = pygame.image.load(path).convert_alpha()
        bounds = source.get_bounding_rect(min_alpha=1)
        if bounds.width <= 0 or bounds.height <= 0:
            raise ValueError("image has no visible pixels")
        source = source.subsurface(bounds).copy()
        width = max(1, round(source.get_width() * wanted_h / source.get_height()))
        image = pygame.transform.smoothscale(source, (width, wanted_h))
        _ACTOR_IMAGE_CACHE[cache_key] = image
        return image
    except Exception as exc:
        print(f"[prologue presentation] actor image load failed: {filename}: {exc}")
        _ACTOR_IMAGE_CACHE[cache_key] = None
        return None


def _actor_effect(image, actor, speaking):
    if bool(actor.get("silhouette", False)):
        result = image.copy()
        result.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return result
    if speaking:
        return image
    try:
        gray = pygame.transform.grayscale(image)
        gray.set_alpha(145)
        result = image.copy()
        result.blit(gray, (0, 0))
    except (AttributeError, pygame.error):
        result = image.copy()
    result.fill((205, 205, 205, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return result


def _talking_offset(elapsed, text):
    amplitude = min(7, 2 + len(text) // 18)
    return -round(abs(math.sin(elapsed * math.tau * 2.4)) * amplitude)


def _typing_speed(line, defaults):
    if line.get("typing_speed") is not None:
        return float(line["typing_speed"])
    style = str(line.get("style", "dialogue")).strip().lower()
    key = {
        "narrator": "narrator_speed",
        "thought": "thought_speed",
        "heavy": "heavy_speed",
    }.get(style, "dialogue_speed")
    return float(defaults.get(key, _DEFAULTS[key]))


def _line_setting(line, key, defaults):
    if line.get(key) is not None:
        return max(0.0, float(line[key]))
    return max(0.0, float(defaults.get(key, _DEFAULTS[key])))


def _speaker_transition(lines, index, defaults):
    if index + 1 >= len(lines):
        return float(defaults.get("speaker_transition", 0.5))
    current = lines[index]
    following = lines[index + 1]
    if following.get("transition_delay") is not None:
        return max(0.0, float(following["transition_delay"]))
    if current.get("speaker") == following.get("speaker") and not following.get(
        "scene"
    ):
        return 0.0
    return float(defaults.get("speaker_transition", 0.5))


def _apply_line_action(state, line):
    transition_target = str(line.get("scene_transition", "")).strip()
    if transition_target:
        scenes = state.get("scenes", {})
        if transition_target in scenes:
            state["pending_scene"] = transition_target
            state["scene_transition_phase"] = "FADE_OUT"
            state["scene_transition_elapsed"] = 0.0
        else:
            print(
                f"[prologue presentation] unknown scene transition: {transition_target}"
            )
    scene = line.get("scene")
    if scene in {"stage", "black"}:
        state["scene"] = scene
    action = line.get("action")
    if action == "hide_characters":
        state["characters_visible"] = False
    elif action == "show_characters":
        state["characters_visible"] = True
    elif action:
        print(f"[prologue presentation] unknown line action: {action}")


def _active_actor_ids(state):
    scene_id = state.get("current_scene")
    scenes = state.get("scenes", {})
    scene = scenes.get(scene_id) if isinstance(scenes, dict) else None
    if not isinstance(scene, dict):
        return None
    actors = scene.get("actors")
    if not isinstance(actors, list):
        return None
    return {str(actor_id).strip().lower() for actor_id in actors if actor_id}


def _resolved_line(line, ctx):
    resolved = dict(line) if isinstance(line, dict) else {}
    game = ctx.get("game")
    player_name = str(getattr(game, "player_name", "Doctor") or "Doctor")
    for key in ("text", "text_zh", "text_en", "speaker_name", "speaker_name_zh", "speaker_name_en"):
        value = resolved.get(key)
        if isinstance(value, str):
            resolved[key] = value.replace("{player_name}", player_name)
    return resolved


def _line_text(line, lang):
    localized = line.get(f"text_{lang}")
    if localized is None:
        localized = line.get("text", "")
    return str(localized or "")


def _speaker_name(actors, line, lang):
    override = line.get(f"speaker_name_{lang}") or line.get("speaker_name")
    if override:
        return str(override)
    speaker_id = line.get("speaker")
    wanted = str(speaker_id or "").strip().lower()
    for actor in actors:
        if str(actor.get("id", "")).strip().lower() != wanted:
            continue
        return str(actor.get(f"name_{lang}") or actor.get("name") or speaker_id)
    return str(speaker_id or "")


def _font(size, bold=False):
    for name in ("Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC"):
        matched = pygame.font.match_font(name)
        if matched:
            return pygame.font.Font(matched, size)
    return pygame.font.SysFont("consolas", size, bold=bold)


def _wrap_text(font, text, max_width):
    rows = []
    current = ""
    for char in str(text):
        if char == "\n":
            rows.append(current)
            current = ""
            continue
        candidate = current + char
        if current and font.size(candidate)[0] > max_width:
            rows.append(current)
            current = char
        else:
            current = candidate
    if current or not rows:
        rows.append(current)
    return rows
