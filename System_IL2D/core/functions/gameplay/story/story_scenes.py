import os
import re
import time

from .. import missions as game_missions


_SPEAKER_NAMES = {
    "system": {"zh": "系統", "en": "System"},
    "kaltsit": {"zh": "Kal'tsit", "en": "Kal'tsit"},
    "priestess": {"zh": "Priestess", "en": "Priestess"},
    "doctor": {"zh": "Doctor", "en": "Doctor"},
}


def _speaker_name(game, scene):
    lang = str(getattr(game, "lang", "") or "").lower()
    value = scene.get("speaker_name_zh") if lang == "zh" else scene.get("speaker_name_en")
    raw = str(value or scene.get("speaker_name") or scene.get("speaker") or "").strip()
    names = _SPEAKER_NAMES.get(raw.lower())
    if names:
        return names.get(lang) or names.get("en") or raw
    return raw or ("旁白" if lang == "zh" else "Narrator")


def start_scene(
    game,
    story_book,
    story_state,
    stage,
    line,
    story_mission,
    scene,
    direct_dialogue=False,
):
    scene_type = str(scene.get("type", "") or "").strip()
    if scene_type == "stage_title":
        return _start_stage_title(game, story_state, scene)
    if scene_type == "dialogue":
        if direct_dialogue:
            return play_dialogue_scene(game, scene)
        return _queue_dialogue(game, story_state, scene)
    if scene_type == "png_dialogue":
        return _start_png_dialogue(game, scene)
    if scene_type == "mission":
        return _start_mission(game, stage, line, story_mission, scene)
    if hasattr(game, "push_message"):
        game.push_message(f"Unknown story scene type: {scene_type}")
    return False


def _start_stage_title(game, story_state, scene):
    card = {
        "scene_id": scene.get("id"),
        "label": scene.get("label", ""),
        "title": scene.get("title", ""),
        "hold_seconds": float(scene.get("hold_seconds", 1.5) or 1.5),
        "fade_seconds": float(scene.get("fade_seconds", 1.0) or 1.0),
        "started_at": time.time(),
    }
    story_state["title_card"] = card
    game.story_title_card = card
    game.ui_mode = "story_title_card"
    return True


def _queue_dialogue(game, story_state, scene):
    speaker = str(scene.get("speaker", "") or "").strip()
    story_state["pending_dialogue"] = {
        "scene_id": scene.get("id"),
        "speaker": speaker,
    }
    if getattr(game, "ui_mode", None) in {"dialog", "story_title_card"}:
        game.ui_mode = None
    return True


def play_dialogue_scene(game, scene):
    lines = [str(v) for v in scene.get("lines", []) or []]
    ok_text = "OK"
    speaker = _speaker_name(game, scene)
    game.dialog_data = {
        "start": "node_1",
        "node_1": {
            "text": "\n".join(lines) if lines else "...",
            "responses": [{"text": ok_text, "next": "story_continue"}],
        },
    }
    game.dialog_node = "node_1"
    game.dialog_text_lines = lines or ["..."]
    game.dialog_lines = list(game.dialog_text_lines)
    game.dialog_options = [{"text": ok_text, "next": "story_continue"}]
    game.dialog_responses = list(game.dialog_options)
    game.dialog_choices = list(game.dialog_options)
    game.dialog_selected = 0
    game.dialog_scroll = 0
    game.active_npc = speaker
    game.dialog_speaker_name = speaker
    game.dialog_npc_name = speaker
    game.dialog_title = speaker
    game.dialog_source = "story"
    game.ui_mode = "dialog"
    return True


def _start_png_dialogue(game, scene):
    ctx = getattr(game, "runtime_context", None)
    if not isinstance(ctx, dict):
        if hasattr(game, "push_message"):
            game.push_message("Story png dialogue missing runtime context")
        return False
    path = _resolve_png_dialogue_path(scene)
    if not path:
        if hasattr(game, "push_message"):
            game.push_message(f"Story png dialogue missing file: {scene.get('source_file', '')}")
        return False
    try:
        from ...ui.prologue_presentation import (
            load_prologue_presentation,
            start_prologue_presentation,
        )

        config = load_prologue_presentation(path)
        return bool(
            start_prologue_presentation(
                ctx, config=config, force=True, purpose="story_png_dialogue"
            )
        )
    except Exception as exc:
        if hasattr(game, "push_message"):
            game.push_message(f"Story png dialogue failed: {exc}")
        return False


def _resolve_png_dialogue_path(scene):
    root = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "Pre_coded_data",
            "game_data",
        )
    )
    source = str(scene.get("source_file", "") or "").strip()
    candidates = []
    if source:
        if os.path.isabs(source):
            candidates.append(source)
        candidates.append(os.path.join(root, source))
        candidates.append(os.path.join(root, "presentations", os.path.basename(source)))
    key = f"{scene.get('id', '')} {source}"
    match = re.search(r"(?:mission_|s5m)(\d+)", key)
    if match:
        candidates.append(os.path.join(root, "presentations", f"s5m{int(match.group(1))}.json"))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _start_mission(game, stage, line, story_mission, scene):
    runtime_id = str(scene.get("runtime_id") or scene.get("mission_id") or "").strip()
    if not runtime_id:
        if hasattr(game, "push_message"):
            game.push_message("Story mission scene is missing runtime_id")
        return False
    mission_state = getattr(game, "mission_state", {}) or {}
    completed = set(mission_state.get("completed", []) or [])
    completed.update((mission_state.get("completed_data", {}) or {}).keys())
    if runtime_id in completed:
        manager = getattr(game, "story_manager", None)
        return bool(manager and manager.advance_scene(game))
    context = {
        "source": "story",
        "stage_id": stage.get("id"),
        "line_id": line.get("id"),
        "story_mission_id": story_mission.get("id"),
        "scene_id": scene.get("id"),
    }
    ok = game_missions.start_runtime_mission(game, runtime_id, source_context=context)
    if ok:
        if hasattr(game, "show_story_mission_card"):
            game.show_story_mission_card(
                story_mission.get("title", runtime_id),
                number=story_mission.get("number"),
            )
        try:
            from .. import mission_handlers

            runtime = game.mission_state.get("active", {}).get(runtime_id)
            if runtime:
                mission_handlers.start_runtime(game, runtime)
        except Exception as exc:
            print(f"[story mission handler] start_runtime failed: {exc}")
        game.ui_mode = None
    return ok
