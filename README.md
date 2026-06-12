# Project: IL2D

IL2D 是一個 2D 俯視角 RPG 原型專案，採資料驅動（JSON）+ 模組化（mods）設計。

## 目前內容
- 固定主地圖：`map_1`、`map_2`、`map_3`
- Rogue 分層地城：程序生成、層數推進、Boss 層規則
- 戰鬥系統：HP/MP、攻防、法術、掉落、EXP/等級
- NPC 系統：對話、商店、任務、關係值
- 隊伍系統：可解鎖隊友（Monst3r / Wisadel）
- Hotbar：item / magic 快捷欄與 `1~0` 快捷施放
- 存檔系統：多槽位存檔/讀檔
- 語系：中英文字串由 `i18n.json` 管理
- 農場模組（farmer mod）：買地、種子、種植、收成、販售、農場地圖

## 專案結構（重點）
```text
main.py
README.md
System_IL2D/
  core/
    system_core.py
    mod_loader.py
    functions/
      gameplay/
      input/
      models/
      rendering/
      support/
      ui/
      world/
    Pre_coded_data/
      entity/
      game_data/
      map/
  mods/
    farmer_entry.py
    farmer_mod/
      farmer_mod_main.py
      functions/
      maps/
      farm_data.json
  clips/
  saves/
  tools/
Backup_version_v001/
```

## 執行方式
```powershell
python main.py
```

## 新電腦快速開始
```powershell
./setup_windows.ps1
```

完成後可直接啟動：
```bat
run_il2d.bat
```

如果 PowerShell 擋腳本，可先執行：
```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 基本操作
- `W/A/S/D`：移動
- `E`：互動
- `F`：農場操作（種植/收成，於農地與對應 UI）
- `ESC`：開啟/關閉遊戲內選單
- `I`：切換目前啟用的快捷欄（item / magic）
- `1~0`：使用目前啟用快捷欄對應槽位

## 模組機制
- `core/mod_loader.py` 會載入 `System_IL2D/mods/*.py` 入口檔。
- 每個 mod 可註冊 `on_game_key`、`on_update`、`on_render` 等 hook。
- 單一 mod 出錯時會記錄到 `ctx["mod_errors"]`，核心流程仍可繼續。

## 說明
- `Backup_version_v001/` 是舊版本備份，不是主執行路徑。
- 主要可執行內容在 `System_IL2D/`。

## License
For study / prototype use.
