# Cámara del prototipo

La ESP32-CAM propuesta inicialmente fue sustituida, con autorización académica, por la cámara IP de un teléfono celular. No hay una ESP32-CAM instalada ni código ficticio para ella.

El teléfono y el servidor deben estar en una red que permita acceso a los endpoints configurados en `.env`:

- `CAMERA_SNAPSHOT_URL`: fotografía JPEG, preferentemente `/shot.jpg`.
- `CAMERA_STREAM_URL`: flujo MJPEG `/video`, usado como respaldo.

`servidor.emergency_notifier` descarga o captura la fotografía con `requests` y OpenCV. Después, `servidor.ia.vision_ia` ejecuta YOLOv8 para describir objetos visibles y EasyOCR para proponer posibles matrículas. Las matrículas se guardan como **candidatas no verificadas** y ninguna detección implica que el objeto participó en el accidente.

Las imágenes se conservan en `evidencias/`, carpeta privada excluida de Git. Cloud Storage es opcional. El aviso de texto por Telegram se intenta antes de capturar o analizar la fotografía, por lo que YOLO y EasyOCR no retrasan ese primer aviso.

## Limitaciones

- El teléfono debe permanecer encendido, con la aplicación de cámara IP activa y una dirección alcanzable.
- Cambios de IP, aislamiento entre clientes Wi-Fi, pérdida de señal o permisos del sistema pueden impedir la captura.
- La calidad, orientación, movimiento y luz afectan YOLO y OCR.
- Las URL sin HTTPS exponen la imagen dentro de la red; deben usarse sólo en una red de laboratorio controlada.
