# Project: IL2D

IL2D 是一個 2D 俯視角 RPG 原型，主打：探索、戰鬥、NPC 對話、商店、裝備、Rogue 分層地圖與資料驅動開發流程。

## 目前版本重點
- 主地圖：`map_1`、`map_2`、`map_3`（固定地圖）
- Rogue 地城：程序生成、分層推進、Boss 層規則
- 戰鬥系統：HP/MP、攻擊、防禦（含高防反傷邏輯）
- NPC 系統：對話樹、商店、任務、關係值
- 隊伍系統：可解鎖隊友（如 Monst3r / Wisadel）
- Hotbar v1：item/magic 雙快捷欄、`1~0` 快速施放
- 多存檔槽：可續關載入進度
- 中英語系：`i18n.json` 管理

## 專案結構
```text
main.py
System_IL2D/
  core/
    system_core.py
    functions/
      gameplay/
      rendering/
      world/
      support/
      models/
    Pre_coded_data/
      game_data/
      map/
      mob_related/
      npc_related/
  clips/
  saves/
```

## 執行方式
```powershell
python main.py
```

## 預設操作
- `W/A/S/D`：移動
- `E`：互動
- `ESC`：開關遊戲內選單
- `I`：切換到 item hotbar
- `O`：切換到 magic hotbar
- `1~0`：觸發目前啟用的 hotbar 槽位

## ESC 選單
- `item`：道具使用
- `hotbar`：快捷欄配置（類型 → 槽位 → 項目）
- `equipments`：裝備管理
- `team`：隊伍資訊
- `objective`：目標顯示
- `status`：角色狀態
- `skill_tree`：技能樹
- `save`：存檔
- `leave`：返回標題/離開遊戲/返回遊戲

## 資料驅動原則
高頻調整資料（道具、怪物、地圖、商店、法術、目標、語系）放在 JSON，避免硬寫在 `.py`。  
程式模組負責邏輯，資料檔負責內容與平衡。

## 開發狀態
- 已可玩（原型）
- 仍在持續調整：UI 可讀性、語系文本、動畫素材對接、系統平衡

## License
For study / prototype use.
