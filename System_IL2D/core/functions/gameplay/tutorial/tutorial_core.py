import random
import time

from ...models.entity import Entity
from ...support.i18n import tr
from ...world.map import mobs_data
from .tutorial_steps import build_tutorial_steps


class GameplayTutorialCore:
    def __init__(self, lang="zh"):
        self.lang = lang
        self.steps = build_tutorial_steps(lang)
        self.active = False
        self.step_index = 0
        self.data = {}
        self._baseline = {}
        self._finish_countdown_start = None
        self._finish_countdown_secs = 5.0

    def start(self, game):
        self.active = True
        self.step_index = 0
        self.data = {
            "move_count": 0,
            "kill_1": 0,
            "talked_npc": False,
            "esc_opened": False,
            "esc_closed": False,
        }
        self._baseline = {
            "level": int(getattr(game, "player_level", 1)),
            "exp": int(getattr(game, "player_exp", 0)),
            "skill_points": int(getattr(game, "player_skill_points", 0)),
            "money": int(getattr(game, "money", 0)),
            "inventory": dict(getattr(game, "inventory", {})),
            "equipment": dict(getattr(game, "equipment", {})),
            "item_hotbar_slots": list(getattr(game, "item_hotbar_slots", [None] * 10)),
            "magic_hotbar_slots": list(getattr(game, "magic_hotbar_slots", [None] * 10)),
        }
        self._finish_countdown_start = None
        self._enter_step(game)

    def current_id(self):
        if not self.active or self.step_index >= len(self.steps):
            return None
        return self.steps[self.step_index]["id"]

    def update(self, game, _dt):
        if not self.active:
            return
        sid = self.current_id()
        if sid != "finish_reset":
            return
        if self._finish_countdown_start is None:
            self._finish_countdown_start = time.time()
            return
        left = self._finish_countdown_secs - (time.time() - self._finish_countdown_start)
        if left > 0:
            return
        self._apply_finish_reset(game)
        game.start_blackout()
        self.active = False

    def get_ui_payload(self):
        if not self.active:
            return None
        if self.step_index < 0 or self.step_index >= len(self.steps):
            return None
        step = self.steps[self.step_index]
        sid = step.get("id", "")
        progress = self._progress_text(sid)
        left = None
        if sid == "finish_reset" and self._finish_countdown_start is not None:
            left = max(0, int(self._finish_countdown_secs - (time.time() - self._finish_countdown_start)) + 1)
        return {
            "speaker": tr(self.lang, "tutorial.dev.speaker"),
            "title": tr(self.lang, step.get("title_key", "tutorial.dev.step.1.title")),
            "hint": tr(self.lang, step.get("hint_key", "tutorial.dev.step.1.hint")),
            "progress": progress,
            "countdown": left,
        }

    def _progress_text(self, sid):
        if sid == "move_basic":
            return f"{min(4, self.data.get('move_count', 0))}/4"
        if sid == "kill_wave_1":
            return f"{min(5, self.data.get('kill_1', 0))}/5"
        if sid == "npc_intro":
            return tr(self.lang, "tutorial.dev.done") if self.data.get("talked_npc", False) else tr(self.lang, "tutorial.dev.todo")
        if sid == "esc_open":
            return tr(self.lang, "tutorial.dev.done") if self.data.get("esc_opened", False) else tr(self.lang, "tutorial.dev.todo")
        if sid == "esc_close":
            return tr(self.lang, "tutorial.dev.done") if self.data.get("esc_closed", False) else tr(self.lang, "tutorial.dev.todo")
        return ""

    def notify(self, game, event_name, **kwargs):
        if not self.active:
            return
        sid = self.current_id()
        if sid is None:
            return

        if sid == "move_basic" and event_name == "move_key":
            self.data["move_count"] += 1
            if self.data["move_count"] >= 4:
                self._advance(game)
            return

        if sid == "kill_wave_1" and event_name == "enemy_killed":
            self.data["kill_1"] += 1
            if self.data["kill_1"] >= 5:
                self._advance(game)
            return

        if sid == "npc_intro" and event_name == "npc_interact":
            self.data["talked_npc"] = True
            self._advance(game)
            return

        if sid == "esc_open" and event_name == "esc_open":
            self.data["esc_opened"] = True
            self._advance(game)
            return
        if sid == "esc_close" and event_name == "esc_close":
            self.data["esc_closed"] = True
            self._advance(game)
            return

    def forced_drop_bonus(self, game, ent):
        if not self.active or self.current_id() != "kill_wave_1":
            return None
        idx = int(self.data.get("kill_1", 0))
        if idx >= 5:
            return None
        item_name = "health potion (small)" if idx % 2 == 0 else "magic potion (small)"
        return {"money": 20, "items": [(item_name, 1)]}

    def _enter_step(self, game):
        sid = self.current_id()
        if sid is None:
            return
        if sid == "combat_intro":
            self._advance(game)
            return
        if sid == "kill_wave_1":
            self._spawn_training_wave(game, count=5)
        if sid == "finish_reset":
            self._finish_countdown_start = time.time()

    def _advance(self, game):
        self.step_index += 1
        if self.step_index >= len(self.steps):
            self.active = False
            return
        self._enter_step(game)

    def _spawn_training_wave(self, game, count=5):
        hostile_ids = [k for k, v in mobs_data.items() if isinstance(v, dict) and v.get("ai_type") == "hostile"]
        if not hostile_ids:
            return
        mob_id = "slime" if "slime" in hostile_ids else hostile_ids[0]
        mob = mobs_data.get(mob_id, {})
        placed = 0
        tries = 0
        while placed < int(count) and tries < 300:
            tries += 1
            nx = game.player.x + random.randint(-4, 4)
            ny = game.player.y + random.randint(-4, 4)
            if nx < 0 or ny < 0 or nx >= game.map.w or ny >= game.map.h:
                continue
            if not game.map.is_walkable(nx, ny):
                continue
            if game.entity_at(nx, ny):
                continue
            ent = Entity(
                mob_id,
                nx,
                ny,
                mob.get("hp", 20),
                mob.get("mp", 0),
                mob.get("attack", 6),
                mob.get("defence", 0),
                ai_type=mob.get("ai_type", "hostile"),
                immortal=mob.get("immortal", False),
            )
            game.entities.append(ent)
            placed += 1

    def _apply_finish_reset(self, game):
        base = self._baseline
        game.player_level = int(base.get("level", 1))
        game.player_exp = int(base.get("exp", 0))
        game.player_skill_points = int(base.get("skill_points", 0))
        game.money = int(base.get("money", 0))
        game.inventory = dict(base.get("inventory", {}))
        game.equipment = dict(base.get("equipment", {}))
        game.item_hotbar_slots = list(base.get("item_hotbar_slots", [None] * 10))
        game.magic_hotbar_slots = list(base.get("magic_hotbar_slots", [None] * 10))
        game.recalculate_stats()
