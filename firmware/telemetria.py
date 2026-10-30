# ============================================
# Proyecto:  Moto-SOS
# Archivo:   telemetria.py
# Objetivo:  Publicar sensores y diagnostico GPS cada dos segundos.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import ujson
import config


def publicar_gps(mqtt, gps, ahora):
    mqtt.publicar(config.TOP_UBICACION, gps.ubicacion(ahora))
    mqtt.publicar(config.TOP_GPS_ESTADO, ujson.dumps(gps.estado(ahora)))


def publicar_telemetria(mqtt, fuerza_g, temperatura, bpm, gps, ahora):
    mqtt.publicar(config.TOP_ACELERACION, fuerza_g if fuerza_g is not None else 0)
    if temperatura is not None:
        mqtt.publicar(config.TOP_TEMPERATURA, temperatura)
    mqtt.publicar(config.TOP_PULSO, bpm)
    publicar_gps(mqtt, gps, ahora)
    print('Telemetria: G={}, Temp={}, BPM={}, GPS={}'.format(
        fuerza_g, temperatura, bpm, gps.estado(ahora)['estado']))
