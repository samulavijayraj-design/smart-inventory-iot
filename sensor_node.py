"""Simulated sensor node: weighs a shelf and publishes the stock via MQTT.

Replaces the ESP32 + HX711 + load cell of a physical weighing shelf.
"""
import json
import time

import config
import mqtt_client
from inventory_logic import LoadCell


class SensorNode:
    def __init__(self, item, seed):
        self.item = item
        self.cell = LoadCell(item, seed)
        self.client = mqtt_client.connect(f"shelf-{item['id']}")

    def publish(self, true_qty, sim_time):
        weight = self.cell.measure(true_qty)          # averaged load-cell reading
        payload = {
            "item": self.item["id"],
            "qty": self.cell.to_quantity(weight),       # weight -> pieces
            "weight_g": round(weight, 1),
            "sim_time": sim_time,
            "sent": time.time(),                        # for latency measurement
        }
        topic = config.TOPIC_STOCK.format(item=self.item["id"])
        self.client.publish(topic, json.dumps(payload), qos=config.QOS)
        return payload

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
