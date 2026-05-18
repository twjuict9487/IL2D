from core.functions.models.entity import Entity
from core.functions.world.map import npc_data


# 確保 Shu 在指定地圖存在，並固定在對應座標。
def ensure_shu(game):
    if getattr(game, "map", None) is None:
        return
    map_name = game.map.name
    if map_name not in ("map_1.json", "map_2.json", "farm_01.json"):
        return
    ent = next((e for e in game.entities if e.eid == "shu"), None)
    if ent is None:
        data = npc_data.get("shu", {})
        ent = Entity(
            "shu",
            7,
            8,
            int(data.get("hp", 1)),
            int(data.get("mp", 0)),
            int(data.get("attack", 0)),
            int(data.get("defence", 0)),
            data.get("ai_type", "friendly"),
            bool(data.get("immortal", False)),
        )
        game._ensure_entity_combat_profile(ent)
        game.entities.append(ent)
    if map_name == "map_1.json":
        ent.x, ent.y = 7, 8
    elif map_name == "map_2.json":
        ent.x, ent.y = 14, 27
    elif map_name == "farm_01.json":
        ent.x, ent.y = 3, 14
