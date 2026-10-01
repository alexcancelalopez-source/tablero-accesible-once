"""Modulo_Reconocimiento: de imagen a posición reconocida.

Localiza el tablero, lo divide en 64 casillas, clasifica cada casilla
(vacía o pieza con tipo y color), detecta casillas resaltadas y flechas,
y asigna un nivel de confianza a cada clasificación.

Este paquete se irá completando en tareas posteriores del plan. Por ahora
expone la localización del tablero, la división en 64 casillas y la detección
de estilo (tarea 9.1).
"""

from modulos.reconocimiento.tablero import (
    ESTILO_COLOR_DIGITAL,
    ESTILO_LIBRO_BYN,
    LADO_TABLERO_NORMALIZADO,
    Casilla,
    TableroNoDetectadoError,
    detectar_estilo,
    dividir_en_64,
    localizar_tablero,
)
from modulos.reconocimiento.contenido import (
    LADO_SILUETA,
    OCUPACION_MINIMA,
    BasesTablero,
    ContenidoCasilla,
    clasificar_contenido,
    detectar_contenido_tablero,
    es_paridad_clara,
    estimar_bases_tablero,
    estimar_color_base,
    normalizar_fondo,
    rasgos_digital,
    rasgos_libro,
    rasgos_tablero,
)
from modulos.reconocimiento.plantillas import (
    GRUPO_EVALUACION,
    GRUPO_PLANTILLAS,
    BancosSiluetas,
    ResumenPlantillas,
    UsoIndebidoDeDatosError,
    cargar_plantillas,
    construir_bancos_siluetas,
    generar_plantillas,
    normalizar_recorte,
    posiciones_conocidas,
)
from modulos.reconocimiento.resaltadas import (
    clasificar_color_hsv,
    detectar_resaltadas,
    detectar_resaltadas_desde_celdas,
    estimar_colores_base_bgr,
)
from modulos.reconocimiento.clasificador import (
    PlantillasEstilo,
    clasificar_pieza,
    reconocer_piezas,
)
from modulos.reconocimiento.flechas import (
    combinar_flechas,
    detectar_flechas_auto,
    obtener_flechas,
    parsear_flecha_manual,
    parsear_flechas_manuales,
)

__all__ = [
    "ESTILO_COLOR_DIGITAL",
    "ESTILO_LIBRO_BYN",
    "LADO_TABLERO_NORMALIZADO",
    "Casilla",
    "TableroNoDetectadoError",
    "detectar_estilo",
    "dividir_en_64",
    "localizar_tablero",
    "BasesTablero",
    "ContenidoCasilla",
    "clasificar_contenido",
    "detectar_contenido_tablero",
    "es_paridad_clara",
    "estimar_bases_tablero",
    "estimar_color_base",
    "normalizar_fondo",
    "GRUPO_EVALUACION",
    "GRUPO_PLANTILLAS",
    "ResumenPlantillas",
    "UsoIndebidoDeDatosError",
    "cargar_plantillas",
    "generar_plantillas",
    "normalizar_recorte",
    "posiciones_conocidas",
    "clasificar_color_hsv",
    "detectar_resaltadas",
    "detectar_resaltadas_desde_celdas",
    "estimar_colores_base_bgr",
    "PlantillasEstilo",
    "clasificar_pieza",
    "reconocer_piezas",
    "combinar_flechas",
    "detectar_flechas_auto",
    "obtener_flechas",
    "parsear_flecha_manual",
    "parsear_flechas_manuales",
]
