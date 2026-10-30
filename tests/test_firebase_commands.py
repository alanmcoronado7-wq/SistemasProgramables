# ============================================
# Proyecto:  Moto-SOS
# Archivo:   test_firebase_commands.py
# Objetivo:  Validar comandos y cancelación Firebase mediante dobles de prueba.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import unittest
from types import SimpleNamespace
from unittest import mock

from servidor import firebase_commands


class ReferenciaFalsa:
    def __init__(self):
        self.callback = None
        self.valores = {}

    def listen(self, callback):
        self.callback = callback
        return self

    def child(self, nombre):
        self.nombre = nombre
        return self

    def set(self, valor):
        self.valores[self.nombre] = valor


class TestFirebaseCommands(unittest.TestCase):
    def test_cancelar_es_comando_de_un_solo_uso(self):
        referencia = ReferenciaFalsa()
        firebase_commands.crear_listener(object(), referencia)
        evento = SimpleNamespace(event_type="put", path="/cancelar", data="ON")
        with mock.patch.object(firebase_commands, "publicar_comando", return_value=True) as publicar:
            referencia.callback(evento)
        publicar.assert_called_once_with(mock.ANY, "cancelar", "ON")
        self.assertEqual(referencia.valores["cancelar"], "OFF")

    def test_valor_invalido_no_se_publica(self):
        referencia = ReferenciaFalsa()
        firebase_commands.crear_listener(object(), referencia)
        evento = SimpleNamespace(event_type="put", path="/buzzer", data="TAL_VEZ")
        with mock.patch.object(firebase_commands, "publicar_comando") as publicar:
            referencia.callback(evento)
        publicar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
