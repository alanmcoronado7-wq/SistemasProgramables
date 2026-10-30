# ============================================
# Proyecto:  Moto-SOS
# Archivo:   comunicaciones.py
# Objetivo:  Wi-Fi y MQTT con reintentos temporizados y topicos existentes.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
import network
from umqtt.simple import MQTTClient
try:
    import utime as time
except ImportError:
    import time
import config
from config_local import WIFI_SSID, WIFI_PASSWORD


def _diff(a, b):
    return time.ticks_diff(a, b) if hasattr(time, 'ticks_diff') else a - b


class EnlaceMQTT:
    def __init__(self, callback):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.callback = callback
        self.cliente = None
        self.conectado = False
        self.ultimo_wifi = None
        self.ultimo_mqtt = None
        if (not WIFI_SSID or not WIFI_PASSWORD or
                WIFI_SSID.startswith('TU_RED_')):
            raise ValueError('Configura firmware/config_local.py con la red Wi-Fi')

    def actualizar(self, ahora):
        if not self.wlan.isconnected():
            self.conectado = False
            if self.ultimo_wifi is None or _diff(ahora, self.ultimo_wifi) >= config.REINTENTO_WIFI_MS:
                self.ultimo_wifi = ahora
                try:
                    self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)
                    print('Wi-Fi: conectando...')
                except OSError as exc:
                    print('Wi-Fi: fallo:', repr(exc))
            return

        if not self.conectado:
            if self.ultimo_mqtt is None or _diff(ahora, self.ultimo_mqtt) >= config.REINTENTO_MQTT_MS:
                self.ultimo_mqtt = ahora
                self._conectar_mqtt()
            return
        try:
            # check_msg NO espera nuevos mensajes; una conexion de socket rota
            # aun puede tardar durante los reintentos de TCP.
            self.cliente.check_msg()
        except OSError as exc:
            print('MQTT: conexion interrumpida:', repr(exc))
            self._desconectar()

    def _conectar_mqtt(self):
        try:
            self._desconectar()
            self.cliente = MQTTClient(config.ID_CLIENTE_MQTT,
                                      config.BROKER_MQTT,
                                      port=config.PUERTO_MQTT,
                                      keepalive=60)
            self.cliente.set_callback(self.callback)
            self.cliente.connect()
            for topico in config.TOPICOS_COMANDOS:
                self.cliente.subscribe(topico)
            self.conectado = True
            print('MQTT: conectado y comandos suscritos')
        except OSError as exc:
            print('MQTT: error conectando:', repr(exc))
            self._desconectar()

    def publicar(self, topico, dato):
        if not self.conectado:
            return False
        try:
            if not isinstance(dato, bytes):
                dato = str(dato).encode('utf-8')
            self.cliente.publish(topico, dato, retain=False)
            return True
        except OSError as exc:
            print('MQTT: publicacion fallida:', repr(exc))
            self._desconectar()
            return False

    def _desconectar(self):
        self.conectado = False
        if self.cliente is not None:
            try:
                self.cliente.disconnect()
            except Exception:
                pass
            self.cliente = None

    def cerrar(self):
        self._desconectar()
