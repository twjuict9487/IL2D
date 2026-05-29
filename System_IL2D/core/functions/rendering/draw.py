import os
import math
import time
import json
import pygame
try:
    from ..support.utils import clamp
    from ..world.map import mobs_data, npc_data, blocktypes, player_data
    from ..support.i18n import tr
    from ..support.asset_resolver import ensure_primed_from_file, resolve_image_candidates, resolve_atlas_candidates, resolve_folder_candidates
except ImportError:
    import sys
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from System_IL2D.core.functions.support.utils import clamp
    from System_IL2D.core.functions.world.map import mobs_data, npc_data, blocktypes, player_data
    from System_IL2D.core.functions.support.i18n import tr
    from System_IL2D.core.functions.support.asset_resolver import ensure_primed_from_file, resolve_image_candidates, resolve_atlas_candidates, resolve_folder_candidates

TILE_SIZE = 60
VIEWPORT = 12
FPS = 60
MAX_ANIM_FRAMES = 48

_IMAGE_CACHE = {}
_ANIM_CACHE = {}
_SPELL_ATLAS_CACHE = {}
_DIALOG_NPC_FALLBACK_IMAGE = {
    "dev": "noFilter_nobg.png",
    "priestess": "priestess_nobg.png",
    "carmen": "carmen_nobg.png",
    "closure": "Closure_nobg.png",
    "kaltsit": "头像_凯尔希.png",
    "ines": "头像_伊内丝.png",
    "monst3r": "头像_Mon3tr.png",
    "wisadel": "头像_维什戴尔.png",
    "shu": "头像_黍.png",
}


ensure_primed_from_file(__file__)
_SYSTEM_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _load_image(filename, size=None):
    if not filename:
        return None
    cache_key = (filename, size)
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]
    candidates = resolve_image_candidates(filename)
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            img = pygame.image.load(path).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, (int(size[0]), int(size[1])))
            _IMAGE_CACHE[cache_key] = img
            return img
        except Exception:
            continue
    _IMAGE_CACHE[cache_key] = None
    return None


def _load_anim_frames(folder_name, size=None):
    if not folder_name:
        return []
    cache_key = (folder_name, size)
    if cache_key in _ANIM_CACHE:
        return _ANIM_CACHE[cache_key]
    # Atlas-first: clips/atlas/<folder_name>_atlas.json (+ optional _pNN pages)
    atlas_frames = []
    atlas_meta_files = []
    for p in resolve_atlas_candidates(f"{folder_name}_atlas.json"):
        if os.path.isfile(p):
            atlas_meta_files.append(p)
            break
    page_idx = 2
    while True:
        page_found = False
        for p in resolve_atlas_candidates(f"{folder_name}_atlas_p{page_idx:02d}.json"):
            if os.path.isfile(p):
                atlas_meta_files.append(p)
                page_found = True
                break
        if not page_found:
            break
        page_idx += 1
    if atlas_meta_files:
        for meta_path in atlas_meta_files:
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                atlas_name = meta.get("atlas")
                frame_defs = meta.get("frames", [])
                if not atlas_name or not isinstance(frame_defs, list):
                    continue
                atlas_path = None
                for p in resolve_atlas_candidates(atlas_name):
                    if os.path.isfile(p):
                        atlas_path = p
                        break
                if not atlas_path:
                    for p in resolve_image_candidates(atlas_name):
                        if os.path.isfile(p):
                            atlas_path = p
                            break
                if not atlas_path:
                    continue
                atlas_img = pygame.image.load(atlas_path).convert_alpha()
                for fr in frame_defs:
                    try:
                        x = int(fr.get("x", 0))
                        y = int(fr.get("y", 0))
                        w = int(fr.get("w", 0))
                        h = int(fr.get("h", 0))
                        if w <= 0 or h <= 0:
                            continue
                        sub = atlas_img.subsurface(pygame.Rect(x, y, w, h)).copy()
                        if size:
                            sub = pygame.transform.smoothscale(sub, (int(size[0]), int(size[1])))
                        atlas_frames.append(sub)
                    except Exception:
                        continue
            except Exception:
                continue
        if len(atlas_frames) > MAX_ANIM_FRAMES:
            step = max(1, len(atlas_frames) // MAX_ANIM_FRAMES)
            atlas_frames = atlas_frames[::step][:MAX_ANIM_FRAMES]
        _ANIM_CACHE[cache_key] = atlas_frames
        return atlas_frames

    # Legacy fallback: clips/<folder_name>/frame_*.png
    folder = None
    for p in resolve_folder_candidates(folder_name):
        if os.path.isdir(p):
            folder = p
            break
    if folder is None:
        _ANIM_CACHE[cache_key] = []
        return []
    frames = []
    names = sorted([n for n in os.listdir(folder) if n.lower().endswith(".png")])
    if len(names) > MAX_ANIM_FRAMES:
        step = max(1, len(names) // MAX_ANIM_FRAMES)
        names = names[::step][:MAX_ANIM_FRAMES]
    for name in names:
        path = os.path.join(folder, name)
        try:
            img = pygame.image.load(path).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, (int(size[0]), int(size[1])))
            frames.append(img)
        except Exception:
            continue
    _ANIM_CACHE[cache_key] = frames
    return frames


def _get_anim_frame(folder_name, size=None, fps=12):
    frames = _load_anim_frames(folder_name, size)
    if not frames:
        return None
    tick = pygame.time.get_ticks() / 1000.0
    idx = int(tick * max(1, fps)) % len(frames)
    return frames[idx]


def _resolve_spell_image_path(image_name):
    if not image_name:
        return None
    cands = resolve_image_candidates(image_name)
    for p in cands:
        if os.path.isfile(p):
            return p
    p2 = os.path.join(_SYSTEM_ROOT, "clips", image_name.replace("/", os.sep).replace("\\", os.sep))
    if os.path.isfile(p2):
        return p2
    return None


def _load_spell_atlas_frames(atlas_cfg):
    if not isinstance(atlas_cfg, dict):
        return []
    image_name = atlas_cfg.get("image")
    fw = int(atlas_cfg.get("frame_w", 0) or 0)
    fh = int(atlas_cfg.get("frame_h", 0) or 0)
    max_frames = int(atlas_cfg.get("frames", 0) or 0)
    if not image_name or fw <= 0 or fh <= 0:
        return []
    key = (image_name, fw, fh, max_frames)
    if key in _SPELL_ATLAS_CACHE:
        return _SPELL_ATLAS_CACHE[key]
    path = _resolve_spell_image_path(image_name)
    if not path:
        _SPELL_ATLAS_CACHE[key] = []
        return []
    try:
        atlas = pygame.image.load(path).convert_alpha()
    except Exception:
        _SPELL_ATLAS_CACHE[key] = []
        return []
    aw, ah = atlas.get_width(), atlas.get_height()
    cols = max(1, aw // fw)
    rows = max(1, ah // fh)
    out = []
    for r in range(rows):
        for c in range(cols):
            if max_frames > 0 and len(out) >= max_frames:
                break
            x = c * fw
            y = r * fh
            if x + fw <= aw and y + fh <= ah:
                out.append(atlas.subsurface(pygame.Rect(x, y, fw, fh)).copy())
        if max_frames > 0 and len(out) >= max_frames:
            break
    _SPELL_ATLAS_CACHE[key] = out
    return out


def _draw_spell_effects(game, screen, cam_px, cam_py, tile_w, tile_h):
    effects = list(getattr(game, "active_spell_effects", []) or [])
    if not effects:
        return
    now = time.time()
    for ef in effects:
        spell = ef.get("spell", {}) or {}
        kind = ef.get("kind")
        if kind == "projectile":
            cfg = spell.get("atlas_projectile", {})
            frames = _load_spell_atlas_frames(cfg)
            if not frames:
                continue
            start = float(ef.get("start", now))
            dur = max(0.01, float(ef.get("travel_sec", 0.2)))
            t = max(0.0, min(1.0, (now - start) / dur))
            px = float(ef.get("sx", 0)) + (float(ef.get("tx", 0)) - float(ef.get("sx", 0))) * t
            py = float(ef.get("sy", 0)) + (float(ef.get("ty", 0)) - float(ef.get("sy", 0))) * t
            fps = max(1, int(cfg.get("fps", 16)))
            idx = int((now - start) * fps) % len(frames)
            fr = frames[idx]
            size = int(cfg.get("size", int(tile_w * 0.85)))
            if size > 0 and (fr.get_width() != size or fr.get_height() != size):
                fr = pygame.transform.smoothscale(fr, (size, size))
            dx = int(px * tile_w - cam_px + (tile_w - fr.get_width()) / 2)
            dy = int(py * tile_h - cam_py + (tile_h - fr.get_height()) / 2)
            screen.blit(fr, (dx, dy))
        elif kind == "impact":
            cfg = spell.get("atlas_impact", spell.get("atlas_beneficial", {}))
            frames = _load_spell_atlas_frames(cfg)
            if not frames:
                continue
            start = float(ef.get("start", now))
            life = max(0.01, float(ef.get("life_sec", 0.35)))
            p = max(0.0, min(1.0, (now - start) / life))
            idx = min(len(frames) - 1, int(p * (len(frames) - 1)))
            fr = frames[idx]
            size = int(cfg.get("size", int(tile_w * 1.05)))
            if size > 0 and (fr.get_width() != size or fr.get_height() != size):
                fr = pygame.transform.smoothscale(fr, (size, size))
            x = float(ef.get("x", 0))
            y = float(ef.get("y", 0))
            dx = int(x * tile_w - cam_px + (tile_w - fr.get_width()) / 2)
            dy = int(y * tile_h - cam_py + (tile_h - fr.get_height()) / 2)
            screen.blit(fr, (dx, dy))


def _get_entity_anim_state(game, ent):
    if ent.eid == "monst3r":
        return getattr(game, "monst3r_anim_state", "move")
    if ent.eid == "wisadel":
        return getattr(game, "wisadel_anim_state", "move")
    return "move"


def _get_entity_render_image(game, ent, ent_def, size):
    # Data-driven render mode:
    # static: use single image
    # animated: use folder frames (move/skill3)
    render_mode = ent_def.get("render_mode", "static")
    if render_mode == "animated":
        state = _get_entity_anim_state(game, ent)
        fps = int(ent_def.get("anim_fps", 12) or 12)
        state_key = f"anim_{state}"
        if state not in ("move", "idle") and ent_def.get(state_key):
            img = _get_anim_frame(ent_def.get(state_key), size=size, fps=fps)
            if img is not None:
                return img
        if state == "skill3" and ent_def.get("anim_skill3"):
            img = _get_anim_frame(ent_def.get("anim_skill3"), size=size, fps=fps)
            if img is not None:
                return img
        if ent_def.get("anim_move"):
            img = _get_anim_frame(ent_def.get("anim_move"), size=size, fps=fps)
            if img is not None:
                return img
    return _load_image(ent_def.get("image"), size)


def _get_dialog_portrait(game, npc_id, ent_def, size):
    npc_key = str(npc_id or "").strip()
    npc_key_l = npc_key.lower()
    if ent_def.get("render_mode") == "animated":
        fps = int(ent_def.get("anim_fps", 12) or 12)
        for anim_key in ("anim_move", "anim_skill3"):
            folder = ent_def.get(anim_key)
            if folder:
                img = _get_anim_frame(folder, size=size, fps=fps)
                if img is not None:
                    return img
    img = _load_image(ent_def.get("image"), size)
    if img is not None:
        return img
    fallback = _DIALOG_NPC_FALLBACK_IMAGE.get(npc_key) or _DIALOG_NPC_FALLBACK_IMAGE.get(npc_key_l)
    if fallback:
        img = _load_image(fallback, size)
        if img is not None:
            return img
    for ext in (".png", ".webp", ".jpg", ".jpeg"):
        img = _load_image(f"{npc_key}_nobg{ext}", size)
        if img is None and npc_key_l and npc_key_l != npc_key:
            img = _load_image(f"{npc_key_l}_nobg{ext}", size)
        if img is not None:
            return img
    for name in (npc_key, npc_key_l):
        if not name:
            continue
        img = _load_image(name, size)
        if img is not None:
            return img
    return None


def _flicker_color():
    t = pygame.time.get_ticks() / 500.0
    s = (math.sin(t) + 1.0) / 2.0
    intensity = 140 + int(115 * s)
    return (intensity, intensity, intensity)


def _tile_color_for_block(bt):
    base_bt = blocktypes.get(bt, {}).get("base")
    if base_bt == "01" or bt == "01":
        return (42, 88, 42)
    if bt == "02":
        return (60, 60, 60)
    if bt == "04":
        return (200, 160, 60)
    return (160, 160, 80)


def _compute_minimap_bg_color(game):
    counts = {}
    for row in getattr(game.map, "grid", []):
        for bt in row:
            counts[bt] = counts.get(bt, 0) + 1
    if not counts:
        return (30, 50, 30)
    top_block = max(counts.items(), key=lambda kv: kv[1])[0]
    base = _tile_color_for_block(top_block)
    return (
        min(255, int(base[0] * 0.9 + 12)),
        min(255, int(base[1] * 0.9 + 12)),
        min(255, int(base[2] * 0.9 + 12)),
    )


def _draw_star(screen, center_x, center_y, outer_r, fill_color, edge_color):
    inner_r = max(2, int(outer_r * 0.45))
    points = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        radius = outer_r if i % 2 == 0 else inner_r
        points.append((center_x + math.cos(ang) * radius, center_y + math.sin(ang) * radius))
    pygame.draw.polygon(screen, fill_color, points)
    pygame.draw.polygon(screen, edge_color, points, 1)


def _draw_minimap(game, screen, cam_px, cam_py, view_w_px, view_h_px):
    map_w = max(1, int(getattr(game.map, "w", 1)))
    map_h = max(1, int(getattr(game.map, "h", 1)))
    mini_w = max(120, screen.get_width() // 4)
    mini_h = max(120, screen.get_height() // 4)
    mini_x = 10
    mini_y = 10
    mini_rect = pygame.Rect(mini_x, mini_y, mini_w, mini_h)

    bg = pygame.Surface((mini_w, mini_h), pygame.SRCALPHA)
    bg.fill((*_compute_minimap_bg_color(game), 220))
    screen.blit(bg, (mini_x, mini_y))
    pygame.draw.rect(screen, (190, 210, 235), mini_rect, 2)

    scale_x = mini_w / map_w
    scale_y = mini_h / map_h

    for p in getattr(game.map, "portals", []) or []:
        px = p.get("x")
        py = p.get("y")
        if px is None or py is None:
            continue
        dot_x = mini_x + int((px + 0.5) * scale_x)
        dot_y = mini_y + int((py + 0.5) * scale_y)
        pygame.draw.circle(screen, (248, 222, 90), (dot_x, dot_y), max(2, int(min(scale_x, scale_y) * 0.35)))

    player_x = mini_x + int((game.player.x + 0.5) * scale_x)
    player_y = mini_y + int((game.player.y + 0.5) * scale_y)
    pygame.draw.circle(screen, (50, 120, 255), (player_x, player_y), max(3, int(min(scale_x, scale_y) * 0.45)))

    view_x = mini_x + int((cam_px / max(1, TILE_SIZE)) * scale_x)
    view_y = mini_y + int((cam_py / max(1, TILE_SIZE)) * scale_y)
    view_w = max(1, int((view_w_px / max(1, TILE_SIZE)) * scale_x))
    view_h = max(1, int((view_h_px / max(1, TILE_SIZE)) * scale_y))
    pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(view_x, view_y, view_w, view_h), 2)
    return mini_rect


def _get_font(size, bold=False):
    # Prefer explicit CJK font files on Windows to avoid "??" fallback text.
    for font_path in (
        r"C:\Windows\Fonts\msjh.ttc",  # Microsoft JhengHei
        r"C:\Windows\Fonts\msyh.ttc",  # Microsoft YaHei
        r"C:\Windows\Fonts\mingliu.ttc",
    ):
        if os.path.isfile(font_path):
            try:
                return pygame.font.Font(font_path, size)
            except Exception:
                pass
    for name in ("Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC", "Noto Sans CJK SC"):
        try:
            matched = pygame.font.match_font(name)
            if matched:
                return pygame.font.Font(matched, size)
        except Exception:
            pass
    return pygame.font.SysFont('consolas', size, bold=bold)


def _draw_text_outline(screen, font, text, color, outline_color, pos, thickness=1):
    x, y = pos
    # Keep outlines dark and thick enough for high-contrast readability.
    if (outline_color[0] + outline_color[1] + outline_color[2]) >= 540:
        outline_color = (8, 12, 20)
    eff_thickness = max(2, int(thickness))
    base = font.render(text, True, color)
    outline = font.render(text, True, outline_color)
    shadow = font.render(text, True, (0, 0, 0))
    # Soft drop shadow improves readability on busy panels.
    shadow.set_alpha(120)
    screen.blit(shadow, (x + 1, y + 2))
    for ox in range(-eff_thickness, eff_thickness + 1):
        for oy in range(-eff_thickness, eff_thickness + 1):
            if ox == 0 and oy == 0:
                continue
            screen.blit(outline, (x + ox, y + oy))
    screen.blit(base, (x, y))


def _draw_readability_row(screen, rect, selected=False):
    fill_alpha = 170 if selected else 120
    fill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    fill.fill((7, 14, 26, fill_alpha))
    screen.blit(fill, rect.topleft)
    border = _flicker_color() if selected else (120, 170, 205)
    width = 2 if selected else 1
    pygame.draw.rect(screen, border, rect, width, border_radius=4)


def _fit_text(font, text, max_w):
    if font.size(text)[0] <= max_w:
        return text
    ell = "..."
    s = text
    while s and font.size(s + ell)[0] > max_w:
        s = s[:-1]
    return (s + ell) if s else ell


def _tr_item_name(game, name):
    if hasattr(game, "display_item_name"):
        disp = game.display_item_name(name)
        if disp and disp != name:
            return disp
    key = f"item.{name}"
    label = tr(game.lang, key)
    return name if label == key else label


def _tr_spell_name(game, name):
    if hasattr(game, "display_spell_name"):
        disp = game.display_spell_name(name)
        if disp and disp != name:
            return disp
    key = f"spell.{name}"
    label = tr(game.lang, key)
    return name if label == key else label


def _tr_slot_name(game, slot):
    key = f"label.{slot}"
    label = tr(game.lang, key)
    return slot if label == key else label


def _tr_item_category(game, category):
    if category == "item":
        key = "item.cat.item"
    else:
        key = f"shop.cat.{category}"
    label = tr(game.lang, key)
    return category if label == key else label


def _is_left_menu_entered(game, label):
    mode = getattr(game, "ui_mode", None)
    if label == "item":
        return mode in ("item", "level_skipper")
    if label == "hotbar":
        return mode == "hotbar"
    if label == "equipments":
        return mode in ("equip_root", "equip", "equip_category")
    if label == "team":
        return mode in ("team", "team_equip_root", "team_equip", "team_equip_category")
    if label == "tutorial":
        return False
    if label == "objective":
        return mode == "objective"
    if label == "map":
        return mode == "map"
    if label == "skill_tree":
        return mode == "skill_tree"
    if label == "save":
        return mode == "save"
    if label == "leave":
        return mode == "leave_confirm"
    return False


def draw_main_menu(screen, selected, lang="zh"):
    # tech grey background
    pygame.draw.rect(screen, (70, 78, 86), screen.get_rect())
    font = _get_font(48, bold=True)
    font2 = _get_font(32)
    font3 = _get_font(24)
    title = font.render('Project: IL2D', True, (255, 255, 255))
    title_y = screen.get_height() // 2 - 140
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, title_y))
    opts = ['new_game', 'continue', 'setting', 'leave', 'credits']
    total_height = len(opts) * 44
    start_y = screen.get_height() // 2 - total_height // 2 + 40
    for i, opt in enumerate(opts):
        color = (255, 255, 0) if i == selected else (200, 200, 200)
        surf = font2.render(tr(lang, f"menu.{opt}"), True, color)
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * 44
        screen.blit(surf, (x, y))
        if i == selected:
            rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)
    credits = font3.render('2026 by twjui', True, (120, 120, 120))
    screen.blit(credits, (screen.get_width() // 2 - credits.get_width() // 2, screen.get_height() - 36))


def draw_continue_menu(screen, slots, selected, lang="zh"):
    pygame.draw.rect(screen, (70, 78, 86), screen.get_rect())
    font = _get_font(36, bold=True)
    font2 = _get_font(22)
    title = font.render(tr(lang, "menu.continue"), True, (255, 255, 255))
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, 60))
    if not slots:
        hint = font2.render(tr(lang, "continue.empty"), True, (200, 200, 200))
        screen.blit(hint, (screen.get_width() // 2 - hint.get_width() // 2, 140))
        return
    start_y = 140
    for i, slot in enumerate(slots):
        exists = slot.get("exists", False)
        status = tr(lang, "continue.exists") if exists else tr(lang, "continue.empty")
        label = f"{tr(lang, 'continue.slot', slot=slot.get('slot', i + 1))} - {status}"
        color = (255, 255, 0) if i == selected else (220, 220, 220)
        surf = font2.render(label, True, color)
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * (font2.get_height() + 12)
        screen.blit(surf, (x, y))
        if i == selected:
            rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)
    hint = font2.render(tr(lang, "continue.hint"), True, (180, 180, 180))
    screen.blit(hint, (screen.get_width() // 2 - hint.get_width() // 2, screen.get_height() - 40))


def draw_dev_menu(screen, ctx):
    lang = getattr(ctx.get("game", None), "lang", "zh")
    panel_w = screen.get_width() * 2 // 3
    panel_h = screen.get_height() * 2 // 3
    panel = pygame.Rect(screen.get_width() // 2 - panel_w // 2, screen.get_height() // 2 - panel_h // 2, panel_w, panel_h)
    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    bg.fill((10, 12, 16, 220))
    screen.blit(bg, panel.topleft)
    pygame.draw.rect(screen, (220, 220, 220), panel, 2)
    font = _get_font(22, bold=True)
    font2 = _get_font(18)
    title = font.render(tr(lang, "dev.title"), True, (255, 255, 255))
    screen.blit(title, (panel.x + 16, panel.y + 12))
    opts = ["pre_dev_set", "max_hp", "max_mp", "add_money", "add_skipper", "get_dev_set", "exit"]
    labels = {
        "pre_dev_set": tr(lang, "dev.pre_dev_set"),
        "max_hp": tr(lang, "dev.max_hp"),
        "max_mp": tr(lang, "dev.max_mp"),
        "add_money": tr(lang, "dev.add_money"),
        "add_skipper": tr(lang, "dev.add_skipper"),
        "get_dev_set": tr(lang, "dev.get_dev_set"),
        "exit": tr(lang, "dev.exit")
    }
    y = panel.y + 60
    for i, key in enumerate(opts):
        color = (255, 255, 0) if i == ctx["dev_menu_selected"] else (200, 200, 200)
        surf = font2.render(labels[key], True, color)
        rect = pygame.Rect(panel.x + 16, y - 4, panel.width - 32, font2.get_height() + 8)
        if i == ctx["dev_menu_selected"]:
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)
        screen.blit(surf, (panel.x + 24, y))
        y += font2.get_height() + 12

    if ctx["dev_menu_target"]:
        prompt = f"{tr(lang, 'dev.input_prefix')} {ctx['dev_menu_target']}: {ctx['dev_menu_input']}"
        surf = font2.render(prompt, True, (230, 230, 230))
        screen.blit(surf, (panel.x + 16, panel.bottom - 40))


def draw_settings_menu(screen, selected, sub_mode, lang_selected, lang="zh"):
    pygame.draw.rect(screen, (70, 78, 86), screen.get_rect())
    font = _get_font(32, bold=True)
    font2 = _get_font(22)
    title = font.render(tr(lang, "menu.setting"), True, (255, 255, 255))
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, 40))
    opts = ["setting.language", "setting.back"]
    start_y = 120
    for i, key in enumerate(opts):
        color = (255, 255, 0) if i == selected else (200, 200, 200)
        label = tr(lang, key)
        surf = font2.render(label, True, color)
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * 40
        screen.blit(surf, (x, y))
        if i == selected:
            rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)

    if sub_mode == "language":
        box_w = 320
        box_h = 140
        box = pygame.Rect(screen.get_width() // 2 - box_w // 2, screen.get_height() // 2 - box_h // 2, box_w, box_h)
        pygame.draw.rect(screen, (20, 24, 30), box)
        pygame.draw.rect(screen, (220, 220, 220), box, 2)
        langs = [("zh", tr(lang, "lang.zh")), ("en", tr(lang, "lang.en"))]
        for i, (_, label) in enumerate(langs):
            color = (255, 255, 0) if i == lang_selected else (220, 220, 220)
            surf = font2.render(label, True, color)
            x = box.x + 24
            y = box.y + 24 + i * 36
            screen.blit(surf, (x, y))
            if i == lang_selected:
                rect = pygame.Rect(x - 8, y - 4, surf.get_width() + 16, surf.get_height() + 8)
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=6)


def draw_esc_menu(screen, selected, game=None):
    font = _get_font(18, bold=True)
    font2 = _get_font(16, bold=True)
    opts = ['item', 'hotbar', 'equipments', 'team', 'tutorial', 'map', 'objective', 'skill_tree', 'save', 'leave']
    # requested blue
    screen.fill((14, 26, 48))
    menu_w = screen.get_width() // 4
    menu_h = screen.get_height()
    x = 0
    y = 0
    # left panel
    left_rect = pygame.Rect(x, y, menu_w, menu_h)
    pygame.draw.rect(screen, (12, 42, 70), left_rect)
    pygame.draw.rect(screen, (190, 230, 255), left_rect, 2)
    item_h = font.get_height() + 10
    for i, opt in enumerate(opts):
        is_selected = i == selected
        is_entered = bool(game is not None and is_selected and _is_left_menu_entered(game, opt))
        color = (230, 230, 230) if is_entered else ((255, 255, 0) if is_selected else (245, 245, 245))
        label = _fit_text(font, tr(game.lang, f"esc.{opt}"), menu_w - 34)
        item_rect = pygame.Rect(x + 12, y + 20 + i * item_h, menu_w - 24, item_h)
        if is_selected:
            if is_entered:
                pygame.draw.rect(screen, (55, 55, 55), item_rect, border_radius=4)
                pygame.draw.rect(screen, (165, 165, 165), item_rect, 2, border_radius=4)
            else:
                pygame.draw.rect(screen, (255, 224, 60), item_rect, 2, border_radius=4)
        else:
            pygame.draw.rect(screen, (90, 140, 170), item_rect, 1, border_radius=4)
        txt_x = item_rect.x + 10
        txt_y = item_rect.y + 2
        _draw_text_outline(screen, font, label, color, (0, 0, 0), (txt_x, txt_y), thickness=2)

    right_x = menu_w
    right_w = screen.get_width() - menu_w
    right_h = screen.get_height()
    panel = pygame.Rect(right_x, y, right_w, right_h)
    pygame.draw.rect(screen, (8, 36, 62), panel)
    pygame.draw.rect(screen, (190, 230, 255), panel, 2)

    if game is None:
        return

    # header bar (top)
    header_h = 72
    header_rect = pygame.Rect(panel.x + 8, panel.y + 8, panel.width - 16, header_h)
    pygame.draw.rect(screen, (6, 28, 48), header_rect)
    pygame.draw.rect(screen, (200, 240, 255), header_rect, 2)
    title = opts[selected]
    title_surf = font.render(tr(game.lang, f"esc.{title}"), True, (255, 255, 255))
    screen.blit(title_surf, (header_rect.x + 12, header_rect.y + 10))

    # main content panel
    content_rect = pygame.Rect(panel.x + 8, header_rect.bottom + 8, panel.width - 16, panel.height - header_h - 24 - 64)
    pygame.draw.rect(screen, (8, 32, 56), content_rect)
    pygame.draw.rect(screen, (200, 240, 255), content_rect, 2)
    # header: player/status info (combined status sublayer)
    if game is not None:
        name = getattr(game, "player_name", "player")
        hp = f"HP {game.player.hp}/{game.player.max_hp}"
        mp = f"MP {game.player.mp}/{game.player.max_mp}"
        atk = f"ATK {game.player.attack}"
        defence = f"DEF {game.player.defence}%"
        lv = f"LV {game.player_level}"
        exp = f"EXP {game.player_exp}/{game.exp_to_next_level()}"
        sp = f"SP {game.player_skill_points}"
        rbx = f"RBX {game.money}"
        name_surf = font.render(name, True, (255, 255, 255))
        line1 = f"{hp}   {mp}   {atk}   {defence}"
        line2 = f"{lv}   {exp}   {sp}   {rbx}"
        line1_surf = font2.render(line1, True, (255, 235, 210))
        line2_surf = font2.render(line2, True, (210, 235, 255))
        right_x = header_rect.right - 12
        _draw_text_outline(screen, font, name, (255, 255, 255), (0, 0, 0), (right_x - name_surf.get_width(), header_rect.y + 10))
        _draw_text_outline(screen, font2, line1, (255, 235, 210), (255, 255, 255), (right_x - line1_surf.get_width(), header_rect.y + 32))
        _draw_text_outline(screen, font2, line2, (210, 235, 255), (255, 255, 255), (right_x - line2_surf.get_width(), header_rect.y + 48))

    if game.ui_mode in ("save", "equip_root", "equip", "equip_category", "item", "hotbar", "team", "team_equip_root", "team_equip", "team_equip_category", "map", "objective", "skill_tree", "leave_confirm", "level_skipper"):
        draw_menu_detail(screen, content_rect, game)
    else:
        label = opts[selected]
        if label in ("item", "hotbar", "equipments", "map", "objective"):
            _draw_menu_selected_like_detail(screen, content_rect, game, label)
        else:
            draw_menu_preview(screen, content_rect, game, selected)


def _draw_menu_selected_like_detail(screen, panel, game, label):
    old_mode = getattr(game, "ui_mode", None)
    old_stage = getattr(game, "hotbar_stage", "grid")
    if label == "equipments":
        game.ui_mode = "equip"
    else:
        game.ui_mode = label
    if label == "hotbar":
        game.hotbar_stage = "grid"
    draw_menu_detail(screen, panel, game)
    game.ui_mode = old_mode
    game.hotbar_stage = old_stage


def draw_menu_preview(screen, panel, game, selected):
    font = _get_font(16)
    opts = ['item', 'hotbar', 'equipments', 'team', 'tutorial', 'map', 'objective', 'skill_tree', 'save', 'leave']
    label = opts[selected]
    lines = []
    if label == "item":
        for name, count in list(game.inventory.items()):
            if count <= 0:
                continue
            lines.append(f"{_tr_item_name(game, name)} x{count}")
    elif label == "hotbar":
        active_label = tr(game.lang, "hotbar.item") if game.active_hotbar == "item" else tr(game.lang, "hotbar.magic")
        lines.append(f"{tr(game.lang, 'hotbar.active')}: {active_label}")
        slots = game.item_hotbar_slots if game.active_hotbar == "item" else game.magic_hotbar_slots
        for i, v in enumerate(slots):
            if not v:
                continue
            key = i + 1 if i < 9 else 0
            name = _tr_item_name(game, v) if game.active_hotbar == "item" else _tr_spell_name(game, v)
            lines.append(f"{key}: {name}")
    elif label == "equipments":
        lines.append(tr(game.lang, "preview.current"))
        shown = 0
        for slot in game.get_equip_categories():
            if shown >= 3:
                break
            equipped = game.equipment.get(slot)
            equip_label = _tr_item_name(game, equipped) if equipped else tr(game.lang, "label.none")
            lines.append(f"{_tr_slot_name(game, slot)}: {equip_label}")
            shown += 1
    elif label == "team":
        lines.append(tr(game.lang, "preview.team"))
        members = getattr(game, "team_members", [])
        if not members:
            lines.append(tr(game.lang, "team.none"))
        else:
            for m in members[:6]:
                lines.append(m)
    elif label == "tutorial":
        lines.append(tr(game.lang, "preview.tutorial"))
        lines.append(tr(game.lang, "preview.tutorial_desc"))
    elif label == "map":
        lines.append(tr(game.lang, "preview.map"))
        lines.append(tr(game.lang, "preview.map_desc"))
    elif label == "objective":
        lines.append(tr(game.lang, "preview.objectives"))
        lines.extend(game.objectives[:4])
    elif label == "skill_tree":
        lines.append(tr(game.lang, "preview.skill_tree"))
        lines.append(f"{tr(game.lang, 'label.sp')} {game.player_skill_points}")
    elif label == "save":
        lines.append(tr(game.lang, "preview.save"))
        if game.last_saved:
            lines.append(f"Last slot: {game.last_save_slot}")
    elif label == "leave":
        lines.append(tr(game.lang, "preview.leave"))
    y = panel.y + 48
    body = pygame.Surface((panel.width - 24, panel.height - 56), pygame.SRCALPHA)
    body.fill((6, 14, 26, 105))
    screen.blit(body, (panel.x + 12, panel.y + 40))
    if label == "item":
        col_w = (panel.width - 44) // 2
        row_h = font.get_height() + 6
        max_rows = max(1, (panel.height - 70) // row_h)
        shown = 0
        for i, line in enumerate(lines):
            row = i // 2
            if row >= max_rows:
                break
            col = i % 2
            x = panel.x + 20 + col * (col_w + 8)
            yy = y + row * row_h
            line = _fit_text(font, line, col_w - 4)
            _draw_text_outline(screen, font, line, (235, 235, 235), (0, 0, 0), (x, yy))
            shown += 1
        return
    for line in lines:
        line = _fit_text(font, line, panel.width - 36)
        _draw_text_outline(screen, font, line, (235, 235, 235), (0, 0, 0), (panel.x + 20, y))
        y += font.get_height() + 6


def draw_menu_detail(screen, panel, game):
    font = _get_font(16)
    y = panel.y + 48
    body = pygame.Surface((panel.width - 24, panel.height - 56), pygame.SRCALPHA)
    body.fill((6, 14, 26, 110))
    screen.blit(body, (panel.x + 12, panel.y + 40))
    if game.ui_mode == "map":
        _draw_world_map(screen, panel, game, font)
        return
    if game.ui_mode == "item":
        categories = game.get_item_categories() if hasattr(game, "get_item_categories") else ["item", "gift", "equipment", "special"]
        current_category = getattr(game, "item_category", "item")
        focus = getattr(game, "item_focus", "tabs")
        if focus not in ("tabs", "items"):
            focus = "tabs"
        if current_category not in categories:
            current_category = "item"
            game.item_category = current_category
        tab_h = font.get_height() + 8
        tab_gap = 6
        tab_w = max(80, (panel.width - 32 - (len(categories) - 1) * tab_gap) // max(1, len(categories)))
        tab_y = y
        for i, cat in enumerate(categories):
            rx = panel.x + 16 + i * (tab_w + tab_gap)
            rect = pygame.Rect(rx, tab_y - 2, tab_w, tab_h)
            is_selected = (cat == current_category)
            tab_active = is_selected and focus == "tabs"
            _draw_readability_row(screen, rect, selected=tab_active)
            if is_selected and focus == "items":
                pygame.draw.rect(screen, (55, 55, 55), rect, border_radius=4)
                pygame.draw.rect(screen, (165, 165, 165), rect, 2, border_radius=4)
            label = _fit_text(font, _tr_item_category(game, cat), tab_w - 10)
            color = (255, 247, 170) if tab_active else (230, 230, 230)
            _draw_text_outline(screen, font, label, color, (0, 0, 0), (rx + 6, tab_y), thickness=2)
        y += tab_h + 10

        items = game.get_item_list()
        if not items:
            _draw_text_outline(screen, font, tr(game.lang, "msg.no_items"), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
            return
        selected = game.item_selected % len(items)
        row_h = font.get_height() + 8
        col_w = (panel.width - 40) // 2
        max_rows = max(1, (panel.bottom - y - 10) // row_h)
        per_page = max_rows * 2
        page = selected // per_page
        start = page * per_page
        end = min(len(items), start + per_page)
        show = items[start:end]
        for i, name in enumerate(show):
            count = game.inventory.get(name, 0)
            line = f"{_tr_item_name(game, name)} x{count}"
            abs_i = start + i
            row = i // 2
            col = i % 2
            rx = panel.x + 16 + col * (col_w + 8)
            ry = y + row * row_h
            rect = pygame.Rect(rx, ry - 2, col_w, font.get_height() + 6)
            item_active = abs_i == selected and focus == "items"
            _draw_readability_row(screen, rect, selected=item_active)
            color = (255, 247, 170) if item_active else (230, 230, 230)
            _draw_text_outline(screen, font, _fit_text(font, line, col_w - 10), color, (0, 0, 0), (rx + 6, ry), thickness=2)
    elif game.ui_mode == "hotbar":
        mode = getattr(game, "hotbar_mode", "item")
        stage = getattr(game, "hotbar_stage", "grid")
        if stage not in ("grid", "pick"):
            stage = "grid"
        slot_sel = max(0, min(9, int(getattr(game, "hotbar_slot_selected", 0))))

        left_w = (panel.width - 40) // 2
        right_x = panel.x + 24 + left_w
        head_y = y
        _draw_text_outline(screen, font, tr(game.lang, "hotbar.item"), (255, 247, 170) if mode == "item" else (230, 230, 230), (0, 0, 0), (panel.x + 20, head_y), thickness=2)
        _draw_text_outline(screen, font, tr(game.lang, "hotbar.magic"), (255, 247, 170) if mode == "magic" else (230, 230, 230), (0, 0, 0), (right_x + 4, head_y), thickness=2)
        y += font.get_height() + 8

        # Always show full 10 rows in settings (item 10 + magic 10).
        rows = list(range(10))

        row_h = font.get_height() + 8
        for i in rows:
            key = i + 1 if i < 9 else 0
            ly = y
            left_rect = pygame.Rect(panel.x + 16, ly - 2, left_w, font.get_height() + 6)
            right_rect = pygame.Rect(right_x, ly - 2, left_w, font.get_height() + 6)
            left_active = (i == slot_sel and mode == "item")
            right_active = (i == slot_sel and mode == "magic")
            _draw_readability_row(screen, left_rect, selected=left_active)
            _draw_readability_row(screen, right_rect, selected=right_active)
            # If we are already inside picker stage, show parent slot as "entered" (dark grey).
            if stage == "pick" and i == slot_sel:
                entered_rect = left_rect if mode == "item" else right_rect
                pygame.draw.rect(screen, (55, 55, 55), entered_rect, border_radius=4)
                pygame.draw.rect(screen, (165, 165, 165), entered_rect, 2, border_radius=4)

            item_name = game.item_hotbar_slots[i]
            magic_name = game.magic_hotbar_slots[i]
            left_txt = f"{key}: {_tr_item_name(game, item_name) if item_name else '-'}"
            right_txt = f"{key}: {_tr_spell_name(game, magic_name) if magic_name else '-'}"
            left_color = (230, 230, 230) if (stage == "pick" and i == slot_sel and mode == "item") else ((255, 247, 170) if left_active else (230, 230, 230))
            right_color = (230, 230, 230) if (stage == "pick" and i == slot_sel and mode == "magic") else ((255, 247, 170) if right_active else (230, 230, 230))
            _draw_text_outline(screen, font, _fit_text(font, left_txt, left_w - 10), left_color, (0, 0, 0), (left_rect.x + 6, ly), thickness=2)
            _draw_text_outline(screen, font, _fit_text(font, right_txt, left_w - 10), right_color, (0, 0, 0), (right_rect.x + 6, ly), thickness=2)
            y += row_h

        if stage == "grid":
            hint = "W/S: row  A/D: item/magic  Enter: choose  Del: clear"
            _draw_text_outline(screen, font, hint, (200, 200, 200), (255, 255, 255), (panel.x + 20, panel.bottom - 28))
            return

        src = game.get_item_list() if mode == "item" else [sp.get("name") for sp in game.get_unlocked_spells()]
        picker_top = min(panel.bottom - 130, y + 8)
        title = f"Assign -> {'ITEM' if mode == 'item' else 'MAGIC'} [{slot_sel + 1 if slot_sel < 9 else 0}]"
        _draw_text_outline(screen, font, title, (230, 230, 230), (255, 255, 255), (panel.x + 20, picker_top))
        picker_y = picker_top + font.get_height() + 8
        if not src:
            _draw_text_outline(screen, font, tr(game.lang, "msg.no_items" if mode == "item" else "msg.no_spells"), (230, 230, 230), (255, 255, 255), (panel.x + 20, picker_y))
            return
        sel = getattr(game, "hotbar_list_selected", 0) % len(src)
        list_row_h = font.get_height() + 6
        max_rows = max(1, (panel.bottom - picker_y - 8) // list_row_h)
        page = sel // max_rows
        start = page * max_rows
        end = min(len(src), start + max_rows)
        for i in range(start, end):
            rect = pygame.Rect(panel.x + 16, picker_y - 2, panel.width - 32, font.get_height() + 4)
            _draw_readability_row(screen, rect, selected=(i == sel))
            label = _tr_item_name(game, src[i]) if mode == "item" else _tr_spell_name(game, src[i])
            _draw_text_outline(screen, font, _fit_text(font, label, panel.width - 44), (255, 247, 170) if i == sel else (230, 230, 230), (0, 0, 0), (panel.x + 24, picker_y), thickness=2)
            picker_y += list_row_h
    elif game.ui_mode == "equip_root":
        options = [
            tr(game.lang, "equip.change"),
            tr(game.lang, "equip.best"),
            tr(game.lang, "equip.put_down_all"),
        ]
        selected = getattr(game, "equip_root_selected", 0) % len(options)
        for i, line in enumerate(options):
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "equip":
        tabs = [
            tr(game.lang, "equip.change"),
            tr(game.lang, "equip.best"),
            tr(game.lang, "equip.put_down_all"),
        ]
        tab_w = (panel.width - 40) // 3
        tab_y = y
        for i, t in enumerate(tabs):
            rx = panel.x + 16 + i * (tab_w + 4)
            rect = pygame.Rect(rx, tab_y - 2, tab_w, font.get_height() + 8)
            tab_selected = (i == game.equip_root_selected)
            tab_active = tab_selected and getattr(game, "equip_focus", "tabs") == "tabs"
            _draw_readability_row(screen, rect, selected=tab_active)
            # Entered-state hint: selected tab is grey only after stepping into deeper sublayer.
            if tab_selected and not tab_active and getattr(game, "equip_focus", "tabs") in ("slots", "items"):
                pygame.draw.rect(screen, (55, 55, 55), rect, border_radius=4)
                pygame.draw.rect(screen, (165, 165, 165), rect, 2, border_radius=4)
                tab_color = (230, 230, 230)
            else:
                tab_color = (255, 247, 170) if tab_selected else (230, 230, 230)
            _draw_text_outline(screen, font, _fit_text(font, t, tab_w - 10), tab_color, (0, 0, 0), (rx + 6, tab_y), thickness=2)
        y += font.get_height() + 14
        categories = game.get_equip_categories()
        non_rings = [c for c in categories if not c.startswith("ring")]
        rings = sorted(
            [c for c in categories if c.startswith("ring")],
            key=lambda s: int(s[4:]) if s[4:].isdigit() else 99
        )
        categories = non_rings + rings
        pair_w = (panel.width - 40) // 2
        pair_gap = 8
        slot_w = max(60, int(pair_w * 0.35))
        val_w = pair_w - slot_w - pair_gap
        row_h = font.get_height() + 8
        cat_rows = (len(categories) + 1) // 2

        for r in range(cat_rows):
            for c in range(2):
                idx = r * 2 + c
                if idx >= len(categories):
                    continue
                name = categories[idx]
                base_x = panel.x + 16 + c * (pair_w + 8)
                ry = y + r * row_h
                slot_rect = pygame.Rect(base_x, ry - 2, slot_w, font.get_height() + 6)
                val_rect = pygame.Rect(base_x + slot_w + pair_gap, ry - 2, val_w, font.get_height() + 6)
                is_sel = idx == (game.equip_category_selected % len(categories))
                is_active = is_sel and getattr(game, "equip_focus", "tabs") == "slots"
                _draw_readability_row(screen, slot_rect, selected=is_active)
                _draw_readability_row(screen, val_rect, selected=is_active)
                if is_sel and not is_active and getattr(game, "equip_focus", "tabs") == "items":
                    pygame.draw.rect(screen, (55, 55, 55), slot_rect, border_radius=4)
                    pygame.draw.rect(screen, (55, 55, 55), val_rect, border_radius=4)
                    pygame.draw.rect(screen, (165, 165, 165), slot_rect, 2, border_radius=4)
                    pygame.draw.rect(screen, (165, 165, 165), val_rect, 2, border_radius=4)
                label = _tr_slot_name(game, name)
                equipped = game.equipment.get(name) if name in game.equipment else None
                equip_label = _tr_item_name(game, equipped) if equipped else tr(game.lang, "label.none")
                slot_color = (230, 230, 230) if (is_sel and not is_active and getattr(game, "equip_focus", "tabs") == "items") else ((255, 247, 170) if is_sel else (230, 230, 230))
                _draw_text_outline(screen, font, _fit_text(font, label, slot_w - 10), slot_color, (0, 0, 0), (slot_rect.x + 6, ry), thickness=2)
                _draw_text_outline(screen, font, _fit_text(font, equip_label, val_w - 10), (230, 230, 230), (0, 0, 0), (val_rect.x + 6, ry), thickness=2)

        y += cat_rows * row_h + 10

        # inventory list for selected category (2 columns)
        if categories:
            game.equip_category_selected = game.equip_category_selected % len(categories)
            game.equip_category = categories[game.equip_category_selected]
        equipables = game.get_equipable_items()
        slot_key = "ring" if game.equip_category.startswith("ring") else game.equip_category
        filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
        if not filtered:
            surf = font.render(tr(game.lang, "msg.no_items_category"), True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        list_x = panel.x + 16
        list_y = y
        col_w2 = (panel.width - 40) // 2
        row_h2 = font.get_height() + 8
        selected = game.equip_selected % len(filtered)
        max_rows = max(1, (panel.bottom - list_y - 10) // row_h2)
        per_page = max_rows * 2
        page = selected // per_page
        start = page * per_page
        end = min(len(filtered), start + per_page)
        for i in range(start, end):
            name = filtered[i]
            li = i - start
            col = li % 2
            row = (i - start) // 2
            color = (255, 255, 0) if i == selected else (230, 230, 230)
            count = game.inventory.get(name, 0)
            label = f"{_tr_item_name(game, name)} x{count}"
            rx = list_x + col * (col_w2 + 8)
            ry = list_y + row * row_h2
            rect = pygame.Rect(rx, ry - 2, col_w2, font.get_height() + 6)
            item_active = (i == selected and getattr(game, "equip_focus", "tabs") == "items")
            _draw_readability_row(screen, rect, selected=item_active)
            item_color = color
            _draw_text_outline(screen, font, _fit_text(font, label, col_w2 - 10), item_color, (0, 0, 0), (rx + 8, ry))
    elif game.ui_mode == "equip_category":
        categories = game.get_equip_categories()
        col_w = (panel.width - 40) // 2
        y = panel.y + 48
        for i, name in enumerate(categories):
            is_sel = i == game.equip_category_selected
            color = (255, 255, 0) if is_sel else (230, 230, 230)
            label = _tr_slot_name(game, name)
            left_rect = pygame.Rect(panel.x + 16, y - 2, col_w, font.get_height() + 4)
            right_rect = pygame.Rect(panel.x + 24 + col_w, y - 2, col_w, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), left_rect, 1, border_radius=4)
            pygame.draw.rect(screen, (255, 255, 255), right_rect, 1, border_radius=4)
            if is_sel:
                pygame.draw.rect(screen, _flicker_color(), left_rect, 2, border_radius=4)
            equipped = game.equipment.get(name) if name in game.equipment else None
            equip_label = _tr_item_name(game, equipped) if equipped else tr(game.lang, "label.none")
            _draw_text_outline(screen, font, label, color, (255, 255, 255), (left_rect.x + 8, y))
            _draw_text_outline(screen, font, equip_label, (230, 230, 230), (255, 255, 255), (right_rect.x + 8, y))
            y += font.get_height() + 6
        # bottom list (3 rows)
        items = game.get_equipable_items()
        bottom_y = panel.bottom - 88
        for i in range(3):
            if i >= len(items):
                break
            name = items[i]
            count = game.inventory.get(name, 0)
            line = f"{_tr_item_name(game, name)} x{count}"
            _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 16, bottom_y + i * (font.get_height() + 6)))
    elif game.ui_mode == "team":
        members = getattr(game, "team_members", [])
        _draw_text_outline(screen, font, tr(game.lang, "preview.team"), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
        y += font.get_height() + 10
        if not members:
            _draw_text_outline(screen, font, tr(game.lang, "team.none"), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
        else:
            selected = int(getattr(game, "team_selected", 0))
            for i, m in enumerate(members):
                line = m
                if m == "monst3r":
                    line = f"Monst3r  ({tr(game.lang, 'team.detect')}: 4)"
                elif m == "wisadel":
                    line = f"Wisadel  ({tr(game.lang, 'team.detect')}: 8, {tr(game.lang, 'team.range')}: 5)"
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 6)
                _draw_readability_row(screen, rect, selected=(i == selected))
                color = (255, 247, 170) if i == selected else (230, 230, 230)
                _draw_text_outline(screen, font, _fit_text(font, line, panel.width - 52), color, (0, 0, 0), (panel.x + 24, y), thickness=2)
                y += font.get_height() + 8
            y += 8
            _draw_text_outline(screen, font, tr(game.lang, "team.hint_open_equip"), (200, 220, 240), (255, 255, 255), (panel.x + 20, y))
    elif game.ui_mode == "team_equip_root":
        options = [
            tr(game.lang, "equip.change"),
            tr(game.lang, "equip.best"),
            tr(game.lang, "equip.put_down_all"),
        ]
        selected = getattr(game, "team_equip_root_selected", 0) % len(options)
        for i, line in enumerate(options):
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
            if i == selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "team_equip":
        tabs = [
            tr(game.lang, "equip.change"),
            tr(game.lang, "equip.best"),
            tr(game.lang, "equip.put_down_all"),
        ]
        members = game.get_team_member_ids() if hasattr(game, "get_team_member_ids") else []
        if not members:
            _draw_text_outline(screen, font, tr(game.lang, "team.none"), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
            return
        m_idx = int(getattr(game, "team_equip_member_selected", 0)) % len(members)
        member = members[m_idx]
        _draw_text_outline(screen, font, tr(game.lang, "team.equip_title", member=member), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
        y += font.get_height() + 10
        tab_w = (panel.width - 40) // 3
        tab_y = y
        for i, t in enumerate(tabs):
            rx = panel.x + 16 + i * (tab_w + 4)
            rect = pygame.Rect(rx, tab_y - 2, tab_w, font.get_height() + 8)
            tab_selected = (i == game.team_equip_root_selected)
            tab_active = tab_selected and getattr(game, "team_equip_focus", "tabs") == "tabs"
            _draw_readability_row(screen, rect, selected=tab_active)
            if tab_selected and not tab_active and getattr(game, "team_equip_focus", "tabs") in ("slots", "items"):
                pygame.draw.rect(screen, (55, 55, 55), rect, border_radius=4)
                pygame.draw.rect(screen, (165, 165, 165), rect, 2, border_radius=4)
                tab_color = (230, 230, 230)
            else:
                tab_color = (255, 247, 170) if tab_selected else (230, 230, 230)
            _draw_text_outline(screen, font, _fit_text(font, t, tab_w - 10), tab_color, (0, 0, 0), (rx + 6, tab_y), thickness=2)
        y += font.get_height() + 14
        categories = game.get_team_equip_categories()
        pair_w = (panel.width - 40) // 2
        pair_gap = 8
        slot_w = max(60, int(pair_w * 0.35))
        val_w = pair_w - slot_w - pair_gap
        row_h = font.get_height() + 8
        cat_rows = (len(categories) + 1) // 2

        for r in range(cat_rows):
            for c in range(2):
                idx = r * 2 + c
                if idx >= len(categories):
                    continue
                name = categories[idx]
                base_x = panel.x + 16 + c * (pair_w + 8)
                ry = y + r * row_h
                slot_rect = pygame.Rect(base_x, ry - 2, slot_w, font.get_height() + 6)
                val_rect = pygame.Rect(base_x + slot_w + pair_gap, ry - 2, val_w, font.get_height() + 6)
                is_sel = idx == (game.team_equip_slot_selected % len(categories))
                is_active = is_sel and getattr(game, "team_equip_focus", "tabs") == "slots"
                _draw_readability_row(screen, slot_rect, selected=is_active)
                _draw_readability_row(screen, val_rect, selected=is_active)
                if is_sel and not is_active and getattr(game, "team_equip_focus", "tabs") == "items":
                    pygame.draw.rect(screen, (55, 55, 55), slot_rect, border_radius=4)
                    pygame.draw.rect(screen, (55, 55, 55), val_rect, border_radius=4)
                    pygame.draw.rect(screen, (165, 165, 165), slot_rect, 2, border_radius=4)
                    pygame.draw.rect(screen, (165, 165, 165), val_rect, 2, border_radius=4)
                label = tr(game.lang, f"team.slot.{name}")
                equipped = game.get_team_equipment_item(member, name) if hasattr(game, "get_team_equipment_item") else None
                equip_label = _tr_item_name(game, equipped) if equipped else tr(game.lang, "label.none")
                slot_color = (230, 230, 230) if (is_sel and not is_active and getattr(game, "team_equip_focus", "tabs") == "items") else ((255, 247, 170) if is_sel else (230, 230, 230))
                _draw_text_outline(screen, font, _fit_text(font, label, slot_w - 10), slot_color, (0, 0, 0), (slot_rect.x + 6, ry), thickness=2)
                _draw_text_outline(screen, font, _fit_text(font, equip_label, val_w - 10), (230, 230, 230), (0, 0, 0), (val_rect.x + 6, ry), thickness=2)

        y += cat_rows * row_h + 10
        if categories:
            game.team_equip_slot_selected = game.team_equip_slot_selected % len(categories)
            game.team_equip_category = categories[game.team_equip_slot_selected]
        equipables = game.get_team_equipable_items()
        slot_key = "ring" if game.team_equip_category.startswith("ring") else game.team_equip_category
        filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == slot_key]
        if not filtered:
            surf = font.render(tr(game.lang, "msg.no_items_category"), True, (230, 230, 230))
            screen.blit(surf, (panel.x + 20, y))
            return
        list_x = panel.x + 16
        list_y = y
        col_w2 = (panel.width - 40) // 2
        row_h2 = font.get_height() + 8
        selected = game.team_equip_item_selected % len(filtered)
        max_rows = max(1, (panel.bottom - list_y - 10) // row_h2)
        per_page = max_rows * 2
        page = selected // per_page
        start = page * per_page
        end = min(len(filtered), start + per_page)
        for i in range(start, end):
            name = filtered[i]
            li = i - start
            col = li % 2
            row = (i - start) // 2
            color = (255, 255, 0) if i == selected else (230, 230, 230)
            count = game.inventory.get(name, 0)
            label = f"{_tr_item_name(game, name)} x{count}"
            rx = list_x + col * (col_w2 + 8)
            ry = list_y + row * row_h2
            rect = pygame.Rect(rx, ry - 2, col_w2, font.get_height() + 6)
            item_active = (i == selected and getattr(game, "team_equip_focus", "tabs") == "items")
            _draw_readability_row(screen, rect, selected=item_active)
            _draw_text_outline(screen, font, _fit_text(font, label, col_w2 - 10), color, (0, 0, 0), (rx + 8, ry))
    elif game.ui_mode == "team_equip_category":
        members = game.get_team_member_ids() if hasattr(game, "get_team_member_ids") else []
        if not members:
            _draw_text_outline(screen, font, tr(game.lang, "team.none"), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
            return
        m_idx = int(getattr(game, "team_equip_member_selected", 0)) % len(members)
        member = members[m_idx]
        _draw_text_outline(screen, font, tr(game.lang, "team.equip_title", member=member), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
        y += font.get_height() + 10
        categories = game.get_team_equip_categories()
        col_w = (panel.width - 40) // 2
        for i, name in enumerate(categories):
            is_sel = i == game.team_equip_slot_selected
            color = (255, 255, 0) if is_sel else (230, 230, 230)
            label = tr(game.lang, f"team.slot.{name}")
            left_rect = pygame.Rect(panel.x + 16, y - 2, col_w, font.get_height() + 4)
            right_rect = pygame.Rect(panel.x + 24 + col_w, y - 2, col_w, font.get_height() + 4)
            pygame.draw.rect(screen, (255, 255, 255), left_rect, 1, border_radius=4)
            pygame.draw.rect(screen, (255, 255, 255), right_rect, 1, border_radius=4)
            if is_sel:
                pygame.draw.rect(screen, _flicker_color(), left_rect, 2, border_radius=4)
            equipped = game.get_team_equipment_item(member, name) if hasattr(game, "get_team_equipment_item") else None
            equip_label = _tr_item_name(game, equipped) if equipped else tr(game.lang, "label.none")
            _draw_text_outline(screen, font, label, color, (255, 255, 255), (left_rect.x + 8, y))
            _draw_text_outline(screen, font, equip_label, (230, 230, 230), (255, 255, 255), (right_rect.x + 8, y))
            y += font.get_height() + 6
    elif game.ui_mode == "objective":
        for line in game.get_objective_lines():
            _draw_text_outline(screen, font, line, (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
            y += font.get_height() + 6
        y += 8
        _draw_text_outline(screen, font, "missions", (210, 230, 255), (255, 255, 255), (panel.x + 20, y))
        y += font.get_height() + 6
        missions = game.get_trackable_missions() if hasattr(game, "get_trackable_missions") else []
        if not missions:
            _draw_text_outline(screen, font, "no mission", (220, 220, 220), (255, 255, 255), (panel.x + 20, y))
        else:
            selected = max(0, min(len(missions) - 1, int(getattr(game, "objective_selected", 0))))
            tracked = getattr(game, "tracked_mission", None)
            for i, row in enumerate(missions):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 6)
                _draw_readability_row(screen, rect, selected=(i == selected))
                marker = "[tracking]" if row.get("id") == tracked else "[ ]"
                line = f"{marker} {row.get('name', 'Mission')}: {row.get('text', '')}"
                color = (255, 247, 170) if i == selected else (230, 230, 230)
                _draw_text_outline(screen, font, _fit_text(font, line, panel.width - 44), color, (0, 0, 0), (panel.x + 24, y), thickness=2)
                y += font.get_height() + 8
    elif game.ui_mode == "skill_tree":
        nodes = game.get_skill_tree_nodes()
        if not nodes:
            _draw_text_outline(screen, font, tr(game.lang, "msg.no_skills"), (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
            return
        _draw_text_outline(screen, font, f"{tr(game.lang, 'label.sp')}: {game.player_skill_points}", (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
        y += font.get_height() + 10
        selected = game.skill_tree_selected % len(nodes)
        for i, n in enumerate(nodes):
            state = tr(game.lang, "skill.unlocked") if n["unlocked"] else tr(game.lang, "skill.locked")
            line = f"{n['name']}  [{state}]  ({tr(game.lang, 'label.cost')}: {n['cost']})"
            color = (255, 255, 0) if i == selected else (230, 230, 230)
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            _draw_readability_row(screen, rect, selected=(i == selected))
            _draw_text_outline(screen, font, line, color, (255, 255, 255), (panel.x + 24, y))
            y += font.get_height() + 8
    elif game.ui_mode == "save":
        slots = 3
        for i in range(slots):
            color = (255, 255, 0) if i == game.save_selected else (230, 230, 230)
            line = f"slot {i + 1}"
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            _draw_readability_row(screen, rect, selected=(i == game.save_selected))
            _draw_text_outline(screen, font, line, color, (255, 255, 255), (panel.x + 24, y))
            y += font.get_height() + 10
        hint = font.render(tr(game.lang, "hint.save"), True, (200, 200, 200))
        screen.blit(hint, (panel.x + 20, panel.bottom - 30))
    elif game.ui_mode == "leave_confirm":
        prompt, options = get_leave_prompt(game)
        surf = font.render(prompt, True, (230, 230, 230))
        screen.blit(surf, (panel.x + 20, y))
        y += font.get_height() + 10
        for i, opt in enumerate(options):
            color = (255, 255, 0) if i == game.leave_selected else (230, 230, 230)
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
            _draw_readability_row(screen, rect, selected=(i == game.leave_selected))
            _draw_text_outline(screen, font, opt, color, (255, 255, 255), (panel.x + 24, y))
            y += font.get_height() + 6
    elif game.ui_mode == "level_skipper":
        available = game.inventory.get("rogue level skipper", 0)
        title = tr(game.lang, "msg.skipper_prompt")
        _draw_text_outline(screen, font, title, (230, 230, 230), (255, 255, 255), (panel.x + 20, y))
        y += font.get_height() + 14
        line = tr(game.lang, "msg.skipper_amount", count=game.level_skip_amount, max_count=available)
        rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 8)
        pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=4)
        pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
        _draw_text_outline(screen, font, line, (255, 255, 0), (255, 255, 255), (panel.x + 24, y))
        y += font.get_height() + 18
        hint = tr(game.lang, "msg.skipper_hint")
        _draw_text_outline(screen, font, hint, (200, 200, 200), (255, 255, 255), (panel.x + 20, y))


def get_leave_prompt(game):
    return "leave", ["starter menu", "leave game", "go back"]


def draw_player_ui(game, screen):
    font = _get_font(18)
    player = getattr(game, 'player', None)
    if player is not None:
        hp = getattr(player, 'hp', 0)
        max_hp = getattr(player, 'max_hp', hp)
        mp = getattr(player, 'mp', 0)
        max_mp = getattr(player, 'max_mp', mp)
        hp_text = f"{tr(game.lang, 'label.hp')}: {hp}/{max_hp}"
        mp_text = f"{tr(game.lang, 'label.mp')}: {mp}/{max_mp}"
        bar_h = 56
        bar_rect = pygame.Rect(0, screen.get_height() - bar_h, screen.get_width(), bar_h)
        pygame.draw.rect(screen, (20, 24, 28), bar_rect)
        pygame.draw.rect(screen, (180, 200, 220), bar_rect, 2)
        surf_hp = font.render(hp_text, True, (255, 200, 200))
        surf_mp = font.render(mp_text, True, (200, 220, 255))
        shadow_hp = font.render(hp_text, True, (0, 0, 0))
        shadow_mp = font.render(mp_text, True, (0, 0, 0))
        y0 = screen.get_height() - bar_h + 6
        _draw_text_outline(screen, font, hp_text, (255, 200, 200), (255, 255, 255), (16, y0))
        _draw_text_outline(screen, font, mp_text, (200, 220, 255), (255, 255, 255), (16, y0 + surf_hp.get_height() + 4))

        # active hotbar above status bar
        hb_font = _get_font(13, bold=True)
        slots = game.item_hotbar_slots if getattr(game, "active_hotbar", "item") == "item" else game.magic_hotbar_slots
        hb_w = screen.get_width() - 24
        hb_h = 34
        hb_x = 12
        hb_y = bar_rect.y - hb_h - 8
        pygame.draw.rect(screen, (8, 12, 18), (hb_x, hb_y, hb_w, hb_h))
        pygame.draw.rect(screen, (120, 150, 180), (hb_x, hb_y, hb_w, hb_h), 1)
        slot_w = (hb_w - 18) // 10
        for i in range(10):
            sx = hb_x + 6 + i * (slot_w + 1)
            sy = hb_y + 4
            rect = pygame.Rect(sx, sy, slot_w, hb_h - 8)
            pygame.draw.rect(screen, (0, 0, 0), rect)
            pygame.draw.rect(screen, (90, 110, 130), rect, 1)
            key = str(i + 1) if i < 9 else "0"
            _draw_text_outline(screen, hb_font, key, (170, 190, 220), (0, 0, 0), (sx + 2, sy + 1), thickness=1)
            name = slots[i]
            if name:
                label = _tr_item_name(game, name) if game.active_hotbar == "item" else _tr_spell_name(game, name)
                _draw_text_outline(screen, hb_font, _fit_text(hb_font, label, slot_w - 6), (230, 230, 230), (0, 0, 0), (sx + 2, sy + 14), thickness=1)


def draw_messages(game, screen):
    if not game.message_queue:
        return
    font = _get_font(14)
    messages = list(game.message_queue)[-3:]
    # Reserve bottom space for status bar + hotbar to prevent overlap.
    y = screen.get_height() - (56 + 34 + 12)
    if game.ui_mode == "dialog" and game.dialog_data and game.dialog_node:
        panel_h = screen.get_height() // 4
        panel_top = (screen.get_height() - 48) - panel_h
        y = min(y, panel_top - 10)
    now = time.time()
    for msg in reversed(messages):
        created = msg.get("created", now)
        age = now - created
        alpha = 255
        if age > game.message_show_time:
            fade_age = min(age - game.message_show_time, game.message_fade_time)
            alpha = int(255 * (1 - fade_age / game.message_fade_time))
        lines = msg.get("lines")
        if not lines:
            lines = [msg.get("text", "")]
        # background box for readability
        max_w = 0
        total_h = len(lines) * (font.get_height() + 4)
        for line in lines:
            max_w = max(max_w, font.size(line)[0])
        box_w = max_w + 16
        box_h = total_h + 10
        box_x = screen.get_width() - box_w - 12
        box_y = y - box_h + 6
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill((10, 12, 16, min(200, alpha)))
        screen.blit(bg, (box_x, box_y))
        for line in reversed(lines):
            surf = font.render(line, True, (255, 255, 255))
            surf.set_alpha(alpha)
            x = screen.get_width() - surf.get_width() - 16
            y -= font.get_height() + 4
            screen.blit(surf, (x, y))
        y -= 6


def draw_tutorial_panel(game, screen):
    core = getattr(game, "tutorial_core", None)
    if not core or not getattr(core, "active", False):
        return
    payload = core.get_ui_payload() if hasattr(core, "get_ui_payload") else None
    if not payload:
        return

    font_title = _get_font(16, bold=True)
    font_body = _get_font(14)
    panel_w = int(screen.get_width() * 0.58)
    panel_h = int(screen.get_height() * 0.15)
    panel_x = int((screen.get_width() - panel_w) * 0.38)
    bar_h = 56
    hotbar_h = 34
    panel_y = screen.get_height() - (bar_h + hotbar_h + panel_h + 20)
    panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    shade = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
    shade.fill((8, 16, 30, 210))
    screen.blit(shade, (panel.x, panel.y))
    pygame.draw.rect(screen, (180, 220, 255), panel, 2, border_radius=8)

    speaker = str(payload.get("speaker", "dev"))
    title = str(payload.get("title", "Tutorial"))
    hint = str(payload.get("hint", ""))
    progress = str(payload.get("progress", ""))
    countdown = payload.get("countdown", None)
    _draw_text_outline(screen, font_title, f"{speaker}:", (170, 220, 255), (0, 0, 0), (panel.x + 12, panel.y + 10), thickness=2)
    _draw_text_outline(screen, font_title, title, (245, 245, 245), (0, 0, 0), (panel.x + 84, panel.y + 10), thickness=2)
    if progress:
        _draw_text_outline(screen, font_body, progress, (255, 240, 170), (0, 0, 0), (panel.right - 150, panel.y + 12), thickness=2)
    lines = _wrap_text(font_body, hint, panel.width - 24)
    yy = panel.y + 36
    for line in lines[:3]:
        _draw_text_outline(screen, font_body, line, (225, 235, 245), (0, 0, 0), (panel.x + 12, yy), thickness=1)
        yy += font_body.get_height() + 4
    if countdown is not None:
        ctext = tr(game.lang, "tutorial.dev.countdown", sec=int(countdown))
        _draw_text_outline(screen, font_body, ctext, (255, 210, 150), (0, 0, 0), (panel.x + 12, panel.bottom - 24), thickness=2)

def _draw_world_map(screen, panel, game, font):
    nodes_all = dict(getattr(game, "world_map_nodes", {}) or {})
    edges_all = list(getattr(game, "world_map_edges", []) or [])
    # Keep world map extensible for mod maps while anchoring known core maps.
    nodes = dict(nodes_all)
    edges = [e for e in edges_all if e[0] in nodes and e[1] in nodes]
    if not nodes:
        return
    explored = set(getattr(game, "explored_maps", set()) or set())
    cur = game.map.name if game.map.name in nodes else ("rogue" if game.map.name == "rogue" else game.map.name)
    if cur not in nodes and game.map.name == "rogue":
        nodes["rogue"] = {"w": max(1, int(getattr(game.map, "w", 20))), "h": max(1, int(getattr(game.map, "h", 20)))}
        cur = "rogue"
    if cur:
        explored.add(cur)

    # Strictly clip drawing to the current ESC sublayer panel.
    old_clip = screen.get_clip()
    screen.set_clip(panel)

    map_rect = pygame.Rect(panel.x + 18, panel.y + 48, panel.width - 36, panel.height - 72)
    centers = {}
    rects = {}

    # Base organization:
    # map_1 left, map_2 middle, map_3 right, rogue up.
    anchor_base = {
        "map_1.json": (0.16, 0.55),
        "map_2.json": (0.50, 0.55),
        "map_3.json": (0.84, 0.55),
        "rogue": (0.50, 0.20),
        # Farmer mod map (requested): below map_2.
        "farm_01.json": (0.50, 0.83),
    }
    # Recenter whole graph so current map is the visual focus.
    focus = cur if cur in anchor_base else "map_2.json"
    focus_src = anchor_base.get(focus, (0.50, 0.55))
    focus_dst = (0.50, 0.55)
    dx = focus_dst[0] - focus_src[0]
    dy = focus_dst[1] - focus_src[1]
    anchor = {}
    for k, (rx, ry) in anchor_base.items():
        anchor[k] = (rx + dx, ry + dy)

    fallback_count = 0
    for name, meta in nodes.items():
        mw = max(1.0, float(meta.get("w", 20)))
        mh = max(1.0, float(meta.get("h", 20)))
        # Bigger map cards for readability.
        box_w = max(52, min(190, int(mw * 2.4)))
        box_h = max(36, min(130, int(mh * 2.4)))
        if name in anchor:
            rx, ry = anchor[name]
        else:
            # Spread unknown/mod maps in a small bottom row band.
            rx = 0.16 + (fallback_count % 5) * 0.17
            ry = 0.87 + (fallback_count // 5) * 0.09
            fallback_count += 1
        cx = int(map_rect.x + map_rect.width * rx)
        cy = int(map_rect.y + map_rect.height * ry)
        r = pygame.Rect(0, 0, box_w, box_h)
        r.center = (cx, cy)
        rects[name] = r
        centers[name] = (cx, cy)

    for a, b in edges:
        if a in centers and b in centers:
            pygame.draw.line(screen, (105, 125, 145), centers[a], centers[b], 2)

    for name, r in rects.items():
        known = name in explored
        fill = (68, 78, 88) if not known else (30, 62, 86)
        border = (0, 0, 0) if not known else (170, 210, 235)
        pygame.draw.rect(screen, fill, r)
        pygame.draw.rect(screen, border, r, 2)
        if known:
            raw = name.replace(".json", "")
            if raw == "map_1":
                label = "map1"
            elif raw == "map_2":
                label = "map2"
            elif raw == "map_3":
                label = "map3"
            elif raw == "rogue":
                label = f"rogue L{int(getattr(game, 'rogue_layer', 0))}"
            else:
                label = raw
            # Name directly on map area (can overflow as requested).
            _draw_text_outline(screen, font, label, (235, 245, 255), (0, 0, 0), (r.x - 2, r.y - 18))
        else:
            _draw_text_outline(screen, font, "???", (180, 180, 180), (0, 0, 0), (r.x + 2, r.y - 18))

    if cur in rects:
        r = rects[cur]
        dot = pygame.Rect(0, 0, 8, 8)
        dot.center = r.center
        pygame.draw.rect(screen, (45, 155, 255), dot)
        pygame.draw.rect(screen, (220, 245, 255), dot, 1)

    # Compass + legend top-right
    lg_font = _get_font(20, bold=True)
    lg_x = panel.right - 170
    lg_y = panel.y + 20
    cx = lg_x + 58
    cy = lg_y + 36
    pygame.draw.circle(screen, (170, 210, 235), (cx, cy), 24, 2)
    pygame.draw.line(screen, (170, 210, 235), (cx, cy - 24), (cx, cy + 24), 2)
    pygame.draw.line(screen, (170, 210, 235), (cx - 24, cy), (cx + 24, cy), 2)
    _draw_text_outline(screen, lg_font, "N", (235, 235, 235), (0, 0, 0), (cx - 7, cy - 41))
    _draw_text_outline(screen, lg_font, "S", (235, 235, 235), (0, 0, 0), (cx - 7, cy + 24))
    _draw_text_outline(screen, lg_font, "W", (235, 235, 235), (0, 0, 0), (cx - 41, cy - 10))
    _draw_text_outline(screen, lg_font, "E", (235, 235, 235), (0, 0, 0), (cx + 25, cy - 10))

    leg_font = _get_font(18, bold=True)
    u = pygame.Rect(lg_x, lg_y + 82, 24, 18)
    pygame.draw.rect(screen, (68, 78, 88), u)
    pygame.draw.rect(screen, (0, 0, 0), u, 2)
    _draw_text_outline(screen, leg_font, tr(game.lang, "map.unexplored"), (220, 220, 220), (0, 0, 0), (u.right + 10, u.y - 2))
    c = pygame.Rect(lg_x, lg_y + 110, 24, 18)
    pygame.draw.rect(screen, (30, 62, 86), c)
    pygame.draw.rect(screen, (170, 210, 235), c, 2)
    b = pygame.Rect(0, 0, 8, 8)
    b.center = c.center
    pygame.draw.rect(screen, (45, 155, 255), b)
    _draw_text_outline(screen, leg_font, tr(game.lang, "map.current"), (220, 220, 220), (0, 0, 0), (c.right + 10, c.y - 2))
    screen.set_clip(old_clip)


def draw_dialog(game, screen):
    if game.ui_mode != "dialog" or not game.dialog_data or not game.dialog_node:
        return
    panel_h = screen.get_height() // 4
    bar_h = 48
    panel_bottom = screen.get_height() - bar_h
    panel = pygame.Rect(0, panel_bottom - panel_h, screen.get_width(), panel_h)
    pygame.draw.rect(screen, (30, 30, 40), panel)
    pygame.draw.rect(screen, (200, 200, 200), panel, 2)
    font = _get_font(16)
    font2 = _get_font(14)
    npc_id = game.active_npc or "npc"
    npc_name = npc_id
    node = game.dialog_data.get(game.dialog_node, {})
    text = node.get("text_zh", node.get("text", "")) if game.lang == "zh" else node.get("text", "")
    responses = game.get_dialog_responses(node)

    img_size = int(panel_h * 0.7)
    ent_def = mobs_data.get(npc_id, None)
    if ent_def is None:
        ent_def = npc_data.get(npc_id, {})
    img = _get_dialog_portrait(game, npc_id, ent_def, (img_size, img_size))
    img_x = panel.x + 12
    img_y = panel.y + 12
    if img:
        screen.blit(img, (img_x, img_y))
    else:
        pygame.draw.rect(screen, (80, 80, 90), (img_x, img_y, img_size, img_size))

    screen.blit(font.render(npc_name, True, (255, 255, 0)), (img_x + img_size + 12, panel.y + 8))

    text_y = panel.y + 32
    max_width = panel.width - img_size - 36
    lines = _wrap_text(font2, text, max_width)
    for line in lines:
        surf = font2.render(line, True, (230, 230, 230))
        screen.blit(surf, (img_x + img_size + 12, text_y))
        text_y += font2.get_height() + 4

    resp_y = panel.bottom - 20 - len(responses) * (font2.get_height() + 6)
    if resp_y < text_y + 8:
        resp_y = text_y + 8
    for i, resp in enumerate(responses):
        color = (255, 255, 0) if i == game.dialog_selected else (200, 200, 200)
        if resp.get("next") == "gift":
            rtext = tr(game.lang, "dialog.gift")
        else:
            rtext = resp.get("text_zh", resp.get("text", "")) if game.lang == "zh" else resp.get("text", "")
        surf = font2.render(rtext, True, color)
        rect = pygame.Rect(img_x + img_size + 8, resp_y - 2, panel.width - img_size - 32, font2.get_height() + 4)
        if i == game.dialog_selected:
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
        screen.blit(surf, (img_x + img_size + 12, resp_y))
        resp_y += font2.get_height() + 6


def draw_blackjack(game, screen):
    if getattr(game, "ui_mode", None) != "blackjack":
        return
    st = getattr(game, "blackjack_ui_state", {}) or {}
    player = st.get("player", {}) or {}
    dealer = st.get("dealer", {}) or {}
    narrative = st.get("narrative", {}) or {}
    finished = bool(st.get("finished", False))
    selected = int(getattr(game, "blackjack_ui_selected", 0))

    panel = pygame.Rect(screen.get_width() // 8, screen.get_height() // 8, screen.get_width() * 3 // 4, screen.get_height() * 3 // 4)
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 130))
    screen.blit(shade, (0, 0))
    pygame.draw.rect(screen, (12, 18, 30), panel, border_radius=10)
    pygame.draw.rect(screen, (180, 220, 255), panel, 2, border_radius=10)

    title_font = _get_font(24, bold=True)
    body_font = _get_font(17)
    small_font = _get_font(15)
    _draw_text_outline(screen, title_font, tr(game.lang, "blackjack.title"), (245, 245, 245), (0, 0, 0), (panel.x + 20, panel.y + 16), thickness=2)

    bet = int(st.get("bet", 0) or 0)
    payout = int(st.get("payout", 0) or 0)
    left_money = int(getattr(game, "money", 0))
    _draw_text_outline(screen, small_font, f"{tr(game.lang, 'blackjack.bet')}: {bet}", (210, 230, 245), (0, 0, 0), (panel.right - 180, panel.y + 22), thickness=2)
    _draw_text_outline(screen, small_font, f"{tr(game.lang, 'blackjack.payout')}: {payout}", (210, 230, 245), (0, 0, 0), (panel.right - 180, panel.y + 46), thickness=2)
    _draw_text_outline(screen, small_font, f"{tr(game.lang, 'blackjack.left_money')}: {left_money}", (210, 230, 245), (0, 0, 0), (panel.right - 180, panel.y + 70), thickness=2)

    y0 = panel.y + 78
    def _fmt_cards(cards):
        suit_map = {"♥": "H", "♦": "D", "♣": "C", "♠": "S", "?": "?"}
        out = []
        for card in cards or []:
            try:
                rank, suit = card
            except Exception:
                out.append(str(card))
                continue
            out.append(f"{rank}{suit_map.get(str(suit), str(suit)[:1] if str(suit) else '?')}")
        return ", ".join(out)

    dealer_cards_text = _fmt_cards(dealer.get("cards", []))
    if not finished and len(dealer.get("cards", [])) > 1 and dealer.get("cards", [None, None])[1] == ("?", "?"):
        dealer_cards_text = f"{dealer_cards_text}, [{tr(game.lang, 'blackjack.hidden')}]"
    _draw_text_outline(screen, body_font, f"{tr(game.lang, 'blackjack.dealer')}: {dealer_cards_text}", (235, 235, 235), (0, 0, 0), (panel.x + 22, y0), thickness=2)
    dealer_value = dealer.get("value", None)
    dealer_value_text = "?" if dealer_value is None else str(dealer_value)
    _draw_text_outline(screen, body_font, f"{tr(game.lang, 'blackjack.dealer_value')}: {dealer_value_text}", (200, 220, 240), (0, 0, 0), (panel.x + 22, y0 + 26), thickness=2)

    _draw_text_outline(screen, body_font, f"{tr(game.lang, 'blackjack.you')}: {_fmt_cards(player.get('cards', []))}", (245, 245, 220), (0, 0, 0), (panel.x + 22, y0 + 70), thickness=2)
    _draw_text_outline(screen, body_font, f"{tr(game.lang, 'blackjack.your_value')}: {player.get('value', 0)}", (245, 245, 220), (0, 0, 0), (panel.x + 22, y0 + 96), thickness=2)

    reaction = narrative.get("reaction", "")
    final_comment = narrative.get("final_comment", "")
    _draw_text_outline(screen, small_font, f"{tr(game.lang, 'blackjack.reaction')}: {reaction}", (200, 235, 220), (0, 0, 0), (panel.x + 22, y0 + 140), thickness=2)
    if finished:
        _draw_text_outline(screen, small_font, f"{tr(game.lang, 'blackjack.result')}: {st.get('result', '')}", (255, 226, 160), (0, 0, 0), (panel.x + 22, y0 + 170), thickness=2)
        _draw_text_outline(screen, small_font, f"{tr(game.lang, 'blackjack.comment')}: {final_comment}", (255, 226, 160), (0, 0, 0), (panel.x + 22, y0 + 196), thickness=2)

    options = (
        [tr(game.lang, "blackjack.hit"), tr(game.lang, "blackjack.stand"), tr(game.lang, "blackjack.leave")]
        if not finished
        else [tr(game.lang, "blackjack.again"), tr(game.lang, "blackjack.leave")]
    )
    oy = panel.bottom - 92
    ox = panel.x + 22
    for i, label in enumerate(options):
        rect = pygame.Rect(ox + i * 160, oy, 140, 36)
        _draw_readability_row(screen, rect, selected=(i == selected))
        color = (255, 247, 170) if i == selected else (230, 230, 230)
        _draw_text_outline(screen, body_font, label, color, (0, 0, 0), (rect.x + 18, rect.y + 8), thickness=2)
    _draw_text_outline(screen, small_font, tr(game.lang, "blackjack.hint"), (180, 205, 225), (0, 0, 0), (panel.x + 22, panel.bottom - 34), thickness=2)


def draw_blackjack_bet(game, screen):
    if getattr(game, "ui_mode", None) != "blackjack_bet":
        return
    panel = pygame.Rect(screen.get_width() // 6, screen.get_height() // 4, screen.get_width() * 2 // 3, screen.get_height() // 3)
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 130))
    screen.blit(shade, (0, 0))
    pygame.draw.rect(screen, (12, 18, 30), panel, border_radius=10)
    pygame.draw.rect(screen, (180, 220, 255), panel, 2, border_radius=10)
    title_font = _get_font(24, bold=True)
    body_font = _get_font(18)
    _draw_text_outline(screen, title_font, tr(game.lang, "blackjack.session_title"), (245, 245, 245), (0, 0, 0), (panel.x + 20, panel.y + 16), thickness=2)
    _draw_text_outline(screen, body_font, tr(game.lang, "blackjack.session_prompt"), (225, 235, 245), (0, 0, 0), (panel.x + 20, panel.y + 62), thickness=2)
    _draw_text_outline(screen, body_font, tr(game.lang, "blackjack.session_money", money=int(getattr(game, "money", 0))), (200, 220, 240), (0, 0, 0), (panel.x + 20, panel.y + 90), thickness=2)
    value = getattr(game, "blackjack_bet_input", "") or ""
    box = pygame.Rect(panel.x + 20, panel.y + 125, panel.width - 40, 42)
    _draw_readability_row(screen, box, selected=True)
    _draw_text_outline(screen, body_font, value if value else "_", (255, 247, 170), (0, 0, 0), (box.x + 10, box.y + 10), thickness=2)
    err = getattr(game, "blackjack_bet_error", "")
    if err == "invalid":
        _draw_text_outline(screen, body_font, tr(game.lang, "blackjack.session_err_invalid"), (255, 180, 180), (0, 0, 0), (panel.x + 20, panel.y + 176), thickness=2)
    elif err == "range":
        _draw_text_outline(screen, body_font, tr(game.lang, "blackjack.session_err_range"), (255, 180, 180), (0, 0, 0), (panel.x + 20, panel.y + 176), thickness=2)
    _draw_text_outline(screen, body_font, tr(game.lang, "blackjack.session_hint"), (180, 205, 225), (0, 0, 0), (panel.x + 20, panel.bottom - 34), thickness=2)


def draw_shop(game, screen):
    if game.ui_mode != "shop":
        return
    panel = pygame.Rect(screen.get_width() // 10, screen.get_height() // 10, screen.get_width() * 8 // 10, screen.get_height() * 8 // 10)
    pygame.draw.rect(screen, (30, 30, 40), panel)
    pygame.draw.rect(screen, (200, 200, 200), panel, 2)
    font = _get_font(16)
    font2 = _get_font(14)
    title = font.render(tr(game.lang, "shop.title"), True, (255, 255, 255))
    screen.blit(title, (panel.x + 12, panel.y + 12))
    money = font2.render(f"{tr(game.lang, 'label.robux')}: {game.money}", True, (200, 200, 200))
    screen.blit(money, (panel.right - money.get_width() - 12, panel.y + 14))
    cats = game.get_shop_categories() if hasattr(game, "get_shop_categories") else ["all"]
    cat_y = panel.y + 36
    cat_x = panel.x + 16
    for cat in cats:
        label = tr(game.lang, f"shop.cat.{cat}")
        if label == f"shop.cat.{cat}":
            label = cat
        surf = font2.render(label, True, (220, 220, 220))
        rect = pygame.Rect(cat_x - 6, cat_y - 2, surf.get_width() + 12, font2.get_height() + 6)
        pygame.draw.rect(screen, (180, 180, 180), rect, 1, border_radius=4)
        if cat == getattr(game, "shop_category", "all"):
            pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
        screen.blit(surf, (cat_x, cat_y))
        cat_x += surf.get_width() + 16

    y = panel.y + 62
    if not game.shop_items:
        empty = font2.render(tr(game.lang, "shop.empty"), True, (220, 220, 220))
        screen.blit(empty, (panel.x + 24, y))
    else:
        for i, item in enumerate(game.shop_items):
            color = (255, 255, 0) if i == game.shop_selected else (230, 230, 230)
            line = f"{_tr_item_name(game, item['name'])} - {item['price']} {tr(game.lang, 'label.robux')}"
            surf = font2.render(line, True, color)
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font2.get_height() + 4)
            if i == game.shop_selected:
                pygame.draw.rect(screen, _flicker_color(), rect, 2, border_radius=4)
            screen.blit(surf, (panel.x + 24, y))
            y += font2.get_height() + 6
    hint = font2.render(tr(game.lang, "shop.hint"), True, (200, 200, 200))
    screen.blit(hint, (panel.x + 20, panel.bottom - 24))


def draw_interact_picker(game, screen):
    if game.ui_mode != "interact_pick":
        return
    candidates = getattr(game, "interact_candidates", [])
    if not candidates:
        return
    font = _get_font(14)
    title_font = _get_font(15, bold=True)
    row_h = font.get_height() + 6
    box_w = 220
    box_h = 36 + len(candidates) * row_h + 8
    x = screen.get_width() - box_w - 12
    y = screen.get_height() - box_h - 60
    box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    box.fill((10, 14, 24, 220))
    screen.blit(box, (x, y))
    pygame.draw.rect(screen, (180, 220, 255), pygame.Rect(x, y, box_w, box_h), 2)
    _draw_text_outline(screen, title_font, "Choose NPC", (240, 240, 240), (0, 0, 0), (x + 10, y + 8), thickness=2)
    yy = y + 30
    selected = game.interact_selected % len(candidates)
    for i, eid in enumerate(candidates):
        rect = pygame.Rect(x + 8, yy - 1, box_w - 16, row_h)
        _draw_readability_row(screen, rect, selected=(i == selected))
        color = (255, 247, 170) if i == selected else (230, 230, 230)
        _draw_text_outline(screen, font, eid, color, (0, 0, 0), (x + 14, yy + 1), thickness=2)
        yy += row_h


def draw_death_menu(game, screen):
    if getattr(game, "ui_mode", None) != "death_menu":
        return
    dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    screen.blit(dim, (0, 0))

    font_title = _get_font(24, bold=True)
    font = _get_font(16)
    menu_w = min(680, screen.get_width() - 120)
    menu_h = 240
    panel = pygame.Rect((screen.get_width() - menu_w) // 2, (screen.get_height() - menu_h) // 2, menu_w, menu_h)
    pygame.draw.rect(screen, (12, 18, 30), panel)
    pygame.draw.rect(screen, (200, 220, 240), panel, 2)

    title = "You Died"
    ts = font_title.render(title, True, (255, 220, 220))
    screen.blit(ts, (panel.centerx - ts.get_width() // 2, panel.y + 20))

    if getattr(game, "death_no_save_notice", ""):
        msg = game.death_no_save_notice
        ms = font.render(msg, True, (230, 230, 230))
        screen.blit(ms, (panel.centerx - ms.get_width() // 2, panel.y + 96))
        ok_rect = pygame.Rect(panel.x + panel.width // 2 - 90, panel.bottom - 54, 180, 34)
        pygame.draw.rect(screen, (55, 55, 55), ok_rect, border_radius=4)
        pygame.draw.rect(screen, (165, 165, 165), ok_rect, 2, border_radius=4)
        _draw_text_outline(screen, font, "ok", (230, 230, 230), (0, 0, 0), (ok_rect.centerx - 10, ok_rect.y + 8), thickness=2)
        return

    options = [
        "revive, but lose 50% of your robux",
        "return to last save slot",
    ]
    row_h = 36
    y = panel.y + 96
    selected = max(0, min(1, int(getattr(game, "death_menu_selected", 0))))
    for i, text in enumerate(options):
        rect = pygame.Rect(panel.x + 24, y + i * (row_h + 10), panel.width - 48, row_h)
        _draw_readability_row(screen, rect, selected=(i == selected))
        color = (255, 247, 170) if i == selected else (230, 230, 230)
        _draw_text_outline(screen, font, _fit_text(font, text, rect.width - 14), color, (0, 0, 0), (rect.x + 8, rect.y + 8), thickness=2)


def draw_level_stat_choice(game, screen):
    if getattr(game, "ui_mode", None) != "level_stat_choice":
        return
    options = game.get_level_stat_options() if hasattr(game, "get_level_stat_options") else []
    if not options:
        return
    font = _get_font(20, bold=True)
    font2 = _get_font(18)
    box_w = min(760, screen.get_width() - 80)
    box_h = min(460, screen.get_height() - 100)
    box = pygame.Rect((screen.get_width() - box_w) // 2, (screen.get_height() - box_h) // 2, box_w, box_h)
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 150))
    screen.blit(shade, (0, 0))
    pygame.draw.rect(screen, (10, 24, 40), box, border_radius=10)
    pygame.draw.rect(screen, (180, 225, 255), box, 2, border_radius=10)
    title = tr(game.lang, "level_stat.title")
    sub = tr(game.lang, "level_stat.pending", count=getattr(game, "level_stat_pending", 0))
    _draw_text_outline(screen, font, title, (235, 245, 255), (0, 0, 0), (box.x + 20, box.y + 18), thickness=2)
    _draw_text_outline(screen, font2, sub, (190, 220, 245), (255, 255, 255), (box.x + 20, box.y + 50), thickness=2)
    y = box.y + 95
    selected = int(getattr(game, "level_stat_selected", 0)) % len(options)
    for i, op in enumerate(options):
        line = tr(game.lang, "level_stat.row", name=op.get("name", ""), value=op.get("value", 0))
        rect = pygame.Rect(box.x + 16, y - 2, box.width - 32, font2.get_height() + 10)
        _draw_readability_row(screen, rect, selected=(i == selected))
        color = (255, 247, 170) if i == selected else (230, 230, 230)
        _draw_text_outline(screen, font2, line, color, (0, 0, 0), (box.x + 24, y), thickness=2)
        y += font2.get_height() + 14
    hint = tr(game.lang, "level_stat.hint")
    _draw_text_outline(screen, font2, hint, (180, 205, 225), (255, 255, 255), (box.x + 20, box.bottom - 34), thickness=2)


def _wrap_text(font, text, max_width):
    words = text.split(' ')
    lines = []
    line = ''
    for word in words:
        test = (line + ' ' + word).strip()
        if font.size(test)[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw(game, screen):
    screen.fill((0, 0, 0))
    map_view_h = VIEWPORT
    map_view_w = VIEWPORT
    tile_h = TILE_SIZE
    tile_w = TILE_SIZE
    view_w_px = map_view_w * tile_w
    view_h_px = map_view_h * tile_h
    if hasattr(game, "get_player_draw_pos"):
        px, py = game.get_player_draw_pos()
    else:
        px, py = game.player.x, game.player.y
    cam_px = px * tile_w + tile_w / 2 - view_w_px / 2
    cam_py = py * tile_h + tile_h / 2 - view_h_px / 2
    max_cam_px = max(0, game.map.w * tile_w - view_w_px)
    max_cam_py = max(0, game.map.h * tile_h - view_h_px)
    cam_px = clamp(cam_px, 0, max_cam_px)
    cam_py = clamp(cam_py, 0, max_cam_py)
    left = int(cam_px // tile_w)
    top = int(cam_py // tile_h)
    offset_x = -(cam_px - left * tile_w)
    offset_y = -(cam_py - top * tile_h)
    portal_set = set()
    if getattr(game.map, "portals", None):
        for p in game.map.portals:
            portal_set.add((p.get("x"), p.get("y")))
    tiles_x = map_view_w + 2
    tiles_y = map_view_h + 2
    for y in range(tiles_y):
        for x in range(tiles_x):
            mx, my = left + x, top + y
            if 0 <= mx < game.map.w and 0 <= my < game.map.h:
                bt = game.map.get_block(mx, my)
                color = _tile_color_for_block(bt)
                tile_x = x * tile_w + offset_x
                tile_y = y * tile_h + offset_y
                pygame.draw.rect(screen, color, (tile_x, tile_y, tile_w, tile_h))
                if bt == "04":
                    # pulsating highlight for exit
                    t = pygame.time.get_ticks() / 1000.0
                    alpha = int(120 + 80 * (0.5 + 0.5 * math.sin(t * 2.0)))
                    overlay = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
                    overlay.fill((255, 230, 120, alpha))
                    screen.blit(overlay, (tile_x, tile_y))
                bt_img = blocktypes.get(bt, {}).get("image")
                if bt_img:
                    size = int(tile_w * 0.9), int(tile_h * 0.9)
                    img = _load_image(bt_img, size)
                    if img:
                        ox = tile_x + (tile_w - size[0]) // 2
                        oy = tile_y + (tile_h - size[1]) // 2
                        screen.blit(img, (ox, oy))
                if (mx, my) in portal_set:
                    overlay = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
                    overlay.fill((180, 60, 220, 160))
                    screen.blit(overlay, (tile_x, tile_y))
    view_rect = pygame.Rect(cam_px, cam_py, view_w_px, view_h_px)
    for ent in game.entities:
        ent_size = getattr(ent, "size", 1)
        ent_px = ent.x * tile_w
        ent_py = ent.y * tile_h
        ent_rect = pygame.Rect(ent_px, ent_py, ent_size * tile_w, ent_size * tile_h)
        if not ent_rect.colliderect(view_rect):
            continue
        if ent.eid == 'player':
            ex, ey = px, py
        else:
            ex, ey = ent.x, ent.y
        ent_size = getattr(ent, "size", 1)
        cell_w = tile_w * ent_size
        cell_h = tile_h * ent_size
        sprite_w = max(8, int(cell_w * 0.84))
        sprite_h = max(8, int(cell_h * 0.84))
        draw_x = ex * tile_w - cam_px + (cell_w - sprite_w) / 2
        draw_y = ey * tile_h - cam_py + (cell_h - sprite_h) / 2
        size = sprite_w, sprite_h
        shadow_w = max(8, int(size[0] * 0.72))
        shadow_h = max(6, int(size[1] * 0.18))
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 70), shadow.get_rect())
        shadow_x = int(draw_x + (size[0] - shadow_w) // 2)
        shadow_y = int(draw_y + size[1] - shadow_h // 2)
        screen.blit(shadow, (shadow_x, shadow_y))
        if ent.eid == "player":
            ent_def = {"image": player_data.get("image")}
        else:
            ent_def = mobs_data.get(ent.eid, None)
            if ent_def is None:
                ent_def = npc_data.get(ent.eid, {})
        img = _get_entity_render_image(game, ent, ent_def, size)
        if img:
            screen.blit(img, (int(draw_x), int(draw_y)))
        else:
            if ent.eid == 'player':
                color = (0, 0, 255)
            elif ent_def.get('ai_type') == 'friendly':
                color = (255, 200, 0)
            else:
                color = (255, 0, 0)
            pygame.draw.rect(screen, color, (int(draw_x) + 4, int(draw_y) + 4, size[0] - 8, size[1] - 8))
        is_hostile = ent.eid != "player" and ent_def.get("ai_type") == "hostile"
        tier = game.get_env_tier() if hasattr(game, "get_env_tier") else 0
        if is_hostile and tier > 0:
            star_size = max(4, int(min(size[0], size[1]) / 8))
            gap = max(2, star_size // 3)
            base_x = int(draw_x + size[0] - star_size - 2)
            base_y = int(draw_y + size[1] - star_size - 2)
            per_row = 3
            for si in range(tier):
                row = si // per_row
                col = si % per_row
                cx = base_x - col * (star_size + gap) + star_size // 2
                cy = base_y - row * (star_size + gap) + star_size // 2
                _draw_star(screen, cx, cy, star_size // 2, (248, 222, 90), (255, 245, 180))

    _draw_spell_effects(game, screen, cam_px, cam_py, tile_w, tile_h)

    minimap_rect = _draw_minimap(game, screen, cam_px, cam_py, view_w_px, view_h_px)
    tracking_lines = game.get_tracking_summary_lines() if hasattr(game, "get_tracking_summary_lines") else []
    if minimap_rect and tracking_lines:
        tfont = _get_font(13)
        line_h = tfont.get_height() + 4
        max_w = 0
        for line in tracking_lines:
            max_w = max(max_w, tfont.size(line)[0])
        box_w = max_w + 16
        box_h = len(tracking_lines) * line_h + 10
        box_x = minimap_rect.x
        box_y = minimap_rect.bottom + 8
        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill((10, 16, 28, 210))
        screen.blit(box, (box_x, box_y))
        pygame.draw.rect(screen, (180, 210, 235), pygame.Rect(box_x, box_y, box_w, box_h), 1)
        yy = box_y + 5
        for line in tracking_lines:
            _draw_text_outline(screen, tfont, line, (230, 230, 230), (0, 0, 0), (box_x + 8, yy), thickness=1)
            yy += line_h

    if getattr(game, "transition_active", False):
        t = game.transition_timer / max(game.transition_duration, 0.001)
        if t <= 0.5:
            alpha = int(255 * (t * 2))
        else:
            alpha = int(255 * (1 - (t - 0.5) * 2))
        s = pygame.Surface(screen.get_size())
        s.set_alpha(max(0, min(255, alpha)))
        s.fill((0, 0, 0))
        screen.blit(s, (0, 0))
    elif game.blackout:
        s = pygame.Surface(screen.get_size())
        s.set_alpha(game.black_alpha)
        s.fill((0, 0, 0))
        screen.blit(s, (0, 0))

    draw_tutorial_panel(game, screen)
    draw_messages(game, screen)
    draw_blackjack_bet(game, screen)
    draw_dialog(game, screen)
    draw_blackjack(game, screen)
    draw_shop(game, screen)
    draw_interact_picker(game, screen)
    draw_death_menu(game, screen)
    draw_level_stat_choice(game, screen)

    if getattr(game, "banner", None):
        banner = game.banner
        now = time.time()
        age = now - banner.get("created", now)
        dur = banner.get("duration", 3.0)
        if age <= dur:
            alpha = int(255 * (1 - age / dur))
            text = banner.get("text", "")
            font = _get_font(20, bold=True)
            surf = font.render(text, True, (255, 255, 255))
            box_w = surf.get_width() + 40
            box_h = surf.get_height() + 20
            box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            box.fill((18, 60, 92, min(200, alpha)))
            x = screen.get_width() // 2 - box_w // 2
            y = screen.get_height() // 2 - box_h // 2
            screen.blit(box, (x, y))
            surf.set_alpha(alpha)
            screen.blit(surf, (x + 20, y + 10))
        else:
            game.banner = None

    if getattr(game, "map", None) is not None and game.map.name == "rogue":
        # mission bar top-right
        total = 1 if game.rogue_is_boss else getattr(game, "rogue_cfg", {}).get("mob_limit_normal", 10)
        left = game.count_hostile_mobs()
        text = f"mob left: {left}/{total}"
        font = _get_font(14)
        surf = font.render(text, True, (255, 255, 255))
        box_w = surf.get_width() + 20
        box_h = surf.get_height() + 10
        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill((10, 12, 16, 200))
        x = screen.get_width() - box_w - 12
        y = 12
        screen.blit(box, (x, y))
        screen.blit(surf, (x + 10, y + 5))
