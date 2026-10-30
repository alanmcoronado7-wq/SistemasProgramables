# ============================================
# Proyecto:  Moto-SOS
# Archivo:   configuracion.py
# Objetivo:  Centralizar rutas y variables de entorno del servidor Python.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
"""Configuración compartida; no contiene credenciales ni valores privados."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://moto-sos-7b12e-default-rtdb.firebaseio.com",
).strip()
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com").strip()
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))

_credentials_path = os.getenv(
    "FIREBASE_CREDENTIALS", "secrets/serviceAccountKey.json"
).strip()
CREDENTIALS = Path(_credentials_path)
if not CREDENTIALS.is_absolute():
    CREDENTIALS = REPO_ROOT / CREDENTIALS

EVIDENCE_DIR = REPO_ROOT / "evidencias"
YOLO_DEFAULT_MODEL = REPO_ROOT / "yolov8n.pt"
