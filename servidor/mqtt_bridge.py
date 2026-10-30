# ============================================
# Proyecto:  Moto-SOS
# Archivo:   mqtt_bridge.py
# Objetivo:  Transferir telemetría MQTT a Firebase y conservar el último fix GPS.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
"""Puente Moto-SOS: MQTT -> Firebase + ultima ubicacion valida con timestamp.
Conserva los topics originales; agrega motosos/gps/estado si firmware GPS v2.
No guardar ubicacion falsa ni inventar posicion.
"""
import json
import math
import threading
import time
import uuid

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
TOPICOS = [
    'motosos/aceleracion', 'motosos/temperatura', 'motosos/pulso',
    'motosos/ubicacion', 'motosos/gps/estado',
]
pendientes = {}
ultimo_fix = None
estado_gps_v2 = None
bloqueo = threading.Lock()


def parsear_coords(mensaje):
    try:
        lat, lon = (float(x.strip()) for x in mensaje.split(','))
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print('Error MQTT:', reason_code)
        return
    client.subscribe([(t, 0) for t in TOPICOS])
    print('MQTT conectado, telemetria y GPS v2 suscritos')


def on_message(client, userdata, msg):
    global ultimo_fix, estado_gps_v2
    try:
        texto = msg.payload.decode('utf-8').strip()
        topico = msg.topic
        cambios = {}
        ahora_ms = int(time.time() * 1000)
        with bloqueo:
            if topico == 'motosos/aceleracion':
                v = float(texto)
                if not math.isfinite(v):
                    return
                cambios['fuerza_g'] = round(v, 2)
            elif topico == 'motosos/temperatura':
                v = float(texto)
                if not math.isfinite(v):
                    return
                cambios['temperatura'] = v
            elif topico == 'motosos/pulso':
                v = int(texto)
                if not 0 <= v <= 250:
                    return
                cambios['bpm'] = v
            elif topico == 'motosos/ubicacion':
                coords = parsear_coords(texto)
                cambios['ubicacion'] = texto
                if coords and (estado_gps_v2 is None or estado_gps_v2):
                    cambios['latitud'], cambios['longitud'] = coords
                    cambios['gps_disponible'] = True
                    # Firmware v1 repite la ultima posicion aunque pierda señal:
                    # se considera la fecha de recepcion, no fecha del fix real.
                    # Con firmware v2, motosos/gps/estado provee calidad real.
                    if ultimo_fix != coords:
                        pendientes['_ultimo_fix_nuevo'] = {
                            'latitud': coords[0], 'longitud': coords[1],
                            'timestamp': ahora_ms, 'origen': 'GPS_ESP32',
                            'calidad': 'NO_VERIFICADA_SIN_ESTADO_GPS',
                        }
                        ultimo_fix = coords
                elif not coords:
                    cambios.update(gps_disponible=False, latitud=None, longitud=None)
            elif topico == 'motosos/gps/estado':
                estado = json.loads(texto)
                if not isinstance(estado, dict):
                    return
                coords_status = None
                if estado.get('fix'):
                    try:
                        coords_status = parsear_coords(
                            '{},{}'.format(estado.get('latitud'), estado.get('longitud'))
                        )
                    except Exception:
                        pass
                estado = {k: estado.get(k) for k in (
                    'fix', 'estado', 'satelites', 'hdop', 'calidad',
                    'edad_fix_seg', 'recibe_nmea', 'tramas', 'checksum_invalidos',
                    'ultima_latitud', 'ultima_longitud',
                )}
                cambios['gps_estado'] = estado
                estado_gps_v2 = bool(estado.get('fix'))
                cambios['gps_disponible'] = bool(estado.get('fix'))
                if estado['fix'] and coords_status:
                    cambios['latitud'], cambios['longitud'] = coords_status
                    cambios['ubicacion'] = '{:.6f}, {:.6f}'.format(*coords_status)
                    cambios['gps_ultima_confirmacion'] = ahora_ms
                    pendientes['_ultimo_fix_nuevo'] = {
                        'latitud': coords_status[0], 'longitud': coords_status[1],
                        'timestamp': ahora_ms, 'origen': 'GPS_ESP32',
                        'calidad': 'FIX_REPORTADO_POR_MODULO',
                        'satelites': estado.get('satelites'), 'hdop': estado.get('hdop'),
                    }
                elif estado['fix']:
                    # El receptor dice fix pero no hay coordenadas utilizables.
                    cambios['gps_disponible'] = False
                else:
                    cambios.update(latitud=None, longitud=None)
            pendientes.update(cambios)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print('MQTT descartado:', msg.topic, exc)


def main():
    firebase_admin.initialize_app(credentials.Certificate(str(CREDENTIALS)), {
        'databaseURL': DATABASE_URL,
    })
    telemetria_ref = db.reference('moto_sos/telemetria_actual')
    ultimo_ref = db.reference('moto_sos/ubicacion_ultima_valida')
    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id='motosos_bridge_' + uuid.uuid4().hex[:8],
    )
    cliente.on_connect = on_connect
    cliente.on_message = on_message
    cliente.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
    cliente.loop_start()
    print('Puente Moto-SOS v2 activo')
    try:
        while True:
            time.sleep(2)
            with bloqueo:
                if not pendientes:
                    continue
                datos = pendientes.copy()
                pendientes.clear()
            ultimo_nuevo = datos.pop('_ultimo_fix_nuevo', None)
            datos['ultima_actualizacion'] = int(time.time() * 1000)
            try:
                telemetria_ref.update(datos)
                if ultimo_nuevo:
                    ultimo_ref.set(ultimo_nuevo)
                print('[FIREBASE] Datos:', datos)
            except Exception as exc:
                print('Error guardando Firebase:', exc)
                with bloqueo:
                    for k, v in datos.items():
                        pendientes.setdefault(k, v)
                    if ultimo_nuevo:
                        pendientes.setdefault('_ultimo_fix_nuevo', ultimo_nuevo)
    except KeyboardInterrupt:
        print('Deteniendo puente...')
    finally:
        cliente.disconnect()
        cliente.loop_stop()


if __name__ == '__main__':
    main()
