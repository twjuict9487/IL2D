"""Automatic farming and the small restaurant simulation for 緣緣莊."""

TABLE_COUNT = 8
COOK_COUNT = 3
QUEUE_LIMIT = 3
COOK_POSITIONS = [(5, 4), (10, 4), (15, 4)]
TABLE_POSITIONS = [(4, 8), (8, 8), (12, 8), (16, 8),
                   (4, 12), (8, 12), (12, 12), (16, 12)]
KITCHEN_POSITION = (10, 5)


def normalize(data, cfg):
    crops = cfg["crops"]
    recipes = cfg["recipes"]
    if len(crops) > 10 or len(recipes) > 5:
        raise ValueError("Farmer Mod supports at most 10 crops and 5 recipes")
    data["si_currency"] = max(0, int(data.get("si_currency", 100)))
    for key in ("seeds", "crops"):
        stock = data.setdefault(key, {})
        for crop in crops:
            stock[crop] = max(0, int(stock.get(crop, 0)))
    data.setdefault("planted", {})
    data.setdefault("farm_elapsed", 0.0)
    restaurant = data.setdefault("restaurant", {})
    restaurant.setdefault("business_active", False)
    restaurant.setdefault("remaining", 0.0)
    restaurant.setdefault("spawn_elapsed", 0.0)
    restaurant.setdefault("revenue", 0)
    restaurant.setdefault("completed_orders", 0)
    restaurant.setdefault("result", None)
    restaurant.setdefault("next_order_id", 1)
    tables = restaurant.setdefault("tables", [])
    while len(tables) < TABLE_COUNT:
        tables.append({"state": "EMPTY", "order": None, "dish": None, "timer": 0.0})
    del tables[TABLE_COUNT:]
    cooks = restaurant.setdefault("cooks", [])
    while len(cooks) < COOK_COUNT:
        cooks.append({"assignment": next(iter(recipes)), "queue": [],
                      "active": None, "progress": 0.0, "state": "IDLE"})
    del cooks[COOK_COUNT:]
    for cook in cooks:
        cook.setdefault("assignment", next(iter(recipes)))
        cook.setdefault("queue", [])
        cook.setdefault("active", None)
        cook.setdefault("progress", 0.0)
        cook.setdefault("state", "IDLE")
        cook["queue"] = [r for r in cook["queue"] if r in recipes][:QUEUE_LIMIT]
    si = restaurant.setdefault("si", {})
    si.setdefault("state", "IDLE")
    si.setdefault("task", None)
    si.setdefault("timer", 0.0)
    si.setdefault("location", "kitchen")
    restaurant.setdefault("finished_dishes", [])
    return restaurant


def buy_seed(data, cfg, crop):
    definition = cfg["crops"].get(crop)
    if not definition:
        return False
    price = int(definition["seed_price"])
    if data["si_currency"] < price:
        return False
    data["si_currency"] -= price
    data["seeds"][crop] += 1
    return True


def buy_ingredients(data, cfg, crop, money):
    definition = cfg["crops"].get(crop)
    if not definition:
        return None
    price = int(definition.get("ingredient_pack_price", 0))
    quantity = int(definition.get("ingredient_pack_size", 0))
    if price <= 0 or quantity <= 0 or money < price:
        return None
    data["crops"][crop] += quantity
    return price


def update_farm(data, cfg, dt):
    data["farm_elapsed"] += max(0.0, dt)
    planted = data["planted"]
    first_plots = [(f"{int(x)},{int(y)}", x, y) for x, y in cfg.get("plots", [])]
    field_plots = [(f"field:{int(x)},{int(y)}", x, y) for x, y in cfg.get("field_plots", [])]
    plots = (first_plots + field_plots)[:max(0, int(data.get("owned_land", 0)))]
    for key, x, y in plots:
        entry = planted.get(key)
        if entry:
            crop = entry.get("crop")
            definition = cfg["crops"].get(crop)
            if not definition:
                planted.pop(key, None)
                continue
            entry["elapsed"] = float(entry.get("elapsed", 0.0)) + max(0.0, dt)
            if entry["elapsed"] >= float(definition["growth_time"]):
                data["crops"][crop] += int(definition["harvest_yield"])
                planted.pop(key, None)
        if key not in planted:
            for crop in cfg["crops"]:
                if data["seeds"][crop] > 0:
                    data["seeds"][crop] -= 1
                    planted[key] = {"crop": crop, "elapsed": 0.0}
                    break


def assign_recipe(data, cfg, cook_index, recipe):
    restaurant = normalize(data, cfg)
    if recipe not in cfg["recipes"] or not 0 <= cook_index < COOK_COUNT:
        return False
    restaurant["cooks"][cook_index]["assignment"] = recipe
    return True


def queue_dish(data, cfg, cook_index, recipe=None):
    restaurant = normalize(data, cfg)
    if not 0 <= cook_index < COOK_COUNT:
        return False
    cook = restaurant["cooks"][cook_index]
    recipe = recipe or cook["assignment"]
    if recipe not in cfg["recipes"] or len(cook["queue"]) + int(cook["active"] is not None) >= QUEUE_LIMIT:
        return False
    cook["queue"].append(recipe)
    return True


def start_business(data, cfg):
    restaurant = normalize(data, cfg)
    if restaurant["business_active"]:
        return False
    restaurant.update(business_active=True, remaining=180.0, spawn_elapsed=0.0,
                      revenue=0, completed_orders=0, result=None)
    restaurant["finished_dishes"] = []
    restaurant["si"] = {"state": "IDLE", "task": None, "timer": 0.0, "location": "kitchen"}
    for table in restaurant["tables"]:
        table.update(state="EMPTY", order=None, dish=None, timer=0.0)
    return True


def close_business(data, cfg):
    restaurant = normalize(data, cfg)
    restaurant["business_active"] = False
    restaurant["remaining"] = 0.0
    restaurant["result"] = {"orders": restaurant["completed_orders"],
                            "revenue": restaurant["revenue"],
                            "balance": data["si_currency"]}
    for table in restaurant["tables"]:
        table.update(state="EMPTY", order=None, dish=None, timer=0.0)
    restaurant["finished_dishes"] = []
    for cook in restaurant["cooks"]:
        cook.update(queue=[], active=None, progress=0.0, state="IDLE")
    restaurant["si"].update(state="IDLE", task=None, timer=0.0)


def _spawn_customer(restaurant, cfg):
    table = next((t for t in restaurant["tables"] if t["state"] == "EMPTY"), None)
    if table is None:
        return
    recipes = list(cfg["recipes"])
    order_id = restaurant["next_order_id"]
    restaurant["next_order_id"] += 1
    table.update(state="OCCUPIED", order={"id": order_id,
                 "recipe": recipes[(order_id - 1) % len(recipes)]}, dish=None, timer=1.0)


def _update_cooks(data, cfg, restaurant, dt):
    for cook in restaurant["cooks"]:
        if cook["active"] is None and cook["queue"]:
            recipe = cook["queue"][0]
            requirements = cfg["recipes"][recipe]["ingredients"]
            if all(data["crops"].get(crop, 0) >= count for crop, count in requirements.items()):
                for crop, count in requirements.items():
                    data["crops"][crop] -= count
                cook["active"] = cook["queue"].pop(0)
                cook["progress"] = 0.0
                cook["state"] = "COOKING"
            else:
                cook["state"] = "BLOCKED"
        if cook["active"] is not None:
            cook["progress"] += dt
            if cook["progress"] >= cfg["recipes"][cook["active"]]["cook_seconds"]:
                restaurant["finished_dishes"].append(cook["active"])
                cook["active"] = None
                cook["progress"] = 0.0
                cook["state"] = "IDLE"


def _next_si_task(restaurant):
    for index, table in enumerate(restaurant["tables"]):
        if table["state"] == "EATING" and table["timer"] <= 0:
            return {"type": "clear", "table": index}
    for index, table in enumerate(restaurant["tables"]):
        if table["state"] == "WAITING_FOR_FOOD" and table["order"]:
            recipe = table["order"]["recipe"]
            if recipe in restaurant["finished_dishes"]:
                restaurant["finished_dishes"].remove(recipe)
                return {"type": "serve", "table": index, "recipe": recipe}
    return None


def _update_si(data, cfg, restaurant, dt):
    si = restaurant["si"]
    if si["state"] == "IDLE":
        task = _next_si_task(restaurant)
        if task:
            si.update(state="MOVING", task=task, timer=float(cfg["si_move_seconds"]))
        return
    si["timer"] -= dt
    if si["timer"] > 0:
        return
    if si["state"] == "MOVING":
        si["location"] = f"table {si['task']['table'] + 1}"
        si.update(state="WORKING", timer=float(cfg["si_work_seconds"]))
    elif si["state"] == "WORKING":
        task = si["task"]
        table = restaurant["tables"][task["table"]]
        if task["type"] == "serve" and table["state"] == "WAITING_FOR_FOOD":
            table.update(state="EATING", dish=task["recipe"], timer=4.0)
        elif task["type"] == "clear" and table["state"] == "EATING":
            price = int(cfg["recipes"][table["dish"]]["price"])
            data["si_currency"] += price
            restaurant["revenue"] += price
            restaurant["completed_orders"] += 1
            table.update(state="EMPTY", order=None, dish=None, timer=0.0)
        si.update(state="COOLDOWN", task=None, timer=float(cfg["si_cooldown_seconds"]))
    else:
        si.update(state="IDLE", timer=0.0, location="kitchen")


def update_restaurant(data, cfg, dt):
    restaurant = normalize(data, cfg)
    if not restaurant["business_active"]:
        return
    dt = min(max(0.0, float(dt)), restaurant["remaining"])
    restaurant["remaining"] -= dt
    restaurant["spawn_elapsed"] += dt
    interval = max(0.1, float(cfg["customer_interval"]))
    while restaurant["remaining"] > 0 and restaurant["spawn_elapsed"] >= interval:
        restaurant["spawn_elapsed"] -= interval
        _spawn_customer(restaurant, cfg)
    for table in restaurant["tables"]:
        if table["state"] == "OCCUPIED":
            table["timer"] -= dt
            if table["timer"] <= 0:
                table["state"] = "WAITING_FOR_FOOD"
        elif table["state"] == "EATING":
            table["timer"] -= dt
    _update_cooks(data, cfg, restaurant, dt)
    _update_si(data, cfg, restaurant, dt)
    if restaurant["remaining"] <= 0:
        close_business(data, cfg)
