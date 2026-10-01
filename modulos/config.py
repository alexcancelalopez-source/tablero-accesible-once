"""Configuración compartida de la herramienta "Tablero Accesible ONCE".

Este módulo reúne las constantes que utilizan varios módulos del pipeline
(reconocimiento, orientación, validación y salidas) para evitar valores
mágicos repartidos por el código. Todos los comentarios y mensajes van en
español, según las reglas del proyecto.
"""

# Umbral de confianza para la clasificación de casillas. Por debajo de este
# valor una casilla se marca como dudosa y no se le asigna ninguna pieza
# (Requisito 2.8).
UMBRAL_CONFIANZA = 0.80

# Tamaño fijo (ancho, alto) en píxeles al que se normaliza cada recorte de
# casilla antes de compararlo con las plantillas de piezas.
TAMANO_PLANTILLA = (64, 64)

# Extensiones de archivo de imagen admitidas por la herramienta
# (Requisito 1.2). Se comparan siempre en minúsculas.
EXTENSIONES_ADMITIDAS = (".png", ".jpg", ".jpeg")

# Tamaño mínimo y máximo admitido del archivo de imagen, en bytes
# (Requisito 1.2): entre 1 byte y 20 megabytes.
TAMANO_MINIMO_BYTES = 1
LIMITE_TAMANO_BYTES = 20 * 1024 * 1024
