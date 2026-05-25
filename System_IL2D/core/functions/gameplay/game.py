import os
import random
import time
import json
from collections import deque
try:
    from ..world.map import GameMap, blocktypes, mobs_data, player_data, npc_data
    from ..models.entity import Entity
    from ..support.utils import MAP_DIR, DIALOG_DIR, SAVE_DIR, ITEMS_FILE, SHOP_FILE, SPELLS_FILE, OBJECTIVES_FILE, ROGUE_FILE, CONFIG_FILE, load_json, clamp, resolve_map_file, iter_all_map_files
    from ..support.i18n import tr
    from ..support.asset_resolver import resolve_atlas_candidates, resolve_folder_candidates
    from . import rogue_ops as game_rogue_ops
    from . import npc_ops as game_npc_ops
    from . import inventory_ops as game_inventory_ops
    from . import save_ops as game_save_ops
except ImportError:
    import sys
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from System_IL2D.core.functions.world.map import GameMap, blocktypes, mobs_data, player_data, npc_data
    from System_IL2D.core.functions.models.entity import Entity
    from System_IL2D.core.functions.support.utils import MAP_DIR, DIALOG_DIR, SAVE_DIR, ITEMS_FILE, SHOP_FILE, SPELLS_FILE, OBJECTIVES_FILE, ROGUE_FILE, CONFIG_FILE, load_json, clamp, resolve_map_file, iter_all_map_files
    from System_IL2D.core.functions.support.i18n import tr
    from System_IL2D.core.functions.support.asset_resolver import resolve_atlas_candidates, resolve_folder_candidates
    from System_IL2D.core.functions.gameplay import rogue_ops as game_rogue_ops
    from System_IL2D.core.functions.gameplay import npc_ops as game_npc_ops
    from System_IL2D.core.functions.gameplay import inventory_ops as game_inventory_ops
    from System_IL2D.core.functions.gameplay import save_ops as game_save_ops


class Game:
    closure_greeted_this_run = False
    DEFAULT_WEAPON_ATTACK_TYPE = {
        "dev's super powerful sword": "P",
        "iron sword": "P",
        "diamond sword": "P",
        "emerald sword": "P",
        "netherite sword": "P",
        "wand": "M",
        "staff": "M",
    }

    def __init__(self):
        pdata = player_data
        self.lang = pdata.get('lang', 'zh')
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
        self.player.base_magic_attack = int(pdata.get("magic_attack", self.player.attack))
        self.player.base_magic_defense = int(pdata.get("magic_defense", 0))
        self.player.magic_attack = self.player.base_magic_attack
        self.player.magic_defense = self.player.base_magic_defense
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
        self.dialog_source = None
        self.interact_candidates = []
        self.interact_selected = 0

        self.shop_selected = 0
        self.save_selected = 0
        self.equip_selected = 0
        self.equip_category_selected = 0
        self.equip_root_selected = 0
        self.equip_focus = "tabs"
        self.equip_category = "weapon"
        self.item_selected = 0
        self.item_category = "item"
        self.item_focus = "tabs"
        self.magic_selected = 0
        self.hotbar_mode = "item"  # item | magic
        self.hotbar_stage = "type"  # type | slot | item
        self.hotbar_type_selected = 0  # 0=item, 1=magic
        self.hotbar_slot_selected = 0
        self.hotbar_list_selected = 0
        self.active_hotbar = "item"  # currently visible/triggered in-game bar
        self.item_hotbar_slots = [None] * 10
        self.magic_hotbar_slots = [None] * 10
        self.leave_step = 0
        self.leave_selected = 0
        self.request_quit = False
        self.request_main_menu = False
        self.carmen_selected = 0
        self.death_menu_selected = 0
        self.death_no_save_notice = ""

        self.money = 0
        self.inventory = {
            'health potion (small)': 0,
            'magic potion (small)': 0,
            'revive ring': 0,
            'berry': 0,
            'retreat item': 0,
            'rogue level skipper': 0
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
        self.objective_selected = 0
        self.tracked_mission = None
        self.active_missions = []
        self.spells = []
        self.spell_last_cast = {}
        self.spell_cd_ticks = {}
        self.player_level = int(pdata.get("level", 1))
        self.player_exp = int(pdata.get("exp", 0))
        self.player_skill_points = int(pdata.get("skill_points", 3))
        self.skill_tree = {"harvest_barries": False}
        self.skill_tree_selected = 0
        self.team_selected = 0
        self.team_equip_member_selected = 0
        self.team_equip_slot_selected = 0
        self.team_equip_item_selected = 0
        self.team_equip_root_selected = 0
        self.team_equip_focus = "tabs"
        self.team_equip_category = "weapon"
        self.team_equipment = {}
        self.team_sync_ratio_base = {"monst3r": 0.2, "wisadel": 0.4}
        self.level_stat_pending = 0
        self.level_stat_selected = 0
        self.item_defs = {}
        self.item_alias = {}
        self.item_display = {}
        self.spell_alias = {}
        self.spell_display = {}
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
        self.environment_difficulty = 0.0
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
        self.ines_intro_done = False
        self.kaltsit_completed = 0
        self.kaltsit_reward_ready = False
        self.ines_reward_ready = False
        self.monst3r_unlocked = False
        self.wisadel_unlocked = False
        self.team_members = []
        self.last_player_tile = tuple(self.map.spawn)
        self.monst3r_anim_state = "move"
        self.monst3r_anim_until = 0.0
        self.wisadel_anim_state = "move"
        self.wisadel_anim_until = 0.0
        self._anim_frame_count_cache = {}
        self.explored_maps = set()
        self.world_map_nodes = {}
        self.world_map_edges = []

        if not os.path.isdir(SAVE_DIR):
            os.makedirs(SAVE_DIR, exist_ok=True)
        self.load_game_data()
        self._build_world_map_graph()
        self.mark_map_explored(self.map.name)
        self.relations = {k: v.get("relation_point", 0) for k, v in npc_data.items() if isinstance(v, dict)}
        self.maybe_startup_closure_greet()

    def canonical_item_name(self, name):
        return self.item_alias.get(name, name)

    def canonical_spell_name(self, name):
        return self.spell_alias.get(name, name)

    def display_item_name(self, name):
        cid = self.canonical_item_name(name)
        return self.item_display.get(cid, cid)

    def display_spell_name(self, name):
        cid = self.canonical_spell_name(name)
        return self.spell_display.get(cid, cid)

    def load_game_data(self):
        cfg = load_json(CONFIG_FILE)
        self.spawn_interval = cfg.get("spawn_interval", self.spawn_interval)
        self.message_show_time = cfg.get("message_show_time", self.message_show_time)
        self.message_fade_time = cfg.get("message_fade_time", self.message_fade_time)
        self.transition_duration = cfg.get("transition_duration", self.transition_duration)
        self.move_anim_duration = cfg.get("move_anim_duration", self.move_anim_duration)
        self.leave_rogue_hp = cfg.get("leave_rogue_hp", 100)
        self._load_item_defs(load_json(ITEMS_FILE))
        raw_shop = load_json(SHOP_FILE)
        self._refresh_equipment_layout()
        self.shop_all_items = self._build_synced_shop_items(raw_shop)
        self.shop_items = list(self.shop_all_items)
        self._load_spells(load_json(SPELLS_FILE))
        self.objectives_cfg = load_json(OBJECTIVES_FILE)
        self.rogue_cfg = load_json(ROGUE_FILE)

    def _load_item_defs(self, raw_defs):
        defs = {}
        alias = {}
        display = {}
        if not isinstance(raw_defs, dict):
            raw_defs = {}
        for key, data in raw_defs.items():
            if not isinstance(data, dict):
                continue
            item_id = data.get("id", key)
            item_id = str(item_id)
            node = dict(data)
            node.pop("id", None)
            defs[item_id] = node
            alias[item_id] = item_id
            alias[key] = item_id
            display[item_id] = key
        self.item_defs = defs
        self.item_alias = alias
        self.item_display = display
        self.inventory = {self.canonical_item_name(k): int(v) for k, v in self.inventory.items()}
        self.inventory = {k: v for k, v in self.inventory.items() if k and isinstance(v, int)}
        self.equipment = {k: self.canonical_item_name(v) if v else None for k, v in self.equipment.items()}

    def _load_spells(self, raw_spells):
        spells = []
        alias = {}
        display = {}
        if not isinstance(raw_spells, list):
            raw_spells = []
        for sp in raw_spells:
            if not isinstance(sp, dict):
                continue
            sid = str(sp.get("id", sp.get("name", "")))
            if not sid:
                continue
            node = dict(sp)
            disp = str(node.get("name", sid))
            node["name"] = sid
            node.pop("id", None)
            spells.append(node)
            alias[sid] = sid
            alias[disp] = sid
            display[sid] = disp
        self.spells = spells
        self.spell_alias = alias
        self.spell_display = display
        self.magic_hotbar_slots = [self.canonical_spell_name(v) if v else None for v in self.magic_hotbar_slots]

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
            name = self.canonical_item_name(row.get("name"))
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
        map_path = resolve_map_file(mapname)
        self.map = GameMap(map_path)
        # Prevent hostile entities from leaking across map transitions.
        if hasattr(self, "entities"):
            self.entities = [
                e for e in self.entities
                if e.eid == "player" or e.ai_type == "team" or npc_data.get(e.eid) is not None or e.immortal
            ]
        # map_1/map_2/map_3 stay fully pre-coded; do not randomize runtime layout.
        self.map_max_h_mob = self.map.mob_limit
        self.player_move_anim = None
        if hasattr(self, "entities"):
            self.place_npcs_for_map()
            self.teleport_team_to_player()
            self.ensure_monst3r_entity()
            self.ensure_wisadel_entity()
        self.set_objectives_for_map()
        self.show_enter_banner(mapname)
        if self.map.name == "rouge_options.json":
            self.rogue_rest_intro_done = False
            self.open_rogue_rest_intro()
        self.mark_map_explored(self.map.name)

    def mark_map_explored(self, map_name):
        if not map_name:
            return
        if not isinstance(getattr(self, "explored_maps", None), set):
            self.explored_maps = set()
        self.explored_maps.add(map_name)

    def _normalize_map_ref(self, name):
        if not name:
            return ""
        if name == "rogue":
            return "rogue"
        return name if name.endswith(".json") else f"{name}.json"

    def _build_world_map_graph(self):
        nodes = {}
        edges = set()
        try:
            for fpath in iter_all_map_files():
                fname = os.path.basename(fpath)
                try:
                    data = load_json(fpath)
                except Exception:
                    continue
                grid = data.get("grid", [])
                h = len(grid)
                w = len(grid[0]) if h > 0 and isinstance(grid[0], list) else 0
                if w <= 0 or h <= 0:
                    continue
                key = self._normalize_map_ref(fname)
                nodes[key] = {"w": int(w), "h": int(h)}
                for p in data.get("portals", []):
                    target = self._normalize_map_ref(p.get("target_map", ""))
                    if not target:
                        continue
                    a, b = sorted([key, target])
                    edges.add((a, b))
            if "rogue" not in nodes:
                nodes["rogue"] = {"w": 20, "h": 20}
            for a, b in list(edges):
                if a not in nodes:
                    nodes[a] = {"w": 20, "h": 20}
                if b not in nodes:
                    nodes[b] = {"w": 20, "h": 20}
        except Exception:
            pass
        self.world_map_nodes = nodes
        self.world_map_edges = sorted(list(edges))

    def place_npcs_for_map(self):
        positions = {
            "map_1.json": [(1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (6, 8), (7, 8)],
            # map_2: keep NPCs near left entrance (portal at x=0,y=15) with 1-tile gap.
            "map_2.json": [(2, 16), (3, 16), (4, 16), (5, 16), (6, 16), (7, 16), (8, 16)],
            "map_3.json": [(1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (6, 8), (7, 8)],
            "rogue": [(1, 12), (1, 13), (-999, -999), (-999, -999), (-999, -999), (-999, -999), (-999, -999)],
            "rouge_options.json": [(4, 5), (6, 5), (-999, -999), (-999, -999), (-999, -999), (-999, -999), (-999, -999)]
        }
        order = ["dev", "priestess", "carmen", "closure", "kaltsit", "ines", "shu"]
        spots = positions.get(self.map.name, [])
        for i, npc_id in enumerate(order):
            ent = next((e for e in self.entities if e.eid == npc_id), None)
            if ent is None:
                data = npc_data.get(npc_id, {})
                ent = Entity(npc_id, 0, 0, data.get('hp', 1), data.get('mp', 0), data.get('attack', 0), data.get('defence', 0), data.get('ai_type'), data.get('immortal', False))
                ent.magic_attack = int(data.get("magic_attack", data.get("attack", 0)))
                ent.magic_defense = float(data.get("magic_defense", 0.0))
                ent.attack_type = str(data.get("attack_type", "P")).upper()
                self.entities.append(ent)
            self._ensure_entity_combat_profile(ent)
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
        if 'ines' in npc_data:
            idata = npc_data['ines']
            self.entities.append(
                Entity('ines', 9, 8, idata.get('hp', 1), idata.get('mp', 0), idata.get('attack', 0), idata.get('defence', 0), idata.get('ai_type'), idata.get('immortal', False))
            )
        for ent in self.entities:
            self._ensure_entity_combat_profile(ent)

    def _ensure_entity_combat_profile(self, ent):
        if not hasattr(ent, "magic_attack"):
            ent.magic_attack = int(getattr(ent, "attack", 0))
        if not hasattr(ent, "magic_defense"):
            ent.magic_defense = 0.0
        if not hasattr(ent, "attack_type"):
            ent.attack_type = "P"

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
            "map_1.json": [(x, 8) for x in range(1, 8)],
            "map_2.json": [(x, 16) for x in range(2, 8)],
            "map_3.json": [(x, 8) for x in range(1, 8)],
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
                # "08" (bush without berries) should only appear after harvesting.
                self.map.grid[y][x] = random.choice(["09"])
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
        # Prevent corner-cutting through diagonal stone gaps:
        # diagonal move is blocked if either orthogonal side is not walkable.
        if dx != 0 and dy != 0:
            if (not self.map.is_walkable(self.player.x + dx, self.player.y)) or (
                not self.map.is_walkable(self.player.x, self.player.y + dy)
            ):
                return False
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
                self.update(player_tick=False)
                return True
            if getattr(target, "immortal", False):
                return False
            player_damage = self.compute_outgoing_damage(self.player, target)
            enemy_damage, reflect = self.compute_player_damage(target, self.player)
            target.hp -= player_damage
            if target.hp <= 0:
                target.hp = -1
                self.player.x, self.player.y = nx, ny
                self.player_move_anim = {"from": (oldx, oldy), "to": (nx, ny), "start": time.time(), "duration": self.move_anim_duration}
                self.on_enemy_death(target)
                self.state_cleanup()
                self.update(player_tick=False)
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
        self.update(player_tick=False)
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
                            self.teleport_team_to_player()
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
        self.add_exp(int(mob.get("exp_reward", 10)))

        # Mission progress (multi-mission)
        for mission in self.get_active_missions():
            if mission.get("done"):
                continue
            mtype = mission.get("type")
            if mtype == "kill_any":
                mission["progress"] = min(mission["target"], mission.get("progress", 0) + 1)
            elif mtype == "kill_specific" and ent.eid == mission.get("mob"):
                mission["progress"] = min(mission["target"], mission.get("progress", 0) + 1)
            if mission.get("progress", 0) >= mission.get("target", 0):
                mission["done"] = True
                self.on_kaltsit_mission_complete(mission)

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

    def exp_to_next_level(self):
        if self.player_level < 20:
            return self.player_level * 10
        return self.player_level * 30

    def skill_points_on_level_up(self):
        return 3 if self.player_level < 20 else 2

    def add_exp(self, amount):
        if amount <= 0:
            return
        self.player_exp += amount
        leveled = 0
        while self.player_exp >= self.exp_to_next_level():
            need = self.exp_to_next_level()
            self.player_exp -= need
            self.player_level += 1
            gained = self.skill_points_on_level_up()
            self.player_skill_points += gained
            leveled += 1
            self.push_message(tr(self.lang, "msg.level_up", level=self.player_level, sp=gained))
            if self.player_level % 5 == 0:
                self.level_stat_pending += 1
        if leveled == 0:
            self.push_message(tr(self.lang, "msg.exp_gain", amount=amount))
        elif self.level_stat_pending > 0 and self.ui_mode is None:
            self.ui_mode = "level_stat_choice"
            self.level_stat_selected = 0

    def _team_entity_for(self, member_id):
        return next((e for e in self.entities if e.eid == member_id), None)

    def get_team_member_ids(self):
        return [m for m in self.team_members if isinstance(m, str)]

    def _team_slot_label(self, slot):
        if slot == "weapon":
            return tr(self.lang, "label.weapon")
        if slot == "armor":
            return tr(self.lang, "label.armor")
        if slot == "ring":
            return tr(self.lang, "team.slot.ring")
        return slot

    def get_team_slot_keys(self):
        return ["weapon", "armor", "ring"]

    def _team_member_for_equip(self):
        members = self.get_team_member_ids()
        if not members:
            return None
        idx = max(0, min(len(members) - 1, int(getattr(self, "team_equip_member_selected", 0))))
        return members[idx]

    def get_team_equip_categories(self):
        return list(self.get_team_slot_keys())

    def open_team_equip(self, member_idx=None):
        members = self.get_team_member_ids()
        if not members:
            self.ui_mode = "team"
            return
        if member_idx is None:
            member_idx = int(getattr(self, "team_selected", 0))
        self.team_equip_member_selected = max(0, min(len(members) - 1, int(member_idx)))
        self.team_selected = self.team_equip_member_selected
        self.team_equip_root_selected = 0
        self.team_equip_focus = "tabs"
        self.team_equip_slot_selected = 0
        self.team_equip_item_selected = 0
        categories = self.get_team_equip_categories()
        self.team_equip_category = categories[0] if categories else "weapon"
        self.ui_mode = "team_equip"

    def open_team_equip_items(self):
        self.ui_mode = "team_equip"
        self.team_equip_focus = "items"

    def get_team_equipable_items(self):
        return self.get_equipable_items()

    def team_equip_selected_item(self):
        member = self._team_member_for_equip()
        if not member:
            return
        equipables = self.get_team_equipable_items()
        slot_key = "ring" if self.team_equip_category.startswith("ring") else self.team_equip_category
        filtered = [n for n in equipables if self.item_defs.get(n, {}).get("slot") == slot_key]
        if not filtered:
            self.push_message(tr(self.lang, "msg.no_items_category"))
            return
        idx = self.team_equip_item_selected % len(filtered)
        picked = filtered[idx]
        self.equip_item_to_team_member(member, self.team_equip_category, picked)

    def team_unequip_all(self):
        member = self._team_member_for_equip()
        if not member:
            return
        row = self._ensure_team_equipment_for_member(member)
        for slot in self.get_team_slot_keys():
            row[slot] = None
        self.sync_team_stats()
        self.push_message(tr(self.lang, "msg.unequipped_all"))

    def team_equip_best(self):
        member = self._team_member_for_equip()
        if not member:
            return
        changed = False
        row = self._ensure_team_equipment_for_member(member)
        for slot in self.get_team_slot_keys():
            slot_key = "ring" if slot.startswith("ring") else slot
            candidates = []
            for name in self.get_team_equipable_items():
                item_def = self.item_defs.get(name, {})
                if item_def.get("slot") != slot_key:
                    continue
                if self.inventory.get(name, 0) <= 0:
                    continue
                candidates.append(name)
            if not candidates:
                continue
            best = max(candidates, key=lambda n: self._item_power_score(self.item_defs.get(n, {})))
            if row.get(slot) != best:
                row[slot] = best
                changed = True
        self.sync_team_stats()
        if changed:
            self.push_message(tr(self.lang, "msg.equip_best_done"))
        else:
            self.push_message(tr(self.lang, "msg.equip_best_no_change"))

    def _team_slot_by_idx(self, idx):
        slots = self.get_team_slot_keys()
        if not slots:
            return "weapon"
        return slots[idx % len(slots)]

    def _normalize_team_equipment(self, raw):
        out = {}
        src = raw if isinstance(raw, dict) else {}
        for member in self.get_team_member_ids():
            row = src.get(member, {})
            if not isinstance(row, dict):
                row = {}
            fixed = {}
            for slot in self.get_team_slot_keys():
                name = row.get(slot)
                fixed[slot] = self.canonical_item_name(name) if name else None
            out[member] = fixed
        self.team_equipment = out

    def _ensure_team_equipment_for_member(self, member_id):
        if member_id not in self.team_equipment:
            self.team_equipment[member_id] = {slot: None for slot in self.get_team_slot_keys()}
        row = self.team_equipment.get(member_id, {})
        for slot in self.get_team_slot_keys():
            row.setdefault(slot, None)
        self.team_equipment[member_id] = row
        return row

    def get_team_equipment_item(self, member_id, slot):
        row = self._ensure_team_equipment_for_member(member_id)
        return row.get(slot)

    def get_team_equipable_items_for_slot(self, slot):
        out = []
        want = "ring" if slot == "ring" else slot
        for name in self.get_equipable_items():
            idef = self.item_defs.get(name, {})
            if idef.get("slot") == want:
                out.append(name)
        return out

    def equip_item_to_team_member(self, member_id, slot, item_name):
        if member_id not in self.get_team_member_ids():
            return False
        row = self._ensure_team_equipment_for_member(member_id)
        if not item_name:
            row[slot] = None
            self.sync_team_stats()
            return True
        item_id = self.canonical_item_name(item_name)
        idef = self.item_defs.get(item_id, {})
        if idef.get("type") != "equipment":
            return False
        if idef.get("slot") != ("ring" if slot == "ring" else slot):
            return False
        if self.inventory.get(item_id, 0) <= 0:
            self.push_message(tr(self.lang, "msg.not_enough_items"))
            return False
        row[slot] = item_id
        self.sync_team_stats()
        self.push_message(
            tr(
                self.lang,
                "msg.team_item_equipped",
                member=member_id,
                item=self.display_item_name(item_id),
                slot=self._team_slot_label(slot),
            )
        )
        return True

    def apply_team_member_bonus(self, ent):
        if ent is None or ent.eid not in ("monst3r", "wisadel"):
            return
        member_id = ent.eid
        row = self._ensure_team_equipment_for_member(member_id)
        base_ratio = float(self.team_sync_ratio_base.get(member_id, 0.2))
        equipped_count = sum(1 for v in row.values() if v)
        ratio = base_ratio + 0.1 * equipped_count
        max_ratio = 0.6 if member_id == "monst3r" else 0.8
        ratio = max(0.0, min(max_ratio, ratio))

        bonus_hp = 0
        bonus_mp = 0
        bonus_atk = 0
        bonus_def = 0
        for _, name in row.items():
            if not name:
                continue
            idef = self.item_defs.get(name, {})
            bonus_hp += int(idef.get("hp", 0))
            bonus_mp += int(idef.get("mp", 0))
            bonus_atk += int(idef.get("attack", 0))
            bonus_def += int(idef.get("defence", 0))

        ent.max_hp = max(1, int(self.player.max_hp * ratio) + bonus_hp)
        ent.max_mp = max(0, int(self.player.max_mp * ratio) + bonus_mp)
        ent.attack = max(1, int(self.player.attack * ratio) + bonus_atk)
        ent.defence = max(0, int(self.player.defence * ratio) + bonus_def)
        if ent.hp > ent.max_hp:
            ent.hp = ent.max_hp
        if ent.mp > ent.max_mp:
            ent.mp = ent.max_mp

    def sync_team_stats(self):
        self._normalize_team_equipment(self.team_equipment)
        self.apply_team_member_bonus(self._team_entity_for("monst3r"))
        self.apply_team_member_bonus(self._team_entity_for("wisadel"))

    def get_level_stat_options(self):
        return [
            {"id": "hp", "name": tr(self.lang, "level_stat.hp"), "value": 80},
            {"id": "mp", "name": tr(self.lang, "level_stat.mp"), "value": 40},
            {"id": "attack", "name": tr(self.lang, "level_stat.attack"), "value": 8},
            {"id": "defence", "name": tr(self.lang, "level_stat.defence"), "value": 3},
        ]

    def choose_level_stat(self, idx):
        opts = self.get_level_stat_options()
        if self.level_stat_pending <= 0 or not opts:
            return False
        pick = opts[idx % len(opts)]
        sid = pick["id"]
        val = int(pick["value"])
        if sid == "hp":
            self.player.max_hp += val
            self.player.hp = self.player.max_hp
        elif sid == "mp":
            self.player.max_mp += val
            self.player.mp = self.player.max_mp
        elif sid == "attack":
            self.player.base_attack += val
        elif sid == "defence":
            self.player.base_defence += val
        self.level_stat_pending = max(0, self.level_stat_pending - 1)
        self.recalculate_stats()
        self.push_message(tr(self.lang, "msg.level_stat_chosen", name=pick["name"], value=val))
        if self.level_stat_pending > 0:
            self.ui_mode = "level_stat_choice"
            self.level_stat_selected = 0
        elif self.ui_mode == "level_stat_choice":
            self.ui_mode = None
        return True

    def state_cleanup(self):
        self.entities = [e for e in self.entities if e.eid == 'player' or e.immortal or e.hp > 0]

    def check_player_death(self):
        if self.player.hp <= 0:
            if self.ui_mode == "death_menu":
                return
            if self.map.name == "rogue":
                rate = self.rogue_cfg.get("death_penalty_rate", 0.2)
                self.money = int(self.money * (1 - rate))
                self.return_from_rogue()
                self.death_timer = None
                return
            self.ui_mode = "death_menu"
            self.death_menu_selected = 0
            self.death_no_save_notice = ""
            self.death_timer = None
        else:
            self.death_timer = None

    def handle_death_menu_confirm(self):
        if self.ui_mode != "death_menu":
            return
        if self.death_no_save_notice:
            self.request_quit = True
            return
        if self.death_menu_selected == 0:
            self.money = int(self.money * 0.5)
            self.player.hp = self.player.max_hp
            self.player.mp = self.player.max_mp
            self.ui_mode = None
            return
        if self.load_latest_save():
            self.ui_mode = None
            return
        self.death_no_save_notice = "welp, looks like you dont have any saves, adios then"

    def start_blackout(self):
        self.blackout = 1
        self.black_alpha = 0

    def update(self, player_tick=False):
        if self.is_ui_blocking():
            return
        if player_tick:
            self.last_player_tile = (self.player.x, self.player.y)
            self.tick += 1
            self.update_spell_cooldowns_tick()
            for ent in self.entities:
                if ent.eid != 'player':
                    self.update_enemy(ent)
            self.update_monst3r(player_tick=True)
            self.update_wisadel(player_tick=True)
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
        self.update_wisadel(player_tick=False)
        self.cleanup_messages()

    def ensure_monst3r_entity(self):
        if not self.monst3r_unlocked:
            self.entities = [e for e in self.entities if e.eid != "monst3r"]
            return
        if any(e.eid == "monst3r" for e in self.entities):
            self.teleport_team_to_player()
            return
        hp = max(1, int(self.player.max_hp * 0.2))
        mp = max(0, int(self.player.max_mp * 0.2))
        atk = max(1, int(self.player.attack * 0.2))
        dfs = max(0, int(self.player.defence * 0.2))
        spawn_x, spawn_y = self._find_team_spawn_near_player()
        if spawn_x is None or spawn_y is None:
            return
        mon = Entity("monst3r", spawn_x, spawn_y, hp, mp, atk, dfs, ai_type="team")
        mon.move_interval = 1
        self.entities.append(mon)
        if "monst3r" not in self.team_members:
            self.team_members.append("monst3r")
        self._ensure_team_equipment_for_member("monst3r")
        self.apply_team_member_bonus(mon)

    def _find_team_spawn_near_player(self, ignore_eid=None):
        candidates = [
            (self.player.x - 1, self.player.y),
            (self.player.x + 1, self.player.y),
            (self.player.x, self.player.y - 1),
            (self.player.x, self.player.y + 1),
            (self.player.x - 1, self.player.y - 1),
            (self.player.x + 1, self.player.y - 1),
            (self.player.x - 1, self.player.y + 1),
            (self.player.x + 1, self.player.y + 1),
        ]
        for tx, ty in candidates:
            blocker = self.entity_at(tx, ty)
            if self.map.is_walkable(tx, ty) and (blocker is None or blocker.eid == ignore_eid):
                return tx, ty
        return None, None

    def _is_hostile_entity(self, ent):
        return ent.eid != "player" and ent.ai_type != "team" and mobs_data.get(ent.eid, {}).get("ai_type") == "hostile" and ent.hp > 0

    def teleport_team_to_player(self):
        for member_id in ("monst3r", "wisadel"):
            ent = next((e for e in self.entities if e.eid == member_id), None)
            if ent is None:
                continue
            tx, ty = self._find_team_spawn_near_player(ignore_eid=member_id)
            if tx is None or ty is None:
                continue
            ent.x, ent.y = tx, ty

    def on_kaltsit_mission_complete(self, mission=None):
        mission = mission or self.kaltsit_mission or {}
        if mission.get("rewarded"):
            return
        mission["rewarded"] = True
        self.kaltsit_completed += 1
        self.push_message(tr(self.lang, "msg.mission_complete_count", count=self.kaltsit_completed))
        if self.kaltsit_completed >= 10 and not self.monst3r_unlocked:
            self.kaltsit_reward_ready = True
        if self.kaltsit_completed >= 10 and not self.wisadel_unlocked:
            self.ines_reward_ready = True

    def ensure_wisadel_entity(self):
        if not self.wisadel_unlocked:
            self.entities = [e for e in self.entities if e.eid != "wisadel"]
            return
        if any(e.eid == "wisadel" for e in self.entities):
            self.teleport_team_to_player()
            return
        hp = max(1, int(self.player.max_hp * 0.4))
        mp = max(0, int(self.player.max_mp * 0.4))
        atk = max(1, int(self.player.attack * 0.4))
        dfs = max(0, int(self.player.defence * 0.4))
        spawn_x, spawn_y = self._find_team_spawn_near_player()
        if spawn_x is None or spawn_y is None:
            return
        wis = Entity("wisadel", spawn_x, spawn_y, hp, mp, atk, dfs, ai_type="team")
        wis.move_interval = 1
        self.entities.append(wis)
        if "wisadel" not in self.team_members:
            self.team_members.append("wisadel")
        self._ensure_team_equipment_for_member("wisadel")
        self.apply_team_member_bonus(wis)

    def update_wisadel(self, player_tick=False):
        wis = next((e for e in self.entities if e.eid == "wisadel"), None)
        if wis is None:
            return
        self.apply_team_member_bonus(wis)
        if not player_tick:
            return
        if self._is_anim_locked("wisadel"):
            return
        if time.time() >= self.wisadel_anim_until:
            self.wisadel_anim_state = "move"
        hostiles = [e for e in self.entities if self._is_hostile_entity(e)]
        target = None
        best_dist = 9999
        for e in hostiles:
            dist = abs(e.x - wis.x) + abs(e.y - wis.y)
            if dist <= 8 and dist < best_dist:
                best_dist = dist
                target = e
        if target is None:
            tx, ty = self.last_player_tile
            if (wis.x, wis.y) == (tx, ty):
                return
            path = self.find_path((wis.x, wis.y), (tx, ty))
            if path and len(path) > 1:
                nx, ny = path[1]
                if self.map.is_walkable(nx, ny) and self.entity_at(nx, ny) is None:
                    wis.x, wis.y = nx, ny
                    self.wisadel_anim_state = "move"
            return
        if best_dist <= 5:
            dmg = max(1, int(wis.attack * (1 - target.defence / 100)))
            target.hp -= dmg
            self._play_entity_action_anim("wisadel", "skill3", fallback_seconds=0.6)
            if target.hp <= 0:
                self.on_enemy_death(target)
                self.state_cleanup()
            return
        path = self.find_path((wis.x, wis.y), (target.x, target.y))
        if path and len(path) > 1:
            nx, ny = path[1]
            if self.map.is_walkable(nx, ny) and self.entity_at(nx, ny) is None:
                wis.x, wis.y = nx, ny
                self.wisadel_anim_state = "move"

    def update_monst3r(self, player_tick=False):
        mon = next((e for e in self.entities if e.eid == "monst3r"), None)
        if mon is None:
            return
        self.apply_team_member_bonus(mon)
        if not player_tick:
            return
        if self._is_anim_locked("monst3r"):
            return
        if time.time() >= self.monst3r_anim_until:
            self.monst3r_anim_state = "move"
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
                if self.map.is_walkable(nx, ny) and self.entity_at(nx, ny) is None:
                    mon.x, mon.y = nx, ny
                    self.monst3r_anim_state = "move"
            return
        if best_dist <= 1:
            dmg = max(1, int(mon.attack * (1 - target.defence / 100)))
            target.hp -= dmg
            self._play_entity_action_anim("monst3r", "skill3", fallback_seconds=1.0)
            if target.hp <= 0:
                self.on_enemy_death(target)
                self.state_cleanup()
            return
        path = self.find_path((mon.x, mon.y), (target.x, target.y))
        if path and len(path) > 1:
            nx, ny = path[1]
            if self.map.is_walkable(nx, ny) and self.entity_at(nx, ny) is None:
                mon.x, mon.y = nx, ny
                self.monst3r_anim_state = "move"

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

    def has_attention_ring(self):
        return any(
            slot.startswith("ring") and name == "AtTENtioN RiNG"
            for slot, name in self.equipment.items()
        )

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
        # Smoothstep easing to reduce tile-snap feeling.
        t = t * t * (3.0 - 2.0 * t)
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
        missions = self.get_active_missions()
        if not missions:
            return lines
        for mission in missions:
            giver = str(mission.get("giver", "kaltsit"))
            giver_name = giver.capitalize()
            text = self._mission_text_short(mission)
            if text:
                lines.append(f"{giver_name}: {text}")
        return lines

    def get_trackable_missions(self):
        missions = []
        for mission in self.get_active_missions():
            giver = str(mission.get("giver", "kaltsit"))
            missions.append({
                "id": giver,
                "name": giver.capitalize(),
                "text": self._mission_text_short(mission),
                "done": bool(mission.get("done", False)),
            })
        return missions

    def _mission_text_short(self, mission):
        mtype = mission.get("type")
        if mtype == "kill_specific":
            return tr(
                self.lang,
                "mission.kill_specific",
                mob=mission.get("mob", "slime"),
                progress=mission.get("progress", 0),
                target=mission.get("target", 1),
            )
        if mtype == "kill_any":
            return tr(
                self.lang,
                "mission.kill_any",
                progress=mission.get("progress", 0),
                target=mission.get("target", 1),
            )
        if mtype == "reach_layer":
            return tr(
                self.lang,
                "mission.reach_layer",
                progress=mission.get("progress", 0),
                target=mission.get("target", 1),
            )
        return ""

    def set_tracked_selected_mission(self):
        missions = self.get_trackable_missions()
        if not missions:
            self.tracked_mission = None
            return
        idx = max(0, min(len(missions) - 1, int(getattr(self, "objective_selected", 0))))
        mid = missions[idx].get("id")
        self.tracked_mission = mid

    def toggle_track_selected_mission(self):
        # Backward-compatible alias: tracking is a reminder target, not a toggle.
        self.set_tracked_selected_mission()

    def get_tracking_summary_lines(self):
        missions = self.get_trackable_missions()
        tracked = getattr(self, "tracked_mission", None)
        if missions and not any(m.get("id") == tracked for m in missions):
            tracked = missions[0].get("id")
            self.tracked_mission = tracked
        for row in missions:
            if row.get("id") != tracked:
                continue
            text = row.get("text", "")
            if not text:
                return []
            return [f"{row.get('name', 'Mission')}: {text}"]
        return []

    def _ensure_active_missions(self):
        pool = getattr(self, "active_missions", None)
        if not isinstance(pool, list):
            pool = []
            self.active_missions = pool
        legacy = getattr(self, "kaltsit_mission", None)
        if isinstance(legacy, dict):
            giver = str(legacy.get("giver", "kaltsit"))
            if not any(isinstance(m, dict) and str(m.get("giver", "kaltsit")) == giver and not m.get("done") for m in pool):
                pool.append(legacy)
        return pool

    def get_active_missions(self):
        pool = self._ensure_active_missions()
        out = [m for m in pool if isinstance(m, dict) and not m.get("done")]
        # Keep legacy pointer consistent for old call sites/save compatibility.
        self.kaltsit_mission = out[0] if out else None
        return out

    def get_mission_by_giver(self, giver):
        giver = str(giver or "kaltsit")
        for m in self.get_active_missions():
            if str(m.get("giver", "kaltsit")) == giver:
                return m
        return None

    def add_active_mission(self, mission):
        if not isinstance(mission, dict):
            return
        mission["giver"] = str(mission.get("giver", "kaltsit"))
        pool = self._ensure_active_missions()
        pool.append(mission)
        if not getattr(self, "tracked_mission", None):
            self.tracked_mission = mission.get("giver")
        self.kaltsit_mission = mission

    def get_skill_tree_nodes(self):
        return [
            {
                "id": "harvest_barries",
                "name": tr(self.lang, "skill.harvest_barries"),
                "cost": 5,
                "unlocked": self.skill_tree.get("harvest_barries", False),
            }
        ]

    def unlock_selected_skill(self):
        nodes = self.get_skill_tree_nodes()
        if not nodes:
            return
        node = nodes[self.skill_tree_selected % len(nodes)]
        if node["unlocked"]:
            self.push_message(tr(self.lang, "msg.skill_already_unlocked"))
            return
        if self.player_skill_points < node["cost"]:
            self.push_message(tr(self.lang, "msg.not_enough_sp"))
            return
        self.player_skill_points -= node["cost"]
        self.skill_tree[node["id"]] = True
        self.push_message(tr(self.lang, "msg.skill_unlocked", name=node["name"]))

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
            self.teleport_team_to_player()
            self.player.hp = self.player.max_hp
            self.inventory["retreat item"] = 0
            self.environment_difficulty = 0.0
            # Keep legacy field in sync for backward compatibility.
            self.rogue_difficulty = 0.0
            self.push_message(tr(self.lang, "msg.retreat_cleared"))
        self.start_transition(do_return)

    def enter_rogue_layer(self, new_entry=False):
        return game_rogue_ops.enter_rogue_layer(self, new_entry)

    def get_env_tier(self):
        step = 0.20
        value = max(0.0, float(getattr(self, "environment_difficulty", 0.0)))
        return int(min(6, (value + 1e-9) / step))

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
            defence = mob.get('defence', 0)
            magic_attack = mob.get("magic_attack", atk)
            magic_defense = mob.get("magic_defense", 0)
            if self.map.name == "rogue":
                mult = 1.0 + max(0.0, float(getattr(self, "environment_difficulty", 0.0)))
                hp = int(hp * mult)
                atk = int(atk * mult)
                defence = int(defence * mult)
                magic_attack = int(magic_attack * mult)
                magic_defense = int(magic_defense * mult)
            ent = Entity(mob_id, x, y, hp, mob.get('mp', 0), atk, defence, mob.get('ai_type'), mob.get('immortal', False))
            ent.magic_attack = int(magic_attack)
            ent.magic_defense = float(magic_defense)
            ent.attack_type = str(mob.get("attack_type", "P")).upper()
            self._ensure_entity_combat_profile(ent)
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
        force_detect = self.has_attention_ring()
        detect_range = int(mob.get("detect_range", 0))
        attack_range = int(mob.get("attack_range", 1 if ent.eid != "soldier" else 2))
        if getattr(ent, "is_boss", False):
            px, py = self.player.x, self.player.y
            dist = abs(ent.x - px) + abs(ent.y - py)
            if dist <= 1:
                enemy_damage, reflect = self.compute_player_damage(ent, self.player)
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
        ent.aggro_active = bool(getattr(ent, "aggro_active", False))
        if force_detect or dist <= detect_range:
            ent.aggro_active = True
        elif dist > detect_range:
            ent.aggro_active = False
        if not ent.aggro_active:
            return
        if dist <= attack_range:
            enemy_damage, reflect = self.compute_player_damage(ent, self.player)
            self.player.hp -= enemy_damage
            if reflect > 0 and ent.hp > 0:
                ent.hp -= reflect
                if ent.hp <= 0:
                    self.on_enemy_death(ent)
            self.check_player_death()
            return
        if force_detect or dist <= detect_range or ent.aggro_active:
            self.move_enemy_toward(ent, (px, py))

    def move_enemy_toward(self, ent, goal):
        path = self.find_path((ent.x, ent.y), goal)
        if path and len(path) > 1:
            nx, ny = path[1]
            if not self.entity_at(nx, ny):
                ent.x, ent.y = nx, ny

    def _clamp_md(self, value):
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0

    def _compute_physical_damage(self, pa, pd):
        pa = max(0.0, float(pa))
        pd = max(0.0, float(pd))
        if pa > pd:
            return int(pa)
        if pa == pd:
            return int(pa * 0.5)
        return int(pa * 0.2)

    def _compute_magic_damage(self, ma, md):
        ma = max(0.0, float(ma))
        md = self._clamp_md(md)
        return int(ma * (1.0 - md))

    def _entity_attack_type(self, attacker):
        if attacker is None:
            return "P"
        if attacker.eid == "player":
            weapon = self.equipment.get("weapon")
            if not weapon:
                return "P"
            idef = self.item_defs.get(weapon, {})
            at = str(idef.get("weapon_attack_type", idef.get("attack_type", ""))).upper()
            if at in ("P", "M"):
                return at
            return self.DEFAULT_WEAPON_ATTACK_TYPE.get(weapon, "P")
        return str(getattr(attacker, "attack_type", "P")).upper() if str(getattr(attacker, "attack_type", "P")).upper() in ("P", "M") else "P"

    def compute_outgoing_damage(self, attacker, defender):
        atk_type = self._entity_attack_type(attacker)
        pa = float(getattr(attacker, "attack", 0))
        pd = float(getattr(defender, "defence", 0))
        ma = float(getattr(attacker, "magic_attack", getattr(attacker, "attack", 0)))
        md = getattr(defender, "magic_defense", 0)
        if atk_type == "M":
            return self._compute_magic_damage(ma, md)
        return self._compute_physical_damage(pa, pd)

    def compute_player_damage(self, attacker, defender=None):
        if defender is None:
            defender = self.player
        return self.compute_outgoing_damage(attacker, defender), 0

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

    def confirm_interact_choice(self):
        return game_npc_ops.confirm_interact_choice(self)

    def cancel_interact_choice(self):
        return game_npc_ops.cancel_interact_choice(self)

    def try_harvest_bush(self):
        return game_npc_ops.try_harvest_bush(self)

    def open_dialog(self, npc_id, source="script"):
        return game_npc_ops.open_dialog(self, npc_id, source=source)

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

    def grant_pre_dev_set(self):
        return game_npc_ops.grant_pre_dev_set(self)

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

    def get_item_categories(self):
        return game_inventory_ops.get_item_categories(self)

    def cycle_item_category(self, step):
        return game_inventory_ops.cycle_item_category(self, step)

    def use_item(self):
        return game_inventory_ops.use_item(self)

    def cast_spell(self):
        return game_inventory_ops.cast_spell(self)

    def use_item_by_name(self, name):
        name = self.canonical_item_name(name)
        if name == "rogue level skipper":
            self.use_level_skipper_hotbar()
            return
        item_type = self.item_defs.get(name, {}).get("type")
        type_to_cat = {
            "consumable": "item",
            "gift": "gift",
            "equipment": "equipment",
            "special": "special",
        }
        old_category = getattr(self, "item_category", "item")
        if item_type in type_to_cat:
            self.item_category = type_to_cat[item_type]
        items = self.get_item_list()
        if name not in items:
            self.item_category = old_category
            self.push_message(tr(self.lang, "msg.no_items"))
            return
        self.item_selected = items.index(name)
        self.use_item()
        self.item_category = old_category

    def use_level_skipper_hotbar(self):
        return game_rogue_ops.use_level_skipper_hotbar(self)

    def _clips_base_dir(self):
        # legacy helper kept for compatibility; folder resolution now uses indexer first
        candidates = resolve_folder_candidates("clips")
        for p in candidates:
            if os.path.isdir(p):
                return p
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "clips")

    def _anim_folder_for_state(self, ent_id, state):
        if ent_id == "wisadel":
            if state == "skill3":
                return "nobg_wisadel_attack"
            return "nobg_wisadel_walk"
        if ent_id == "monst3r":
            if state == "skill3":
                return "nobg_mons3r_attack"
            return "nobg_monst3r_walk"
        return None

    def _anim_fps_for(self, ent_id):
        ent_def = npc_data.get(ent_id, {})
        try:
            return max(1, int(ent_def.get("anim_fps", 12)))
        except Exception:
            return 12

    def _anim_frame_count(self, folder_name):
        if not folder_name:
            return 0
        cache = getattr(self, "_anim_frame_count_cache", {})
        if folder_name in cache:
            return cache[folder_name]
        total = 0
        base_meta = None
        for p in resolve_atlas_candidates(f"{folder_name}_atlas.json"):
            if os.path.isfile(p):
                base_meta = p
                break
        if base_meta:
            meta_files = [base_meta]
            page_idx = 2
            while True:
                page_meta = None
                for p in resolve_atlas_candidates(f"{folder_name}_atlas_p{page_idx:02d}.json"):
                    if os.path.isfile(p):
                        page_meta = p
                        break
                if not page_meta:
                    break
                meta_files.append(page_meta)
                page_idx += 1
            for mp in meta_files:
                try:
                    data = json.loads(open(mp, "r", encoding="utf-8").read())
                    frames = data.get("frames", [])
                    if isinstance(frames, list):
                        total += len(frames)
                except Exception:
                    continue
        else:
            folder = None
            for p in resolve_folder_candidates(folder_name):
                if os.path.isdir(p):
                    folder = p
                    break
            if folder and os.path.isdir(folder):
                total = len([n for n in os.listdir(folder) if n.lower().endswith(".png")])
        cache[folder_name] = total
        self._anim_frame_count_cache = cache
        return total

    def _compute_anim_end_time(self, ent_id, state, fallback_seconds=0.5):
        folder = self._anim_folder_for_state(ent_id, state)
        frames = self._anim_frame_count(folder)
        fps = self._anim_fps_for(ent_id)
        if frames > 0 and fps > 0:
            duration = max(float(fallback_seconds), float(frames) / float(fps))
        else:
            duration = float(fallback_seconds)
        return time.time() + duration

    def _is_anim_locked(self, ent_id):
        now = time.time()
        if ent_id == "wisadel":
            st = getattr(self, "wisadel_anim_state", "move")
            until = float(getattr(self, "wisadel_anim_until", 0.0))
            return st not in ("move", "idle") and now < until
        if ent_id == "monst3r":
            st = getattr(self, "monst3r_anim_state", "move")
            until = float(getattr(self, "monst3r_anim_until", 0.0))
            return st not in ("move", "idle") and now < until
        return False

    def _play_entity_action_anim(self, ent_id, state, fallback_seconds=0.5):
        end_time = self._compute_anim_end_time(ent_id, state, fallback_seconds=fallback_seconds)
        if ent_id == "wisadel":
            self.wisadel_anim_state = state
            self.wisadel_anim_until = end_time
        elif ent_id == "monst3r":
            self.monst3r_anim_state = state
            self.monst3r_anim_until = end_time

    def cast_spell_by_name(self, name):
        return game_inventory_ops.cast_spell_by_name(self, name)

    def update_spell_cooldowns_tick(self):
        return game_inventory_ops.update_spell_cooldowns_tick(self)

    def recalculate_stats(self):
        game_inventory_ops.recalculate_stats(self)
        self.sync_team_stats()
        return None

    def get_equipable_items(self):
        return game_inventory_ops.get_equipable_items(self)
