from adapters.base import BaseAdapter
from adapters.mock import MockAdapter

def get_adapter(platform_config: dict) -> BaseAdapter:
    name = platform_config["name"]
    if name == "mock":
        return MockAdapter(platform_config.get("credentials", {}))
    else:
        raise ValueError(f"Unknown platform: {name}")