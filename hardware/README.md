# Hardware Moto-SOS

## Componentes registrados en el firmware

- ESP32 con MicroPython.
- MPU6050 para aceleración e impacto.
- MAX30102 para pulso experimental.
- DHT11 para temperatura.
- GPS NEO-6M a 9600 baudios.
- Buzzer, motor vibrador y ventilador mediante salidas digitales.
- Botón físico de cancelación con resistencia `PULL_UP` interna.
- Teléfono celular como cámara IP del servidor.

Las conexiones vigentes están documentadas en [`docs/tabla_hal.md`](../docs/tabla_hal.md). El código indica bus I2C compartido en GPIO21/GPIO22, DHT11 en GPIO15, GPS UART2 TX27/RX26, buzzer GPIO18, ventilador GPIO19, vibrador GPIO13 y botón GPIO4.

## Artefactos pendientes

No se encontraron en el repositorio un esquemático, archivos STL ni fotografías públicas del montaje. Deben incorporarse únicamente cuando existan y después de revisar que no expongan datos personales. Las fotografías privadas de pruebas permanecen en `evidencias/`, excluida de Git.

Antes de energizar el prototipo se deben comprobar alimentación común, niveles de tensión, orientación del GPS y la etapa de potencia necesaria para cargas como ventilador o vibrador. Una salida GPIO no debe alimentar directamente una carga que exceda la corriente permitida por el ESP32.
