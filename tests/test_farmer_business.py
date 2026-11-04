import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "System_IL2D"))

from mods.farmer_mod.functions import business, state
from mods.farmer_mod.functions import ui_actions, rendering
import pygame
from core.functions.world.map import GameMap
from core.functions.support.utils import resolve_map_file


class FarmerBusinessTests(unittest.TestCase):
    def setUp(self):
        self.cfg = state.load_farm_cfg()
        self.data = state.default_state(self.cfg)
        business.normalize(self.data, self.cfg)

    def test_seed_purchase_and_automatic_harvest(self):
        balance = self.data["si_currency"]
        self.assertTrue(business.buy_seed(self.data, self.cfg, "rice"))
        self.assertEqual(self.data["si_currency"], balance - self.cfg["crops"]["rice"]["seed_price"])
        business.update_farm(self.data, self.cfg, 0.1)
        self.assertEqual(self.data["seeds"]["rice"], 0)
        self.assertEqual(len(self.data["planted"]), 1)
        business.update_farm(self.data, self.cfg, 10)
        self.assertEqual(self.data["crops"]["rice"], 2)
        self.assertFalse(self.data["planted"])

    def test_ingredient_packs_use_main_currency(self):
        messages = []
        game = type("GameStub", (), {"shop_selected": 4, "ui_mode": "farm_shop",
                                     "money": 25,
                                     "push_message": lambda self, message: messages.append(message)})()
        ctx = {"game": game, "farmer_mod": {"cfg": self.cfg, "data": self.data}}
        si_balance = self.data["si_currency"]
        rice_before = self.data["crops"]["rice"]
        self.assertEqual(ui_actions.rows(ctx)[4][0], "ingredient:rice")
        key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        self.assertTrue(ui_actions.handle_key(ctx, key))
        self.assertEqual(game.money, 5)
        self.assertEqual(self.data["crops"]["rice"], rice_before + 10)
        self.assertEqual(self.data["si_currency"], si_balance)
        self.assertTrue(ui_actions.handle_key(ctx, key))
        self.assertEqual(game.money, 5)
        self.assertEqual(self.data["crops"]["rice"], rice_before + 10)
        self.assertIn("主貨幣不足", messages)

    def test_cooks_are_independent_and_queue_is_bounded(self):
        self.data["crops"].update(rice=12, wheat=12)
        restaurant = self.data["restaurant"]
        recipes = list(self.cfg["recipes"])
        for index, recipe in enumerate(recipes):
            self.assertTrue(business.assign_recipe(self.data, self.cfg, index, recipe))
            for _ in range(3):
                self.assertTrue(business.queue_dish(self.data, self.cfg, index))
            self.assertFalse(business.queue_dish(self.data, self.cfg, index))
        self.assertTrue(business.start_business(self.data, self.cfg))
        self.assertFalse(business.start_business(self.data, self.cfg))
        business.update_restaurant(self.data, self.cfg, 0.1)
        self.assertEqual([cook["state"] for cook in restaurant["cooks"]], ["COOKING"] * 3)
        self.assertEqual([len(cook["queue"]) for cook in restaurant["cooks"]], [2] * 3)
        self.assertTrue(all(value >= 0 for value in self.data["crops"].values()))

    def test_eight_tables_si_cooldown_and_single_payment(self):
        restaurant = self.data["restaurant"]
        for _ in range(8):
            business._spawn_customer(restaurant, self.cfg)
        self.assertEqual(sum(table["state"] == "OCCUPIED" for table in restaurant["tables"]), 8)
        business._spawn_customer(restaurant, self.cfg)
        self.assertEqual(sum(table["state"] != "EMPTY" for table in restaurant["tables"]), 8)
        table = restaurant["tables"][0]
        table["state"] = "WAITING_FOR_FOOD"
        recipe = table["order"]["recipe"]
        restaurant["finished_dishes"].append(recipe)
        business._update_si(self.data, self.cfg, restaurant, 0)
        self.assertEqual(restaurant["si"]["state"], "MOVING")
        business._update_si(self.data, self.cfg, restaurant, self.cfg["si_move_seconds"])
        business._update_si(self.data, self.cfg, restaurant, self.cfg["si_work_seconds"])
        self.assertEqual(table["state"], "EATING")
        self.assertEqual(restaurant["si"]["state"], "COOLDOWN")
        business._update_si(self.data, self.cfg, restaurant, self.cfg["si_cooldown_seconds"])
        table["timer"] = 0
        business._update_si(self.data, self.cfg, restaurant, 0)
        business._update_si(self.data, self.cfg, restaurant, self.cfg["si_move_seconds"])
        business._update_si(self.data, self.cfg, restaurant, self.cfg["si_work_seconds"])
        price = self.cfg["recipes"][recipe]["price"]
        self.assertEqual(restaurant["revenue"], price)
        self.assertEqual(restaurant["completed_orders"], 1)
        business._update_si(self.data, self.cfg, restaurant, 10)
        self.assertEqual(restaurant["revenue"], price)

    def test_closing_cancels_orders_and_save_roundtrip(self):
        self.assertTrue(business.start_business(self.data, self.cfg))
        business.update_restaurant(self.data, self.cfg, 180)
        result = self.data["restaurant"]["result"]
        self.assertFalse(self.data["restaurant"]["business_active"])
        self.assertEqual(self.data["restaurant"]["remaining"], 0)
        self.assertEqual(result["balance"], self.data["si_currency"])
        self.assertTrue(all(t["state"] == "EMPTY" for t in self.data["restaurant"]["tables"]))
        with tempfile.TemporaryDirectory() as directory:
            original = state.SAVE_DIR
            state.SAVE_DIR = directory
            try:
                game = type("GameStub", (), {"last_save_slot": 2})()
                ctx = {"farmer_mod": {"cfg": self.cfg, "data": self.data}}
                state.save_state(game, ctx)
                loaded = {"farmer_mod": {"cfg": self.cfg, "data": state.default_state(self.cfg)}}
                state.load_state(game, loaded)
                self.assertEqual(loaded["farmer_mod"]["data"]["si_currency"], self.data["si_currency"])
                self.assertEqual(loaded["farmer_mod"]["data"]["restaurant"]["result"], result)
            finally:
                state.SAVE_DIR = original

    def test_management_controls_and_interrupted_session(self):
        game = type("GameStub", (), {"shop_selected": 2, "ui_mode": "farm_shop",
                                     "push_message": lambda self, message: None,
                                     "last_save_slot": 3})()
        ctx = {"game": game, "farmer_mod": {"cfg": self.cfg, "data": self.data}}
        self.assertTrue(ui_actions.handle_key(ctx, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)))
        self.assertEqual(self.data["seeds"]["rice"], 1)
        business.start_business(self.data, self.cfg)
        with tempfile.TemporaryDirectory() as directory:
            original = state.SAVE_DIR
            state.SAVE_DIR = directory
            try:
                state.save_state(game, ctx)
                loaded = {"farmer_mod": {"cfg": self.cfg, "data": state.default_state(self.cfg)}}
                state.load_state(game, loaded)
                recovered = loaded["farmer_mod"]["data"]
                self.assertFalse(recovered["restaurant"]["business_active"])
                self.assertEqual(recovered["seeds"]["rice"], 1)
                self.assertEqual(recovered["si_currency"], self.data["si_currency"])
            finally:
                state.SAVE_DIR = original

    def test_two_farm_maps_and_field_production(self):
        hub = GameMap(resolve_map_file("farm_01.json"))
        field = GameMap(resolve_map_file("farm_02.json"))
        self.assertEqual((hub.w, hub.h), (16, 22))
        self.assertEqual((field.w, field.h), (24, 24))
        self.assertEqual(hub.grid[8][15], "03")
        self.assertEqual(field.grid[8][0], "03")
        self.data["owned_land"] = len(self.cfg["plots"]) + 1
        self.data["seeds"]["rice"] = len(self.cfg["plots"]) + 1
        business.update_farm(self.data, self.cfg, 0.1)
        self.assertIn("field:5,5", self.data["planted"])

    def test_management_panel_hides_farm_overlay(self):
        game = type("GameStub", (), {"ui_mode": "farm_shop", "shop_selected": 0,
                                     "map": type("MapStub", (), {"name": "farm_01.json"})()})()
        ctx = {"game": game, "farmer_mod": {"cfg": self.cfg, "data": self.data}}
        with patch.object(rendering, "draw_si_shop") as shop, patch.object(rendering, "draw_farm_land_overlay") as land:
            rendering.render(ctx, object())
        shop.assert_called_once()
        land.assert_not_called()

    def test_si_shop_only_intercepts_nearby_interaction(self):
        player = type("PlayerStub", (), {"x": 8, "y": 18})()
        game = type("GameStub", (), {"map": type("MapStub", (), {"name": "farm_01.json"})(),
                                     "player": player, "ui_mode": None, "shop_selected": 0})()
        ctx = {"game": game}
        self.assertTrue(ui_actions.farm_key(ctx, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)))
        self.assertEqual(game.ui_mode, "farm_shop")
        player.y = 3
        game.ui_mode = None
        self.assertFalse(ui_actions.farm_key(ctx, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)))

    def test_restaurant_map_music_and_kitchen_interaction(self):
        from core.functions.audio.music_resolver import resolve_current_music
        from core.functions.support.asset_resolver import resolve_audio_candidates
        restaurant_map = GameMap(resolve_map_file("farm_restaurant.json"))
        self.assertEqual((restaurant_map.w, restaurant_map.h), (20, 18))
        self.assertEqual(len(business.COOK_POSITIONS), 3)
        self.assertEqual(len(business.TABLE_POSITIONS), 8)
        for name in ("farm_01.json", "farm_02.json", "farm_restaurant.json"):
            game = type("GameStub", (), {"map": GameMap(resolve_map_file(name))})()
            self.assertTrue(resolve_audio_candidates(resolve_current_music(game)))
        player = type("PlayerStub", (), {"x": 5, "y": 5})()
        game = type("GameStub", (), {"map": restaurant_map, "player": player,
                                     "ui_mode": None,
                                     "push_message": lambda self, message: None})()
        ctx = {"game": game, "farmer_mod": {"cfg": self.cfg, "data": self.data}}
        self.assertTrue(ui_actions.farm_key(ctx, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)))
        self.assertEqual(game.ui_mode, "farm_kitchen")
        self.assertEqual(ctx["farmer_mod"]["kitchen_index"], 0)
        ctx["farmer_mod"]["kitchen_selected"] = 1
        self.assertTrue(ui_actions.handle_kitchen_key(ctx, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)))
        self.assertEqual(len(self.data["restaurant"]["cooks"][0]["queue"]), 1)

    def test_asking_si_starts_business_and_enters_restaurant(self):
        class GameStub:
            def __init__(self):
                self.map = GameMap(resolve_map_file("farm_01.json"))
                self.player = type("PlayerStub", (), {"x": 8, "y": 18})()
                self.ui_mode = "farm_shop"
                self.shop_selected = 0
                self.banner = {"text": ""}
                self.messages = []

            def load_map(self, name):
                self.map = GameMap(resolve_map_file(name))

            def push_message(self, message):
                self.messages.append(message)

        game = GameStub()
        ctx = {"game": game, "farmer_mod": {"cfg": self.cfg, "data": self.data}}
        self.assertTrue(ui_actions.handle_key(ctx, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)))
        self.assertEqual(game.map.name, "farm_restaurant.json")
        self.assertTrue(self.data["restaurant"]["business_active"])
        self.assertEqual(game.banner["text"], "現正進入：緣緣莊餐廳")
        self.assertIsNone(game.ui_mode)


if __name__ == "__main__":
    unittest.main()
