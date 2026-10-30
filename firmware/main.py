# ============================================
# Proyecto:  Moto-SOS
# Archivo:   main.py
# Objetivo:  Punto de arranque del firmware modular en ESP32.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
from app import MotoSOSApp

if __name__ == '__main__':
    MotoSOSApp().run()
