# ============================================
# Proyecto:  Moto-SOS
# Archivo:   sensores.py
# Objetivo:  Drivers MPU6050, MAX30102 y DHT11 con recuperacion I2C.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import math
import dht
from machine import Pin
try:
    import utime as time
except ImportError:
    import time
import config


def ticks_diff(a, b):
    return time.ticks_diff(a, b) if hasattr(time, 'ticks_diff') else a - b


def signed16(msb, lsb):
    v = (msb << 8) | lsb
    return v - 65536 if v >= 32768 else v


class MPU6050Sensor:
    def __init__(self, i2c):
        self.i2c = i2c
        self.disponible = False
        self.ultimo_intento = None
        self.fuerza_g = None

    def iniciar(self):
        try:
            if config.DIR_MPU6050 not in self.i2c.scan():
                raise OSError('MPU6050 ausente del bus')
            who = self.i2c.readfrom_mem(config.DIR_MPU6050, 0x75, 1)[0]
            if (who & 0x7E) != 0x68:
                raise OSError('WHO_AM_I MPU inesperado: {}'.format(hex(who)))
            self.i2c.writeto_mem(config.DIR_MPU6050, 0x6B, b'\x01')
            self.i2c.writeto_mem(config.DIR_MPU6050, 0x1C, b'\x00')  # +/-2g
            self.disponible = True
            print('MPU6050 inicializado; rango +/-2g')
        except Exception as exc:
            self.disponible = False
            print('MPU6050 no disponible:', repr(exc))
        return self.disponible

    def leer(self, ahora):
        if not self.disponible:
            if self.ultimo_intento is None or ticks_diff(ahora, self.ultimo_intento) >= config.REINTENTO_MPU_MS:
                self.ultimo_intento = ahora
                self.iniciar()
            return None
        try:
            b = self.i2c.readfrom_mem(config.DIR_MPU6050, 0x3B, 6)
            if len(b) != 6:
                raise OSError('MPU6050: lectura incompleta')
            ax = signed16(b[0], b[1]) / 16384.0
            ay = signed16(b[2], b[3]) / 16384.0
            az = signed16(b[4], b[5]) / 16384.0
            self.fuerza_g = round(math.sqrt(ax * ax + ay * ay + az * az), 2)
            return self.fuerza_g
        except Exception as exc:
            self.disponible = False
            print('MPU6050 error I2C:', repr(exc))
            return None


class SensorPulsoMAX30102:
    def __init__(self, i2c):
        self.i2c = i2c
        self.disponible = False
        self.ultimo_intento = None
        self.bpm = 0
        self.ir_baseline = None
        self.ir_anterior = 0
        self.ultimo_latido = 0
        self.intervalos = []

    def _escribir(self, registro, valor):
        self.i2c.writeto(config.DIR_MAX30102, bytes((registro, valor)))

    def _leer_reg(self, registro):
        self.i2c.writeto(config.DIR_MAX30102, bytes((registro,)), False)
        return self.i2c.readfrom(config.DIR_MAX30102, 1, True)[0]

    def iniciar(self):
        try:
            if config.DIR_MAX30102 not in self.i2c.scan():
                raise OSError('MAX30102 ausente')
            if self._leer_reg(0xFF) != 0x15:
                raise OSError('ID MAX30102 incorrecto')
            self._escribir(0x09, 0x40)  # reset, sin espera prolongada
            time.sleep_ms(100) if hasattr(time, 'sleep_ms') else time.sleep(0.1)
            self._escribir(0x04, 0x00)
            self._escribir(0x05, 0x00)
            self._escribir(0x06, 0x00)
            self._escribir(0x08, 0x10)
            self._escribir(0x09, 0x03)
            self._escribir(0x0A, 0x23)
            self._escribir(0x0C, 0x3F)
            self._escribir(0x0D, 0x3F)
            if (self._leer_reg(0x09) & 0x07) != 0x03:
                raise OSError('MAX30102 no entro en modo SpO2')
            self.disponible = True
            self.bpm = 0
            self.ir_baseline = None
            self.intervalos = []
            print('MAX30102 inicializado')
        except Exception as exc:
            self.disponible = False
            print('MAX30102 no disponible:', repr(exc))
        return self.disponible

    def _leer_fifo(self):
        wr = self._leer_reg(0x04) & 0x1F
        rd = self._leer_reg(0x06) & 0x1F
        if wr == rd:
            return None
        self.i2c.writeto(config.DIR_MAX30102, b'\x07', False)
        datos = self.i2c.readfrom(config.DIR_MAX30102, 6, True)
        if len(datos) != 6:
            raise OSError('FIFO MAX incompleta')
        ir = ((datos[3] << 16) | (datos[4] << 8) | datos[5]) & 0x3FFFF
        return ir

    def _procesar_ir(self, ir, ahora):
        # Mismo algoritmo de linea base y mediana de 5 BPM que el original.
        if ir < 50000:
            self.bpm = 0
            self.ir_baseline = None
            self.ultimo_latido = ahora
            self.intervalos = []
            self.ir_anterior = ir
            return
        if self.ir_baseline is None:
            self.ir_baseline = ir
            self.ir_anterior = ir
            self.ultimo_latido = ahora
            return
        self.ir_baseline += (ir - self.ir_baseline) * 0.05
        umbral = self.ir_baseline - 200
        if ir < umbral and self.ir_anterior >= umbral:
            delta = ticks_diff(ahora, self.ultimo_latido)
            if 375 < delta < 1500:
                bpm_bruto = int(60000 / delta)
                self.intervalos.append(bpm_bruto)
                if len(self.intervalos) > 5:
                    self.intervalos.pop(0)
                valores = sorted(self.intervalos)
                self.bpm = valores[len(valores) // 2]
            if delta > 350:
                self.ultimo_latido = ahora
        self.ir_anterior = ir

    def actualizar(self, ahora):
        if not self.disponible:
            if self.ultimo_intento is None or ticks_diff(ahora, self.ultimo_intento) >= config.REINTENTO_MAX_MS:
                self.ultimo_intento = ahora
                self.iniciar()
            return
        try:
            # Cuota pequena por iteracion para que GPS, boton y MQTT progresen.
            for _ in range(3):
                ir = self._leer_fifo()
                if ir is None:
                    break
                self._procesar_ir(ir, time.ticks_ms() if hasattr(time, 'ticks_ms') else ahora)
        except OSError as exc:
            self.disponible = False
            print('MAX30102 error I2C:', repr(exc))


class TemperaturaDHT:
    def __init__(self):
        self.sensor = dht.DHT11(Pin(config.PIN_DHT))
        self.valor = None

    def actualizar(self):
        try:
            self.sensor.measure()
            self.valor = self.sensor.temperature()
        except Exception as exc:
            print('DHT11 error:', repr(exc))
            self.valor = None
        return self.valor
