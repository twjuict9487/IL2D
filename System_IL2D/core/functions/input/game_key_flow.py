import time, pygame
from ..support.i18n import tr

P = pygame
U = lambda k: k in (P.K_UP, P.K_w)
D = lambda k: k in (P.K_DOWN, P.K_s)
L = lambda k: k in (P.K_LEFT, P.K_a)
R = lambda k: k in (P.K_RIGHT, P.K_d)
OK = lambda k: k in (P.K_RETURN, P.K_SPACE)
NUM = {
    P.K_1: 0,
    P.K_2: 1,
    P.K_3: 2,
    P.K_4: 3,
    P.K_5: 4,
    P.K_6: 5,
    P.K_7: 6,
    P.K_8: 7,
    P.K_9: 8,
    P.K_0: 9,
}
MOV = {P.K_w: ("w", 0, -1), P.K_s: ("s", 0, 1), P.K_a: ("a", -1, 0), P.K_d: ("d", 1, 0)}


def _set_mission_feedback(g, r, mission_id=None):
    r = str(r or "").strip()
    if not r:
        return
    t = tr(getattr(g, "lang", "en"), r)
    if not t or t == r:
        t = r.replace(".", " ").title()
    p = {
        "text": t,
        "reason": r,
        "mission_id": mission_id,
        "created": time.time(),
        "duration": 2.5,
    }
    g.mission_feedback = p
    if hasattr(g, "banner"):
        g.banner = {"text": t, "created": p["created"], "duration": p["duration"]}
    if hasattr(g, "push_message"):
        try:
            g.push_message(t)
        except Exception:
            pass


def _move_sel(o, a, n, d, wrap=False):
    v = getattr(o, a, 0) + d
    setattr(o, a, v % n if wrap and n else max(0, min(n - 1, v)) if n else 0)


def _scroll(o, a, d, hi=None):
    if hasattr(o, a):
        setattr(
            o,
            a,
            max(0, min(hi if hi is not None else 10**9, int(getattr(o, a, 0)) + d)),
        )


def _mission_pick(g, row):
    s = row.get("status")
    i = row.get("id")
    if s == "available" and hasattr(g, "accept_mission"):
        g.accept_mission(i)
    elif s in {"ready", "ready_to_return"} and hasattr(g, "turn_in_mission"):
        g.turn_in_mission(i)
    elif s == "active":
        if hasattr(g, "set_tracked_mission"):
            g.set_tracked_mission(i)
        else:
            g.tracked_mission = i
    else:
        giver = getattr(g, "mission_board_giver", None)
        r = ""
        try:
            from ..gameplay import missions as m

            r = m.mission_acceptance_reason(g, i, giver_id=giver)
        except Exception:
            r = str(s or "mission.locked")
        _set_mission_feedback(g, r or "mission.locked", i)


def _settle_bj(g):
    st = getattr(g, "blackjack_ui_state", {}) or {}
    if st.get("finished") and not getattr(g, "blackjack_round_settled", False):
        g.money = max(
            0,
            int(getattr(g, "money", 0))
            - int(st.get("bet", 0) or 0)
            + int(st.get("payout", 0) or 0),
        )
        g.blackjack_round_settled = True


def handle_game_key(
    c, e, press_move_fn, set_always_on_top_fn, center_window_fn, tile_size, viewport
):
    g = c["game"]
    k = e.key
    m = g.ui_mode
    if m == "death_menu":
        if getattr(g, "chase_death_pending", False):
            g.death_menu_selected = 0
            if OK(k):
                g.handle_death_menu_confirm()
            return
        if g.death_no_save_notice:
            if OK(k) or k == P.K_ESCAPE:
                g.request_quit = True
        elif U(k):
            g.death_menu_selected = max(0, g.death_menu_selected - 1)
        elif D(k):
            g.death_menu_selected = min(1, g.death_menu_selected + 1)
        elif OK(k):
            g.handle_death_menu_confirm()
        return
    chase = getattr(g, "chase_controller", None)
    if chase and chase.is_chase_map(g):
        if chase.is_input_locked():
            return
        if chase.is_forced_run() and (k == P.K_ESCAPE or k in (P.K_a, P.K_d)):
            return
    if m == "story_title_card":
        return
    if m == "story_timeline":
        rows = g.get_story_timeline_rows() if hasattr(g, "get_story_timeline_rows") else []
        if U(k) and rows:
            g.story_timeline_selected = max(
                0, int(getattr(g, "story_timeline_selected", 0)) - 1
            )
            _scroll(g, "story_timeline_scroll", -1)
        elif D(k) and rows:
            g.story_timeline_selected = min(
                len(rows) - 1, int(getattr(g, "story_timeline_selected", 0)) + 1
            )
            _scroll(g, "story_timeline_scroll", 1, max(0, len(rows) - 1))
        elif OK(k):
            if hasattr(g, "confirm_story_timeline_selection"):
                g.confirm_story_timeline_selection()
        elif k == P.K_ESCAPE:
            if hasattr(g, "close_story_timeline"):
                g.close_story_timeline()
            else:
                g.ui_mode = None
        return
    if m == "level_stat_choice":
        o = g.get_level_stat_options() if hasattr(g, "get_level_stat_options") else []
        if not o:
            g.ui_mode = None
            return
        if U(k):
            _move_sel(g, "level_stat_selected", len(o), -1, 1)
        elif D(k):
            _move_sel(g, "level_stat_selected", len(o), 1, 1)
        elif OK(k):
            g.choose_level_stat(g.level_stat_selected)
        return
    if k == P.K_i and m is None:
        g.active_hotbar = "magic" if g.active_hotbar == "item" else "item"
    elif k in NUM:
        if m is None:
            s = NUM[k]
            n = (
                g.item_hotbar_slots
                if g.active_hotbar == "item"
                else g.magic_hotbar_slots
            )[s]
            if n:
                (
                    g.use_item_by_name
                    if g.active_hotbar == "item"
                    else g.cast_spell_by_name
                )(n)
        return
    if m == "interact_pick":
        a = g.interact_candidates
        if U(k) and a:
            _move_sel(g, "interact_selected", len(a), -1, 1)
            _scroll(g, "interact_scroll", -1)
        elif D(k) and a:
            _move_sel(g, "interact_selected", len(a), 1, 1)
            _scroll(g, "interact_scroll", 1, max(0, len(a) - 1))
        elif k in (P.K_PAGEUP, P.K_HOME):
            _scroll(g, "interact_scroll", -3)
        elif k in (P.K_PAGEDOWN, P.K_END):
            _scroll(g, "interact_scroll", 3, max(0, len(a) - 1))
        elif k == P.K_RETURN:
            g.confirm_interact_choice()
        elif k == P.K_ESCAPE:
            g.cancel_interact_choice()
        return
    if m == "dialog":
        if k in (P.K_UP, P.K_w, P.K_LEFT, P.K_a):
            g.dialog_selected = max(0, int(getattr(g, "dialog_selected", 0)) - 1)
        elif k in (P.K_DOWN, P.K_s, P.K_RIGHT, P.K_d):
            g.dialog_selected = int(getattr(g, "dialog_selected", 0)) + 1
        elif k == P.K_PAGEUP:
            _scroll(g, "dialog_scroll", -3)
        elif k == P.K_PAGEDOWN:
            _scroll(g, "dialog_scroll", 3)
        elif k == P.K_RETURN:
            g.dialog_choose()
        elif k == P.K_ESCAPE:
            (
                g.close_dialog
                if hasattr(g, "close_dialog")
                else lambda: setattr(g, "ui_mode", None)
            )()
        return
    if m == "shop":
        if k == P.K_UP and g.shop_items:
            _move_sel(g, "shop_selected", len(g.shop_items), -1, 1)
        elif k == P.K_DOWN and g.shop_items:
            _move_sel(g, "shop_selected", len(g.shop_items), 1, 1)
        elif L(k):
            g.cycle_shop_category(-1)
        elif R(k):
            g.cycle_shop_category(1)
        elif k == P.K_RETURN:
            g.buy_selected_item()
        elif k == P.K_ESCAPE:
            g.close_shop()
        return
    if m == "blackjack_bet":
        if k == P.K_ESCAPE:
            g.ui_mode = None
        elif k == P.K_BACKSPACE:
            g.blackjack_bet_input = getattr(g, "blackjack_bet_input", "")[:-1]
            g.blackjack_bet_error = ""
        elif k == P.K_RETURN:
            x = (getattr(g, "blackjack_bet_input", "") or "").strip()
            if not x.isdigit():
                g.blackjack_bet_error = "invalid"
                return
            a = int(x)
            money = int(getattr(g, "money", 0))
            if a <= 0 or a > money:
                g.blackjack_bet_error = "range"
                return
            g.blackjack_session_bank = a
            g.blackjack_ui_state = g.blackjack_start(a)
            g.blackjack_ui_selected = 0
            g.blackjack_round_settled = False
            g.blackjack_bet_error = ""
            g.ui_mode = "blackjack"
        elif e.unicode and e.unicode.isdigit():
            x = getattr(g, "blackjack_bet_input", "")
            if len(x) < 9:
                g.blackjack_bet_input = x + e.unicode
                g.blackjack_bet_error = ""
        return
    if m == "blackjack":
        st = getattr(g, "blackjack_ui_state", {}) or {}
        f = bool(st.get("finished"))
        _settle_bj(g)
        n = 2 if f else 3
        if U(k) or L(k):
            g.blackjack_ui_selected = (getattr(g, "blackjack_ui_selected", 0) - 1) % n
        elif D(k) or R(k):
            g.blackjack_ui_selected = (getattr(g, "blackjack_ui_selected", 0) + 1) % n
        elif k == P.K_ESCAPE:
            g.ui_mode = None
        elif k == P.K_RETURN:
            s = int(getattr(g, "blackjack_ui_selected", 0))
            if f:
                if s == 0 and hasattr(g, "blackjack_start"):
                    b = min(
                        max(1, int(st.get("bet", 10) or 10)),
                        int(getattr(g, "money", 0)),
                    )
                    if b <= 0:
                        g.ui_mode = None
                        return
                    g.blackjack_ui_state = g.blackjack_start(b)
                    g.blackjack_ui_selected = 0
                    g.blackjack_round_settled = False
                else:
                    g.ui_mode = None
            elif s == 0 and hasattr(g, "blackjack_hit"):
                g.blackjack_ui_state = g.blackjack_hit()
                g.blackjack_ui_selected = 0
                _settle_bj(g)
            elif s == 1 and hasattr(g, "blackjack_stand"):
                g.blackjack_ui_state = g.blackjack_stand()
                g.blackjack_ui_selected = 0
                _settle_bj(g)
            else:
                g.ui_mode = None
        return
    if m == "mission_board":
        ms = (
            g.get_mission_board_entries(getattr(g, "mission_board_giver", None))
            if hasattr(g, "get_mission_board_entries")
            else []
        )
        if U(k) and ms:
            g.mission_board_selected = max(0, g.mission_board_selected - 1)
            _scroll(g, "mission_detail_scroll", -(10**9))
            _scroll(g, "mission_board_scroll", -1)
        elif D(k) and ms:
            g.mission_board_selected = min(len(ms) - 1, g.mission_board_selected + 1)
            _scroll(g, "mission_detail_scroll", -(10**9))
            _scroll(g, "mission_board_scroll", 1, max(0, len(ms) - 1))
        elif k in (P.K_PAGEUP, P.K_LEFT):
            _scroll(g, "mission_detail_scroll", -4)
        elif k in (P.K_PAGEDOWN, P.K_RIGHT):
            _scroll(g, "mission_detail_scroll", 4)
        elif k == P.K_RETURN:
            giver = getattr(g, "mission_board_giver", None)
            ms = (
                g.get_mission_board_entries(giver)
                if giver and hasattr(g, "get_mission_board_entries")
                else []
            )
            if ms:
                _mission_pick(
                    g,
                    ms[
                        max(
                            0,
                            min(
                                len(ms) - 1,
                                int(getattr(g, "mission_board_selected", 0)),
                            ),
                        )
                    ],
                )
        elif k == P.K_ESCAPE:
            (
                g.close_mission_board
                if hasattr(g, "close_mission_board")
                else g.close_dialog
            )()
        return
    if m == "hotbar":
        if k == P.K_i:
            g.hotbar_mode = "magic" if g.hotbar_mode == "item" else "item"
            g.hotbar_type_selected = 0 if g.hotbar_mode == "item" else 1
            g.hotbar_list_selected = 0
        elif k in (P.K_DELETE, P.K_BACKSPACE):
            (
                g.item_hotbar_slots if g.hotbar_mode == "item" else g.magic_hotbar_slots
            ).__setitem__(g.hotbar_slot_selected, None)
        return
    if k == P.K_ESCAPE:
        c["state"] = "esc_menu"
    if k == P.K_F12:
        c["fullscreen"] = not c["fullscreen"]
        w = tile_size * viewport
        h = tile_size * (viewport + 1)
        c["screen"] = P.display.set_mode((w, h), P.FULLSCREEN if c["fullscreen"] else 0)
        if not c["fullscreen"]:
            center_window_fn(c["screen"])
        set_always_on_top_fn()
    if k in MOV:
        press_move_fn(c, *MOV[k])
    elif k == P.K_e:
        g.player_interact()
