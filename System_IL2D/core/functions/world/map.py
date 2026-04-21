
import os
from ..support.utils import load_json, MAP_DIR, MOB_DIR, PLAYER_FILE, NPC_FILE

blocktypes = load_json(os.path.join(MAP_DIR, 'blocktype.json'))
mobs_data = load_json(os.path.join(MOB_DIR, 'mobs.json'))
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

class GameMap:
    def __init__(self, mapfile):
        data = load_json(mapfile)
        self.name = os.path.basename(mapfile)
        self.grid = _normalize_grid(data['grid'])
        self.spawn = tuple(data['spawn'])
        self.portals = data.get('portals', [])
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
