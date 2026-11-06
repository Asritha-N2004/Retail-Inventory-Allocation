import os, random, math
from datetime import date, timedelta
from sqlalchemy import select, func
from .database import *
from .security import passwords


def seed():
    rng = random.Random(42)
    with Session.begin() as s:
        if s.scalar(select(func.count(Product.id))):
            return
        roles = [
            "Administrator",
            "Inventory Manager",
            "Warehouse Manager",
            "Store Manager",
            "Analyst",
        ]
        s.add_all([Role(name=r) for r in roles])
        s.flush()
        password = os.getenv("DEMO_PASSWORD", "RetailDemo!2026")
        s.add_all(
            [
                User(username=n, password_hash=passwords.hash(password), role=r)
                for n, r in [
                    ("admin", roles[0]),
                    ("manager", roles[1]),
                    ("analyst", roles[-1]),
                ]
            ]
        )
        cities = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai"]
        locations = []
        for i in range(22):
            kind = (
                "Warehouse"
                if i < 5
                else (
                    "Distribution Center"
                    if i == 5
                    else "Physical Store" if i < 21 else "Online Fulfillment Center"
                )
            )
            locations.append(
                Location(
                    location_name=f"{cities[i%5]} {kind} {i+1:02}",
                    location_type=kind,
                    region=cities[i % 5],
                    storage_capacity=100000 if i < 6 else 12000 if i < 21 else 50000,
                    fulfillment_capacity=8000 if i == 21 else 5000,
                    latitude=12 + i * 0.6,
                    longitude=72 + i * 0.2,
                )
            )
        s.add_all(locations)
        categories = {
            "Electronics": [
                "Wireless Headphones",
                "Smart Watch",
                "Bluetooth Speaker",
                "USB-C Hub",
            ],
            "Clothing": ["Cotton Tee", "Denim Jeans", "Linen Shirt", "Running Jacket"],
            "Grocery": ["Organic Coffee", "Basmati Rice", "Rolled Oats", "Green Tea"],
            "Home Appliances": [
                "Air Fryer",
                "Electric Kettle",
                "Table Fan",
                "Hand Blender",
            ],
            "Personal Care": ["Face Cleanser", "Body Lotion", "Sunscreen", "Shampoo"],
            "Accessories": [
                "Travel Backpack",
                "Leather Wallet",
                "Sunglasses",
                "Phone Case",
            ],
        }
        products = []
        for i in range(100):
            cat = list(categories)[i % 6]
            cost = rng.randint(50, 2000)
            products.append(
                Product(
                    sku=f"RTL-{i+1:04}",
                    product_name=f"{categories[cat][i//6%4]} · {i//24+1}",
                    category=cat,
                    unit_cost=cost,
                    selling_price=round(cost * 1.45, 2),
                )
            )
        s.add_all(products)
        s.flush()
        stock = []
        sales = []
        end = date(2026, 11, 5)
        for p in products:
            for loc in locations:
                source = loc.id <= 6
                stock.append(
                    Inventory(
                        product_id=p.id,
                        location_id=loc.id,
                        quantity_on_hand=(
                            rng.randint(100, 350) if source else rng.randint(0, 100)
                        ),
                        quantity_reserved=rng.randint(0, 3) if source else 0,
                        safety_stock=10 if source else 5,
                        reorder_level=25 if source else 15,
                    )
                )
                if source:
                    continue
                base = 1 + (p.id % 7) * 0.5 + (4 if loc.id == 22 else 0)
                for day in range(365):
                    d = end - timedelta(days=364 - day)
                    promotion = day % 60 < 5
                    qty = max(
                        0,
                        round(
                            base
                            * (1 + 0.3 * math.sin(day * 2 * math.pi / 365))
                            * (1.5 if promotion else 1)
                            + rng.gauss(0, 1.5)
                        ),
                    )
                    sales.append(
                        dict(
                            product_id=p.id,
                            location_id=loc.id,
                            sales_channel="online" if loc.id == 22 else "offline",
                            quantity_sold=qty,
                            selling_price=p.selling_price,
                            promotion_flag=promotion,
                            sale_date=d.isoformat(),
                        )
                    )
        s.add_all(stock)
        s.bulk_insert_mappings(Sale, sales)
        s.add(
            Notification(
                message="Network initialized: 100 products, 22 locations and 365 days of sales."
            )
        )
        s.add(
            Setting(
                key="optimization",
                value={
                    "stockout_penalty": 25,
                    "holding_cost": 0.15,
                    "reallocation_cost": 0.2,
                    "online_priority": 1.2,
                },
            )
        )
        s.add_all(
            [
                Supplier(name=f"{city} Supply Co.", lead_days=3 + i)
                for i, city in enumerate(cities)
            ]
        )


if __name__ == "__main__":
    migrate()
    seed()
