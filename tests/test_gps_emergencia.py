# ============================================
# Proyecto:  Moto-SOS
# Archivo:   test_gps_emergencia.py
# Objetivo:  Comprobar parsing NMEA y transiciones de la FSM sin hardware.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'firmware'))
from gps_motosos import GPSNMEA
from emergencias import GestorEmergencias


def nmea(cuerpo):
    raw = cuerpo.encode('ascii')
    suma = 0
    for c in raw:
        suma ^= c
    return b'$' + raw + b'*' + ('%02X' % suma).encode('ascii') + b'\r\n'


class TestGPS(unittest.TestCase):
    def test_gngga_parcial(self):
        g = GPSNMEA(vencimiento_ms=30000)
        m = nmea('GNGGA,123519,2110.0000,N,10140.0000,W,1,08,0.8,12.3,M,0,M,,')
        g.feed(m[:13], 1000)
        assert not g.estado(1000)['fix']
        g.feed(m[13:], 1000)
        estado = g.estado(1000)
        self.assertTrue(estado['fix'])
        self.assertEqual(estado['satelites'], 8)
        self.assertAlmostEqual(estado['latitud'], 21.1666667, places=5)
        self.assertAlmostEqual(estado['longitud'], -101.6666667, places=5)

    def test_rmc_y_fix_caducado(self):
        g = GPSNMEA(vencimiento_ms=10000)
        g.feed(nmea('GPRMC,123519,A,2109.0000,N,10135.0000,W,0,0,301026,,,'), 2000)
        self.assertTrue(g.estado(3000)['fix'])
        self.assertFalse(g.estado(17000)['fix'])
        self.assertEqual(g.estado(17000)['estado'], 'CADUCADO')
        self.assertAlmostEqual(g.estado(17000)['ultima_latitud'], 21.15)
        self.assertEqual(g.ubicacion(17000), 'Esperando fix GPS...')

    def test_checksum_mal(self):
        g = GPSNMEA()
        g.feed(b'$GPGGA,123519,2110.0000,N,10140.0000,W,1,08,0.8*00\n', 1)
        self.assertFalse(g.estado(1)['fix'])
        self.assertEqual(g.estado(1)['checksum_invalidos'], 1)

    def test_no_fix_pese_a_recibir_tramas(self):
        g = GPSNMEA()
        g.feed(nmea('GPGGA,123519,,,,,0,00,99.9,,,,,,'), 5)
        self.assertEqual(g.estado(5)['estado'], 'SIN_FIX')
        self.assertFalse(g.estado(5)['fix'])


class TestEmergencias(unittest.TestCase):
    def test_impacto_cancelacion_remota(self):
        f = GestorEmergencias()
        self.assertEqual(f.actualizar(1.7, False, 1000), 'IMPACTO_DETECTADO')
        self.assertIsNone(f.actualizar(1.0, False, 3200))
        self.assertEqual(f.cancelar_remoto(3300), 'FALSA ALARMA: CANCELADA POR APP')
        self.assertFalse(f.pendiente)
        self.assertIsNone(f.actualizar(1.7, False, 3500))
        f.actualizar(1.0, False, 7000)
        self.assertEqual(f.actualizar(1.7, False, 7100), 'IMPACTO_DETECTADO')

    def test_confirmacion_5seg_y_rearme(self):
        f = GestorEmergencias()
        self.assertEqual(f.actualizar(1.8, False, 100), 'IMPACTO_DETECTADO')
        self.assertIsNone(f.actualizar(0.9, False, 5099))
        self.assertEqual(f.actualizar(0.9, False, 5100), 'EMERGENCIA_CONFIRMADA')
        self.assertIsNone(f.actualizar(2.0, False, 6000))
        f.actualizar(1.0, False, 21000)
        self.assertEqual(f.actualizar(1.8, False, 21200), 'IMPACTO_DETECTADO')

    def test_cancelacion_fisica(self):
        f = GestorEmergencias()
        f.actualizar(1.8, False, 100)
        self.assertEqual(f.actualizar(1.8, True, 400),
                         'FALSA ALARMA: CANCELADA POR EL PILOTO')


if __name__ == '__main__':
    unittest.main()
