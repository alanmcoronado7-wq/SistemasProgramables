# ============================================
# Proyecto:  Moto-SOS
# Archivo:   test_firebase.py
# Objetivo:  Ejecutar manualmente una prueba explícita de lectura/escritura Firebase.
# Equipo:    Fernández Guerrero Cristóbal
#            García Silva Emmanuel Alejandro
#            Martínez Coronado Alan Mauricio
# Matrículas: PENDIENTES
# Materia:   Sistemas Programables — ISC TecNM León
# Semestre:  ago-dic-2026
# ============================================
"""Diagnóstico manual; nunca se ejecuta al importar el módulo ni desde unit tests."""

import argparse

import firebase_admin
from firebase_admin import credentials, db

from servidor.configuracion import CREDENTIALS, DATABASE_URL


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico Firebase Moto-SOS")
    parser.add_argument(
        "--confirmar-escritura",
        action="store_true",
        help="autoriza escribir en moto_sos/prueba_conexion",
    )
    args = parser.parse_args()
    if not args.confirmar_escritura:
        parser.error("falta --confirmar-escritura; no se modificó Firebase")

    firebase_admin.initialize_app(
        credentials.Certificate(str(CREDENTIALS)), {"databaseURL": DATABASE_URL}
    )
    referencia = db.reference("moto_sos/prueba_conexion")
    referencia.set({
        "estado": "CONECTADO",
        "origen": "Python",
        "mensaje": "Prueba Moto-SOS",
    })
    print("Datos enviados correctamente")
    print("Datos recuperados:", referencia.get())


if __name__ == "__main__":
    main()
