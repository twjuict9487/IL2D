import math
import os

from ..support.i18n import tr
from ..support.utils import GAME_DATA_DIR, load_json


CHASE_MAP = "the_great_chase_01.json"
PLAY_STATES = {"SAFE_CAMPFIRE", "SAVE_REQUIRED", "ARMED", "OPENING_RUN", "MONSTER_CHASE"}
LOCKED_STATES = {"ARRIVAL", "PNG_SCENE", "MUSIC_OUTRO", "STAGE_5_CARD", "COMPLETE"}


def _default_config():
    return {
        "id": "stage_4_to_5",
        "map": CHASE_MAP,
        "stage_5_map": "map_4.json",
        "music": "Sewer Creature.mp3",
        "campfire": [6, 5],
        "save_trigger_x": 15,
        "chase_start_x": 16,
        "monster_release_x": 350,
        "final_trigger_x": 2222,
        "player_tiles_per_second": 16.6667,
        "opening_segment": [0.0, 20.0],
        "scene_segment": [132.0, 153.0],
        "outro_segment": [153.0, 169.2],
        "presentation_file": "tgc_presentation.json",
        "warning_seconds": 3.0,
        "monster_start_gap": 4.0,
        "monster_contact_lead": 1.0,
        "danger_distance": 8.0,
        "progress_bar_fade_seconds": 0.5,
        "monster_distance_speeds": [
            {"max_distance": 8.0, "ratio": 0.95},
            {"max_distance": 20.0, "ratio": 1.0},
            {"max_distance": 60.0, "inclusive": False, "ratio": 1.05},
            {"ratio": 2.0},
        ],
    }


def load_config(path=None):
    config = _default_config()
    path = path or os.path.join(GAME_DATA_DIR, "transition_chases.json")
    try:
        raw = load_json(path)
        rows = raw.get("chases", raw) if isinstance(raw, dict) else {}
        row = rows.get("stage_4_to_5", {}) if isinstance(rows, dict) else {}
        if isinstance(row, dict):
            config.update(row)
    except Exception as exc:
        print(f"[chase] config fallback: {exc}")
    return config


def default_state():
    return {
        "phase": "LOCKED",
        "checkpoint_authorized": False,
        "checkpoint_slot": None,
        "opening_music_active": False,
        "forced_run_active": False,
        "monster_released": False,
        "monster_x": 0.0,
        "music_logical_position": 0.0,
        "warning_timer": 0.0,
        "scene_timer": 0.0,
        "presentation_started": False,
        "transition_completed": False,
        "move_accumulator": 0.0,
        "save_context": False,
    }


class ChaseTransitionController:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.state = default_state()

    @property
    def map_name(self):
        return str(self.config.get("map", CHASE_MAP))

    def is_chase_map(self, game):
        return getattr(getattr(game, "map", None), "name", None) == self.map_name

    def is_input_locked(self):
        return self.state.get("phase") in LOCKED_STATES

    def is_forced_run(self):
        return bool(self.state.get("forced_run_active"))

    def is_presentation_ready(self):
        fade_seconds = max(
            0.0, float(self.config.get("progress_bar_fade_seconds", 0.5))
        )
        return (
            self.state.get("phase") == "PNG_SCENE"
            and float(self.state.get("scene_timer", 0.0)) >= fade_seconds
        )

    def get_spatial_progress(self, game):
        if not self.is_chase_map(game):
            return None
        phase = self.state.get("phase")
        if phase not in {"OPENING_RUN", "MONSTER_CHASE", "PNG_SCENE"}:
            return None
        if getattr(game, "chase_death_pending", False) or getattr(game.player, "hp", 0) <= 0:
            return None
        alpha = 1.0
        if phase == "PNG_SCENE":
            fade_seconds = max(
                0.001, float(self.config.get("progress_bar_fade_seconds", 0.5))
            )
            alpha = max(
                0.0,
                1.0 - float(self.state.get("scene_timer", 0.0)) / fade_seconds,
            )
            if alpha <= 0.0:
                return None
        start_x = float(self.config.get("chase_start_x", 16))
        end_x = float(self.config.get("final_trigger_x", 2222))
        span = max(1.0, end_x - start_x)
        if hasattr(game, "get_player_draw_pos"):
            player_x = float(game.get_player_draw_pos()[0])
        else:
            player_x = float(game.player.x)
        player_progress = max(0.0, min(1.0, (player_x - start_x) / span))
        monster_visible = bool(self.state.get("monster_released"))
        contact_lead = float(self.config.get("monster_contact_lead", 1.0))
        monster_leading_edge_x = float(self.state.get("monster_x", 0.0)) + contact_lead
        monster_progress = max(
            0.0, min(1.0, (monster_leading_edge_x - start_x) / span)
        )
        danger_distance = max(0.0, float(self.config.get("danger_distance", 8.0)))
        return {
            "visible": player_x >= start_x,
            "alpha": alpha,
            "start_x": start_x,
            "end_x": end_x,
            "player_x": player_x,
            "player_progress": player_progress,
            "completion_percent": player_progress * 100.0,
            "remaining_tiles": max(0, int(math.ceil(end_x - player_x))),
            "monster_visible": monster_visible,
            "monster_leading_edge_x": monster_leading_edge_x,
            "monster_progress": monster_progress,
            "danger": monster_visible
            and player_x - monster_leading_edge_x <= danger_distance,
        }

    def serialize(self):
        return {
            "phase": self.state.get("phase", "LOCKED"),
            "checkpoint_authorized": bool(self.state.get("checkpoint_authorized")),
            "checkpoint_slot": self.state.get("checkpoint_slot"),
            "transition_completed": bool(self.state.get("transition_completed")),
        }

    def restore(self, game, payload):
        restored = default_state()
        if isinstance(payload, dict):
            restored["checkpoint_authorized"] = bool(
                payload.get("checkpoint_authorized", False)
            )
            slot = payload.get("checkpoint_slot")
            restored["checkpoint_slot"] = int(slot) if str(slot or "").isdigit() else None
            restored["transition_completed"] = bool(
                payload.get("transition_completed", False)
            )
        self.state = restored
        if self.is_chase_map(game):
            self.reset_to_campfire(game, preserve_checkpoint=True)
        elif restored["transition_completed"]:
            self.state["phase"] = "COMPLETE"

    def unlock_guidance(self, game):
        self.state["phase"] = "KALTSIT_GUIDANCE"
        flags = getattr(game, "story_state", {}).setdefault("stage_flags", {})
        flags["great_chase_unlocked"] = True
        flags["great_chase_guidance_complete"] = True
        return True

    def enter_map(self, game):
        keep_authorized = bool(self.state.get("checkpoint_authorized"))
        keep_slot = self.state.get("checkpoint_slot")
        keep_complete = bool(self.state.get("transition_completed"))
        self.state = default_state()
        self.state["checkpoint_authorized"] = keep_authorized
        self.state["checkpoint_slot"] = keep_slot
        self.state["transition_completed"] = keep_complete
        self.state["phase"] = "ARMED" if keep_authorized else "SAFE_CAMPFIRE"
        flags = getattr(game, "story_state", {}).setdefault("stage_flags", {})
        flags["great_chase_active"] = True
        self.state["opening_music_active"] = True
        if hasattr(game, "player"):
            game.player.x, game.player.y = game.map.spawn
        self._play_segment(game, *self.config.get("opening_segment", [0.0, 20.0]), loop=True)

    def leave_map(self, game):
        if self.state.get("phase") not in {"LOCKED", "COMPLETE"}:
            self._stop_music(game, 100)
        self.state["opening_music_active"] = False
        self.state["forced_run_active"] = False
        self.state["monster_released"] = False
        self.state["save_context"] = False

    def reset_to_campfire(self, game, preserve_checkpoint=True):
        authorized = bool(self.state.get("checkpoint_authorized")) if preserve_checkpoint else False
        slot = self.state.get("checkpoint_slot") if preserve_checkpoint else None
        completed = bool(self.state.get("transition_completed"))
        self.state = default_state()
        self.state["checkpoint_authorized"] = authorized
        self.state["checkpoint_slot"] = slot
        self.state["transition_completed"] = completed
        self.state["phase"] = "ARMED" if authorized else "SAFE_CAMPFIRE"
        self.state["opening_music_active"] = True
        if hasattr(game, "player"):
            campfire = self.config.get("campfire", [7, 5])
            game.player.x = max(1, int(campfire[0]) - 1)
            game.player.y = int(campfire[1])
            game.player.hp = max(1, game.player.max_hp)
            game.player.mp = game.player.max_mp
        game.ui_mode = None
        self._play_segment(game, *self.config.get("opening_segment", [0.0, 20.0]), loop=True)

    def try_interact(self, game):
        if not self.is_chase_map(game) or self.state.get("forced_run_active"):
            return False
        campfire = self.config.get("campfire", [7, 5])
        distance = abs(int(game.player.x) - int(campfire[0])) + abs(
            int(game.player.y) - int(campfire[1])
        )
        if distance > 1:
            return False
        self.state["save_context"] = True
        self.state["phase"] = "SAVE_REQUIRED"
        game.open_save()
        game.request_open_save_menu = True
        return True

    def on_save_result(self, game, slot, success):
        from_campfire = bool(self.state.get("save_context")) and self.is_chase_map(game)
        self.state["save_context"] = False
        if not success or not from_campfire:
            return False
        self.state["checkpoint_authorized"] = True
        self.state["checkpoint_slot"] = int(slot)
        self.state["phase"] = "ARMED"
        if hasattr(game, "push_message"):
            game.push_message(tr(game.lang, "chase.checkpoint_saved"))
        return True

    def cancel_save(self):
        self.state["save_context"] = False
        if self.state.get("phase") == "SAVE_REQUIRED":
            self.state["phase"] = (
                "ARMED" if self.state.get("checkpoint_authorized") else "SAFE_CAMPFIRE"
            )

    def transform_player_move(self, game, dx, dy, forced=False):
        if not self.is_chase_map(game):
            return dx, dy
        if self.is_input_locked():
            return None
        if forced:
            return 1, 0
        if self.is_forced_run():
            if dy:
                return 0, 1 if dy > 0 else -1
            return None
        next_x = int(game.player.x) + dx
        save_gate_x = int(self.config.get("save_trigger_x", 15))
        chase_start_x = int(self.config.get("chase_start_x", save_gate_x + 1))
        if dx > 0 and next_x >= save_gate_x:
            if not self.state.get("checkpoint_authorized"):
                if hasattr(game, "push_message"):
                    game.push_message(tr(game.lang, "chase.save_required"))
                return None
        if dx > 0 and next_x >= chase_start_x:
            self._start_run(game)
            return None
        return dx, dy

    def update(self, game, dt):
        if not self.is_chase_map(game):
            return False
        dt = max(0.0, min(0.1, float(dt or 0.0)))
        phase = self.state.get("phase")
        if phase in {"SAFE_CAMPFIRE", "SAVE_REQUIRED", "ARMED"}:
            self._update_segment(game)
            return True
        if phase in {"OPENING_RUN", "MONSTER_CHASE"}:
            self.state["music_logical_position"] += dt
            self.state["warning_timer"] = max(0.0, self.state["warning_timer"] - dt)
            speed = max(0.1, float(self.config.get("player_tiles_per_second", 16.6667)))
            self.state["move_accumulator"] += speed * dt
            while self.state["move_accumulator"] >= 1.0:
                self.state["move_accumulator"] -= 1.0
                game._chase_forced_step = True
                try:
                    game.request_player_move(1, 0)
                finally:
                    game._chase_forced_step = False
            if int(game.player.x) >= int(self.config.get("monster_release_x", 345)):
                self._release_monster(game)
            if self.state.get("monster_released"):
                distance = float(game.player.x) - float(self.state["monster_x"])
                ratio = self._monster_ratio(distance)
                self.state["monster_x"] += speed * ratio * dt
                lead = float(self.config.get("monster_contact_lead", 1.0))
                if self.state["monster_x"] + lead >= float(game.player.x):
                    self.kill_player(game)
                    return True
            if int(game.player.x) >= int(self.config.get("final_trigger_x", 2212)):
                self._start_arrival(game)
            return True
        if phase == "PNG_SCENE":
            self.state["scene_timer"] += dt
            scene = self.config.get("scene_segment", [132.0, 153.0])
            if self.state["scene_timer"] >= max(0.1, float(scene[1]) - float(scene[0])):
                self._finish(game)
            return True
        if phase == "MUSIC_OUTRO":
            self.state["scene_timer"] += dt
            outro = self.config.get("outro_segment", [153.0, 169.2])
            if self.state["scene_timer"] >= max(0.1, float(outro[1]) - float(outro[0])):
                self._finish(game)
            return True
        return phase in LOCKED_STATES

    def kill_player(self, game):
        self._stop_music(game, 250)
        self.state["forced_run_active"] = False
        game.player.hp = 0
        game.chase_death_pending = True
        game.check_player_death()

    def retry_from_checkpoint(self, game):
        slot = self.state.get("checkpoint_slot")
        if not slot:
            return False
        if not game.load_save(int(slot)):
            return False
        self.reset_to_campfire(game, preserve_checkpoint=True)
        return True

    def _start_run(self, game):
        self.state["phase"] = "OPENING_RUN"
        self.state["forced_run_active"] = True
        self.state["music_logical_position"] = float(
            self.config.get("opening_segment", [0.0, 20.0])[1]
        )

    def _release_monster(self, game):
        if self.state.get("monster_released"):
            return
        self.state["phase"] = "MONSTER_CHASE"
        self.state["monster_released"] = True
        self.state["monster_x"] = float(game.player.x) - float(
            self.config.get("monster_start_gap", 22.0)
        )
        self.state["warning_timer"] = float(self.config.get("warning_seconds", 3.0))
        opening_end = float(self.config.get("opening_segment", [0.0, 20.0])[1])
        self.state["music_logical_position"] = opening_end
        audio = getattr(game, "audio", None)
        if audio and hasattr(audio, "play_bgm_segment"):
            audio.play_bgm_segment(self.config.get("music"), opening_end, None, loop=False)

    def _start_arrival(self, game):
        self.state["phase"] = "PNG_SCENE"
        self.state["forced_run_active"] = False
        self.state["scene_timer"] = 0.0
        self.state["presentation_started"] = False
        self._stop_music(game, 100)

    def complete_presentation(self, game):
        if self.state.get("phase") != "PNG_SCENE":
            return False
        self._finish(game)
        return True

    def _start_outro(self, game):
        self.state["phase"] = "MUSIC_OUTRO"
        self.state["scene_timer"] = 0.0
        outro = self.config.get("outro_segment", [153.0, 169.2])
        self._play_segment(game, float(outro[0]), float(outro[1]), loop=False)

    def _finish(self, game):
        self._stop_music(game, 0)
        self.state["phase"] = "COMPLETE"
        self.state["transition_completed"] = True
        game.load_map(self.config.get("stage_5_map", "map_4.json"))
        game.player.x, game.player.y = game.map.spawn
        manager = getattr(game, "story_manager", None)
        if manager:
            manager.complete_great_chase(game)

    def _monster_ratio(self, distance):
        for band in self.config.get("monster_distance_speeds", []) or []:
            limit = band.get("max_distance")
            if limit is None:
                return max(0.0, float(band.get("ratio", 1.0)))
            inclusive = bool(band.get("inclusive", True))
            if distance < float(limit) or (inclusive and distance == float(limit)):
                return max(0.0, float(band.get("ratio", 1.0)))
        return 2.0

    def _play_segment(self, game, start, end, loop=False):
        audio = getattr(game, "audio", None)
        if audio and hasattr(audio, "play_bgm_segment"):
            audio.play_bgm_segment(
                self.config.get("music"), float(start), float(end), loop=loop
            )

    def _update_segment(self, game):
        audio = getattr(game, "audio", None)
        if audio and hasattr(audio, "update_bgm_segment"):
            audio.update_bgm_segment()

    def _stop_music(self, game, fade_ms):
        audio = getattr(game, "audio", None)
        if audio:
            audio.stop_bgm(fadeout_ms=fade_ms)
        game.current_music = None
