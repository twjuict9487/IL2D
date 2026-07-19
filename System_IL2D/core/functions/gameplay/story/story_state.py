from copy import deepcopy


def normalize_story_state(state, story_book=None):
    book = story_book or {}
    src = state if isinstance(state, dict) else {}
    unlocked = _clean_list(src.get("unlocked_story_missions", src.get("unlocked", [])))
    started = _clean_list(src.get("started_story_missions", src.get("started", [])))
    completed = _clean_list(
        src.get("completed_story_missions", src.get("completed", []))
    )
    completed_lines = _clean_list(src.get("completed_lines", []))
    completed_stages = _clean_list(src.get("completed_stages", []))
    started_stages = _clean_list(src.get("started_stages", []))
    unlocked_stages = _clean_list(src.get("unlocked_stages", []))
    flags = src.get("stage_flags", {})
    if not isinstance(flags, dict):
        flags = {}
    notified = _clean_list(src.get("notified_runtime_missions", []))

    if not unlocked_stages:
        for stage in book.get("stages", []) or []:
            if not stage.get("requires"):
                unlocked_stages.append(stage.get("id"))
    if not unlocked:
        for stage in book.get("stages", []) or []:
            for line in stage.get("lines", []) or []:
                if line.get("role") == "major" and not line.get("requires"):
                    missions = line.get("missions", []) or []
                    if missions:
                        unlocked.append(missions[0].get("id"))
                    break

    out = {
        "active_stage": _clean(src.get("active_stage")),
        "active_line": _clean(src.get("active_line")),
        "active_story_mission": _clean(src.get("active_story_mission")),
        "current_scene_index": int(src.get("current_scene_index", 0) or 0),
        "started_stages": [v for v in started_stages if v],
        "completed_stages": [v for v in completed_stages if v],
        "unlocked_stages": [v for v in unlocked_stages if v],
        "started_story_missions": [v for v in started if v],
        "completed_story_missions": [v for v in completed if v],
        "unlocked_story_missions": [v for v in unlocked if v],
        "completed_lines": [v for v in completed_lines if v],
        "stage_flags": deepcopy(flags),
        "notified_runtime_missions": [v for v in notified if v],
        "pending_dialogue": deepcopy(src.get("pending_dialogue"))
        if isinstance(src.get("pending_dialogue"), dict)
        else None,
        "skip_opening_for_active": bool(src.get("skip_opening_for_active", False)),
        "title_card": deepcopy(src.get("title_card"))
        if isinstance(src.get("title_card"), dict)
        else None,
    }
    return out


def _clean(value):
    text = str(value or "").strip()
    return text or None


def _clean_list(value):
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v or "").strip()]
