"""Analisis visual Moto-SOS (PC): YOLOv8 COCO + EasyOCR.

Adapta el algoritmo original de servidor_ia.py sin Firebase ni MQTT propios.
Recibe una fotografia ya capturada por emergency_notifier.py y produce:
- objetos generales detectados por YOLO
- resumen de vehiculos y objetos del entorno
- posibles matriculas mediante EasyOCR (no validadas)
- imagen con recuadros

No identifica involucrados en un accidente ni clasifica policia/ambulancia.
"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter
from pathlib import Path

import cv2

LOG = logging.getLogger("MotoSOS.IA")
BASE_DIR = Path(__file__).resolve().parent

# Compatible con yolov8n.pt del proyecto previo. Tambien acepta ruta a modelo personalizado.
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt").strip()
CONF_THRESHOLD = float(os.getenv("YOLO_CONF", "0.35"))
OCR_THRESHOLD = float(os.getenv("OCR_CONF", "0.25"))  # Mismo umbral del algoritmo original
CAMERA_ROTATION = os.getenv("CAMERA_ROTATION", "NONE").strip().upper()

# Los IDs 2,3,5,7 conservan el mapa original de servidor_ia.py (COCO).
VEHICLE_NAMES = {"car": "Automovil", "motorcycle": "Motocicleta", "bus": "Autobus", "truck": "Camion"}
TRANSLATIONS = {
    "person": "Persona", "bicycle": "Bicicleta", "car": "Automovil",
    "motorcycle": "Motocicleta", "bus": "Autobus", "truck": "Camion",
    "traffic light": "Semaforo", "stop sign": "Senal de alto",
    "bench": "Banca", "dog": "Perro", "cat": "Gato", "backpack": "Mochila",
    "handbag": "Bolso", "umbrella": "Paraguas", "bird": "Ave",
    "fire hydrant": "Hidrante", "parking meter": "Parquimetro",
    "chair": "Silla", "cell phone": "Telefono", "carrot": "Zanahoria",
}
PLATE_REGEX = re.compile(r"^[A-Z]{1,4}-?[0-9]{2,4}-?[A-Z]{0,3}$")
OCR_EXCLUDE = ("RUTA", "BUS", "POLICIA", "AMBULANCIA")
_yolo = None
_ocr = None


def _load_yolo():
    global _yolo
    if _yolo is None:
        from ultralytics import YOLO
        model_candidate = Path(MODEL_PATH)
        if not model_candidate.is_absolute() and (BASE_DIR / model_candidate).exists():
            model_candidate = BASE_DIR / model_candidate
        LOG.info("Cargando modelo YOLO: %s", model_candidate)
        _yolo = YOLO(str(model_candidate))
    return _yolo


def _load_ocr():
    global _ocr
    if _ocr is None:
        import easyocr
        LOG.info("Cargando EasyOCR (es/en, CPU)...")
        _ocr = easyocr.Reader(["es", "en"], gpu=False)
    return _ocr


def _rotate(frame):
    mapping = {
        "NONE": None, "90_CW": cv2.ROTATE_90_CLOCKWISE,
        "90_CCW": cv2.ROTATE_90_COUNTERCLOCKWISE,
        "180": cv2.ROTATE_180,
    }
    if CAMERA_ROTATION not in mapping:
        raise ValueError("CAMERA_ROTATION debe ser NONE, 90_CW, 90_CCW o 180")
    return cv2.rotate(frame, mapping[CAMERA_ROTATION]) if mapping[CAMERA_ROTATION] is not None else frame


def _box_label(image, rect, texto, color):
    x1, y1, x2, y2 = (int(v) for v in rect)
    height, width = image.shape[:2]
    x1 = max(0, min(x1, width - 1))
    x2 = max(0, min(x2, width - 1))
    y1 = max(0, min(y1, height - 1))
    y2 = max(0, min(y2, height - 1))
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
    x_text = max(1, x1)
    y_text = max(15, y1 - 7)
    cv2.putText(image, texto[:45], (x_text, y_text), cv2.FONT_HERSHEY_SIMPLEX,
                0.54, color, 2, cv2.LINE_AA)


def analizar_imagen(archivo: Path, anotada: Path) -> dict:
    """Devuelve metadatos serializables a JSON. No guarda en Firebase ni envía Telegram."""
    frame = cv2.imread(str(archivo))
    if frame is None:
        raise ValueError(f"No se pudo leer foto: {archivo}")
    frame = _rotate(frame)
    dibujada = frame.copy()
    objetos, placas = [], []
    errores = []

    # A. Deteccion: misma base YOLO del servidor original, mas clases del entorno.
    try:
        resultados = _load_yolo().predict(source=frame, conf=CONF_THRESHOLD, verbose=False)
        for result in resultados:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                etiqueta_en = str(result.names[cls_id])
                tipo = TRANSLATIONS.get(etiqueta_en, etiqueta_en)
                conf = float(box.conf[0].item())
                xyxy = [int(v) for v in box.xyxy[0].tolist()]
                # Limitar tamano del registro para Realtime Database.
                if len(objetos) < 80:
                    objetos.append({
                        "clase": etiqueta_en,
                        "descripcion": tipo,
                        "confianza": round(conf, 3),
                        "bbox": xyxy,
                    })
                _box_label(dibujada, xyxy, f"{tipo} {conf:.0%}", (20, 200, 20))
    except Exception as exc:
        LOG.exception("No se pudo ejecutar YOLO")
        errores.append(f"YOLO: {type(exc).__name__}: {str(exc)[:120]}")

    # B. OCR: se conserva regex/zoom/filtro original, pero se etiquetan como CANDIDATAS.
    # EasyOCR no demuestra que el texto sea una placa de matricula.
    try:
        reader = _load_ocr()
        encontrados = reader.readtext(frame, mag_ratio=2.5)
        vistos = set()
        for bbox, texto, confianza in encontrados:
            posible = re.sub(r"\s+", "", str(texto).upper())
            if any(word in posible for word in OCR_EXCLUDE):
                continue
            if not PLATE_REGEX.fullmatch(posible) or float(confianza) <= OCR_THRESHOLD:
                continue
            if posible in vistos:
                continue
            vistos.add(posible)
            placas.append({"texto": posible, "confianza_ocr": round(float(confianza), 3),
                           "verificada": False})
            if len(placas) >= 15:
                break
            coords = [(int(p[0]), int(p[1])) for p in bbox]
            xs = [p[0] for p in coords]
            ys = [p[1] for p in coords]
            _box_label(dibujada, (min(xs), min(ys), max(xs), max(ys)),
                       f"Placa? {posible}", (0, 175, 255))
    except Exception as exc:
        LOG.exception("No se pudo ejecutar EasyOCR")
        errores.append(f"OCR: {type(exc).__name__}: {str(exc)[:120]}")

    vehiculos = Counter(o["descripcion"] for o in objetos if o["clase"] in VEHICLE_NAMES)
    entorno = Counter(o["descripcion"] for o in objetos if o["clase"] not in VEHICLE_NAMES)

    anotada.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(anotada), dibujada):
        errores.append("No se pudo guardar foto anotada")
        anotada_local = None
    else:
        anotada_local = anotada.name

    if len(errores) == 2 or (len(errores) > 0 and not objetos and not placas):
        estado = "ERROR" if not objetos and not placas else "PARCIAL"
    else:
        estado = "PARCIAL" if errores else "OK"

    return {
        "estado": estado,
        "motor_objetos": MODEL_PATH,
        "motor_ocr": "EasyOCR es/en + filtro de matriculas",
        "objetos": objetos,
        "vehiculos": dict(vehiculos),
        "entorno": dict(entorno),
        "placas_candidatas": placas,
        "placas_verificadas": False,
        "foto_anotada_local": anotada_local,
        "errores": errores,
        "aviso": "Detecciones preliminares. No identifican responsables ni confirman matriculas.",
    }


def resumen_ia(resultado: dict) -> str:
    """Texto breve para el pie de foto de Telegram (alerta y ubicacion ya enviados)."""
    if resultado.get("estado") == "ERROR":
        return "IA no disponible; revisar imagen original manualmente."
    vehiculos = resultado.get("vehiculos") or {}
    entorno = resultado.get("entorno") or {}
    placas = resultado.get("placas_candidatas") or []

    def compacto(conteo):
        return ", ".join(f"{cantidad} {tipo}" for tipo, cantidad in conteo.items()) or "Ninguno"

    placa_texto = ", ".join(p["texto"] for p in placas) or "Sin candidatas"
    return (
        "ANALISIS VISUAL (estimado)\n"
        f"Vehiculos visibles: {compacto(vehiculos)}\n"
        f"Otros objetos: {compacto(entorno)}\n"
        f"Posibles placas OCR: {placa_texto}\n"
        "Verificar placas y contexto visualmente; no se infiere participacion en accidente."
    )
