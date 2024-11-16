import logging
import paho.mqtt.client as mqtt
import requests
import json
import time

# Initialisierung des Loggings
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# MQTT-Konfiguration
mqtt_broker = "DEIN_MQTT_BROKER_ADRESSE"
mqtt_port = 1883  # Standard MQTT-Port, anpassen falls notwendig

# API-Konfiguration
api_base_url = "https://api.zendure.com"  # Basis-URL der Zendure API

# MQTT-Client initialisieren
mqtt_client = mqtt.Client()

class ZendureSolarflowAdapter:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.access_token = None
        self.user_id = None

    # Anmeldung bei der API, um Access Token zu erhalten
    def login(self):
        auth = f"{self.username}:{self.password}"
        headers = {
            "Content-Type": "application/json",
            "Accept-Language": "de-DE",
            "Authorization": "Basic " + auth,
            "User-Agent": "Zendure/4.3.1 (iPhone; iOS 14.4.2; Scale/3.00)",
        }
        data = {
            "password": self.password,
            "account": self.username,
            "appId": "121c83f761305d6cf7b",
            "appType": "iOS",
            "grantType": "password",
            "tenantId": ""
        }
        response = requests.post(f"{api_base_url}/auth/login", json=data, headers=headers)

        if response.status_code == 200 and response.json().get("success"):
            self.access_token = response.json()["data"]["accessToken"]
            self.user_id = response.json()["data"]["userId"]
            logger.info("Erfolgreich bei Zendure API angemeldet.")
        else:
            logger.error("Anmeldung bei Zendure API fehlgeschlagen.")
    
    # Geräteliste von der API abrufen
    def get_device_list(self):
        if not self.access_token:
            logger.error("Kein Access Token gefunden!")
            return []

        headers = {
            "Authorization": "Bearer " + self.access_token
        }
        response = requests.get(f"{api_base_url}/devices", headers=headers)

        if response.status_code == 200:
            logger.info("Geräteliste erfolgreich abgerufen.")
            return response.json().get("data", [])
        else:
            logger.error("Fehler beim Abrufen der Geräteliste.")
            return []

    # Beispiel einer MQTT-Publikation
    def publish_mqtt(self, product_key, device_key, topic_suffix, payload):
        topic = f"iot/{product_key}/{device_key}/{topic_suffix}"
        mqtt_client.publish(topic, json.dumps(payload))
        logger.info(f"MQTT Nachricht an {topic} gesendet: {payload}")

    # MQTT für AC Mode konfigurieren
    def set_ac_mode(self, product_key, device_key, ac_mode):
        if 0 <= ac_mode <= 2:
            payload = {"properties": {"acMode": ac_mode}}
            self.publish_mqtt(product_key, device_key, "properties/write", payload)
        else:
            logger.error("AC Mode muss zwischen 0 und 2 liegen.")

# Beispiel einer Anwendung
if __name__ == "__main__":
    adapter = ZendureSolarflowAdapter("DEIN_BENUTZERNAME", "DEIN_PASSWORT")
    adapter.login()

    # Abruf der Geräteliste
    devices = adapter.get_device_list()
    if devices:
        for device in devices:
            product_key = device.get("productKey")
            device_key = device.get("deviceKey")
            adapter.set_ac_mode(product_key, device_key, 1)

    # Beispiel für eine Verbindung zum MQTT-Broker
    mqtt_client.connect(mqtt_broker, mqtt_port, 60)
    mqtt_client.loop_start()

    # ... Weitere MQTT-Konfigurationen oder API-Aufrufe
