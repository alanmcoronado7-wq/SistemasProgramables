# Sprint 1 — Sensores, actuadores, MQTT y HAL

**Periodo académico:** agosto–diciembre de 2026

**Corte documental:** 30 de octubre de 2026

**Objetivo:** disponer de sensores leyendo, actuadores respondiendo y comunicación MQTT funcional, con una HAL documentada.

## Hardware

El prototipo registrado usa ESP32, MPU6050, MAX30102, DHT11, GPS NEO-6M, buzzer, motor vibrador, ventilador y botón de cancelación. El bus I2C se comparte en GPIO21/GPIO22; el GPS usa UART2 en GPIO27/GPIO26. La cámara IP de un teléfono sustituye a la ESP32-CAM y pertenece al lado servidor.

No se encontraron esquemático, STL ni fotografías públicas dentro del repositorio. Las conexiones derivadas del código están en [tabla_hal.md](tabla_hal.md) y requieren cotejo final con el montaje.

## Firmware

El punto de entrada es `firmware/main.py`. `MotoSOSApp` coordina:

- `sensores.py`: MPU6050, MAX30102, DHT11 y recuperación básica.
- `gps_motosos.py`: NMEA GGA/RMC, checksum, fix y última posición.
- `actuadores.py`: buzzer, vibrador, ventilador y botón.
- `emergencias.py`: impacto, ventana de 5 s, cancelación y protección contra repetición.
- `comunicaciones.py`: Wi-Fi, MQTT, comandos y reconexión.
- `telemetria.py`: publicaciones periódicas y diagnóstico GPS.

Para desplegar, se copian los **contenidos** de `firmware/` a la raíz del sistema de archivos del ESP32. `config_local.example.py` debe copiarse como `config_local.py` y completarse localmente.

## Comunicación MQTT

La telemetría se publica cada 2000 ms. La aceleración se lee cada 30 ms para alimentar la máquina de estados. El detalle de tópicos, payloads y dirección se conserva en [arquitectura.md](arquitectura.md#contrato-mqtt).

## HAL

La HAL documental está en [tabla_hal.md](tabla_hal.md); la distribución del código está explicada en [`firmware/hal/README.md`](../firmware/hal/README.md).

## Pruebas

### Funcionalidades verificadas previamente

Según el registro del proyecto antes de esta intervención se habían comprobado físicamente: MPU6050, DHT11, publicación/recepción MQTT, escritura de telemetría en Firebase, control remoto de buzzer/vibrador/ventilador, cancelación Firebase, confirmación MQTT, cámara IP, Telegram, YOLOv8 y OCR experimental. Estas pruebas **no se repitieron** después de reorganizar los archivos.

### Pruebas de escritorio de esta intervención

La suite automatizada usa `unittest` y dobles; no accede a Firebase, Telegram, broker, cámara ni ESP32 reales. Cubre parser NMEA y caducidad, transiciones/cancelaciones de emergencia, conversión MQTT, coordenadas, generación de registro, fallos de cámara/Telegram, deduplicación, comandos Firebase y filtros de IA. El resultado real de la última ejecución debe consultarse en la entrega de Codex o repetirse con:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

También se valida sintaxis con `compileall` y arranque no destructivo con `--help`.

### Pendiente en hardware real

- Revalidar todos los sensores y actuadores con el firmware ya reorganizado.
- Comprobar GPS al aire libre: recepción NMEA, tiempo hasta fix, satélites, HDOP y transición a `CADUCADO`.
- Confirmar cableado físico contra la tabla HAL y documentar etapa de potencia.
- Ejecutar un simulacro controlado de extremo a extremo con autorización; puede enviar Telegram y escribir Firebase.
- Volver a probar cámara e IA bajo iluminación y movimiento representativos.

## Evidencias

- Circuito en protoboard: **PENDIENTE de incorporar**.
- Telemetría MQTT: **PENDIENTE de incorporar**.
- Actuadores funcionando: **PENDIENTE de incorporar**.
- Tabla HAL: [disponible](tabla_hal.md).
- Primer commit GitHub: **PENDIENTE; no se creó automáticamente**.

El índice para evidencias públicas está en [`docs/evidencias/README.md`](evidencias/README.md). No se inventaron imágenes ni mediciones.

## Estado del sprint

| Área | Estado | Criterio |
|---|---|---|
| Firmware modular | Completado en código | Separado en `firmware/`, con entrada `main.py`. |
| Sensores | Implementado; revalidación pendiente | Drivers preservados; pruebas físicas previas no repetidas. |
| Actuadores | Implementado; revalidación pendiente | Pines y comandos preservados. |
| MQTT | Implementado; prueba de red pendiente | Contrato preservado y conversión probada con dobles. |
| GPS | Implementado; validación física bloqueada por hardware/entorno | Parser y estados probados en escritorio. |
| HAL | Completado documentalmente | Tabla y explicación disponibles. |
| Hardware/evidencias | Pendiente | Requiere montaje, fotografías y mediciones reales. |
| Documentación | Completado | README, arquitectura, Firebase y cámara. |
| GitHub | Preparado, no publicado | Falta commit autorizado y push explícitamente autorizado. |

## Riesgos conocidos

El umbral de 1.5 G es experimental, el MAX30102 no es un instrumento médico y el broker MQTT público no ofrece privacidad ni autenticación. Moto-SOS es un prototipo académico, no un sistema certificado de atención a emergencias.
