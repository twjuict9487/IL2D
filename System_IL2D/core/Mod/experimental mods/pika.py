import random

# ==========================================
# 種田模組 (Farming Module)
# ==========================================

class CropType:
    """定義作物屬性：名稱, 買價, 賣價, 成熟所需步數"""
    WHEAT = {"name": "小麥", "buy": 10, "sell": 25, "steps": 3}
    CORN = {"name": "玉米", "buy": 20, "sell": 55, "steps": 5}
    STRAWBERRY = {"name": "草莓", "buy": 50, "sell": 150, "steps": 8}

class Plot:
    """土地類別，負責處理單一土地的作物生長狀態"""
    def __init__(self):
        self.crop = None          # 當前作物數據
        self.progress = 0         # 生長進度
        self.is_watered = False   # 是否已澆水
        self.is_fertilized = False # 是否已施肥

    def plant(self, crop_type):
        if self.crop is None:
            self.crop = crop_type
            self.progress = 0
            self.is_watered = False
            self.is_fertilized = False
            return True
        return False

    def grow(self):
        """生長邏輯：必須澆水才會成長，施肥可以加倍成長"""
        if self.crop and self.is_watered:
            growth_speed = 2 if self.is_fertilized else 1
            self.progress += growth_speed
            self.is_watered = False # 每一階段都要重新澆水
            return True
        return False

    def is_mature(self):
        return self.crop and self.progress >= self.crop["steps"]

    def __str__(self):
        if not self.crop:
            return "[ 空地 ]"
        status = "已成熟" if self.is_mature() else f"生長中({self.progress}/{self.crop['steps']})"
        water_str = " (已澆水)" if self.is_watered else " (乾涸)"
        ferti_str = " (已施肥)" if self.is_fertilized else ""
        return f"[{self.crop['name']} - {status}{water_str}{ferti_str}]"

class FarmingSystem:
    def __init__(self):
        self.money = 100
        self.level = 1
        self.exp = 0
        self.fertilizer_count = 0
        self.inventory = {
            "小麥種子": 2,
            "玉米種子": 0,
            "草莓種子": 0,
            "小麥成品": 0,
            "玉米成品": 0,
            "草莓成品": 0
        }
        self.plots = [Plot() for _ in range(3)] # 初始 3 塊地

    def hunt_monsters(self):
        """模擬打怪掉落肥料"""
        print("\n⚔️ 你前往森林與怪物戰鬥...")
        drop = random.randint(1, 3)
        self.fertilizer_count += drop
        print(f"戰勝了！怪物掉落了 {drop} 個肥料。")

        # --- 動態掉落率邏輯 ---
        # 根據玩家等級設定額外肥料掉落機率
        if self.level >= 30:
            drop_rate = 0.20      # 30等以上：20% 封頂
        elif self.level >= 20:
            drop_rate = 0.10      # 20-29等：10%
        elif self.level >= 10:
            drop_rate = 0.0667    # 10-19等：6.67%
        else:
            drop_rate = 0.05      # 1-9等：初始 5%

        if random.random() < drop_rate:
            extra_fertilizer = random.randint(1, 2)
            self.fertilizer_count += extra_fertilizer
            print(f"✨ 額外驚喜！你從怪物身上搜到了 {extra_fertilizer} 個額外肥料！(目前機率: {drop_rate*100:.2f}%)")

    def buy_seeds(self):
        print("\n🛒 歡迎來到種子商店")
        print(f"當前金幣: {self.money}")
        crops = [CropType.WHEAT, CropType.CORN, CropType.STRAWBERRY]
        for i, c in enumerate(crops, 1):
            print(f"{i}. {c['name']}種子 - 價格: {c['buy']}")
        
        choice = input("請選擇購買 (或輸入 n 返回): ")
        if choice.isdigit() and 1 <= int(choice) <= 3:
            target = crops[int(choice)-1]
            if self.money >= target['buy']:
                self.money -= target['buy']
                self.inventory[f"{target['name']}種子"] += 1
                print(f"成功購買了 {target['name']}種子！")
            else:
                print("金幣不足！")

    def sell_crops(self):
        print("\n💰 販售收成")
        total_gain = 0
        for c in [CropType.WHEAT, CropType.CORN, CropType.STRAWBERRY]:
            count = self.inventory[f"{c['name']}成品"]
            if count > 0:
                gain = count * c['sell']
                total_gain += gain
                self.inventory[f"{c['name']}成品"] = 0
                print(f"賣出 {count} 個{c['name']}，獲得 {gain} 金幣")
        
        if total_gain > 0:
            self.money += total_gain
        else:
            print("倉庫裡沒有可以賣的作物。")

    def manage_farm(self):
        while True:
            print("\n" + "="*30)
            # 在介面上顯示當前等級與經驗值
            print(f"🌾 我的農場 | 等級: {self.level} (EXP: {self.exp}/3) | 金幣: {self.money} | 肥料: {self.fertilizer_count}")
            for i, plot in enumerate(self.plots):
                print(f"{i+1}. {plot}")
            print("="*30)
            print("指令: 1-3(選擇土地) | s(商店) | h(打怪) | m(賣出) | n(下一天/生長) | q(離開)")
            
            cmd = input("執行操作: ").lower()
            
            if cmd in ["1", "2", "3"]:
                idx = int(cmd) - 1
                plot = self.plots[idx]
                
                if plot.is_mature():
                    print(f"收成了 {plot.crop['name']}！")
                    self.inventory[f"{plot.crop['name']}成品"] += 1
                    plot.crop = None
                    
                    # --- 升級機制 ---
                    # 每次收成獲得 1 點經驗值
                    self.exp += 1
                    # 每累積 3 點經驗值提升 1 個等級
                    if self.exp >= 3:
                        self.level += 1
                        self.exp = 0
                        print(f"🎊 恭喜升級！當前等級：{self.level}")
                elif plot.crop is None:
                    print("選擇種子:")
                    seeds = [k for k, v in self.inventory.items() if "種子" in k and v > 0]
                    if not seeds:
                        print("你沒有任何種子。")
                    else:
                        for i, s in enumerate(seeds, 1): print(f"{i}. {s}")
                        s_choice = input("選擇種植 (或 n 取消): ")
                        if s_choice.isdigit() and 1 <= int(s_choice) <= len(seeds):
                            s_name = seeds[int(s_choice)-1]
                            # 匹配作物類型
                            c_type = None
                            if "小麥" in s_name: c_type = CropType.WHEAT
                            elif "玉米" in s_name: c_type = CropType.CORN
                            elif "草莓" in s_name: c_type = CropType.STRAWBERRY
                            
                            if plot.plant(c_type):
                                self.inventory[s_name] -= 1
                                print(f"已種下 {c_type['name']}。")
                else:
                    print("1. 澆水")
                    print("2. 施肥")
                    sub_cmd = input("選擇操作: ")
                    if sub_cmd == "1":
                        plot.is_watered = True
                        print("澆水成功！(作物將在下一天成長)")
                    elif sub_cmd == "2":
                        if self.fertilizer_count > 0:
                            if not plot.is_fertilized:
                                self.fertilizer_count -= 1
                                plot.is_fertilized = True
                                print("施肥成功！成長速度倍增。")
                            else:
                                print("這塊地已經施過肥了。")
                        else:
                            print("肥料不足，快去打怪！")
            
            elif cmd == 's': self.buy_seeds()
            elif cmd == 'h': self.hunt_monsters()
            elif cmd == 'm': self.sell_crops()
            elif cmd == 'n':
                print("\n🌞 太陽升起，新的一天...")
                any_grow = False
                for p in self.plots:
                    if p.grow(): any_grow = True
                if not any_grow:
                    print("(提醒：作物需要澆水才會成長喔！)")
            elif cmd == 'q':
                break

def play_farming():
    farm = FarmingSystem()
    print("\n" + "*"*50)
    print("歡迎來到 迷你農場模組！")
    print("在這裡你可以體驗種田、打怪獲取肥料、最後致富。")
    print("*"*50)
    farm.manage_farm()

if __name__ == "__main__":
    while True:
        print("\n" + "="*30)
        print("  IL2D 系統 - 迷你農場模組")
        print("="*30)
        print("1. 開始農場遊戲 (Start Farming)")
        print("q. 退出")
        main_choice = input("\n請選擇指令: ").strip().lower()
        
        if main_choice == "1":
            play_farming()
        elif main_choice == "q":
            break
        else:
            print("無效選擇。")
