import os
import random
import time
from collections import deque
from .map import GameMap, blocktypes, mobs_data, player_data, npc_data
from .entity import Entity
from .utils import MAP_DIR, DIALOG_DIR, SAVE_DIR, ITEMS_FILE, SHOP_FILE, SPELLS_FILE, OBJECTIVES_FILE, ROGUE_FILE, CONFIG_FILE, load_json, clamp
from .i18n import tr


class Game:
    def __init__(self):
        self.load_map('map_1.json')
        pdata = player_data
        self.player = Entity(
            'player',
            *self.map.spawn,
            pdata['hp'],
            pdata.get('mp', 0),
            pdata.get('attack', 10),
            pdata.get('defence', 0),
            ai_type='player'
        )
        self.player_name = pdata.get('name', 'player')
        self.lang = pdata.get('lang', 'en')
        self.player.base_attack = self.player.attack
        self.player.base_defence = self.player.defence
        self.entities = [self.player]
        self.spawn_default_entities()
        self.place_npcs_for_map()

        self.tick = 0
        self.map_max_h_mob = self.map.mob_limit
        self.spawn_interval = 4.0
        self.spawn_timer = 0.0
        self.camera_x = self.player.x
        self.camera_y = self.player.y
        self.blackout = 0  # 0: normal, 1: fade out, 2: fade in
        self.black_alpha = 0

        self.message_queue = deque()
        self.message_show_time = 2.0
        self.message_fade_time = 2.0

        self.ui_mode = None  # None, dialog, shop, save, equip, item, magic, objective, status, leave_confirm
        self.dialog_data = None
        self.dialog_node = None
        self.dialog_selected = 0
        self.active_npc = None

        self.shop_selected = 0
        self.save_selected = 0
        self.equip_selected = 0
        self.equip_category_selected = 0
        self.equip_category = "weapon"
        self.item_selected = 0
        self.magic_selected = 0
        self.leave_step = 0
        self.leave_selected = 0
        self.request_quit = False

        self.money = 0
        self.inventory = {
            'health potion (small)': 0,
            'magic potion (small)': 0,
            'revive ring': 0,
            'barry': 0,
            'retreat item': 0
        }
        self.equipment = {
            'weapon': None,
            'armor': None,
            'ring1': None,
            'ring2': None,
            'ring3': None,
            'ring4': None,
            'ring5': None,
            'ring6': None
        }
        self.objectives = ["Find the dev", "Try the shop"]
        self.spells = []
        self.item_defs = {}
        self.shop_items = []
        self.last_saved = False
        self.last_save_slot = None
        self.bush_regrow = {}
        self.rogue_layer = 0
        self.rogue_is_boss = False
        self.rogue_target_mobs = 0
        self.transition_active = False
        self.transition_timer = 0.0
        self.transition_duration = 1.0
        self.transition_mid_done = False
        self.transition_action = None
        self.banner = None

        if not os.path.isdir(SAVE_DIR):
            os.makedirs(SAVE_DIR, exist_ok=True)
        self.load_game_data()

    def load_game_data(self):
        cfg = load_json(CONFIG_FILE)
        self.spawn_interval = cfg.get("spawn_interval", self.spawn_interval)
        self.message_show_time = cfg.get("message_show_time", self.message_show_time)
        self.message_fade_time = cfg.get("message_fade_time", self.message_fade_time)
        self.transition_duration = cfg.get("transition_duration", self.transition_duration)
        self.leave_rogue_hp = cfg.get("leave_rogue_hp", 100)
        self.item_defs = load_json(ITEMS_FILE)
        self.shop_items = load_json(SHOP_FILE)
        self.spells = load_json(SPELLS_FILE)
        self.objectives_cfg = load_json(OBJECTIVES_FILE)
        self.rogue_cfg = load_json(ROGUE_FILE)

    def load_map(self, mapname):
        if mapname == "rogue":
            self.enter_rogue_layer(new_entry=True)
            return
        self.map = GameMap(os.path.join(MAP_DIR, mapname))
        self.map_max_h_mob = self.map.mob_limit
        if hasattr(self, "entities"):
            self.place_npcs_for_map()
        self.set_objectives_for_map()
        self.show_enter_banner(mapname)

    def place_npcs_for_map(self):
        positions = {
            "map_1.json": [(1, 8), (2, 8), (3, 8)],
            "map_2.json": [(2, 8), (3, 8), (4, 8)],
            "map_3.json": [(1, 8), (2, 8), (3, 8)],
            "rogue": [(1, 12), (1, 13)]
        }
        order = ["dev", "priestess", "carmen"]
        spots = positions.get(self.map.name, [])
        for i, npc_id in enumerate(order):
            ent = next((e for e in self.entities if e.eid == npc_id), None)
            if ent is None:
                data = npc_data.get(npc_id, {})
                ent = Entity(npc_id, 0, 0, data.get('hp', 1), data.get('mp', 0), data.get('attack', 0), data.get('defence', 0), data.get('ai_type'), data.get('immortal', False))
                self.entities.append(ent)
            if i < len(spots):
                ent.x, ent.y = spots[i]
            elif self.map.name == "rogue":
                ent.x, ent.y = -999, -999

    def spawn_default_entities(self):
        if 'slime' in mobs_data:
            sdata = mobs_data['slime']
            self.entities.append(
                Entity('slime', 2, 1, sdata['hp'], sdata.get('mp', 0), sdata.get('attack', 10), sdata.get('defence', 0), sdata.get('ai_type'), sdata.get('immortal', False))
            )
        if 'skeleton' in mobs_data:
            kdata = mobs_data['skeleton']
            self.entities.append(
                Entity('skeleton', 7, 1, kdata['hp'], kdata.get('mp', 0), kdata.get('attack', 10), kdata.get('defence', 0), kdata.get('ai_type'), kdata.get('immortal', False))
            )
        if 'zombie' in mobs_data:
            zdata = mobs_data['zombie']
            self.entities.append(
                Entity('zombie', 1, 6, zdata['hp'], zdata.get('mp', 0), zdata.get('attack', 10), zdata.get('defence', 0), zdata.get('ai_type'), zdata.get('immortal', False))
            )
        if 'soldier' in mobs_data:
            mdata = mobs_data['soldier']
            self.entities.append(
                Entity('soldier', 8, 6, mdata['hp'], mdata.get('mp', 0), mdata.get('attack', 10), mdata.get('defence', 0), mdata.get('ai_type'), mdata.get('immortal', False))
            )
        if 'dev' in npc_data:
            ddata = npc_data['dev']
            self.entities.append(
                Entity('dev', 2, 8, ddata.get('hp', 1), ddata.get('mp', 0), ddata.get('attack', 0), ddata.get('defence', 0), ddata.get('ai_type'), ddata.get('immortal', False))
            )
        if 'priestess' in npc_data:
            pdata = npc_data['priestess']
            self.entities.append(
                Entity('priestess', 4, 8, pdata.get('hp', 1), pdata.get('mp', 0), pdata.get('attack', 0), pdata.get('defence', 0), pdata.get('ai_type'), pdata.get('immortal', False))
            )
        if 'carmen' in npc_data:
            cdata = npc_data['carmen']
            self.entities.append(
                Entity('carmen', 6, 8, cdata.get('hp', 1), cdata.get('mp', 0), cdata.get('attack', 0), cdata.get('defence', 0), cdata.get('ai_type'), cdata.get('immortal', False))
            )

    def get_entity_def(self, eid):
        if eid in mobs_data:
            return mobs_data[eid]
        if eid in npc_data:
            return npc_data[eid]
        return {}

    def entity_at(self, x, y):
        for e in self.entities:
            size = getattr(e, "size", 1)
            if size > 1:
                if e.x <= x < e.x + size and e.y <= y < e.y + size and (e.immortal or e.hp > 0):
                    return e
            elif (e.x, e.y) == (x, y) and (e.immortal or e.hp > 0):
                return e
        return None

    def is_ui_blocking(self):
        return self.ui_mode is not None

    def request_player_move(self, dx, dy):
        if self.transition_active:
            return False
        if hasattr(self, 'death_timer') and self.death_timer is not None:
            return False
        if self.is_ui_blocking():
            return False
        nx, ny = self.player.x + dx, self.player.y + dy
        if not self.map.is_walkable(nx, ny):
            return False
        target = self.entity_at(nx, ny)
        if target and target.eid != 'player' and target.hp > 0:
            target_def = self.get_entity_def(target.eid)
            if target_def.get('ai_type') in ('friendly', 'neutral'):
                return False
            if getattr(target, "immortal", False):
                return False
            player_damage = max(0, int(self.player.attack * (1 - target.defence / 100)))
            enemy_damage = max(0, int(target.attack * (1 - self.player.defence / 100)))
            target.hp -= player_damage
            if target.hp <= 0:
                target.hp = -1
                self.player.x, self.player.y = nx, ny
                self.on_enemy_death(target)
                self.state_cleanup()
                self.update(player_tick=True)
                return True
            self.player.hp -= enemy_damage
            self.check_player_death()
            self.state_cleanup()
            return False
        self.player.x, self.player.y = nx, ny
        bt = self.map.get_block(nx, ny)
        if bt and 'on_step' in blocktypes[bt]:
            if blocktypes[bt]['on_step'] == 'portal':
                self.handle_portal_at(nx, ny)
            elif blocktypes[bt]['on_step'] == 'level_exit':
                self.handle_exit_tile()
        self.state_cleanup()
        self.update(player_tick=True)
        return True

    def handle_portal_at(self, x, y):
        if not getattr(self.map, "portals", None):
            return
        for p in self.map.portals:
            if p.get("x") == x and p.get("y") == y:
                target_map = p.get("target_map", "")
                target_spawn = p.get("target_spawn", None)
                if target_map:
                    if target_map == "rogue":
                        self.start_transition(self.enter_rogue_layer)
                    else:
                        def do_load():
                            self.load_map(target_map)
                            if target_spawn and len(target_spawn) == 2:
                                self.player.x, self.player.y = target_spawn
                            else:
                                self.player.x, self.player.y = self.map.spawn
                        self.start_transition(do_load)
                return

    def handle_exit_tile(self):
        if self.map.name != "rogue":
            self.start_blackout()
            return
        if self.count_hostile_mobs() > 0:
            self.show_dev_block()
            self.start_transition(self.reset_rogue_to_spawn)
        else:
            self.start_transition(self.enter_next_rogue_layer)

    def on_enemy_death(self, ent):
        mob = mobs_data.get(ent.eid, {})
        reward_money = mob.get('reward_money', {})
        reward_items = mob.get('reward_items', [])
        lines = [tr(self.lang, "reward.killed", name=ent.eid)]
        if reward_money:
            if isinstance(reward_money, dict):
                amount = reward_money.get("amount", 0)
                chance = 1.0
            else:
                amount = int(reward_money)
                chance = 1.0
            if amount and random.random() < chance:
                self.money += amount
                lines.append(tr(self.lang, "reward.dropped", text=f"{amount} robux"))
        dropped_items = []
        if reward_items:
            if isinstance(reward_items, dict):
                reward_items = [{"name": k, "count": v, "chance": 0.5} for k, v in reward_items.items()]
            for item in reward_items:
                name = item.get("name")
                count = item.get("count", 1)
                chance = 0.4
                if name and random.random() < chance:
                    self.inventory[name] = self.inventory.get(name, 0) + count
                    dropped_items.append(f"{name} x{count}")
        if dropped_items:
            lines.append(tr(self.lang, "reward.dropped", text=", ".join(dropped_items)))
        self.push_message_lines(lines)

    def push_message(self, text):
        self.message_queue.append({
            "text": text,
            "created": time.time()
        })

    def push_message_lines(self, lines):
        self.message_queue.append({
            "lines": lines,
            "created": time.time()
        })

    def state_cleanup(self):
        self.entities = [e for e in self.entities if e.eid == 'player' or e.immortal or e.hp > 0]

    def check_player_death(self):
        if self.player.hp <= 0:
            if self.map.name == "rogue":
                rate = self.rogue_cfg.get("death_penalty_rate", 0.2)
                self.money = int(self.money * (1 - rate))
                self.return_from_rogue()
                self.death_timer = None
                return
            if self.inventory.get('revive ring', 0) > 0:
                self.inventory['revive ring'] -= 1
                self.player.hp = self.player.max_hp
                self.push_message("revive ring broken!")
                self.death_timer = None
                return
            self.death_timer = 10.0
        else:
            self.death_timer = None

    def start_blackout(self):
        self.blackout = 1
        self.black_alpha = 0

    def update(self, player_tick=False):
        if self.is_ui_blocking():
            return
        if player_tick:
            self.tick += 1
            for ent in self.entities:
                if ent.eid != 'player':
                    self.update_enemy(ent)
            self.apply_recover_ring_tick()
            if self.map.name == "rogue" and not self.rogue_is_boss:
                self.rogue_target_mobs = 10
        self.camera_x = self.player.x
        self.camera_y = self.player.y
        if self.blackout == 1:
            self.black_alpha += 20
            if self.black_alpha >= 255:
                self.black_alpha = 255
                self.load_map('map_1.json')
                self.player.x, self.player.y = self.map.spawn
                self.blackout = 2
        elif self.blackout == 2:
            self.black_alpha -= 20
            if self.black_alpha <= 0:
                self.black_alpha = 0
                self.blackout = 0
        if player_tick:
            self.cleanup_messages()

    def update_time(self, dt):
        if self.transition_active:
            self.update_transition(dt)
            return
        if self.is_ui_blocking():
            return
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval and self.map.name != "rogue":
            self.spawn_timer = 0.0
            if self.count_hostile_mobs() < self.map_max_h_mob:
                self.spawn_random_hostile()
        self.update_bush_regrow()
        self.cleanup_messages()

    def apply_recover_ring_tick(self):
        ring_name = "recover ring"
        ring_def = self.item_defs.get(ring_name, {})
        per_hp = ring_def.get("per_tick_hp", 2)
        per_mp = ring_def.get("per_tick_mp", 1)
        count = sum(1 for slot, name in self.equipment.items() if slot.startswith("ring") and name == ring_name)
        if count <= 0:
            return
        self.player.hp = clamp(self.player.hp + per_hp * count, 0, self.player.max_hp)
        self.player.mp = clamp(self.player.mp + per_mp * count, 0, self.player.max_mp)

    def update_bush_regrow(self):
        if not self.bush_regrow:
            return
        now = time.time()
        current_map = self.map.name
        to_remove = []
        for (mname, x, y), t in self.bush_regrow.items():
            if mname != current_map:
                continue
            if now >= t:
                if 0 <= y < self.map.h and 0 <= x < self.map.w and self.map.grid[y][x] == "08":
                    self.map.grid[y][x] = "07"
                to_remove.append((mname, x, y))
        for key in to_remove:
            self.bush_regrow.pop(key, None)

    def count_hostile_mobs(self):
        count = 0
        for e in self.entities:
            if e.eid != 'player' and mobs_data.get(e.eid, {}).get('ai_type') == 'hostile' and e.hp > 0:
                count += 1
        return count

    def set_objectives_for_map(self):
        cfg = getattr(self, "objectives_cfg", {})
        if self.map.name == "rogue":
            lines = cfg.get("rogue", ["obj.rogue"])
            self.objectives = [tr(self.lang, s) if s.startswith("obj.") else s for s in lines]
        else:
            lines = cfg.get("default", ["Find the dev", "Try the shop"])
            self.objectives = [tr(self.lang, s) if s.startswith("obj.") else s for s in lines]

    def show_enter_banner(self, label):
        name = label.replace(".json", "")
        self.banner = {"text": f"Now entering: {name}", "created": time.time(), "duration": 3.0}

    def show_dev_block(self):
        self.dialog_data = {
            "start": "node_1",
            "node_1": {
                "text": "you have to kill everything in this layer before proceed, now go back and get killin",
                "responses": [{"text": "ok", "next": "end"}]
            }
        }
        self.dialog_node = "node_1"
        self.dialog_selected = 0
        self.active_npc = "dev"
        self.ui_mode = "dialog"

    def start_transition(self, action):
        self.transition_active = True
        self.transition_timer = 0.0
        self.transition_mid_done = False
        self.transition_action = action

    def update_transition(self, dt):
        self.transition_timer += dt
        half = self.transition_duration / 2.0
        if self.transition_timer >= half and not self.transition_mid_done:
            self.transition_mid_done = True
            if self.transition_action:
                self.transition_action()
        if self.transition_timer >= self.transition_duration:
            self.transition_active = False
            self.transition_action = None

    def reset_rogue_to_spawn(self):
        self.player.x, self.player.y = self.map.spawn

    def return_from_rogue(self):
        def do_return():
            self.load_map("map_2.json")
            self.player.x, self.player.y = self.map.spawn
            self.player.hp = getattr(self, "leave_rogue_hp", 100)
        self.start_transition(do_return)

    def enter_rogue_layer(self, new_entry=False):
        if new_entry:
            self.rogue_layer = 0
        self.rogue_layer += 1
        cfg = getattr(self, "rogue_cfg", {})
        boss_every = cfg.get("boss_every", 5)
        self.rogue_is_boss = (self.rogue_layer % boss_every == 0)
        size = cfg.get("boss_size", [10, 15]) if self.rogue_is_boss else cfg.get("normal_size", [20, 20])
        w, h = size[0], size[1]
        data = self.generate_rogue_map(w, h)
        self.map = GameMap.from_data("rogue", data)
        self.map_max_h_mob = self.map.mob_limit
        self.player.x, self.player.y = self.map.spawn
        self.place_npcs_for_map()
        self.set_objectives_for_map()
        layer_label = f"boss layer {self.rogue_layer}" if self.rogue_is_boss else f"layer {self.rogue_layer}"
        self.banner = {"text": f"Now entering {layer_label}", "created": time.time(), "duration": 3.0}
        retreat_name = cfg.get("retreat_item", "retreat item")
        self.inventory[retreat_name] = self.inventory.get(retreat_name, 0) + 1
        self.spawn_rogue_mobs()

    def enter_next_rogue_layer(self):
        self.enter_rogue_layer(new_entry=False)

    def generate_rogue_map(self, w, h):
        # create walls
        grid = [["02" for _ in range(w)] for _ in range(h)]
        start = (2, h - 2) if h <= 15 else (1, h - 2)
        exit_pos = (w - 2, 1)
        # carve simple path
        x, y = start
        grid[y][x] = "01"
        while x < exit_pos[0]:
            x += 1
            grid[y][x] = "01"
        while y > exit_pos[1]:
            y -= 1
            grid[y][x] = "01"
        # add random open tiles
        for yy in range(1, h - 1):
            for xx in range(1, w - 1):
                if grid[yy][xx] == "02" and random.random() < 0.65:
                    grid[yy][xx] = "01"
        # remove isolated open areas
        def neighbors(cx, cy):
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h:
                    yield nx, ny
        reachable = set()
        stack = [start]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in reachable:
                continue
            if grid[cy][cx] != "01":
                continue
            reachable.add((cx, cy))
            for nx, ny in neighbors(cx, cy):
                if (nx, ny) not in reachable and grid[ny][nx] == "01":
                    stack.append((nx, ny))
        for yy in range(1, h - 1):
            for xx in range(1, w - 1):
                if grid[yy][xx] == "01" and (xx, yy) not in reachable:
                    grid[yy][xx] = "02"
        # ensure npc spots
        if h > 13:
            grid[12][1] = "01"
            grid[13][1] = "01"
            if start == (1, h - 2):
                grid[h - 2][1] = "01"
            else:
                grid[h - 2][2] = "01"
        exit_x, exit_y = exit_pos
        grid[exit_y][exit_x] = "04"
        return {
            "grid": grid,
            "spawn": [start[0], start[1]],
            "mob_limit": getattr(self, "rogue_cfg", {}).get("mob_limit_normal", 10),
            "portals": []
        }

    def spawn_rogue_mobs(self):
        # clear existing hostiles
        self.entities = [e for e in self.entities if e.eid == "player" or e.immortal or mobs_data.get(e.eid, {}).get("ai_type") in ("friendly", "neutral")]
        if self.rogue_is_boss:
            self.spawn_rogue_boss()
            self.rogue_target_mobs = 1
            return
        self.rogue_target_mobs = getattr(self, "rogue_cfg", {}).get("mob_limit_normal", 10)
        count = self.count_hostile_mobs()
        target = self.rogue_target_mobs
        while count < target:
            if not self.spawn_random_hostile():
                break
            count = self.count_hostile_mobs()

    def spawn_rogue_boss(self):
        # pick a base hostile for stats
        base_id = None
        for k, v in mobs_data.items():
            if isinstance(v, dict) and v.get("ai_type") == "hostile":
                base_id = k
                base = v
                break
        if base_id is None:
            return
        w, h = self.map.w, self.map.h
        bx, by = w // 2 - 1, h // 2 - 1
        cfg = getattr(self, "rogue_cfg", {})
        hp_mult = cfg.get("boss_hp_mult", 5)
        atk_mult = cfg.get("boss_attack_mult", 3)
        boss = Entity(base_id, bx, by, base.get("hp", 30) * hp_mult, base.get("mp", 0), base.get("attack", 10) * atk_mult, base.get("defence", 0), base.get("ai_type"))
        boss.size = 3
        boss.is_boss = True
        self.entities.append(boss)

    def spawn_random_hostile(self):
        hostile_ids = [k for k, v in mobs_data.items() if isinstance(v, dict) and v.get('ai_type') == 'hostile']
        if not hostile_ids:
            return False
        mob_id = random.choice(hostile_ids)
        mob = mobs_data[mob_id]
        for _ in range(50):
            x = random.randint(0, self.map.w - 1)
            y = random.randint(0, self.map.h - 1)
            if not self.map.is_walkable(x, y):
                continue
            if self.entity_at(x, y):
                continue
            ent = Entity(mob_id, x, y, mob['hp'], mob.get('mp', 0), mob.get('attack', 10), mob.get('defence', 0), mob.get('ai_type'), mob.get('immortal', False))
            self.entities.append(ent)
            return True
        return False

    def cleanup_messages(self):
        now = time.time()
        max_age = self.message_show_time + self.message_fade_time
        while self.message_queue:
            created = self.message_queue[0].get("created", now)
            if now - created > max_age:
                self.message_queue.popleft()
            else:
                break

    def update_enemy(self, ent):
        mob = mobs_data.get(ent.eid)
        if mob is None:
            return
        if mob.get('ai_type') in ('friendly', 'neutral'):
            return
        if getattr(ent, "is_boss", False):
            px, py = self.player.x, self.player.y
            dist = abs(ent.x - px) + abs(ent.y - py)
            if dist <= 1:
                enemy_damage = max(0, int(ent.attack * (1 - self.player.defence / 100)))
                self.player.hp -= enemy_damage
                self.check_player_death()
            return
        if self.tick % mob.get('move_interval', 1) != 0:
            return
        px, py = self.player.x, self.player.y
        dist = abs(ent.x - px) + abs(ent.y - py)
        if ent.eid == 'soldier':
            if dist <= mob.get('attack_range', 2):
                enemy_damage = max(0, int(ent.attack * (1 - self.player.defence / 100)))
                self.player.hp -= enemy_damage
                self.check_player_death()
                return
            if dist <= mob.get('detect_range', 6):
                self.move_enemy_toward(ent, (px, py))
            return
        if dist <= mob.get('detect_range', 0):
            self.move_enemy_toward(ent, (px, py))

    def move_enemy_toward(self, ent, goal):
        path = self.find_path((ent.x, ent.y), goal)
        if path and len(path) > 1:
            nx, ny = path[1]
            if not self.entity_at(nx, ny):
                ent.x, ent.y = nx, ny

    def find_path(self, start, goal):
        queue = deque()
        queue.append((start, [start]))
        visited = set()
        visited.add(start)
        while queue:
            (x, y), path = queue.popleft()
            if (x, y) == goal:
                return path
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if self.map.is_walkable(nx, ny) and (nx, ny) not in visited:
                    if not self.entity_at(nx, ny) or (nx, ny) == goal:
                        queue.append(((nx, ny), path + [(nx, ny)]))
                        visited.add((nx, ny))
        return None

    def player_interact(self):
        if self.is_ui_blocking():
            return
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = self.player.x + dx, self.player.y + dy
            ent = self.entity_at(nx, ny)
            if ent and ent.eid != 'player':
                ent_def = self.get_entity_def(ent.eid)
                if ent_def.get('ai_type') in ('friendly', 'neutral'):
                    self.open_dialog(ent.eid)
                return
        bt = self.map.get_block(self.player.x, self.player.y)
        if bt and 'on_step' in blocktypes[bt]:
            if blocktypes[bt]['on_step'] == 'level_exit':
                self.start_blackout()
        self.try_harvest_bush()

    def try_harvest_bush(self):
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = self.player.x + dx, self.player.y + dy
            bt = self.map.get_block(nx, ny)
            if bt == "07":
                count = random.randint(1, 3)
                self.inventory["barry"] = self.inventory.get("barry", 0) + count
                unit = "barry" if count == 1 else "barries"
                text = tr(self.lang, "msg.harvested_berry", count=count, unit=unit)
                self.push_message(text)
                self.map.grid[ny][nx] = "08"
                key = (self.map.name, nx, ny)
                self.bush_regrow[key] = time.time() + random.uniform(20.0, 30.0)
                return

    def open_dialog(self, npc_id):
        dialog_path = os.path.join(DIALOG_DIR, f"{npc_id}.json")
        if not os.path.isfile(dialog_path):
            return
        self.dialog_data = load_json(dialog_path)
        self.dialog_node = self.dialog_data.get("start")
        self.dialog_selected = 0
        self.active_npc = npc_id
        self.ui_mode = "dialog"

    def dialog_choose(self):
        if not self.dialog_data or not self.dialog_node:
            return
        node = self.dialog_data.get(self.dialog_node, {})
        responses = node.get("responses", [])
        if not responses:
            self.close_dialog()
            return
        choice = responses[self.dialog_selected % len(responses)]
        next_node = choice.get("next")
        if next_node == "end":
            self.close_dialog()
            return
        if next_node == "shop":
            self.open_shop()
            return
        if next_node == "heal":
            self.npc_heal()
            self.close_dialog()
            return
        self.dialog_node = next_node
        self.dialog_selected = 0

    def close_dialog(self):
        self.dialog_data = None
        self.dialog_node = None
        self.dialog_selected = 0
        self.active_npc = None
        if self.ui_mode == "dialog":
            self.ui_mode = None

    def open_shop(self):
        self.ui_mode = "shop"
        self.shop_selected = 0

    def close_shop(self):
        if self.ui_mode == "shop":
            self.ui_mode = None

    def npc_heal(self):
        npc = npc_data.get(self.active_npc, {})
        cost = npc.get("heal_cost", 50)
        if self.money < cost:
            self.push_message(tr(self.lang, "msg.not_enough_robux"))
            return
        self.money -= cost
        self.player.hp = self.player.max_hp
        self.player.mp = self.player.max_mp
        self.push_message(tr(self.lang, "msg.healed_full"))

    def buy_selected_item(self):
        item = self.shop_items[self.shop_selected % len(self.shop_items)]
        name = item["name"]
        price = item["price"]
        if self.money < price:
            self.push_message(tr(self.lang, "msg.not_enough_robux"))
            return
        self.money -= price
        self.inventory[name] = self.inventory.get(name, 0) + 1
        self.push_message(tr(self.lang, "msg.bought_item", name=name, price=price))

    def open_save(self):
        self.ui_mode = "save"
        self.save_selected = 0

    def save_game(self):
        slot = self.save_selected + 1
        save_path = os.path.join(SAVE_DIR, f"slot_{slot}.json")
        payload = {
            "map": "map_1.json",
            "player": {
                "x": self.player.x,
                "y": self.player.y,
                "hp": self.player.hp,
                "mp": self.player.mp,
                "attack": self.player.attack,
                "defence": self.player.defence,
                "max_hp": self.player.max_hp,
                "max_mp": self.player.max_mp
            },
            "money": self.money,
            "inventory": self.inventory,
            "equipment": self.equipment,
            "objectives": self.objectives
        }
        with open(save_path, "w", encoding="utf-8") as f:
            import json
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.last_saved = True
        self.last_save_slot = slot
        self.push_message(tr(self.lang, "msg.saved_slot", slot=slot))

    def load_save(self, slot):
        save_path = os.path.join(SAVE_DIR, f"slot_{slot}.json")
        if not os.path.isfile(save_path):
            return False
        data = load_json(save_path)
        self.load_map(data.get("map", "map_1.json"))
        pdata = data.get("player", {})
        self.player.x = pdata.get("x", self.player.x)
        self.player.y = pdata.get("y", self.player.y)
        self.player.max_hp = pdata.get("max_hp", self.player.max_hp)
        self.player.hp = pdata.get("hp", self.player.hp)
        self.player.max_mp = pdata.get("max_mp", self.player.max_mp)
        self.player.mp = pdata.get("mp", self.player.mp)
        self.player.attack = pdata.get("attack", self.player.attack)
        self.player.defence = pdata.get("defence", self.player.defence)
        self.player.base_attack = self.player.attack
        self.player.base_defence = self.player.defence
        self.money = data.get("money", 0)
        self.inventory = data.get("inventory", self.inventory)
        self.equipment = data.get("equipment", self.equipment)
        self.objectives = data.get("objectives", self.objectives)
        self.recalculate_stats()
        self.last_saved = True
        self.last_save_slot = slot
        return True

    def load_latest_save(self):
        for slot in range(3, 0, -1):
            if self.load_save(slot):
                return True
        return False

    def open_leave_confirm(self):
        self.ui_mode = "leave_confirm"
        self.leave_step = 0
        self.leave_selected = 0

    def handle_leave_confirm(self):
        if self.leave_step == 0:
            if self.leave_selected == 0:
                self.leave_step = 1
                self.leave_selected = 0
            else:
                self.leave_step = 2
                self.leave_selected = 0
        elif self.leave_step == 1:
            if self.leave_selected == 0:
                self.request_quit = True
            else:
                self.ui_mode = None
        elif self.leave_step == 2:
            self.ui_mode = None

    def open_equip(self):
        self.ui_mode = "equip_category"
        self.equip_category_selected = 0
        self.equip_selected = 0

    def open_equip_items(self):
        self.ui_mode = "equip"
        self.equip_selected = 0

    def get_equip_categories(self):
        return ["weapon", "armor", "ring1", "ring2", "ring3", "ring4", "ring5", "ring6"]

    def equip_selected_item(self):
        equipables = self.get_equipable_items()
        if not equipables:
            return
        slot_key = "ring" if self.equip_category.startswith("ring") else self.equip_category
        filtered = [n for n in equipables if self.item_defs.get(n, {}).get("slot") == slot_key]
        if not filtered:
            self.push_message(tr(self.lang, "msg.no_items_category"))
            return
        name = filtered[self.equip_selected % len(filtered)]
        item_def = self.item_defs.get(name, {})
        slot = item_def.get("slot")
        if not slot:
            return
        equipped_count = sum(1 for v in self.equipment.values() if v == name)
        if self.inventory.get(name, 0) <= equipped_count:
            self.push_message(tr(self.lang, "msg.not_enough_items"))
            return
        target_slot = self.equip_category if self.equip_category.startswith("ring") else slot
        self.equipment[target_slot] = name
        self.recalculate_stats()
        self.push_message(tr(self.lang, "msg.equipped_item", name=name))

    def get_item_list(self):
        items = []
        for name, count in self.inventory.items():
            if count > 0:
                items.append(name)
        return items

    def use_item(self):
        items = self.get_item_list()
        if not items:
            self.push_message(tr(self.lang, "msg.no_items"))
            return
        name = items[self.item_selected % len(items)]
        count = self.inventory.get(name, 0)
        if count <= 0:
            self.push_message(tr(self.lang, "msg.no_items"))
            return
        if name == "health potion (small)":
            self.player.hp = clamp(self.player.hp + 20, 0, self.player.max_hp)
        elif name == "health potion (medium)":
            self.player.hp = clamp(self.player.hp + 50, 0, self.player.max_hp)
        elif name == "magic potion (small)":
            self.player.mp = clamp(self.player.mp + 10, 0, self.player.max_mp)
        elif name == "magic potion (medium)":
            self.player.mp = clamp(self.player.mp + 25, 0, self.player.max_mp)
        elif name == "barry":
            self.player.hp = clamp(self.player.hp + 10, 0, self.player.max_hp)
        elif name == "retreat item":
            if self.map.name != "rogue":
                self.push_message(tr(self.lang, "msg.cannot_use_item"))
                return
            self.inventory[name] = max(0, self.inventory.get(name, 0) - 1)
            self.player.hp = getattr(self, "leave_rogue_hp", 100)
            self.return_from_rogue()
            self.push_message(tr(self.lang, "msg.used_item", name=name))
            return
        else:
            self.push_message(tr(self.lang, "msg.cannot_use_item"))
            return
        self.inventory[name] = max(0, self.inventory.get(name, 0) - 1)
        self.push_message(tr(self.lang, "msg.used_item", name=name))

    def cast_spell(self):
        if not self.spells:
            self.push_message(tr(self.lang, "msg.no_spells"))
            return
        spell = self.spells[self.magic_selected % len(self.spells)]
        name = spell.get("name", "spell")
        cost = spell.get("mp_cost", 0)
        if self.player.mp < cost:
            self.push_message(tr(self.lang, "msg.not_enough_mp"))
            return
        self.player.mp -= cost
        if name == "heal":
            before = self.player.hp
            self.player.hp = clamp(self.player.hp + 25, 0, self.player.max_hp)
            healed = self.player.hp - before
            if healed <= 0:
                self.push_message(tr(self.lang, "msg.heal_full"))
            else:
                self.push_message(tr(self.lang, "msg.heal_gain", amount=healed))
        else:
            self.push_message(tr(self.lang, "msg.cast_spell", name=name))

    def recalculate_stats(self):
        attack_bonus = 0
        defence_bonus = 0
        for slot, name in self.equipment.items():
            if not name:
                continue
            item_def = self.item_defs.get(name, {})
            attack_bonus += item_def.get("attack", 0)
            defence_bonus += item_def.get("defence", 0)
        self.player.attack = self.player.base_attack + attack_bonus
        self.player.defence = self.player.base_defence + defence_bonus

    def get_equipable_items(self):
        equipables = []
        for name, count in self.inventory.items():
            if count <= 0:
                continue
            item_def = self.item_defs.get(name, {})
            if item_def.get("type") == "equipment":
                equipables.append(name)
        return equipables
