# ============================================
# Proyecto:  Moto-SOS
# Archivo:   config.py
# Objetivo:  Pines, umbrales y topicos compartidos del firmware.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================

# Pines confirmados en el firmware original.
SDA_I2C = 21
SCL_I2C = 22
FRECUENCIA_I2C = 50000
PIN_DHT = 15
PIN_BUZZER = 18
PIN_VENTILADOR = 19
PIN_VIBRADOR = 13
PIN_CANCELAR = 4
PIN_GPS_TX_ESP32 = 27
PIN_GPS_RX_ESP32 = 26
GPS_BAUDIOS = 9600

# Hardware
DIR_MAX30102 = 0x57
DIR_MPU6050 = 0x68
UMBRAL_VENTILADOR_C = 22  # Original enviado por usuario: >22 C.
UMBRAL_IMPACTO_G = 1.5
UMBRAL_REARME_G = 1.2
VENTANA_CANCELACION_MS = 5000
INMUNIDAD_CANCELACION_MS = 3000
INMUNIDAD_CONFIRMACION_MS = 15000

# Publicacion: NO modificar sin cambiar tambien el puente Python.
TOP_ACELERACION = b'motosos/aceleracion'
TOP_TEMPERATURA = b'motosos/temperatura'
TOP_PULSO = b'motosos/pulso'
TOP_UBICACION = b'motosos/ubicacion'
TOP_GPS_ESTADO = b'motosos/gps/estado'
TOP_ALERTA = b'motosos/alerta'
TOP_EMERGENCIA = b'motosos/emergencia/confirmada'

# Suscripciones remotas, conservadas.
TOP_BUZZER_CMD = b'motosos/buzzer/cmd'
TOP_VENTILADOR_CMD = b'motosos/ventilador/cmd'
TOP_VIBRADOR_CMD = b'motosos/vibrador/cmd'
TOP_CANCELAR_CMD = b'motosos/cancelar/cmd'
TOPICOS_COMANDOS = (TOP_BUZZER_CMD, TOP_VENTILADOR_CMD,
                    TOP_VIBRADOR_CMD, TOP_CANCELAR_CMD)

BROKER_MQTT = 'broker.hivemq.com'  # SOLO DEMOSTRACIONES EN AMBIENTE CONTROLADO
PUERTO_MQTT = 1883
ID_CLIENTE_MQTT = 'moto_sos_esp32_final'

TELEMETRIA_MS = 2000
LECTURA_MPU_MS = 30
REINTENTO_MAX_MS = 3000
REINTENTO_MPU_MS = 5000
REINTENTO_MQTT_MS = 5000
REINTENTO_WIFI_MS = 10000
GPS_FIX_VIGENCIA_MS = 30000
