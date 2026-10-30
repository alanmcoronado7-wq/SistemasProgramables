# Abstracción de hardware del firmware

Moto-SOS mantiene una HAL ligera, adecuada para MicroPython, sin duplicar los controladores en esta carpeta. La abstracción se reparte entre módulos con responsabilidades claras:

- `sensores.py`: acceso I2C al MPU6050 y MAX30102, acceso digital al DHT11, conversión de aceleración a fuerza G, cálculo existente de BPM y reintentos ante fallos.
- `actuadores.py`: salidas digitales para buzzer, motor vibrador y ventilador; entrada con `PULL_UP` para el botón de cancelación.
- `gps_motosos.py`: analizador NMEA independiente de UART, con checksum, validación de coordenadas y estados `SIN_NMEA`, `SIN_FIX`, `VALIDO` y `CADUCADO`.
- `app.py`: crea `SoftI2C`, `UART2` y los pines; coordina los objetos anteriores sin contener sus algoritmos.
- `config.py`: única referencia de pines, direcciones I2C, tiempos y tópicos.

Esta organización permite probar en CPython el parser NMEA y la máquina de estados. Los módulos que importan `machine`, `network`, `dht` o `umqtt` requieren MicroPython y hardware real.

La tabla completa de interfaces está en [`docs/tabla_hal.md`](../../docs/tabla_hal.md).
