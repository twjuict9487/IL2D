
import os
from .utils import load_json, MAP_DIR, MOB_DIR, PLAYER_FILE, NPC_FILE

blocktypes = load_json(os.path.join(MAP_DIR, 'blocktype.json'))
mobs_data = load_json(os.path.join(MOB_DIR, 'mobs.json'))
player_data = load_json(PLAYER_FILE)
npc_data = load_json(NPC_FILE)

class GameMap:
    def __init__(self, mapfile):
        data = load_json(mapfile)
        self.name = os.path.basename(mapfile)
        self.grid = data['grid']
        self.spawn = tuple(data['spawn'])
        self.portals = data.get('portals', [])
        self.mob_limit = data.get('mob_limit', 4)
        self.h = len(self.grid)
        self.w = len(self.grid[0])

    def is_walkable(self, x, y):
        if 0 <= y < self.h and 0 <= x < self.w:
            bt = self.grid[y][x]
            return blocktypes[bt]['walkable']
        return False

    def get_block(self, x, y):
        if 0 <= y < self.h and 0 <= x < self.w:
            return self.grid[y][x]
        return None
