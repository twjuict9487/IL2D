import os
import random
import time

from ..support.i18n import tr
from ..support.utils import DIALOG_DIR, load_json
from ..world.map import blocktypes, mobs_data, npc_data


def player_interact(game):
    if game.is_ui_blocking():
        return
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = game.player.x + dx, game.player.y + dy
        ent = game.entity_at(nx, ny)
        if ent and ent.eid != "player":
            ent_def = game.get_entity_def(ent.eid)
            if ent_def.get("ai_type") in ("friendly", "neutral"):
                if game.map.name == "rouge_options.json" and ent.eid == "dev":
                    game.open_rogue_rest_leave()
                elif ent.eid == "carmen":
                    game.open_dialog("carmen")
                else:
                    game.open_dialog(ent.eid)
            return
    bt = game.map.get_block(game.player.x, game.player.y)
    if bt and "on_step" in blocktypes[bt]:
        if blocktypes[bt]["on_step"] == "level_exit":
            game.start_blackout()
    game.try_harvest_bush()


def try_harvest_bush(game):
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = game.player.x + dx, game.player.y + dy
        bt = game.map.get_block(nx, ny)
        if bt == "07":
            count = random.randint(1, 3)
            game.inventory["barry"] = game.inventory.get("barry", 0) + count
            unit = "barry" if count == 1 else "barries"
            game.push_message(tr(game.lang, "msg.harvested_berry", count=count, unit=unit))
            game.map.grid[ny][nx] = "08"
            key = (game.map.name, nx, ny)
            game.bush_regrow[key] = time.time() + random.uniform(20.0, 30.0)
            return


def open_dialog(game, npc_id):
    if npc_id == "kaltsit":
        _open_kaltsit_mission_dialog(game)
        return
    dialog_path = os.path.join(DIALOG_DIR, f"{npc_id}.json")
    if not os.path.isfile(dialog_path):
        return
    game.dialog_data = load_json(dialog_path)
    game.dialog_node = game.dialog_data.get("start")
    game.dialog_selected = 0
    game.active_npc = npc_id
    game.ui_mode = "dialog"


def _open_kaltsit_mission_dialog(game):
    if (
        getattr(game, "kaltsit_completed", 0) >= 10
        and not getattr(game, "monst3r_unlocked", False)
    ):
        game.monst3r_unlocked = True
        game.kaltsit_reward_ready = False
        game.ensure_monst3r_entity()
        game.dialog_data = {
            "start": "node_1",
            "node_1": {
                "text": tr(game.lang, "msg.team_monst3r_joined"),
                "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}],
            },
        }
        game.dialog_node = "node_1"
        game.dialog_selected = 0
        game.active_npc = "kaltsit"
        game.ui_mode = "dialog"
        return

    if not getattr(game, "kaltsit_intro_done", False):
        game.kaltsit_intro_done = True
        game.dialog_data = {
            "start": "node_1",
            "node_1": {
                "text": tr(game.lang, "dialog.kaltsit_intro"),
                "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}],
            },
        }
        game.dialog_node = "node_1"
        game.dialog_selected = 0
        game.active_npc = "kaltsit"
        game.ui_mode = "dialog"
        return
    mission = getattr(game, "kaltsit_mission", None)
    if not mission or mission.get("done"):
        mission = _generate_kaltsit_mission(game)
        game.kaltsit_mission = mission
    text = _mission_text(game, mission)
    game.dialog_data = {
        "start": "node_1",
        "node_1": {
            "text": text,
            "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}]
        }
    }
    game.dialog_node = "node_1"
    game.dialog_selected = 0
    game.active_npc = "kaltsit"
    game.ui_mode = "dialog"


def _generate_kaltsit_mission(game):
    types = ["kill_specific", "kill_any", "reach_layer"]
    mtype = random.choice(types)
    if mtype == "kill_specific":
        mob_ids = [k for k, v in mobs_data.items() if isinstance(v, dict) and v.get("ai_type") == "hostile"]
        mob_id = random.choice(mob_ids) if mob_ids else "slime"
        target = random.randint(1, 10)
        return {"type": mtype, "mob": mob_id, "target": target, "progress": 0, "done": False}
    if mtype == "kill_any":
        target = random.randint(1, 10)
        return {"type": mtype, "target": target, "progress": 0, "done": False}
    target = random.randint(1, 10)
    target = min(target, 15)
    return {"type": "reach_layer", "target": target, "progress": 0, "done": False}


def _mission_text(game, mission):
    mtype = mission.get("type")
    if mtype == "kill_specific":
        return tr(
            game.lang,
            "mission.kill_specific",
            mob=mission.get("mob", "slime"),
            progress=mission.get("progress", 0),
            target=mission.get("target", 1),
        )
    if mtype == "kill_any":
        return tr(
            game.lang,
            "mission.kill_any",
            progress=mission.get("progress", 0),
            target=mission.get("target", 1),
        )
    return tr(
        game.lang,
        "mission.reach_layer",
        progress=mission.get("progress", 0),
        target=mission.get("target", 1),
    )


def open_rogue_rest_intro(game):
    game.dialog_data = {
        "start": "node_1",
        "node_1": {"text": "come talk to me when you're ready.", "responses": [{"text": "okay", "next": "end"}]},
    }
    game.dialog_node = "node_1"
    game.dialog_selected = 0
    game.active_npc = "dev"
    game.ui_mode = "dialog"


def open_rogue_rest_leave(game):
    game.dialog_data = {
        "start": "node_1",
        "node_1": {
            "text": "you have been gone through alot in this rouge, perhaps its time to save and leave?",
            "responses": [{"text": "okay", "next": "node_leave"}],
        },
        "node_leave": {
            "text": "are you going to leave?",
            "responses": [{"text": "yes", "next": "rogue_leave_yes"}, {"text": "no", "next": "rogue_leave_no"}],
        },
    }
    game.dialog_node = "node_1"
    game.dialog_selected = 0
    game.active_npc = "dev"
    game.ui_mode = "dialog"


def dialog_choose(game):
    if not game.dialog_data or not game.dialog_node:
        return
    node = game.dialog_data.get(game.dialog_node, {})
    responses = game.get_dialog_responses(node)
    if not responses:
        game.close_dialog()
        return
    choice = responses[game.dialog_selected % len(responses)]
    next_node = choice.get("next")
    if next_node == "end":
        game.close_dialog()
        return
    if next_node == "gift":
        game.gift_to_npc()
        game.close_dialog()
        return
    if next_node == "upgrade":
        game.dialog_node = "upgrade"
        game.dialog_selected = 0
        return
    if next_node == "carmen_upgrade_hp":
        game.carmen_roll("hp")
        game.close_dialog()
        return
    if next_node == "carmen_upgrade_mp":
        game.carmen_roll("mp")
        game.close_dialog()
        return
    if next_node == "carmen_talk":
        game.push_message(tr(game.lang, "msg.carmen_talk"))
        game.close_dialog()
        return
    if next_node == "rogue_leave_yes":
        game.close_dialog()
        game.return_from_rogue()
        return
    if next_node == "rogue_leave_no":
        game.close_dialog()
        game.rogue_difficulty += 0.2
        game.push_message(tr(game.lang, "msg.rogue_deeper_warn"))
        game.start_transition(game.enter_next_rogue_layer)
        return
    if next_node == "shop":
        game.open_shop("default")
        return
    if next_node == "dev_shop":
        game.open_shop("dev")
        return
    if next_node == "heal":
        game.npc_heal()
        game.close_dialog()
        return
    game.dialog_node = next_node
    game.dialog_selected = 0


def get_dialog_responses(game, node):
    responses = node.get("responses", [])
    if game.active_npc and game.active_npc in npc_data:
        if not any(r.get("next") == "gift" for r in responses):
            responses = responses + [{"text": "gift", "next": "gift"}]
    return responses


def close_dialog(game):
    game.dialog_data = None
    game.dialog_node = None
    game.dialog_selected = 0
    game.active_npc = None
    if game.ui_mode == "dialog":
        game.ui_mode = None


def gift_to_npc(game):
    gift_name = "Asus Tuf Gaming A15"
    if game.inventory.get(gift_name, 0) <= 0:
        game.push_message(tr(game.lang, "msg.not_enough_items"))
        return
    game.inventory[gift_name] = max(0, game.inventory.get(gift_name, 0) - 1)
    npc = npc_data.get(game.active_npc or "", {})
    add = npc.get("gift_relation", 0)
    game.relations[game.active_npc] = game.relations.get(game.active_npc, 0) + add
    game.push_message(tr(game.lang, "msg.gifted", name=game.active_npc, amount=add))


def open_carmen_upgrade(game):
    game.ui_mode = "carmen_upgrade"
    game.carmen_selected = 0


def carmen_roll(game, stat):
    cost = 100
    if game.money < cost:
        game.push_message(tr(game.lang, "msg.not_enough_robux"))
        return
    game.money -= cost
    delta = 10 if random.random() < 0.9 else -5
    if stat == "hp":
        game.player.max_hp = max(50, game.player.max_hp + delta)
        if game.player.hp > game.player.max_hp:
            game.player.hp = game.player.max_hp
        game.push_message(tr(game.lang, "msg.upgrade_hp", delta=delta))
    else:
        game.player.max_mp = max(10, game.player.max_mp + delta)
        if game.player.mp > game.player.max_mp:
            game.player.mp = game.player.max_mp
        game.push_message(tr(game.lang, "msg.upgrade_mp", delta=delta))


def maybe_startup_closure_greet(game):
    # class attribute lives on Game class instance type
    if game.__class__.closure_greeted_this_run:
        return
    if "closure" not in npc_data:
        return
    game.dialog_data = {
        "start": "node_1",
        "node_1": {"text": tr(game.lang, "dialog.closure_welcome"), "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}]},
    }
    game.dialog_node = "node_1"
    game.dialog_selected = 0
    game.active_npc = "closure"
    game.ui_mode = "dialog"
    game.__class__.closure_greeted_this_run = True


def open_shop(game, shop_mode="default"):
    game.shop_mode = shop_mode
    if shop_mode == "dev":
        game.shop_base_items = [
            i for i in game.shop_all_items if i.get("name", "").startswith("dev's super powerful") or i.get("name") == "rouge level skipper"
        ]
    else:
        game.shop_base_items = [i for i in game.shop_all_items if not i.get("name", "").startswith("dev's super powerful")]
    game.shop_category = "all"
    game.refresh_shop_items()
    game.ui_mode = "shop"
    game.shop_selected = 0


def _shop_item_category(game, name):
    item_def = game.item_defs.get(name, {})
    item_type = item_def.get("type", "")
    if item_type in ("consumable", "equipment", "gift"):
        return item_type
    return "other"


def get_shop_categories(_game):
    return ["all", "consumable", "equipment", "gift", "other"]


def refresh_shop_items(game):
    if game.shop_category == "all":
        game.shop_items = list(game.shop_base_items)
    else:
        game.shop_items = [item for item in game.shop_base_items if game._shop_item_category(item.get("name", "")) == game.shop_category]
    if not game.shop_items:
        game.shop_selected = 0
    else:
        game.shop_selected %= len(game.shop_items)


def cycle_shop_category(game, step):
    cats = game.get_shop_categories()
    idx = cats.index(game.shop_category) if game.shop_category in cats else 0
    idx = (idx + step) % len(cats)
    game.shop_category = cats[idx]
    game.refresh_shop_items()


def grant_dev_set(game):
    dev_items = [name for name in game.item_defs.keys() if name.startswith("dev's super powerful")]
    if not dev_items:
        return
    for name in dev_items:
        if name == "dev's super powerful ring":
            owned = game.inventory.get(name, 0)
            equipped = sum(1 for v in game.equipment.values() if v == name)
            if owned + equipped >= 1:
                continue
        game.inventory[name] = max(1, game.inventory.get(name, 0))
    game.recalculate_stats()
    game.push_message(tr(game.lang, "msg.dev_set_granted"))


def close_shop(game):
    if game.ui_mode == "shop":
        game.ui_mode = None


def npc_heal(game):
    npc = npc_data.get(game.active_npc, {})
    cost = npc.get("heal_cost", 50)
    if game.money < cost:
        game.push_message(tr(game.lang, "msg.not_enough_robux"))
        return
    game.money -= cost
    game.player.hp = game.player.max_hp
    game.player.mp = game.player.max_mp
    game.push_message(tr(game.lang, "msg.healed_full"))


def buy_selected_item(game):
    if not game.shop_items:
        game.push_message(tr(game.lang, "msg.no_items"))
        return
    item = game.shop_items[game.shop_selected % len(game.shop_items)]
    name = item["name"]
    price = item["price"]
    if game.money < price:
        game.push_message(tr(game.lang, "msg.not_enough_robux"))
        return
    if name == "dev's super powerful ring":
        owned = game.inventory.get(name, 0)
        equipped = sum(1 for v in game.equipment.values() if v == name)
        if owned + equipped >= 1:
            game.push_message(tr(game.lang, "msg.only_one"))
            return
    game.money -= price
    game.inventory[name] = game.inventory.get(name, 0) + 1
    game.push_message(tr(game.lang, "msg.bought_item", name=name, price=price))
