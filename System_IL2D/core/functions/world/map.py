
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

class GameMap:
    def __init__(self, mapfile):
        data = load_json(mapfile)
        self.name = os.path.basename(mapfile)
        self.grid = _normalize_grid(data['grid'])
        self.spawn = tuple(data['spawn'])
        self.portals = data.get('portals', [])
        self.mission_targets = data.get('mission_targets', [])
        self.npc_layout = _normalize_npc_layout(data.get('npc_layout', {}))
        self.mob_limit = data.get('mob_limit', 4)
        self.spawn_interval = data.get('spawn_interval')
        self.h = len(self.grid)
        self.w = len(self.grid[0])

    @classmethod
    def from_data(cls, name, data):
        obj = cls.__new__(cls)
        obj.name = name
        obj.grid = _normalize_grid(data['grid'])
        obj.spawn = tuple(data['spawn'])
        obj.portals = data.get('portals', [])
        obj.mission_targets = data.get('mission_targets', [])
        obj.npc_layout = _normalize_npc_layout(data.get('npc_layout', {}))
        obj.mob_limit = data.get('mob_limit', 4)
        obj.spawn_interval = data.get('spawn_interval')
        obj.h = len(obj.grid)
        obj.w = len(obj.grid[0])
        return obj

    def is_walkable(self, x, y):
        if 0 <= y < self.h and 0 <= x < self.w:
            bt = self.grid[y][x]
            return blocktypes[bt]['walkable']
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
