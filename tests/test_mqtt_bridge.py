# ============================================
# Proyecto:  Moto-SOS
# Archivo:   test_mqtt_bridge.py
# Objetivo:  Validar conversión MQTT y diagnóstico GPS sin servicios externos.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import json
import unittest
from unittest import mock

from servidor import mqtt_bridge


class Mensaje:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload.encode("utf-8")


class TestMQTTBridge(unittest.TestCase):
    def setUp(self):
        mqtt_bridge.pendientes.clear()
        mqtt_bridge.ultimo_fix = None
        mqtt_bridge.estado_gps_v2 = None

    def test_validacion_coordenadas(self):
        self.assertEqual(mqtt_bridge.parsear_coords("21.1, -101.7"), (21.1, -101.7))
        self.assertIsNone(mqtt_bridge.parsear_coords("91, 0"))
        self.assertIsNone(mqtt_bridge.parsear_coords("nan, 0"))

    def test_conversion_telemetria(self):
        mqtt_bridge.on_message(None, None, Mensaje("motosos/aceleracion", "1.678"))
        mqtt_bridge.on_message(None, None, Mensaje("motosos/pulso", "72"))
        self.assertEqual(mqtt_bridge.pendientes["fuerza_g"], 1.68)
        self.assertEqual(mqtt_bridge.pendientes["bpm"], 72)

    @mock.patch("servidor.mqtt_bridge.time.time", return_value=1_800_000_000.0)
    def test_estado_gps_genera_ultimo_fix(self, _time):
        payload = json.dumps({
            "fix": True,
            "estado": "VALIDO",
            "latitud": 21.123456,
            "longitud": -101.654321,
            "satelites": 7,
            "hdop": 1.1,
            "ultima_latitud": 21.123456,
            "ultima_longitud": -101.654321,
        })
        mqtt_bridge.on_message(None, None, Mensaje("motosos/gps/estado", payload))
        self.assertTrue(mqtt_bridge.pendientes["gps_disponible"])
        self.assertEqual(mqtt_bridge.pendientes["latitud"], 21.123456)
        self.assertEqual(
            mqtt_bridge.pendientes["_ultimo_fix_nuevo"]["calidad"],
            "FIX_REPORTADO_POR_MODULO",
        )


if __name__ == "__main__":
    unittest.main()
