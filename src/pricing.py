def calculate_discount(price: float, tier: str) -> float:
    """Calculate discounted price based on customer membership tier."""
    if tier == "PREMIUM":
        return price * 0.80  # 20% discount on main
    elif tier == "GOLD":
        return price * 0.85  # 15% discount
    elif tier == "SILVER":
        return price * 0.90  # 10% discount
    return price
