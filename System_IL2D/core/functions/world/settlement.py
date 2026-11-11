import os

from ..support.utils import load_json


def apply_progression(mapfile, data, completed_story_missions):
    filename = data["settlement"]["progression_file"]
    progression = load_json(os.path.join(os.path.dirname(mapfile), filename))
    completed = set(completed_story_missions)
    grid = [row.split() for row in data["grid"]]
    data["grid"] = grid
    for step in progression["stages"]:
        if step["completed_mission"] not in completed:
            break
        for x, y, row in step["tile_runs"]:
            tiles = row.split()
            if not (0 <= y < len(grid) and 0 <= x <= len(grid[y]) - len(tiles)):
                raise ValueError(f"Settlement tile run outside map: {x}, {y}")
            grid[y][x:x + len(tiles)] = tiles
        data.setdefault("mission_targets", []).extend(step.get("add_mission_targets", []))
        data.setdefault("roofs", []).extend(step.get("add_roofs", []))
        data.update(step.get("map_settings", {}))
        data["settlement_stage"] = step["stage"]


def contains(bounds, x, y):
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def roof_tile(bounds, x, y):
    left, top, right, bottom = bounds
    edge = "west" if x == left else "east" if x == right else "middle"
    ridge = (top + bottom) // 2
    if y == top:
        slope = "north_eave"
    elif y == bottom:
        slope = "south_eave"
    elif y == ridge:
        slope = "ridge"
    else:
        slope = "north" if y < ridge else "south"
    return f"{slope}_{edge}"
