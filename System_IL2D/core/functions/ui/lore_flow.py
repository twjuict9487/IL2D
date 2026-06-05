import os

from ..support.utils import GAME_DATA_DIR, load_json


def get_lore_archive_path():
    if GAME_DATA_DIR:
        return os.path.join(GAME_DATA_DIR, "lore_archive.json")
    return ""


def load_lore_archive():
    path = get_lore_archive_path()
    if not path or not os.path.isfile(path):
        return {}
    try:
        data = load_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _iter_entry_roots(archive):
    if not isinstance(archive, dict):
        return []
    roots = []
    for key in ("entries", "fragments"):
        block = archive.get(key, [])
        if isinstance(block, dict):
            block = [block]
        if isinstance(block, list):
            roots.extend([item for item in block if isinstance(item, dict)])
    intro = archive.get("intro")
    if isinstance(intro, dict):
        roots.append(intro)
    return roots


def iter_lore_entries(archive):
    out = []
    seen = set()
    for entry in _iter_entry_roots(archive):
        entry_id = str(entry.get("id", "") or "").strip()
        if not entry_id or entry_id in seen:
            continue
        seen.add(entry_id)
        out.append(entry)
    return out


def get_lore_entry_by_id(archive, entry_id):
    entry_id = str(entry_id or "").strip()
    if not entry_id:
        return None
    for entry in iter_lore_entries(archive):
        if str(entry.get("id", "") or "").strip() == entry_id:
            return entry
    return None


def get_lore_entry_title(entry, lang="zh"):
    if not isinstance(entry, dict):
        return ""
    if lang == "zh":
        for key in ("title_zh", "title", "name_zh", "name"):
            val = entry.get(key)
            if val:
                return str(val)
    for key in ("title_en", "title", "name_en", "name"):
        val = entry.get(key)
        if val:
            return str(val)
    return str(entry.get("id", "") or "")


def flatten_lore_page(page):
    if isinstance(page, list):
        return "\n".join(str(line) for line in page if line is not None)
    if page is None:
        return ""
    return str(page)


def chunk_lore_lines(lines, page_size):
    page_size = max(1, int(page_size or 1))
    out = []
    buf = []
    for line in lines or []:
        buf.append(str(line))
        if len(buf) >= page_size:
            out.append("\n".join(buf))
            buf = []
    if buf or not out:
        out.append("\n".join(buf))
    return out


def get_lore_entry_pages(archive, entry_id):
    entry = get_lore_entry_by_id(archive, entry_id)
    if not entry:
        return []
    pages = entry.get("pages")
    if isinstance(pages, list) and pages:
        return [flatten_lore_page(page) for page in pages]
    lines = entry.get("lines", [])
    if not isinstance(lines, list):
        lines = []
    page_size = 6
    if isinstance(archive, dict):
        try:
            page_size = int(archive.get("page_size", page_size) or page_size)
        except Exception:
            page_size = 6
    return chunk_lore_lines(lines, page_size)


def build_lore_index(archive):
    items = []
    for entry in iter_lore_entries(archive):
        items.append(
            {
                "id": str(entry.get("id", "") or ""),
                "title": get_lore_entry_title(entry, "zh"),
                "category": str(entry.get("category", "archive") or "archive"),
                "order": int(entry.get("order", 0) or 0),
            }
        )
    items.sort(key=lambda row: (row.get("order", 0), row.get("category", ""), row.get("title", ""), row.get("id", "")))
    return items
