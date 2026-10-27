"""Inventory backend: subscribes to stock messages, checks the ROP, raises
alerts and stores all values in the database.

In a deployment this logic runs in Node-RED or a small server next to the
broker; here it is a Python MQTT client.
"""
import json
import threading
import time

import config
import mqtt_client
from inventory_logic import ReorderLogic
from storage import Storage


class InventoryBackend:
    def __init__(self, items, db_path=config.DB_PATH):
        self.logic = {i["id"]: ReorderLogic(i) for i in items}
        self.storage = Storage(db_path, reset=True)
        for i in items:
            self.storage.add_item(i, self.logic[i["id"]].rop)
        self.records = []            # every processed measurement
        self.alerts = []             # every reorder alert
        self._processed = threading.Condition()
        self._count = 0
        self.client = mqtt_client.connect("backend", on_message=self._on_message)
        self.client.subscribe(config.TOPIC_STOCK.format(item="+"), qos=config.QOS)

    def _on_message(self, client, userdata, msg):
        received = time.time()
        m = json.loads(msg.payload)
        m["latency_ms"] = (received - m["sent"]) * 1000
        order_qty = self.logic[m["item"]].on_measurement(m["qty"])
        m["order_qty"] = order_qty
        self.records.append(m)
        self.storage.add_measurement(m)
        if order_qty:
            alert = {"item": m["item"], "sim_time": m["sim_time"], "qty": m["qty"],
                     "rop": round(self.logic[m["item"]].rop), "order_qty": order_qty}
            self.alerts.append(alert)
            self.storage.add_alert(alert)
            self.client.publish(config.TOPIC_ALERT.format(item=m["item"]),
                                json.dumps(alert), qos=config.QOS)
        with self._processed:
            self._count += 1
            self._processed.notify_all()

    def wait_for(self, n, timeout=10):
        """Block until n messages in total have been processed."""
        with self._processed:
            if not self._processed.wait_for(lambda: self._count >= n, timeout):
                raise TimeoutError(f"only {self._count}/{n} messages processed")
        self.storage.commit()

    def delivered(self, item_id):
        self.logic[item_id].on_delivery()

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
        self.storage.close()
