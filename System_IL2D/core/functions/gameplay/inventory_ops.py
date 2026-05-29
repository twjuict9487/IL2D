import time
import random
from ..support.i18n import tr
from ..support.utils import clamp

ITEM_CATEGORY_ORDER = ["item", "gift", "equipment", "special"]
ITEM_CATEGORY_TYPES = {
    "item": {"consumable"},
    "gift": {"gift"},
    "equipment": {"equipment"},
    "special": {"special", "magic_book"},
}


def _normalize_item_category(value):
    token = str(value or "item").lower()
    return token if token in ITEM_CATEGORY_ORDER else "item"


def get_item_categories(game):
    return list(ITEM_CATEGORY_ORDER)


def cycle_item_category(game, step):
    categories = get_item_categories(game)
    if not categories:
        game.item_category = "item"
        game.item_selected = 0
        return
    current = _normalize_item_category(getattr(game, "item_category", "item"))
    idx = categories.index(current)
    idx = (idx + int(step)) % len(categories)
    game.item_category = categories[idx]
    game.item_selected = 0


def open_equip(game):
    game.ui_mode = "equip"
    game.equip_root_selected = 0
    game.equip_focus = "tabs"
    game.equip_category_selected = max(0, game.get_equip_categories().index(game.equip_category)) if game.get_equip_categories() else 0


def open_equip_items(game):
    game.ui_mode = "equip"
    game.equip_focus = "items"
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
    game.push_message(tr(game.lang, "msg.equipped_item", name=game.display_item_name(name)))
    game.tutorial_notify("equipment_changed", item_name=name, slot=target_slot)


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
        game.tutorial_notify("equipment_changed", item_name="equip_best", slot="multi")
        game.push_message(tr(game.lang, "msg.equip_best_done"))
    else:
        game.push_message(tr(game.lang, "msg.equip_best_no_change"))


def get_item_list(game):
    category = _normalize_item_category(getattr(game, "item_category", "item"))
    allowed_types = ITEM_CATEGORY_TYPES.get(category, {"consumable"})
    items = []
    for name, count in game.inventory.items():
        if count <= 0:
            continue
        item_def = game.item_defs.get(name, {})
        item_type = item_def.get("type")
        if item_type not in allowed_types:
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
    elif name == "berry":
        game.player.hp = clamp(game.player.hp + 10, 0, game.player.max_hp)
    elif name == "retreat item":
        if game.map.name not in ("rogue", "rouge_options.json"):
            game.push_message(tr(game.lang, "msg.cannot_use_item"))
            return
        game.inventory[name] = max(0, game.inventory.get(name, 0) - 1)
        game.return_from_rogue()
        game.push_message(tr(game.lang, "msg.used_item", name=game.display_item_name(name)))
        game.ui_mode = None
        game.request_close_esc_menu = True
        return
    elif name == "rogue level skipper":
        game.open_level_skipper_ui()
        return
    elif name.startswith("magic_book_"):
        magic_id = name[len("magic_book_"):]
        if game.unlock_magic(magic_id):
            game.inventory[name] = max(0, game.inventory.get(name, 0) - 1)
            game.push_message(tr(game.lang, "msg.magic_unlocked", name=game.display_spell_name(magic_id)))
        else:
            game.push_message(tr(game.lang, "msg.magic_already_unlocked", name=game.display_spell_name(magic_id)))
        return
    else:
        game.push_message(tr(game.lang, "msg.cannot_use_item"))
        return
    game.inventory[name] = max(0, game.inventory.get(name, 0) - 1)
    game.push_message(tr(game.lang, "msg.used_item", name=game.display_item_name(name)))


def cast_spell(game):
    spells_pool = game.get_unlocked_spells() if hasattr(game, "get_unlocked_spells") else game.spells
    if not spells_pool:
        game.push_message(tr(game.lang, "msg.no_spells"))
        return
    spell = spells_pool[game.magic_selected % len(spells_pool)]
    name = spell.get("name", "spell")
    spell_label = game.display_spell_name(name)
    cost = int(spell.get("mp_cost", 0))
    cooldown_ticks = int(spell.get("cooldown_ticks", spell.get("cooldown", 10)))
    remain = int(game.spell_cd_ticks.get(name, 0))
    if remain > 0:
        game.push_message(tr(game.lang, "msg.spell_cooldown", name=spell_label, sec=remain))
        return
    if game.player.mp < cost:
        game.push_message(tr(game.lang, "msg.out_of_mp"))
        return
    # Casting consumes MP even when no target is hit.
    game.player.mp -= cost
    game.spell_cd_ticks[name] = max(0, cooldown_ticks)
    archetype = str(spell.get("archetype", "")).lower()
    effect_type = str(spell.get("effect_type", "")).lower()
    if archetype == "beneficial" or effect_type in ("heal", "beneficial"):
        _apply_beneficial_spell(game, spell, spell_label)
        return

    target_range = int(spell.get("range_manhattan", spell.get("range", 4)))
    target_ent = find_nearest_enemy_in_range(game, game.player, target_range)
    if target_ent is not None:
        target_tile = (target_ent.x, target_ent.y)
    else:
        target_tile = pick_random_tile_in_manhattan(game, game.player.x, game.player.y, target_range) or (game.player.x, game.player.y)

    _spawn_projectile_effect(game, spell, (game.player.x, game.player.y), target_tile)
    game.push_message(tr(game.lang, "msg.cast_spell", name=spell_label))


def update_spell_cooldowns_tick(game):
    if not isinstance(getattr(game, "spell_cd_ticks", None), dict):
        game.spell_cd_ticks = {}
    for name in list(game.spell_cd_ticks.keys()):
        left = int(game.spell_cd_ticks.get(name, 0))
        left -= 1
        if left <= 0:
            game.spell_cd_ticks.pop(name, None)
        else:
            game.spell_cd_ticks[name] = left


def find_nearest_enemy_in_range(game, caster, target_range):
    nearest = []
    best_dist = None
    for ent in game.entities:
        if ent.eid == "player":
            continue
        if getattr(ent, "immortal", False) or ent.hp <= 0:
            continue
        ent_def = game.get_entity_def(ent.eid)
        if ent_def.get("ai_type") != "hostile":
            continue
        dist = abs(caster.x - ent.x) + abs(caster.y - ent.y)  # Manhattan
        if dist > target_range:
            continue
        if best_dist is None or dist < best_dist:
            best_dist = dist
            nearest = [ent]
        elif dist == best_dist:
            nearest.append(ent)
    if not nearest:
        return None
    return random.choice(nearest)


def pick_random_tile_in_manhattan(game, cx, cy, target_range):
    cells = []
    for y in range(max(0, cy - target_range), min(game.map.h, cy + target_range + 1)):
        for x in range(max(0, cx - target_range), min(game.map.w, cx + target_range + 1)):
            dist = abs(cx - x) + abs(cy - y)
            if dist <= target_range:
                cells.append((x, y))
    if not cells:
        return None
    return random.choice(cells)


def _spawn_projectile_effect(game, spell, source_tile, target_tile):
    sx, sy = source_tile
    tx, ty = target_tile
    dist = abs(sx - tx) + abs(sy - ty)
    travel_sec = max(0.08, min(0.65, 0.06 * max(1, dist)))
    effect = {
        "kind": "projectile",
        "spell": dict(spell),
        "sx": float(sx),
        "sy": float(sy),
        "tx": float(tx),
        "ty": float(ty),
        "start": time.time(),
        "travel_sec": float(travel_sec),
    }
    if not isinstance(getattr(game, "active_spell_effects", None), list):
        game.active_spell_effects = []
    game.active_spell_effects.append(effect)


def update_spell_effects(game):
    now = time.time()
    effects = list(getattr(game, "active_spell_effects", []) or [])
    if not effects:
        return
    kept = []
    for ef in effects:
        kind = ef.get("kind")
        if kind == "projectile":
            st = float(ef.get("start", now))
            dur = max(0.01, float(ef.get("travel_sec", 0.2)))
            if now - st >= dur:
                _resolve_spell_impact(game, ef)
                impact = {
                    "kind": "impact",
                    "spell": ef.get("spell", {}),
                    "x": float(ef.get("tx", ef.get("sx", 0))),
                    "y": float(ef.get("ty", ef.get("sy", 0))),
                    "start": now,
                    "life_sec": float(ef.get("spell", {}).get("impact_life_sec", 0.35)),
                }
                kept.append(impact)
            else:
                kept.append(ef)
        elif kind == "impact":
            st = float(ef.get("start", now))
            life = max(0.01, float(ef.get("life_sec", 0.35)))
            if now - st < life:
                kept.append(ef)
    game.active_spell_effects = kept


def _resolve_spell_impact(game, projectile):
    spell = projectile.get("spell", {}) or {}
    cx = int(round(float(projectile.get("tx", 0))))
    cy = int(round(float(projectile.get("ty", 0))))
    base_damage = int(spell.get("base_damage", 8))
    magic_ratio = float(spell.get("magic_ratio", 1.0))
    aoe = int(spell.get("aoe_manhattan", spell.get("aoe_radius", 5)))
    victims = []
    for ent in game.entities:
        if ent.eid == "player" or ent.hp <= 0 or getattr(ent, "immortal", False):
            continue
        ent_def = game.get_entity_def(ent.eid)
        if ent_def.get("ai_type") != "hostile":
            continue
        if abs(ent.x - cx) + abs(ent.y - cy) <= aoe:
            victims.append(ent)
    total = 0
    for ent in victims:
        damage = compute_magic_damage(game.player, ent, base_damage, magic_ratio)
        ent.hp -= damage
        total += max(0, damage)
        if ent.hp <= 0:
            game.on_enemy_death(ent)
    if victims:
        game.state_cleanup()
    if total > 0:
        game.push_message(tr(game.lang, "msg.spell_aoe_hit", amount=total))


def _apply_beneficial_spell(game, spell, spell_label):
    heal_amount = int(spell.get("heal_amount", 25))
    targets = [game.player]
    members = set(getattr(game, "team_members", []) or [])
    for ent in game.entities:
        if ent.eid in members and ent.hp > 0 and getattr(ent, "ai_type", "") == "team":
            targets.append(ent)
    total_heal = 0
    for ent in targets:
        before = ent.hp
        ent.hp = clamp(ent.hp + heal_amount, 0, ent.max_hp)
        total_heal += max(0, ent.hp - before)
        if not isinstance(getattr(game, "active_spell_effects", None), list):
            game.active_spell_effects = []
        game.active_spell_effects.append({
            "kind": "impact",
            "spell": dict(spell),
            "x": float(ent.x),
            "y": float(ent.y),
            "start": time.time(),
            "life_sec": float(spell.get("beneficial_life_sec", 0.45)),
        })
    if total_heal <= 0:
        game.push_message(tr(game.lang, "msg.heal_full"))
    else:
        game.push_message(tr(game.lang, "msg.heal_gain", amount=total_heal))


def compute_magic_damage(caster, target, base_damage, magic_ratio):
    atk = float(getattr(caster, "magic_attack", getattr(caster, "attack", 0)))
    md = float(getattr(target, "magic_defense", 0))
    md = max(0.0, min(1.0, md))
    ma = float(int(base_damage) + int(atk * float(magic_ratio)))
    return int(ma * (1.0 - md))


def cast_spell_by_name(game, spell_name):
    spells_pool = game.get_unlocked_spells() if hasattr(game, "get_unlocked_spells") else game.spells
    if not spells_pool:
        game.push_message(tr(game.lang, "msg.no_spells"))
        return
    spell_name = game.canonical_spell_name(spell_name)
    idx = next((i for i, sp in enumerate(spells_pool) if sp.get("name") == spell_name), None)
    if idx is None:
        game.push_message(tr(game.lang, "msg.no_spells"))
        return
    game.magic_selected = idx
    cast_spell(game)


def recalculate_stats(game):
    attack_bonus = 0
    defence_bonus = 0
    magic_attack_bonus = 0
    magic_defense_bonus = 0
    for slot, name in game.equipment.items():
        if not name:
            continue
        item_def = game.item_defs.get(name, {})
        attack_bonus += item_def.get("attack", 0)
        defence_bonus += item_def.get("defence", 0)
        magic_attack_bonus += item_def.get("magic", 0)
        magic_attack_bonus += item_def.get("magic_attack", 0)
        magic_defense_bonus += item_def.get("magic_defense", 0)
    game.player.attack = game.player.base_attack + attack_bonus
    game.player.defence = game.player.base_defence + defence_bonus
    game.player.magic_attack = getattr(game.player, "base_magic_attack", game.player.attack) + magic_attack_bonus
    game.player.magic_defense = getattr(game.player, "base_magic_defense", 0) + magic_defense_bonus


def get_equipable_items(game):
    equipables = []
    for name, count in game.inventory.items():
        if count <= 0:
            continue
        item_def = game.item_defs.get(name, {})
        if item_def.get("type") == "equipment":
            equipables.append(name)
    return equipables
