from ..support.i18n import tr
from ..support.utils import clamp


def open_equip(game):
    game.ui_mode = "equip_root"
    game.equip_root_selected = 0


def open_equip_items(game):
    game.ui_mode = "equip"
    game.equip_selected = 0


def get_equip_categories(game):
    return list(game.equip_categories)


def equip_selected_item(game):
    equipables = game.get_equipable_items()
    if not equipables:
        return
    slot_key = "ring" if game.equip_category.startswith("ring") else game.equip_category
    filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
    if not filtered:
        game.push_message(tr(game.lang, "msg.no_items_category"))
        return
    name = filtered[game.equip_selected % len(filtered)]
    item_def = game.item_defs.get(name, {})
    slot = item_def.get("slot")
    if not slot:
        return
    equipped_count = sum(1 for v in game.equipment.values() if v == name)
    if game.inventory.get(name, 0) <= equipped_count:
        game.push_message(tr(game.lang, "msg.not_enough_items"))
        return
    if name == "dev's super powerful ring":
        target_slot = game.equip_category if game.equip_category.startswith("ring") else slot
        if any(v == name for v in game.equipment.values()) and game.equipment.get(target_slot) != name:
            game.handle_cheat_ring()
            return
    target_slot = game.equip_category if game.equip_category.startswith("ring") else slot
    game.equipment[target_slot] = name
    game.recalculate_stats()
    game.push_message(tr(game.lang, "msg.equipped_item", name=name))


def unequip_all(game):
    for slot in game.equipment.keys():
        game.equipment[slot] = None
    game.recalculate_stats()
    game.push_message(tr(game.lang, "msg.unequipped_all"))


def equip_best(game):
    equipables = game.get_equipable_items()
    if not equipables:
        game.push_message(tr(game.lang, "msg.no_items_category"))
        return
    slot_to_items = {}
    for name in equipables:
        idef = game.item_defs.get(name, {})
        slot_key = idef.get("slot")
        if not slot_key:
            continue
        slot_to_items.setdefault(slot_key, []).append(name)
    changed = False
    for slot in game.equipment.keys():
        base_slot = "ring" if slot.startswith("ring") else slot
        candidates = slot_to_items.get(base_slot, [])
        if not candidates:
            continue
        dev_candidates = [n for n in candidates if n.startswith("dev's super powerful")]
        pool = dev_candidates if dev_candidates else candidates
        best_name = max(pool, key=lambda n: game._item_power_score(game.item_defs.get(n, {})))
        if slot.startswith("ring") and best_name == "dev's super powerful ring":
            if any(v == best_name for k, v in game.equipment.items() if k != slot):
                continue
        if game.equipment.get(slot) != best_name:
            game.equipment[slot] = best_name
            changed = True
    dev_ring = "dev's super powerful ring"
    first_slot = None
    for slot in game.equipment.keys():
        if not slot.startswith("ring"):
            continue
        if game.equipment.get(slot) == dev_ring:
            if first_slot is None:
                first_slot = slot
            else:
                game.equipment[slot] = None
                changed = True
    game.recalculate_stats()
    if changed:
        game.push_message(tr(game.lang, "msg.equip_best_done"))
    else:
        game.push_message(tr(game.lang, "msg.equip_best_no_change"))


def get_item_list(game):
    items = []
    for name, count in game.inventory.items():
        if count <= 0:
            continue
        idef = game.item_defs.get(name, {})
        if idef.get("type") == "equipment":
            continue
        items.append(name)
    return items


def use_item(game):
    items = game.get_item_list()
    if not items:
        game.push_message(tr(game.lang, "msg.no_items"))
        return
    name = items[game.item_selected % len(items)]
    count = game.inventory.get(name, 0)
    if count <= 0:
        game.push_message(tr(game.lang, "msg.no_items"))
        return
    if name == "health potion (small)":
        game.player.hp = clamp(game.player.hp + 20, 0, game.player.max_hp)
    elif name == "health potion (medium)":
        game.player.hp = clamp(game.player.hp + 50, 0, game.player.max_hp)
    elif name == "magic potion (small)":
        game.player.mp = clamp(game.player.mp + 10, 0, game.player.max_mp)
    elif name == "magic potion (medium)":
        game.player.mp = clamp(game.player.mp + 25, 0, game.player.max_mp)
    elif name == "barry":
        game.player.hp = clamp(game.player.hp + 10, 0, game.player.max_hp)
    elif name == "retreat item":
        if game.map.name not in ("rogue", "rouge_options.json"):
            game.push_message(tr(game.lang, "msg.cannot_use_item"))
            return
        game.inventory[name] = max(0, game.inventory.get(name, 0) - 1)
        game.return_from_rogue()
        game.push_message(tr(game.lang, "msg.used_item", name=name))
        game.ui_mode = None
        game.request_close_esc_menu = True
        return
    elif name == "rouge level skipper":
        game.open_level_skipper_ui()
        return
    else:
        game.push_message(tr(game.lang, "msg.cannot_use_item"))
        return
    game.inventory[name] = max(0, game.inventory.get(name, 0) - 1)
    game.push_message(tr(game.lang, "msg.used_item", name=name))


def cast_spell(game):
    if not game.spells:
        game.push_message(tr(game.lang, "msg.no_spells"))
        return
    spell = game.spells[game.magic_selected % len(game.spells)]
    name = spell.get("name", "spell")
    cost = spell.get("mp_cost", 0)
    if game.player.mp < cost:
        game.push_message(tr(game.lang, "msg.not_enough_mp"))
        return
    game.player.mp -= cost
    if name == "heal":
        before = game.player.hp
        game.player.hp = clamp(game.player.hp + 25, 0, game.player.max_hp)
        healed = game.player.hp - before
        if healed <= 0:
            game.push_message(tr(game.lang, "msg.heal_full"))
        else:
            game.push_message(tr(game.lang, "msg.heal_gain", amount=healed))
    else:
        game.push_message(tr(game.lang, "msg.cast_spell", name=name))


def recalculate_stats(game):
    attack_bonus = 0
    defence_bonus = 0
    for slot, name in game.equipment.items():
        if not name:
            continue
        item_def = game.item_defs.get(name, {})
        attack_bonus += item_def.get("attack", 0)
        defence_bonus += item_def.get("defence", 0)
    game.player.attack = game.player.base_attack + attack_bonus
    game.player.defence = game.player.base_defence + defence_bonus


def get_equipable_items(game):
    equipables = []
    for name, count in game.inventory.items():
        if count <= 0:
            continue
        item_def = game.item_defs.get(name, {})
        if item_def.get("type") == "equipment":
            equipables.append(name)
    return equipables
