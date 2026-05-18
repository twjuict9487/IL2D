import json
import os

from core.functions.support.utils import SAVE_DIR

from .constants import MOD_KEY


# 回傳 farmer_mod 資料夾絕對路徑。
def mod_dir():
    return os.path.dirname(os.path.dirname(__file__))


# 回傳農場地圖檔路徑。
def farm_map_path():
    return os.path.join(mod_dir(), "maps", "farm_01.json")


# 讀取農場設定檔（種子價格、土地座標等）。
def load_farm_cfg():
    path = os.path.join(mod_dir(), "farm_data.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# 取得目前遊戲存檔槽位，用於分槽保存 mod 狀態。
def slot_key(game):
    return int(getattr(game, "last_save_slot", 0) or 0)


# 根據槽位組出 mod 存檔路徑。
def save_path(game):
    return os.path.join(SAVE_DIR, f"mod_farm_slot_{slot_key(game)}.json")


# 建立 farmer mod 的預設資料狀態。
def default_state(_cfg):
    return {
        "owned_land": 0,
        "seeds": {"rice": 0, "wheat": 0},
        "crops": {"rice": 0, "wheat": 0},
        "planted": {},
        "panel_index": 0,
        "prev_map_name": None,
        "prev_pos": None,
    }


# 從 ctx 讀取（或初始化）mod 共享狀態容器。
def get_state(ctx):
    return ctx.setdefault(MOD_KEY, {})


# 取得 runtime 狀態，並確保 cfg/data 已初始化。
def farm_runtime(ctx):
    state = get_state(ctx)
    if "cfg" not in state:
        state["cfg"] = load_farm_cfg()
    if "data" not in state:
        state["data"] = default_state(state["cfg"])
    return state


# 從檔案載入當前槽位的 mod 資料到 runtime。
def load_state(game, ctx):
    state = farm_runtime(ctx)
    path = save_path(game)
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            state["data"].update(data)
    except Exception:
        pass


# 將 runtime 的 mod 資料寫入當前槽位檔案。
def save_state(game, ctx):
    os.makedirs(SAVE_DIR, exist_ok=True)
    state = farm_runtime(ctx)
    path = save_path(game)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state["data"], f, ensure_ascii=False, indent=2)


# 把 farmer mod 存檔掛到遊戲主存檔流程（ESC 存檔時才落盤）。
def attach_save_hook(game, ctx):
    if hasattr(game, "_farm_mod_original_save_game"):
        return
    game._farm_mod_original_save_game = game.save_game

    def _wrapped_save_game():
        game._farm_mod_original_save_game()
        if getattr(game, "last_saved", False):
            save_state(game, ctx)

    game.save_game = _wrapped_save_game
