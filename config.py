"""Scenario and model parameters for the smart inventory simulation.

The scenario is a representative small metal-parts manufacturer with three
frequently used stock items stored on weighing shelves. All values are
assumptions of the use-case scenario (Section 3.1 of the report).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# MQTT broker (local amqtt instance started by run_simulation.py)
# TLS-encrypted listener with username/password authentication (NFR5)
BROKER_HOST = "localhost"
BROKER_PORT = 18883
TOPIC_STOCK = "factory/storeroom/{item}/stock"   # sensor node -> backend
TOPIC_ALERT = "factory/storeroom/{item}/alert"   # backend -> dashboard / sender
QOS = 1

# Security material created by setup_security.py
CERT_DIR = os.path.join(HERE, "certs")
CA_CERT = os.path.join(CERT_DIR, "ca.crt")
PASSWORD_FILE = os.path.join(CERT_DIR, "passwd")
# Local test credentials for the simulation only (override via environment)
MQTT_USER = os.environ.get("MQTT_USER", "inventory")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "sim-test-only")

# Storage and dashboard
RESULTS_DIR = os.path.join(HERE, "results")
DB_PATH = os.path.join(RESULTS_DIR, "inventory.db")
DASHBOARD_PORT = 8050

# Time model: working days with hourly shelf measurements
WORKING_DAYS = 60            # one quarter (12 five-day weeks)
HOURS_PER_DAY = 8            # one shift, 08:00-16:00
REVIEW_PERIOD_MANUAL = 5     # manual baseline: stock count once per week

# Inventory policy
Z_SERVICE = 1.65             # service-level factor for a 95 % cycle service level

# Load-cell model (per shelf)
READINGS_PER_MEASUREMENT = 10    # HX711 readings averaged per measurement
READING_NOISE_G = 5.0            # std. dev. of a single reading in g
DRIFT_PER_DAY_G = 0.5            # std. dev. of the daily zero-point drift in g

# Manual baseline: relative std. dev. of a manual stock count
MANUAL_COUNT_ERROR = 0.02

# Stock items: unit weight, coefficient of variation of the unit weight,
# mean and std. dev. of daily demand (pieces), lead time (working days),
# fixed order quantity (pieces)
ITEMS = [
    {"id": "BOLT-M8", "name": "Hex bolt M8x30", "unit_g": 17.0, "cv": 0.010,
     "d": 180, "sd": 45, "L": 5, "Q": 1500},
    {"id": "BRKT-AL", "name": "Aluminium bracket", "unit_g": 85.0, "cv": 0.005,
     "d": 40, "sd": 12, "L": 7, "Q": 400},
    {"id": "DISC-125", "name": "Cutting disc 125 mm", "unit_g": 120.0, "cv": 0.020,
     "d": 25, "sd": 8, "L": 4, "Q": 250},
]

SEED = 42                    # seed of the end-to-end MQTT run
REPLICATIONS = 30            # seeds for the policy comparison
