import contextlib
import io
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame

from System_IL2D.core.functions.rendering import draw
from System_IL2D.core.functions.world.map import GameMap, blocktypes


def _first_tileset_tile():
    for code, meta in blocktypes.items():
        if isinstance(meta, dict) and meta.get("tileset_json") and meta.get("tileset_ref"):
            return code, meta
    raise AssertionError("no tileset-backed tile definitions found")


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    code, meta = _first_tileset_tile()
    tileset_json = meta["tileset_json"]
    tileset_ref = meta["tileset_ref"]
    size = (24, 24)

    draw._TILESET_CACHE.clear()
    draw._REPORTED_BAD_TILE_ROTATIONS.clear()

    base = draw._c(tileset_json, tileset_ref, size)
    assert base is not None, f"tile {code} did not load"
    assert draw._c(tileset_json, tileset_ref, size, 0) is base

    rotated = {}
    for angle in (0, 90, 180, 270):
        surf = draw._c(tileset_json, tileset_ref, size, angle)
        assert surf is not None, f"rotation {angle} did not load"
        assert surf.get_size() == size
        rotated[angle] = surf

    assert rotated[90] is draw._c(tileset_json, tileset_ref, size, 90)
    assert rotated[0] is not rotated[90]
    assert rotated[90] is not rotated[180]
    assert rotated[180] is not rotated[270]

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        invalid = draw._c(tileset_json, tileset_ref, size, 45)
    assert invalid is rotated[0]
    assert "invalid tile rotation" in out.getvalue()
    assert draw._c(tileset_json, tileset_ref, size, 90.5) is rotated[0]

    map_dir = os.path.join(ROOT, "System_IL2D", "core", "Pre_coded_data", "map")
    for name in ("map_1.json", "ritc.json"):
        gm = GameMap(os.path.join(map_dir, name))
        assert gm.w > 0 and gm.h > 0, f"{name} failed to load"

    pygame.quit()
    print("ok tile rotation smoke")


if __name__ == "__main__":
    main()
