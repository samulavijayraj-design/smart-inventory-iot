"""Checks that the broker rejects insecure or unauthorised connections (NFR5).

Usage:  python check_security.py      (starts and stops the broker itself)
"""
import ssl
import time

import paho.mqtt.client as mqtt

import config
from run_simulation import start_broker


def try_connect(user, password, use_tls):
    result = {}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"check-{time.time()}")
    if user:
        c.username_pw_set(user, password)
    if use_tls:
        c.tls_set(ca_certs=config.CA_CERT)
    c.on_connect = lambda cl, ud, fl, rc, pr: result.setdefault("rc", str(rc))
    try:
        c.connect(config.BROKER_HOST, config.BROKER_PORT)
        c.loop_start()
        time.sleep(1.5)
        c.loop_stop()
        c.disconnect()
    except (ssl.SSLError, OSError) as e:
        return f"rejected ({type(e).__name__})"
    return "accepted" if result.get("rc") == "Success" else f"rejected ({result.get('rc', 'no answer')})"


if __name__ == "__main__":
    broker = start_broker()
    try:
        cases = [("Valid credentials, TLS", config.MQTT_USER, config.MQTT_PASSWORD, True),
                 ("Wrong password, TLS", config.MQTT_USER, "wrong", True),
                 ("No credentials, TLS", None, None, True),
                 ("Valid credentials, no TLS", config.MQTT_USER, config.MQTT_PASSWORD, False)]
        for name, u, p, tls in cases:
            print(f"{name:28s} -> {try_connect(u, p, tls)}")
    finally:
        broker.terminate()
