from src.pricing import calculate_discount


def test_calculate_discount_premium():
    base_price = 100.0
    discounted = calculate_discount(base_price, "PREMIUM")
    assert discounted == 80.0


def test_calculate_discount_gold():
    base_price = 100.0
    discounted = calculate_discount(base_price, "GOLD")
    assert discounted == 85.0


def test_calculate_discount_standard():
    base_price = 100.0
    discounted = calculate_discount(base_price, "STANDARD")
    assert discounted == 100.0
