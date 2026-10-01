"""Clasificación de pieza por comparación de SILUETAS con confianza.

Tercera etapa del Modulo_Reconocimiento (tarea 12.1, Requisitos 2.4, 2.5, 2.7,
2.8). Tras localizar el tablero, dividirlo en 64 casillas y extraer la silueta y
la ocupación de cada casilla (etapa de contenido, tarea 10), esta etapa
identifica el tipo y el color de las piezas de las casillas ocupadas.

Enfoque validado (ver ``docs/prototipo_vision.py`` y ``docs/diagnostico_vision.md``)
-----------------------------------------------------------------------------------
1. Se analiza la imagen: estilo (color digital / libro b/n) y, por casilla, su
   silueta 64×64, la fracción de ocupación y si la pieza es blanca o negra.
2. Solo se procesan las casillas cuya fracción de ocupación alcanza
   :data:`~modulos.reconocimiento.contenido.OCUPACION_MINIMA` (las demás son
   vacías: ni pieza ni dudosa).
3. El **tipo** se decide comparando la silueta de la casilla contra el **banco de
   siluetas** del estilo detectado con ``cv2.matchTemplate`` y
   ``TM_CCOEFF_NORMED``, añadiendo un margen de :data:`_MARGEN_SILUETA` píxeles a
   la silueta de la casilla para tolerar pequeños desplazamientos. El mayor score
   sobre todo el banco es la **confianza**.
4. El **color** (blanco/negro) se decide aparte, a partir de la silueta (no del
   template matching): lo aporta la etapa de rasgos (``es_blanco``).

Regla de no invención (Requisito 2.8, invariante central — Property 5)
----------------------------------------------------------------------
Si el mejor score es menor que :data:`~modulos.config.UMBRAL_CONFIANZA`, la
casilla se marca como dudosa con motivo ``confianza_baja`` y se deja SIN pieza:
NUNCA se añade una pieza por debajo del umbral. Solo si el score alcanza el
umbral se registra la pieza con su confianza. Así ninguna casilla dudosa por
confianza baja aporta pieza a la :class:`Posicion`.

Aquí NO se corrige la orientación ni se valida la legalidad: esas etapas las
realizan después el Modulo_Orientacion y el Modulo_Validacion.

Todos los nombres, comentarios y mensajes van en español, según las reglas del
proyecto (regla 15).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from modulos.config import UMBRAL_CONFIANZA
from modulos.posicion import Dudosa, Pieza, Posicion, unir_casilla
from modulos.reconocimiento.contenido import OCUPACION_MINIMA, rasgos_tablero
from modulos.reconocimiento.plantillas import BancosSiluetas, construir_bancos_siluetas
from modulos.reconocimiento.tablero import (
    detectar_estilo,
    dividir_en_64,
    localizar_tablero,
)


# Tipo de las plantillas de un estilo en el esquema clásico {(tipo, color): [imgs]}.
# Se conserva para compatibilidad de la API pública (importado por otros módulos).
PlantillasEstilo = Dict[Tuple[str, str], List[np.ndarray]]

# Margen (en píxeles) que se añade alrededor de la silueta de la casilla antes de
# compararla con las plantillas del banco, para tolerar desplazamientos de 1-4 px
# (mismo valor que el prototipo validado).
_MARGEN_SILUETA = 4


def clasificar_pieza(
    silueta: np.ndarray,
    banco_estilo: List[Tuple[str, np.ndarray]],
) -> Optional[Tuple[str, float]]:
    """Clasifica el TIPO de una silueta contra el banco de siluetas de un estilo.

    Añade un margen de :data:`_MARGEN_SILUETA` píxeles a la silueta y la compara
    con cada silueta del banco mediante ``cv2.matchTemplate`` y
    ``TM_CCOEFF_NORMED``, tomando el máximo. Devuelve el ``(tipo, score)`` de la
    mejor coincidencia. Reproduce ``clasificar`` del prototipo validado.

    :param silueta: silueta 64×64 (``uint8``) de la casilla a clasificar.
    :param banco_estilo: lista ``[(tipo, silueta_64x64), ...]`` del estilo.
    :returns: ``(tipo, score)`` de la mejor coincidencia, o ``None`` si el banco
        está vacío.
    """
    if not banco_estilo:
        return None

    patron = cv2.copyMakeBorder(
        silueta, _MARGEN_SILUETA, _MARGEN_SILUETA, _MARGEN_SILUETA, _MARGEN_SILUETA,
        cv2.BORDER_CONSTANT, value=0,
    ).astype(np.float32)

    mejor_tipo: Optional[str] = None
    mejor_score = -2.0
    for tipo, plantilla in banco_estilo:
        resultado = cv2.matchTemplate(patron, plantilla.astype(np.float32), cv2.TM_CCOEFF_NORMED)
        score = float(resultado.max())
        if score > mejor_score:
            mejor_score = score
            mejor_tipo = tipo

    if mejor_tipo is None:
        return None
    return mejor_tipo, mejor_score


def reconocer_piezas(
    imagen: np.ndarray,
    plantillas: Optional[BancosSiluetas] = None,
    raiz_proyecto: str = ".",
) -> Posicion:
    """Reconoce las piezas de un tablero a partir de su imagen.

    Localiza el tablero, detecta el estilo, lo divide en 64 casillas y extrae los
    rasgos (silueta, ocupación y color) de cada casilla. Para cada casilla ocupada
    (fracción >= :data:`OCUPACION_MINIMA`) clasifica el tipo contra el banco de
    siluetas del estilo y decide, según el umbral de confianza, si registra la
    pieza o marca la casilla como dudosa (Requisitos 2.4, 2.5, 2.7, 2.8).

    Reglas de decisión por casilla:

    - Ocupación < :data:`OCUPACION_MINIMA`: casilla vacía; no genera ni pieza ni
      dudosa.
    - Ocupada con mejor score ``>= UMBRAL_CONFIANZA``: se añade una :class:`Pieza`
      con ``confianza = score`` y el color de ``es_blanco``.
    - Ocupada con mejor score ``< UMBRAL_CONFIANZA``: se añade una :class:`Dudosa`
      con motivo ``"confianza_baja"`` y NO se añade pieza (invariante Property 5).
    - Si el estilo detectado no tiene banco de siluetas, las casillas ocupadas se
      marcan dudosas (no se inventa ninguna pieza).

    NO corrige la orientación ni valida la legalidad.

    :param imagen: matriz BGR de OpenCV con el tablero.
    :param plantillas: banco de siluetas ``{estilo: [(tipo, silueta), ...]}``; si
        es ``None`` se construye con :func:`construir_bancos_siluetas`.
    :param raiz_proyecto: raíz desde la que construir el banco si no se pasa.
    :returns: :class:`Posicion` con las piezas reconocidas y las casillas dudosas.
    """
    if plantillas is None:
        plantillas = construir_bancos_siluetas(raiz_proyecto=raiz_proyecto)

    area = localizar_tablero(imagen)
    estilo = detectar_estilo(area)
    celdas = dividir_en_64(area)
    rasgos = rasgos_tablero(celdas, estilo)

    banco_estilo = plantillas.get(estilo, [])

    posicion = Posicion()

    for (columna, fila), (silueta, fraccion, es_blanco) in rasgos.items():
        # Casilla vacía: no se clasifica ni se genera nada.
        if fraccion < OCUPACION_MINIMA:
            continue

        token = unir_casilla(columna, fila)
        clasificacion = clasificar_pieza(silueta, banco_estilo)

        if clasificacion is None:
            # Sin banco con el que comparar: no se inventa; se marca dudosa.
            posicion.dudosas.append(Dudosa(casilla=token, motivo="confianza_baja"))
            continue

        tipo, score = clasificacion
        color = "blanco" if es_blanco else "negro"

        if score >= UMBRAL_CONFIANZA:
            posicion.piezas.append(
                Pieza(
                    tipo=tipo,
                    color=color,
                    columna=columna,
                    fila=fila,
                    confianza=max(0.0, min(1.0, score)),
                )
            )
        else:
            # Confianza por debajo del umbral: dudosa y SIN pieza (Property 5).
            posicion.dudosas.append(Dudosa(casilla=token, motivo="confianza_baja"))

    return posicion
