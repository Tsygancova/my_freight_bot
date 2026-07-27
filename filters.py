def match_filter(order: dict, user_filter: dict) -> bool:
    if not user_filter:
        return True
    
    if user_filter.get("origin_countries"):
        if order.get("origin_country") not in user_filter["origin_countries"]:
            return False
    if user_filter.get("dest_countries"):
        if order.get("dest_country") not in user_filter["dest_countries"]:
            return False
    
    max_w = user_filter.get("max_weight_kg")
    if max_w and order.get("weight_kg", 0) > max_w:
        return False
    
    max_p = user_filter.get("max_pallets")
    if max_p and order.get("pallets", 0) > max_p:
        return False
    
    min_p = user_filter.get("min_price_eur")
    if min_p and order.get("price_eur", 0) < min_p:
        return False
    
    return True