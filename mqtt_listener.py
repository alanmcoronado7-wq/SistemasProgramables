
import uuid
import paho.mqtt.client as mqtt

# Configuración del broker
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

# Tópicos publicados por el ESP32
TOPICOS = [
    "motosos/aceleracion",
    "motosos/temperatura",
    "motosos/pulso",
    "motosos/ubicacion",
    "motosos/alerta",
    "motosos/emergencia/confirmada",
]


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("Error de conexión MQTT:", reason_code)
        return

    print("Conectado correctamente al broker MQTT")

    for topico in TOPICOS:
        client.subscribe(topico)
        print("Suscrito a:", topico)


def on_message(client, userdata, msg):
    mensaje = msg.payload.decode("utf-8", errors="replace")

    print(f"[MQTT] {msg.topic}: {mensaje}")


def main():
    client_id = f"motosos_bridge_{uuid.uuid4().hex[:8]}"

    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id
    )

    cliente.on_connect = on_connect
    cliente.on_message = on_message

    try:
        print("Conectando con HiveMQ...")
        cliente.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        cliente.loop_forever()

    except KeyboardInterrupt:
        print("\nDeteniendo receptor MQTT...")

    except OSError as error:
        print("Error de red:", error)

    finally:
        cliente.disconnect()


if __name__ == "__main__":
    main()
