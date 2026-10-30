# ============================================
# Proyecto:  Moto-SOS
# Archivo:   test_emergency_notifier.py
# Objetivo:  Validar registros, fallos externos y deduplicación de emergencias.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import queue
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import requests

from servidor import emergency_notifier as notifier


class Mensaje:
    topic = notifier.TOPIC_EMERGENCY
    payload = b"EMERGENCIA REAL: ENVIAR FOTOS Y UBICACION"


class TestEmergencyNotifier(unittest.TestCase):
    def setUp(self):
        notifier.LAST_EMERGENCY = 0.0
        while True:
            try:
                notifier.QUEUE.get_nowait()
                notifier.QUEUE.task_done()
            except queue.Empty:
                break

    def test_registro_firebase_puro(self):
        fecha = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
        telemetria = {
            "fuerza_g": 1.8,
            "temperatura": 28,
            "bpm": 74,
            "latitud": 21.12,
            "longitud": -101.68,
            "gps_disponible": True,
            "gps_ultima_confirmacion": int(fecha.timestamp() * 1000),
            "gps_estado": {"fix": True, "estado": "VALIDO"},
        }
        datos, mensaje = notifier.construir_registro_accidente(
            telemetria, fecha, simulacro=False
        )
        self.assertEqual(datos["tipo"], "EMERGENCIA_CONFIRMADA")
        self.assertEqual(datos["ubicacion_tipo"], "GPS_ACTUAL")
        self.assertEqual(datos["analisis_ia"]["estado"], "PENDIENTE")
        self.assertIn("21.120000", mensaje)

    def test_fallo_camara_no_lanza_excepcion(self):
        with tempfile.TemporaryDirectory() as temporal:
            destino = Path(temporal) / "foto.jpg"
            with (
                mock.patch.object(notifier, "CAMERA_SNAPSHOT_URL", "http://camara/shot.jpg"),
                mock.patch.object(notifier, "CAMERA_STREAM_URL", ""),
                mock.patch.object(
                    notifier.requests,
                    "get",
                    side_effect=requests.RequestException("sin red"),
                ),
            ):
                self.assertIsNone(notifier.capturar_foto(destino))

    def test_fallo_telegram_se_registra(self):
        with mock.patch.object(notifier, "_telegram_post", side_effect=TimeoutError("timeout")):
            resultado = notifier.notificar_texto_telegram("prueba")
        self.assertEqual(resultado["estado"], "ERROR")

    @mock.patch("servidor.emergency_notifier.time.monotonic", side_effect=[100.0, 105.0])
    def test_emergencia_duplicada_se_descarta(self, _monotonic):
        notifier.on_message(None, None, Mensaje())
        notifier.on_message(None, None, Mensaje())
        self.assertEqual(notifier.QUEUE.qsize(), 1)


if __name__ == "__main__":
    unittest.main()
