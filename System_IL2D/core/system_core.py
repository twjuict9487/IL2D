import pygame
from temp.core.game import Game
from temp.core.draw import draw, draw_main_menu, draw_esc_menu, draw_player_ui, TILE_SIZE, VIEWPORT, FPS


def _wrap_text(font, text, max_width):
    words = text.split(' ')
    lines = []
    line = ''
    for word in words:
        test = (line + ' ' + word).strip()
        if font.size(test)[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def init_context():
    pygame.init()
    screen = pygame.display.set_mode((TILE_SIZE * VIEWPORT, TILE_SIZE * (VIEWPORT + 1)))
    pygame.display.set_caption('Projekt:"IL2D" Prototype')
    clock = pygame.time.Clock()
    return {
        "screen": screen,
        "clock": clock,
        "game": Game(),
        "running": True,
        "fullscreen": False,
        "state": "main_menu",
        "menu_selected": 0,
        "esc_selected": 0
    }


def run_frame(ctx):
    dt = ctx["clock"].tick(FPS) / 1000.0
    _process_events(ctx)
    _update(ctx, dt)
    _render(ctx)


def _process_events(ctx):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            ctx["running"] = False
        elif event.type == pygame.KEYDOWN:
            _handle_key(ctx, event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            _handle_mouse(ctx, event.pos)


def _handle_key(ctx, event):
    state = ctx["state"]
    if state == "main_menu":
        _handle_main_menu_key(ctx, event)
    elif state == "esc_menu":
        _handle_esc_menu_key(ctx, event)
    elif state == "game":
        _handle_game_key(ctx, event)


def _handle_main_menu_key(ctx, event):
    if event.key == pygame.K_UP:
        ctx["menu_selected"] = (ctx["menu_selected"] - 1) % 4
    elif event.key == pygame.K_DOWN:
        ctx["menu_selected"] = (ctx["menu_selected"] + 1) % 4
    elif event.key == pygame.K_RETURN:
        if ctx["menu_selected"] == 0:
            ctx["game"] = Game()
            ctx["state"] = "game"
        elif ctx["menu_selected"] == 1:
            if not ctx["game"].load_latest_save():
                ctx["game"] = Game()
            ctx["state"] = "game"
        elif ctx["menu_selected"] == 2:
            ctx["running"] = False
        elif ctx["menu_selected"] == 3:
            pass


def _handle_esc_menu_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode:
        if event.key in (pygame.K_UP, pygame.K_LEFT):
            if game.ui_mode == "save":
                game.save_selected = (game.save_selected - 1) % 3
            elif game.ui_mode == "equip":
                game.equip_selected = max(0, game.equip_selected - 1)
            elif game.ui_mode == "equip_category":
                game.equip_category_selected = max(0, game.equip_category_selected - 1)
            elif game.ui_mode == "item":
                game.item_selected = max(0, game.item_selected - 1)
            elif game.ui_mode == "magic":
                game.magic_selected = max(0, game.magic_selected - 1)
            elif game.ui_mode == "leave_confirm":
                game.leave_selected = max(0, game.leave_selected - 1)
        elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
            if game.ui_mode == "save":
                game.save_selected = (game.save_selected + 1) % 3
            elif game.ui_mode == "equip":
                game.equip_selected = game.equip_selected + 1
            elif game.ui_mode == "equip_category":
                game.equip_category_selected = min(1, game.equip_category_selected + 1)
            elif game.ui_mode == "item":
                game.item_selected = game.item_selected + 1
            elif game.ui_mode == "magic":
                game.magic_selected = game.magic_selected + 1
            elif game.ui_mode == "leave_confirm":
                max_opt = 0 if game.leave_step == 2 else 1
                game.leave_selected = min(max_opt, game.leave_selected + 1)
        elif event.key == pygame.K_ESCAPE:
            if game.ui_mode == "equip":
                game.ui_mode = "equip_category"
            else:
                game.ui_mode = None
        elif event.key == pygame.K_RETURN:
            if game.ui_mode == "save":
                game.save_game()
            elif game.ui_mode == "equip":
                game.equip_selected_item()
            elif game.ui_mode == "equip_category":
                game.equip_category = "weapon" if game.equip_category_selected == 0 else "armor"
                game.open_equip_items()
            elif game.ui_mode == "item":
                game.use_item()
            elif game.ui_mode == "magic":
                game.cast_spell()
            elif game.ui_mode == "leave_confirm":
                game.handle_leave_confirm()
        return

    if event.key == pygame.K_UP:
        ctx["esc_selected"] = (ctx["esc_selected"] - 1) % 7
    elif event.key == pygame.K_DOWN:
        ctx["esc_selected"] = (ctx["esc_selected"] + 1) % 7
    elif event.key == pygame.K_ESCAPE:
        ctx["state"] = "game"
    elif event.key == pygame.K_RETURN:
        if ctx["esc_selected"] == 0:
            game.ui_mode = "item"
        elif ctx["esc_selected"] == 1:
            game.ui_mode = "magic"
        elif ctx["esc_selected"] == 2:
            game.open_equip()
        elif ctx["esc_selected"] == 3:
            game.ui_mode = "objective"
        elif ctx["esc_selected"] == 4:
            game.ui_mode = "status"
        elif ctx["esc_selected"] == 5:
            game.open_save()
        elif ctx["esc_selected"] == 6:
            game.open_leave_confirm()


def _handle_game_key(ctx, event):
    game = ctx["game"]
    if game.ui_mode == "dialog":
        if event.key == pygame.K_UP:
            game.dialog_selected = max(0, game.dialog_selected - 1)
        elif event.key == pygame.K_DOWN:
            game.dialog_selected = game.dialog_selected + 1
        elif event.key == pygame.K_RETURN:
            game.dialog_choose()
        elif event.key == pygame.K_ESCAPE:
            game.close_dialog()
        return
    if game.ui_mode == "shop":
        if event.key == pygame.K_UP:
            game.shop_selected = (game.shop_selected - 1) % len(game.shop_items)
        elif event.key == pygame.K_DOWN:
            game.shop_selected = (game.shop_selected + 1) % len(game.shop_items)
        elif event.key == pygame.K_RETURN:
            game.buy_selected_item()
        elif event.key == pygame.K_ESCAPE:
            game.close_shop()
        return

    if event.key == pygame.K_ESCAPE:
        ctx["state"] = "esc_menu"
    if event.key == pygame.K_F12:
        ctx["fullscreen"] = not ctx["fullscreen"]
        if ctx["fullscreen"]:
            ctx["screen"] = pygame.display.set_mode((TILE_SIZE * VIEWPORT, TILE_SIZE * VIEWPORT), pygame.FULLSCREEN)
        else:
            ctx["screen"] = pygame.display.set_mode((TILE_SIZE * VIEWPORT, TILE_SIZE * VIEWPORT))
    if event.key == pygame.K_w:
        game.request_player_move(0, -1)
    elif event.key == pygame.K_s:
        game.request_player_move(0, 1)
    elif event.key == pygame.K_a:
        game.request_player_move(-1, 0)
    elif event.key == pygame.K_d:
        game.request_player_move(1, 0)
    elif event.key == pygame.K_e:
        game.player_interact()


def _handle_mouse(ctx, pos):
    state = ctx["state"]
    if state == "main_menu":
        _handle_mouse_main_menu(ctx, pos)
    elif state == "esc_menu":
        _handle_mouse_esc_menu(ctx, pos)
    elif state == "game":
        _handle_mouse_game(ctx, pos)


def _handle_mouse_main_menu(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    font2 = pygame.font.SysFont('consolas', 32)
    opts = ['new game', 'continue', 'leave', 'credits']
    total_height = len(opts) * 44
    start_y = screen.get_height() // 2 - total_height // 2 + 40
    for i, opt in enumerate(opts):
        surf = font2.render(opt, True, (255, 255, 255))
        x = screen.get_width() // 2 - surf.get_width() // 2
        y = start_y + i * 44
        rect = pygame.Rect(x - 12, y - 4, surf.get_width() + 24, surf.get_height() + 8)
        if rect.collidepoint(mx, my):
            ctx["menu_selected"] = i
            if i == 0:
                ctx["game"] = Game()
                ctx["state"] = "game"
            elif i == 1:
                if not ctx["game"].load_latest_save():
                    ctx["game"] = Game()
                ctx["state"] = "game"
            elif i == 2:
                ctx["running"] = False
            elif i == 3:
                pass
            break


def _handle_mouse_esc_menu(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    game = ctx["game"]
    menu_w = screen.get_width() // 4
    font = pygame.font.SysFont('consolas', 16)
    item_h = font.get_height() + 6
    if mx < menu_w:
        idx = (my - 20) // item_h
        if 0 <= idx < 7:
            ctx["esc_selected"] = idx
            if idx == 0:
                game.ui_mode = "item"
            elif idx == 1:
                game.ui_mode = "magic"
            elif idx == 2:
                game.open_equip()
            elif idx == 3:
                game.ui_mode = "objective"
            elif idx == 4:
                game.ui_mode = "status"
            elif idx == 5:
                game.open_save()
            elif idx == 6:
                game.open_leave_confirm()
    else:
        panel = pygame.Rect(menu_w, 0, screen.get_width() - menu_w, screen.get_height())
        font = pygame.font.SysFont('consolas', 14)
        y = panel.y + 48
        if game.ui_mode == "save":
            for i in range(3):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.save_selected = i
                    game.save_game()
                    break
                y += font.get_height() + 10
        elif game.ui_mode == "equip_category":
            for i in range(2):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.equip_category_selected = i
                    game.equip_category = "weapon" if i == 0 else "armor"
                    game.open_equip_items()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "equip":
            equipables = game.get_equipable_items()
            filtered = [n for n in equipables if game.item_defs.get(n, {}).get("slot") == game.equip_category]
            for i, _ in enumerate(filtered):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.equip_selected = i
                    game.equip_selected_item()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "item":
            items = game.get_item_list()
            for i, _ in enumerate(items):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.item_selected = i
                    game.use_item()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "magic":
            for i, _ in enumerate(game.spells):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.magic_selected = i
                    game.cast_spell()
                    break
                y += font.get_height() + 6
        elif game.ui_mode == "leave_confirm":
            y = panel.y + 48 + font.get_height() + 10
            options = ["yes", "no"] if game.leave_step < 2 else ["ok"]
            for i, _ in enumerate(options):
                rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font.get_height() + 4)
                if rect.collidepoint(mx, my):
                    game.leave_selected = i
                    game.handle_leave_confirm()
                    break
                y += font.get_height() + 6


def _handle_mouse_game(ctx, pos):
    mx, my = pos
    screen = ctx["screen"]
    game = ctx["game"]
    if game.ui_mode == "dialog":
        panel_h = screen.get_height() // 3
        panel = pygame.Rect(0, screen.get_height() - panel_h - 12, screen.get_width(), panel_h)
        img_size = panel_h - 24
        font2 = pygame.font.SysFont('consolas', 14)
        responses = game.dialog_data.get(game.dialog_node, {}).get("responses", [])
        max_width = panel.width - img_size - 36
        text = game.dialog_data.get(game.dialog_node, {}).get("text", "")
        lines = _wrap_text(font2, text, max_width)
        text_y = panel.y + 32 + len(lines) * (font2.get_height() + 4)
        resp_y = panel.bottom - 20 - len(responses) * (font2.get_height() + 6)
        if resp_y < text_y + 8:
            resp_y = text_y + 8
        for i, _ in enumerate(responses):
            rect = pygame.Rect(panel.x + img_size + 8, resp_y - 2, panel.width - img_size - 32, font2.get_height() + 4)
            if rect.collidepoint(mx, my):
                game.dialog_selected = i
                game.dialog_choose()
                break
            resp_y += font2.get_height() + 6
    elif game.ui_mode == "shop":
        panel = pygame.Rect(screen.get_width() // 10, screen.get_height() // 10, screen.get_width() * 8 // 10, screen.get_height() * 8 // 10)
        font2 = pygame.font.SysFont('consolas', 14)
        y = panel.y + 48
        for i, _ in enumerate(game.shop_items):
            rect = pygame.Rect(panel.x + 16, y - 2, panel.width - 32, font2.get_height() + 4)
            if rect.collidepoint(mx, my):
                game.shop_selected = i
                game.buy_selected_item()
                break
            y += font2.get_height() + 6


def _update(ctx, dt):
    game = ctx["game"]
    if ctx["state"] == "game" and getattr(game, 'death_timer', None) is not None:
        game.death_timer -= dt
        if game.death_timer <= 0:
            pygame.quit()
            ctx["running"] = False
            return
    if ctx["state"] == "game" and getattr(game, 'death_timer', None) is None:
        game.update(player_tick=False)
        game.update_time(dt)


def _render(ctx):
    if ctx["state"] == "main_menu":
        draw_main_menu(ctx["screen"], ctx["menu_selected"])
    elif ctx["state"] == "esc_menu":
        draw(ctx["game"], ctx["screen"])
        draw_esc_menu(ctx["screen"], ctx["esc_selected"], ctx["game"])
    else:
        draw(ctx["game"], ctx["screen"])
        draw_player_ui(ctx["game"], ctx["screen"])
    if ctx["game"].request_quit:
        ctx["running"] = False
    pygame.display.flip()
