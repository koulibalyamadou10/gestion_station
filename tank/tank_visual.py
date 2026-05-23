from decimal import Decimal


def tank_usage_percent(quantity, max_capacity):
    if max_capacity is None or max_capacity <= 0:
        return None
    qty = quantity or Decimal("0")
    return float(min((qty / max_capacity) * Decimal("100"), Decimal("100")))


def build_tank_visual_item(
    *,
    name,
    product,
    quantity,
    max_capacity,
    station_name="",
    detail_label="",
    detail_before=None,
    detail_after=None,
    gauge_quantity=None,
    usage_label="de remplissage",
):
    gauge_qty = gauge_quantity if gauge_quantity is not None else quantity
    return {
        "name": name,
        "product": product,
        "actual_quantity": quantity or Decimal("0"),
        "max_capacity": max_capacity,
        "usage_percent": tank_usage_percent(gauge_qty, max_capacity),
        "station_name": station_name,
        "detail_label": detail_label,
        "detail_before": detail_before,
        "detail_after": detail_after,
        "usage_label": usage_label,
    }
