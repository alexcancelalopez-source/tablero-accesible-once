"""Detección de contenido por casilla mediante la SILUETA de la pieza.

Segunda etapa del Modulo_Reconocimiento (tarea 10.1, Requisitos 2.4, 2.7, 2.8).
Antes de clasificar el tipo de pieza (tarea 12), cada una de las 64 casillas pasa
por esta etapa de *detección de contenido* (vacía / no vacía).

Enfoque validado (ver ``docs/prototipo_vision.py`` y ``docs/diagnostico_vision.md``)
-----------------------------------------------------------------------------------
En vez de medir varianza y bordes contra un fondo estimado —que fallaba con
los resaltados y el rayado de los diagramas de imprenta—, esta etapa extrae la
**silueta** de la pieza (su forma rellena, independiente del fondo) y mide la
**fracción de ocupación** de esa silueta dentro de la casilla. La silueta se
obtiene de forma distinta según el estilo del diagrama:

- **color digital** (:func:`rasgos_digital`): las piezas tienen contorno oscuro;
  se recorta un pequeño margen interior, se detectan bordes con Canny, se dilatan
  y se rellenan los contornos suficientemente grandes. El color de la pieza
  (blanco/negro) se decide por la proporción de píxeles oscuros dentro de la
  silueta.
- **libro b/n** (:func:`rasgos_libro`): se difumina la casilla para anular el
  rayado y se compara con una casilla vacía de referencia de la MISMA paridad
  (clara/rayada); lo que difiere es la pieza. El color se decide por la
  proporción de píxeles claros dentro de la silueta erosionada.

Una casilla se considera **vacía** cuando la fracción de ocupación de su silueta
es menor que :data:`OCUPACION_MINIMA` (una casilla vacía no genera silueta
apreciable). En ese caso la clasificación es nítida: ``vacia=True``, confianza
alta (>= 0.9) y ``dudosa=False`` (Requisito 2.8, una casilla vacía nítida nunca
es dudosa). Con pieza => ``vacia=False``.

API pública conservada (para no romper el resto del sistema ni los tests):
:class:`ContenidoCasilla`, :class:`BasesTablero`, :func:`es_paridad_clara`,
:func:`estimar_color_base`, :func:`estimar_bases_tablero`, :func:`normalizar_fondo`,
:func:`clasificar_contenido`, :func:`detectar_contenido_tablero`. Se añade la
función nueva :func:`rasgos_tablero`, que expone la silueta, la fracción de
ocupación y el color por casilla para el clasificador (tarea 12).

Todos los nombres, comentarios y mensajes van en español, según las reglas del
proyecto (regla 15).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import cv2
import numpy as np

from modulos.posicion import COLUMNAS, iterar_casillas
from modulos.reconocimiento.tablero import (
    ESTILO_COLOR_DIGITAL,
    ESTILO_LIBRO_BYN,
    Casilla,
)


# ---------------------------------------------------------------------------
# Constantes de configuración de la detección de contenido
# ---------------------------------------------------------------------------

# Lado (en píxeles) al que se normaliza cada silueta. Coincide con el tamaño de
# plantilla del clasificador (tarea 12) para poder compararlas directamente.
LADO_SILUETA = 64

# Fracción de ocupación mínima de la silueta para considerar que una casilla
# tiene pieza. Por debajo, la casilla se considera vacía. Es el umbral
# ``ocupacion_min`` del prototipo validado (0.09).
OCUPACION_MINIMA = 0.09

# Área mínima de un contorno (proporción del área de la casilla) para rellenarlo
# como parte de la silueta. Descarta motas de ruido.
_AREA_MINIMA_CONTORNO = 0.04

# Umbral de saturación media (canal S de HSV) para inferir el estilo a partir de
# los recortes de las casillas cuando no se conoce de antemano (mismo criterio
# que la detección de estilo del tablero).
_UMBRAL_SATURACION_COLOR = 30.0

# --- Parámetros del estilo color digital ---
# Margen interior relativo que se recorta de cada casilla antes de buscar bordes.
_MARGEN_DIGITAL = 0.08
# Umbrales de Canny para el contorno de las piezas digitales.
_CANNY_DIGITAL = (60, 160)
# Un píxel de la silueta se considera oscuro si su gris es inferior a este valor.
_GRIS_OSCURO_DIGITAL = 70
# La pieza es blanca si la proporción de píxeles NO oscuros dentro de la silueta
# supera este valor.
_UMBRAL_BLANCO_DIGITAL = 0.62

# --- Parámetros del estilo libro b/n ---
# Margen (en píxeles) que se recorta de cada casilla antes de analizarla.
_MARGEN_LIBRO = 6
# Sigma del difuminado gaussiano que anula el rayado de las casillas oscuras.
_SIGMA_LIBRO = 3
# Diferencia mínima (0-255) entre la casilla difuminada y la referencia de su
# paridad para considerar el píxel parte de la pieza.
_UMBRAL_DIFERENCIA_LIBRO = 50
# La pieza es blanca si la proporción de píxeles claros (> este gris) dentro de
# la silueta erosionada supera :data:`_UMBRAL_BLANCO_LIBRO`.
_GRIS_CLARO_LIBRO = 170
_UMBRAL_BLANCO_LIBRO = 0.25


# ---------------------------------------------------------------------------
# Resultado de la clasificación de una casilla
# ---------------------------------------------------------------------------

@dataclass
class ContenidoCasilla:
    """Resultado de la detección de contenido de una casilla.

    - ``vacia``: ``True`` si la casilla se ha clasificado como vacía.
    - ``confianza``: valor en ``[0.0, 1.0]``. Para una casilla vacía nítida es
      alta (>= 0.9); para una no vacía refleja la ocupación de la silueta.
    - ``dudosa``: ``True`` si la casilla queda cerca del umbral de ocupación y
      conviene revisarla (Requisito 2.8). Una casilla vacía nítida nunca es
      dudosa.
    """

    vacia: bool
    confianza: float
    dudosa: bool


@dataclass
class BasesTablero:
    """Bases del tablero estimadas para adaptar la etapa al tema de la imagen.

    Conserva las intensidades medias de las casillas claras y oscuras (por
    paridad ``columna + fila``) y la textura de fondo típica de cada grupo
    (desviación de intensidad y densidad de bordes medianas). Aunque el enfoque
    de silueta ya no depende de estas bases para decidir vacía / no vacía, se
    mantiene la estructura para no romper la API pública usada por otros módulos.

    - ``base_clara`` / ``base_oscura``: intensidad media de fondo (0–255).
    - ``desviacion_clara`` / ``desviacion_oscura``: desviación de intensidad
      mediana del interior de cada grupo.
    - ``densidad_clara`` / ``densidad_oscura``: densidad de bordes mediana del
      interior de cada grupo.
    """

    base_clara: float
    base_oscura: float
    desviacion_clara: float
    desviacion_oscura: float
    densidad_clara: float
    densidad_oscura: float


# ---------------------------------------------------------------------------
# Paridad de la casilla (clara / oscura)
# ---------------------------------------------------------------------------

def es_paridad_clara(columna: str, fila: int) -> bool:
    """Indica si la casilla ``(columna, fila)`` es de las claras del tablero.

    El color de una casilla depende de la paridad de ``índice_columna + fila``:
    suma par corresponde a un grupo (aquí, las claras) e impar al otro. Lo
    importante no es el nombre absoluto sino separar de forma consistente las 64
    casillas en dos grupos por paridad.
    """
    indice_columna = COLUMNAS.index(columna)
    return (indice_columna + fila) % 2 == 0


def _paridad(columna: str, fila: int) -> int:
    """Paridad 0/1 de la casilla, como en el prototipo (``(col + fila) % 2``)."""
    return (COLUMNAS.index(columna) + fila) % 2


# ---------------------------------------------------------------------------
# Utilidades internas de imagen
# ---------------------------------------------------------------------------

def _a_gris(celda_img: np.ndarray) -> np.ndarray:
    """Devuelve la casilla en escala de grises (``float32``)."""
    if celda_img.ndim == 3 and celda_img.shape[2] == 3:
        gris = cv2.cvtColor(celda_img, cv2.COLOR_BGR2GRAY)
    else:
        gris = celda_img
    return gris.astype(np.float32)


def _a_gris_uint8(celda_img: np.ndarray) -> np.ndarray:
    """Devuelve la casilla en escala de grises (``uint8``)."""
    if celda_img.ndim == 3 and celda_img.shape[2] == 3:
        return cv2.cvtColor(celda_img, cv2.COLOR_BGR2GRAY)
    return celda_img.astype(np.uint8)


def _interior(gris: np.ndarray, margen_relativo: float = 0.12) -> np.ndarray:
    """Recorta el margen exterior de la casilla para descartar la rejilla."""
    alto, ancho = gris.shape[:2]
    margen_y = int(alto * margen_relativo)
    margen_x = int(ancho * margen_relativo)
    if alto - 2 * margen_y < 3 or ancho - 2 * margen_x < 3:
        return gris
    return gris[margen_y : alto - margen_y, margen_x : ancho - margen_x]


def _rellenar_contornos(mascara: np.ndarray, area_minima: float) -> np.ndarray:
    """Rellena los contornos externos de ``mascara`` con área suficiente.

    Devuelve una máscara binaria (0/255) con la forma rellena de la pieza. Es la
    función ``_rellenar`` del prototipo validado.
    """
    contornos, _ = cv2.findContours(
        mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    silueta = np.zeros_like(mascara)
    grandes = [c for c in contornos if cv2.contourArea(c) > area_minima * mascara.size]
    cv2.drawContours(silueta, grandes, -1, 255, -1)
    return silueta


# ---------------------------------------------------------------------------
# Inferencia del estilo a partir de las celdas
# ---------------------------------------------------------------------------

def _inferir_estilo(celdas: Dict[Tuple[str, int], Casilla]) -> str:
    """Infiere el estilo (color digital / libro b/n) a partir de las celdas.

    La función :func:`detectar_contenido_tablero` no recibe el estilo, así que se
    deduce midiendo la saturación media de todos los recortes de casilla: si hay
    color apreciable es color digital; si es esencialmente gris, libro b/n. Es el
    mismo criterio que la detección de estilo del tablero.
    """
    saturaciones = []
    for celda in celdas.values():
        img = celda.imagen
        if img is None or img.size == 0:
            continue
        if img.ndim == 3 and img.shape[2] == 3:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            saturaciones.append(float(hsv[:, :, 1].mean()))
        else:
            saturaciones.append(0.0)
    if not saturaciones:
        return ESTILO_LIBRO_BYN
    if float(np.mean(saturaciones)) > _UMBRAL_SATURACION_COLOR:
        return ESTILO_COLOR_DIGITAL
    return ESTILO_LIBRO_BYN


# ---------------------------------------------------------------------------
# Extracción de siluetas por estilo (enfoque validado)
# ---------------------------------------------------------------------------

def rasgos_digital(
    celdas: Dict[Tuple[str, int], Casilla],
) -> Dict[Tuple[str, int], Tuple[np.ndarray, float, bool]]:
    """Extrae la silueta de cada casilla en un tablero de color digital.

    Para cada casilla: recorta un margen interior, detecta bordes con Canny, los
    dilata y rellena los contornos grandes para obtener la silueta de la pieza. La
    fracción de ocupación es la media de la silueta (0–1) y el color es blanco si
    la proporción de píxeles NO oscuros dentro de la silueta supera el umbral.
    Reproduce ``rasgos_digital`` del prototipo validado.

    :returns: ``{(columna, fila): (silueta_64x64, fraccion, es_blanco)}``.
    """
    salida: Dict[Tuple[str, int], Tuple[np.ndarray, float, bool]] = {}
    for clave, celda in celdas.items():
        img = celda.imagen
        alto = img.shape[0]
        margen = int(alto * _MARGEN_DIGITAL)
        gris = _a_gris_uint8(img)[margen : alto - margen, margen : alto - margen]
        bordes = cv2.dilate(
            cv2.Canny(gris, *_CANNY_DIGITAL), np.ones((3, 3), np.uint8)
        )
        silueta = _rellenar_contornos(bordes, _AREA_MINIMA_CONTORNO)
        dentro = gris[silueta > 0]
        proporcion_blanco = (
            1 - (dentro < _GRIS_OSCURO_DIGITAL).mean() if dentro.size else 0.0
        )
        salida[clave] = (
            cv2.resize(silueta, (LADO_SILUETA, LADO_SILUETA), interpolation=cv2.INTER_AREA),
            float(silueta.mean()) / 255.0,
            bool(proporcion_blanco > _UMBRAL_BLANCO_DIGITAL),
        )
    return salida


def rasgos_libro(
    celdas: Dict[Tuple[str, int], Casilla],
) -> Dict[Tuple[str, int], Tuple[np.ndarray, float, bool]]:
    """Extrae la silueta de cada casilla en un diagrama de libro en blanco y negro.

    Difumina cada casilla (para anular el rayado) y la compara con la mediana de
    las casillas vacías de su MISMA paridad (referencia); lo que difiere es la
    pieza. Rellena los contornos grandes para la silueta. El color es blanco si la
    proporción de píxeles claros dentro de la silueta erosionada supera el umbral.
    Reproduce ``rasgos_libro`` del prototipo validado.

    :returns: ``{(columna, fila): (silueta_64x64, fraccion, es_blanco)}``.
    """
    preparado: Dict[Tuple[str, int], Tuple[np.ndarray, np.ndarray]] = {}
    for clave, celda in celdas.items():
        gris = _a_gris_uint8(celda.imagen)[_MARGEN_LIBRO:-_MARGEN_LIBRO, _MARGEN_LIBRO:-_MARGEN_LIBRO]
        difuminado = cv2.GaussianBlur(gris, (0, 0), _SIGMA_LIBRO).astype(np.float32)
        preparado[clave] = (gris, difuminado)

    # Referencia por paridad: mediana del difuminado de las casillas de esa
    # paridad (las vacías dominan y definen el fondo rayado/claro).
    referencia: Dict[int, np.ndarray] = {}
    for par in (0, 1):
        pila = [dif for clave, (_, dif) in preparado.items() if _paridad(*clave) == par]
        if pila:
            referencia[par] = np.median(np.stack(pila), axis=0)

    salida: Dict[Tuple[str, int], Tuple[np.ndarray, float, bool]] = {}
    for clave, (gris, difuminado) in preparado.items():
        ref = referencia.get(_paridad(*clave))
        if ref is None:
            ref = np.zeros_like(difuminado)
        mascara = (np.abs(difuminado - ref) > _UMBRAL_DIFERENCIA_LIBRO).astype(np.uint8) * 255
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        silueta = _rellenar_contornos(mascara, _AREA_MINIMA_CONTORNO)
        interior = gris[cv2.erode(silueta, np.ones((7, 7), np.uint8)) > 0]
        proporcion_blanco = (interior > _GRIS_CLARO_LIBRO).mean() if interior.size else 0.0
        salida[clave] = (
            cv2.resize(silueta, (LADO_SILUETA, LADO_SILUETA), interpolation=cv2.INTER_AREA),
            float(silueta.mean()) / 255.0,
            bool(proporcion_blanco > _UMBRAL_BLANCO_LIBRO),
        )
    return salida


def rasgos_tablero(
    celdas: Dict[Tuple[str, int], Casilla],
    estilo: str,
) -> Dict[Tuple[str, int], Tuple[np.ndarray, float, bool]]:
    """Extrae la silueta, la ocupación y el color de las 64 casillas por estilo.

    Es la función que usa el clasificador (tarea 12): delega en
    :func:`rasgos_digital` o :func:`rasgos_libro` según ``estilo``.

    :param celdas: diccionario ``{(columna, fila): Casilla}``.
    :param estilo: ``"color_digital"`` o ``"libro_byn"``.
    :returns: ``{(columna, fila): (silueta_64x64, fraccion, es_blanco)}``.
    """
    if estilo == ESTILO_COLOR_DIGITAL:
        return rasgos_digital(celdas)
    return rasgos_libro(celdas)


# ---------------------------------------------------------------------------
# Bases del tablero (API pública conservada)
# ---------------------------------------------------------------------------

def _densidad_bordes(celda_img: np.ndarray) -> float:
    """Proporción de píxeles de borde (Canny) en el interior de la casilla."""
    gris = _interior(_a_gris(celda_img)).astype(np.uint8)
    bordes = cv2.Canny(gris, 50, 150)
    if bordes.size == 0:
        return 0.0
    return float(np.count_nonzero(bordes)) / float(bordes.size)


def _intensidad_media(celda_img: np.ndarray) -> float:
    """Intensidad media (gris) del interior de la casilla."""
    return float(_interior(_a_gris(celda_img)).mean())


def normalizar_fondo(celda_img: np.ndarray, base_correspondiente: float) -> np.ndarray:
    """Resta el fondo base de la casilla y devuelve el residuo absoluto en gris.

    Convierte la casilla a gris y le resta la intensidad ``base_correspondiente``;
    el resultado (valor absoluto) mide cuánto se aparta cada píxel del fondo
    esperado. Se conserva para la API pública.
    """
    gris = _a_gris(celda_img)
    return np.abs(gris - float(base_correspondiente))


def estimar_color_base(
    celdas: Dict[Tuple[str, int], Casilla],
) -> Tuple[float, float]:
    """Estima la intensidad media de las casillas claras y de las oscuras.

    Separa las 64 casillas por paridad y calcula la **mediana** de la intensidad
    media del interior de cada grupo (robusta frente a casillas con pieza). Así el
    algoritmo se adapta al tema de la imagen (verde/crema digital, gris de
    imprenta, etc.). Se conserva para la API pública.

    :returns: par ``(base_clara, base_oscura)`` en la escala 0–255.
    """
    intensidades_claras = []
    intensidades_oscuras = []
    for columna, fila in iterar_casillas():
        celda = celdas.get((columna, fila))
        if celda is None:
            continue
        intensidad = _intensidad_media(celda.imagen)
        if es_paridad_clara(columna, fila):
            intensidades_claras.append(intensidad)
        else:
            intensidades_oscuras.append(intensidad)

    base_clara = float(np.median(intensidades_claras)) if intensidades_claras else 255.0
    base_oscura = float(np.median(intensidades_oscuras)) if intensidades_oscuras else 0.0
    return base_clara, base_oscura


def estimar_bases_tablero(
    celdas: Dict[Tuple[str, int], Casilla],
) -> BasesTablero:
    """Estima las bases de intensidad y la textura de fondo por paridad.

    Amplía :func:`estimar_color_base` con la mediana de la desviación de
    intensidad y de la densidad de bordes del interior de cada grupo de paridad.
    Se conserva para la API pública (otros usos y diagnóstico).

    :returns: :class:`BasesTablero` con intensidades y texturas de fondo.
    """
    base_clara, base_oscura = estimar_color_base(celdas)

    desviaciones = {True: [], False: []}
    densidades = {True: [], False: []}
    for columna, fila in iterar_casillas():
        celda = celdas.get((columna, fila))
        if celda is None:
            continue
        clara = es_paridad_clara(columna, fila)
        base = base_clara if clara else base_oscura
        residuo_interior = _interior(normalizar_fondo(celda.imagen, base))
        desviaciones[clara].append(float(residuo_interior.std()))
        densidades[clara].append(_densidad_bordes(celda.imagen))

    def _mediana(valores: list) -> float:
        return float(np.median(valores)) if valores else 0.0

    return BasesTablero(
        base_clara=base_clara,
        base_oscura=base_oscura,
        desviacion_clara=_mediana(desviaciones[True]),
        desviacion_oscura=_mediana(desviaciones[False]),
        densidad_clara=_mediana(densidades[True]),
        densidad_oscura=_mediana(densidades[False]),
    )


# ---------------------------------------------------------------------------
# Clasificación vacía / no vacía de una casilla (API pública conservada)
# ---------------------------------------------------------------------------

def _contenido_desde_fraccion(fraccion: float) -> ContenidoCasilla:
    """Construye el :class:`ContenidoCasilla` a partir de la ocupación de silueta.

    - ``fraccion < OCUPACION_MINIMA`` => casilla vacía nítida (confianza alta, no
      dudosa; una vacía nítida nunca es dudosa, Requisito 2.8).
    - ``fraccion >= OCUPACION_MINIMA`` => casilla con pieza (no vacía); la
      confianza crece con la ocupación.
    """
    if fraccion < OCUPACION_MINIMA:
        # Cuanto menor es la ocupación, más segura es la casilla vacía.
        margen = (OCUPACION_MINIMA - fraccion) / OCUPACION_MINIMA
        confianza = min(0.90 + 0.10 * margen, 1.0)
        return ContenidoCasilla(vacia=True, confianza=confianza, dudosa=False)

    # No vacía: confianza en [0.80, 1.0] según cuánto supere el umbral.
    margen = min(1.0, (fraccion - OCUPACION_MINIMA) / max(OCUPACION_MINIMA, 1e-6))
    confianza = min(0.80 + 0.20 * margen, 1.0)
    return ContenidoCasilla(vacia=False, confianza=confianza, dudosa=False)


def clasificar_contenido(
    celda_img: np.ndarray,
    base_clara: float,
    base_oscura: float,
    columna: str,
    fila: int,
    bases: "BasesTablero | None" = None,
) -> ContenidoCasilla:
    """Clasifica una casilla como vacía o no vacía a partir de su silueta.

    Extrae la silueta de la pieza dependiendo del estilo (que se infiere del
    propio recorte: color => digital; gris => libro) y decide vacía / no vacía por
    la fracción de ocupación (:data:`OCUPACION_MINIMA`). Los parámetros
    ``base_clara``, ``base_oscura`` y ``bases`` se conservan por compatibilidad de
    API, aunque el enfoque de silueta ya no depende de ellos.

    Nota: en el estilo libro, la referencia por paridad se calcula idealmente con
    las 64 casillas; usada de forma aislada sobre una sola casilla, esta función
    aproxima la referencia con la propia casilla difuminada (aún así separa bien
    vacía de pieza en la práctica). Para las 64 casillas conviene usar
    :func:`detectar_contenido_tablero`.

    :param celda_img: recorte de la casilla (BGR o gris).
    :param base_clara: intensidad de fondo de las casillas claras (compatibilidad).
    :param base_oscura: intensidad de fondo de las casillas oscuras (compatibilidad).
    :param columna: letra de columna ``a``–``h``.
    :param fila: número de fila ``1``–``8``.
    :param bases: bases del tablero (compatibilidad); no se usa en este enfoque.
    :returns: :class:`ContenidoCasilla` con ``vacia``, ``confianza`` y ``dudosa``.
    """
    # Casilla individual: se envuelve en un diccionario de una entrada y se usa la
    # extracción de silueta del estilo inferido del propio recorte.
    celda = Casilla(columna=columna, fila=fila, imagen=celda_img, limites=(0, 0, 0, 0))
    celdas = {(columna, fila): celda}
    estilo = _inferir_estilo(celdas)
    rasgos = rasgos_tablero(celdas, estilo)
    _silueta, fraccion, _blanco = rasgos[(columna, fila)]
    return _contenido_desde_fraccion(fraccion)


def detectar_contenido_tablero(
    celdas: Dict[Tuple[str, int], Casilla],
) -> Dict[Tuple[str, int], ContenidoCasilla]:
    """Aplica la detección de contenido a las 64 casillas del tablero.

    Infiere el estilo a partir de las celdas, extrae la silueta y la fracción de
    ocupación de cada casilla (:func:`rasgos_tablero`) y decide vacía / no vacía
    con la fracción (:data:`OCUPACION_MINIMA`). En el estilo libro, la referencia
    por paridad se calcula con todas las casillas, que es como el enfoque validado
    logra su mejor precisión.

    :param celdas: diccionario ``{(columna, fila): Casilla}`` (salida de
        :func:`dividir_en_64`).
    :returns: diccionario ``{(columna, fila): ContenidoCasilla}``.
    """
    estilo = _inferir_estilo(celdas)
    rasgos = rasgos_tablero(celdas, estilo)

    resultado: Dict[Tuple[str, int], ContenidoCasilla] = {}
    for columna, fila in iterar_casillas():
        if (columna, fila) not in rasgos:
            continue
        _silueta, fraccion, _blanco = rasgos[(columna, fila)]
        resultado[(columna, fila)] = _contenido_desde_fraccion(fraccion)
    return resultado
