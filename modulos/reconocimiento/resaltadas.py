"""Detección y clasificación de casillas resaltadas (Modulo_Reconocimiento).

Tercera etapa del Modulo_Reconocimiento dedicada a los resaltados de color
(tarea 13.1, Requisitos 6.1, 6.5, 6.6). Sobre un tablero ya localizado y
dividido en 64 casillas, esta etapa identifica qué casillas están marcadas con
un color especial (amarillo, rojo, verde o azul) y las clasifica, sin inventar
resaltados donde no los hay.

Idea general
------------
1. Se establecen los dos **colores base** del tablero muestreando las casillas
   por paridad (``columna + fila``): el color medio (robusto, por mediana de
   canal) de las casillas claras (``base_clara_bgr``) y el de las oscuras
   (``base_oscura_bgr``). Así el algoritmo se adapta al tema concreto del
   diagrama (verde/crema digital, gris de imprenta, etc.).
2. Para cada casilla se mide su **color vivo dominante**: la mediana del color
   de los píxeles vivos del interior (saturación y brillo apreciables). Se
   calcula la fracción de píxeles vivos y la diferencia de ese color vivo
   respecto a la base MÁS CERCANA de las dos.
3. Una casilla es candidata a resaltada solo si tiene una fracción de píxeles
   vivos suficiente Y su color vivo se aparta claramente de AMBAS bases (una
   casilla normal, con o sin pieza en gris, tiene su color vivo igual a la base
   de su paridad, es decir diferencia ≈ 0).
4. El color vivo se clasifica en **HSV** por rangos de tono con saturación
   mínima: amarillo, rojo, verde o azul.
5. Si el color encaja en uno de los cuatro, se añade una :class:`Resaltada`. Si
   la casilla difiere de sus bases pero el color NO encaja en ninguno, se añade
   a ``dudosas`` con motivo ``color_resaltado_desconocido`` y se avisa en
   español; nunca se inventa el color (Requisito 6.6).
6. Si no hay ninguna casilla resaltada ni dudosa, se devuelven listas vacías y
   ningún aviso: la sección de resaltadas se omite por completo (Requisito 6.5).

Por qué este criterio es robusto y conservador
-----------------------------------------------
Los resaltados de color son propios del estilo *color digital*
(``ejemplos/braille/``). En los diagramas de libro en blanco y negro
(``ejemplos/audio/``) las casillas y las piezas son grises (saturación ≈ 0), de
modo que NO tienen píxeles vivos y quedan descartadas de forma natural (fracción
de vivos nula). En los tableros digitales, una casilla normal —aunque tenga una
pieza encima— conserva como color vivo dominante el de su base (por ejemplo, el
verde del tablero), por lo que su diferencia con la base más cercana es casi
nula; solo un resaltado real (un color distinto que cubre la casilla) se aparta
de ambas bases. Exigir a la vez fracción de vivos, diferencia con ambas bases y
un tono/saturación clasificable evita inventar resaltados donde no los hay
(regla 12, Requisito 6.6).

Todos los nombres, comentarios y mensajes van en español, según las reglas del
proyecto (regla 15).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from modulos.posicion import (
    COLORES_RESALTADO,
    Dudosa,
    Resaltada,
    iterar_casillas,
    unir_casilla,
)
from modulos.reconocimiento.contenido import es_paridad_clara
from modulos.reconocimiento.tablero import (
    Casilla,
    dividir_en_64,
    localizar_tablero,
)


# ---------------------------------------------------------------------------
# Constantes de configuración de la detección de resaltados
#
# Los umbrales se ajustaron empíricamente sobre ``ejemplos/`` (tableros con
# resaltados conocidos y diagramas de libro b/n sin ellos, ver la verificación
# de la tarea 13.1). El criterio general es ser CONSERVADOR: solo marcar
# resaltada una casilla cuyo color vivo dominante se aparta claramente de ambas
# bases del tablero Y presenta un tono clasificable. Así no se inventan
# resaltados en los diagramas de imprenta en blanco y negro (regla 12).
# ---------------------------------------------------------------------------

# Margen relativo (proporción del lado) que se recorta del borde de cada casilla
# antes de medir su color, para descartar las líneas de la rejilla y las
# etiquetas de coordenadas y quedarnos con el interior de la casilla.
_MARGEN_INTERIOR = 0.15

# Saturación mínima (canal S de HSV, 0–255) para considerar "vivo" un píxel.
# Los píxeles grises (piezas y casillas de los diagramas de imprenta) quedan por
# debajo y no cuentan como color; los colores del tablero digital y los
# resaltados sí superan este valor.
_SATURACION_PIXEL_VIVO = 90.0

# Valor/brillo mínimo (canal V de HSV, 0–255) para considerar "vivo" un píxel.
# Descarta píxeles casi negros (contornos de piezas, sombras), cuyo tono no es
# fiable.
_VALOR_PIXEL_VIVO = 90.0

# Fracción mínima de píxeles vivos en el interior de la casilla para que su color
# vivo dominante sea representativo. Por debajo (p. ej. casi todo gris, típico de
# los diagramas b/n) la casilla no puede ser un resaltado de color.
_FRACCION_VIVOS_MINIMA = 0.15

# Diferencia de color (distancia euclídea en BGR, 0–255) entre el color vivo
# dominante de una casilla y la base MÁS CERCANA de las dos por encima de la cual
# la casilla se considera candidata a resaltada. Una casilla normal tiene su
# color vivo prácticamente igual a la base de su paridad (diferencia ≈ 0); un
# resaltado real se aparta de ambas bases muy por encima de este umbral.
_UMBRAL_DIFERENCIA_BASE = 45.0

# Saturación mínima (canal S de HSV, 0–255) que debe tener el color vivo para
# clasificar su tono como resaltado. Filtra colores apagados/grisáceos.
_SATURACION_MINIMA_RESALTADO = 80.0

# Valor/brillo mínimo (canal V de HSV, 0–255) para clasificar el color vivo.
_VALOR_MINIMO_RESALTADO = 60.0

# Rangos de tono (canal H de HSV en OpenCV, escala 0–179) de cada color de
# resaltado admitido. El rojo envuelve el origen del círculo de tono, por lo que
# se describe con dos tramos. Los rangos son holgados para tolerar variaciones de
# matiz, pero disjuntos entre sí para no confundir colores.
_RANGOS_TONO: Dict[str, Tuple[Tuple[int, int], ...]] = {
    # Amarillo: tonos amarillo-ámbar (aprox. 22°–44° reales de HSV OpenCV).
    "amarillo": ((22, 44),),
    # Verde: del amarillo-verdoso al cian (aprox. 90°–170° reales).
    "verde": ((45, 85),),
    # Azul: del cian al añil (aprox. 180°–270° reales).
    "azul": ((90, 135),),
    # Rojo: envuelve el origen del círculo de tono (rojos y magentas).
    "rojo": ((0, 12), (160, 179)),
}


# ---------------------------------------------------------------------------
# Utilidades internas de imagen
# ---------------------------------------------------------------------------

def _asegurar_bgr(celda_img: np.ndarray) -> np.ndarray:
    """Devuelve la casilla en BGR de 3 canales.

    Si el recorte llega en un solo canal (gris), se replica a 3 canales para
    poder trabajar en color de forma uniforme.
    """
    if celda_img.ndim == 2:
        return cv2.cvtColor(celda_img.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    if celda_img.ndim == 3 and celda_img.shape[2] == 3:
        return celda_img
    canal = celda_img[..., 0] if celda_img.ndim == 3 else celda_img
    return cv2.cvtColor(canal.astype(np.uint8), cv2.COLOR_GRAY2BGR)


def _interior(imagen: np.ndarray) -> np.ndarray:
    """Recorta el margen exterior de la casilla para descartar la rejilla.

    Elimina una franja de :data:`_MARGEN_INTERIOR` del lado en cada borde. Si la
    casilla es muy pequeña, se devuelve tal cual para no quedarse sin píxeles.
    """
    alto, ancho = imagen.shape[:2]
    margen_y = int(alto * _MARGEN_INTERIOR)
    margen_x = int(ancho * _MARGEN_INTERIOR)
    if alto - 2 * margen_y < 3 or ancho - 2 * margen_x < 3:
        return imagen
    return imagen[margen_y : alto - margen_y, margen_x : ancho - margen_x]


def _color_medio_bgr(celda_img: np.ndarray) -> np.ndarray:
    """Color medio (mediana por canal) del interior de la casilla, en BGR.

    Se usa la mediana por canal en lugar de la media para que una pieza colocada
    sobre una casilla (u otras variaciones locales) no distorsione el color de
    fondo predominante que interesa medir.

    :returns: array ``float32`` de forma ``(3,)`` con el color ``(B, G, R)``.
    """
    interior = _interior(_asegurar_bgr(celda_img)).astype(np.uint8)
    pixeles = interior.reshape(-1, 3).astype(np.float32)
    return np.median(pixeles, axis=0).astype(np.float32)


def _color_vivo_dominante(celda_img: np.ndarray) -> Tuple[Optional[np.ndarray], float]:
    """Color vivo dominante del interior de la casilla y fracción de vivos.

    Considera "vivos" los píxeles con saturación y brillo por encima de
    :data:`_SATURACION_PIXEL_VIVO` y :data:`_VALOR_PIXEL_VIVO`. El color vivo
    dominante es la mediana por canal (en BGR) de esos píxeles; representa el
    color intenso predominante de la casilla, ignorando zonas grises (piezas,
    sombras).

    :returns: par ``(color_vivo_bgr, fraccion_vivos)``. Si no hay píxeles vivos,
        el color es ``None`` y la fracción ``0.0``.
    """
    interior = _interior(_asegurar_bgr(celda_img)).astype(np.uint8)
    bgr = interior.reshape(-1, 3)
    hsv = cv2.cvtColor(interior, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    vivos = (hsv[:, 1] >= _SATURACION_PIXEL_VIVO) & (hsv[:, 2] >= _VALOR_PIXEL_VIVO)
    total = bgr.shape[0]
    fraccion = float(vivos.sum()) / float(total) if total else 0.0
    if not vivos.any():
        return None, fraccion
    color_vivo = np.median(bgr[vivos].astype(np.float32), axis=0).astype(np.float32)
    return color_vivo, fraccion


def _diferencia_color(color_a: np.ndarray, color_b: np.ndarray) -> float:
    """Distancia euclídea entre dos colores BGR (escala 0–255)."""
    return float(np.linalg.norm(color_a.astype(np.float32) - color_b.astype(np.float32)))


# ---------------------------------------------------------------------------
# Estimación de los colores base del tablero por paridad
# ---------------------------------------------------------------------------

def estimar_colores_base_bgr(
    celdas: Dict[Tuple[str, int], Casilla],
) -> Tuple[np.ndarray, np.ndarray]:
    """Estima el color base (BGR) de las casillas claras y de las oscuras.

    Recorre las 64 casillas, las separa por paridad (:func:`es_paridad_clara`) y
    calcula, para cada grupo, la **mediana por canal** del color medio del
    interior de sus casillas. La doble mediana (por casilla y por grupo) hace la
    estimación robusta frente a las casillas con pieza o resaltadas, que no
    representan el color de fondo del tablero.

    :param celdas: diccionario ``{(columna, fila): Casilla}`` (salida de
        :func:`~modulos.reconocimiento.tablero.dividir_en_64`).
    :returns: par ``(base_clara_bgr, base_oscura_bgr)``, cada uno un array
        ``float32`` de forma ``(3,)`` con el color ``(B, G, R)`` del grupo.
    """
    colores_claras: List[np.ndarray] = []
    colores_oscuras: List[np.ndarray] = []
    for columna, fila in iterar_casillas():
        celda = celdas.get((columna, fila))
        if celda is None:
            continue
        color = _color_medio_bgr(celda.imagen)
        if es_paridad_clara(columna, fila):
            colores_claras.append(color)
        else:
            colores_oscuras.append(color)

    def _mediana_grupo(colores: List[np.ndarray], respaldo: float) -> np.ndarray:
        if not colores:
            return np.array([respaldo, respaldo, respaldo], dtype=np.float32)
        return np.median(np.stack(colores, axis=0), axis=0).astype(np.float32)

    # Respaldos razonables si faltara algún grupo (claras≈claro, oscuras≈oscuro).
    base_clara = _mediana_grupo(colores_claras, 235.0)
    base_oscura = _mediana_grupo(colores_oscuras, 20.0)
    return base_clara, base_oscura


# ---------------------------------------------------------------------------
# Clasificación del color de un resaltado en HSV
# ---------------------------------------------------------------------------

def clasificar_color_hsv(color_bgr: np.ndarray) -> Optional[str]:
    """Clasifica un color BGR en uno de los cuatro resaltados admitidos.

    Convierte el color a HSV y decide por rangos de tono, exigiendo una
    saturación y un brillo mínimos para que el tono sea fiable. Devuelve
    ``"amarillo"``, ``"rojo"``, ``"verde"`` o ``"azul"`` si el color encaja en
    alguno de los rangos de :data:`_RANGOS_TONO`; en caso contrario (color
    grisáceo, apagado o con un tono que no cae en ningún rango) devuelve
    ``None``, señal de color no clasificable (Requisito 6.6).

    :param color_bgr: color ``(B, G, R)`` como array o secuencia de 3 valores
        en la escala 0–255.
    :returns: el nombre del color de resaltado, o ``None`` si no es clasificable.
    """
    color = np.array(color_bgr, dtype=np.uint8).reshape(1, 1, 3)
    hsv = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)[0, 0]
    tono, saturacion, valor = int(hsv[0]), int(hsv[1]), int(hsv[2])

    # Un color con poca saturación o muy oscuro no tiene tono fiable: no se
    # clasifica como resaltado de color (evita falsos positivos en gris).
    if saturacion < _SATURACION_MINIMA_RESALTADO or valor < _VALOR_MINIMO_RESALTADO:
        return None

    for color_nombre, tramos in _RANGOS_TONO.items():
        for tono_min, tono_max in tramos:
            if tono_min <= tono <= tono_max:
                return color_nombre
    # Tono fuera de todos los rangos admitidos: no clasificable.
    return None


# ---------------------------------------------------------------------------
# Detección de casillas resaltadas sobre las 64 celdas
# ---------------------------------------------------------------------------

def detectar_resaltadas_desde_celdas(
    celdas: Dict[Tuple[str, int], Casilla],
) -> Tuple[List[Resaltada], List[Dudosa], List[str]]:
    """Detecta y clasifica las casillas resaltadas de un tablero ya dividido.

    Para cada una de las 64 casillas:

    1. Estima su color vivo dominante y la fracción de píxeles vivos.
    2. La casilla es candidata a resaltada solo si la fracción de vivos alcanza
       :data:`_FRACCION_VIVOS_MINIMA` Y su color vivo se aparta de la base más
       cercana (clara u oscura) por encima de :data:`_UMBRAL_DIFERENCIA_BASE`.
    3. Clasifica el color con :func:`clasificar_color_hsv`. Si encaja en uno de
       los cuatro colores, añade una :class:`Resaltada`. Si no encaja (color no
       clasificable), añade una :class:`Dudosa` con motivo
       ``color_resaltado_desconocido`` y emite un aviso en español, sin inventar
       el color (Requisito 6.6).

    Si ninguna casilla resulta resaltada ni dudosa, devuelve tres listas vacías:
    la sección de resaltadas se omite por completo (Requisito 6.5). Las casillas
    se recorren en orden determinista (fila 1→8, columna a→h).

    :param celdas: diccionario ``{(columna, fila): Casilla}``.
    :returns: tupla ``(resaltadas, dudosas, avisos)`` con las listas resultantes.
    """
    base_clara, base_oscura = estimar_colores_base_bgr(celdas)

    resaltadas: List[Resaltada] = []
    dudosas: List[Dudosa] = []
    avisos: List[str] = []

    for columna, fila in iterar_casillas():
        celda = celdas.get((columna, fila))
        if celda is None:
            continue

        color_vivo, fraccion = _color_vivo_dominante(celda.imagen)

        # Sin suficiente color vivo no puede haber resaltado (caso típico de los
        # diagramas de libro b/n, sin apenas píxeles de color).
        if color_vivo is None or fraccion < _FRACCION_VIVOS_MINIMA:
            continue

        # Distancia a la base MÁS CERCANA: una casilla normal (con o sin pieza)
        # conserva como color vivo el de su base y queda cerca de 0; solo un
        # resaltado real se aparta de ambas bases.
        diferencia = min(
            _diferencia_color(color_vivo, base_clara),
            _diferencia_color(color_vivo, base_oscura),
        )
        if diferencia < _UMBRAL_DIFERENCIA_BASE:
            continue

        token = unir_casilla(columna, fila)
        color_nombre = clasificar_color_hsv(color_vivo)
        if color_nombre in COLORES_RESALTADO:
            resaltadas.append(Resaltada(casilla=token, color=color_nombre))
        else:
            # La casilla destaca del fondo pero su color no encaja en ninguno de
            # los cuatro admitidos: dudosa, sin inventar color (Requisito 6.6).
            dudosas.append(
                Dudosa(casilla=token, motivo="color_resaltado_desconocido")
            )
            avisos.append(
                f"La casilla {token} parece resaltada pero su color no se ha "
                f"podido clasificar; revísela manualmente."
            )

    return resaltadas, dudosas, avisos


# ---------------------------------------------------------------------------
# Función de conveniencia: acepta imagen completa o celdas
# ---------------------------------------------------------------------------

def detectar_resaltadas(
    entrada,
) -> Tuple[List[Resaltada], List[Dudosa], List[str]]:
    """Detecta las casillas resaltadas a partir de una imagen o de las celdas.

    Función de conveniencia que admite dos formas de entrada:

    - Una imagen/área del tablero (``np.ndarray``): se localiza el tablero (si es
      la imagen completa) y se divide en 64 casillas antes de detectar.
    - Un diccionario de celdas ``{(columna, fila): Casilla}`` (salida de
      :func:`~modulos.reconocimiento.tablero.dividir_en_64`): se usa directamente.

    :param entrada: imagen BGR (``np.ndarray``) o diccionario de celdas.
    :returns: tupla ``(resaltadas, dudosas, avisos)`` (ver
        :func:`detectar_resaltadas_desde_celdas`).
    """
    if isinstance(entrada, np.ndarray):
        area = localizar_tablero(entrada)
        celdas = dividir_en_64(area)
    elif isinstance(entrada, dict):
        celdas = entrada
    else:
        raise TypeError(
            "detectar_resaltadas espera una imagen (np.ndarray) o un diccionario "
            "de celdas {(columna, fila): Casilla}."
        )
    return detectar_resaltadas_desde_celdas(celdas)
