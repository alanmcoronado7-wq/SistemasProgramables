# ============================================
# Proyecto:  Moto-SOS
# Archivo:   app.py
# Objetivo:  Orquestar sensores, GPS, red, telemetria y FSM de impacto.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
from machine import Pin, SoftI2C, UART
try:
    import utime as time
except ImportError:
    import time

import config
from actuadores import Actuadores
from comunicaciones import EnlaceMQTT
from emergencias import GestorEmergencias
from gps_motosos import GPSNMEA
from sensores import MPU6050Sensor, SensorPulsoMAX30102, TemperaturaDHT
from telemetria import publicar_gps, publicar_telemetria


def _diff(a, b):
    return time.ticks_diff(a, b) if hasattr(time, 'ticks_diff') else a - b


class MotoSOSApp:
    def __init__(self):
        self.salida = Actuadores()
        i2c = SoftI2C(scl=Pin(config.SCL_I2C), sda=Pin(config.SDA_I2C),
                      freq=config.FRECUENCIA_I2C)
        self.mpu = MPU6050Sensor(i2c)
        self.max = SensorPulsoMAX30102(i2c)
        self.dht = TemperaturaDHT()
        try:
            self.uart = UART(2, baudrate=config.GPS_BAUDIOS,
                             tx=config.PIN_GPS_TX_ESP32,
                             rx=config.PIN_GPS_RX_ESP32,
                             timeout=0, rxbuf=1024)
        except TypeError:  # Variantes MicroPython sin rxbuf.
            self.uart = UART(2, baudrate=config.GPS_BAUDIOS,
                             tx=config.PIN_GPS_TX_ESP32,
                             rx=config.PIN_GPS_RX_ESP32, timeout=0)
        self.gps = GPSNMEA(vencimiento_ms=config.GPS_FIX_VIGENCIA_MS)
        self.emergencia = GestorEmergencias()
        self.mqtt = EnlaceMQTT(self._recibir_comando)
        self.ultimo_mpu = None
        self.ultimo_envio = None
        self.fuerza_g = None
        self.temperatura = None

    def _recibir_comando(self, topico, mensaje):
        ahora = time.ticks_ms()
        valor = mensaje.strip().upper()
        if topico == config.TOP_CANCELAR_CMD:
            if valor == b'ON':
                evento = self.emergencia.cancelar_remoto(ahora)
                if evento:
                    self._manejar_evento(evento, ahora)
            return
        if self.salida.comando(topico, valor):
            print('Control remoto:', topico, valor)

    def _poll_gps(self, ahora):
        try:
            # Lectura por fragmentos (readline con timeout puede esperar a \n).
            # Limitar procesamiento evita robar tiempo al MAX30102.
            for _ in range(8):
                disponibles = self.uart.any()
                if not disponibles:
                    break
                bloque = self.uart.read(min(disponibles, 256))
                if bloque:
                    self.gps.feed(bloque, ahora)
        except OSError as exc:
            print('GPS UART error:', repr(exc))

    def _manejar_evento(self, evento, ahora):
        if evento == 'IMPACTO_DETECTADO':
            self.salida.activar_alerta()
            self.mqtt.publicar(config.TOP_ACELERACION,
                               self.fuerza_g if self.fuerza_g is not None else 0)
            self.mqtt.publicar(config.TOP_ALERTA, 'IMPACTO_DETECTADO')
            print('IMPACTO: 5 segundos para cancelar')
        elif evento.startswith('FALSA ALARMA'):
            self.salida.detener_alerta()
            self.mqtt.publicar(config.TOP_ALERTA, evento)
            print(evento)
        elif evento == 'EMERGENCIA_CONFIRMADA':
            self.salida.detener_alerta()
            # Publicar ubicacion y datos disponibles antes del evento MQTT.
            # El servidor los guarda de manera asincrona; puede existir un
            # desfase y no garantiza consistencia atomica del historico.
            publicar_telemetria(self.mqtt, self.fuerza_g, self.temperatura,
                                self.max.bpm, self.gps, ahora)
            self.mqtt.publicar(config.TOP_EMERGENCIA,
                               'EMERGENCIA REAL: ENVIAR FOTOS Y UBICACION')
            print('Emergencia confirmada y publicada a MQTT')

    def run(self):
        self.mpu.iniciar()
        self.max.iniciar()
        print('Moto-SOS modular iniciado. GPS: 9600 NMEA; sin comando UBX no verificado')
        print('GPS: prueba al aire libre, con antena orientada al cielo')
        try:
            while True:
                ahora = time.ticks_ms()
                self._poll_gps(ahora)
                self.max.actualizar(ahora)
                self.mqtt.actualizar(ahora)

                if self.ultimo_mpu is None or _diff(ahora, self.ultimo_mpu) >= config.LECTURA_MPU_MS:
                    self.ultimo_mpu = ahora
                    valor = self.mpu.leer(ahora)
                    if valor is not None:
                        self.fuerza_g = valor
                    # La FSM se actualiza incluso si falla el MPU para
                    # respetar temporizador de 5 s y boton cancelar.
                    evento = self.emergencia.actualizar(
                        valor, self.salida.boton_presionado(), ahora)
                    if evento:
                        self._manejar_evento(evento, ahora)

                if self.ultimo_envio is None or _diff(ahora, self.ultimo_envio) >= config.TELEMETRIA_MS:
                    self.ultimo_envio = ahora
                    self.temperatura = self.dht.actualizar()
                    self.salida.ajustar_ventilador(self.temperatura)
                    publicar_telemetria(self.mqtt, self.fuerza_g, self.temperatura,
                                        self.max.bpm, self.gps, ahora)
                # Pausa corta para reducir CPU; nunca 500 ms/5 s en el loop.
                time.sleep_ms(5)
        finally:
            self.salida.apagar_todo()
            self.mqtt.cerrar()
            print('Moto-SOS: salidas apagadas; enlace cerrado')
