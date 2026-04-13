import os
import random
import time
from collections import deque
from .map import GameMap, blocktypes, mobs_data, player_data, npc_data
from .entity import Entity
from .utils import MAP_DIR, DIALOG_DIR, SAVE_DIR, load_json, clamp
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
            'barry': 0
        }
        self.equipment = {
            'weapon': None,
            'armor': None
        }
        self.objectives = ["Find the dev", "Try the shop"]
        self.spells = [
            {"name": "spark", "mp_cost": 5},
            {"name": "heal", "mp_cost": 8}
        ]
        self.item_defs = {
            "health potion (small)": {"type": "consumable"},
            "health potion (medium)": {"type": "consumable"},
            "magic potion (small)": {"type": "consumable"},
            "magic potion (medium)": {"type": "consumable"},
            "revive ring": {"type": "special"},
            "barry": {"type": "consumable"},
            "iron sword": {"type": "equipment", "slot": "weapon", "attack": 30},
            "iron chestplate": {"type": "equipment", "slot": "armor", "defence": 20}
        }
        self.shop_items = [
            {"name": "health potion (medium)", "price": 25},
            {"name": "magic potion (medium)", "price": 40},
            {"name": "iron sword", "price": 100},
            {"name": "iron chestplate", "price": 150},
            {"name": "revive ring", "price": 200}
        ]
        self.last_saved = False
        self.last_save_slot = None
        self.bush_regrow = {}

        if not os.path.isdir(SAVE_DIR):
            os.makedirs(SAVE_DIR, exist_ok=True)

    def load_map(self, mapname):
        self.map = GameMap(os.path.join(MAP_DIR, mapname))
        self.map_max_h_mob = self.map.mob_limit
        if hasattr(self, "entities"):
            self.place_npcs_for_map()

    def place_npcs_for_map(self):
        positions = {
            "map_1.json": [(1, 8), (2, 8), (3, 8)],
            "map_2.json": [(2, 8), (3, 8), (4, 8)],
            "map_3.json": [(1, 8), (2, 8), (3, 8)]
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
            if (e.x, e.y) == (x, y) and (e.immortal or e.hp > 0):
                return e
        return None

    def is_ui_blocking(self):
        return self.ui_mode is not None

    def request_player_move(self, dx, dy):
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
                self.start_blackout()
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
                    self.load_map(target_map)
                    if target_spawn and len(target_spawn) == 2:
                        self.player.x, self.player.y = target_spawn
                    else:
                        self.player.x, self.player.y = self.map.spawn
                return

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
        if self.is_ui_blocking():
            return
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0.0
            if self.count_hostile_mobs() < self.map_max_h_mob:
                self.spawn_random_hostile()
        self.update_bush_regrow()
        self.cleanup_messages()

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

    def equip_selected_item(self):
        equipables = self.get_equipable_items()
        if not equipables:
            return
        filtered = [n for n in equipables if self.item_defs.get(n, {}).get("slot") == self.equip_category]
        if not filtered:
            self.push_message(tr(self.lang, "msg.no_items_category"))
            return
        name = filtered[self.equip_selected % len(filtered)]
        item_def = self.item_defs.get(name, {})
        slot = item_def.get("slot")
        if not slot:
            return
        self.equipment[slot] = name
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
