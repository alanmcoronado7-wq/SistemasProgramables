"""Moto-SOS: MQTT -> foto IP -> Telegram + historial Firebase.

Se ejecuta JUNTO a mqtt_firebase_bridge.py y firebase_commands.py.
No reemplaza la telemetria ni el control remoto ya probados.

PRUEBAS:
  python emergency_notifier.py --probar-camara
  python emergency_notifier.py --simulacro
  python emergency_notifier.py

NO es un servicio de emergencias certificado ni garantizado.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import queue
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import firebase_admin
import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv
from firebase_admin import credentials, db, storage
from vision_ia import analizar_imagen, resumen_ia

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = "https://moto-sos-7b12e-default-rtdb.firebaseio.com"
CREDENTIALS = BASE_DIR / "secrets" / "serviceAccountKey.json"
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_EMERGENCY = "motosos/emergencia/confirmada"
TOPIC_ALERT = "motosos/alerta"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
CAMERA_SNAPSHOT_URL = os.getenv("CAMERA_SNAPSHOT_URL", "").strip()
CAMERA_STREAM_URL = os.getenv("CAMERA_STREAM_URL", "").strip()
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
TZ_NAME = os.getenv("MOTOSOS_TZ", "America/Mexico_City").strip()

EVIDENCE_DIR = BASE_DIR / "evidencias"
DEDUPE_SECONDS = 12  # Mitiga repeticion inmediata; NO sustituye un ID desde el ESP32.
QUEUE = queue.Queue(maxsize=30)
STOP = threading.Event()
LAST_EMERGENCY = 0.0
LAST_LOCK = threading.Lock()

LOG = logging.getLogger("MotoSOS")


def validar_configuracion() -> None:
    if not CREDENTIALS.is_file():
        raise FileNotFoundError(
            "Falta secrets/serviceAccountKey.json en MotoSOS_Bridge."
        )
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("Configura TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en .env")


def inicializar_firebase() -> None:
    try:
        firebase_admin.get_app()
    except ValueError:
        options = {"databaseURL": DATABASE_URL}
        if FIREBASE_STORAGE_BUCKET:
            options["storageBucket"] = FIREBASE_STORAGE_BUCKET
        firebase_admin.initialize_app(credentials.Certificate(str(CREDENTIALS)), options)


def _validar_coordenadas(telemetria: dict):
    try:
        lat = float(telemetria["latitud"])
        lon = float(telemetria["longitud"])
        if (
            math.isfinite(lat)
            and math.isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            return lat, lon
    except (ValueError, TypeError, KeyError):
        pass
    return None


def construir_mensaje(telemetria: dict, fecha: datetime, simulacro: bool):
    """Mensaje informativo. GPS = ultima posicion, NO localizacion garantizada."""
    coord = _validar_coordenadas(telemetria)
    actualizacion = telemetria.get("ultima_actualizacion")
    try:
        edad_s = max(0, (fecha.timestamp() * 1000 - int(actualizacion)) / 1000)
    except (ValueError, TypeError):
        edad_s = None

    etiqueta = "SIMULACRO - NO ES UNA EMERGENCIA" if simulacro else "MOTO-SOS: ACCIDENTE CONFIRMADO"
    lineas = [
        f"🚨 {etiqueta}",
        f"Fecha y hora de confirmación: {fecha:%d/%m/%Y %H:%M:%S}",
        f"Zona horaria: {TZ_NAME}",
    ]
    if coord:
        lat, lon = coord
        lineas.extend([
            f"Última posición GPS: {lat:.6f}, {lon:.6f}",
            f"Mapa: https://www.google.com/maps?q={lat:.6f},{lon:.6f}",
        ])
        if edad_s is not None and edad_s > 30:
            lineas.append("ATENCIÓN: datos posiblemente desactualizados")
        else:
            lineas.append("Posición reportada por el casco (no verificada)")
    else:
        lineas.append("Ubicación: no disponible; confirmar por otra vía")

    fuerza = telemetria.get("fuerza_g")
    temperatura = telemetria.get("temperatura")
    bpm = telemetria.get("bpm")
    lineas.append(f"Fuerza G reportada: {fuerza if fuerza is not None else 'sin dato'}")
    lineas.append(f"Temperatura del casco: {temperatura if temperatura is not None else 'sin dato'} °C")
    lineas.append(f"Pulso (BPM): {bpm if bpm not in (None, 0, '0') else 'sin lectura válida'}")
    lineas.append("Aviso automático; verificar la situación antes de actuar")
    return "\n".join(lineas), coord, edad_s


def capturar_foto(destino: Path) -> Path | None:
    """Usa /shot.jpg preferentemente; /video MJPEG como respaldo."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if CAMERA_SNAPSHOT_URL:
        try:
            respuesta = requests.get(
                CAMERA_SNAPSHOT_URL, timeout=(4, 7),
                headers={"Accept": "image/jpeg,image/*"},
            )
            respuesta.raise_for_status()
            if len(respuesta.content) > 9_000_000:
                raise ValueError("La imagen supera 9 MB")
            # Validar que la respuesta sea realmente una imagen.
            import numpy as np
            imagen = cv2.imdecode(
                np.frombuffer(respuesta.content, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if imagen is None:
                raise ValueError("La URL no devolvio una foto valida")
            if not cv2.imwrite(str(destino), imagen):
                raise OSError("No se pudo guardar el JPEG")
            LOG.info("Foto obtenida del endpoint de instantanea")
            return destino
        except (requests.RequestException, ValueError, OSError) as exc:
            LOG.warning("Camara /shot.jpg no disponible: %s", exc)

    if CAMERA_STREAM_URL:
        captura = None
        try:
            opciones = [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
            ]
            captura = cv2.VideoCapture(
                CAMERA_STREAM_URL, cv2.CAP_FFMPEG, opciones
            )
            if not captura.isOpened():
                raise OSError("No se pudo abrir el stream /video")
            ok, frame = captura.read()
            if not ok or frame is None:
                raise OSError("No llego un fotograma del stream")
            if not cv2.imwrite(str(destino), frame):
                raise OSError("No se pudo guardar el fotograma")
            LOG.info("Foto capturada desde stream /video")
            return destino
        except (cv2.error, OSError, TypeError) as exc:
            LOG.warning("Camara /video no disponible: %s", exc)
        finally:
            if captura is not None:
                captura.release()
    return None


def almacenar_foto_storage(foto: Path, event_id: str) -> dict:
    """Storage es OPCIONAL; en Spark no se puede usar Cloud Storage."""
    if not FIREBASE_STORAGE_BUCKET:
        return {"estado": "NO_CONFIGURADO"}
    object_path = f"moto_sos/evidencias/{event_id}.jpg"
    try:
        blob = storage.bucket().blob(object_path)
        blob.upload_from_filename(str(foto), content_type="image/jpeg")
        LOG.info("Foto almacenada en Cloud Storage: %s", object_path)
        return {
            "estado": "GUARDADO",
            "bucket": FIREBASE_STORAGE_BUCKET,
            "ruta": object_path,
        }
    except Exception as exc:
        LOG.exception("No se pudo subir foto a Cloud Storage")
        return {"estado": "ERROR", "detalle": str(exc)[:200]}


def _telegram_post(method: str, *, data: dict, photo: Path | None = None) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    if photo:
        with photo.open("rb") as archivo:
            respuesta = requests.post(
                url, data=data, files={"photo": (photo.name, archivo, "image/jpeg")},
                timeout=(5, 25),
            )
    else:
        respuesta = requests.post(url, data=data, timeout=(5, 15))
    respuesta.raise_for_status()
    contenido = respuesta.json()
    if not contenido.get("ok"):
        raise RuntimeError(contenido.get("description", "Error Telegram desconocido"))
    return contenido["result"]


def notificar_texto_telegram(mensaje: str) -> dict:
    """El texto con GPS sale primero, para no depender de la cámara."""
    try:
        respuesta = _telegram_post(
            "sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje[:4096]},
        )
        return {"estado": "ENVIADO", "message_id": respuesta.get("message_id")}
    except Exception as exc:
        LOG.error("Telegram aviso inicial: %s", exc)
        return {"estado": "ERROR", "detalle": str(exc)[:200]}


def notificar_foto_telegram(foto: Path, mensaje: str) -> dict:
    try:
        respuesta = _telegram_post(
            "sendPhoto",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": mensaje[:1024]},
            photo=foto,
        )
        return {"estado": "ENVIADA", "message_id": respuesta.get("message_id")}
    except Exception as exc:
        LOG.error("Telegram envio de foto: %s", exc)
        return {"estado": "ERROR", "detalle": str(exc)[:200]}


def registrar_accidente(fecha: datetime, simulacro: bool = False) -> None:
    """Mensaje de alerta primero, foto despues. El historial no bloquea Telegram."""
    historico = db.reference("moto_sos/historico_accidentes")
    evento = historico.push()
    event_id = evento.key
    timestamp_ms = int(fecha.timestamp() * 1000)
    tipo = "SIMULACRO" if simulacro else "EMERGENCIA_CONFIRMADA"

    try:
        telemetria = db.reference("moto_sos/telemetria_actual").get() or {}
        if not isinstance(telemetria, dict):
            telemetria = {}
    except Exception:
        LOG.exception("No se pudo leer telemetria Firebase")
        telemetria = {}

    mensaje, coordenadas, edad_gps = construir_mensaje(telemetria, fecha, simulacro)
    datos = {
        "timestamp": timestamp_ms,
        "fecha_hora_local": fecha.isoformat(),
        "tipo": tipo,
        "estado": "PROCESANDO",
        "fuerza_g_reportada": telemetria.get("fuerza_g"),
        "temperatura": telemetria.get("temperatura"),
        "bpm": telemetria.get("bpm"),
        "latitud": coordenadas[0] if coordenadas else None,
        "longitud": coordenadas[1] if coordenadas else None,
        "edad_telemetria_seg": round(edad_gps, 1) if edad_gps is not None else None,
        "ubicacion_tipo": "ULTIMA_REPORTADA" if coordenadas else "SIN_GPS",
        "mensaje_telegram": mensaje,
        "foto_local": None,
        "foto_anotada_local": None,
        "analisis_ia": {"estado": "PENDIENTE"},
        "foto_storage": {"estado": "PENDIENTE"},
        "telegram": {"mensaje": {"estado": "PENDIENTE"}, "foto": {"estado": "PENDIENTE"}},
    }

    def actualizar_seguro(nuevos: dict) -> None:
        try:
            evento.update(nuevos)
        except Exception:
            LOG.exception("No se pudo actualizar historial Firebase")

    try:
        evento.set(datos)
        if not simulacro:
            db.reference("moto_sos/telemetria_actual").update({
                "estado_alerta": "EMERGENCIA_CONFIRMADA",
                "emergencia_confirmada": True,
            })
        LOG.warning("Evento registrado: %s (%s)", event_id, tipo)
    except Exception:
        LOG.exception("Firebase no disponible; se intentara Telegram igualmente")

    # PRIORIDAD: texto inmediato con ubicacion y hora, sin esperar camara.
    resultado_texto = notificar_texto_telegram(mensaje)
    try:
        evento.child("telegram").child("mensaje").set(resultado_texto)
    except Exception:
        LOG.exception("No se pudo registrar confirmacion de Telegram")
    LOG.info("Telegram aviso: %s", resultado_texto["estado"])

    # Evidencia visual: si la camara no responde el aviso ya se envio.
    foto = capturar_foto(EVIDENCE_DIR / f"{event_id}.jpg")
    if foto:
        actualizar_seguro({"foto_local": foto.name})
        foto_telegram = foto
        texto_ia = "IA no disponible; revisar imagen manualmente."
        try:
            archivo_anotado = EVIDENCE_DIR / f"{event_id}_analizada.jpg"
            ia = analizar_imagen(foto, archivo_anotado)
            texto_ia = resumen_ia(ia)
            if ia.get("foto_anotada_local"):
                foto_telegram = archivo_anotado
            actualizar_seguro({
                "analisis_ia": ia,
                "foto_anotada_local": ia.get("foto_anotada_local"),
            })
            LOG.info("Analisis IA: %s | %s vehiculos | %s placas candidatas",
                     ia["estado"], sum(ia["vehiculos"].values()), len(ia["placas_candidatas"]))
        except Exception as exc:
            LOG.exception("IA fallo; se enviara la foto original")
            texto_ia = "No se pudo ejecutar IA; verifique foto original."
            actualizar_seguro({"analisis_ia": {
                "estado": "ERROR", "detalle": f"{type(exc).__name__}: {str(exc)[:160]}"
            }})
        # Enviar datos completos en el primer texto; imagen anotada + IA en segundo.
        pie_de_foto = (
            ("SIMULACRO - NO ES UNA EMERGENCIA\n" if simulacro else "ACCIDENTE CONFIRMADO\n")
            + f"Evento: {event_id}\n"
            + texto_ia
        )
        resultado_foto = notificar_foto_telegram(foto_telegram, pie_de_foto)
        # Se conserva el original sin anotaciones en Storage cuando esta habilitado.
        resultado_storage = almacenar_foto_storage(foto, event_id)
    else:
        LOG.warning("Sin foto disponible; el aviso de texto no depende de la camara")
        actualizar_seguro({"analisis_ia": {"estado": "SIN_FOTO"}})
        resultado_foto = {"estado": "SIN_FOTO"}
        resultado_storage = {"estado": "SIN_FOTO"}

    estado_final = (
        "NOTIFICADO"
        if resultado_texto["estado"] == "ENVIADO" or resultado_foto["estado"] == "ENVIADA"
        else "NOTIFICACION_FALLIDA"
    )
    try:
        evento.child("telegram").child("foto").set(resultado_foto)
    except Exception:
        LOG.exception("No se pudo registrar estado de foto Telegram")
    actualizar_seguro({
        "foto_storage": resultado_storage,
        "estado": estado_final,
    })
    LOG.info("Telegram foto: %s | Estado evento: %s", resultado_foto["estado"], estado_final)


def procesar_estado(mensaje: str) -> None:
    if mensaje == "IMPACTO_DETECTADO":
        cambios = {"estado_alerta": "ALERTA_PENDIENTE", "emergencia_confirmada": False}
    elif mensaje.startswith("FALSA ALARMA"):
        cambios = {"estado_alerta": "FALSA_ALARMA", "emergencia_confirmada": False}
    else:
        return
    db.reference("moto_sos/telemetria_actual").update(cambios)
    LOG.info("Alerta -> Firebase: %s", cambios["estado_alerta"])


def trabajador() -> None:
    while not STOP.is_set():
        try:
            clase, valor = QUEUE.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            if clase == "emergencia":
                registrar_accidente(valor, simulacro=False)
            elif clase == "estado":
                procesar_estado(valor)
        except Exception:
            LOG.exception("Error procesando evento; MQTT seguira escuchando")
        finally:
            QUEUE.task_done()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        LOG.error("Error MQTT: %s", reason_code)
        return
    client.subscribe([(TOPIC_EMERGENCY, 0), (TOPIC_ALERT, 0)])
    LOG.info("Conectado y suscrito a emergencias y alertas")


def on_message(client, userdata, msg):
    global LAST_EMERGENCY
    texto = msg.payload.decode("utf-8", errors="replace").strip()
    if msg.topic == TOPIC_EMERGENCY:
        if "EMERGENCIA REAL" not in texto:
            return
        ahora = time.monotonic()
        with LAST_LOCK:
            if ahora - LAST_EMERGENCY < DEDUPE_SECONDS:
                LOG.warning("Emergencia repetida dentro de %ss; ignorada", DEDUPE_SECONDS)
                return
            LAST_EMERGENCY = ahora
        item = ("emergencia", datetime.now(ZoneInfo(TZ_NAME)))
    elif msg.topic == TOPIC_ALERT:
        item = ("estado", texto)
    else:
        return
    try:
        QUEUE.put_nowait(item)
    except queue.Full:
        LOG.error("Cola de eventos llena, no se proceso %s", msg.topic)


def main():
    parser = argparse.ArgumentParser(description="Notificador Moto-SOS")
    parser.add_argument("--probar-camara", action="store_true", help="No publica en Firebase ni en Telegram")
    parser.add_argument("--simulacro", action="store_true", help="Crea evento de prueba y envia Telegram marcado como simulacro")
    parser.add_argument("--probar-ia", action="store_true", help="Ejecuta YOLO+OCR localmente sin Firebase ni Telegram")
    parser.add_argument("--imagen", type=Path, help="Imagen local para --probar-ia (si se omite, usa camara IP)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.probar_camara:
        archivo = capturar_foto(EVIDENCE_DIR / f"prueba_camara_{int(time.time())}.jpg")
        print("Foto guardada:" if archivo else "No se pudo capturar foto:", archivo or "verifica las URL y la red")
        return

    if args.probar_ia:
        if args.imagen:
            foto = args.imagen
            if not foto.is_file():
                raise FileNotFoundError(f"No se encontro imagen: {foto}")
        else:
            foto = capturar_foto(EVIDENCE_DIR / f"prueba_ia_{int(time.time())}.jpg")
            if foto is None:
                raise RuntimeError("Camara no disponible: verifica URL y red")
        destino = EVIDENCE_DIR / f"{foto.stem}_analizada.jpg"
        ia = analizar_imagen(foto, destino)
        print("\n" + resumen_ia(ia))
        print("Estado:", ia["estado"])
        print("Imagen anotada:", destino if destino.is_file() else "No disponible")
        for error in ia["errores"]:
            print("Aviso:", error)
        return

    validar_configuracion()
    inicializar_firebase()
    LOG.info("Firebase conectado")

    if args.simulacro:
        registrar_accidente(datetime.now(ZoneInfo(TZ_NAME)), simulacro=True)
        return

    hilo = threading.Thread(target=trabajador, daemon=True, name="motosos-events")
    hilo.start()
    cliente = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"motosos_notificador_{uuid.uuid4().hex[:8]}",
    )
    cliente.on_connect = on_connect
    cliente.on_message = on_message
    try:
        cliente.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        LOG.info("Escuchando emergencias Moto-SOS...")
        cliente.loop_forever()
    except KeyboardInterrupt:
        LOG.info("Deteniendo servicio...")
    finally:
        # No interrumpe el trabajo de otras terminales.
        cliente.disconnect()
        STOP.set()
        hilo.join(timeout=3)


if __name__ == "__main__":
    main()
