from mods.michael_mods.blackjack import BlackjackCore


# 掛載 michael blackjack mod：提供可被 UI/指令呼叫的遊戲核心 API。
def register_mod(ctx):
    game = ctx["game"]
    state = ctx.setdefault("michael_blackjack", {})
    state["core"] = BlackjackCore(decks=2, hit_soft_17=False)

    def _core():
        return ctx["michael_blackjack"]["core"]

    game.blackjack_start = lambda bet: _core().start_round(bet)
    game.blackjack_hit = lambda: _core().hit()
    game.blackjack_stand = lambda: _core().stand()
    game.blackjack_state = lambda hide_dealer=True: _core().state(hide_dealer=hide_dealer)
