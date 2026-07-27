from adapters.base import BaseAdapter
import random
import asyncio

class MockAdapter(BaseAdapter):
    async def fetch_orders(self) -> list[dict]:
        await asyncio.sleep(0.5)
        orders = []
        # Список возможных UN-номеров для опасных грузов (иногда None)
        un_numbers = [None, 1203, 1789, 1830, 1987, 1993, 2020, 2247, 3262, 3291, 3462]
        for i in range(5):
            un = random.choice(un_numbers)
            orders.append({
                "id": f"mock_{i}",
                "platform": "mock",
                "origin_country": random.choice(["NL", "BE", "DE"]),
                "origin_city": random.choice(["Amsterdam", "Rotterdam", "Brussels", "Berlin", "Munich"]),
                "dest_country": random.choice(["DE", "FR", "UK", "IT"]),
                "dest_city": random.choice(["Munich", "Paris", "London", "Milan", "Hamburg"]),
                "weight_kg": random.randint(100, 1200),
                "volume_m3": round(random.uniform(1.0, 6.0), 1),   # <-- добавили объём
                "pallets": random.randint(1, 4),
                "price_eur": random.randint(80, 500),
                "un_number": un,   # <-- добавили UN-номер
                "raw": {}
            })
        return orders