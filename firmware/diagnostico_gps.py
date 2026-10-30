# ============================================
# Proyecto:  Moto-SOS
# Archivo:   diagnostico_gps.py
# Objetivo:  Diagnosticar NEO-6M por UART sin iniciar MQTT ni sensores I2C.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
from machine import UART
import utime as time
from gps_motosos import GPSNMEA
import config


def main():
    uart = UART(2, baudrate=config.GPS_BAUDIOS, tx=config.PIN_GPS_TX_ESP32,
                rx=config.PIN_GPS_RX_ESP32, timeout=0)
    gps = GPSNMEA(vencimiento_ms=config.GPS_FIX_VIGENCIA_MS)
    ultimo = time.ticks_ms()
    print('GPS: comprobando UART 9600; coloca antena al aire libre')
    try:
        while True:
            ahora = time.ticks_ms()
            for _ in range(8):
                n = uart.any()
                if not n:
                    break
                bloque = uart.read(min(n, 256))
                if bloque:
                    gps.feed(bloque, ahora)
            if time.ticks_diff(ahora, ultimo) >= 5000:
                ultimo = ahora
                print(gps.estado(ahora))
            time.sleep_ms(10)
    except KeyboardInterrupt:
        print('Diagnostico detenido')


if __name__ == '__main__':
    main()
