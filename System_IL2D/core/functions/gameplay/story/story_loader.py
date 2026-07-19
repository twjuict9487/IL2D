import os
from copy import deepcopy

from ...support.utils import GAME_DATA_DIR, load_json


STORY_CAMPAIGN_FILE = os.path.join(GAME_DATA_DIR, "story_campaign.json")


def empty_story_book():
    return {
        "version": 1,
        "source_file": "",
        "stages": [],
        "stages_by_id": {},
        "lines_by_id": {},
        "story_missions_by_id": {},
        "scenes_by_id": {},
        "mission_scene_refs": {},
        "errors": [],
    }


def load_story_book(path=None, mission_book=None):
    path = path or STORY_CAMPAIGN_FILE
    raw = load_json(path)
    book = empty_story_book()
    book["version"] = int(raw.get("version", 1) or 1)
    book["source_file"] = path
    book["stages"] = []

    seen = set()
    for stage in raw.get("stages", []) or []:
        if not isinstance(stage, dict):
            continue
        stage_copy = deepcopy(stage)
        stage_id = _require_id(stage_copy, "stage")
        _check_unique(book, seen, stage_id, "stage")
        stage_copy.setdefault("requires", [])
        stage_copy.setdefault("unlocks", [])
        stage_copy.setdefault("opening_scenes", [])
        stage_copy.setdefault("lines", [])
        book["stages"].append(stage_copy)
        book["stages_by_id"][stage_id] = stage_copy

        for scene in stage_copy.get("opening_scenes", []) or []:
            _index_scene(book, seen, scene, stage_copy, None, None)

        for line in stage_copy.get("lines", []) or []:
            if not isinstance(line, dict):
                continue
            line_id = _require_id(line, "line")
            _check_unique(book, seen, line_id, "line")
            line.setdefault("requires", [])
            line.setdefault("unlocks", [])
            line.setdefault("missions", [])
            line["_stage_id"] = stage_id
            book["lines_by_id"][line_id] = line
            for mission in line.get("missions", []) or []:
                if not isinstance(mission, dict):
                    continue
                story_mission_id = _require_id(mission, "story mission")
                _check_unique(book, seen, story_mission_id, "story_mission")
                mission.setdefault("requires", [])
                mission.setdefault("unlocks", [])
                mission.setdefault("scenes", [])
                mission["_stage_id"] = stage_id
                mission["_line_id"] = line_id
                book["story_missions_by_id"][story_mission_id] = mission
                for scene in mission.get("scenes", []) or []:
                    _index_scene(book, seen, scene, stage_copy, line, mission)

    validate_story_book(book, mission_book=mission_book, emit=False)
    return book


def validate_story_book(book, mission_book=None, emit=True):
    errors = []
    if not isinstance(book, dict):
        return ["story book is not a dict"]
    line_ids = set(book.get("lines_by_id", {}))
    story_mission_ids = set(book.get("story_missions_by_id", {}))
    known_story_ids = set(book.get("stages_by_id", {})) | line_ids | story_mission_ids
    runtime_ids = set((mission_book or {}).get("missions_by_id", {}))

    for stage in book.get("stages", []) or []:
        _validate_refs(errors, stage, known_story_ids, "stage")
        for line in stage.get("lines", []) or []:
            _validate_refs(errors, line, known_story_ids, "line")
            for mission in line.get("missions", []) or []:
                _validate_refs(errors, mission, known_story_ids, "story mission")
                for scene in mission.get("scenes", []) or []:
                    if scene.get("type") == "mission":
                        runtime_id = scene.get("runtime_id") or scene.get("mission_id")
                        if not runtime_id:
                            errors.append(f"{scene.get('id')}: missing runtime_id")
                        elif runtime_ids and runtime_id not in runtime_ids:
                            errors.append(
                                f"{scene.get('id')}: runtime mission {runtime_id} not found"
                            )
    book["errors"] = errors
    if emit:
        for err in errors:
            print(f"[story] {err}")
    if errors:
        raise ValueError("; ".join(errors))
    return errors


def _require_id(row, label):
    row_id = str(row.get("id", "") or "").strip()
    if not row_id:
        raise ValueError(f"missing {label} id")
    return row_id


def _check_unique(book, seen, row_id, label):
    if row_id in seen:
        book.setdefault("errors", []).append(f"duplicate {label} id {row_id}")
        raise ValueError(f"duplicate {label} id {row_id}")
    seen.add(row_id)


def _index_scene(book, seen, scene, stage, line, mission):
    if not isinstance(scene, dict):
        return
    scene_id = _require_id(scene, "scene")
    _check_unique(book, seen, scene_id, "scene")
    scene["_stage_id"] = stage.get("id")
    if line:
        scene["_line_id"] = line.get("id")
    if mission:
        scene["_story_mission_id"] = mission.get("id")
    book["scenes_by_id"][scene_id] = scene
    if scene.get("type") == "mission":
        runtime_id = str(scene.get("runtime_id") or scene.get("mission_id") or "")
        if runtime_id:
            book["mission_scene_refs"][runtime_id] = {
                "stage_id": stage.get("id"),
                "line_id": line.get("id") if line else None,
                "story_mission_id": mission.get("id") if mission else None,
                "scene_id": scene_id,
            }


def _validate_refs(errors, row, known_ids, label):
    row_id = row.get("id", label)
    for key in ("requires", "unlocks"):
        refs = row.get(key, []) or []
        if not isinstance(refs, list):
            errors.append(f"{row_id}: {key} must be a list")
            continue
        for ref in refs:
            if str(ref) not in known_ids:
                errors.append(f"{row_id}: {key} reference {ref} not found")
