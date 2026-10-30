# ============================================
# Proyecto:  Moto-SOS
# Archivo:   test_vision_ia.py
# Objetivo:  Validar filtros OCR y resumen IA sin cargar modelos ni imágenes.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import unittest

from servidor.ia.vision_ia import formato_placa, normalizar_texto, resumen_ia


class TestVisionIA(unittest.TestCase):
    def test_normaliza_y_clasifica_candidata(self):
        self.assertEqual(normalizar_texto("abc-123"), "ABC123")
        self.assertEqual(formato_placa("ABC123"), "3L3N")
        self.assertIsNone(formato_placa("AMBULANCIA"))

    def test_resumen_no_atribuye_participacion(self):
        resultado = {
            "estado": "OK",
            "vehiculos": {"Automovil": 1},
            "entorno": {"Persona": 2},
            "placas_candidatas": [{"texto": "ABC123"}],
        }
        texto = resumen_ia(resultado)
        self.assertIn("ABC123", texto)
        self.assertIn("no prueba involucramiento", texto)


if __name__ == "__main__":
    unittest.main()
