import os

from ..world.map import npc_data
from ..support.i18n import tr
from ..support.utils import SAVE_DIR, load_json


def open_save(game):
    game.ui_mode = "save"
    game.save_selected = 0


def save_game(game):
    slot = game.save_selected + 1
    save_path = os.path.join(SAVE_DIR, f"slot_{slot}.json")
    payload = {
        "map": game.map.name,
        "player": {
            "name": game.player_name,
            "x": game.player.x,
            "y": game.player.y,
            "hp": game.player.hp,
            "mp": game.player.mp,
            "attack": game.player.attack,
            "defence": game.player.defence,
            "max_hp": game.player.max_hp,
            "max_mp": game.player.max_mp,
        },
        "lang": game.lang,
        "money": game.money,
        "inventory": game.inventory,
        "equipment": game.equipment,
        "objectives": game.objectives,
        "relations": game.relations,
        "kaltsit_mission": game.kaltsit_mission,
        "active_missions": getattr(game, "active_missions", []),
        "tracked_mission": getattr(game, "tracked_mission", None),
        "objective_selected": int(getattr(game, "objective_selected", 0)),
        "kaltsit_intro_done": game.kaltsit_intro_done,
        "ines_intro_done": game.ines_intro_done,
        "kaltsit_completed": game.kaltsit_completed,
        "kaltsit_reward_ready": game.kaltsit_reward_ready,
        "ines_reward_ready": game.ines_reward_ready,
        "monst3r_unlocked": game.monst3r_unlocked,
        "wisadel_unlocked": game.wisadel_unlocked,
        "team_members": game.team_members,
        "rogue_layer": getattr(game, "rogue_layer", 0),
        "level": game.player_level,
        "exp": game.player_exp,
        "skill_points": game.player_skill_points,
        "skill_tree": game.skill_tree,
        "item_hotbar_slots": game.item_hotbar_slots,
        "magic_hotbar_slots": game.magic_hotbar_slots,
        "active_hotbar": game.active_hotbar,
    }
    with open(save_path, "w", encoding="utf-8") as f:
        import json

        json.dump(payload, f, ensure_ascii=False, indent=2)
    game.last_saved = True
    game.last_save_slot = slot
    game.push_message(tr(game.lang, "msg.saved_slot", slot=slot))


def load_save(game, slot):
    save_path = os.path.join(SAVE_DIR, f"slot_{slot}.json")
    if not os.path.isfile(save_path):
        return False
    data = load_json(save_path)
    map_name = data.get("map", "map_1.json")
    game.load_map(map_name)
    pdata = data.get("player", {})
    game.player.x = pdata.get("x", game.player.x)
    game.player.y = pdata.get("y", game.player.y)
    game.player_name = pdata.get("name", game.player_name)
    game.player.max_hp = pdata.get("max_hp", game.player.max_hp)
    game.player.hp = pdata.get("hp", game.player.hp)
    game.player.max_mp = pdata.get("max_mp", game.player.max_mp)
    game.player.mp = pdata.get("mp", game.player.mp)
    game.player.attack = pdata.get("attack", game.player.attack)
    game.player.defence = pdata.get("defence", game.player.defence)
    game.player.base_attack = game.player.attack
    game.player.base_defence = game.player.defence
    game.money = data.get("money", 0)
    saved_inv = data.get("inventory", {})
    if isinstance(saved_inv, dict):
        # legacy key migration
        if "barry" in saved_inv and "berry" not in saved_inv:
            saved_inv["berry"] = saved_inv.get("barry", 0)
        if "rouge level skipper" in saved_inv and "rogue level skipper" not in saved_inv:
            saved_inv["rogue level skipper"] = saved_inv.get("rouge level skipper", 0)
        for name, count in saved_inv.items():
            if isinstance(count, int):
                game.inventory[game.canonical_item_name(name)] = count
    eq = data.get("equipment", game.equipment)
    if isinstance(eq, dict):
        eq = {k: game.canonical_item_name(v) if v else None for k, v in eq.items()}
    game.equipment = game._merge_equipment_slots(eq)
    game.objectives = data.get("objectives", game.objectives)
    game.lang = data.get("lang", game.lang)
    game.relations = data.get("relations", {k: v.get("relation_point", 0) for k, v in npc_data.items() if isinstance(v, dict)})
    game.kaltsit_mission = data.get("kaltsit_mission", game.kaltsit_mission)
    loaded_active = data.get("active_missions", None)
    if isinstance(loaded_active, list):
        game.active_missions = [m for m in loaded_active if isinstance(m, dict)]
    game.tracked_mission = data.get("tracked_mission", getattr(game, "tracked_mission", None))
    game.objective_selected = int(data.get("objective_selected", getattr(game, "objective_selected", 0)))
    game.kaltsit_intro_done = data.get("kaltsit_intro_done", game.kaltsit_intro_done)
    game.ines_intro_done = data.get("ines_intro_done", game.ines_intro_done)
    game.kaltsit_completed = data.get("kaltsit_completed", game.kaltsit_completed)
    game.kaltsit_reward_ready = data.get("kaltsit_reward_ready", game.kaltsit_reward_ready)
    game.ines_reward_ready = data.get("ines_reward_ready", game.ines_reward_ready)
    game.monst3r_unlocked = data.get("monst3r_unlocked", game.monst3r_unlocked)
    game.wisadel_unlocked = data.get("wisadel_unlocked", game.wisadel_unlocked)
    game.team_members = data.get("team_members", game.team_members)
    game.rogue_layer = data.get("rogue_layer", game.rogue_layer)
    game.player_level = int(data.get("level", game.player_level))
    game.player_exp = int(data.get("exp", game.player_exp))
    game.player_skill_points = int(data.get("skill_points", game.player_skill_points))
    loaded_tree = data.get("skill_tree", {})
    if isinstance(loaded_tree, dict):
        game.skill_tree.update(loaded_tree)
    item_slots = data.get("item_hotbar_slots")
    if isinstance(item_slots, list):
        game.item_hotbar_slots = [(game.canonical_item_name(v) if v else None) for v in (item_slots + [None] * 10)[:10]]
    magic_slots = data.get("magic_hotbar_slots")
    if isinstance(magic_slots, list):
        game.magic_hotbar_slots = [(game.canonical_spell_name(v) if v else None) for v in (magic_slots + [None] * 10)[:10]]
    active = data.get("active_hotbar", "item")
    game.active_hotbar = "magic" if active == "magic" else "item"
    # Loading an existing save should not auto-open startup NPC dialog.
    game.ui_mode = None
    game.dialog_data = None
    game.dialog_node = None
    game.active_npc = None
    game.teleport_team_to_player()
    game.ensure_monst3r_entity()
    game.ensure_wisadel_entity()
    game.recalculate_stats()
    game.last_saved = True
    game.last_save_slot = slot
    return True


def load_latest_save(game):
    for slot in range(3, 0, -1):
        if game.load_save(slot):
            return True
    return False


def open_leave_confirm(game):
    game.ui_mode = "leave_confirm"
    game.leave_selected = 0


def handle_leave_confirm(game):
    # 0: starter menu, 1: leave game, 2: go back
    if game.leave_selected == 0:
        game.request_main_menu = True
    elif game.leave_selected == 1:
        game.request_quit = True
    else:
        game.ui_mode = None
