# ============================================
# Proyecto:  Moto-SOS
# Archivo:   vision_ia.py
# Objetivo:  Detectar objetos y proponer matrículas candidatas en evidencias.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
"""Moto-SOS Vision v2: YOLO para contexto, EasyOCR multi-ROI para placas.
Las matriculas son CANDIDATAS, no identificaciones verificadas.
PLATE_MODEL_PATH es opcional: debe apuntar a pesos entrenados para localizar placas.
"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter
from pathlib import Path

import cv2

from servidor.configuracion import REPO_ROOT, YOLO_DEFAULT_MODEL

LOG = logging.getLogger('MotoSOS.IA')
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = os.getenv('YOLO_MODEL_PATH', str(YOLO_DEFAULT_MODEL)).strip()
PLATE_MODEL_PATH = os.getenv('PLATE_MODEL_PATH', '').strip()
CONF_THRESHOLD = float(os.getenv('YOLO_CONF', '0.35'))
OCR_THRESHOLD = float(os.getenv('OCR_CONF', '0.23'))
CAMERA_ROTATION = os.getenv('CAMERA_ROTATION', 'NONE').upper().strip()
MAX_VEHICLES_OCR = 7

VEHICLE_NAMES = {'car': 'Automovil', 'motorcycle': 'Motocicleta',
                 'bus': 'Autobus', 'truck': 'Camion'}
TRANSLATIONS = {
    'person': 'Persona', 'bicycle': 'Bicicleta', 'car': 'Automovil',
    'motorcycle': 'Motocicleta', 'bus': 'Autobus', 'truck': 'Camion',
    'traffic light': 'Semaforo', 'stop sign': 'Senal de alto',
    'bench': 'Banca', 'dog': 'Perro', 'cat': 'Gato', 'backpack': 'Mochila',
    'handbag': 'Bolso', 'umbrella': 'Paraguas', 'bird': 'Ave',
    'fire hydrant': 'Hidrante', 'parking meter': 'Parquimetro',
    'chair': 'Silla', 'cell phone': 'Telefono',
}
# No es un padron legal exhaustivo. Se aceptan variantes con marcadores de cautela.
PLATE_PATTERNS = [
    ('MOTO_2N3L1N', re.compile(r'^\d{2}[A-Z]{3}\d$')),
    ('3L3N1L', re.compile(r'^[A-Z]{3}\d{3}[A-Z]$')),
    ('3L3N', re.compile(r'^[A-Z]{3}\d{3}$')),
    ('MIXTO_NUM_INICIAL', re.compile(r'^\d{2,4}[A-Z]{2,4}\d{0,2}$')),
    ('MIXTO_LETRA_INICIAL', re.compile(r'^[A-Z]{2,4}\d{2,4}[A-Z0-9]{0,2}$')),
]
OCR_EXCLUDE = ('RUTA', 'POLICIA', 'AMBULANCIA', 'MEXICO', 'GUANAJUATO', 'AUTOBUS')
_yolo = None
_ocr = None
_plate_yolo = None


def _modelo(ruta):
    from ultralytics import YOLO
    candidato = Path(ruta)
    if not candidato.is_absolute():
        if (REPO_ROOT / candidato).is_file():
            candidato = REPO_ROOT / candidato
        elif (BASE_DIR / candidato).is_file():
            candidato = BASE_DIR / candidato
    return YOLO(str(candidato))


def _load_yolo():
    global _yolo
    if _yolo is None:
        LOG.info('Cargando YOLO %s', MODEL_PATH)
        _yolo = _modelo(MODEL_PATH)
    return _yolo


def _load_plate_yolo():
    global _plate_yolo
    if not PLATE_MODEL_PATH:
        return None
    if _plate_yolo is None:
        _plate_yolo = _modelo(PLATE_MODEL_PATH)
    return _plate_yolo


def _load_ocr():
    global _ocr
    if _ocr is None:
        import easyocr
        LOG.info('Cargando EasyOCR CPU')
        _ocr = easyocr.Reader(['es', 'en'], gpu=False)
    return _ocr


def normalizar_texto(texto):
    return re.sub(r'[^A-Z0-9]', '', str(texto).upper())


def formato_placa(texto):
    t = normalizar_texto(texto)
    if len(t) < 5 or len(t) > 9 or any(x in t for x in OCR_EXCLUDE):
        return None
    if not any(c.isalpha() for c in t) or not any(c.isdigit() for c in t):
        return None
    for nombre, patron in PLATE_PATTERNS:
        if patron.fullmatch(t):
            return nombre
    return None


def _rotar(frame):
    rot = {'NONE': None, '90_CW': cv2.ROTATE_90_CLOCKWISE,
           '90_CCW': cv2.ROTATE_90_COUNTERCLOCKWISE, '180': cv2.ROTATE_180}
    if CAMERA_ROTATION not in rot:
        raise ValueError('CAMERA_ROTATION invalida')
    return cv2.rotate(frame, rot[CAMERA_ROTATION]) if rot[CAMERA_ROTATION] is not None else frame


def _dibujar(image, box, etiqueta, color=(12, 190, 35)):
    h, w = image.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in box)
    x1, x2 = max(0, min(x1, w - 1)), max(0, min(x2, w - 1))
    y1, y2 = max(0, min(y1, h - 1)), max(0, min(y2, h - 1))
    if x2 <= x1 or y2 <= y1:
        return
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
    cv2.putText(image, etiqueta[:40], (x1, max(16, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.53, color, 2, cv2.LINE_AA)


def _roi(frame, rect):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [int(n) for n in rect]
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    if x2 - x1 < 32 or y2 - y1 < 20:
        return None
    return frame[y1:y2, x1:x2]


def _ocr_calls(frame, vehiculos, errores):
    """Escaneo global + regiones de vehiculos y placas personalizadas si existen."""
    h, w = frame.shape[:2]
    regiones = [('escena_completa', (0, 0, w, h))]
    for clase, box in vehiculos[:MAX_VEHICLES_OCR]:
        x1, y1, x2, y2 = box
        alto = y2 - y1
        ancho = x2 - x1
        # Incluye la parte inferior (placas traseras) y parte media (delanteras).
        regiones.append((f'{clase}_completo', (
            x1 - int(ancho * .06), y1 - int(alto * .05),
            x2 + int(ancho * .06), y2 + int(alto * .06))))
        regiones.append((f'{clase}_inferior', (
            x1 - int(ancho * .04), y1 + int(alto * .40),
            x2 + int(ancho * .04), y2 + int(alto * .05))))

    if PLATE_MODEL_PATH:
        try:
            resultado = _load_plate_yolo().predict(source=frame, conf=.25, imgsz=960, verbose=False)
            for r in resultado:
                for box in r.boxes:
                    x1, y1, x2, y2 = [int(x) for x in box.xyxy[0].tolist()]
                    marg = max(8, int((y2 - y1) * .22))
                    regiones.append(('detector_placas', (x1-marg, y1-marg, x2+marg, y2+marg)))
        except Exception as exc:
            errores.append('Detector de placas: ' + str(exc)[:90])

    vistos_roi = set()
    lector = _load_ocr()
    hallazgos = {}

    for nombre, rect in regiones[:20]:
        rect = (max(0, rect[0]), max(0, rect[1]), min(w, rect[2]), min(h, rect[3]))
        if rect in vistos_roi:
            continue
        vistos_roi.add(rect)
        recorte = _roi(frame, rect)
        if recorte is None:
            continue
        rh, rw = recorte.shape[:2]
        max_dim = max(rh, rw)
        factor = min(3.0, max(1.0, 1450.0 / max_dim))
        nueva = cv2.resize(recorte, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        gris = cv2.cvtColor(nueva, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        mejorada = clahe.apply(gris)
        # La escena completa: solo 1 variante; regiones: original y contraste mejorado.
        versiones = [nueva] if nombre == 'escena_completa' else [nueva, mejorada]
        for variante in versiones:
            try:
                resultados = lector.readtext(
                    variante, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- ',
                    mag_ratio=1.0, min_size=6, detail=1,
                    text_threshold=0.55, low_text=0.3, contrast_ths=0.15,
                )
            except Exception as exc:
                LOG.exception('OCR fallido en %s', nombre)
                errores.append('OCR: ' + str(exc)[:100])
                continue
            # Se prueban tokens individuales y pares cercanos; el OCR a veces parte una placa.
            posibles = list(resultados)
            for i, a in enumerate(resultados):
                for b in resultados[i+1:i+4]:
                    try:
                        ax = max(float(p[0]) for p in a[0]); ay = sum(float(p[1]) for p in a[0]) / 4
                        bx = min(float(p[0]) for p in b[0]); by = sum(float(p[1]) for p in b[0]) / 4
                        ah = max(float(p[1]) for p in a[0]) - min(float(p[1]) for p in a[0])
                        if 0 <= bx-ax <= max(ah*2, 60) and abs(ay-by) <= max(ah*.65, 10):
                            xy = [list(p) for p in a[0]] + [list(p) for p in b[0]]
                            bbox = [[min(x[0] for x in xy), min(x[1] for x in xy)]] * 4
                            posibles.append((bbox, str(a[1])+str(b[1]), min(float(a[2]), float(b[2]))))
                    except (ValueError, TypeError, IndexError):
                        continue

            for bbox, texto, confianza in posibles:
                placa = normalizar_texto(texto)
                formato = formato_placa(placa)
                if not formato or float(confianza) < OCR_THRESHOLD:
                    continue
                try:
                    xs = [float(p[0]) for p in bbox]; ys = [float(p[1]) for p in bbox]
                    xyxy = [
                        int(rect[0] + min(xs)/factor), int(rect[1] + min(ys)/factor),
                        int(rect[0] + max(xs)/factor), int(rect[1] + max(ys)/factor),
                    ]
                except (IndexError, ValueError, TypeError):
                    xyxy = None
                anterior = hallazgos.get(placa)
                if anterior is None:
                    hallazgos[placa] = {
                        'texto': placa, 'formato': formato,
                        'confianza_ocr': round(float(confianza), 3),
                        'apariciones': 1,
                        'zonas': [nombre], 'bbox': xyxy,
                        'verificada': False,
                    }
                else:
                    anterior['apariciones'] += 1
                    if nombre not in anterior['zonas']:
                        anterior['zonas'].append(nombre)
                    if float(confianza) > anterior['confianza_ocr']:
                        anterior['confianza_ocr'] = round(float(confianza), 3)
                        anterior['bbox'] = xyxy

    return sorted(hallazgos.values(), key=lambda p: (p['apariciones'], p['confianza_ocr']), reverse=True)[:15]


def analizar_imagen(archivo: Path, anotada: Path) -> dict:
    frame = cv2.imread(str(archivo))
    if frame is None:
        raise ValueError('No se pudo abrir foto: ' + str(archivo))
    frame = _rotar(frame)
    dibujada = frame.copy()
    errores, objetos, vehiculos_roi = [], [], []
    try:
        resultados = _load_yolo().predict(source=frame, conf=CONF_THRESHOLD, imgsz=960, verbose=False)
        for result in resultados:
            if result.boxes is None:
                continue
            for box in result.boxes:
                clase = str(result.names[int(box.cls[0].item())])
                confianza = float(box.conf[0].item())
                bbox = [int(v) for v in box.xyxy[0].tolist()]
                if len(objetos) < 80:
                    objetos.append({
                        'clase': clase, 'descripcion': TRANSLATIONS.get(clase, clase),
                        'confianza': round(confianza, 3), 'bbox': bbox,
                    })
                _dibujar(dibujada, bbox, f"{TRANSLATIONS.get(clase, clase)} {confianza:.0%}")
                if clase in VEHICLE_NAMES:
                    vehiculos_roi.append((clase, bbox))
    except Exception as exc:
        LOG.exception('Fallo YOLO')
        errores.append('YOLO: ' + str(exc)[:120])
    try:
        placas = _ocr_calls(frame, vehiculos_roi, errores)
        for p in placas:
            if p['bbox']:
                _dibujar(dibujada, p['bbox'], 'Placa? ' + p['texto'], (0, 180, 255))
    except Exception as exc:
        LOG.exception('Fallo general OCR')
        errores.append('OCR: ' + str(exc)[:120])
        placas = []

    vehiculos = Counter(o['descripcion'] for o in objetos if o['clase'] in VEHICLE_NAMES)
    entorno = Counter(o['descripcion'] for o in objetos if o['clase'] not in VEHICLE_NAMES)
    anotada.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(anotada), dibujada):
        errores.append('No se pudo guardar foto anotada')
    estado = 'PARCIAL' if errores and (objetos or placas) else 'ERROR' if errores else 'OK'
    return {
        'estado': estado, 'motor_objetos': MODEL_PATH,
        'motor_ocr': 'EasyOCR multirregion CLAHE + filtros placas',
        'objetos': objetos, 'vehiculos': dict(vehiculos), 'entorno': dict(entorno),
        'placas_candidatas': placas, 'placas_verificadas': False,
        'foto_anotada_local': anotada.name if anotada.is_file() else None,
        'errores': errores,
        'aviso': 'Placas candidatas y objetos visibles; revisar manualmente, no se atribuye participacion.',
    }


def resumen_ia(resultado: dict) -> str:
    if resultado.get('estado') == 'ERROR':
        return 'IA no disponible; revisar fotografia original.'
    vehiculos = resultado.get('vehiculos') or {}
    entorno = resultado.get('entorno') or {}
    placas = resultado.get('placas_candidatas') or []

    def c(d):
        return ', '.join(f'{n} {tipo}' for tipo, n in d.items()) or 'Ninguno'

    placa_txt = ', '.join(p['texto'] for p in placas) or 'Sin candidatas'
    return (
        'ANALISIS VISUAL (no verificado)\n'
        f'Vehiculos: {c(vehiculos)}\n'
        f'Objetos/personas: {c(entorno)}\n'
        f'Posibles placas OCR: {placa_txt}\n'
        'Verificar matrículas y contexto visualmente; no prueba involucramiento.'
    )
