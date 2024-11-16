import paho.mqtt.client as mqtt
import time
import logging
import configparser
from webService import login, get_device_list
from threading import Timer, Event
import json

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Globale Variablen
access_token = None
token_expiry_time = None

# Konfigurationsdatei einlesen
config = configparser.ConfigParser()
config.read('src/solarflow/config.ini')

# Produkt- und Geräte-ID aus der Konfigurationsdatei lesen
product_id = config.get('solarflow', 'product_id', fallback=None)
device_id = config.get('solarflow', 'device_id', fallback=None)

# Check if required sections and keys exist
required_sections = ['cloudweb', 'cloudmqtt', 'mqtt']
required_keys = {
    'cloudweb': ['cloud_web_user', 'cloud_web_pwd', 'token_url'],
    'cloudmqtt': ['cloud_mqtt_user', 'cloud_mqtt_pwd', 'cloud_mqtt_host', 'cloud_mqtt_port'],
    'mqtt': ['mqtt_user', 'mqtt_pwd', 'mqtt_host', 'mqtt_port']
}

for section in required_sections:
    if section not in config.sections():
        raise KeyError(f"Missing section '{section}' in configuration file")
    for key in required_keys[section]:
        if key not in config[section]:
            raise KeyError(f"Missing key '{key}' in section '{section}' in configuration file")

def getClientId(cloud=False):
    global access_token, token_expiry_time
    if not cloud:
        return config.get('mqtt', 'mqtt_user', fallback=None)

    current_time = time.time()
    if access_token is None or (token_expiry_time is not None and current_time >= token_expiry_time):
        access_token = login(
            config.get('cloudweb', 'cloud_web_user', fallback=None),
            config.get('cloudweb', 'cloud_web_pwd', fallback=None, raw=True),
            config.get('cloudweb', 'token_url', fallback=None)
        )
        token_expiry_time = current_time + 300  # Token expires in 5 minutes (300 seconds)
    
    devicelist = get_device_list(access_token, config.get('cloudweb', 'device_list_url', fallback=None))
    if devicelist:
        log.info(f"Device list: {devicelist}")

    return access_token

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info(f"Connected to MQTT Broker: {client._client_id.decode('utf-8')}")
        # Subscribe to topics here
        if client._client_id.decode('utf-8') == getClientId(cloud=False):
            subscribe_local(client)
        else:
            subscribe_zendure(client)
    else:
        log.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    if client._client_id.decode('utf-8') == getClientId(cloud=False):
        log.info(f"Message received on local broker on topic {msg.topic} with payload {msg.payload}")
        process_and_control(msg, userdata['zendure_client'], product_id, device_id)
    else:
        log.info(f"Message received on Zendure broker on topic {msg.topic} with payload {msg.payload}")

def subscribe_zendure(client):
    topics = [
        f'/{product_id}/{device_id}/#'
    ]
    for t in topics:
        client.subscribe(t)
        log.info(f"Subscribed to {t} on Zendure broker")

def subscribe_local(client):
    topics = [
        config.get('smartmeter', 'base_topic', fallback='default/base/topic'),
        'local/topic2'
    ]
    for t in topics:
        client.subscribe(t)
        log.info(f"Subscribed to {t} on local broker")

def connect_mqtt(client_id, mqtt_user, mqtt_pwd, mqtt_host, mqtt_port):
    client = mqtt.Client(client_id)
    client.username_pw_set(mqtt_user, mqtt_pwd)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqtt_host, mqtt_port, 60)
    return client

def process_and_control(msg, zendure_client, product_id, device_id):
    """
    Verarbeitet Nachrichten vom lokalen Broker und steuert das Laden und Entladen des Speichers
    durch das Setzen der entsprechenden Werte im Zendure-Broker.

    :param msg: Die empfangene Nachricht vom lokalen Broker
    :param zendure_client: Der MQTT-Client für den Zendure-Broker
    :param product_id: Die Produkt-ID für den Zendure-Broker
    :param device_id: Die Geräte-ID für den Zendure-Broker
    """
    topic = msg.topic
    payload = msg.payload.decode()


    # Beispielhafte Steuerlogik basierend auf dem empfangenen Topic und Payload

    grid_power = int(payload)
    if grid_power > 300:
        # Strom wird ins Netz eingespeist, Speicher laden
        set_battery_target(zendure_client, product_id, device_id, "charging")
        log.info(f'Grid power is {grid_power}W, setting battery target to CHARGING')
    else:
        # Strom wird aus dem Netz bezogen, Speicher entladen
        set_battery_target(zendure_client, product_id, device_id, "discharging")
        log.info(f'Grid power is {grid_power}W, setting battery target to DISCHARGING')

def set_battery_target(zendure_client, product_id, device_id, target):
    """
    Setzt das Batterie-Ziel im Zendure-Broker.

    :param zendure_client: Der MQTT-Client für den Zendure-Broker
    :param product_id: Die Produkt-ID für den Zendure-Broker
    :param device_id: Die Geräte-ID für den Zendure-Broker
    :param target: Das Batterie-Ziel (z.B. "charging" oder "discharging")
    """
    payload = {"properties": {"batteryTarget": target}}
    zendure_client.publish(f'iot/{product_id}/{device_id}/properties/write', json.dumps(payload))
    log.info(f'Setting battery target mode to {target}')

class RepeatedTimer:
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.event = Event()
        self.thread = Timer(self.interval, self.run)
        self.thread.start()

    def run(self):
        while not self.event.is_set():
            self.function(*self.args, **self.kwargs)
            self.event.wait(self.interval)

    def stop(self):
        self.event.set()
        self.thread.cancel()

def run():
    log.info("Starting run function")

    zendure_client = connect_mqtt(
        client_id=getClientId(cloud=True),
        mqtt_user=config.get('cloudmqtt', 'cloud_mqtt_user', fallback=None),
        mqtt_pwd=config.get('cloudmqtt', 'cloud_mqtt_pwd', fallback=None, raw=True),
        mqtt_host=config.get('cloudmqtt', 'cloud_mqtt_host', fallback=None),
        mqtt_port=config.getint('cloudmqtt', 'cloud_mqtt_port')
    )
    log.info("Zendure client connected")

    local_client = connect_mqtt(
        client_id=getClientId(cloud=False),
        mqtt_user=config.get('mqtt', 'mqtt_user', fallback=None),
        mqtt_pwd=config.get('mqtt', 'mqtt_pwd', fallback=None, raw=True),
        mqtt_host=config.get('mqtt', 'mqtt_host', fallback=None),
        mqtt_port=config.getint('mqtt', 'mqtt_port')
    )
    log.info("Local client connected")

    # Setze den zendure_client in den userdata des lokalen Clients
    local_client.user_data_set({'zendure_client': zendure_client})

    # Start both clients in separate threads
    zendure_client.loop_start()
    log.info("Zendure client loop started")

    local_client.loop_start()
    log.info("Local client loop started")

    # Token-Refresh-Timer starten
    token_refresh_timer = RepeatedTimer(300, getClientId, cloud=True)
    log.info("Token refresh timer started")

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        local_client.loop_stop()
        zendure_client.loop_stop()
        token_refresh_timer.stop()
        log.info("Clients and token refresh timer stopped")

if __name__ == '__main__':
    run()