import os
import random
from collections import deque
from .map import GameMap, blocktypes, mobs_data
from .entity import Entity
from .utils import MAP_DIR, DIALOG_DIR, SAVE_DIR, load_json, clamp


class Game:
    def __init__(self):
        self.load_map('map_1.json')
        pdata = mobs_data['player']
        self.player = Entity(
            'player',
            *self.map.spawn,
            pdata['hp'],
            pdata.get('mp', 0),
            pdata.get('attack', 10),
            pdata.get('defence', 0),
            ai_type='player'
        )
        self.player.base_attack = self.player.attack
        self.player.base_defence = self.player.defence
        self.entities = [self.player]
        self.spawn_default_entities()

        self.tick = 0
        self.map_max_h_mob = 4
        self.spawn_interval = 4.0
        self.spawn_timer = 0.0
        self.camera_x = self.player.x
        self.camera_y = self.player.y
        self.blackout = 0  # 0: normal, 1: fade out, 2: fade in
        self.black_alpha = 0

        self.message_queue = deque()
        self.message_duration_ticks = 180

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
            'revive ring': 0
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

        if not os.path.isdir(SAVE_DIR):
            os.makedirs(SAVE_DIR, exist_ok=True)

    def load_map(self, mapname):
        self.map = GameMap(os.path.join(MAP_DIR, mapname))

    def spawn_default_entities(self):
        if 'slime' in mobs_data:
            sdata = mobs_data['slime']
            self.entities.append(
                Entity('slime', 2, 1, sdata['hp'], sdata.get('mp', 0), sdata.get('attack', 10), sdata.get('defence', 0), sdata.get('ai_type'))
            )
        if 'skeleton' in mobs_data:
            kdata = mobs_data['skeleton']
            self.entities.append(
                Entity('skeleton', 7, 1, kdata['hp'], kdata.get('mp', 0), kdata.get('attack', 10), kdata.get('defence', 0), kdata.get('ai_type'))
            )
        if 'zombie' in mobs_data:
            zdata = mobs_data['zombie']
            self.entities.append(
                Entity('zombie', 1, 6, zdata['hp'], zdata.get('mp', 0), zdata.get('attack', 10), zdata.get('defence', 0), zdata.get('ai_type'))
            )
        if 'soldier' in mobs_data:
            mdata = mobs_data['soldier']
            self.entities.append(
                Entity('soldier', 8, 6, mdata['hp'], mdata.get('mp', 0), mdata.get('attack', 10), mdata.get('defence', 0), mdata.get('ai_type'))
            )
        if 'dev' in mobs_data:
            ddata = mobs_data['dev']
            self.entities.append(
                Entity('dev', 2, 8, ddata['hp'], ddata.get('mp', 0), ddata.get('attack', 0), ddata.get('defence', 0), ddata.get('ai_type'))
            )

    def entity_at(self, x, y):
        for e in self.entities:
            if (e.x, e.y) == (x, y) and e.hp > 0:
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
            if mobs_data.get(target.eid, {}).get('ai_type') == 'friendly':
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
            if blocktypes[bt]['on_step'] == 'level_exit':
                self.start_blackout()
        self.state_cleanup()
        self.update(player_tick=True)
        return True

    def on_enemy_death(self, ent):
        mob = mobs_data.get(ent.eid, {})
        reward_money = mob.get('reward_money', 0)
        reward_items = mob.get('reward_items', {})
        reward_text = mob.get('reward_text', None)
        if reward_money:
            self.money += reward_money
        if reward_items:
            for name, count in reward_items.items():
                self.inventory[name] = self.inventory.get(name, 0) + count
        if reward_text:
            self.push_message(reward_text)

    def push_message(self, text):
        self.message_queue.append({
            "text": text,
            "expire_tick": self.tick + self.message_duration_ticks
        })

    def state_cleanup(self):
        self.entities = [e for e in self.entities if e.eid == 'player' or e.hp > 0]

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

    def count_hostile_mobs(self):
        count = 0
        for e in self.entities:
            if e.eid != 'player' and mobs_data.get(e.eid, {}).get('ai_type') == 'hostile' and e.hp > 0:
                count += 1
        return count

    def spawn_random_hostile(self):
        hostile_ids = [k for k, v in mobs_data.items() if v.get('ai_type') == 'hostile']
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
            ent = Entity(mob_id, x, y, mob['hp'], mob.get('mp', 0), mob.get('attack', 10), mob.get('defence', 0), mob.get('ai_type'))
            self.entities.append(ent)
            return True
        return False

    def cleanup_messages(self):
        while self.message_queue and self.message_queue[0]["expire_tick"] <= self.tick:
            self.message_queue.popleft()

    def update_enemy(self, ent):
        mob = mobs_data[ent.eid]
        if mob.get('ai_type') == 'friendly':
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
                if mobs_data.get(ent.eid, {}).get('ai_type') == 'friendly':
                    self.open_dialog(ent.eid)
                return
        bt = self.map.get_block(self.player.x, self.player.y)
        if bt and 'on_step' in blocktypes[bt]:
            if blocktypes[bt]['on_step'] == 'level_exit':
                self.start_blackout()

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

    def buy_selected_item(self):
        item = self.shop_items[self.shop_selected % len(self.shop_items)]
        name = item["name"]
        price = item["price"]
        if self.money < price:
            self.push_message("not enough robux")
            return
        self.money -= price
        self.inventory[name] = self.inventory.get(name, 0) + 1
        self.push_message(f"bought {name} for {price} robux")

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
        self.push_message(f"saved to slot {slot}")

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
            self.push_message("no items for this category")
            return
        name = filtered[self.equip_selected % len(filtered)]
        item_def = self.item_defs.get(name, {})
        slot = item_def.get("slot")
        if not slot:
            return
        self.equipment[slot] = name
        self.recalculate_stats()
        self.push_message(f"equipped {name}")

    def get_item_list(self):
        items = []
        for name, count in self.inventory.items():
            if count > 0:
                items.append(name)
        return items

    def use_item(self):
        items = self.get_item_list()
        if not items:
            self.push_message("no items")
            return
        name = items[self.item_selected % len(items)]
        count = self.inventory.get(name, 0)
        if count <= 0:
            self.push_message("no items")
            return
        if name == "health potion (small)":
            self.player.hp = clamp(self.player.hp + 20, 0, self.player.max_hp)
        elif name == "health potion (medium)":
            self.player.hp = clamp(self.player.hp + 50, 0, self.player.max_hp)
        elif name == "magic potion (small)":
            self.player.mp = clamp(self.player.mp + 10, 0, self.player.max_mp)
        elif name == "magic potion (medium)":
            self.player.mp = clamp(self.player.mp + 25, 0, self.player.max_mp)
        else:
            self.push_message("cannot use this item")
            return
        self.inventory[name] = max(0, self.inventory.get(name, 0) - 1)
        self.push_message(f"used {name}")

    def cast_spell(self):
        if not self.spells:
            self.push_message("no spells")
            return
        spell = self.spells[self.magic_selected % len(self.spells)]
        name = spell.get("name", "spell")
        cost = spell.get("mp_cost", 0)
        if self.player.mp < cost:
            self.push_message("not enough MP")
            return
        self.player.mp -= cost
        if name == "heal":
            self.player.hp = clamp(self.player.hp + 25, 0, self.player.max_hp)
            self.push_message("cast heal")
        else:
            self.push_message(f"cast {name}")

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
