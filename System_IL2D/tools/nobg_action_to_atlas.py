import argparse
import json
import math
from pathlib import Path


def _load_png(path):
    try:
        from PIL import Image  # type: ignore
        return ("pil", Image.open(path).convert("RGBA"))
    except Exception:
        pass
    try:
        import pygame  # type: ignore
        if not pygame.get_init():
            pygame.init()
        img = pygame.image.load(str(path)).convert_alpha()
        return ("pygame", img)
    except Exception as e:
        raise RuntimeError(f"Cannot load PNG '{path}'. Install Pillow or pygame. ({e})")


def _new_canvas(width, height, backend):
    if backend == "pil":
        from PIL import Image  # type: ignore
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))
    import pygame  # type: ignore
    surf = pygame.Surface((width, height), flags=pygame.SRCALPHA, depth=32)
    surf.fill((0, 0, 0, 0))
    return surf


def _img_size(img, backend):
    if backend == "pil":
        return img.size
    return img.get_width(), img.get_height()


def _paste(canvas, img, x, y, backend):
    if backend == "pil":
        canvas.paste(img, (x, y), img)
        return
    canvas.blit(img, (x, y))


def _save_png(canvas, out_path, backend, compress_level=1):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if backend == "pil":
        canvas.save(str(out_path), "PNG", compress_level=int(compress_level), optimize=False)
        return
    import pygame  # type: ignore
    pygame.image.save(canvas, str(out_path))


def _collect_folders(clips_dir, include):
    clips_dir = Path(clips_dir)
    if include:
        return [clips_dir / name for name in include]
    return [p for p in clips_dir.iterdir() if p.is_dir() and p.name.startswith("nobg_")]


def _sorted_frames(folder):
    folder = Path(folder)
    frames = sorted(folder.glob("*.png"))
    # Keep predictable order for frame_0001 style names.
    return frames


def _grid_cols(count):
    return max(1, int(math.ceil(math.sqrt(count))))


def _pack_chunk(folder_name, frames, loaded, fw, fh, out_dir, fps, backend, chunk_idx, compress_level):
    cols = _grid_cols(len(loaded))
    rows = int(math.ceil(len(loaded) / cols))
    atlas_w = cols * fw
    atlas_h = rows * fh
    canvas = _new_canvas(atlas_w, atlas_h, backend)

    meta_frames = []
    for i, (fp, img) in enumerate(zip(frames, loaded)):
        x = (i % cols) * fw
        y = (i // cols) * fh
        _paste(canvas, img, x, y, backend)
        meta_frames.append(
            {
                "index": i,
                "name": fp.name,
                "x": x,
                "y": y,
                "w": fw,
                "h": fh,
                "duration": 1,
            }
        )

    suffix = f"_p{chunk_idx:02d}" if chunk_idx > 1 else ""
    atlas_name = f"{folder_name}_atlas{suffix}.png"
    json_name = f"{folder_name}_atlas{suffix}.json"
    atlas_path = out_dir / atlas_name
    json_path = out_dir / json_name
    _save_png(canvas, atlas_path, backend, compress_level=compress_level)

    meta = {
        "version": 1,
        "animation": folder_name,
        "atlas": atlas_name,
        "frame_size": [fw, fh],
        "atlas_size": [atlas_w, atlas_h],
        "fps": int(fps),
        "loop": True,
        "frames": meta_frames,
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "atlas": str(atlas_path),
        "json": str(json_path),
        "frames": len(frames),
        "size": f"{atlas_w}x{atlas_h}",
    }


def pack_folder(folder, out_dir, fps, max_frames_per_atlas=0, compress_level=1):
    folder = Path(folder)
    out_dir = Path(out_dir)
    frames = _sorted_frames(folder)
    if not frames:
        return None

    first_backend, first_img = _load_png(frames[0])
    fw, fh = _img_size(first_img, first_backend)
    backend = first_backend

    loaded = [first_img]
    for fp in frames[1:]:
        b, img = _load_png(fp)
        if b != backend:
            raise RuntimeError(f"Mixed backend load state in {folder.name}.")
        w, h = _img_size(img, backend)
        if (w, h) != (fw, fh):
            raise ValueError(
                f"Frame size mismatch in {folder.name}: {fp.name} is {w}x{h}, expected {fw}x{fh}"
            )
        loaded.append(img)

    chunk_size = int(max_frames_per_atlas) if int(max_frames_per_atlas) > 0 else len(frames)
    pages = []
    chunk_idx = 1
    for start in range(0, len(frames), chunk_size):
        end = min(len(frames), start + chunk_size)
        page = _pack_chunk(
            folder.name,
            frames[start:end],
            loaded[start:end],
            fw,
            fh,
            out_dir,
            fps,
            backend,
            chunk_idx,
            compress_level,
        )
        pages.append(page)
        chunk_idx += 1
    return {
        "folder": folder.name,
        "frames": len(frames),
        "pages": pages,
    }


def main():
    parser = argparse.ArgumentParser(description="Pack nobg action frames into atlas PNG + JSON.")
    parser.add_argument(
        "--clips-dir",
        default="System_IL2D/clips",
        help="Root clips directory containing nobg_* folders.",
    )
    parser.add_argument(
        "--out-dir",
        default="System_IL2D/clips/atlas",
        help="Output directory for atlas png/json.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=12,
        help="Default fps written into output json.",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        default=None,
        help="Optional folder names to include, e.g. nobg_wisadel_walk nobg_wisadel_attack",
    )
    parser.add_argument(
        "--max-frames-per-atlas",
        type=int,
        default=0,
        help="Split one action into multiple atlas pages when frame count is high (0 = no split).",
    )
    parser.add_argument(
        "--compress-level",
        type=int,
        default=1,
        help="PNG compress level 0-9 (lower is faster, bigger file).",
    )
    args = parser.parse_args()

    clips_dir = Path(args.clips_dir)
    out_dir = Path(args.out_dir)
    if not clips_dir.exists():
        raise FileNotFoundError(f"clips dir not found: {clips_dir}")

    folders = _collect_folders(clips_dir, args.include)
    if not folders:
        print("No nobg folders found.")
        return

    ok = 0
    fail = 0
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            print(f"[skip] {folder} is not a folder")
            continue
        try:
            result = pack_folder(
                folder,
                out_dir,
                args.fps,
                max_frames_per_atlas=args.max_frames_per_atlas,
                compress_level=args.compress_level,
            )
            if result is None:
                print(f"[skip] {folder.name}: no png frames")
                continue
            ok += 1
            pages = result.get("pages", [])
            page_desc = ", ".join(
                f"{Path(p['atlas']).name}({p['frames']}f,{p['size']})" for p in pages
            )
            print(
                f"[ok] {result['folder']} -> frames={result['frames']}, pages={len(pages)}: {page_desc}"
            )
        except Exception as e:
            fail += 1
            print(f"[fail] {folder.name}: {e}")

    print(f"done. success={ok}, failed={fail}")


if __name__ == "__main__":
    main()
