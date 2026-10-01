"""Localización del tablero, división en 64 casillas y detección de estilo.

Este módulo implementa la primera etapa del Modulo_Reconocimiento
(Requisitos 2.1, 2.2, 2.3, 2.6): tomar una imagen decodificada con OpenCV,
localizar el área rectangular del tablero de ajedrez, recortarla a un cuadrado
normalizado, dividirla en las 64 casillas (8 filas x 8 columnas) y detectar si
el diagrama es de estilo *color digital* (piezas vectoriales sobre tablero
verde/crema, como los de ``ejemplos/braille/``) o de estilo *libro en blanco y
negro* (diagramas de imprenta, como los de ``ejemplos/audio/``).

La localización depende del estilo (enfoque validado en ``docs/prototipo_vision.py``):

- **Color digital**: se recortan los márgenes blancos/uniformes alrededor del
  tablero (columnas y filas con suficiente proporción de píxeles "no blancos") y
  se reescala el recorte al tamaño normalizado.
- **Libro en blanco y negro**: se localiza el marco negro grueso del diagrama y
  se recorta por dentro (dejando fuera el número del diagrama y los márgenes),
  midiendo el grosor del marco, y se reescala con interpolación cúbica.

Este cambio de enfoque corrige los fallos diagnosticados en
``docs/diagnostico_vision.md`` (perspectivas deformadas y rejillas desplazadas):
en vez de buscar un cuadrilátero y aplicar ``warpPerspective`` —que se torcía con
flechas o casillas resaltadas—, se recorta directamente el área del tablero según
su estilo, que es mucho más estable en estos ejemplos.

Aquí NO se clasifica el contenido de cada casilla (vacía/no vacía es la tarea
10; el reconocimiento de pieza por siluetas es la tarea 12). Esta etapa se limita
a localizar, dividir y detectar el estilo.

Importante sobre la orientación: la numeración de rejilla que se asigna aquí es
una numeración *por defecto* (fila 1 abajo, columna ``a`` a la izquierda desde
la perspectiva de la imagen). La corrección de la orientación real del tablero
(cuando está visto desde el lado de las negras) la realiza después el
Modulo_Orientacion; esta etapa solo divide el área localizada en 8x8.

Si no se localiza ningún tablero, se lanza :class:`TableroNoDetectadoError`, de
modo que el flujo rechace el procesamiento y NO genere ninguna posición
(Requisito 2.2).

Todos los nombres, comentarios y mensajes van en español, según las reglas del
proyecto (regla 15).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import cv2
import numpy as np

from modulos.posicion import COLUMNAS, FILAS, iterar_casillas


# ---------------------------------------------------------------------------
# Excepción de dominio
# ---------------------------------------------------------------------------

class TableroNoDetectadoError(Exception):
    """Se lanza cuando no se localiza ningún tablero 8x8 en la imagen.

    Su mensaje va en español y es apto para mostrarse al usuario. Al lanzarse,
    el Modulo_Reconocimiento rechaza el procesamiento y no genera ninguna
    posición (Requisito 2.2).
    """

    def __init__(
        self,
        mensaje: str = "No se ha detectado un tablero en la imagen.",
    ) -> None:
        super().__init__(mensaje)


# ---------------------------------------------------------------------------
# Constantes de configuración de la localización
# ---------------------------------------------------------------------------

# Lado en píxeles del cuadrado al que se normaliza el tablero. Es múltiplo de 8
# para que las 64 casillas queden con un tamaño entero idéntico (cada casilla
# mide LADO_TABLERO_NORMALIZADO / 8 = 80 píxeles).
LADO_TABLERO_NORMALIZADO = 640

# Umbral de saturación media (canal S de HSV, escala 0-255) por encima del cual
# se considera que la imagen tiene color apreciable y es, por tanto, de estilo
# "color digital". Por debajo se considera esencialmente en escala de grises
# (estilo "libro b/n"). El valor separa con holgura los tableros verdes/crema de
# ``ejemplos/braille/`` de los diagramas grises de ``ejemplos/audio/``.
_UMBRAL_SATURACION_COLOR = 30.0

# Localización digital: un píxel se considera "no blanco" (parte del tablero) si
# su gris es inferior a este valor. Los márgenes blancos de la imagen quedan por
# encima y se recortan.
_UMBRAL_NO_BLANCO = 245

# Proporción mínima de píxeles "no blancos" que debe tener una fila/columna para
# considerarla parte del tablero digital (y no un margen uniforme).
_PROPORCION_NO_BLANCO = 0.5

# Localización de libro: un píxel se considera "negro" (parte del marco) si su
# gris es inferior a este valor.
_UMBRAL_NEGRO_MARCO = 110

# Proporción mínima de píxeles negros de una fila/columna para considerarla parte
# del marco negro grueso del diagrama de imprenta.
_PROPORCION_MARCO = 0.6

# Proporción mínima de píxeles de borde (Canny) que debe tener el área localizada
# para aceptarla como tablero. Descarta imágenes uniformes o casi vacías (p. ej.
# una imagen en blanco), que no contienen la estructura de rejilla y piezas de un
# tablero real (Requisito 2.2).
_PROPORCION_BORDES_MINIMA = 0.01

# Nombres de los dos estilos admitidos.
ESTILO_COLOR_DIGITAL = "color_digital"
ESTILO_LIBRO_BYN = "libro_byn"


# ---------------------------------------------------------------------------
# Estructura de una casilla dentro de la rejilla
# ---------------------------------------------------------------------------

@dataclass
class Casilla:
    """Una de las 64 casillas de la rejilla del tablero localizado.

    - ``columna``: letra ``a``–``h`` (numeración de rejilla por defecto,
      columna ``a`` a la izquierda de la imagen).
    - ``fila``: entero ``1``–``8`` (numeración de rejilla por defecto, fila 1
      abajo en la imagen).
    - ``imagen``: recorte ``np.ndarray`` de la casilla dentro del tablero ya
      normalizado.
    - ``limites``: caja ``(x0, y0, x1, y1)`` del recorte dentro del tablero
      normalizado, en píxeles.

    La numeración es provisional: el Modulo_Orientacion podrá reinterpretarla
    al corregir la orientación real del tablero.
    """

    columna: str
    fila: int
    imagen: np.ndarray
    limites: Tuple[int, int, int, int]

    @property
    def casilla(self) -> str:
        """Token de casilla de la rejilla, por ejemplo ``"e1"``."""
        return f"{self.columna}{self.fila}"


# ---------------------------------------------------------------------------
# Detección del estilo del diagrama
# ---------------------------------------------------------------------------

def detectar_estilo(imagen: np.ndarray) -> str:
    """Detecta si ``imagen`` es de estilo color digital o libro en blanco y negro.

    Heurística simple basada en la saturación de color: se convierte la imagen a
    HSV y se calcula la saturación media (canal S). Si supera
    :data:`_UMBRAL_SATURACION_COLOR`, la imagen tiene color apreciable y se
    clasifica como :data:`ESTILO_COLOR_DIGITAL` (tableros verdes/crema de
    ``ejemplos/braille/``). En caso contrario es esencialmente escala de grises y
    se clasifica como :data:`ESTILO_LIBRO_BYN` (diagramas de ``ejemplos/audio/``).

    Acepta tanto la imagen completa como el área ya recortada del tablero
    (Requisito 2.6). Es el mismo criterio (``es_color``) del prototipo validado.

    :param imagen: matriz BGR de OpenCV.
    :returns: ``"color_digital"`` o ``"libro_byn"``.
    """
    if imagen is None or not isinstance(imagen, np.ndarray) or imagen.size == 0:
        raise TableroNoDetectadoError()

    if imagen.ndim != 3 or imagen.shape[2] != 3:
        # Una imagen de un solo canal no tiene color: es libro en blanco y negro.
        return ESTILO_LIBRO_BYN

    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    saturacion_media = float(hsv[:, :, 1].mean())

    if saturacion_media > _UMBRAL_SATURACION_COLOR:
        return ESTILO_COLOR_DIGITAL
    return ESTILO_LIBRO_BYN


# ---------------------------------------------------------------------------
# Localización del tablero por estilo
# ---------------------------------------------------------------------------

def _localizar_digital(imagen: np.ndarray) -> np.ndarray:
    """Recorta los márgenes blancos/uniformes de un tablero de color digital.

    Convierte a gris, marca los píxeles "no blancos" (parte del tablero) y se
    queda con el rango de filas y columnas cuya proporción de "no blanco" supera
    :data:`_PROPORCION_NO_BLANCO`. Después reescala el recorte al tamaño
    normalizado. Reproduce ``localizar_digital`` del prototipo validado.
    """
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    no_blanco = gris < _UMBRAL_NO_BLANCO
    filas = np.where(no_blanco.mean(axis=1) > _PROPORCION_NO_BLANCO)[0]
    columnas = np.where(no_blanco.mean(axis=0) > _PROPORCION_NO_BLANCO)[0]
    if len(filas) and len(columnas):
        imagen = imagen[filas[0] : filas[-1] + 1, columnas[0] : columnas[-1] + 1]
    return cv2.resize(imagen, (LADO_TABLERO_NORMALIZADO, LADO_TABLERO_NORMALIZADO))


def _grosor_marco(mascara: np.ndarray) -> Tuple[int, int]:
    """Mide el grosor del marco negro por arriba y por abajo de ``mascara``.

    Recorre las filas desde arriba mientras la fila esté mayoritariamente negra
    (media > 0.5) y hasta un máximo de un décimo del alto; de forma simétrica
    desde abajo. Devuelve ``(fila_interior_superior, fila_interior_inferior)``,
    los índices por dentro del marco. Reproduce la función ``grosor`` interna del
    prototipo (aplicable también a la traspuesta para medir laterales).
    """
    alto = mascara.shape[0]
    superior = 0
    while superior < alto // 10 and mascara[superior].mean() > 0.5:
        superior += 1
    inferior = alto - 1
    while inferior > alto * 9 // 10 and mascara[inferior].mean() > 0.5:
        inferior -= 1
    return superior, inferior


def _localizar_libro(imagen: np.ndarray) -> np.ndarray:
    """Localiza el marco negro grueso de un diagrama de libro y recorta dentro.

    Marca los píxeles negros (gris < :data:`_UMBRAL_NEGRO_MARCO`), busca las
    filas y columnas del marco (con proporción de negro > :data:`_PROPORCION_MARCO`),
    mide el grosor del marco por los cuatro lados y recorta por dentro, dejando
    fuera el número del diagrama y los márgenes. Reescala con interpolación cúbica
    al tamaño normalizado. Reproduce ``localizar_libro`` del prototipo validado.
    """
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    bw = (gris < _UMBRAL_NEGRO_MARCO).astype(np.uint8)
    alto, ancho = bw.shape

    filas = np.where(bw.mean(axis=1) > _PROPORCION_MARCO)[0]
    columnas = np.where(bw.mean(axis=0) > _PROPORCION_MARCO)[0]
    y0, y1 = (int(filas.min()), int(filas.max())) if len(filas) > 1 else (0, alto - 1)
    x0, x1 = (int(columnas.min()), int(columnas.max())) if len(columnas) > 1 else (0, ancho - 1)

    marco = bw[y0 : y1 + 1, x0 : x1 + 1]
    superior, inferior = _grosor_marco(marco)
    izquierda, derecha = _grosor_marco(marco.T)

    recorte = imagen[y0 + superior : y0 + inferior + 1, x0 + izquierda : x0 + derecha + 1]
    return cv2.resize(
        recorte,
        (LADO_TABLERO_NORMALIZADO, LADO_TABLERO_NORMALIZADO),
        interpolation=cv2.INTER_CUBIC,
    )


def _parece_tablero(area: np.ndarray) -> bool:
    """Indica si ``area`` presenta suficiente estructura para ser un tablero.

    Exige una proporción mínima de píxeles de borde (Canny). Una imagen uniforme
    o casi vacía —por ejemplo una imagen en blanco— no la supera y se rechaza como
    tablero (Requisito 2.2).
    """
    if area is None or area.size == 0:
        return False
    if area.ndim == 3:
        gris = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY)
    else:
        gris = area
    bordes = cv2.Canny(gris, 50, 150)
    proporcion = float(np.count_nonzero(bordes)) / float(bordes.size)
    return proporcion >= _PROPORCION_BORDES_MINIMA


def localizar_tablero(imagen: np.ndarray) -> np.ndarray:
    """Localiza el área del tablero en ``imagen`` y la devuelve normalizada.

    Decide la localización según el estilo detectado (Requisito 2.1):

    - **color digital**: recorta los márgenes blancos/uniformes alrededor del
      tablero (:func:`_localizar_digital`);
    - **libro b/n**: localiza el marco negro grueso y recorta por dentro
      (:func:`_localizar_libro`).

    En ambos casos devuelve un recorte cuadrado de lado
    :data:`LADO_TABLERO_NORMALIZADO` píxeles, listo para dividir en 8x8.

    Lanza :class:`TableroNoDetectadoError` si la imagen no es válida o si el área
    resultante no presenta estructura de tablero (imagen en blanco, etc.), para
    rechazar el procesamiento sin generar ninguna posición (Requisito 2.2).

    :param imagen: matriz BGR de OpenCV (``np.ndarray`` de 3 canales).
    :returns: recorte cuadrado del tablero normalizado (área 640x640).
    """
    if imagen is None or not isinstance(imagen, np.ndarray) or imagen.size == 0:
        raise TableroNoDetectadoError()

    if imagen.ndim != 3 or imagen.shape[2] != 3:
        raise TableroNoDetectadoError()

    alto, ancho = imagen.shape[:2]
    if alto < 8 or ancho < 8:
        # Demasiado pequeña para contener 64 casillas distinguibles.
        raise TableroNoDetectadoError()

    try:
        if detectar_estilo(imagen) == ESTILO_COLOR_DIGITAL:
            area = _localizar_digital(imagen)
        else:
            area = _localizar_libro(imagen)
    except cv2.error as error:  # Recorte degenerado (imagen sin marco, etc.).
        raise TableroNoDetectadoError() from error

    if area is None or area.size == 0 or not _parece_tablero(area):
        # El área no tiene estructura de tablero (imagen en blanco o uniforme).
        raise TableroNoDetectadoError()

    return area


# ---------------------------------------------------------------------------
# División en 64 casillas
# ---------------------------------------------------------------------------

def dividir_en_64(area: np.ndarray) -> Dict[Tuple[str, int], Casilla]:
    """Divide el ``area`` del tablero normalizado en 64 casillas 8x8.

    Reparte el área en 8 filas (numeradas de 1 a 8) y 8 columnas (nombradas de
    la ``a`` a la ``h``), Requisito 2.3. Devuelve un diccionario indexado por
    ``(columna, fila)`` cuyos valores son :class:`Casilla` con el recorte y sus
    límites.

    La numeración de rejilla es la de por defecto: la columna ``a`` queda a la
    izquierda de la imagen y la fila 1 en la parte inferior (fila 8 arriba). Es la
    misma convención que usa el prototipo validado (clave ``(COLS[c], 8 - r)`` con
    ``r`` la fila de imagen desde arriba). La orientación real la corrige después
    el Modulo_Orientacion.

    :param area: recorte cuadrado del tablero (salida de :func:`localizar_tablero`).
    :returns: diccionario ``{(columna, fila): Casilla}`` con 64 entradas.
    """
    if area is None or not isinstance(area, np.ndarray) or area.size == 0:
        raise TableroNoDetectadoError()

    alto, ancho = area.shape[:2]
    # Bordes de las 8 franjas en cada eje, robustos aunque alto/ancho no sean
    # múltiplos exactos de 8 (usando linspace en lugar de un paso fijo).
    bordes_x = np.linspace(0, ancho, 9).astype(int)
    bordes_y = np.linspace(0, alto, 9).astype(int)

    casillas: Dict[Tuple[str, int], Casilla] = {}
    for columna, fila in iterar_casillas():
        indice_columna = COLUMNAS.index(columna)  # 0..7 de izquierda a derecha
        # La fila 1 está abajo: la fila de la imagen crece hacia abajo, así que
        # la fila 1 (abajo) corresponde a la franja inferior de la imagen.
        indice_fila_imagen = FILAS.index(fila)      # 0 para fila 1 ... 7 para fila 8
        fila_desde_arriba = 7 - indice_fila_imagen  # invertir: fila 1 abajo

        x0 = int(bordes_x[indice_columna])
        x1 = int(bordes_x[indice_columna + 1])
        y0 = int(bordes_y[fila_desde_arriba])
        y1 = int(bordes_y[fila_desde_arriba + 1])

        recorte = area[y0:y1, x0:x1].copy()
        casillas[(columna, fila)] = Casilla(
            columna=columna,
            fila=fila,
            imagen=recorte,
            limites=(x0, y0, x1, y1),
        )

    return casillas
