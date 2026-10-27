"""SQLite storage of measurements and alerts (FR4)."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY, name TEXT, unit_g REAL, rop INTEGER, order_qty INTEGER);
CREATE TABLE IF NOT EXISTS measurements (
    item TEXT, sim_time REAL, qty INTEGER, weight_g REAL, latency_ms REAL);
CREATE TABLE IF NOT EXISTS alerts (
    item TEXT, sim_time REAL, qty INTEGER, rop INTEGER, order_qty INTEGER);
CREATE INDEX IF NOT EXISTS idx_meas ON measurements (item, sim_time);
"""


class Storage:
    def __init__(self, path, reset=False):
        self.db = sqlite3.connect(path, check_same_thread=False)
        if reset:
            self.db.executescript("DROP TABLE IF EXISTS items; DROP TABLE IF EXISTS "
                                  "measurements; DROP TABLE IF EXISTS alerts;")
        self.db.executescript(SCHEMA)

    def add_item(self, item, rop):
        self.db.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?)",
                        (item["id"], item["name"], item["unit_g"], round(rop), item["Q"]))
        self.db.commit()

    def add_measurement(self, m):
        self.db.execute("INSERT INTO measurements VALUES (?,?,?,?,?)",
                        (m["item"], m["sim_time"], m["qty"], m["weight_g"], m["latency_ms"]))

    def add_alert(self, a):
        self.db.execute("INSERT INTO alerts VALUES (?,?,?,?,?)",
                        (a["item"], a["sim_time"], a["qty"], a["rop"], a["order_qty"]))

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()
