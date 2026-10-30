# Tabla HAL — Moto-SOS

La tabla refleja `firmware/config.py` y los controladores actuales. “PENDIENTE” significa que no existe evidencia de una medición física reproducible en el repositorio; no equivale a cero ni a una prueba fallida.

| Núm. | Componente | Tipo | Pines | Protocolo | Función | Publicación MQTT | Suscripción MQTT | Unidad | Rango teórico documentado/configurado | Rango medido | Observaciones técnicas |
|---:|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MPU6050 | Sensor inercial | SDA 21, SCL 22 | I2C, `0x68`, 50 kHz | Magnitud de aceleración e impacto | `motosos/aceleracion` | — | G | ±2 G por configuración actual; magnitud resultante no firmada | PENDIENTE | Valida `WHO_AM_I`; umbral experimental de impacto: 1.5 G; reintento I2C cada 5 s. |
| 2 | MAX30102 | Sensor óptico | SDA 21, SCL 22 | I2C, `0x57`, 50 kHz | Pulso experimental | `motosos/pulso` | — | BPM | Algoritmo acepta intervalos de 375 a 1500 ms (aprox. 40–160 BPM) | PENDIENTE | Mediana de hasta 5 lecturas; `0` significa sin lectura válida, no ausencia de pulso. No es dispositivo médico. |
| 3 | DHT11 | Sensor ambiental | GPIO15 | Digital propietario | Temperatura del casco | `motosos/temperatura` | — | °C | 0–50 °C según rango nominal habitual del DHT11 | PENDIENTE | Si falla, no publica temperatura en ese ciclo. |
| 4 | GPS NEO-6M | Receptor GNSS | UART2: TX ESP32 27, RX ESP32 26 | NMEA 9600 baudios | Posición y diagnóstico | `motosos/ubicacion`, `motosos/gps/estado` | — | grados, satélites, HDOP, s | Latitud −90 a 90; longitud −180 a 180 | PENDIENTE | Acepta GGA/RMC de talkers GP/GN con checksum; no inventa coordenadas; conserva última posición y marca `CADUCADO`. |
| 5 | Buzzer | Actuador sonoro | GPIO18 | Digital | Alerta local | `motosos/alerta` describe el estado | `motosos/buzzer/cmd` | ON/OFF | 0/1 lógico | Respuesta verificada previamente; no revalidada tras reorganización | Se activa con la alerta y admite control remoto fuera de una alerta activa. |
| 6 | Ventilador | Actuador térmico | GPIO19 | Digital | Ventilación automática/remota | Temperatura en `motosos/temperatura` | `motosos/ventilador/cmd` | ON/OFF | 0/1 lógico; automático sobre 22 °C | Respuesta verificada previamente; no revalidada tras reorganización | `OFF` remoto devuelve el control al modo automático. Requiere etapa de potencia apropiada. |
| 7 | Motor vibrador | Actuador háptico | GPIO13 | Digital | Alerta local | `motosos/alerta` describe el estado | `motosos/vibrador/cmd` | ON/OFF | 0/1 lógico | Respuesta verificada previamente; no revalidada tras reorganización | Se activa junto con el buzzer. Requiere etapa de potencia apropiada. |
| 8 | Botón cancelar | Entrada humana | GPIO4 | Digital `PULL_UP` | Cancelar durante 5 s | `motosos/alerta` publica falsa alarma | — | presionado/libre | 0/1 lógico, activo en bajo | PENDIENTE | Sólo cancela mientras la emergencia está pendiente. |
| 9 | Cámara IP de celular | Sensor visual externo | Red Wi-Fi | HTTP JPEG/MJPEG | Evidencia fotográfica para servidor | No publica desde ESP32 | URL en `.env` del servidor | imagen | Depende de resolución configurada en la app | Captura verificada previamente; no revalidada tras reorganización | Sustituye a ESP32-CAM; YOLO/OCR se ejecutan en el servidor. |

## Notas de conexión

Los rótulos TX/RX de la tabla son los pines del ESP32. La conexión física UART debe cruzarse: TX del GPS hacia RX GPIO26 del ESP32; RX del GPS hacia TX GPIO27 si se utiliza comunicación bidireccional. El firmware sólo procesa NMEA y no envía comandos UBX no verificados.
