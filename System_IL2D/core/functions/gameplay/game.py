import os
import random
import time
from collections import deque
from ..world.map import GameMap, blocktypes, mobs_data, player_data, npc_data
from ..models.entity import Entity
from ..support.utils import MAP_DIR, DIALOG_DIR, SAVE_DIR, ITEMS_FILE, SHOP_FILE, SPELLS_FILE, OBJECTIVES_FILE, ROGUE_FILE, CONFIG_FILE, load_json, clamp
from ..support.i18n import tr
from . import rogue_ops as game_rogue_ops
from . import npc_ops as game_npc_ops
from . import inventory_ops as game_inventory_ops
from . import save_ops as game_save_ops


class Game:
    closure_greeted_this_run = False

    def __init__(self):
        pdata = player_data
        self.lang = pdata.get('lang', 'en')
        self.player_name = pdata.get('name', 'player')
        self.load_map('map_1.json')
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

        self.ui_mode = None  # None, dialog, shop, save, equip, item, magic, objective, status, leave_confirm, level_skipper
        self.dialog_data = None
        self.dialog_node = None
        self.dialog_selected = 0
        self.active_npc = None

        self.shop_selected = 0
        self.save_selected = 0
        self.equip_selected = 0
        self.equip_category_selected = 0
        self.equip_root_selected = 0
        self.equip_category = "weapon"
        self.item_selected = 0
        self.magic_selected = 0
        self.leave_step = 0
        self.leave_selected = 0
        self.request_quit = False
        self.carmen_selected = 0

        self.money = 0
        self.inventory = {
            'health potion (small)': 0,
            'magic potion (small)': 0,
            'revive ring': 0,
            'barry': 0,
            'retreat item': 0,
            'rouge level skipper': 0
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
        self.equip_categories = ["weapon", "armor", "ring1", "ring2", "ring3", "ring4", "ring5", "ring6"]
        self.objectives = ["Find the dev", "Try the shop"]
        self.spells = []
        self.item_defs = {}
        self.shop_items = []
        self.shop_all_items = []
        self.shop_base_items = []
        self.shop_mode = "default"
        self.shop_category = "all"
        self.last_saved = False
        self.last_save_slot = None
        self.bush_regrow = {}
        self.rogue_layer = 0
        self.rogue_is_boss = False
        self.rogue_target_mobs = 0
        self.rogue_difficulty = 0.0
        self.rogue_rest_intro_done = False
        self.transition_active = False
        self.transition_timer = 0.0
        self.transition_duration = 1.0
        self.transition_mid_done = False
        self.transition_action = None
        self.banner = None
        self.move_anim_duration = 0.1
        self.player_move_anim = None
        self.level_skip_amount = 1
        # Runtime-only placeholder state requested by user; intentionally not persisted.
        self.starting = {"enabled": False, "note": "ram_only"}
        self.request_close_esc_menu = False
        self.kaltsit_mission = None
        self.kaltsit_intro_done = False
        self.kaltsit_completed = 0
        self.kaltsit_reward_ready = False
        self.monst3r_unlocked = False
        self.team_members = []
        self.last_player_tile = tuple(self.map.spawn)

        if not os.path.isdir(SAVE_DIR):
            os.makedirs(SAVE_DIR, exist_ok=True)
        self.load_game_data()
        self.relations = {k: v.get("relation_point", 0) for k, v in npc_data.items() if isinstance(v, dict)}
        self.maybe_startup_closure_greet()

    def load_game_data(self):
        cfg = load_json(CONFIG_FILE)
        self.spawn_interval = cfg.get("spawn_interval", self.spawn_interval)
        self.message_show_time = cfg.get("message_show_time", self.message_show_time)
        self.message_fade_time = cfg.get("message_fade_time", self.message_fade_time)
        self.transition_duration = cfg.get("transition_duration", self.transition_duration)
        self.move_anim_duration = cfg.get("move_anim_duration", self.move_anim_duration)
        self.leave_rogue_hp = cfg.get("leave_rogue_hp", 100)
        self.item_defs = load_json(ITEMS_FILE)
        raw_shop = load_json(SHOP_FILE)
        self._refresh_equipment_layout()
        self.shop_all_items = self._build_synced_shop_items(raw_shop)
        self.shop_items = list(self.shop_all_items)
        self.spells = load_json(SPELLS_FILE)
        self.objectives_cfg = load_json(OBJECTIVES_FILE)
        self.rogue_cfg = load_json(ROGUE_FILE)

    def _refresh_equipment_layout(self):
        slot_order = ["weapon", "shield", "helmet", "armor", "pants", "boots"]
        discovered = set()
        for data in self.item_defs.values():
            if not isinstance(data, dict):
                continue
            if data.get("type") != "equipment":
                continue
            slot = data.get("slot")
            if not slot:
                continue
            discovered.add(slot)
        categories = [s for s in slot_order if s in discovered]
        extras = sorted([s for s in discovered if s not in set(slot_order) and s != "ring"])
        categories.extend(extras)
        categories.extend([f"ring{i}" for i in range(1, 7)])
        if not categories:
            categories = ["weapon", "armor"] + [f"ring{i}" for i in range(1, 7)]
        self.equip_categories = categories
        self.equipment = self._merge_equipment_slots(self.equipment)
        if self.equip_category not in self.equip_categories:
            self.equip_category = self.equip_categories[0]

    def _merge_equipment_slots(self, source):
        merged = {k: None for k in self.equip_categories}
        if not isinstance(source, dict):
            return merged
        for key, val in source.items():
            if key in merged:
                merged[key] = val
        # old save compatibility: single "ring" goes into ring1.
        if source.get("ring") and merged.get("ring1") is None:
            merged["ring1"] = source.get("ring")
        return merged

    def _item_power_score(self, item_def):
        attack = item_def.get("attack", 0)
        defence = item_def.get("defence", 0)
        magic = item_def.get("magic", 0)
        return attack + defence + magic

    def _build_synced_shop_items(self, raw_shop):
        # Keep non-equipment entries from shop.json, and rebuild equipment prices
        # from item definitions with "next level = x2 price".
        if not isinstance(raw_shop, list):
            raw_shop = []
        price_map = {}
        non_equipment = []
        for row in raw_shop:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            price = int(row.get("price", 0) or 0)
            if not name:
                continue
            price_map[name] = price
            idef = self.item_defs.get(name, {})
            if not isinstance(idef, dict) or idef.get("type") != "equipment":
                non_equipment.append({"name": name, "price": price})

        by_slot = {}
        for name, idef in self.item_defs.items():
            if not isinstance(idef, dict) or idef.get("type") != "equipment":
                continue
            slot = idef.get("slot")
            if not slot:
                continue
            by_slot.setdefault(slot, []).append(name)

        base_price_default = {
            "weapon": 100,
            "shield": 150,
            "helmet": 120,
            "armor": 150,
            "pants": 120,
            "boots": 120,
            "ring": 220,
        }
        equipment_rows = []
        for slot, names in by_slot.items():
            names = sorted(
                names,
                key=lambda n: (self._item_power_score(self.item_defs.get(n, {})), n)
            )
            if not names:
                continue
            seeded = [price_map[n] for n in names if price_map.get(n, 0) > 0]
            base_price = min(seeded) if seeded else base_price_default.get(slot, 200)
            level = 0
            prev_score = None
            for name in names:
                score = self._item_power_score(self.item_defs.get(name, {}))
                if prev_score is not None and score > prev_score:
                    level += 1
                price = int(base_price * (2 ** level))
                seeded_price = price_map.get(name, 0)
                if seeded_price > price:
                    price = seeded_price
                equipment_rows.append({"name": name, "price": price})
                prev_score = score

        # Stable order: non-equipment first, then equipment by slot/order.
        slot_rank = {"weapon": 0, "shield": 1, "helmet": 2, "armor": 3, "pants": 4, "boots": 5, "ring": 6}
        equipment_rows.sort(
            key=lambda r: (
                slot_rank.get(self.item_defs.get(r["name"], {}).get("slot"), 99),
                r["price"],
                r["name"]
            )
        )
        return non_equipment + equipment_rows

    def load_map(self, mapname):
        if mapname == "rogue":
            self.enter_rogue_layer(new_entry=True)
            return
        self.map = GameMap(os.path.join(MAP_DIR, mapname))
        # map_1/map_2/map_3 stay fully pre-coded; do not randomize runtime layout.
        self.map_max_h_mob = self.map.mob_limit
        self.player_move_anim = None
        if hasattr(self, "entities"):
            self.place_npcs_for_map()
            self.ensure_monst3r_entity()
        self.set_objectives_for_map()
        self.show_enter_banner(mapname)
        if self.map.name == "rouge_options.json":
            self.rogue_rest_intro_done = False
            self.open_rogue_rest_intro()

    def place_npcs_for_map(self):
        positions = {
            "map_1.json": [(1, 8), (2, 8), (3, 8), (4, 8), (5, 8)],
            # map_2: keep NPCs near left entrance (portal at x=0,y=15) with 1-tile gap.
            "map_2.json": [(2, 16), (3, 16), (4, 16), (5, 16), (6, 16)],
            "map_3.json": [(1, 8), (2, 8), (3, 8), (4, 8), (5, 8)],
            "rogue": [(1, 12), (1, 13), (-999, -999), (-999, -999), (-999, -999)],
            "rouge_options.json": [(4, 5), (6, 5), (-999, -999), (-999, -999), (-999, -999)]
        }
        order = ["dev", "priestess", "carmen", "closure", "kaltsit"]
        spots = positions.get(self.map.name, [])
        for i, npc_id in enumerate(order):
            ent = next((e for e in self.entities if e.eid == npc_id), None)
            if ent is None:
                data = npc_data.get(npc_id, {})
                ent = Entity(npc_id, 0, 0, data.get('hp', 1), data.get('mp', 0), data.get('attack', 0), data.get('defence', 0), data.get('ai_type'), data.get('immortal', False))
                self.entities.append(ent)
            if i < len(spots):
                ent.x, ent.y = spots[i]
            elif self.map.name in ("rogue", "rouge_options.json"):
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
        if 'closure' in npc_data:
            cdata = npc_data['closure']
            self.entities.append(
                Entity('closure', 7, 8, cdata.get('hp', 1), cdata.get('mp', 0), cdata.get('attack', 0), cdata.get('defence', 0), cdata.get('ai_type'), cdata.get('immortal', False))
            )
        if 'kaltsit' in npc_data:
            kdata = npc_data['kaltsit']
            self.entities.append(
                Entity('kaltsit', 8, 8, kdata.get('hp', 1), kdata.get('mp', 0), kdata.get('attack', 0), kdata.get('defence', 0), kdata.get('ai_type'), kdata.get('immortal', False))
            )

    def _populate_runtime_deco(self):
        # Rebuild decor on normal maps so they don't look empty.
        if self.map.name not in ("map_1.json", "map_2.json", "map_3.json"):
            return
        h = self.map.h
        w = self.map.w
        if h <= 2 or w <= 2:
            return
        reserved = {(self.map.spawn[0], self.map.spawn[1])}

        def _reserve_if_inner(rx, ry):
            if 1 <= rx < w - 1 and 1 <= ry < h - 1:
                reserved.add((rx, ry))

        for p in getattr(self.map, "portals", []):
            px, py = p.get("x"), p.get("y")
            reserved.add((px, py))
            # Keep portal approaches clear, especially when portal is on map edge.
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                _reserve_if_inner(px + dx, py + dy)
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                _reserve_if_inner(px + dx, py + dy)

        # Avoid expected NPC lines on open-world maps.
        npc_rows = {
            "map_1.json": [(x, 8) for x in range(1, 7)],
            "map_2.json": [(x, 16) for x in range(2, 7)],
            "map_3.json": [(x, 8) for x in range(1, 7)],
        }
        for pos in npc_rows.get(self.map.name, []):
            reserved.add(pos)

        # map_1 specific rearrange: keep a clean travel lane from spawn to right portal.
        if self.map.name == "map_1.json":
            travel_y = self.map.spawn[1]
            for x in range(1, w - 1):
                _reserve_if_inner(x, travel_y)
            # Small vertical breathing around the lane for smoother movement.
            for x in range(1, w - 1):
                _reserve_if_inner(x, travel_y - 1)
                _reserve_if_inner(x, travel_y + 1)

        # Clear old decor into base grass first.
        deco_codes = {"05", "06", "07", "08", "09"}
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if self.map.grid[y][x] in deco_codes:
                    self.map.grid[y][x] = "01"

        # Randomly place decor; keep blocking decor low.
        all_cells = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1)]
        random.shuffle(all_cells)
        total = (w - 2) * (h - 2)
        block_target = max(4, int(total * 0.08))
        walk_target = max(4, int(total * 0.07))

        placed_block = 0
        placed_walk = 0
        for x, y in all_cells:
            if (x, y) in reserved:
                continue
            if self.map.grid[y][x] != "01":
                continue
            if placed_block < block_target:
                self.map.grid[y][x] = random.choice(["05", "06", "07"])
                placed_block += 1
                continue
            if placed_walk < walk_target:
                self.map.grid[y][x] = random.choice(["08", "09"])
                placed_walk += 1
                continue
            if placed_block >= block_target and placed_walk >= walk_target:
                break

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
        oldx, oldy = self.player.x, self.player.y
        nx, ny = self.player.x + dx, self.player.y + dy
        if not self.map.is_walkable(nx, ny):
            return False
        target = self.entity_at(nx, ny)
        if target and target.eid != 'player' and target.hp > 0:
            target_def = self.get_entity_def(target.eid)
            if target_def.get('ai_type') in ('friendly', 'neutral'):
                return False
            if target_def.get('ai_type') == 'team':
                # Team member should never be attacked by player.
                # Swap positions so movement feels natural.
                tx, ty = target.x, target.y
                target.x, target.y = oldx, oldy
                self.player.x, self.player.y = tx, ty
                self.player_move_anim = {"from": (oldx, oldy), "to": (tx, ty), "start": time.time(), "duration": self.move_anim_duration}
                self.state_cleanup()
                self.update(player_tick=True)
                return True
            if getattr(target, "immortal", False):
                return False
            player_damage = max(0, int(self.player.attack * (1 - target.defence / 100)))
            enemy_damage, reflect = self.compute_player_damage(target.attack, target)
            target.hp -= player_damage
            if target.hp <= 0:
                target.hp = -1
                self.player.x, self.player.y = nx, ny
                self.player_move_anim = {"from": (oldx, oldy), "to": (nx, ny), "start": time.time(), "duration": self.move_anim_duration}
                self.on_enemy_death(target)
                self.state_cleanup()
                self.update(player_tick=True)
                return True
            self.player.hp -= enemy_damage
            if reflect > 0 and target.hp > 0:
                target.hp -= reflect
                if target.hp <= 0:
                    self.on_enemy_death(target)
            self.check_player_death()
            self.state_cleanup()
            return False
        self.player.x, self.player.y = nx, ny
        self.player_move_anim = {"from": (oldx, oldy), "to": (nx, ny), "start": time.time(), "duration": self.move_anim_duration}
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
                        self.start_transition(lambda: self.enter_rogue_layer(new_entry=True))
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
        if self.map.name == "rouge_options.json":
            self.start_transition(self.enter_next_rogue_layer)
            return
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
        is_boss = getattr(ent, "is_boss", False)
        if reward_money:
            if isinstance(reward_money, dict):
                amount = reward_money.get("amount", 0)
                chance = 1.0
            else:
                amount = int(reward_money)
                chance = 1.0
            if amount and random.random() < chance:
                if is_boss:
                    amount = amount * 10
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
                if is_boss:
                    chance = 1.0
                    count = count * 3
                if name and random.random() < chance:
                    self.inventory[name] = self.inventory.get(name, 0) + count
                    dropped_items.append(f"{name} x{count}")
        if dropped_items:
            lines.append(tr(self.lang, "reward.dropped", text=", ".join(dropped_items)))
        self.push_message_lines(lines)

        # Kaltsit mission progress
        mission = getattr(self, "kaltsit_mission", None)
        if not mission or mission.get("done"):
            return
        mtype = mission.get("type")
        if mtype == "kill_any":
            mission["progress"] = min(mission["target"], mission.get("progress", 0) + 1)
        elif mtype == "kill_specific" and ent.eid == mission.get("mob"):
            mission["progress"] = min(mission["target"], mission.get("progress", 0) + 1)
        if mission.get("progress", 0) >= mission.get("target", 0):
            mission["done"] = True
            self.on_kaltsit_mission_complete()

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
                self.push_message(tr(self.lang, "msg.revive_ring_broken"))
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
            self.last_player_tile = (self.player.x, self.player.y)
            self.tick += 1
            for ent in self.entities:
                if ent.eid != 'player':
                    self.update_enemy(ent)
            self.update_monst3r(player_tick=True)
            self.apply_recover_ring_tick()
            self.apply_dev_ring_tick()
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
        current_spawn_interval = self.map.spawn_interval if self.map.spawn_interval is not None else self.spawn_interval
        self.spawn_timer += dt
        if self.spawn_timer >= current_spawn_interval and self.map.name != "rogue":
            self.spawn_timer = 0.0
            if self.count_hostile_mobs() < self.map_max_h_mob:
                self.spawn_random_hostile()
        self.update_bush_regrow()
        self.update_monst3r(player_tick=False)
        self.cleanup_messages()

    def ensure_monst3r_entity(self):
        if not self.monst3r_unlocked:
            self.entities = [e for e in self.entities if e.eid != "monst3r"]
            return
        if any(e.eid == "monst3r" for e in self.entities):
            return
        hp = max(1, int(self.player.max_hp * 0.2))
        mp = max(0, int(self.player.max_mp * 0.2))
        atk = max(1, int(self.player.attack * 0.2))
        dfs = max(0, int(self.player.defence * 0.2))
        spawn_x = max(1, self.player.x - 1)
        spawn_y = self.player.y
        mon = Entity("monst3r", spawn_x, spawn_y, hp, mp, atk, dfs, ai_type="team")
        mon.move_interval = 1
        self.entities.append(mon)
        if "monst3r" not in self.team_members:
            self.team_members.append("monst3r")

    def on_kaltsit_mission_complete(self):
        mission = self.kaltsit_mission or {}
        if mission.get("rewarded"):
            return
        mission["rewarded"] = True
        self.kaltsit_completed += 1
        self.push_message(tr(self.lang, "msg.mission_complete_count", count=self.kaltsit_completed))
        if self.kaltsit_completed >= 10 and not self.monst3r_unlocked:
            self.kaltsit_reward_ready = True

    def update_monst3r(self, player_tick=False):
        mon = next((e for e in self.entities if e.eid == "monst3r"), None)
        if mon is None:
            return
        # Sync 20% of current player combat stats.
        mon.attack = max(1, int(self.player.attack * 0.2))
        mon.defence = max(0, int(self.player.defence * 0.2))
        mon.max_hp = max(1, int(self.player.max_hp * 0.2))
        if mon.hp > mon.max_hp:
            mon.hp = mon.max_hp
        if not player_tick:
            return
        hostiles = [e for e in self.entities if e.eid != "player" and e.eid != "monst3r" and mobs_data.get(e.eid, {}).get("ai_type") == "hostile" and e.hp > 0]
        target = None
        best_dist = 9999
        for e in hostiles:
            dist = abs(e.x - mon.x) + abs(e.y - mon.y)
            if dist <= 4 and dist < best_dist:
                best_dist = dist
                target = e
        if target is None:
            # Follow behind player.
            tx, ty = self.last_player_tile
            if (mon.x, mon.y) == (tx, ty):
                return
            path = self.find_path((mon.x, mon.y), (tx, ty))
            if path and len(path) > 1:
                nx, ny = path[1]
                if self.map.is_walkable(nx, ny) and (self.entity_at(nx, ny) is None or (nx, ny) == (self.player.x, self.player.y)):
                    mon.x, mon.y = nx, ny
            return
        if best_dist <= 1:
            dmg = max(1, int(mon.attack * (1 - target.defence / 100)))
            target.hp -= dmg
            if target.hp <= 0:
                self.on_enemy_death(target)
                self.state_cleanup()
            return
        path = self.find_path((mon.x, mon.y), (target.x, target.y))
        if path and len(path) > 1:
            nx, ny = path[1]
            if self.map.is_walkable(nx, ny) and self.entity_at(nx, ny) is None:
                mon.x, mon.y = nx, ny

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

    def apply_dev_ring_tick(self):
        ring_name = "dev's super powerful ring"
        count = sum(1 for slot, name in self.equipment.items() if slot.startswith("ring") and name == ring_name)
        if count <= 0:
            return
        if count > 1:
            self.handle_cheat_ring()
            # keep only one equipped
            kept = False
            for slot in list(self.equipment.keys()):
                if slot.startswith("ring") and self.equipment[slot] == ring_name:
                    if not kept:
                        kept = True
                    else:
                        self.equipment[slot] = None
            return
        hp_gain = max(int(self.player.max_hp * 0.10), int(self.player.max_hp * 0.05))
        mp_gain = max(int(self.player.max_mp * 0.10), int(self.player.max_mp * 0.05))
        self.player.hp = clamp(self.player.hp + hp_gain, 0, self.player.max_hp)
        self.player.mp = clamp(self.player.mp + mp_gain, 0, self.player.max_mp)
        if random.random() < 0.05:
            self.money += 100
            self.push_message(tr(self.lang, "msg.dev_lucky_robux"))

    def get_player_draw_pos(self):
        anim = self.player_move_anim
        if not anim:
            return self.player.x, self.player.y
        now = time.time()
        start = anim.get("start", now)
        dur = anim.get("duration", 0.1)
        if dur <= 0:
            self.player_move_anim = None
            return self.player.x, self.player.y
        t = (now - start) / dur
        if t >= 1.0:
            self.player_move_anim = None
            return self.player.x, self.player.y
        fx, fy = anim.get("from", (self.player.x, self.player.y))
        tx, ty = anim.get("to", (self.player.x, self.player.y))
        px = fx + (tx - fx) * t
        py = fy + (ty - fy) * t
        return px, py

    def handle_cheat_ring(self):
        self.money = int(self.money * 0.5)
        self.dialog_data = {
            "start": "node_1",
            "node_1": {
                "text": tr(self.lang, "dialog.cheat_warn"),
                "responses": [{"text": tr(self.lang, "dialog.ok"), "next": "end"}]
            }
        }
        self.dialog_node = "node_1"
        self.dialog_selected = 0
        self.active_npc = "dev"
        self.ui_mode = "dialog"
        self.push_message(tr(self.lang, "msg.cheat_penalty"))

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

    def get_objective_lines(self):
        lines = list(self.objectives)
        mission = getattr(self, "kaltsit_mission", None)
        if not mission:
            return lines
        mtype = mission.get("type")
        if mtype == "kill_specific":
            text = tr(
                self.lang,
                "mission.kill_specific",
                mob=mission.get("mob", "slime"),
                progress=mission.get("progress", 0),
                target=mission.get("target", 1),
            )
        elif mtype == "kill_any":
            text = tr(
                self.lang,
                "mission.kill_any",
                progress=mission.get("progress", 0),
                target=mission.get("target", 1),
            )
        elif mtype == "reach_layer":
            text = tr(
                self.lang,
                "mission.reach_layer",
                progress=mission.get("progress", 0),
                target=mission.get("target", 1),
            )
        else:
            text = ""
        if text:
            lines.append(f"Kaltsit: {text}")
        return lines

    def show_enter_banner(self, label):
        name = label.replace(".json", "")
        self.banner = {"text": tr(self.lang, "banner.now_entering", where=name), "created": time.time(), "duration": 3.0}

    def show_dev_block(self):
        self.dialog_data = {
            "start": "node_1",
            "node_1": {
                "text": tr(self.lang, "dialog.dev_block"),
                "responses": [{"text": tr(self.lang, "dialog.ok"), "next": "end"}]
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
            self.player.hp = self.player.max_hp
            self.inventory["retreat item"] = 0
            self.push_message(tr(self.lang, "msg.retreat_cleared"))
        self.start_transition(do_return)

    def enter_rogue_layer(self, new_entry=False):
        return game_rogue_ops.enter_rogue_layer(self, new_entry)

    def enter_next_rogue_layer(self):
        return game_rogue_ops.enter_next_rogue_layer(self)

    def open_level_skipper_ui(self):
        return game_rogue_ops.open_level_skipper_ui(self)

    def change_level_skip_amount(self, delta):
        return game_rogue_ops.change_level_skip_amount(self, delta)

    def confirm_level_skipper_use(self):
        return game_rogue_ops.confirm_level_skipper_use(self)

    def generate_rogue_map(self, w, h):
        return game_rogue_ops.generate_rogue_map(self, w, h)

    def spawn_rogue_mobs(self):
        return game_rogue_ops.spawn_rogue_mobs(self)

    def spawn_rogue_boss(self):
        return game_rogue_ops.spawn_rogue_boss(self)

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
            hp = mob['hp']
            atk = mob.get('attack', 10)
            if self.map.name == "rogue":
                mult = 1.0 + self.rogue_difficulty
                hp = int(hp * mult)
                atk = int(atk * mult)
            ent = Entity(mob_id, x, y, hp, mob.get('mp', 0), atk, mob.get('defence', 0), mob.get('ai_type'), mob.get('immortal', False))
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
                enemy_damage, reflect = self.compute_player_damage(ent.attack, ent)
                self.player.hp -= enemy_damage
                if reflect > 0 and ent.hp > 0:
                    ent.hp -= reflect
                    if ent.hp <= 0:
                        self.on_enemy_death(ent)
                self.check_player_death()
            return
        if self.tick % mob.get('move_interval', 1) != 0:
            return
        px, py = self.player.x, self.player.y
        dist = abs(ent.x - px) + abs(ent.y - py)
        if ent.eid == 'soldier':
            if dist <= mob.get('attack_range', 2):
                enemy_damage, reflect = self.compute_player_damage(ent.attack, ent)
                self.player.hp -= enemy_damage
                if reflect > 0 and ent.hp > 0:
                    ent.hp -= reflect
                    if ent.hp <= 0:
                        self.on_enemy_death(ent)
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

    def compute_player_damage(self, incoming, attacker=None):
        defence = self.player.defence
        if defence <= 100:
            return max(0, int(incoming * (1 - defence / 100))), 0
        # reverse damage when defence exceeds 100
        reflect = int(incoming * ((defence - 100) / 100))
        return 0, max(0, reflect)

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
        return game_npc_ops.player_interact(self)

    def try_harvest_bush(self):
        return game_npc_ops.try_harvest_bush(self)

    def open_dialog(self, npc_id):
        return game_npc_ops.open_dialog(self, npc_id)

    def open_rogue_rest_intro(self):
        return game_npc_ops.open_rogue_rest_intro(self)

    def open_rogue_rest_leave(self):
        return game_npc_ops.open_rogue_rest_leave(self)

    def dialog_choose(self):
        return game_npc_ops.dialog_choose(self)

    def get_dialog_responses(self, node):
        return game_npc_ops.get_dialog_responses(self, node)

    def close_dialog(self):
        return game_npc_ops.close_dialog(self)

    def gift_to_npc(self):
        return game_npc_ops.gift_to_npc(self)

    def open_carmen_upgrade(self):
        return game_npc_ops.open_carmen_upgrade(self)

    def carmen_roll(self, stat):
        return game_npc_ops.carmen_roll(self, stat)

    def maybe_startup_closure_greet(self):
        return game_npc_ops.maybe_startup_closure_greet(self)

    def open_shop(self, shop_mode="default"):
        return game_npc_ops.open_shop(self, shop_mode)

    def _shop_item_category(self, name):
        return game_npc_ops._shop_item_category(self, name)

    def get_shop_categories(self):
        return game_npc_ops.get_shop_categories(self)

    def refresh_shop_items(self):
        return game_npc_ops.refresh_shop_items(self)

    def cycle_shop_category(self, step):
        return game_npc_ops.cycle_shop_category(self, step)

    def grant_dev_set(self):
        return game_npc_ops.grant_dev_set(self)

    def close_shop(self):
        return game_npc_ops.close_shop(self)

    def npc_heal(self):
        return game_npc_ops.npc_heal(self)

    def buy_selected_item(self):
        return game_npc_ops.buy_selected_item(self)

    def open_save(self):
        return game_save_ops.open_save(self)

    def save_game(self):
        return game_save_ops.save_game(self)

    def load_save(self, slot):
        return game_save_ops.load_save(self, slot)

    def load_latest_save(self):
        return game_save_ops.load_latest_save(self)

    def open_leave_confirm(self):
        return game_save_ops.open_leave_confirm(self)

    def handle_leave_confirm(self):
        return game_save_ops.handle_leave_confirm(self)

    def open_equip(self):
        return game_inventory_ops.open_equip(self)

    def open_equip_items(self):
        return game_inventory_ops.open_equip_items(self)

    def get_equip_categories(self):
        return game_inventory_ops.get_equip_categories(self)

    def equip_selected_item(self):
        return game_inventory_ops.equip_selected_item(self)

    def unequip_all(self):
        return game_inventory_ops.unequip_all(self)

    def equip_best(self):
        return game_inventory_ops.equip_best(self)

    def get_item_list(self):
        return game_inventory_ops.get_item_list(self)

    def use_item(self):
        return game_inventory_ops.use_item(self)

    def cast_spell(self):
        return game_inventory_ops.cast_spell(self)

    def recalculate_stats(self):
        return game_inventory_ops.recalculate_stats(self)

    def get_equipable_items(self):
        return game_inventory_ops.get_equipable_items(self)
