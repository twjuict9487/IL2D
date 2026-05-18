import random
from enum import Enum

COLD_REACTIONS = [
    "嗯...還可以啦。",
    "哈，普通牌而已。",
    "看起來運氣一般呢。",
    "這點數...還需要努力。",
    "平常的手牌呢。",
]
NERVOUS_REACTIONS = [
    "呃...你這手牌有點危險呢！",
    "哇，這...這點數！",
    "嘖...看起來你運氣不錯啊。",
    "天啊，你...你真的要和我比？",
    "心...心臟要跳出來了...",
    "我...我開始緊張了...",
    "這...這太可怕了！",
]
DEALER_WIN_COMMENTS = [
    "哼，我就說嘛，運氣不會一直站在你那邊！",
    "看來今天是我的勝利呢。",
    "嘿嘿，這次你輸了。",
    "我就知道會是這樣的結局。",
    "果然，我的牌更強。",
    "哈，又是我贏。",
    "這就是現實啊。",
]
PLAYER_WIN_COMMENTS = [
    "不...不可能！我怎麼會輸給你！",
    "這...這一定是我的運氣不好！",
    "該死，你居然贏了我！",
    "呃...我認輸了...",
    "你...你真的打敗我了...",
    "我...我無話可說...",
    "好吧，你是贏家。但下次會不同！",
    "該死...我一定會贏回來的...",
]
DRAW_COMMENTS = [
    "看來我們勢均力敵呢。",
    "平手...也算是一種結果吧。",
    "呵呵，打平了。",
    "有意思，下次再來。",
    "嗯，這算是平局吧。",
    "不分上下啊。",
    "平手...嗯，還可以。",
]
PRESSURE_REACTIONS = [
    "你最近手感很好...我得更小心。",
    "連勝了？這把我不會放水。",
    "你的節奏變快了，我看見了。",
]
DANGER_REACTIONS = [
    "你只差一步就可能翻盤。",
    "這點數很黏，停不停都難選。",
    "再一張就可能爆，別衝動。",
]


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
            return 11
        if self.rank in [Rank.JACK, Rank.QUEEN, Rank.KING]:
            return 10
        return int(self.rank.value)

class Hand:
    def __init__(self):
        self.cards = []

    def add_card(self, card):
        self.cards.append(card)

    def get_value(self):
        """計算手牌的總值（考慮 A 的靈活性）"""
        total, aces = 0, 0
        for card in self.cards:
            if card.rank == Rank.ACE:
                aces += 1
                total += 11
            else:
                total += card.get_value()
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
    def __init__(self, num_decks=1, reshuffle_threshold=10):
        self.num_decks = max(1, int(num_decks))
        self.reshuffle_threshold = max(5, int(reshuffle_threshold))
        self.cards = []
        self.create_deck(self.num_decks)

    def create_deck(self, num_decks):
        """建立牌組"""
        self.cards = [Card(s, r) for _ in range(num_decks) for s in Suit for r in Rank]
        random.shuffle(self.cards)

    def draw_card(self):
        """抽一張牌"""
        if len(self.cards) < self.reshuffle_threshold:
            self.create_deck(self.num_decks)
        return self.cards.pop()


class BlackjackGame:
    def __init__(self, bet=0, num_decks=2, hit_soft_17=False, reshuffle_threshold=10):
        self.deck = Deck(num_decks=num_decks, reshuffle_threshold=reshuffle_threshold)
        self.player_hand = None
        self.dealer_hand = None
        self.game_over = False
        self.result = None
        self.bet = bet
        self.winnings = 0
        self.hit_soft_17 = bool(hit_soft_17)

    def get_dealer_reaction(self):
        """
        根據玩家手牌分數返回荷官的反應
        """
        return random.choice(NERVOUS_REACTIONS if self.player_hand.get_value() >= 19 else COLD_REACTIONS)

    def get_dealer_final_comment(self):
        """
        根據遊戲結果返回荷官的感言
        """
        if "玩家獲勝" in self.result:
            return random.choice(PLAYER_WIN_COMMENTS)
        if "平手" in self.result:
            return random.choice(DRAW_COMMENTS)
        if "莊家獲勝" in self.result or "玩家爆牌" in self.result:
            return random.choice(DEALER_WIN_COMMENTS)
        return "遊戲結束。"

    def start_game(self):
        """開始一局遊戲"""
        self.player_hand, self.dealer_hand = Hand(), Hand()
        self.game_over, self.result, self.winnings = False, None, 0
        for _ in range(2):
            self.player_hand.add_card(self.deck.draw_card())
            self.dealer_hand.add_card(self.deck.draw_card())
        if self.player_hand.is_blackjack():
            self.game_over = True
            if self.dealer_hand.is_blackjack():
                self.result, self.winnings = "平手 - 都是 21 點", self.bet
            else:
                self.result, self.winnings = "玩家獲勝 - 21 點！", int(self.bet * 2.5)

    def player_hit(self):
        """玩家要牌"""
        if self.game_over:
            return
        self.player_hand.add_card(self.deck.draw_card())
        v = self.player_hand.get_value()
        if v > 21:
            self.game_over, self.result, self.winnings = True, "玩家爆牌 - 超過 21 點", 0
        elif v == 21:
            self.player_stand()

    def player_stand(self):
        """玩家停牌"""
        if self.game_over:
            return
        self.game_over = True
        self.dealer_play()

    def dealer_play(self):
        """莊家的自動遊戲邏輯"""
        while self.dealer_hand.get_value() < 17 or (self.hit_soft_17 and self._is_soft_17(self.dealer_hand)):
            self.dealer_hand.add_card(self.deck.draw_card())
        pv, dv = self.player_hand.get_value(), self.dealer_hand.get_value()
        if dv > 21:
            self.result, self.winnings = "玩家獲勝 - 莊家爆牌", self.bet * 2
        elif pv > dv:
            self.result, self.winnings = "玩家獲勝", self.bet * 2
        elif pv < dv:
            self.result, self.winnings = "莊家獲勝", 0
        else:
            self.result, self.winnings = "平手", self.bet

    def _is_soft_17(self, hand):
        if hand.get_value() != 17:
            return False
        total_raw = sum(c.get_value() for c in hand.cards)
        ace_count = sum(1 for c in hand.cards if c.rank == Rank.ACE)
        return ace_count > 0 and total_raw != 17

    def display_game_state(self, show_dealer_hole_card=False, chips=0):
        """顯示遊戲狀態"""
        print("\n" + "=" * 50)
        print("【21 點遊戲】")
        print("=" * 50)
        print(f"當前籌碼: {chips}")
        if self.bet > 0:
            print(f"本局下注: {self.bet}")
        print("=" * 50)

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
            print("\n" + "-" * 50)
            print(f"【結果】{self.result}")
            final_comment = self.get_dealer_final_comment()
            print(f"\n荷官：\"{final_comment}\"")
            if self.winnings > self.bet:
                print(f"\n獲得: +{self.winnings - self.bet} 籌碼")
            elif self.winnings < self.bet:
                print(f"\n失去: -{self.bet - self.winnings} 籌碼")
            else:
                print("\n本局平手")
            print("-" * 50)


# 與 mod 掛載層相容的薄封裝：不改原始玩法，只提供 API 介面。
class BlackjackCore:
    def __init__(self, decks=2, hit_soft_17=False):
        self._decks = max(1, int(decks))
        self._hit_soft_17 = bool(hit_soft_17)
        self._reshuffle_threshold = 18
        self._game = None
        self._reaction = ""
        self._final_comment = ""
        self._player_streak = 0
        self._dealer_streak = 0
        self._last_reaction = ""
        self._last_final_comment = ""

    def _pick_non_repeat(self, pool, last_value):
        if not pool:
            return ""
        if len(pool) == 1:
            return pool[0]
        picked = random.choice(pool)
        return picked if picked != last_value else random.choice([x for x in pool if x != last_value] or [picked])

    def _build_reaction(self):
        if self._game is None or self._game.player_hand is None:
            return ""
        pv = self._game.player_hand.get_value()
        du = self._game.dealer_hand.cards[0].get_value() if self._game.dealer_hand.cards else 0
        pool = (
            PRESSURE_REACTIONS + NERVOUS_REACTIONS if self._player_streak >= 2
            else NERVOUS_REACTIONS if pv >= 19
            else DANGER_REACTIONS if 15 <= pv <= 18 and du >= 9
            else COLD_REACTIONS
        )
        return self._pick_non_repeat(pool, self._last_reaction)

    def _build_final_comment(self):
        if self._game is None or not self._game.result:
            return ""
        result = self._game.result
        if "玩家獲勝" in result:
            base = self._pick_non_repeat(PLAYER_WIN_COMMENTS, self._last_final_comment)
            return f"{base} 你已經連贏了，氣勢很足。" if self._player_streak >= 2 else base
        if "平手" in result:
            return self._pick_non_repeat(DRAW_COMMENTS, self._last_final_comment)
        if "莊家獲勝" in result or "玩家爆牌" in result:
            base = self._pick_non_repeat(DEALER_WIN_COMMENTS, self._last_final_comment)
            return f"{base} 先穩住節奏，下局再拿回來。" if self._dealer_streak >= 2 else base
        return "遊戲結束。"

    def _update_streak(self):
        if self._game is None or not self._game.result:
            return
        r = self._game.result
        self._player_streak, self._dealer_streak = (
            (self._player_streak + 1, 0) if "玩家獲勝" in r
            else (0, self._dealer_streak + 1) if ("莊家獲勝" in r or "玩家爆牌" in r)
            else (0, 0)
        )

    def _build_state(self, hide_dealer=True):
        if self._game is None or self._game.player_hand is None:
            return {"finished": True, "result": "idle", "bet": 0, "payout": 0, "player": {"cards": [], "text": "", "value": 0}, "dealer": {"cards": [], "text": "", "value": None}, "narrative": {"reaction": "", "final_comment": ""}}
        g = self._game
        shown = [g.dealer_hand.cards[0]] if hide_dealer and not g.game_over and g.dealer_hand.cards else g.dealer_hand.cards
        dealer_text = ", ".join(str(c) for c in shown)
        if hide_dealer and not g.game_over and len(g.dealer_hand.cards) > 1:
            dealer_text = f"{dealer_text}, [隱藏]"
        return {
            "finished": g.game_over,
            "result": g.result or "playing",
            "bet": g.bet,
            "payout": g.winnings,
            "player": {"cards": [(c.rank.value, c.suit.value) for c in g.player_hand.cards], "text": str(g.player_hand), "value": g.player_hand.get_value()},
            "dealer": {"cards": [(c.rank.value, c.suit.value) for c in shown], "text": dealer_text, "value": None if (hide_dealer and not g.game_over) else g.dealer_hand.get_value()},
            "narrative": {"reaction": self._reaction, "final_comment": self._final_comment},
        }

    def start_round(self, bet):
        self._game = BlackjackGame(bet=max(1, int(bet)), num_decks=self._decks, hit_soft_17=self._hit_soft_17, reshuffle_threshold=self._reshuffle_threshold)
        self._game.start_game()
        self._reaction = self._last_reaction = self._build_reaction()
        self._final_comment = self._build_final_comment() if self._game.game_over else ""
        if self._final_comment:
            self._last_final_comment = self._final_comment
            self._update_streak()
        return self._build_state(hide_dealer=not self._game.game_over)

    def hit(self):
        if self._game is None:
            return self._build_state(hide_dealer=False)
        self._game.player_hit()
        if self._game.game_over:
            self._update_streak()
            self._final_comment = self._last_final_comment = self._build_final_comment()
        else:
            self._reaction = self._last_reaction = self._build_reaction()
        return self._build_state(hide_dealer=not self._game.game_over)

    def stand(self):
        if self._game is None:
            return self._build_state(hide_dealer=False)
        self._game.player_stand()
        self._update_streak()
        self._final_comment = self._last_final_comment = self._build_final_comment()
        return self._build_state(hide_dealer=False)

    def state(self, hide_dealer=True):
        return self._build_state(hide_dealer=hide_dealer)


def play_blackjack():
    """主遊戲循環"""
    print("\n" + "*" * 50)
    print("歡迎來到 21 點遊戲！")
    print("*" * 50)

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
        print("\n" + "=" * 50)
        print(f"【新的一局】當前籌碼: {player_chips}")
        print("=" * 50)

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

        old_chips = player_chips
        player_chips = player_chips - bet + game.winnings

        print("\n" + "=" * 50)
        print(f"籌碼更新: {old_chips} -> {player_chips}")
        print("=" * 50)

        if player_chips <= 0:
            print("\n遊戲結束 - 籌碼用盡！")
            print(f"初始籌碼: {initial_chips}")
            print(f"最終籌碼: {player_chips}")
            break

        while True:
            again = input("\n要再玩一局嗎？(y/n)：").strip().lower()
            if again in ["y", "n"]:
                break
            print("請輸入 y 或 n")

        if again == "n":
            print("\n" + "*" * 50)
            print(f"感謝遊戲！最終籌碼: {player_chips}")
            print("*" * 50)
            break


if __name__ == "__main__":
    play_blackjack()
