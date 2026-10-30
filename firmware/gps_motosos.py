# ============================================
# Proyecto:  Moto-SOS
# Archivo:   gps_motosos.py
# Objetivo:  Analizar GGA/RMC con checksum y diagnosticar fix GPS.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
"""GPS no bloqueante para MicroPython/ESP32. NMEA GGA/RMC de talkers GP y GN.
No acelera físicamente satélites; diagnostica recepción y calidad de fix.
Uso: gps = GPSNMEA(); gps.feed(datos_uart, time.ticks_ms()); gps.estado(time.ticks_ms()).
"""
try:
    import utime as time
except ImportError:
    import time


def _diff(a, b):
    if hasattr(time, 'ticks_diff'):
        return time.ticks_diff(a, b)
    return a - b


def _coords(valor, hemisferio, latitud):
    if not valor or hemisferio not in ('N', 'S', 'E', 'W'):
        return None
    grados = 2 if latitud else 3
    try:
        deg = int(valor[:grados])
        minutos = float(valor[grados:])
        if minutos < 0 or minutos >= 60:
            return None
        dec = deg + minutos / 60.0
        if dec > (90 if latitud else 180):
            return None
        return -dec if hemisferio in ('S', 'W') else dec
    except (ValueError, TypeError):
        return None


class GPSNMEA:
    def __init__(self, vencimiento_ms=30000):
        self.buffer = b''
        self.vencimiento_ms = vencimiento_ms
        self.latitud = None
        self.longitud = None
        self.ultimo_fix = None
        self.ultimo_nmea = None
        self.satelites = None
        self.hdop = None
        self.calidad = 0
        self.tramas = 0
        self.checksum_invalidos = 0
        self.fix_reportado = False

    def feed(self, datos, ahora_ms):
        """Acepta fragmentos de UART, incluso lineas divididas entre lecturas."""
        if not datos:
            return
        self.buffer += datos
        # Evita consumir RAM con bytes ilegibles o sin fin de linea
        if len(self.buffer) > 1024 and b'\n' not in self.buffer:
            self.buffer = b''
            return
        while b'\n' in self.buffer:
            linea, self.buffer = self.buffer.split(b'\n', 1)
            if len(linea) <= 160:
                self._parsear(linea.strip(), ahora_ms)
        if len(self.buffer) > 1024:
            self.buffer = self.buffer[-160:]

    def _parsear(self, linea, ahora_ms):
        if not linea.startswith(b'$') or b'*' not in linea:
            return
        cuerpo, checksum = linea[1:].split(b'*', 1)
        try:
            esperado = int(checksum[:2], 16)
        except ValueError:
            return
        real = 0
        for byte in cuerpo:
            real ^= byte
        if real != esperado:
            self.checksum_invalidos += 1
            return
        campos = cuerpo.decode('ascii', 'ignore').split(',')
        tipo = campos[0]
        if len(tipo) < 5 or tipo[:2] not in ('GP', 'GN'):
            return
        tipo = tipo[-3:]
        if tipo not in ('GGA', 'RMC'):
            return
        self.tramas += 1
        self.ultimo_nmea = ahora_ms
        try:
            if tipo == 'GGA' and len(campos) > 8:
                self.calidad = int(campos[6] or 0)
                self.satelites = int(campos[7] or 0)
                self.hdop = float(campos[8]) if campos[8] else None
                valido = self.calidad > 0
                lat = _coords(campos[2], campos[3], True)
                lon = _coords(campos[4], campos[5], False)
            elif tipo == 'RMC' and len(campos) > 6:
                valido = campos[2] == 'A'
                lat = _coords(campos[3], campos[4], True)
                lon = _coords(campos[5], campos[6], False)
            else:
                return
            self.fix_reportado = valido
            if valido and lat is not None and lon is not None:
                self.latitud = lat
                self.longitud = lon
                self.ultimo_fix = ahora_ms
        except (ValueError, TypeError, IndexError):
            return

    def estado(self, ahora_ms):
        edad = _diff(ahora_ms, self.ultimo_fix) if self.ultimo_fix is not None else None
        nmea_edad = _diff(ahora_ms, self.ultimo_nmea) if self.ultimo_nmea is not None else None
        recibe_nmea = nmea_edad is not None and 0 <= nmea_edad < 5000
        # Un RMC valido anterior no debe convertirse en posicion presente indefinidamente
        fix = bool(edad is not None and 0 <= edad <= self.vencimiento_ms
                   and (nmea_edad is not None and nmea_edad <= self.vencimiento_ms)
                   and self.fix_reportado)
        if fix:
            nombre_estado = 'VALIDO'
        elif edad is not None and edad > self.vencimiento_ms:
            nombre_estado = 'CADUCADO'
        elif recibe_nmea:
            nombre_estado = 'SIN_FIX'
        else:
            nombre_estado = 'SIN_NMEA'
        return {
            'fix': fix,
            'estado': nombre_estado,
            'latitud': round(self.latitud, 6) if fix else None,
            'longitud': round(self.longitud, 6) if fix else None,
            'ultima_latitud': round(self.latitud, 6) if self.latitud is not None else None,
            'ultima_longitud': round(self.longitud, 6) if self.longitud is not None else None,
            'satelites': self.satelites,
            'hdop': self.hdop,
            'calidad': self.calidad,
            'edad_fix_seg': round(edad / 1000, 1) if edad is not None and edad >= 0 else None,
            'recibe_nmea': recibe_nmea,
            'tramas': self.tramas,
            'checksum_invalidos': self.checksum_invalidos,
        }

    def ubicacion(self, ahora_ms):
        estado = self.estado(ahora_ms)
        if estado['fix']:
            return '{:.6f}, {:.6f}'.format(estado['latitud'], estado['longitud'])
        return 'Esperando fix GPS...'
