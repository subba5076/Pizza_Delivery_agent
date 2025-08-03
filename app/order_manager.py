import json
import os

menu_path = os.path.join(os.path.dirname(__file__), "menu.json")
with open(menu_path, "r") as f:
    MENU = json.load(f)

def find_item(category, item_id):
    for item in MENU.get(category, []):
        if item["id"] == item_id:
            return item
    return None

def calculate_price(order_items):
    total = 0
    for item in order_items:
        # Determine category based on item name or explicit category field
        category = None
        if "category" in item: # Prefer explicit category if available from agen.py
            category = item["category"]
        elif "pizza" in item["name"].lower(): # Fallback to name if category not explicit
            category = "pizzas"
        elif "pasta" in item["name"].lower():
            category = "pastas"
        elif "drink" in item["name"].lower() or item["category"] == "drinks": # Handle drinks
            category = "drinks"
        else:
            return None, f"Unknown item category: {item['name']}"

        menu_item = find_item(category, item.get("id"))
        if not menu_item:
            return None, f"Item not found in menu: {item['name']}"

        price = 0

        if category in ["pizzas", "pastas"]:
            # Find size price for pizzas and pastas
            size_info = next((s for s in menu_item["sizes"] if s["size"].lower() == item.get("size", "").lower()), None)
            if not size_info:
                return None, f"Invalid or missing size for {item['name']}: {item.get('size')}"
            price = size_info["price"]

            # Price adjustments: crust, protein, gluten free etc.
            if "crust" in item:
                crust = item["crust"]
                if crust == "gluten-free" and MENU.get("gluten_free_options", {}).get("pizza_crust", {}).get("available", False):
                    price += MENU["gluten_free_options"]["pizza_crust"]["price_adjustment"]

            if "protein" in item and "protein_options" in menu_item:
                prot = item["protein"]
                protein_opt = next((p for p in menu_item["protein_options"] if p["name"] == prot), None)
                if protein_opt:
                    price += protein_opt.get("price_adjustment", 0)

            # Add-ons for pasta
            if category == "pastas" and "add_ons" in menu_item and "addons" in item:
                for addon in item["addons"]:
                    addon_info = next((a for a in menu_item["add_ons"] if a["name"] == addon), None)
                    if addon_info:
                        price += addon_info["price"]
        elif category == "drinks":
            # For drinks, assume a direct price
            if "price" in menu_item:
                price = menu_item["price"]
            else:
                return None, f"Price information missing for drink: {item['name']}"
        
        # Multiply by quantity
        total += price * item.get("quantity", 1)

    return total, None