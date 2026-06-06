import re
from copy import deepcopy

from ..support.utils import load_json


_KILL_HINTS = ("擊殺", "消滅", "擊敗", "殲滅")
_MISSION_COMPLETE_HINTS = ("完成", "任務")
_KEY_INTERACT_HINTS = ("回收", "上傳", "標記", "保護", "提交", "帶回", "收集", "掃描", "交付", "回傳")
_RETURN_HINTS = ("報告", "撤離", "撤退", "離開")


def _clean_text(text):
    return str(text or "").strip().strip("。").strip()


def _slugify_text(text):
    cleaned = _clean_text(text)
    if not cleaned:
        return "mission"
    lowered = cleaned.lower()
    lowered = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered or "mission"


def _extract_int(text, default=1):
    m = re.search(r"(\d+)", str(text or ""))
    return int(m.group(1)) if m else int(default)


def _parse_count_and_name(text):
    cleaned = _clean_text(text)
    target = _extract_int(cleaned, 1)
    name = cleaned
    if "隻" in cleaned:
        name = cleaned.split("隻", 1)[-1].strip()
    elif "名" in cleaned:
        name = cleaned.split("名", 1)[-1].strip()
    elif "份" in cleaned:
        name = cleaned.split("份", 1)[-1].strip()
    elif "個" in cleaned:
        name = cleaned.split("個", 1)[-1].strip()
    return target, name


def _parse_objective_line(text):
    cleaned = _clean_text(text)
    if not cleaned:
        return None

    target = _extract_int(cleaned, 1)
    obj = {
        "text": cleaned,
        "target": target,
        "progress": 0,
        "done": False,
        "type": "key_interact",
    }

    if any(hint in cleaned for hint in _RETURN_HINTS) and "成功撤離" in cleaned:
        obj["type"] = "return"
        return obj

    if "向" in cleaned and "報告" in cleaned:
        obj["type"] = "return"
        return obj

    if any(hint in cleaned for hint in _MISSION_COMPLETE_HINTS) and "任務" in cleaned:
        obj["type"] = "mission_complete"
        obj["target"] = target
        obj["mode"] = "high_risk" if "高風險" in cleaned else "normal"
        return obj

    if any(hint in cleaned for hint in _KILL_HINTS):
        obj["type"] = "kill"
        obj["target"] = target
        obj["mob"] = None
        generic_tokens = ("敵對目標", "敵人", "敵對怪物", "敵方偵察單位", "敵方單位", "敵對單位")
        if any(tok in cleaned for tok in generic_tokens):
            obj["mode"] = "any"
        elif "隻" in cleaned:
            obj["mode"] = "specific"
            _, maybe_name = _parse_count_and_name(cleaned)
            if maybe_name and maybe_name != cleaned and maybe_name not in generic_tokens:
                obj["mob_hint"] = maybe_name
        else:
            obj["mode"] = "any"
        return obj

    if any(hint in cleaned for hint in _KEY_INTERACT_HINTS):
        obj["type"] = "key_interact"
        obj["target"] = target
        obj["target_id"] = None
        obj["required_key"] = None
        obj["set_flag"] = None
        obj["consume_key"] = False
        return obj

    if "撤離" in cleaned or "撤退" in cleaned or "離開" in cleaned:
        obj["type"] = "return"
        obj["target"] = target
        return obj

    if "完成" in cleaned and "次" in cleaned:
        obj["type"] = "mission_complete"
        obj["target"] = target
        return obj

    return obj


def _fill_key_interact_meta(mission, objective, index):
    if not isinstance(objective, dict) or objective.get("type") != "key_interact":
        return objective
    mission_id = str((mission or {}).get("id", "mission"))
    giver_id = str((mission or {}).get("giver_id", "giver"))
    title = _slugify_text((mission or {}).get("title", mission_id))
    body = _slugify_text(objective.get("text", "target"))
    text_source = str(objective.get("text", ""))
    target_kind = "terminal"
    if any(tok in text_source for tok in ("終端", "終端機", "系統", "節點")):
        target_kind = "terminal"
    elif any(tok in text_source for tok in ("資料", "記錄", "檔案", "碎片", "情報", "訊號", "回聲")):
        target_kind = "data"
    elif any(tok in text_source for tok in ("門", "門禁", "鎖", "權限", "存取", "封存")):
        target_kind = "access"
    elif any(tok in text_source for tok in ("NPC", "人物", "人員", "訊息")):
        target_kind = "npc"
    objective["target_id"] = f"{giver_id}:{title}:{body}:{index}"
    objective["required_key"] = f"{target_kind}_access_card::{mission_id}:{index}"
    objective["set_flag"] = f"checked_{target_kind}_{title}_{index}"
    objective["consume_key"] = bool(objective.get("consume_key", False))
    objective.setdefault("key_label", f"{target_kind}_access_card")
    return objective


def _parse_reward_line(text):
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    money_match = re.search(r"(\d+)\s*Robux", cleaned, re.IGNORECASE)
    if money_match:
        return {"type": "money", "amount": int(money_match.group(1)), "text": cleaned}
    if cleaned.startswith("解鎖：") or cleaned.lower().startswith("unlock:"):
        return {"type": "unlock", "name": cleaned.split("：", 1)[-1].split(":", 1)[-1].strip(), "text": cleaned}
    item_match = re.match(r"^(.*?)(?:\s*[×x]\s*(\d+))?$", cleaned)
    if item_match:
        name = item_match.group(1).strip()
        count = int(item_match.group(2) or 1)
        return {"type": "item", "name": name, "count": count, "text": cleaned}
    return {"type": "text", "text": cleaned}


def load_mission_book(path):
    raw = load_json(path)
    book = {
        "version": raw.get("version", 1),
        "source_file": raw.get("source_file", "temp_mission"),
        "giver_aliases": raw.get("giver_aliases", {}),
        "giver_display": raw.get("giver_display", {}),
        "missions": [],
        "missions_by_id": {},
        "missions_by_giver": {},
        "first_by_giver": {},
        "title_to_id": {},
    }
    for entry in raw.get("missions", []):
        if not isinstance(entry, dict):
            continue
        giver_id = str(entry.get("giver_id", "") or entry.get("giver_name", "")).strip()
        mission_id = str(entry.get("id", "")).strip()
        title = _clean_text(entry.get("title"))
        giver_name = _clean_text(entry.get("giver_name")) or giver_id
        if not mission_id:
            mission_id = f"{giver_id}_{int(entry.get('index', len(book['missions']) + 1))}"
        objectives = []
        for idx, line in enumerate(entry.get("objective_lines", []) or []):
            spec = _parse_objective_line(line)
            if spec:
                spec = _fill_key_interact_meta({"id": mission_id, "giver_id": giver_id, "title": title}, spec, idx)
                objectives.append(spec)
        rewards = []
        for line in entry.get("reward_lines", []) or []:
            spec = _parse_reward_line(line)
            if spec:
                rewards.append(spec)
        parsed = {
            "id": mission_id,
            "index": int(entry.get("index", len(book["missions"]) + 1)),
            "giver_id": giver_id,
            "giver_name": giver_name,
            "title": title,
            "description_lines": list(entry.get("description_lines", []) or []),
            "accept_lines": list(entry.get("accept_lines", []) or []),
            "objective_lines": list(entry.get("objective_lines", []) or []),
            "return_lines": list(entry.get("return_lines", []) or []),
            "reward_lines": list(entry.get("reward_lines", []) or []),
            "objectives": objectives,
            "rewards": rewards,
        }
        unlocks = []
        for reward in rewards:
            if reward.get("type") == "unlock":
                unlocks.append(reward.get("name", ""))
        parsed["unlocks"] = [u for u in unlocks if u]
        book["missions"].append(parsed)
        book["missions_by_id"][mission_id] = parsed
        book["title_to_id"][title] = mission_id
        book["missions_by_giver"].setdefault(giver_id, []).append(parsed)
    for giver_id, rows in book["missions_by_giver"].items():
        rows.sort(key=lambda r: int(r.get("index", 0)))
        if rows:
            book["first_by_giver"][giver_id] = rows[0]["id"]
    return book


def empty_mission_book():
    return {
        "version": 1,
        "source_file": "",
        "giver_aliases": {},
        "giver_display": {},
        "missions": [],
        "missions_by_id": {},
        "missions_by_giver": {},
        "first_by_giver": {},
        "title_to_id": {},
    }


def normalize_state(state, mission_book=None):
    mission_book = mission_book or empty_mission_book()
    src = state if isinstance(state, dict) else {}
    active = src.get("active", {})
    if isinstance(active, list):
        active = {str(row.get("id", f"legacy_{idx}")): row for idx, row in enumerate(active) if isinstance(row, dict)}
    elif not isinstance(active, dict):
        active = {}
    completed = src.get("completed", [])
    if not isinstance(completed, list):
        completed = []
    accepted = src.get("accepted", [])
    if not isinstance(accepted, list):
        accepted = []
    unlocked = src.get("unlocked", [])
    if not isinstance(unlocked, list):
        unlocked = []
    flags = src.get("flags", {})
    if not isinstance(flags, dict):
        flags = {}
    key_items = src.get("key_items", {})
    if not isinstance(key_items, dict):
        key_items = {}
    completed_data = src.get("completed_data", {})
    if not isinstance(completed_data, dict):
        completed_data = {}
    tracked = src.get("tracked", None)
    board_giver = src.get("board_giver", None)
    completed_count = int(src.get("completed_count", len(completed)))
    if not unlocked:
        for giver_id in mission_book.get("missions_by_giver", {}):
            first = mission_book.get("first_by_giver", {}).get(giver_id)
            if first and first not in unlocked:
                unlocked.append(first)
    clean_active = {}
    for mid, runtime in active.items():
        if not isinstance(runtime, dict):
            continue
        clean_active[str(mid)] = normalize_runtime(runtime, mission_book)
    return {
        "active": clean_active,
        "accepted": [str(v) for v in accepted if isinstance(v, str)],
        "completed": [str(v) for v in completed if isinstance(v, str)],
        "completed_data": {str(k): normalize_runtime(v, mission_book) for k, v in completed_data.items() if isinstance(v, dict)},
        "unlocked": [str(v) for v in unlocked if isinstance(v, str)],
        "flags": flags,
        "key_items": key_items,
        "tracked": str(tracked) if tracked else None,
        "board_giver": str(board_giver) if board_giver else None,
        "completed_count": completed_count,
    }


def normalize_runtime(runtime, mission_book=None):
    mission_book = mission_book or empty_mission_book()
    src = runtime if isinstance(runtime, dict) else {}
    mission_id = str(src.get("id", "") or src.get("mission_id", "")).strip()
    base = deepcopy(mission_book.get("missions_by_id", {}).get(mission_id, {}))
    if not base:
        base = {}
    out = {
        "id": mission_id,
        "giver_id": str(src.get("giver_id", base.get("giver_id", "")) or base.get("giver_id", "")),
        "giver_name": str(src.get("giver_name", base.get("giver_name", "")) or base.get("giver_name", "")),
        "title": str(src.get("title", base.get("title", mission_id))),
        "description_lines": list(src.get("description_lines", base.get("description_lines", [])) or []),
        "accept_lines": list(src.get("accept_lines", base.get("accept_lines", [])) or []),
        "objective_lines": list(src.get("objective_lines", base.get("objective_lines", [])) or []),
        "return_lines": list(src.get("return_lines", base.get("return_lines", [])) or []),
        "reward_lines": list(src.get("reward_lines", base.get("reward_lines", [])) or []),
        "objectives": [],
        "rewards": list(src.get("rewards", base.get("rewards", [])) or []),
        "unlocks": list(src.get("unlocks", base.get("unlocks", [])) or []),
        "status": str(src.get("status", "active")),
    }
    src_objectives = src.get("objectives", None)
    if isinstance(src_objectives, list) and src_objectives:
        for item in src_objectives:
            if isinstance(item, dict):
                obj = {
                    "type": item.get("type", "key_interact"),
                    "text": item.get("text", ""),
                    "target": int(item.get("target", 1) or 1),
                    "progress": int(item.get("progress", 0) or 0),
                    "done": bool(item.get("done", False)),
                }
                for key in ("mob", "mob_hint", "mode"):
                    if key in item:
                        obj[key] = item.get(key)
                for key in ("target_id", "required_key", "set_flag", "consume_key", "key_label"):
                    if key in item:
                        obj[key] = item.get(key)
                if obj.get("type") == "key_interact":
                    obj.setdefault("target_id", None)
                    obj.setdefault("required_key", None)
                    obj.setdefault("set_flag", None)
                    obj.setdefault("consume_key", False)
                out["objectives"].append(obj)
    if not out["objectives"]:
        for item in base.get("objectives", []):
            obj = dict(item)
            obj.setdefault("progress", 0)
            obj.setdefault("done", False)
            if obj.get("type") == "key_interact":
                obj.setdefault("target_id", None)
                obj.setdefault("required_key", None)
                obj.setdefault("set_flag", None)
                obj.setdefault("consume_key", False)
            out["objectives"].append(obj)
    return out


def build_runtime(mission_def):
    runtime = normalize_runtime({"id": mission_def.get("id")}, {"missions_by_id": {mission_def.get("id"): mission_def}})
    runtime["status"] = "active"
    runtime["objectives"] = [dict(obj) for obj in mission_def.get("objectives", [])]
    for obj in runtime["objectives"]:
        obj.setdefault("progress", 0)
        obj.setdefault("done", False)
    runtime["rewards"] = list(mission_def.get("rewards", []))
    runtime["unlocks"] = list(mission_def.get("unlocks", []))
    return runtime


def ensure_key_items_for_mission(game, mission_runtime):
    if not isinstance(mission_runtime, dict):
        return []
    granted = []
    if not isinstance(getattr(game, "mission_key_items", None), dict):
        game.mission_key_items = {}
    for obj in mission_runtime.get("objectives", []) or []:
        if not isinstance(obj, dict):
            continue
        if obj.get("type") != "key_interact":
            continue
        key_name = str(obj.get("required_key") or "").strip()
        if not key_name:
            continue
        if int(game.mission_key_items.get(key_name, 0)) <= 0:
            game.mission_key_items[key_name] = 1
            granted.append(key_name)
    if granted:
        state, _ = _get_state(game)
        state["key_items"] = dict(getattr(game, "mission_key_items", {}))
    return granted


def _get_state(game):
    book = getattr(game, "mission_book", None) or empty_mission_book()
    state = normalize_state(getattr(game, "mission_state", None), book)
    game.mission_state = state
    return state, book


def get_mission_def(game, mission_id):
    _, book = _get_state(game)
    return book.get("missions_by_id", {}).get(str(mission_id))


def _is_unlocked_state(state, book, mission_id):
    mid = str(mission_id)
    if mid in state["completed"]:
        return True
    if mid in state["unlocked"]:
        return True
    mission = book.get("missions_by_id", {}).get(mid)
    if not mission:
        return False
    giver = mission.get("giver_id", "")
    rows = book.get("missions_by_giver", {}).get(giver, [])
    idx = next((i for i, row in enumerate(rows) if row.get("id") == mid), None)
    if idx is None:
        return False
    if idx == 0:
        return True
    prev = rows[idx - 1]["id"]
    return prev in state["completed"] or prev in state["unlocked"]


def get_giver_missions(game, giver_id):
    _, book = _get_state(game)
    return list(book.get("missions_by_giver", {}).get(str(giver_id), []))


def get_runtime(game, mission_id):
    state, _ = _get_state(game)
    mid = str(mission_id)
    if mid in state["active"]:
        return state["active"][mid]
    if mid in state["completed_data"]:
        return state["completed_data"][mid]
    return None


def is_unlocked(game, mission_id):
    state, book = _get_state(game)
    return _is_unlocked_state(state, book, mission_id)


def get_status(game, mission_id):
    state, _ = _get_state(game)
    mid = str(mission_id)
    if mid in state["completed"]:
        return "completed"
    runtime = state["active"].get(mid)
    if runtime:
        if is_ready_to_turn_in(runtime):
            return "ready"
        return "active"
    if _is_unlocked_state(state, getattr(game, "mission_book", empty_mission_book()), mid):
        return "available"
    return "locked"


def is_ready_to_turn_in(runtime):
    if not isinstance(runtime, dict):
        return False
    objectives = runtime.get("objectives", [])
    if not objectives:
        return True
    for obj in objectives:
        if obj.get("type") == "return":
            continue
        if not bool(obj.get("done", False)):
            return False
    return True


def get_board_rows(game, giver_id):
    giver_id = str(giver_id or "")
    state, book = _get_state(game)
    rows = []
    for mission in book.get("missions_by_giver", {}).get(giver_id, []):
        mid = mission.get("id")
        status = get_status(game, mid)
        runtime = state["active"].get(mid) or state["completed_data"].get(mid)
        if runtime:
            obj_text = get_objective_summary(runtime)
        else:
            obj_text = get_objective_summary({"objectives": mission.get("objectives", [])})
        rows.append({
            "id": mid,
            "title": mission.get("title", mid),
            "giver_id": giver_id,
            "giver_name": mission.get("giver_name", giver_id),
            "status": status,
            "objectives": obj_text,
            "briefing": list(mission.get("description_lines", [])),
            "accept_lines": list(mission.get("accept_lines", [])),
            "return_lines": list(mission.get("return_lines", [])),
            "reward_lines": list(mission.get("reward_lines", [])),
            "unlocks": list(mission.get("unlocks", [])),
            "runtime": runtime,
        })
    return rows


def get_objective_summary(runtime):
    out = []
    for obj in runtime.get("objectives", []) or []:
        if not isinstance(obj, dict):
            continue
        prefix = ""
        if obj.get("type") == "kill":
            prefix = "kill"
        elif obj.get("type") == "mission_complete":
            prefix = "mission"
        elif obj.get("type") == "key_interact":
            prefix = "key"
        elif obj.get("type") == "return":
            prefix = "return"
        text = obj.get("text", "")
        progress = int(obj.get("progress", 0) or 0)
        target = int(obj.get("target", 1) or 1)
        done = bool(obj.get("done", False))
        marker = "✓" if done else "•"
        out.append(f"{marker} {text} ({progress}/{target})")
    return out


def _bump_objectives(runtime, predicate, amount=1):
    changed = False
    for obj in runtime.get("objectives", []) or []:
        if not isinstance(obj, dict):
            continue
        if not predicate(obj):
            continue
        if obj.get("done"):
            continue
        target = max(1, int(obj.get("target", 1) or 1))
        progress = min(target, int(obj.get("progress", 0) or 0) + int(amount))
        obj["progress"] = progress
        if progress >= target:
            obj["done"] = True
        changed = True
    return changed


def update_on_enemy_death(game, enemy_id):
    state, _ = _get_state(game)
    enemy_id = str(enemy_id or "")
    changed = False
    for runtime in state["active"].values():
        changed |= _bump_objectives(
            runtime,
            lambda obj: obj.get("type") == "kill" and (
                obj.get("mode") != "specific" or not obj.get("mob_hint") or obj.get("mob_hint") == enemy_id
            ),
            amount=1,
        )
    return changed


def update_on_key_interact(game, key_id=None):
    return record_key_interaction(game, target_id=key_id, key_id=key_id)


def _consume_key_item(game, key_name, count=1):
    key_name = str(key_name or "").strip()
    if not key_name:
        return False
    count = max(1, int(count or 1))
    if not isinstance(getattr(game, "mission_key_items", None), dict):
        game.mission_key_items = {}
    current = int(game.mission_key_items.get(key_name, 0))
    if current < count:
        inv = getattr(game, "inventory", {})
        if isinstance(inv, dict) and int(inv.get(key_name, 0)) >= count:
            inv[key_name] = int(inv.get(key_name, 0)) - count
            return True
        return False
    remaining = current - count
    if remaining > 0:
        game.mission_key_items[key_name] = remaining
    else:
        game.mission_key_items.pop(key_name, None)
    return True


def record_key_interaction(game, target_id=None, key_id=None, consume=False, flag=None):
    state, _ = _get_state(game)
    target_id = str(target_id or key_id or "").strip()
    key_id = str(key_id or target_id or "").strip()
    changed = False
    key_state_changed = False
    for runtime in state["active"].values():
        for obj in runtime.get("objectives", []) or []:
            if not isinstance(obj, dict) or obj.get("type") != "key_interact" or obj.get("done"):
                continue
            obj_target = str(obj.get("target_id") or "").strip()
            req_key = str(obj.get("required_key") or "").strip()
            if target_id and obj_target and obj_target != target_id:
                continue
            if req_key:
                if key_id and key_id != req_key and target_id != req_key:
                    continue
                if int(getattr(game, "mission_key_items", {}).get(req_key, 0)) <= 0 and int(getattr(game, "inventory", {}).get(req_key, 0)) <= 0:
                    continue
                if consume and not _consume_key_item(game, req_key, 1):
                    continue
                if consume:
                    key_state_changed = True
            obj["progress"] = max(int(obj.get("progress", 0) or 0), int(obj.get("target", 1) or 1))
            obj["done"] = True
            set_flag = str(flag or obj.get("set_flag") or "").strip()
            if set_flag:
                if not isinstance(getattr(game, "mission_flags", None), dict):
                    game.mission_flags = {}
                game.mission_flags[set_flag] = True
                state["flags"][set_flag] = True
            changed = True
    if changed or key_state_changed:
        state["key_items"] = dict(getattr(game, "mission_key_items", {}))
    return changed


def update_on_mission_complete(game):
    state, _ = _get_state(game)
    completed_total = int(state.get("completed_count", len(state.get("completed", []))))
    changed = False
    for runtime in state["active"].values():
        changed |= _bump_objectives(
            runtime,
            lambda obj: obj.get("type") == "mission_complete",
            amount=1,
        )
        for obj in runtime.get("objectives", []) or []:
            if obj.get("type") == "mission_complete" and obj.get("progress", 0) < obj.get("target", 1):
                obj["progress"] = min(int(obj.get("target", 1) or 1), completed_total)
                if obj["progress"] >= int(obj.get("target", 1) or 1):
                    obj["done"] = True
                changed = True
    return changed


def mark_return_objective(game, mission_id):
    state, _ = _get_state(game)
    runtime = state["active"].get(str(mission_id))
    if not runtime:
        return False
    changed = _bump_objectives(runtime, lambda obj: obj.get("type") == "return", amount=1)
    return changed


def accept_mission(game, mission_id):
    state, book = _get_state(game)
    mid = str(mission_id)
    if mid in state["completed"]:
        return False
    if mid in state["active"]:
        return False
    if not _is_unlocked_state(state, book, mid):
        return False
    mission = book.get("missions_by_id", {}).get(mid)
    if not mission:
        return False
    runtime = build_runtime(mission)
    runtime["status"] = "active"
    state["active"][mid] = runtime
    if mid not in state["accepted"]:
        state["accepted"].append(mid)
    if not state.get("tracked"):
        state["tracked"] = mid
    ensure_key_items_for_mission(game, runtime)
    return True


def _apply_reward_item(game, name, count=1):
    if not name:
        return
    count = max(1, int(count or 1))
    try:
        if hasattr(game, "canonical_item_name"):
            cname = game.canonical_item_name(name)
        else:
            cname = name
    except Exception:
        cname = name
    if hasattr(game, "item_defs") and isinstance(getattr(game, "item_defs"), dict) and cname in getattr(game, "item_defs", {}):
        game.inventory[cname] = game.inventory.get(cname, 0) + count
        return
    if not isinstance(getattr(game, "mission_key_items", None), dict):
        game.mission_key_items = {}
    game.mission_key_items[cname] = int(game.mission_key_items.get(cname, 0)) + count


def grant_rewards(game, mission_runtime):
    rewards = mission_runtime.get("rewards", []) or []
    for reward in rewards:
        if not isinstance(reward, dict):
            continue
        rtype = reward.get("type")
        if rtype == "money":
            game.money = int(getattr(game, "money", 0)) + int(reward.get("amount", 0) or 0)
        elif rtype == "item":
            _apply_reward_item(game, reward.get("name", ""), reward.get("count", 1))
        elif rtype == "unlock":
            unlock_name = reward.get("name", "")
            if unlock_name:
                if not isinstance(getattr(game, "mission_flags", None), dict):
                    game.mission_flags = {}
                game.mission_flags[f"unlock:{unlock_name}"] = True
    if hasattr(game, "push_message"):
        reward_lines = mission_runtime.get("reward_lines", [])
        if reward_lines:
            game.push_message_lines([f"Reward: {line}" for line in reward_lines[:3]])


def complete_mission(game, mission_id):
    state, book = _get_state(game)
    mid = str(mission_id)
    runtime = state["active"].get(mid)
    if not runtime:
        return False
    if not is_ready_to_turn_in(runtime):
        return False
    _bump_objectives(runtime, lambda obj: obj.get("type") == "return", amount=1)
    runtime["status"] = "completed"
    completed_snapshot = normalize_runtime(runtime, book)
    completed_snapshot["status"] = "completed"
    state["completed_data"][mid] = completed_snapshot
    if mid not in state["completed"]:
        state["completed"].append(mid)
    state["active"].pop(mid, None)
    if mid in state["accepted"]:
        state["accepted"].remove(mid)
    if hasattr(game, "tracked_mission") and game.tracked_mission == mid:
        game.tracked_mission = None
    for reward in runtime.get("rewards", []) or []:
        if reward.get("type") != "unlock":
            continue
        unlock_name = reward.get("name", "")
        if not unlock_name:
            continue
        next_id = book.get("title_to_id", {}).get(unlock_name)
        if next_id and next_id not in state["unlocked"]:
            state["unlocked"].append(next_id)
        elif unlock_name in book.get("missions_by_id", {}):
            if unlock_name not in state["unlocked"]:
                state["unlocked"].append(unlock_name)
    giver_id = runtime.get("giver_id", "")
    giver_rows = book.get("missions_by_giver", {}).get(giver_id, [])
    for idx, row in enumerate(giver_rows):
        if row.get("id") != mid:
            continue
        if idx + 1 < len(giver_rows):
            nxt = giver_rows[idx + 1].get("id")
            if nxt and nxt not in state["unlocked"]:
                state["unlocked"].append(nxt)
        break
    grant_rewards(game, runtime)
    return True


def get_summary(game, mission_id):
    runtime = get_runtime(game, mission_id)
    mission_def = get_mission_def(game, mission_id)
    if not runtime and not mission_def:
        return None
    base = runtime or mission_def or {}
    return {
        "id": base.get("id", str(mission_id)),
        "title": base.get("title", ""),
        "giver_id": base.get("giver_id", ""),
        "giver_name": base.get("giver_name", ""),
        "status": get_status(game, mission_id),
        "briefing": list(base.get("description_lines", [])),
        "objectives": get_objective_summary(runtime or base),
        "rewards": list(base.get("reward_lines", [])),
        "unlocks": list(base.get("unlocks", [])),
        "accept_lines": list(base.get("accept_lines", [])),
        "return_lines": list(base.get("return_lines", [])),
    }
