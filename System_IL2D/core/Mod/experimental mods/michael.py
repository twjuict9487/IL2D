import random
from enum import Enum

class Suit(Enum):
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"

class Rank(Enum):
    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
    
    def __str__(self):
        return f"{self.rank.value}{self.suit.value}"
    
    def get_value(self):
        """獲取牌的點數值"""
        if self.rank == Rank.ACE:
            return 11  # 先假設 A = 11
        elif self.rank in [Rank.JACK, Rank.QUEEN, Rank.KING]:
            return 10
        else:
            return int(self.rank.value)

class Hand:
    def __init__(self):
        self.cards = []
    
    def add_card(self, card):
        self.cards.append(card)
    
    def get_value(self):
        """計算手牌的總值（考慮 A 的靈活性）"""
        total = 0
        aces = 0
        
        for card in self.cards:
            if card.rank == Rank.ACE:
                aces += 1
                total += 11
            else:
                total += card.get_value()
        
        # 如果超過 21，將 A 從 11 改為 1
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    def __str__(self):
        return ", ".join(str(card) for card in self.cards)
    
    def is_blackjack(self):
        """檢查是否是 21 點（兩張牌且總值為 21）"""
        return len(self.cards) == 2 and self.get_value() == 21

class Deck:
    def __init__(self, num_decks=1):
        self.cards = []
        self.create_deck(num_decks)
    
    def create_deck(self, num_decks):
        """建立牌組"""
        for _ in range(num_decks):
            for suit in Suit:
                for rank in Rank:
                    self.cards.append(Card(suit, rank))
        random.shuffle(self.cards)
    
    def draw_card(self):
        """抽一張牌"""
        if len(self.cards) < 10:
            self.create_deck(1)  # 牌不足時重新洗牌
        return self.cards.pop()

class BlackjackGame:
    def __init__(self, bet=0):
        self.deck = Deck(num_decks=2)
        self.player_hand = None
        self.dealer_hand = None
        self.game_over = False
        self.result = None
        self.bet = bet
        self.winnings = 0
    
    def get_dealer_reaction(self):
        """
        根據玩家手牌分數返回荷官的反應
        """
        player_value = self.player_hand.get_value()
        
        # 冷漠反應（≤18分）
        cold_reactions = [
            "嗯...還可以啦。",
            "哈，普通牌而已。",
            "看起來運氣一般呢。",
            "這點數...還需要努力。",
            "平常的手牌呢。",
        ]
        
        # 緊張反應（≥19分）
        nervous_reactions = [
            "呃...你這手牌有點危險呢！",
            "哇，這...這點數！",
            "嘖...看起來你運氣不錯啊。",
            "天啊，你...你真的要和我比？",
            "心...心臟要跳出來了...",
            "我...我開始緊張了...",
            "這...這太可怕了！",
        ]
        
        if player_value >= 19:
            return random.choice(nervous_reactions)
        else:
            return random.choice(cold_reactions)
    
    def get_dealer_final_comment(self):
        """
        根據遊戲結果返回荷官的感言
        """
        # 荷官獲勝
        dealer_win_comments = [
            "哼，我就說嘛，運氣不會一直站在你那邊！",
            "看來今天是我的勝利呢。",
            "嘿嘿，這次你輸了。",
            "我就知道會是這樣的結局。",
            "果然，我的牌更強。",
            "哈，又是我贏。",
            "這就是現實啊。",
        ]
        
        # 玩家獲勝
        player_win_comments = [
            "不...不可能！我怎麼會輸給你！",
            "這...這一定是我的運氣不好！",
            "該死，你居然贏了我！",
            "呃...我認輸了...",
            "你...你真的打敗我了...",
            "我...我無話可說...",
            "好吧，你是贏家。但下次會不同！",
            "該死...我一定會贏回來的...",
        ]
        
        # 平手
        draw_comments = [
            "看來我們勢均力敵呢。",
            "平手...也算是一種結果吧。",
            "呵呵，打平了。",
            "有意思，下次再來。",
            "嗯，這算是平局吧。",
            "不分上下啊。",
            "平手...嗯，還可以。",
        ]
        
        if "玩家獲勝" in self.result:
            return random.choice(player_win_comments)
        elif "平手" in self.result:
            return random.choice(draw_comments)
        elif "莊家獲勝" in self.result or "玩家爆牌" in self.result:
            return random.choice(dealer_win_comments)
        else:
            return "遊戲結束。"
    
    def start_game(self):
        """開始一局遊戲"""
        self.player_hand = Hand()
        self.dealer_hand = Hand()
        self.game_over = False
        self.result = None
        
        # 發初始牌
        self.player_hand.add_card(self.deck.draw_card())
        self.dealer_hand.add_card(self.deck.draw_card())
        self.player_hand.add_card(self.deck.draw_card())
        self.dealer_hand.add_card(self.deck.draw_card())
        
        # 檢查玩家是否有 21 點
        if self.player_hand.is_blackjack():
            self.game_over = True
            if self.dealer_hand.is_blackjack():
                self.result = "平手 - 都是 21 點"
                self.winnings = self.bet  # 退還下注
            else:
                self.result = "玩家獲勝 - 21 點！"
                self.winnings = int(self.bet * 2.5)  # 21 點獲得 2.5 倍
    
    def player_hit(self):
        """玩家要牌"""
        if not self.game_over:
            self.player_hand.add_card(self.deck.draw_card())
            
            if self.player_hand.get_value() > 21:
                self.game_over = True
                self.result = "玩家爆牌 - 超過 21 點"
                self.winnings = 0  # 爆牌失敗
            elif self.player_hand.get_value() == 21:
                self.game_over = True
                self.player_stand()
    
    def player_stand(self):
        """玩家停牌"""
        if not self.game_over:
            self.game_over = True
            self.dealer_play()
    
    def dealer_play(self):
        """莊家的自動遊戲邏輯"""
        # 莊家在 17 以上停牌
        while self.dealer_hand.get_value() < 17:
            self.dealer_hand.add_card(self.deck.draw_card())
        
        # 判定勝負
        player_value = self.player_hand.get_value()
        dealer_value = self.dealer_hand.get_value()
        
        if dealer_value > 21:
            self.result = "玩家獲勝 - 莊家爆牌"
            self.winnings = self.bet * 2  # 獲得雙倍
        elif player_value > dealer_value:
            self.result = "玩家獲勝"
            self.winnings = self.bet * 2  # 獲得雙倍
        elif player_value < dealer_value:
            self.result = "莊家獲勝"
            self.winnings = 0  # 失去下注
        else:
            self.result = "平手"
            self.winnings = self.bet  # 退還下注
    
    def display_game_state(self, show_dealer_hole_card=False, chips=0):
        """顯示遊戲狀態"""
        print("\n" + "="*50)
        print("【21 點遊戲】")
        print("="*50)
        print(f"當前籌碼: {chips}")
        if self.bet > 0:
            print(f"本局下注: {self.bet}")
        print("="*50)
        
        print("\n荷官：") 
        dealer_reaction = self.get_dealer_reaction()
        print(f"  \"{dealer_reaction}\"")
        
        print("\n莊家的牌：")
        if show_dealer_hole_card or self.game_over:
            print(f"  {self.dealer_hand} (點數: {self.dealer_hand.get_value()})")
        else:
            print(f"  {self.dealer_hand.cards[0]}, [隱藏]")
        
        print("\n玩家的牌：")
        print(f"  {self.player_hand} (點數: {self.player_hand.get_value()})")
        
        if self.game_over:
            print("\n" + "-"*50)
            print(f"【結果】{self.result}")
            
            # 顯示荷官的胜負感言
            final_comment = self.get_dealer_final_comment()
            print(f"\n荷官：\"{final_comment}\"")
            
            if self.winnings > self.bet:
                print(f"\n獲得: +{self.winnings - self.bet} 籌碼")
            elif self.winnings < self.bet:
                print(f"\n失去: -{self.bet - self.winnings} 籌碼")
            else:
                print(f"\n本局平手")
            print("-"*50)

def play_blackjack():
    """主遊戲循環"""
    print("\n" + "*"*50)
    print("歡迎來到 21 點遊戲！")
    print("*"*50)
    
    # 初始籌碼
    while True:
        try:
            initial_chips = int(input("\n請輸入初始籌碼數量: "))
            if initial_chips > 0:
                break
            print("籌碼數量必須大於 0")
        except ValueError:
            print("請輸入有效的數字")
    
    player_chips = initial_chips
    print(f"\n您的初始籌碼: {player_chips}")
    
    while player_chips > 0:
        print("\n" + "="*50)
        print(f"【新的一局】當前籌碼: {player_chips}")
        print("="*50)
        
        # 下注
        while True:
            try:
                bet = int(input(f"\n請下注 (1-{player_chips})："))
                if 1 <= bet <= player_chips:
                    break
                print(f"下注金額必須在 1 到 {player_chips} 之間")
            except ValueError:
                print("請輸入有效的數字")
        
        game = BlackjackGame(bet=bet)
        game.start_game()
        game.display_game_state(chips=player_chips)
        
        if not game.game_over:
            while not game.game_over:
                print("\n你的選擇：")
                print("1. 要牌 (Hit)")
                print("2. 停牌 (Stand)")
                choice = input("請選擇 (1/2)：").strip()
                
                if choice == "1":
                    game.player_hit()
                    game.display_game_state(chips=player_chips)
                    if game.game_over:
                        break
                elif choice == "2":
                    game.player_stand()
                    game.display_game_state(chips=player_chips)
                    break
                else:
                    print("無效的選擇，請重新輸入")
        
        # 更新籌碼
        old_chips = player_chips
        player_chips = player_chips - bet + game.winnings
        
        # 顯示籌碼變化
        print("\n" + "="*50)
        print(f"籌碼更新: {old_chips} -> {player_chips}")
        print("="*50)
        
        if player_chips <= 0:
            print("\n遊戲結束 - 籌碼用盡！")
            print(f"初始籌碼: {initial_chips}")
            print(f"最終籌碼: {player_chips}")
            break
        
        # 詢問是否繼續
        while True:
            again = input("\n要再玩一局嗎？(y/n)：").strip().lower()
            if again in ["y", "n"]:
                break
            print("請輸入 y 或 n")
        
        if again == "n":
            print("\n" + "*"*50)
            print(f"感謝遊戲！最終籌碼: {player_chips}")
            print("*"*50)
            break

if __name__ == "__main__":
    play_blackjack()
