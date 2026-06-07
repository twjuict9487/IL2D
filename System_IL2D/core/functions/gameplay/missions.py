import re
from copy import deepcopy

from ..support.utils import MISSIONS_FILE, load_json


_KILL_HINTS = ("?捏", "瘨?", "??", "畾脫?")
_MISSION_COMPLETE_HINTS = ("摰?", "隞餃?")
_KEY_INTERACT_HINTS = ("?", "銝", "璅?", "靽風", "?漱", "撣嗅?", "?園?", "??", "鈭支?", "?")
_RETURN_HINTS = ("?勗?", "?日", "?日", "?ａ?")

_LEGACY_GIVER_ALIASES = {
    "kaltsit": "凱爾希",
    "凱爾希": "凱爾希",
    "ines": "伊內絲",
    "伊內絲": "伊內絲",
    "closure": "可露希爾",
    "可露希爾": "可露希爾",
    "priestess": "priestess",
    "Priestess": "priestess",
}



def _clean_text(text):
    return str(text or "").strip().strip('"').strip("'").strip()


_MISSION_GIVER_ALIASES = {
    "kaltsit": "凱爾希",
    "ines": "伊內絲",
    "closure": "可露希爾",
    "priestess": "priestess",
}


def _resolve_giver_key(book, giver_id):
    giver_id = _clean_text(giver_id)
    if not giver_id:
        return giver_id
    entries = []
    if isinstance(book, dict):
        entries = list(book.values())
    elif isinstance(book, list):
        entries = list(book)
    exact_keys = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key_name in ("giver_id", "provider", "provider_id", "giver", "giver_name"):
            raw = _clean_text(entry.get(key_name))
            if raw:
                exact_keys.add(raw)
        title = _clean_text(entry.get("id"))
        if title:
            exact_keys.add(title)
    if giver_id in exact_keys:
        return giver_id
    ordered_givers = []
    if isinstance(book, dict):
        ordered_givers = list((book.get("missions_by_giver", {}) or {}).keys())
    runtime_aliases = ("kaltsit", "ines", "closure", "priestess")
    lowered = giver_id.lower()
    if lowered in runtime_aliases and ordered_givers:
        alias_idx = runtime_aliases.index(lowered)
        if alias_idx < len(ordered_givers):
            return ordered_givers[alias_idx]
    alias = _MISSION_GIVER_ALIASES.get(giver_id.lower())
    if alias:
        return alias
    return giver_id


def _mission_entries(book):
    if isinstance(book, dict):
        if isinstance(book.get("missions"), list):
            return list(book.get("missions") or [])
        if isinstance(book.get("entries"), list):
            return list(book.get("entries") or [])
        return list(book.values())
    if isinstance(book, list):
        return list(book)
    return []


def _mission_id(entry):
    if not isinstance(entry, dict):
        return ""
    for key in ("id", "mission_id", "missionId", "name"):
        value = _clean_text(entry.get(key))
        if value:
            return value
    return ""


def _mission_provider(entry):
    if not isinstance(entry, dict):
        return ""
    for key in ("provider", "provider_id", "giver_id", "giver", "giver_name"):
        value = _clean_text(entry.get(key))
        if value:
            return value
    return ""


def _runtime_state_ids(game, *names):
    out = set()
    for name in names:
        value = getattr(game, name, None)
        if isinstance(value, dict):
            out.update(_clean_text(k) for k in value.keys() if _clean_text(k))
        elif isinstance(value, (set, list, tuple)):
            for item in value:
                if isinstance(item, dict):
                    mid = _mission_id(item)
                    if mid:
                        out.add(mid)
                else:
                    mid = _clean_text(item)
                    if mid:
                        out.add(mid)
    return out


def _mission_status(game, mission_id):
    mission_id = _clean_text(mission_id)
    if not mission_id:
        return "missing"
    active = _runtime_state_ids(game, "mission_state", "active_missions", "missions_active", "active_mission_ids")
    completed = _runtime_state_ids(game, "mission_completed", "missions_completed", "completed_missions", "mission_done")
    if mission_id in completed:
        return "completed"
    if mission_id in active:
        return "active"
    return "available"


def _mission_unlock_refs(entry):
    refs = []
    if not isinstance(entry, dict):
        return refs
    raw_unlocks = entry.get("unlocks")
    if isinstance(raw_unlocks, list):
        refs.extend(_clean_text(item) for item in raw_unlocks if _clean_text(item))
    elif isinstance(raw_unlocks, dict):
        for key in ("requires", "mission", "mission_id", "id"):
            value = _clean_text(raw_unlocks.get(key))
            if value:
                refs.append(value)
    for key in ("requires", "requires_completed", "prerequisite", "prerequisites", "unlocks_after"):
        raw = entry.get(key)
        if isinstance(raw, (list, tuple, set)):
            refs.extend(_clean_text(item) for item in raw if _clean_text(item))
        elif isinstance(raw, str):
            val = _clean_text(raw)
            if val:
                refs.append(val)
    return [r for r in refs if r]


def validate_missions(path=None, emit=True):
    import json

    path = path or MISSIONS_FILE
    report = {
        "file": path,
        "errors": [],
        "warnings": [],
        "count": 0,
        "duplicate_ids": [],
    }
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as exc:
        report["errors"].append(f"mission file load failed: {exc}")
        if emit:
            print(f"[missions] {report['errors'][-1]}")
        return report
    try:
        book = load_mission_book(path)
        entries = _mission_entries(book)
    except Exception:
        entries = _mission_entries(data)
    report["count"] = len(entries)
    seen = {}
    ids = []
    known_titles = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = _clean_text(entry.get("title") or entry.get("name"))
        if title:
            known_titles.add(title)
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            report["errors"].append(f"entry #{idx + 1} is not an object")
            continue
        mid = _mission_id(entry)
        if not mid:
            report["errors"].append(f"entry #{idx + 1} missing id")
            continue
        if mid in seen:
            report["duplicate_ids"].append(mid)
            report["errors"].append(f"duplicate mission id: {mid}")
        seen[mid] = entry
        ids.append(mid)
        provider = _mission_provider(entry)
        if not provider:
            report["warnings"].append(f"{mid}: missing provider")
        chain = _clean_text(entry.get("chain") or entry.get("giver_id") or entry.get("giver_name"))
        if not chain:
            report["warnings"].append(f"{mid}: missing chain")
        order = entry.get("order", entry.get("index"))
        try:
            order_val = int(order)
            if order_val <= 0:
                report["warnings"].append(f"{mid}: invalid order {order}")
        except Exception:
            report["warnings"].append(f"{mid}: invalid order {order}")
        required_aliases = {
            "name": ("name", "title"),
            "description": ("description", "description_lines"),
            "accept_dialogue": ("accept_dialogue", "accept_lines"),
            "objectives": ("objectives", "objective_lines"),
            "return_dialogue": ("return_dialogue", "return_lines"),
            "rewards": ("rewards", "reward_lines"),
            "unlocks": ("unlocks",),
        }
        for required_key, aliases in required_aliases.items():
            has_field = False
            for alias in aliases:
                if required_key == "unlocks":
                    if alias in entry:
                        has_field = True
                        break
                    continue
                value = entry.get(alias)
                if value not in (None, "", [], {}):
                    has_field = True
                    break
            if not has_field:
                report["warnings"].append(f"{mid}: missing field {required_key}")
        objectives = entry.get("objectives", entry.get("objective_lines"))
        if isinstance(objectives, list):
            if not objectives:
                report["warnings"].append(f"{mid}: empty objectives")
        elif isinstance(objectives, dict):
            if not objectives:
                report["warnings"].append(f"{mid}: empty objectives")
        elif objectives is None:
            report["warnings"].append(f"{mid}: no objectives/objective_lines")
        else:
            report["warnings"].append(f"{mid}: unsupported objectives shape {type(objectives).__name__}")
        allowed_objective_types = {"kill", "mission_complete", "key_interact", "return"}
        if isinstance(objectives, list):
            for obj in objectives:
                if not isinstance(obj, dict):
                    report["warnings"].append(f"{mid}: malformed objective entry")
                    continue
                obj_type = _clean_text(obj.get("type") or "key_interact")
                if obj_type not in allowed_objective_types:
                    report["warnings"].append(f"{mid}: unsupported objective type {obj_type}")
                if obj_type == "key_interact":
                    if not _clean_text(obj.get("required_key")):
                        report["warnings"].append(f"{mid}: key_interact objective missing required_key")
                    if not _clean_text(obj.get("target_id")):
                        report["warnings"].append(f"{mid}: key_interact objective missing target_id")
        rewards = entry.get("rewards", entry.get("reward_lines"))
        if rewards in (None, "", [], {}):
            report["warnings"].append(f"{mid}: no rewards/reward_lines")
        elif isinstance(rewards, list):
            allowed_reward_types = {"money", "item", "unlock", "text"}
            for reward in rewards:
                if not isinstance(reward, dict):
                    report["warnings"].append(f"{mid}: malformed reward entry")
                    continue
                rtype = _clean_text(reward.get("type"))
                if rtype and rtype not in allowed_reward_types:
                    report["warnings"].append(f"{mid}: unsupported reward type {rtype}")
        unlock_refs = _mission_unlock_refs(entry)
        for ref in unlock_refs:
            if ref not in ids and ref not in seen and ref not in known_titles:
                report["warnings"].append(f"{mid}: unlock reference {ref} not found yet")
        objective_lines = entry.get("objective_lines") or []
        if isinstance(objective_lines, list):
            for line in objective_lines:
                if isinstance(line, str) and "unsupported" in line.lower():
                    report["warnings"].append(f"{mid}: suspicious objective line {line}")
    if emit:
        prefix = "[missions]"
        for item in report["errors"]:
            print(f"{prefix} ERROR: {item}")
        for item in report["warnings"]:
            print(f"{prefix} WARN: {item}")
        if not report["errors"] and not report["warnings"]:
            print(f"{prefix} mission data ok ({report['count']} entries)")
    return report


def can_accept_mission(game, mission_id, giver_id=None):
    mission_id = _clean_text(mission_id)
    if not mission_id:
        return False, "mission.missing_id", None
    book = getattr(game, "mission_book", None)
    entry = None
    if isinstance(book, dict):
        for candidate in _mission_entries(book):
            if _mission_id(candidate) == mission_id:
                entry = candidate
                break
    elif isinstance(book, list):
        for candidate in book:
            if _mission_id(candidate) == mission_id:
                entry = candidate
                break
    if entry is None:
        return False, "mission.not_found", None
    provider = _mission_provider(entry)
    if giver_id:
        resolved = _resolve_giver_key(book, giver_id)
        if provider and provider != resolved and _clean_text(entry.get("giver_name")) != _clean_text(giver_id):
            return False, "mission.provider_mismatch", entry
    status = _mission_status(game, mission_id)
    if status == "active":
        return False, "mission.already_active", entry
    if status == "completed":
        return False, "mission.already_completed", entry
    if not _is_unlocked_state(normalize_state(getattr(game, "mission_state", None), book), book, mission_id):
        rows = list(book.get("missions_by_giver", {}).get(provider, [])) if isinstance(book, dict) else []
        idx = next((i for i, row in enumerate(rows) if _mission_id(row) == mission_id), None)
        if idx is not None and idx > 0:
            prev = rows[idx - 1].get("id")
            if prev and prev not in _runtime_state_ids(game, "mission_completed", "missions_completed", "completed_missions", "mission_done", "mission_state"):
                return False, "mission.missing_prerequisite", entry
        return False, "mission.locked", entry
    prereq_refs = []
    for key in ("requires", "requires_completed", "prerequisite", "prerequisites", "unlock_requirements", "chain_requires"):
        raw = entry.get(key)
        if isinstance(raw, (list, tuple, set)):
            prereq_refs.extend(_clean_text(item) for item in raw if _clean_text(item))
        elif isinstance(raw, str):
            val = _clean_text(raw)
            if val:
                prereq_refs.append(val)
    completed = _runtime_state_ids(game, "mission_completed", "missions_completed", "completed_missions", "mission_done")
    for ref in prereq_refs:
        if ref and ref not in completed and ref != mission_id:
            return False, "mission.missing_prerequisite", entry
    return True, "", entry


def mission_acceptance_reason(game, mission_id, giver_id=None):
    ok, reason, _ = can_accept_mission(game, mission_id, giver_id=giver_id)
    return "" if ok else reason


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
    for sep in ("：", ":", "—", "-", "，", ",", "；", ";", "、"):
        if sep in cleaned:
            tail = cleaned.split(sep, 1)[-1].strip()
            if tail:
                name = tail
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

    lowered = cleaned.lower()
    if any(hint in cleaned for hint in _RETURN_HINTS) or any(tok in cleaned for tok in ("回報", "返回", "交任務", "報告")):
        obj["type"] = "return"
        return obj

    if any(tok in cleaned for tok in ("返回", "回報", "交任務", "報告")) and "任務" not in cleaned:
        obj["type"] = "return"
        return obj

    if any(hint in cleaned for hint in _MISSION_COMPLETE_HINTS) or any(tok in lowered for tok in ("mission complete", "complete mission")):
        obj["type"] = "mission_complete"
        obj["target"] = target
        obj["mode"] = "high_risk" if any(tok in cleaned for tok in ("高風險", "high risk", "高難度")) else "normal"
        return obj

    if any(hint in cleaned for hint in _KILL_HINTS) or any(tok in cleaned for tok in ("擊殺", "消滅", "殲滅", "清除", "擊倒", "擊敗", "kill")):
        obj["type"] = "kill"
        obj["target"] = target
        obj["mob"] = None
        generic_tokens = ("任意", "敵人", "敵對", "怪物", "hostile", "mob", "any")
        if any(tok in cleaned for tok in generic_tokens):
            obj["mode"] = "any"
        else:
            obj["mode"] = "specific"
            _, maybe_name = _parse_count_and_name(cleaned)
            if maybe_name and maybe_name != cleaned and maybe_name not in generic_tokens:
                obj["mob_hint"] = maybe_name
        return obj

    if any(hint in cleaned for hint in _KEY_INTERACT_HINTS) or any(tok in cleaned for tok in ("互動", "掃描", "上傳", "提交", "收集", "帶回", "回收", "交付", "保護")):
        obj["type"] = "key_interact"
        obj["target"] = target
        obj["target_id"] = None
        obj["required_key"] = None
        obj["set_flag"] = None
        obj["consume_key"] = False
        return obj

    if any(tok in cleaned for tok in ("回報", "返回", "回去", "交任務", "報告")):
        obj["type"] = "return"
        obj["target"] = target
        return obj

    if any(hint in cleaned for hint in _MISSION_COMPLETE_HINTS) or any(tok in lowered for tok in ("mission complete", "complete mission")):
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
    if any(tok in text_source for tok in ("終端", "terminal", "控制台", "掃描器")):
        target_kind = "terminal"
    elif any(tok in text_source for tok in ("資料", "data", "檔案", "文件", "記錄")):
        target_kind = "data"
    elif any(tok in text_source for tok in ("存取", "access", "門禁", "權限", "入口", "鑰匙")):
        target_kind = "access"
    elif any(tok in text_source for tok in ("NPC", "對話", "人物", "角色", "交談")):
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
    if cleaned.startswith("解鎖") or cleaned.lower().startswith("unlock:"):
        unlock_name = cleaned
        for sep in ("：", ":"):
            if sep in cleaned:
                unlock_name = cleaned.split(sep, 1)[-1].strip()
                break
        return {"type": "unlock", "name": unlock_name, "text": cleaned}
    item_match = re.match(r"^(.*?)(?:\s*[?x]\s*(\d+))?$", cleaned)
    if item_match:
        name = item_match.group(1).strip()
        count = int(item_match.group(2) or 1)
        return {"type": "item", "name": name, "count": count, "text": cleaned}
    return {"type": "text", "text": cleaned}


def _resolve_giver_key(book, giver_id):
    raw = str(giver_id or "").strip()
    if not raw:
        return raw
    missions_by_giver = (book or {}).get("missions_by_giver", {})
    if raw in missions_by_giver:
        return raw
    legacy = _LEGACY_GIVER_ALIASES.get(raw)
    if legacy and legacy in missions_by_giver:
        return legacy
    aliases = (book or {}).get("giver_aliases", {})
    alias = aliases.get(raw)
    if alias and alias in missions_by_giver:
        return alias
    display = (book or {}).get("giver_display", {})
    display_name = display.get(raw)
    if display_name and display_name in missions_by_giver:
        return display_name
    for key, value in display.items():
        if raw == value and value in missions_by_giver:
            return value
        if raw == key and value in missions_by_giver:
            return value
    lowered = raw.lower()
    for key in missions_by_giver:
        if str(key).strip().lower() == lowered:
            return key
    return raw


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
            "chain": _clean_text(entry.get("chain") or giver_id),
            "order": int(entry.get("order", entry.get("index", len(book["missions"]) + 1)) or 0),
            "giver_id": giver_id,
            "giver_name": giver_name,
            "provider": giver_id,
            "name": title,
            "title": title,
            "description": list(entry.get("description_lines", []) or []),
            "accept_dialogue": list(entry.get("accept_lines", []) or []),
            "description_lines": list(entry.get("description_lines", []) or []),
            "accept_lines": list(entry.get("accept_lines", []) or []),
            "objective_texts": list(entry.get("objective_lines", []) or []),
            "objective_lines": list(entry.get("objective_lines", []) or []),
            "return_lines": list(entry.get("return_lines", []) or []),
            "return_dialogue": list(entry.get("return_lines", []) or []),
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
        "chain": str(src.get("chain", base.get("chain", src.get("giver_id", base.get("giver_id", ""))))),
        "order": int(src.get("order", base.get("order", src.get("index", base.get("index", 0)))) or 0),
        "giver_id": str(src.get("giver_id", base.get("giver_id", "")) or base.get("giver_id", "")),
        "giver_name": str(src.get("giver_name", base.get("giver_name", "")) or base.get("giver_name", "")),
        "provider": str(src.get("provider", base.get("provider", src.get("giver_id", base.get("giver_id", ""))))),
        "name": str(src.get("name", base.get("name", base.get("title", mission_id)))),
        "title": str(src.get("title", base.get("title", mission_id))),
        "description": list(src.get("description", base.get("description", base.get("description_lines", []))) or []),
        "accept_dialogue": list(src.get("accept_dialogue", base.get("accept_dialogue", base.get("accept_lines", []))) or []),
        "description_lines": list(src.get("description_lines", base.get("description_lines", [])) or []),
        "accept_lines": list(src.get("accept_lines", base.get("accept_lines", [])) or []),
        "objective_lines": list(src.get("objective_lines", base.get("objective_lines", [])) or []),
        "return_dialogue": list(src.get("return_dialogue", base.get("return_dialogue", base.get("return_lines", []))) or []),
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
    runtime["chain"] = str(mission_def.get("chain", mission_def.get("giver_id", "")))
    runtime["order"] = int(mission_def.get("order", mission_def.get("index", 0)) or 0)
    runtime["provider"] = str(mission_def.get("provider", mission_def.get("giver_id", "")))
    runtime["name"] = str(mission_def.get("name", mission_def.get("title", mission_def.get("id", ""))))
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
    return prev in state["completed"]


def get_giver_missions(game, giver_id):
    _, book = _get_state(game)
    resolved = _resolve_giver_key(book, giver_id)
    rows = list(book.get("missions_by_giver", {}).get(resolved, []))
    if rows:
        return rows
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
    state, book = _get_state(game)
    giver_id = _resolve_giver_key(book, giver_id)
    rows = []
    for mission in book.get("missions_by_giver", {}).get(giver_id, []):
        mid = mission.get("id")
        status = get_status(game, mid)
        runtime = state["active"].get(mid) or state["completed_data"].get(mid)
        if runtime:
            obj_text = get_objective_summary(runtime)
        else:
            obj_text = get_objective_summary({"objectives": mission.get("objectives", [])})
        title = _display_name(mission, fallback=mid or giver_id)
        rows.append({
            "id": mid,
            "chain": mission.get("chain", giver_id),
            "order": mission.get("order", mission.get("index", 0)),
            "title": title,
            "name": _display_name(mission, fallback=title),
            "giver_id": giver_id,
            "giver_name": mission.get("giver_name", giver_id),
            "provider": mission.get("provider", giver_id),
            "status": status,
            "description": list(mission.get("description", mission.get("description_lines", []))),
            "accept_dialogue": list(mission.get("accept_dialogue", mission.get("accept_lines", []))),
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
        text = _clean_text(obj.get("text", ""))
        if not text:
            if obj.get("type") == "kill":
                text = "Kill objective"
            elif obj.get("type") == "mission_complete":
                text = "Mission objective"
            elif obj.get("type") == "key_interact":
                text = "Interaction objective"
            elif obj.get("type") == "return":
                text = "Return to giver"
            else:
                text = "Objective"
        progress = int(obj.get("progress", 0) or 0)
        target = int(obj.get("target", 1) or 1)
        done = bool(obj.get("done", False))
        marker = "[x]" if done else "[ ]"
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
    reward_lines = mission_runtime.get("reward_lines", [])
    if reward_lines:
        lines = [f"Reward: {line}" for line in reward_lines[:3]]
        if hasattr(game, "push_message_lines"):
            try:
                game.push_message_lines(lines)
                return
            except Exception:
                pass
        if hasattr(game, "push_message"):
            for line in lines:
                try:
                    game.push_message(line)
                except Exception:
                    pass


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
    giver_id = _resolve_giver_key(book, runtime.get("giver_id", ""))
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
    title = _display_name(base, fallback=str(mission_id))
    return {
        "id": base.get("id", str(mission_id)),
        "chain": base.get("chain", base.get("giver_id", "")),
        "order": base.get("order", base.get("index", 0)),
        "title": title,
        "name": _display_name(base, fallback=title),
        "giver_id": base.get("giver_id", ""),
        "giver_name": base.get("giver_name", ""),
        "provider": base.get("provider", base.get("giver_id", "")),
        "status": get_status(game, mission_id),
        "briefing": list(base.get("description", base.get("description_lines", []))),
        "description": list(base.get("description", base.get("description_lines", []))),
        "accept_dialogue": list(base.get("accept_dialogue", base.get("accept_lines", []))),
        "objectives": get_objective_summary(runtime or base),
        "rewards": list(base.get("reward_lines", [])),
        "unlocks": list(base.get("unlocks", [])),
        "accept_lines": list(base.get("accept_lines", [])),
        "return_lines": list(base.get("return_lines", [])),
    }


def _display_name(entry, fallback="Mission"):
    if not isinstance(entry, dict):
        return fallback
    for key in ("title", "name", "giver_name", "giver_id", "giver", "provider", "id"):
        value = _clean_text(entry.get(key))
        if value:
            return value
    return fallback
