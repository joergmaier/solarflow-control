import paho.mqtt.client as mqtt
import json

# MQTT-Konfiguration
mqtt_broker = "DEIN_MQTT_BROKER_ADRESSE"
mqtt_port = 1883  # Standard MQTT-Port, passe diesen ggf. an

# MQTT-Client einrichten
client = mqtt.Client()
client.connect(mqtt_broker, mqtt_port, 60)

# Setzt den AC-Modus
def set_ac_mode(product_key, device_key, ac_mode):
    if 0 <= ac_mode <= 2:
        topic = f"iot/{product_key}/{device_key}/properties/write"
        payload = {"properties": {"acMode": ac_mode}}
        client.publish(topic, json.dumps(payload))
        print(f"AC-Modus auf {ac_mode} gesetzt.")
    else:
        print("AC-Modus muss zwischen 0 und 2 liegen.")

# Setzt das Ladelimit (State of Charge - SoC)
def set_charge_limit(product_key, device_key, soc_set):
    if 40 < soc_set <= 100:
        topic = f"iot/{product_key}/{device_key}/properties/write"
        payload = {"properties": {"socSet": soc_set * 10}}
        client.publish(topic, json.dumps(payload))
        print(f"Ladelimit auf {soc_set}% gesetzt.")
    else:
        print("Ladelimit muss zwischen 40 und 100 liegen.")

# Setzt das Entladelimit
def set_discharge_limit(product_key, device_key, min_soc):
    if 0 < min_soc < 90:
        topic = f"iot/{product_key}/{device_key}/properties/write"
        payload = {"properties": {"minSoc": min_soc * 10}}
        client.publish(topic, json.dumps(payload))
        print(f"Entladelimit auf {min_soc}% gesetzt.")
    else:
        print("Entladelimit muss zwischen 0 und 90 liegen.")

# Setzt das Output-Limit
def set_output_limit(product_key, device_key, limit, product_name=None):
    if limit:
        limit = round(limit)
    else:
        limit = 0

    if limit > 1200:
        limit = 1200
    elif limit < 30:
        limit = 30

    # Anpassung des Limits für spezifische Produkte
    if product_name and "hyper" not in product_name.lower():
        if limit < 100:
            if 90 < limit <= 100:
                limit = 90
            elif 60 < limit <= 90:
                limit = 60
            elif 30 < limit <= 60:
                limit = 30

    topic = f"iot/{product_key}/{device_key}/properties/write"
    payload = {"properties": {"outputLimit": limit}}
    client.publish(topic, json.dumps(payload))
    print(f"Output-Limit auf {limit} gesetzt.")

# Setzt das Input-Limit
def set_input_limit(product_key, device_key, limit, product_name=None):
    if limit:
        limit = round(limit)
    else:
        limit = 0

    max_limit = 1200 if product_name and "hyper" in product_name.lower() else 900

    if "ace" in (product_name or "").lower():
        limit = round(limit / 100) * 100  # Anpassung in 100er Schritten

    if limit < 30:
        limit = 30
    elif limit > max_limit:
        limit = max_limit

    topic = f"iot/{product_key}/{device_key}/properties/write"
    payload = {"properties": {"inputLimit": limit}}
    client.publish(topic, json.dumps(payload))
    print(f"Input-Limit auf {limit} gesetzt.")

# Beispielaufruf
product_key = "deinProductKey"
device_key = "deinDeviceKey"
set_ac_mode(product_key, device_key, 1)
set_charge_limit(product_key, device_key, 80)
set_discharge_limit(product_key, device_key, 20)
set_output_limit(product_key, device_key, 100, product_name="solarFlow HUB")
set_input_limit(product_key, device_key, 400, product_name="solarFlow ACE")

client.disconnect()
