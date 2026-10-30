# ============================================
# Proyecto:  Moto-SOS
# Archivo:   emergencias.py
# Objetivo:  Maquina de estados de impacto, cancelacion y confirmacion.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
try:
    import utime as time
except ImportError:
    import time
import config


def _transcurrido(a, b):
    if hasattr(time, 'ticks_diff'):
        return time.ticks_diff(a, b)
    return a - b


class GestorEmergencias:
    """Estados: NORMAL, PENDIENTE. Rearme + inmunidad tras eventos.

    El umbral (1.5 G) es el mismo que el original: es experimental y
    puede activarse en movimientos normales. No diagnostica accidentes.
    """
    def __init__(self):
        self.pendiente = False
        self.inicio = None
        self.ultimo_fin = None
        self.inmunidad_ms = 0
        self.armado = True

    def actualizar(self, fuerza_g, boton_presionado, ahora):
        """Devuelve evento o None; no ejecuta llamadas de red."""
        if self.pendiente:
            if boton_presionado:
                return self._finalizar('FALSA ALARMA: CANCELADA POR EL PILOTO', ahora,
                                       config.INMUNIDAD_CANCELACION_MS)
            if _transcurrido(ahora, self.inicio) >= config.VENTANA_CANCELACION_MS:
                return self._finalizar('EMERGENCIA_CONFIRMADA', ahora,
                                       config.INMUNIDAD_CONFIRMACION_MS)
            return None

        if fuerza_g is None:
            return None
        if fuerza_g < config.UMBRAL_REARME_G:
            self.armado = True
        dentro_inmunidad = (self.ultimo_fin is not None and
                            _transcurrido(ahora, self.ultimo_fin) < self.inmunidad_ms)
        if self.armado and not dentro_inmunidad and fuerza_g > config.UMBRAL_IMPACTO_G:
            self.pendiente = True
            self.armado = False
            self.inicio = ahora
            return 'IMPACTO_DETECTADO'
        return None

    def cancelar_remoto(self, ahora):
        if not self.pendiente:
            return None
        return self._finalizar('FALSA ALARMA: CANCELADA POR APP', ahora,
                               config.INMUNIDAD_CANCELACION_MS)

    def _finalizar(self, evento, ahora, inmunidad):
        self.pendiente = False
        self.ultimo_fin = ahora
        self.inmunidad_ms = inmunidad
        return evento
