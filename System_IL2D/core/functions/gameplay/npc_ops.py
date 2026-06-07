import os
import random
import time

from ..support.i18n import tr
from ..support.utils import DIALOG_DIR, load_json, resolve_dialog_file
from ..world.map import blocktypes, mobs_data, npc_data

MISSION_GIVERS = {"kaltsit", "ines", "closure", "priestess"}
GIFT_ITEM_NAME = "Asus Tuf Gaming A15"

_DIALOG_DISPLAY_NAMES = {
    "dev": {"zh": "DEV", "en": "DEV"},
    "priestess": {"zh": "Priestess", "en": "Priestess"},
    "carmen": {"zh": "Carmen", "en": "Carmen"},
    "closure": {"zh": "可露希爾", "en": "Closure"},
    "kaltsit": {"zh": "凱爾希", "en": "Kal'tsit"},
    "ines": {"zh": "伊內絲", "en": "Ines"},
    "monst3r": {"zh": "Mon3tr", "en": "Mon3tr"},
    "wisadel": {"zh": "Wisadel", "en": "Wisadel"},
    "shu": {"zh": "黍", "en": "Shu"},
}


def _resolve_dialog_node(dialog_data, node_ref):
    if not isinstance(dialog_data, dict):
        return None
    if isinstance(node_ref, dict):
        return node_ref
    if not node_ref:
        return None
    key = str(node_ref)
    node = dialog_data.get(key)
    if isinstance(node, dict):
        return node
    for key_name in ("start", "root", "entry", "default", "dialog", "dialogue", "node"):
        node = dialog_data.get(key_name)
        if isinstance(node, dict):
            return node
        if isinstance(node, str):
            candidate = dialog_data.get(node)
            if isinstance(candidate, dict):
                return candidate
    for value in dialog_data.values():
        if isinstance(value, dict):
            return value
    return None


def _dialog_lines_from_node(node, lang=None):
    if not isinstance(node, dict):
        return ["..."]
    preferred = []
    if str(lang or "").lower() == "zh":
        preferred.extend(["text_zh", "text"])
    else:
        preferred.extend(["text", "text_zh"])
    preferred.extend(["body", "content", "message", "line", "description", "dialog"])
    for key in preferred:
        value = node.get(key)
        if value in (None, ""):
            continue
        lines = []
        if isinstance(value, list):
            for item in value:
                if item in (None, ""):
                    continue
                lines.extend(str(item).splitlines() or [str(item)])
        else:
            lines.extend(str(value).splitlines() or [str(value)])
        if lines:
            return lines
    if not lines and isinstance(node.get("lines"), list):
        lines = []
        for item in node.get("lines") or []:
            if item in (None, ""):
                continue
            lines.extend(str(item).splitlines() or [str(item)])
        if lines:
            return lines
    return ["..."]


def _dialog_options_from_node(node):
    if not isinstance(node, dict):
        return []
    for key in ("responses", "options", "choices", "replies", "answers"):
        value = node.get(key)
        if isinstance(value, list):
            return list(value)
    return []


def _dialog_pointer_options(node):
    if not isinstance(node, dict):
        return []
    pointer_keys = ("pointers", "links", "actions")
    out = []
    for key in pointer_keys:
        value = node.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict):
                out.append(dict(item))
            elif isinstance(item, str) and item.strip():
                out.append({"text": item.strip(), "next": item.strip()})
    return out


def _dialog_global_options(dialog_data):
    if not isinstance(dialog_data, dict):
        return []
    value = dialog_data.get("pointers")
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _append_unique_option(options, option):
    if not isinstance(option, dict):
        return
    next_key = option.get("next")
    text_key = option.get("text")
    for existing in options:
        if not isinstance(existing, dict):
            continue
        if next_key is not None and existing.get("next") == next_key:
            return
        if text_key is not None and existing.get("text") == text_key:
            return
    options.append(option)


def _merge_option_by_next(options, option):
    if not isinstance(option, dict):
        return
    next_key = option.get("next")
    if next_key is None:
        _append_unique_option(options, option)
        return
    for existing in options:
        if not isinstance(existing, dict):
            continue
        if existing.get("next") == next_key:
            for key, value in option.items():
                if key == "text":
                    continue
                if value is None:
                    continue
                existing[key] = value
            return
    options.append(option)


def _trace_dialog_event(game, npc_id, option, action_type, payload=None, handler=None, result=None):
    trace = {
        "npc_id": str(npc_id or ""),
        "option": str((option or {}).get("text") or (option or {}).get("text_zh") or ""),
        "action_type": str(action_type or ""),
        "payload": payload,
        "handler": str(handler or ""),
        "result": str(result or ""),
        "timestamp": time.time(),
    }
    if not isinstance(getattr(game, "dialog_trace", None), list):
        game.dialog_trace = []
    game.dialog_trace.append(trace)
    game.dialog_trace_last = trace
    if getattr(game, "debug_dialog_trace", False):
        print("[dialog-trace]", trace)
    return trace


def _option_is_available(option):
    if not isinstance(option, dict):
        return True, "", ""
    status = str(option.get("status", "") or "").strip().lower()
    available = True
    if option.get("available") is False:
        available = False
    if option.get("enabled") is False:
        available = False
    if option.get("locked") is True:
        available = False
    if status in {"locked", "unavailable", "disabled", "hidden"}:
        available = False
    reason = ""
    for key in ("reason", "reason_key", "message", "note", "hint", "locked_reason", "unavailable_reason"):
        value = option.get(key)
        if value not in (None, ""):
            reason = str(value).strip()
            break
    return available, reason, status


def _dialog_display_name(game, npc_id):
    npc_key = str(npc_id or "").strip()
    if not npc_key:
        return ""
    npc_key_l = npc_key.lower()
    lang = str(getattr(game, "lang", "") or "").lower()
    mapped = _DIALOG_DISPLAY_NAMES.get(npc_key_l)
    if mapped:
        return mapped.get("zh") if lang == "zh" else mapped.get("en") or mapped.get("zh") or npc_key
    npc = npc_data.get(npc_key_l) if isinstance(npc_data, dict) else {}
    if isinstance(npc, dict):
        for key in ("display_name_zh", "display_name", "name"):
            value = npc.get(key)
            if value not in (None, ""):
                return str(value)
    return npc_key


def _set_dialog_state(game, npc_id, dialog_data, node_ref, source="script"):
    game.dialog_data = dialog_data if isinstance(dialog_data, dict) else {}
    game.dialog_node = node_ref
    game.active_npc = npc_id
    game.dialog_source = source
    dialog_entry = _resolve_dialog_node(game.dialog_data, node_ref)
    game.dialog_text_lines = _dialog_lines_from_node(dialog_entry, getattr(game, "lang", None))
    game.dialog_lines = list(game.dialog_text_lines)
    dialog_options = []
    if hasattr(game, "get_dialog_responses") and callable(getattr(game, "get_dialog_responses", None)):
        try:
            dialog_options = list(game.get_dialog_responses(dialog_entry) or [])
        except Exception:
            dialog_options = []
    for pointer in _dialog_global_options(game.dialog_data):
        _append_unique_option(dialog_options, pointer)
    if not dialog_options:
        dialog_options = _dialog_options_from_node(dialog_entry)
        for pointer in _dialog_pointer_options(dialog_entry):
            _append_unique_option(dialog_options, pointer)
    game.dialog_options = list(dialog_options)
    game.dialog_responses = list(dialog_options)
    game.dialog_choices = list(dialog_options)
    game.dialog_selected = 0
    game.dialog_scroll = 0
    game.dialog_speaker_name = _dialog_display_name(game, npc_id)
    game.dialog_npc_name = game.dialog_speaker_name
    game.dialog_title = game.dialog_speaker_name
    game.ui_mode = "dialog"


def player_interact(game):
    if game.is_ui_blocking():
        return
    candidates = []
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = game.player.x + dx, game.player.y + dy
        ent = game.entity_at(nx, ny)
        if ent and ent.eid != "player":
            ent_def = game.get_entity_def(ent.eid)
            if ent_def.get("ai_type") in ("friendly", "neutral"):
                candidates.append(ent.eid)
    if candidates:
        # keep order, unique
        unique = []
        seen = set()
        for eid in candidates:
            if eid not in seen:
                seen.add(eid)
                unique.append(eid)
        if len(unique) == 1:
            _open_interaction_for_npc(game, unique[0])
        else:
            game.interact_candidates = unique
            game.interact_selected = 0
            game.ui_mode = "interact_pick"
        return
    mission_target_hit = False
    # TODO: add explicit mission_targets entries to maps once placement is finalized.
    for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = game.player.x + dx, game.player.y + dy
        target = None
        if hasattr(game.map, "get_mission_target"):
            target = game.map.get_mission_target(nx, ny)
        if not target:
            continue
        mission_target_hit = True
        if hasattr(game, "record_mission_key_interact"):
            game.record_mission_key_interact(
                target_id=target.get("target_id") or target.get("id") or f"{game.map.name}:{nx}:{ny}",
                key_id=target.get("required_key"),
                consume=bool(target.get("consume_key", False)),
                flag=target.get("set_flag"),
                target_kind=target.get("kind"),
            )
        msg = target.get("message")
        if msg and hasattr(game, "push_message"):
            game.push_message(str(msg))
        break
    bt = game.map.get_block(game.player.x, game.player.y)
    if bt and "on_step" in blocktypes[bt]:
        if blocktypes[bt]["on_step"] == "level_exit":
            game.start_blackout()
    if not mission_target_hit:
        game.try_harvest_bush()


def _open_interaction_for_npc(game, npc_id):
    game.tutorial_notify("npc_interact", npc_id=npc_id)
    if hasattr(game, "record_mission_key_interact"):
        game.record_mission_key_interact(target_id=f"npc:{npc_id}")
    if game.map.name == "rouge_options.json" and npc_id == "dev":
        game.open_rogue_rest_leave()
    elif npc_id == "carmen":
        game.open_dialog("carmen", source="interaction")
    else:
        game.open_dialog(npc_id, source="interaction")


def confirm_interact_choice(game):
    if not getattr(game, "interact_candidates", None):
        game.ui_mode = None
        return
    idx = game.interact_selected % len(game.interact_candidates)
    npc_id = game.interact_candidates[idx]
    game.interact_candidates = []
    game.interact_selected = 0
    _open_interaction_for_npc(game, npc_id)


def cancel_interact_choice(game):
    game.interact_candidates = []
    game.interact_selected = 0
    if game.ui_mode == "interact_pick":
        game.ui_mode = None


def try_harvest_bush(game):
    if not getattr(game, "skill_tree", {}).get("harvest_barries", False):
        game.push_message(tr(game.lang, "msg.need_skill_harvest"))
        return
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = game.player.x + dx, game.player.y + dy
        bt = game.map.get_block(nx, ny)
        if bt == "07":
            count = random.randint(1, 3)
            game.inventory["berry"] = game.inventory.get("berry", 0) + count
            if hasattr(game, "record_mission_item_gain"):
                try:
                    game.record_mission_item_gain("berry", count, source="bush")
                except Exception:
                    pass
            unit = "berry" if count == 1 else "berries"
            game.push_message(tr(game.lang, "msg.harvested_berry", count=count, unit=unit))
            game.map.grid[ny][nx] = "08"
            key = (game.map.name, nx, ny)
            game.bush_regrow[key] = time.time() + random.uniform(20.0, 30.0)
            return


def open_dialog(game, npc_id, source="script"):
    dialog_path = resolve_dialog_file(npc_id)
    if not os.path.isfile(dialog_path):
        if npc_id in MISSION_GIVERS and hasattr(game, "open_mission_board"):
            game.open_mission_board(npc_id, source=source)
            return
        fallback_text = tr(game.lang, "msg.dialog_unavailable")
        ok_text = tr(game.lang, "dialog.ok")
        dialog_data = {
            "start": "node_1",
            "node_1": {
                "text": fallback_text,
                "text_zh": fallback_text,
                "responses": [{"text": ok_text, "text_zh": ok_text, "next": "end"}],
            },
        }
        _set_dialog_state(game, npc_id, dialog_data, "node_1", source=source)
        return
    try:
        dialog_data = load_json(dialog_path)
    except Exception:
        fallback_text = tr(game.lang, "msg.dialog_unavailable")
        ok_text = tr(game.lang, "dialog.ok")
        dialog_data = {
            "start": "node_1",
            "node_1": {
                "text": fallback_text,
                "text_zh": fallback_text,
                "responses": [{"text": ok_text, "text_zh": ok_text, "next": "end"}],
            },
        }
    dialog_node = dialog_data.get("start")
    if not isinstance(dialog_node, dict) and isinstance(dialog_data, dict):
        for key in ("root", "entry", "default", "dialog", "dialogue"):
            maybe = dialog_data.get(key)
            if isinstance(maybe, dict):
                dialog_node = maybe
                break
        if not isinstance(dialog_node, dict):
            for key, value in dialog_data.items():
                if key.startswith("_"):
                    continue
                if isinstance(value, dict):
                    dialog_node = value
                    break
    _set_dialog_state(game, npc_id, dialog_data, dialog_node or "start", source=source)
    if source == "interaction" and hasattr(game, "record_mission_talk"):
        try:
            game.record_mission_talk(npc_id)
        except Exception:
            pass


def _open_kaltsit_mission_dialog(game, npc_id="kaltsit", source="script"):
    if (
        getattr(game, "kaltsit_completed", 0) >= 10
        and npc_id == "kaltsit"
        and not getattr(game, "monst3r_unlocked", False)
    ):
        game.monst3r_unlocked = True
        game.kaltsit_reward_ready = False
        game.ensure_monst3r_entity()
        _set_dialog_state(game, npc_id, {
            "start": "node_1",
            "node_1": {
                "text": tr(game.lang, "msg.team_monst3r_joined"),
                "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}],
            },
        }, "node_1", source=source)
        return
    if (
        getattr(game, "kaltsit_completed", 0) >= 10
        and npc_id == "ines"
        and not getattr(game, "wisadel_unlocked", False)
    ):
        game.wisadel_unlocked = True
        game.ines_reward_ready = False
        game.ensure_wisadel_entity()
        _set_dialog_state(game, npc_id, {
            "start": "node_1",
            "node_1": {
                "text": tr(game.lang, "msg.team_wisadel_joined"),
                "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}],
            },
        }, "node_1", source=source)
        return

    intro_flag = "kaltsit_intro_done" if npc_id == "kaltsit" else "ines_intro_done"
    if not getattr(game, intro_flag, False):
        setattr(game, intro_flag, True)
        _set_dialog_state(game, npc_id, {
            "start": "node_1",
            "node_1": {
                "text": tr(game.lang, "dialog.kaltsit_intro") if npc_id == "kaltsit" else tr(game.lang, "dialog.ines_intro"),
                "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}],
            },
        }, "node_1", source=source)
        return
    mission = game.get_mission_by_giver(npc_id) if hasattr(game, "get_mission_by_giver") else None
    if not mission or mission.get("done"):
        mission = _generate_kaltsit_mission(game, giver=npc_id)
        if hasattr(game, "add_active_mission"):
            game.add_active_mission(mission)
        else:
            game.kaltsit_mission = mission
    elif not mission.get("giver"):
        mission["giver"] = npc_id
    text = _mission_text(game, mission)
    _set_dialog_state(game, npc_id, {
        "start": "node_1",
        "node_1": {
            "text": text,
            "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}]
        }
    }, "node_1", source=source)


def open_legacy_mission_dialog(game, npc_id="kaltsit", source="script"):
    return _open_kaltsit_mission_dialog(game, npc_id=npc_id, source=source)


def _generate_kaltsit_mission(game, giver="kaltsit"):
    types = ["kill_specific", "kill_any", "reach_layer"]
    mtype = random.choice(types)
    if mtype == "kill_specific":
        mob_ids = [k for k, v in mobs_data.items() if isinstance(v, dict) and v.get("ai_type") == "hostile"]
        mob_id = random.choice(mob_ids) if mob_ids else "slime"
        target = random.randint(1, 10)
        return {"type": mtype, "mob": mob_id, "target": target, "progress": 0, "done": False, "giver": giver}
    if mtype == "kill_any":
        target = random.randint(1, 10)
        return {"type": mtype, "target": target, "progress": 0, "done": False, "giver": giver}
    target = random.randint(1, 10)
    target = min(target, 15)
    return {"type": "reach_layer", "target": target, "progress": 0, "done": False, "giver": giver}


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
    _set_dialog_state(game, "dev", {
        "start": "node_1",
        "node_1": {
            "text": tr(game.lang, "dialog.rogue_rest_intro"),
            "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}],
        },
    }, "node_1", source="script")


def open_rogue_rest_leave(game):
    _set_dialog_state(game, "dev", {
        "start": "node_1",
        "node_1": {
            "text": tr(game.lang, "dialog.rogue_rest_prompt"),
            "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "node_leave"}],
        },
        "node_leave": {
            "text": tr(game.lang, "dialog.rogue_rest_confirm"),
            "responses": [
                {"text": tr(game.lang, "dialog.yes"), "next": "rogue_leave_yes"},
                {"text": tr(game.lang, "dialog.no"), "next": "rogue_leave_no"},
            ],
        },
    }, "node_1", source="script")


def dialog_choose(game):
    if not game.dialog_data or not game.dialog_node:
        return
    node = _resolve_dialog_node(game.dialog_data, game.dialog_node)
    if not isinstance(node, dict):
        _trace_dialog_event(game, getattr(game, "active_npc", None), {}, "resolve_node", payload={"node": game.dialog_node}, handler="_resolve_dialog_node", result="missing_node")
        game.close_dialog()
        return
    responses = game.get_dialog_responses(node)
    if not responses:
        _trace_dialog_event(game, getattr(game, "active_npc", None), {}, "responses", payload={"node": game.dialog_node}, handler="get_dialog_responses", result="no_responses")
        game.close_dialog()
        return
    choice = responses[game.dialog_selected % len(responses)]
    if isinstance(choice, dict):
        available, reason, status = _option_is_available(choice)
        if not available:
            msg = reason or tr(game.lang, "msg.option_unavailable")
            if not msg or msg == "msg.option_unavailable":
                fallback = {
                    "locked": tr(game.lang, "mission.locked"),
                    "unavailable": tr(game.lang, "msg.dialog_unavailable"),
                    "disabled": tr(game.lang, "msg.dialog_unavailable"),
                    "hidden": tr(game.lang, "msg.dialog_unavailable"),
                }
                msg = fallback.get(status, "") or tr(game.lang, "msg.option_unavailable")
            if hasattr(game, "push_message"):
                game.push_message(msg)
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": choice.get("next"), "reason": reason, "status": status}, handler="availability_check", result="blocked")
            return
    next_node = choice.get("next")
    _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="dialog_choose", result="dispatch")
    if next_node == "end":
        game.close_dialog()
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="close_dialog", result="closed")
        return
    if next_node == "gift":
        game.gift_to_npc()
        game.close_dialog()
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="gift_to_npc", result="closed")
        return
    if next_node == "upgrade":
        game.dialog_node = "upgrade"
        game.dialog_selected = 0
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="dialog_node_transition", result="upgrade")
        return
    if next_node == "carmen_upgrade_hp":
        game.carmen_roll("hp")
        game.close_dialog()
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="carmen_roll", result="closed")
        return
    if next_node == "carmen_upgrade_mp":
        game.carmen_roll("mp")
        game.close_dialog()
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="carmen_roll", result="closed")
        return
    if next_node == "carmen_talk":
        game.push_message(tr(game.lang, "msg.carmen_talk"))
        game.close_dialog()
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="carmen_talk", result="closed")
        return
    if next_node == "rogue_leave_yes":
        game.close_dialog()
        game.return_from_rogue()
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="return_from_rogue", result="closed")
        return
    if next_node == "rogue_leave_no":
        game.close_dialog()
        game.environment_difficulty = max(0.0, float(getattr(game, "environment_difficulty", 0.0)) + 0.2)
        # Keep legacy field in sync for backward compatibility.
        game.rogue_difficulty = game.environment_difficulty
        game.push_message(tr(game.lang, "msg.rogue_deeper_warn"))
        game.start_transition(game.enter_next_rogue_layer)
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="start_transition", result="queued")
        return
    if next_node == "shop":
        game.open_shop("default")
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="open_shop", result="opened")
        return
    if next_node == "dev_shop":
        game.open_shop("dev")
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="open_shop", result="opened")
        return
    if next_node == "farm_shop":
        if hasattr(game, "farm_open_shop"):
            game.farm_open_shop()
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="farm_open_shop", result="opened")
        else:
            game.push_message("farm mod is not loaded")
            game.close_dialog()
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="farm_open_shop", result="missing_handler")
        return
    if next_node == "blackjack":
        if hasattr(game, "blackjack_start") and hasattr(game, "blackjack_state"):
            game.dialog_data = None
            game.dialog_node = None
            game.dialog_selected = 0
            game.active_npc = None
            game.dialog_source = None
            if int(getattr(game, "money", 0)) <= 0:
                game.push_message(tr(game.lang, "blackjack.no_money"))
                game.ui_mode = None
                _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="blackjack_start", result="no_money")
                return
            if int(game.money) <= 1000:
                bet = max(1, int(game.money))
                game.blackjack_session_bank = bet
                game.blackjack_ui_state = game.blackjack_start(bet)
                game.blackjack_ui_selected = 0
                game.blackjack_round_settled = False
                game.ui_mode = "blackjack"
                _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node, "bet": bet}, handler="blackjack_start", result="opened")
            else:
                game.blackjack_bet_input = ""
                game.blackjack_bet_error = ""
                game.ui_mode = "blackjack_bet"
                _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="blackjack_start", result="bet_prompt")
        else:
            game.push_message("blackjack mod is not loaded")
            game.close_dialog()
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="blackjack_start", result="missing_handler")
        return
    if next_node == "heal":
        game.npc_heal()
        game.close_dialog()
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="npc_heal", result="closed")
        return
    if next_node == "lore_archive":
        if getattr(game, "lore_archive", None):
            game.open_lore_archive()
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="open_lore_archive", result="opened")
        else:
            game.push_message(tr(game.lang, "msg.archive_unavailable"))
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="open_lore_archive", result="missing_handler")
        game.close_dialog()
        return
    if next_node == "mission_board":
        giver = getattr(game, "active_npc", None)
        game.close_dialog()
        if giver and hasattr(game, "open_mission_board"):
            game.open_mission_board(giver, source="interaction")
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node, "giver": giver}, handler="open_mission_board", result="opened")
        return
    if next_node in {"legacy_mission", "quest", "random_quest"}:
        giver = getattr(game, "active_npc", None)
        game.close_dialog()
        if giver in {"kaltsit", "ines"}:
            _open_kaltsit_mission_dialog(game, npc_id=giver, source="interaction")
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node, "giver": giver}, handler="legacy_mission", result="opened")
        else:
            if hasattr(game, "push_message"):
                game.push_message(tr(game.lang, "msg.mission_unavailable"))
            _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node, "giver": giver}, handler="legacy_mission", result="blocked")
        return
    resolved = _resolve_dialog_node(game.dialog_data, next_node)
    if resolved is None:
        if hasattr(game, "push_message"):
            game.push_message(tr(game.lang, "msg.dialog_unavailable"))
        _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="dialog_node_transition", result="missing_node")
        return
    _set_dialog_state(game, getattr(game, "active_npc", None), game.dialog_data, next_node, source=getattr(game, "dialog_source", "script"))
    _trace_dialog_event(game, getattr(game, "active_npc", None), choice, "option", payload={"next": next_node}, handler="dialog_node_transition", result="transitioned")


def get_dialog_responses(game, node):
    responses = node.get("responses", [])
    for pointer in _dialog_pointer_options(node):
        _append_unique_option(responses, pointer)
    global_options = _dialog_global_options(getattr(game, "dialog_data", None))
    global_nexts = {str(item.get("next")) for item in global_options if isinstance(item, dict) and item.get("next")}
    for pointer in global_options:
        _append_unique_option(responses, pointer)
    allow_maps = {"map_1.json", "map_2.json", "map_3.json"}
    gift_count = int((getattr(game, "inventory", {}) or {}).get(GIFT_ITEM_NAME, 0) or 0)
    can_gift = (
        game.active_npc
        and game.active_npc in npc_data
        and getattr(game, "map", None) is not None
        and game.map.name in allow_maps
        and getattr(game, "dialog_source", None) == "interaction"
    )
    if can_gift and "gift" not in global_nexts:
        gift_option = {
            "text": tr(game.lang, "dialog.gift"),
            "next": "gift",
        }
        if gift_count <= 0:
            gift_option["available"] = False
            gift_option["reason"] = tr(game.lang, "msg.not_enough_items")
        else:
            gift_option["available"] = True
            gift_option["reason"] = ""
        _merge_option_by_next(responses, gift_option)
    if getattr(game, "active_npc", None) in {"priestess", "kaltsit"} and getattr(game, "dialog_source", None) == "interaction" and "lore_archive" not in global_nexts:
        _append_unique_option(responses, {"text": tr(game.lang, "dialog.archive"), "next": "lore_archive"})
    if getattr(game, "active_npc", None) in MISSION_GIVERS and getattr(game, "dialog_source", None) == "interaction" and "mission_board" not in global_nexts:
        _append_unique_option(responses, {"text": tr(game.lang, "dialog.mission_board"), "next": "mission_board"})
    if getattr(game, "active_npc", None) in {"kaltsit", "ines"} and getattr(game, "dialog_source", None) == "interaction" and "legacy_mission" not in global_nexts:
        _append_unique_option(responses, {"text": tr(game.lang, "dialog.legacy_mission"), "next": "legacy_mission"})
    return responses


def close_dialog(game):
    game.dialog_data = None
    game.dialog_node = None
    game.dialog_text_lines = None
    game.dialog_lines = None
    game.dialog_options = None
    game.dialog_responses = None
    game.dialog_choices = None
    game.dialog_selected = 0
    game.dialog_scroll = 0
    game.active_npc = None
    game.dialog_speaker_name = None
    game.dialog_npc_name = None
    game.dialog_title = None
    game.dialog_source = None
    if game.ui_mode == "dialog":
        game.ui_mode = None


def close_mission_board(game):
    game.mission_board_giver = None
    game.mission_board_selected = 0
    game.mission_board_scroll = 0
    game.mission_detail_scroll = 0
    game.dialog_data = None
    game.dialog_node = None
    game.dialog_text_lines = None
    game.dialog_lines = None
    game.dialog_options = None
    game.dialog_responses = None
    game.dialog_choices = None
    game.dialog_selected = 0
    game.dialog_scroll = 0
    game.active_npc = None
    game.dialog_speaker_name = None
    game.dialog_npc_name = None
    game.dialog_title = None
    game.dialog_source = None
    if game.ui_mode == "mission_board":
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
    if getattr(getattr(game, "map", None), "name", None) != "map_1.json":
        return
    if "closure" not in npc_data:
        return
    _set_dialog_state(game, "closure", {
        "start": "node_1",
        "node_1": {"text": tr(game.lang, "dialog.closure_welcome"), "responses": [{"text": tr(game.lang, "dialog.ok"), "next": "end"}]},
    }, "node_1", source="script")
    game.__class__.closure_greeted_this_run = True


def open_shop(game, shop_mode="default"):
    game.shop_mode = shop_mode
    if shop_mode == "dev":
        game.shop_base_items = [
            i for i in game.shop_all_items if i.get("name", "").startswith("dev's super powerful") or i.get("name") == "rogue level skipper"
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


def grant_pre_dev_set(game):
    # 1) Max HP/MP directly
    game.player.max_hp = 10000
    game.player.max_mp = 10000
    game.player.hp = game.player.max_hp
    game.player.mp = game.player.max_mp

    # 2) Grant all known items x100
    for name in game.item_defs.keys():
        game.inventory[name] = game.inventory.get(name, 0) + 100

    # 3) Ensure dev set exists and auto-equip best
    game.grant_dev_set()
    game.equip_best()
    game.push_message(tr(game.lang, "msg.pre_dev_set_granted"))


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
    game.tutorial_notify("item_purchased", item_name=name, item_type=game.item_defs.get(name, {}).get("type"))
    item_label = game.display_item_name(name)
    key = f"item.{name}"
    tr_label = tr(game.lang, key)
    if tr_label != key:
        item_label = tr_label
    game.push_message(tr(game.lang, "msg.bought_item", name=item_label, price=price))
