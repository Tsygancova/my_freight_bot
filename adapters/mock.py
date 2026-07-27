from adapters.base import BaseAdapter
import random
import asyncio

class MockAdapter(BaseAdapter):
    async def fetch_orders(self) -> list[dict]:
        await asyncio.sleep(0.5)
        orders = []
        for i in range(5):
            orders.append({
                "id": f"mock_{i}",
                "platform": "mock",
                "origin_country": random.choice(["NL", "BE", "DE"]),
                "origin_city": random.choice(["Amsterdam", "Rotterdam", "Brussels", "Berlin"]),
                "dest_country": random.choice(["DE", "FR", "UK", "IT"]),
                "dest_city": random.choice(["Munich", "Paris", "London", "Milan"]),
                "weight_kg": random.randint(100, 1200),
                "volume_m3": round(random.uniform(1.0, 6.0), 1),
                "pallets": random.randint(1, 4),
                "price_eur": random.randint(80, 500),
                "raw": {}
            })
        return orders