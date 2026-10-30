
import math
import threading
import time
import uuid
from pathlib import Path

import firebase_admin
import paho.mqtt.client as mqtt
from firebase_admin import credentials, db

# =====================================
# CONFIGURACION
# =====================================

BASE_DIR = Path(__file__).resolve().parent
CREDENCIALES = BASE_DIR / "secrets" / "serviceAccountKey.json"

DATABASE_URL = (
    "https://moto-sos-7b12e-default-rtdb.firebaseio.com"
)

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

TOPICOS = [
    "motosos/aceleracion",
    "motosos/temperatura",
    "motosos/pulso",
    "motosos/ubicacion",
]

INTERVALO_ENVIO = 2

pendientes = {}
bloqueo = threading.Lock()


# =====================================
# PROCESAMIENTO DE DATOS
# =====================================

def procesar_mensaje(topico, mensaje):
    if topico == "motosos/aceleracion":
        valor = float(mensaje)
        if not math.isfinite(valor):
            raise ValueError("Aceleracion invalida")
        return {"fuerza_g": valor}

    if topico == "motosos/temperatura":
        valor = float(mensaje)
        if not math.isfinite(valor):
            raise ValueError("Temperatura invalida")
        return {"temperatura": valor}

    if topico == "motosos/pulso":
        valor = int(mensaje)
        if not 0 <= valor <= 250:
            raise ValueError("BPM fuera de rango")
        return {"bpm": valor}

    if topico == "motosos/ubicacion":
        datos = {
            "ubicacion": mensaje,
            "gps_disponible": False,
            "latitud": None,
            "longitud": None,
        }

        try:
            lat, lon = map(float, mensaje.split(","))

            if math.isfinite(lat) and math.isfinite(lon):
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    datos["latitud"] = lat
                    datos["longitud"] = lon
                    datos["gps_disponible"] = True

        except (ValueError, TypeError):
            pass

        return datos

    return {}


# =====================================
# MQTT CALLBACKS
# =====================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("Error MQTT:", reason_code)
        return

    print("MQTT conectado correctamente")

    for topico in TOPICOS:
        client.subscribe(topico)


def on_message(client, userdata, msg):
    try:
        mensaje = msg.payload.decode("utf-8")
        cambios = procesar_mensaje(msg.topic, mensaje)

        with bloqueo:
            pendientes.update(cambios)

    except (ValueError, UnicodeDecodeError) as error:
        print("Mensaje descartado:", error)


# =====================================
# PROGRAMA PRINCIPAL
# =====================================

def main():
    if not CREDENCIALES.is_file():
        raise FileNotFoundError("No se encontro serviceAccountKey.json")

    cred = credentials.Certificate(str(CREDENCIALES))

    firebase_admin.initialize_app(cred, {
        "databaseURL": DATABASE_URL
    })

    referencia = db.reference("moto_sos/telemetria_actual")
    print("Firebase inicializado correctamente")

    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"motosos_bridge_{uuid.uuid4().hex[:8]}"
    )

    cliente.on_connect = on_connect
    cliente.on_message = on_message

    cliente.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    cliente.loop_start()

    print("Puente Moto-SOS iniciado")

    try:
        while True:
            time.sleep(INTERVALO_ENVIO)

            with bloqueo:
                if not pendientes:
                    continue

                datos = pendientes.copy()
                pendientes.clear()

            datos["ultima_actualizacion"] = int(time.time() * 1000)

            try:
                referencia.update(datos)
                print("[FIREBASE] Telemetria actualizada:", datos)

            except Exception as error:
                print("Error guardando en Firebase:", error)

                with bloqueo:
                    for clave, valor in datos.items():
                        pendientes.setdefault(clave, valor)

    except KeyboardInterrupt:
        print("\nDeteniendo puente Moto-SOS...")

    finally:
        cliente.disconnect()
        cliente.loop_stop()


if __name__ == "__main__":
    main()
