# ============================================
# Proyecto:  Moto-SOS
# Archivo:   firebase_commands.py
# Objetivo:  Convertir comandos Firebase en órdenes MQTT para los actuadores.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import time
import uuid
import threading

import firebase_admin
import paho.mqtt.client as mqtt
from firebase_admin import credentials, db

from servidor.configuracion import (
    CREDENTIALS,
    DATABASE_URL,
    MQTT_BROKER,
    MQTT_KEEPALIVE,
    MQTT_PORT,
)

# ======================================
# CONFIGURACION
# ======================================

TOPICOS = {
    "buzzer": "motosos/buzzer/cmd",
    "ventilador": "motosos/ventilador/cmd",
    "vibrador": "motosos/vibrador/cmd",
    "cancelar": "motosos/cancelar/cmd"
}

ESTADOS_INICIALES = {
    "buzzer": "OFF",
    "ventilador": "OFF",
    "vibrador": "OFF",
    "cancelar": "OFF"
}

ultimo_estado = {
    nombre: None for nombre in TOPICOS
}

mqtt_conectado = threading.Event()


# ======================================
# MQTT
# ======================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("Error MQTT:", reason_code)
        mqtt_conectado.clear()
        return

    mqtt_conectado.set()
    print("[MQTT] Conectado correctamente")


def on_disconnect(client, userdata, flags, reason_code, properties):
    mqtt_conectado.clear()
    print("[MQTT] Desconectado:", reason_code)


def publicar_comando(cliente, nombre, valor):
    if not mqtt_conectado.is_set():
        print("[MQTT] Sin conexion. Comando no enviado.")
        return False

    topico = TOPICOS[nombre]

    try:
        info = cliente.publish(
            topico,
            payload=valor,
            qos=0,
            retain=False
        )

        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            print("[MQTT] Fallo al publicar:", nombre)
            return False

        info.wait_for_publish(timeout=3)

        if not info.is_published():
            print("[MQTT] Envio no confirmado:", nombre)
            return False

        print(f"[MQTT] {topico} -> {valor}")
        return True

    except Exception as error:
        print("[MQTT] Error:", error)
        return False


# ======================================
# FIREBASE -> MQTT
# ======================================

def crear_listener(cliente, referencia):

    def recibir_cambio(evento):
        if evento.event_type not in ("put", "patch"):
            return

        if evento.path == "/":
            cambios = evento.data
            if not isinstance(cambios, dict):
                return

        else:
            nombre = evento.path.strip("/")
            if "/" in nombre:
                return

            cambios = {nombre: evento.data}

        for nombre, valor in cambios.items():
            if nombre not in TOPICOS:
                continue

            if valor not in ("ON", "OFF"):
                print("[FIREBASE] Valor invalido:", nombre, valor)
                continue

            # Cancelacion: comando de un solo uso
            if nombre == "cancelar":
                if valor == "ON":
                    if publicar_comando(cliente, nombre, "ON"):
                        referencia.child("cancelar").set("OFF")
                        print("[FIREBASE] Cancelar restablecido a OFF")
                continue

            # No reenviar comandos sin cambios
            if ultimo_estado[nombre] == valor:
                continue

            if publicar_comando(cliente, nombre, valor):
                ultimo_estado[nombre] = valor

    return referencia.listen(recibir_cambio)


# ======================================
# INICIO
# ======================================

def main():
    cred = credentials.Certificate(str(CREDENTIALS))

    firebase_admin.initialize_app(cred, {
        "databaseURL": DATABASE_URL
    })

    referencia = db.reference("moto_sos/comandos")

    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"motosos_control_{uuid.uuid4().hex[:8]}"
    )

    cliente.on_connect = on_connect
    cliente.on_disconnect = on_disconnect

    escucha = None

    try:
        cliente.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        cliente.loop_start()

        if not mqtt_conectado.wait(timeout=10):
            raise RuntimeError("No se pudo conectar a MQTT")

        # Estado seguro inicial para esta prueba
        referencia.set(ESTADOS_INICIALES)

        escucha = crear_listener(cliente, referencia)

        print("[FIREBASE] Escuchando comandos...")
        print("[SISTEMA] Control remoto Moto-SOS activo")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nDeteniendo control remoto...")

    finally:
        if escucha is not None:
            escucha.close()

        # Intentar apagar actuadores de prueba
        publicar_comando(cliente, "buzzer", "OFF")
        publicar_comando(cliente, "vibrador", "OFF")

        cliente.disconnect()
        cliente.loop_stop()


if __name__ == "__main__":
    main()
