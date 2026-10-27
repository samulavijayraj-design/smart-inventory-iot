"""Inventory model, load-cell model and reorder logic (no network code)."""
import math
import random

import config


def safety_stock(item, z=config.Z_SERVICE):
    """SS = z * sigma_d * sqrt(L)  (Formula 2 in the report)."""
    return z * item["sd"] * math.sqrt(item["L"])


def reorder_point(item, z=config.Z_SERVICE):
    """ROP = d * L + SS  (Formula 1 in the report)."""
    return item["d"] * item["L"] + safety_stock(item, z)


def periodic_reorder_level(item, review, z=config.Z_SERVICE):
    """Reorder level of a periodic review: protection interval R + L."""
    t = review + item["L"]
    return item["d"] * t + z * item["sd"] * math.sqrt(t)


class DemandGenerator:
    """Daily demand ~ N(d, sd), truncated at 0, spread over the shift."""

    def __init__(self, seed):
        self.rng = random.Random(seed)

    def day(self, item):
        total = max(0, round(self.rng.gauss(item["d"], item["sd"])))
        hourly = [0] * config.HOURS_PER_DAY
        for _ in range(total):
            hourly[self.rng.randrange(config.HOURS_PER_DAY)] += 1
        return hourly


class LoadCell:
    """Weighing shelf: part-weight variation + averaged reading noise + drift."""

    def __init__(self, item, seed):
        self.item = item
        self.rng = random.Random(seed)
        self.drift = 0.0

    def new_day(self):
        self.drift += self.rng.gauss(0, config.DRIFT_PER_DAY_G)

    def measure(self, true_qty):
        w, cv = self.item["unit_g"], self.item["cv"]
        parts = self.rng.gauss(true_qty * w, math.sqrt(true_qty) * cv * w) if true_qty else 0.0
        noise = self.rng.gauss(0, config.READING_NOISE_G / math.sqrt(config.READINGS_PER_MEASUREMENT))
        return parts + noise + self.drift

    def to_quantity(self, weight_g):
        return max(0, round(weight_g / self.item["unit_g"]))


class ReorderLogic:
    """Continuous review: one open order at a time, alert when qty <= ROP."""

    def __init__(self, item):
        self.item = item
        self.rop = reorder_point(item)
        self.open_order = False

    def on_measurement(self, qty):
        """Return the order quantity to place (0 if no reorder is needed)."""
        if not self.open_order and qty <= self.rop:
            self.open_order = True
            return self.item["Q"]
        return 0

    def on_delivery(self):
        self.open_order = False


def simulate_manual(item, seed, review=config.REVIEW_PERIOD_MANUAL):
    """Baseline: weekly manual count, reorder when counted stock <= level."""
    demand = DemandGenerator(seed)
    rng = random.Random(seed + 7)
    level = periodic_reorder_level(item, review)
    stock = round(level + item["Q"])
    pipeline = {}
    unmet = demanded = inv_sum = steps = 0
    for day in range(config.WORKING_DAYS):
        stock += pipeline.pop(day, 0)
        if day % review == 0:
            counted = stock * (1 + rng.gauss(0, config.MANUAL_COUNT_ERROR))
            if counted <= level and not any(d > day for d in pipeline):
                pipeline[day + item["L"]] = item["Q"]
        for h in demand.day(item):
            served = min(stock, h)
            unmet += h - served
            demanded += h
            stock -= served
            inv_sum += stock
            steps += 1
    return {"unmet": unmet, "demanded": demanded, "avg_inventory": inv_sum / steps}


def simulate_iot(item, seed, measure_seed):
    """IoT policy without network (same logic as the MQTT backend)."""
    demand = DemandGenerator(seed)
    cell = LoadCell(item, measure_seed)
    logic = ReorderLogic(item)
    stock = round(logic.rop + item["Q"])
    pipeline = {}
    unmet = demanded = inv_sum = steps = 0
    for day in range(config.WORKING_DAYS):
        if pipeline.pop(day, 0):
            stock += item["Q"]
            logic.on_delivery()
        cell.new_day()
        for h in demand.day(item):
            served = min(stock, h)
            unmet += h - served
            demanded += h
            stock -= served
            inv_sum += stock
            steps += 1
            if logic.on_measurement(cell.to_quantity(cell.measure(stock))):
                pipeline[day + item["L"]] = item["Q"]
    return {"unmet": unmet, "demanded": demanded, "avg_inventory": inv_sum / steps}
