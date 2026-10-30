# Esquema de Firebase Realtime Database

Moto-SOS usa **Realtime Database**, no Firestore. Los ejemplos siguientes son ficticios y sólo documentan tipos y relaciones; no deben importarse como datos reales.

```text
moto_sos/
├── telemetria_actual/
├── comandos/
├── ubicacion_ultima_valida/
└── historico_accidentes/
    └── {id_generado_por_push}/
```

## Ejemplo ficticio

```json
{
  "moto_sos": {
    "telemetria_actual": {
      "fuerza_g": 1.08,
      "temperatura": 27,
      "bpm": 74,
      "ubicacion": "21.000000, -101.000000",
      "latitud": 21.0,
      "longitud": -101.0,
      "gps_disponible": true,
      "gps_estado": {
        "fix": true,
        "estado": "VALIDO",
        "satelites": 8,
        "hdop": 0.9,
        "edad_fix_seg": 1.2,
        "recibe_nmea": true
      },
      "estado_alerta": "NORMAL",
      "emergencia_confirmada": false,
      "ultima_actualizacion": 1793383200000
    },
    "comandos": {
      "buzzer": "OFF",
      "ventilador": "OFF",
      "vibrador": "OFF",
      "cancelar": "OFF"
    },
    "ubicacion_ultima_valida": {
      "latitud": 21.0,
      "longitud": -101.0,
      "timestamp": 1793383200000,
      "origen": "GPS_ESP32",
      "calidad": "FIX_REPORTADO_POR_MODULO",
      "satelites": 8,
      "hdop": 0.9
    },
    "historico_accidentes": {
      "-ID_FICTICIO": {
        "timestamp": 1793383205000,
        "fecha_hora_local": "2026-10-30T12:00:05-06:00",
        "tipo": "EMERGENCIA_CONFIRMADA",
        "estado": "NOTIFICADO",
        "fuerza_g_reportada": 2.1,
        "temperatura": 27,
        "bpm": 74,
        "latitud": 21.0,
        "longitud": -101.0,
        "ubicacion_tipo": "GPS_ACTUAL",
        "analisis_ia": {
          "estado": "OK",
          "vehiculos": {"Automovil": 1},
          "placas_candidatas": [
            {
              "texto": "ABC123",
              "confianza_ocr": 0.63,
              "verificada": false
            }
          ],
          "placas_verificadas": false,
          "aviso": "Ejemplo ficticio; no atribuye participación."
        },
        "telegram": {
          "mensaje": {"estado": "ENVIADO"},
          "foto": {"estado": "ENVIADA"}
        }
      }
    }
  }
}
```

## Escritura por proceso

| Proceso | Rutas principales |
|---|---|
| `servidor.mqtt_bridge` | `telemetria_actual`, `ubicacion_ultima_valida` |
| `servidor.firebase_commands` | Lee `comandos`; restablece `cancelar` a `OFF` |
| `servidor.emergency_notifier` | `telemetria_actual`, `historico_accidentes` |

## Reglas

[`reglas.json`](reglas.json) niega acceso global y exige usuarios autenticados con claims `motosos_reader` o `motosos_admin`. La escritura exige `motosos_admin`; los cuatro comandos sólo aceptan `ON` y `OFF`. El Firebase Admin SDK del servidor usa una cuenta de servicio y no depende de estas reglas.

El archivo es una propuesta versionable: **no se desplegó ni se modificó la base real**. Antes de aplicarlo deben configurarse Firebase Authentication y los custom claims correspondientes, probarse en Emulator Suite y revisarse desde la consola del proyecto.
