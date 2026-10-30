# ============================================
# Proyecto:  Moto-SOS
# Archivo:   actuadores.py
# Objetivo:  Control seguro de buzzer, ventilador, vibrador y boton cancelar.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
from machine import Pin
import config


class Actuadores:
    def __init__(self):
        self.buzzer = Pin(config.PIN_BUZZER, Pin.OUT, value=0)
        self.vibrador = Pin(config.PIN_VIBRADOR, Pin.OUT, value=0)
        self.ventilador = Pin(config.PIN_VENTILADOR, Pin.OUT, value=0)
        self.boton = Pin(config.PIN_CANCELAR, Pin.IN, Pin.PULL_UP)
        self.ventilador_manual = False
        self.alerta = False

    def boton_presionado(self):
        return self.boton.value() == 0

    def activar_alerta(self):
        self.alerta = True
        self.buzzer.value(1)
        self.vibrador.value(1)

    def detener_alerta(self):
        self.alerta = False
        self.buzzer.value(0)
        self.vibrador.value(0)

    def comando(self, topico, valor):
        """El OFF del ventilador devuelve el control al modo automatico original."""
        if self.alerta or valor not in (b'ON', b'OFF'):
            return False
        encender = (valor == b'ON')
        if topico == config.TOP_BUZZER_CMD:
            self.buzzer.value(encender)
        elif topico == config.TOP_VIBRADOR_CMD:
            self.vibrador.value(encender)
        elif topico == config.TOP_VENTILADOR_CMD:
            self.ventilador_manual = encender
            self.ventilador.value(encender)
        else:
            return False
        return True

    def ajustar_ventilador(self, temperatura):
        if temperatura is not None and not self.ventilador_manual:
            self.ventilador.value(int(temperatura > config.UMBRAL_VENTILADOR_C))

    def apagar_todo(self):
        self.buzzer.value(0)
        self.vibrador.value(0)
        self.ventilador.value(0)
