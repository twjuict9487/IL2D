import os
from ..support.utils import load_json, BLOCKTYPE_FILE, MOBS_FILE, PLAYER_FILE, NPC_FILE

blocktypes = load_json(BLOCKTYPE_FILE)
mobs_data = load_json(MOBS_FILE)
player_data = load_json(PLAYER_FILE)
npc_data = load_json(NPC_FILE)


def _normalize_grid(raw_grid):
    # Support both:
    # 1) 2D list: [["01","02"], ...]
    # 2) readable row strings: ["01 02 03", ...]
    grid = []
    for row in raw_grid:
        if isinstance(row, str):
            toks = [t for t in row.replace(",", " ").split() if t]
            grid.append(toks)
        else:
            grid.append(list(row))
    return grid


def _build_compact_grid(layout):
    if not isinstance(layout, dict):
        raise ValueError("compact_layout must be an object")
    width = max(1, int(layout.get("width", 1)))
    height = max(1, int(layout.get("height", 1)))
    base = str(layout.get("base", "01"))
    boundary = str(layout.get("boundary", "02"))
    grid = [[base for _ in range(width)] for _ in range(height)]
    if bool(layout.get("border", True)):
        for x in range(width):
            grid[0][x] = boundary
            grid[height - 1][x] = boundary
        for y in range(height):
            grid[y][0] = boundary
            grid[y][width - 1] = boundary
    for rect in layout.get("rects", []) or []:
        if not isinstance(rect, dict):
            continue
        tile = str(rect.get("tile", boundary))
        try:
            x1 = max(0, int(rect.get("x", 0)))
            y1 = max(0, int(rect.get("y", 0)))
            x2 = min(width, x1 + max(1, int(rect.get("w", 1))))
            y2 = min(height, y1 + max(1, int(rect.get("h", 1))))
        except (TypeError, ValueError):
            continue
        for y in range(y1, y2):
            for x in range(x1, x2):
                grid[y][x] = tile
    return grid


def _grid_from_data(data):
    raw_grid = data.get("grid")
    if isinstance(raw_grid, list) and raw_grid:
        return _normalize_grid(raw_grid)
    if data.get("compact_layout"):
        return _build_compact_grid(data.get("compact_layout"))
    raise ValueError("map requires grid or compact_layout")


def _validate_grid(grid, source_name):
    if not isinstance(grid, list) or not grid:
        raise ValueError(f"map segment {source_name!r} has no grid rows")
    width = len(grid[0])
    if width <= 0:
        raise ValueError(f"map segment {source_name!r} has an empty first row")
    for row_index, row in enumerate(grid):
        if len(row) != width:
            raise ValueError(
                f"map segment {source_name!r} row {row_index} has width {len(row)}; "
                f"expected {width}"
            )
    return width, len(grid)


def _grid_with_appended_segments(mapfile, data):
    first_name = os.path.basename(mapfile)
    grid = _grid_from_data(data)
    width, height = _validate_grid(grid, first_name)
    segment_filenames = [first_name]
    segment_boundaries = [width]
    base_dir = os.path.realpath(os.path.dirname(mapfile))

    raw_segments = data.get("append_segments", []) or []
    if not isinstance(raw_segments, list):
        raise ValueError("append_segments must be a list of JSON filenames")
    for raw_name in raw_segments:
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("append_segments entries must be non-empty filenames")
        segment_name = raw_name.strip()
        segment_path = os.path.realpath(os.path.join(base_dir, segment_name))
        if os.path.commonpath((base_dir, segment_path)) != base_dir:
            raise ValueError(f"map segment escapes map directory: {segment_name!r}")
        segment_data = load_json(segment_path)
        if segment_data.get("append_segments"):
            raise ValueError(
                f"nested append_segments is not supported in {segment_name!r}"
            )
        if segment_data.get("portals"):
            raise ValueError(
                f"appended map segment {segment_name!r} must not define portals"
            )
        segment_grid = _grid_from_data(segment_data)
        segment_width, segment_height = _validate_grid(segment_grid, segment_name)
        if segment_height != height:
            raise ValueError(
                f"map segment {segment_name!r} has height {segment_height}; "
                f"expected {height}"
            )
        declared = segment_data.get("segment", {})
        if isinstance(declared, dict) and declared.get("width") is not None:
            if int(declared["width"]) != segment_width:
                raise ValueError(
                    f"map segment {segment_name!r} declares width {declared['width']}; "
                    f"grid width is {segment_width}"
                )
        for row_index in range(height):
            grid[row_index].extend(segment_grid[row_index])
        segment_filenames.append(os.path.basename(segment_name))
        segment_boundaries.append(segment_boundaries[-1] + segment_width)

    return grid, segment_filenames, segment_boundaries


def _normalize_npc_layout(raw_layout):
    layout = {}
    if not isinstance(raw_layout, dict):
        return layout
    for npc_id, spot in raw_layout.items():
        if not isinstance(npc_id, str):
            continue
        if not isinstance(spot, (list, tuple)) or len(spot) < 2:
            continue
        try:
            layout[npc_id] = (int(spot[0]), int(spot[1]))
        except Exception:
            continue
    return layout


def _normalize_campfires(raw_campfires):
    from ..gameplay.campfires import normalize_definitions

    return normalize_definitions(raw_campfires)


class GameMap:
    def __init__(self, mapfile):
        data = load_json(mapfile)
        self.name = os.path.basename(mapfile)
        (
            self.grid,
            self.segment_filenames,
            self.segment_boundaries,
        ) = _grid_with_appended_segments(mapfile, data)
        self.region = str(data.get("region", "") or "").strip()
        self.music_override = (
            data.get("music_override") or data.get("music") or data.get("bgm")
        )
        self.spawn = tuple(data["spawn"])
        self.portals = data.get("portals", [])
        self.mission_targets = data.get("mission_targets", [])
        self.campfires = _normalize_campfires(data.get("campfires", []))
        self.mob_spawn_pool = data.get("mob_spawn_pool", None)
        self.mob_spawn_classes = data.get("mob_spawn_classes", None)
        self.mob_spawn_rank = data.get("mob_spawn_rank", None)
        self.npc_layout = _normalize_npc_layout(data.get("npc_layout", {}))
        self.mob_limit = data.get("mob_limit", 4)
        self.spawn_interval = data.get("spawn_interval")
        self.chase_transition = data.get("chase_transition")
        self.world_hidden = bool(data.get("world_hidden", False))
        self.h = len(self.grid)
        self.w = len(self.grid[0])
        self.segment_debug = {
            "filenames": list(self.segment_filenames),
            "boundaries": list(self.segment_boundaries),
        }

    @classmethod
    def from_data(cls, name, data):
        obj = cls.__new__(cls)
        obj.name = name
        obj.grid = _grid_from_data(data)
        width, _height = _validate_grid(obj.grid, name)
        if data.get("append_segments"):
            raise ValueError("GameMap.from_data cannot resolve append_segments")
        obj.segment_filenames = [os.path.basename(name)]
        obj.segment_boundaries = [width]
        obj.region = str(data.get("region", "") or "").strip()
        obj.music_override = (
            data.get("music_override") or data.get("music") or data.get("bgm")
        )
        obj.spawn = tuple(data["spawn"])
        obj.portals = data.get("portals", [])
        obj.mission_targets = data.get("mission_targets", [])
        obj.campfires = _normalize_campfires(data.get("campfires", []))
        obj.mob_spawn_pool = data.get("mob_spawn_pool", None)
        obj.mob_spawn_classes = data.get("mob_spawn_classes", None)
        obj.mob_spawn_rank = data.get("mob_spawn_rank", None)
        obj.npc_layout = _normalize_npc_layout(data.get("npc_layout", {}))
        obj.mob_limit = data.get("mob_limit", 4)
        obj.spawn_interval = data.get("spawn_interval")
        obj.chase_transition = data.get("chase_transition")
        obj.world_hidden = bool(data.get("world_hidden", False))
        obj.h = len(obj.grid)
        obj.w = len(obj.grid[0])
        obj.segment_debug = {
            "filenames": list(obj.segment_filenames),
            "boundaries": list(obj.segment_boundaries),
        }
        return obj

    def is_walkable(self, x, y):
        if 0 <= y < self.h and 0 <= x < self.w:
            bt = self.grid[y][x]
            return blocktypes[bt]["walkable"]
        return False

    def get_block(self, x, y):
        if 0 <= y < self.h and 0 <= x < self.w:
            return self.grid[y][x]
        return None

    def get_mission_target(self, x, y):
        targets = getattr(self, "mission_targets", []) or []
        for target in targets:
            if not isinstance(target, dict):
                continue
            try:
                tx = int(target.get("x", -999))
                ty = int(target.get("y", -999))
            except Exception:
                continue
            if tx == int(x) and ty == int(y):
                return target
        return None
