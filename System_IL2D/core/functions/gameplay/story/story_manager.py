from .story_state import normalize_story_state
from . import story_scenes
from .. import missions as game_missions
from ..chase_transition import default_state as default_chase_state


class StoryManager:
    def __init__(self, story_book):
        self.book = story_book or {}

    def start_story_after_tutorial(self, game):
        state = self._state(game)
        if state["stage_flags"].get("tutorial_stage_1_started"):
            return False
        if "stage_1" in state["completed_stages"] or "stage_1" in state["started_stages"]:
            state["stage_flags"]["tutorial_stage_1_started"] = True
            return False
        if getattr(game, "_loading_save", False):
            return False
        state["stage_flags"]["tutorial_stage_1_started"] = True
        return self.start_stage(game, "stage_1", automatic=True)

    def get_dev_skip_options(self):
        options = []
        for stage in self.book.get("stages", []) or []:
            try:
                stage_number = int(stage.get("number", 0) or 0)
            except (TypeError, ValueError):
                continue
            if not 1 <= stage_number <= 4:
                continue
            for line in stage.get("lines", []) or []:
                if line.get("role") != "major":
                    continue
                for mission in line.get("missions", []) or []:
                    number = str(mission.get("number", "") or "")
                    parts = number.split(".")
                    try:
                        mission_number = int(parts[-1])
                    except (TypeError, ValueError):
                        continue
                    if 1 <= mission_number <= 9:
                        options.append(
                            {
                                "id": mission.get("id"),
                                "number": number,
                                "title": mission.get("title", ""),
                                "stage_id": stage.get("id"),
                            }
                        )
        return options

    def dev_skip_to(self, game, story_mission_id):
        options = self.get_dev_skip_options()
        target_index = next(
            (index for index, row in enumerate(options) if row.get("id") == story_mission_id),
            None,
        )
        if target_index is None:
            return False
        target = options[target_index]
        target_stage_id = target.get("stage_id")
        ordered_major_ids = [
            mission.get("id")
            for stage in self.book.get("stages", []) or []
            for line in stage.get("lines", []) or []
            if line.get("role") == "major"
            for mission in line.get("missions", []) or []
        ]
        full_target_index = ordered_major_ids.index(story_mission_id)
        prior_ids = ordered_major_ids[:full_target_index]
        target_stage_index = next(
            (
                index
                for index, stage in enumerate(self.book.get("stages", []) or [])
                if stage.get("id") == target_stage_id
            ),
            0,
        )
        stages = list(self.book.get("stages", []) or [])
        state = self._state(game)
        state["completed_story_missions"] = list(prior_ids)
        state["started_story_missions"] = list(prior_ids)
        state["unlocked_story_missions"] = [story_mission_id]
        state["completed_lines"] = []
        state["completed_stages"] = []
        state["started_stages"] = [
            stage.get("id") for stage in stages[: target_stage_index + 1]
        ]
        state["unlocked_stages"] = list(state["started_stages"])
        for stage in stages[:target_stage_index]:
            stage_id = stage.get("id")
            if stage_id:
                state["completed_stages"].append(stage_id)
            for line in stage.get("lines", []) or []:
                if line.get("role") == "major" and line.get("id"):
                    state["completed_lines"].append(line.get("id"))
                elif line.get("missions"):
                    self._unlock_id(state, line["missions"][0].get("id"))
        state["active_stage"] = None
        state["active_line"] = None
        state["active_story_mission"] = None
        state["current_scene_index"] = 0
        state["pending_dialogue"] = None
        state["title_card"] = None
        state["skip_opening_for_active"] = True
        flags = state.setdefault("stage_flags", {})
        flags["tutorial_stage_1_started"] = True
        for key in (
            "great_chase_unlocked",
            "great_chase_active",
            "great_chase_completed",
        ):
            flags.pop(key, None)
        game.story_title_card = None
        game.story_mission_card = None
        game.ui_mode = None

        mission_state = getattr(game, "mission_state", {})
        if isinstance(mission_state, dict):
            active = mission_state.get("active", {})
            removed_runtime_ids = set()
            if isinstance(active, dict):
                for runtime_id, runtime in list(active.items()):
                    context = runtime.get("source_context", {}) if isinstance(runtime, dict) else {}
                    if isinstance(context, dict) and context.get("source") == "story":
                        removed_runtime_ids.add(runtime_id)
                        active.pop(runtime_id, None)
            accepted = mission_state.get("accepted", [])
            if isinstance(accepted, list):
                mission_state["accepted"] = [
                    runtime_id for runtime_id in accepted if runtime_id not in removed_runtime_ids
                ]
            if mission_state.get("tracked") in removed_runtime_ids:
                mission_state["tracked"] = None
                game.tracked_mission = None

            target_mission = self.book.get("story_missions_by_id", {}).get(story_mission_id, {})
            target_runtime_ids = {
                str(scene.get("runtime_id") or scene.get("mission_id") or "").strip()
                for scene in target_mission.get("scenes", []) or []
                if scene.get("type") == "mission"
            }
            target_runtime_ids.discard("")
            for key in ("completed", "accepted", "unlocked"):
                values = mission_state.get(key, [])
                if isinstance(values, list):
                    mission_state[key] = [value for value in values if value not in target_runtime_ids]
            completed_data = mission_state.get("completed_data", {})
            if isinstance(completed_data, dict):
                for runtime_id in target_runtime_ids:
                    completed_data.pop(runtime_id, None)

        return self.start_story_mission(game, story_mission_id)

    def dev_skip_to_stage_5_transition(self, game):
        state = self._state(game)
        stages = list(self.book.get("stages", []) or [])
        prior_stages = [stage for stage in stages if int(stage.get("number", 0) or 0) <= 4]
        prior_missions = [
            mission.get("id")
            for stage in prior_stages
            for line in stage.get("lines", []) or []
            if line.get("role") == "major"
            for mission in line.get("missions", []) or []
            if mission.get("id")
        ]
        state["completed_story_missions"] = list(prior_missions)
        state["started_story_missions"] = list(prior_missions)
        state["completed_stages"] = [stage.get("id") for stage in prior_stages]
        state["started_stages"] = list(state["completed_stages"])
        state["unlocked_stages"] = list(state["completed_stages"])
        state["completed_lines"] = [
            line.get("id")
            for stage in prior_stages
            for line in stage.get("lines", []) or []
            if line.get("role") == "major" and line.get("id")
        ]
        state["active_stage"] = None
        state["active_line"] = None
        state["active_story_mission"] = None
        state["pending_dialogue"] = None
        state["title_card"] = None
        flags = state.setdefault("stage_flags", {})
        flags["tutorial_stage_1_started"] = True
        flags["great_chase_unlocked"] = True
        flags["great_chase_active"] = False
        flags["great_chase_completed"] = False
        flags["great_chase_guidance_complete"] = True
        game.story_title_card = None
        game.story_mission_card = None
        game.ui_mode = None
        controller = getattr(game, "chase_controller", None)
        if controller:
            controller.state = default_chase_state()
            controller.unlock_guidance(game)
        game.load_map("burnt_supply_route.json")
        game.player.x, game.player.y = (13, 8)
        return True

    def start_stage(self, game, stage_id, automatic=False):
        stage = self.book.get("stages_by_id", {}).get(str(stage_id))
        if not stage:
            return False
        state = self._state(game)
        if stage_id in state["completed_stages"]:
            return False
        if stage_id not in state["unlocked_stages"] and stage.get("requires"):
            return False
        if stage_id not in state["started_stages"]:
            state["started_stages"].append(stage_id)
        if stage_id not in state["unlocked_stages"]:
            state["unlocked_stages"].append(stage_id)
        first = self._first_available_story_mission(stage, state)
        if not first:
            return False
        line, story_mission = first
        state["active_stage"] = stage_id
        state["active_line"] = line.get("id")
        state["active_story_mission"] = story_mission.get("id")
        state["current_scene_index"] = 0
        state["skip_opening_for_active"] = False
        if story_mission.get("id") not in state["started_story_missions"]:
            state["started_story_missions"].append(story_mission.get("id"))
        scenes = self._active_scenes(stage, story_mission, state=state)
        return self._start_scene_at(game, stage, line, story_mission, scenes, 0)

    def start_story_mission(self, game, story_mission_id):
        state = self._state(game)
        story_mission = self.book.get("story_missions_by_id", {}).get(story_mission_id)
        if not story_mission or story_mission_id not in state["unlocked_story_missions"]:
            return False
        stage = self.book.get("stages_by_id", {}).get(story_mission.get("_stage_id"))
        line = self.book.get("lines_by_id", {}).get(story_mission.get("_line_id"))
        if not stage or not line:
            return False
        state["active_stage"] = stage.get("id")
        state["active_line"] = line.get("id")
        state["active_story_mission"] = story_mission_id
        state["current_scene_index"] = 0
        state["skip_opening_for_active"] = True
        if stage.get("id") not in state["started_stages"]:
            state["started_stages"].append(stage.get("id"))
        if story_mission_id not in state["started_story_missions"]:
            state["started_story_missions"].append(story_mission_id)
        scenes = self._active_scenes(stage, story_mission, state=state)
        return self._start_scene_at(
            game, stage, line, story_mission, scenes, 0, direct_dialogue=True
        )

    def advance_scene(self, game):
        state = self._state(game)
        story_mission = self.book.get("story_missions_by_id", {}).get(
            state.get("active_story_mission")
        )
        if not story_mission:
            return False
        stage = self.book.get("stages_by_id", {}).get(story_mission.get("_stage_id"))
        line = self.book.get("lines_by_id", {}).get(story_mission.get("_line_id"))
        scenes = self._active_scenes(stage, story_mission, state=state)
        next_index = int(state.get("current_scene_index", 0) or 0) + 1
        if next_index >= len(scenes):
            return self.complete_story_mission(game, story_mission.get("id"))
        state["current_scene_index"] = next_index
        return self._start_scene_at(game, stage, line, story_mission, scenes, next_index)

    def on_mission_completed(self, game, runtime_id):
        state = self._state(game)
        runtime_id = str(runtime_id or "")
        if runtime_id in state["notified_runtime_missions"]:
            return False
        active = getattr(game, "mission_state", {}).get("completed_data", {}).get(runtime_id)
        context = active.get("source_context", {}) if isinstance(active, dict) else {}
        if context.get("source") != "story":
            return False
        if context.get("story_mission_id") != state.get("active_story_mission"):
            return False
        state["notified_runtime_missions"].append(runtime_id)
        return self.advance_scene(game)

    def reconcile_runtime_completion(self, game):
        """Repair saves where runtime completion was recorded before story advancement."""
        state = self._state(game)
        story_mission = self.book.get("story_missions_by_id", {}).get(
            state.get("active_story_mission")
        )
        if not story_mission:
            return False
        stage = self.book.get("stages_by_id", {}).get(story_mission.get("_stage_id"))
        scenes = self._active_scenes(stage, story_mission, state=state)
        index = int(state.get("current_scene_index", 0) or 0)
        if not 0 <= index < len(scenes):
            return False
        scene = scenes[index]
        if scene.get("type") != "mission":
            return False
        runtime_id = str(scene.get("runtime_id") or scene.get("mission_id") or "").strip()
        mission_state = getattr(game, "mission_state", {}) or {}
        completed = set(mission_state.get("completed", []) or [])
        completed.update((mission_state.get("completed_data", {}) or {}).keys())
        if not runtime_id or runtime_id not in completed:
            return False
        if runtime_id not in state["notified_runtime_missions"]:
            state["notified_runtime_missions"].append(runtime_id)
        return self.advance_scene(game)

    def start_pending_dialogue_for_npc(self, game, npc_id):
        state = self._state(game)
        pending = state.get("pending_dialogue")
        if not isinstance(pending, dict):
            return False
        speaker = str(pending.get("speaker", "") or "").strip().lower()
        if speaker and speaker != str(npc_id or "").strip().lower():
            return False
        scene = self.book.get("scenes_by_id", {}).get(pending.get("scene_id"))
        if not isinstance(scene, dict) or scene.get("type") != "dialogue":
            return False
        state["pending_dialogue"] = None
        return story_scenes.play_dialogue_scene(game, scene)

    def next_unstarted_story_mission_for_npc(self, game, npc_id):
        state = self._state(game)
        npc_id = str(npc_id or "").strip().lower()
        if not npc_id:
            return None
        current_map = str(getattr(getattr(game, "map", None), "name", "") or "")
        preferred_stage = None
        if current_map in {"map_4.json", "map_5.json", "map_6.json", "new_ritc.json"}:
            preferred_stage = "stage_5"
        unlocked = state.get("unlocked_story_missions", [])
        started = set(state.get("started_story_missions", []) or [])
        completed = set(state.get("completed_story_missions", []) or [])
        matches = []
        for mission_id in unlocked:
            mission = self.book.get("story_missions_by_id", {}).get(mission_id)
            if not mission or mission_id in started or mission_id in completed:
                continue
            for scene in mission.get("scenes", []) or []:
                if str(scene.get("type", "")).strip() != "dialogue":
                    continue
                speaker = str(scene.get("speaker", "") or "").strip().lower()
                if speaker == npc_id:
                    matches.append(mission_id)
                break
        if preferred_stage:
            for mission_id in matches:
                mission = self.book.get("story_missions_by_id", {}).get(mission_id)
                if mission and mission.get("_stage_id") == preferred_stage:
                    return mission_id
        if matches:
            return matches[0]
        return None

    def complete_story_mission(self, game, story_mission_id):
        state = self._state(game)
        story_mission = self.book.get("story_missions_by_id", {}).get(story_mission_id)
        if not story_mission:
            return False
        newly_completed = story_mission_id not in state["completed_story_missions"]
        if newly_completed:
            state["completed_story_missions"].append(story_mission_id)
        for unlock_id in story_mission.get("unlocks", []) or []:
            self._unlock_id(state, unlock_id)
        line = self.book.get("lines_by_id", {}).get(story_mission.get("_line_id"))
        next_stage_id = None
        if line:
            next_stage_id = self._maybe_complete_line(state, line)
            next_mission = self._next_line_mission(line, story_mission_id)
            if next_mission:
                self._unlock_id(state, next_mission.get("id"))
        state["active_story_mission"] = None
        state["active_line"] = None
        state["active_stage"] = None
        state["current_scene_index"] = 0
        state["skip_opening_for_active"] = False
        game.ui_mode = None
        if hasattr(game, "push_message"):
            game.push_message(f"Story mission complete: {story_mission.get('number', story_mission_id)}")
        if story_mission_id == "story_4_1_10":
            self._activate_great_chase(game, state, show_card=newly_completed)
        if next_stage_id:
            return self.start_stage(game, next_stage_id, automatic=True)
        return True

    def _activate_great_chase(self, game, state, show_card=False):
        flags = state.setdefault("stage_flags", {})
        flags["great_chase_unlocked"] = True
        if not flags.get("great_chase_completed"):
            flags["great_chase_active"] = True
        flags.setdefault("great_chase_guidance_complete", False)
        controller = getattr(game, "chase_controller", None)
        if controller and controller.state.get("phase") == "LOCKED":
            controller.state["phase"] = "KALTSIT_GUIDANCE"
        if show_card and hasattr(game, "show_story_mission_card"):
            game.show_story_mission_card("生死奔襲", number="TRANSIT")
        return True

    def ready_runtime_for_npc(self, game, npc_id):
        state = self._state(game)
        story_mission_id = state.get("active_story_mission")
        story_mission = self.book.get("story_missions_by_id", {}).get(story_mission_id)
        if not story_mission:
            return None
        stage = self.book.get("stages_by_id", {}).get(story_mission.get("_stage_id"))
        scenes = self._active_scenes(stage, story_mission, state=state)
        scene_index = int(state.get("current_scene_index", 0) or 0)
        if scene_index < 0 or scene_index >= len(scenes):
            return None
        current_scene = scenes[scene_index]
        if current_scene.get("type") != "mission":
            return None
        next_scene = scenes[scene_index + 1] if scene_index + 1 < len(scenes) else {}
        if next_scene.get("type") == "dialogue":
            speaker = str(next_scene.get("speaker", "") or "").strip().lower()
            if speaker and speaker != str(npc_id or "").strip().lower():
                return None
        runtime_id = str(
            current_scene.get("runtime_id") or current_scene.get("mission_id") or ""
        ).strip()
        runtime = (
            getattr(game, "mission_state", {}).get("active", {}).get(runtime_id)
            if runtime_id
            else None
        )
        if not isinstance(runtime, dict):
            return None
        context = runtime.get("source_context", {})
        if not isinstance(context, dict) or context.get("source") != "story":
            return None
        if context.get("story_mission_id") != story_mission_id:
            return None
        if not game_missions.is_ready_to_turn_in(runtime):
            return None
        return runtime_id

    def complete_stage(self, game, stage_id):
        state = self._state(game)
        if stage_id not in state["completed_stages"]:
            state["completed_stages"].append(stage_id)
        return True

    def complete_great_chase(self, game):
        state = self._state(game)
        flags = state.setdefault("stage_flags", {})
        flags["great_chase_unlocked"] = True
        flags["great_chase_active"] = False
        flags["great_chase_completed"] = True
        stage_5 = self.book.get("stages_by_id", {}).get("stage_5")
        if stage_5:
            self._unlock_id(state, "stage_5")
            for line in stage_5.get("lines", []) or []:
                if line.get("role") != "major":
                    continue
                missions = line.get("missions", []) or []
                if missions:
                    self._unlock_id(state, missions[0].get("id"))
                break
        return True

    def get_stage_status(self, game, stage_id):
        state = self._state(game)
        if stage_id in state["completed_stages"]:
            return "completed"
        if stage_id == state.get("active_stage") or stage_id in state["started_stages"]:
            return "active"
        if stage_id in state["unlocked_stages"]:
            return "available"
        return "locked"

    def can_start_stage(self, game, stage_id):
        state = self._state(game)
        if stage_id in state["completed_stages"]:
            return False
        return stage_id in state["unlocked_stages"] or not self.book.get("stages_by_id", {}).get(stage_id, {}).get("requires")

    def _state(self, game):
        game.story_state = normalize_story_state(
            getattr(game, "story_state", None), self.book
        )
        self._reconcile_story_progress(game.story_state)
        return game.story_state

    def _reconcile_story_progress(self, state):
        completed = set(state.get("completed_story_missions", []))
        unlocked = state.setdefault("unlocked_story_missions", [])
        for line in self.book.get("lines_by_id", {}).values():
            missions = line.get("missions", []) or []
            for index, mission in enumerate(missions[:-1]):
                if mission.get("id") not in completed:
                    continue
                next_id = missions[index + 1].get("id")
                if next_id and next_id not in completed and next_id not in unlocked:
                    unlocked.append(next_id)
        if "story_4_1_10" in completed:
            flags = state.setdefault("stage_flags", {})
            flags["great_chase_unlocked"] = True
            if not flags.get("great_chase_completed"):
                flags["great_chase_active"] = True
        flags = state.setdefault("stage_flags", {})
        if (
            not flags.get("great_chase_completed")
            and "stage_5" not in state.get("started_stages", [])
            and "stage_5" not in state.get("completed_stages", [])
        ):
            state["unlocked_stages"] = [
                stage_id
                for stage_id in state.get("unlocked_stages", [])
                if stage_id != "stage_5"
            ]

    def _first_available_story_mission(self, stage, state):
        for line in stage.get("lines", []) or []:
            for mission in line.get("missions", []) or []:
                mid = mission.get("id")
                if mid in state["completed_story_missions"]:
                    continue
                if mid in state["unlocked_story_missions"] or not mission.get("requires"):
                    return line, mission
        return None

    def _active_scenes(self, stage, story_mission, state=None):
        scenes = []
        skip_opening = bool((state or {}).get("skip_opening_for_active", False))
        if not skip_opening and int(story_mission.get("_scene_started_with_opening", 0) or 0) == 0:
            scenes.extend(stage.get("opening_scenes", []) or [])
        scenes.extend(story_mission.get("scenes", []) or [])
        return scenes

    def _start_scene_at(
        self, game, stage, line, story_mission, scenes, index, direct_dialogue=False
    ):
        if not scenes:
            return self.complete_story_mission(game, story_mission.get("id"))
        scene = scenes[index]
        return story_scenes.start_scene(
            game,
            self.book,
            game.story_state,
            stage,
            line,
            story_mission,
            scene,
            direct_dialogue=direct_dialogue,
        )

    def _unlock_id(self, state, unlock_id):
        unlock_id = str(unlock_id or "")
        if unlock_id in self.book.get("story_missions_by_id", {}):
            if unlock_id not in state["unlocked_story_missions"]:
                state["unlocked_story_missions"].append(unlock_id)
        elif unlock_id in self.book.get("stages_by_id", {}):
            if unlock_id not in state["unlocked_stages"]:
                state["unlocked_stages"].append(unlock_id)

    def _maybe_complete_line(self, state, line):
        missions = line.get("missions", []) or []
        if missions and all(
            m.get("id") in state["completed_story_missions"] for m in missions
        ):
            line_id = line.get("id")
            if line_id not in state["completed_lines"]:
                state["completed_lines"].append(line_id)
            for unlock_id in line.get("unlocks", []) or []:
                self._unlock_id(state, unlock_id)
            stage = self.book.get("stages_by_id", {}).get(line.get("_stage_id"))
            if stage and line.get("role") == "major":
                stage_id = stage.get("id")
                if stage_id not in state["completed_stages"]:
                    state["completed_stages"].append(stage_id)
                self._unlock_stage_side_lines(state, stage)
                return self._unlock_next_stage_major(state, stage)
        return None

    def _unlock_stage_side_lines(self, state, stage):
        for line in stage.get("lines", []) or []:
            if line.get("role") == "major":
                continue
            missions = line.get("missions", []) or []
            if missions:
                self._unlock_id(state, missions[0].get("id"))

    def _next_line_mission(self, line, story_mission_id):
        missions = line.get("missions", []) or []
        for idx, mission in enumerate(missions):
            if mission.get("id") == story_mission_id and idx + 1 < len(missions):
                return missions[idx + 1]
        return None

    def _unlock_next_stage_major(self, state, stage):
        stages = self.book.get("stages", []) or []
        for idx, row in enumerate(stages):
            if row.get("id") != stage.get("id") or idx + 1 >= len(stages):
                continue
            next_stage = stages[idx + 1]
            if stage.get("id") == "stage_4" and next_stage.get("id") == "stage_5":
                state.setdefault("stage_flags", {})["great_chase_unlocked"] = True
                return None
            if next_stage.get("id") not in state["unlocked_stages"]:
                state["unlocked_stages"].append(next_stage.get("id"))
            for line in next_stage.get("lines", []) or []:
                if line.get("role") != "major":
                    continue
                missions = line.get("missions", []) or []
                if missions:
                    self._unlock_id(state, missions[0].get("id"))
                return next_stage.get("id")
        return None
