"""Creates MQTT clients with TLS encryption and authentication (NFR5)."""
import paho.mqtt.client as mqtt

import config


def connect(client_id, on_message=None):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)
    client.tls_set(ca_certs=config.CA_CERT)      # verifies the broker certificate
    if on_message:
        client.on_message = on_message
    client.connect(config.BROKER_HOST, config.BROKER_PORT)
    client.loop_start()
    return client
