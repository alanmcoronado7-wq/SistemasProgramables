
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

BASE_DIR = Path(__file__).resolve().parent
CREDENCIALES = BASE_DIR / "secrets" / "serviceAccountKey.json"

DATABASE_URL = (
    "https://moto-sos-7b12e-default-rtdb.firebaseio.com"
)

cred = credentials.Certificate(str(CREDENCIALES))

firebase_admin.initialize_app(cred, {
    "databaseURL": DATABASE_URL
})

referencia = db.reference("moto_sos/prueba_conexion")

referencia.set({
    "estado": "CONECTADO",
    "origen": "Python",
    "mensaje": "Prueba Moto-SOS"
})

print("Datos enviados correctamente")
print("Datos recuperados:", referencia.get())
