# Moto-SOS — Casco de Rescate Inmediato

Prototipo académico de casco inteligente que identifica impactos potenciales, activa alertas locales, permite cancelar falsas alarmas y comunica telemetría, ubicación y evidencia visual a un servidor. El servidor integra MQTT, Firebase Realtime Database, una cámara IP de celular, Telegram, YOLOv8 y EasyOCR.

> Moto-SOS no es un dispositivo médico ni un sistema certificado de detección o atención de emergencias. Toda alerta, ubicación y lectura debe verificarse por una persona.

## Problema y objetivo

En un accidente de motocicleta puede existir demora para informar la situación y la ubicación. El objetivo general es desarrollar un casco que detecte eventos compatibles con un impacto, dé cinco segundos para cancelar una falsa alarma y, si se confirma, envíe información disponible sin inventar coordenadas ni atribuir participación a objetos detectados por IA.

## Equipo

- Fernández Guerrero Cristóbal — matrícula: **PENDIENTE**.
- García Silva Emmanuel Alejandro — matrícula: **PENDIENTE**.
- Martínez Coronado Alan Mauricio — matrícula: **PENDIENTE**.

Tecnológico Nacional de México — Instituto Tecnológico de León

Materia: Sistemas Programables

Semestre: agosto–diciembre de 2026

Número de equipo: **PENDIENTE**

## Arquitectura

```text
Sensores/GPS -> ESP32 -> MQTT -> mqtt_bridge -> Firebase Realtime Database
                    ^       |                         |
                    |       +-> emergency_notifier -> Telegram
                    |                   ^              + cámara IP / YOLO / OCR
                    +-- firebase_commands <------------+
```

El detalle de capas, estados GPS y contrato MQTT se encuentra en [docs/arquitectura.md](docs/arquitectura.md).

## Hardware

| Componente | Interfaz principal | Uso |
|---|---|---|
| ESP32 | MicroPython | Coordinación del casco |
| MPU6050 | I2C GPIO21/22 | Aceleración e impacto |
| MAX30102 | I2C GPIO21/22 | BPM experimental |
| DHT11 | GPIO15 | Temperatura |
| GPS NEO-6M | UART2 TX27/RX26, 9600 baudios | Ubicación y diagnóstico |
| Buzzer | GPIO18 | Alerta sonora |
| Ventilador | GPIO19 | Control térmico |
| Motor vibrador | GPIO13 | Alerta háptica |
| Botón | GPIO4, activo en bajo | Cancelación física |
| Teléfono celular | HTTP por Wi-Fi | Cámara IP del servidor |

La referencia completa está en [docs/tabla_hal.md](docs/tabla_hal.md). El montaje y las etapas de potencia deben validarse antes de energizar cargas.

## Tecnologías

- ESP32, MicroPython, I2C, UART/NMEA y Wi-Fi.
- MQTT mediante HiveMQ en la configuración de demostración.
- Python 3, Paho MQTT y Firebase Admin SDK.
- Firebase Realtime Database; Cloud Storage opcional.
- OpenCV, Ultralytics YOLOv8, EasyOCR, NumPy y PyTorch.
- Telegram Bot API y cámara IP de celular.

## Estructura

```text
MotoSOS_Bridge/
├── firmware/
│   ├── hal/                  # Explicación de la HAL
│   ├── cam/                  # Cámara IP del celular
│   ├── main.py               # Entrada del ESP32
│   ├── app.py                # Coordinación
│   ├── config.py             # Pines, tiempos y tópicos
│   ├── config_local.example.py
│   ├── sensores.py
│   ├── gps_motosos.py
│   ├── actuadores.py
│   ├── emergencias.py
│   ├── comunicaciones.py
│   ├── telemetria.py
│   └── diagnostico_gps.py
├── servidor/
│   ├── ia/vision_ia.py
│   ├── configuracion.py
│   ├── mqtt_bridge.py
│   ├── firebase_commands.py
│   ├── emergency_notifier.py
│   ├── mqtt_listener.py
│   └── requirements.txt
├── firebase/
│   ├── reglas.json
│   └── esquema.md
├── hardware/README.md
├── docs/
│   ├── tabla_hal.md
│   ├── sprint_1.md
│   ├── arquitectura.md
│   └── evidencias/README.md
├── tests/
├── secrets/                 # Privado, ignorado por Git
├── evidencias/              # Privado, ignorado por Git
├── .env.example
├── .gitignore
└── README.md
```

## Instalación del servidor

Desde PowerShell y la raíz del repositorio:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r servidor\requirements.txt
Copy-Item .env.example .env
```

Las versiones en `requirements.txt` corresponden al entorno local inspeccionado con Python 3.14.7. Las bibliotecas de IA ocupan varios cientos de MB. El archivo `yolov8n.pt` debe estar en la raíz o la ruta debe indicarse mediante `YOLO_MODEL_PATH`. La regla `*.pt` evita agregar modelos nuevos, pero el `yolov8n.pt` actual ya está versionado y seguirá así hasta que el equipo decida retirarlo del índice con un commit específico.

## Configuración

### Firebase Realtime Database

1. Colocar la cuenta de servicio en `secrets/serviceAccountKey.json`; nunca versionarla.
2. Configurar `FIREBASE_DATABASE_URL` en `.env`.
3. Configurar `FIREBASE_STORAGE_BUCKET` sólo si el proyecto permite Cloud Storage.
4. Revisar [firebase/esquema.md](firebase/esquema.md) y probar [firebase/reglas.json](firebase/reglas.json) en Emulator Suite antes de desplegarlas. Este repositorio no modifica reglas reales automáticamente.

La prueba manual de escritura requiere una autorización explícita en el comando:

```powershell
python -m servidor.test_firebase --confirmar-escritura
```

### MQTT

El firmware conserva `broker.hivemq.com:1883` y el servidor permite sobrescribirlo con `MQTT_BROKER`, `MQTT_PORT` y `MQTT_KEEPALIVE`. El broker público, QoS 0 y la conexión sin TLS son únicamente para demostraciones controladas: los tópicos son globales y no autentican dispositivos.

### Telegram

Crear localmente `.env` a partir del ejemplo y completar `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`. No registrar esos valores en documentación, capturas o commits. El simulacro **sí puede enviar mensajes y escribir Firebase**:

```powershell
python -m servidor.emergency_notifier --simulacro
```

Debe ejecutarse sólo con autorización y destinatarios avisados.

### Cámara IP

Configurar el teléfono y completar `CAMERA_SNAPSHOT_URL` y/o `CAMERA_STREAM_URL`. Una comprobación local de cámara no envía Telegram ni escribe Firebase:

```powershell
python -m servidor.emergency_notifier --probar-camara
```

La guía y limitaciones están en [firmware/cam/README.md](firmware/cam/README.md).

## Firmware ESP32

1. Instalar MicroPython compatible en el ESP32.
2. Copiar todos los archivos `.py` de `firmware/` —no la carpeta contenedora— a la raíz del sistema de archivos del ESP32.
3. Copiar `firmware/config_local.example.py` como `config_local.py` en el ESP32 y completar SSID/contraseña de una red de 2.4 GHz.
4. Mantener `main.py` en la raíz para el arranque automático.
5. Reiniciar y observar la consola serie.

`config_local.py` está ignorado por Git. No cambiar pines o tópicos sin actualizar firmware, servidor, HAL y pruebas.

Para aislar el GPS del resto del sistema puede ejecutarse `diagnostico_gps.py` en el ESP32. La antena necesita cielo abierto; alimentación, antena y entorno no pueden corregirse exclusivamente por software.

## Ejecución

Abrir terminales independientes desde la raíz:

```powershell
python -m servidor.mqtt_bridge
python -m servidor.firebase_commands
python -m servidor.emergency_notifier
```

Receptor MQTT de diagnóstico:

```powershell
python -m servidor.mqtt_listener
```

Prueba IA local sin Firebase ni Telegram:

```powershell
python -m servidor.emergency_notifier --probar-ia --imagen RUTA_A_IMAGEN.jpg
```

Las fotografías generadas van a `evidencias/`, excluida de Git.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q firmware servidor tests
.\.venv\Scripts\python.exe -m servidor.emergency_notifier --help
```

Las pruebas automatizadas usan mocks y no contactan Telegram, Firebase, MQTT ni la cámara. Un mock exitoso no demuestra funcionamiento físico. Consulte [docs/sprint_1.md](docs/sprint_1.md) para separar validaciones anteriores, comprobaciones actuales y pendientes de hardware.

## Sprint 1 y evidencias

El firmware modular, el contrato MQTT, la HAL y la documentación están preparados. Sensores, actuadores, GPS y flujo completo requieren revalidación física después de la reorganización. No se agregaron fotografías ficticias; [docs/evidencias/README.md](docs/evidencias/README.md) enumera las evidencias aún necesarias.

## Limitaciones

- Umbral de impacto de 1.5 G experimental: puede producir falsos positivos o negativos.
- MAX30102 y DHT11 no proporcionan diagnóstico médico.
- GPS puede tardar en obtener fix o fallar bajo techo; una posición anterior se marca como `CADUCADO`.
- MQTT público sin TLS no brinda confidencialidad, autenticidad ni disponibilidad garantizada.
- Cámara, OCR y detección dependen de red, luz, encuadre y modelo. Las placas son candidatas no verificadas.
- Telegram, Firebase, Internet y energía son dependencias externas.

## Seguridad

- No subir `.env`, `secrets/`, `config_local.py`, evidencias privadas, claves ni modelos pesados adicionales.
- Usar un broker privado con TLS, credenciales y tópicos no predecibles antes de salir del laboratorio.
- Aplicar mínimo privilegio a Firebase y rotar la cuenta de servicio si se expone.
- Debido al antecedente de exposición durante el desarrollo, rotar la contraseña Wi-Fi y el token de Telegram si todavía no existe confirmación documental de su rotación. Ocultarlos hoy no invalida copias previas.
- `.gitignore` no elimina secretos ni archivos grandes ya presentes en el historial. Cualquier limpieza de historial compartido requiere coordinación y no debe hacerse con `push --force` improvisado.

## Licencia

No se proporcionó una licencia. El uso, distribución y publicación quedan **PENDIENTES** de decisión del equipo y la institución.
