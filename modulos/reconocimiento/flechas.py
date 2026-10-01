"""Detección automática de flechas y combinación con las flechas manuales.

Este módulo implementa la etapa de flechas del Modulo_Reconocimiento y del CLI
(Requisitos 7.1 y 7.5). Las flechas de los diagramas son difíciles de detectar
de forma fiable, así que el diseño combina una **detección automática
best-effort** (de baja fiabilidad) con la **entrada manual explícita** que llega
por el parámetro ``--flecha`` del CLI.

Reparto de responsabilidades:

- :func:`parsear_flecha_manual` y :func:`parsear_flechas_manuales`: convierten
  las cadenas ``ORIGEN-DESTINO`` (o ``ORIGEN-DESTINO:inverso``) en objetos
  :class:`~modulos.posicion.Flecha`, validando que ambas casillas sean válidas
  (``a``–``h`` × ``1``–``8``). Si una casilla no es válida, se descarta la flecha
  y se emite un aviso en español, sin inventar nunca casillas (Requisito 7.5).
- :func:`detectar_flechas_auto`: detección best-effort sobre la imagen del
  tablero (gris + Canny + ``HoughLinesP``, fusión de segmentos colineales y
  heurística de la punta). Su fiabilidad es baja por diseño: es aceptable que no
  devuelva ninguna flecha. Nunca inventa flechas donde no hay evidencia clara y
  nunca lanza excepción; el usuario puede corregir con ``--flecha``.
- :func:`combinar_flechas`: fusiona las flechas automáticas con las manuales
  dando prioridad a las manuales (una manual sustituye a la auto con el mismo
  origen y destino; si no coincide con ninguna, se añade). El resultado es
  determinista y con orden estable.
- :func:`obtener_flechas`: función de conveniencia que hace detección auto +
  parseo manual + combinación y devuelve las flechas combinadas y los avisos.

Todos los nombres, comentarios y mensajes van en español, según las reglas del
proyecto (regla 15).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

try:  # OpenCV solo se necesita para la detección automática.
    import cv2
except Exception:  # pragma: no cover - entorno sin OpenCV
    cv2 = None  # type: ignore[assignment]

from modulos.posicion import COLUMNAS, Flecha, es_casilla_valida, unir_casilla
from modulos.reconocimiento.tablero import Casilla


# ---------------------------------------------------------------------------
# Constantes de la detección automática (best-effort)
# ---------------------------------------------------------------------------

# Sufijo reservado que, en una cadena manual, indica que la flecha apunta en
# sentido contrario (por ejemplo ``e5-f3:inverso``).
_SUFIJO_INVERSO = ":inverso"

# Umbral (en píxeles) de la distancia entre extremos de dos segmentos para
# considerarlos parte del mismo trazo al fusionar segmentos colineales.
_DISTANCIA_FUSION = 25.0

# Diferencia angular máxima (en grados) para considerar dos segmentos colineales.
_ANGULO_COLINEAL_GRADOS = 12.0

# Longitud mínima (en píxeles) de un trazo fusionado para aceptarlo como flecha.
# Descarta segmentos cortos de ruido; solo trazos con recorrido claro cuentan.
_LONGITUD_MINIMA_TRAZO = 40.0

# Asimetría mínima de densidad de bordes entre los dos extremos de un trazo para
# aceptarlo como flecha. Una flecha real tiene una cabeza (mucho más borde en un
# extremo) y una cola (menos borde). Las líneas de la rejilla del tablero, en
# cambio, tienen densidad parecida en ambos extremos: exigir esta asimetría
# evita confundir la rejilla con flechas y respeta el principio de no inventar
# flechas donde no hay evidencia clara de una cabeza (Requisito 7.5).
_ASIMETRIA_MINIMA_PUNTA = 0.10


# ---------------------------------------------------------------------------
# Parseo de flechas manuales
# ---------------------------------------------------------------------------

def parsear_flecha_manual(cadena: str) -> Tuple[Optional[Flecha], Optional[str]]:
    """Parsea una cadena ``ORIGEN-DESTINO`` a una :class:`Flecha` manual.

    Admite la forma directa ``"e5-f3"`` y la forma inversa con el sufijo
    reservado ``"e5-f3:inverso"``. Ambas casillas se validan con
    :func:`~modulos.posicion.es_casilla_valida`.

    Devuelve una tupla ``(flecha, aviso)``:

    - Si la cadena es válida, ``flecha`` es una :class:`Flecha` con
      ``fuente="manual"`` y ``aviso`` es ``None``.
    - Si el origen o el destino no corresponden a una casilla válida (o la
      sintaxis es incorrecta), ``flecha`` es ``None`` y ``aviso`` contiene un
      mensaje en español que describe el problema, sin inventar casillas
      (Requisito 7.5).
    """
    if not isinstance(cadena, str):
        return None, "Flecha no reconocida: valor vacío o no textual."

    texto = cadena.strip()
    if not texto:
        return None, "Flecha no reconocida: valor vacío."

    # Determinar el sentido a partir del sufijo reservado ":inverso".
    sentido = "directo"
    cuerpo = texto
    if texto.lower().endswith(_SUFIJO_INVERSO):
        sentido = "inverso"
        cuerpo = texto[: -len(_SUFIJO_INVERSO)]

    # El cuerpo debe ser exactamente ORIGEN-DESTINO (un único guion separador).
    partes = cuerpo.split("-")
    if len(partes) != 2:
        return None, (
            f"Flecha no reconocida: {cadena!r}. El formato debe ser "
            f"ORIGEN-DESTINO, por ejemplo f3-e5 o e5-f3:inverso."
        )

    origen = partes[0].strip().lower()
    destino = partes[1].strip().lower()

    # Validar ambas casillas sin inventar ninguna (Requisito 7.5).
    casillas_invalidas = []
    if not es_casilla_valida(origen):
        casillas_invalidas.append(f"origen {origen!r}")
    if not es_casilla_valida(destino):
        casillas_invalidas.append(f"destino {destino!r}")

    if casillas_invalidas:
        detalle = " y ".join(casillas_invalidas)
        return None, (
            f"Flecha no reconocida: {cadena!r}. Casilla no válida ({detalle}); "
            f"las casillas deben ir de 'a' a 'h' y de 1 a 8."
        )

    return Flecha(origen=origen, destino=destino, sentido=sentido, fuente="manual"), None


def parsear_flechas_manuales(
    lista_cadenas: Optional[List[str]],
) -> Tuple[List[Flecha], List[str]]:
    """Parsea la lista repetible de ``--flecha`` a flechas manuales.

    Aplica :func:`parsear_flecha_manual` a cada cadena de ``lista_cadenas``.
    Devuelve una tupla ``(flechas, avisos)`` donde ``flechas`` contiene solo las
    flechas válidas (en el mismo orden de entrada) y ``avisos`` contiene, en
    español, un mensaje por cada cadena descartada, sin inventar casillas
    (Requisito 7.5).
    """
    flechas: List[Flecha] = []
    avisos: List[str] = []

    if not lista_cadenas:
        return flechas, avisos

    for cadena in lista_cadenas:
        flecha, aviso = parsear_flecha_manual(cadena)
        if flecha is not None:
            flechas.append(flecha)
        if aviso is not None:
            avisos.append(aviso)

    return flechas, avisos


# ---------------------------------------------------------------------------
# Detección automática de flechas (best-effort, baja fiabilidad)
# ---------------------------------------------------------------------------

def _angulo_segmento(x1: float, y1: float, x2: float, y2: float) -> float:
    """Devuelve el ángulo del segmento en grados dentro del rango ``[0, 180)``.

    Se normaliza a media circunferencia porque un segmento no tiene sentido
    propio (la orientación se decide después mediante la heurística de la punta).
    """
    angulo = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
    return angulo


def _diferencia_angular(a: float, b: float) -> float:
    """Diferencia mínima entre dos ángulos en grados sobre ``[0, 180)``."""
    diferencia = abs(a - b) % 180.0
    return min(diferencia, 180.0 - diferencia)


def _distancia(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    """Distancia euclídea entre dos puntos ``(x, y)``."""
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _fusionar_segmentos_colineales(
    segmentos: List[Tuple[float, float, float, float]],
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Fusiona segmentos colineales y contiguos en trazos más largos.

    Recibe una lista de segmentos ``(x1, y1, x2, y2)`` (los que devuelve
    ``HoughLinesP``) y agrupa los que comparten dirección (colineales dentro de
    :data:`_ANGULO_COLINEAL_GRADOS`) y tienen extremos cercanos (dentro de
    :data:`_DISTANCIA_FUSION`). Cada trazo resultante se representa por sus dos
    extremos más alejados, que son los candidatos a origen y destino.

    La fusión es una heurística best-effort: no pretende ser exacta, solo
    reducir el ruido de segmentos partidos por una misma flecha.
    """
    trazos: List[List[Tuple[float, float]]] = []
    angulos_trazo: List[float] = []

    for x1, y1, x2, y2 in segmentos:
        angulo = _angulo_segmento(x1, y1, x2, y2)
        extremo_a = (x1, y1)
        extremo_b = (x2, y2)

        indice_encontrado = None
        for indice, puntos in enumerate(trazos):
            if _diferencia_angular(angulo, angulos_trazo[indice]) > _ANGULO_COLINEAL_GRADOS:
                continue
            # Comprobar cercanía con cualquiera de los puntos ya acumulados.
            cerca = any(
                _distancia(extremo_a, p) <= _DISTANCIA_FUSION
                or _distancia(extremo_b, p) <= _DISTANCIA_FUSION
                for p in puntos
            )
            if cerca:
                indice_encontrado = indice
                break

        if indice_encontrado is None:
            trazos.append([extremo_a, extremo_b])
            angulos_trazo.append(angulo)
        else:
            trazos[indice_encontrado].extend((extremo_a, extremo_b))

    # Reducir cada trazo a sus dos extremos más alejados entre sí.
    resultado: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    for puntos in trazos:
        mejor_par = None
        mejor_distancia = -1.0
        for i in range(len(puntos)):
            for j in range(i + 1, len(puntos)):
                distancia = _distancia(puntos[i], puntos[j])
                if distancia > mejor_distancia:
                    mejor_distancia = distancia
                    mejor_par = (puntos[i], puntos[j])
        if mejor_par is not None and mejor_distancia >= _LONGITUD_MINIMA_TRAZO:
            resultado.append(mejor_par)

    return resultado


def _casilla_de_punto(
    punto: Tuple[float, float],
    celdas: Dict[Tuple[str, int], Casilla],
) -> Optional[str]:
    """Mapea un punto ``(x, y)`` a la casilla de la rejilla que lo contiene.

    Recorre las 64 :class:`Casilla` usando sus ``limites`` ``(x0, y0, x1, y1)``
    dentro del tablero normalizado y devuelve el token de la casilla que contiene
    el punto (por ejemplo ``"e4"``), o ``None`` si el punto cae fuera de la
    rejilla. Nunca inventa una casilla: si no hay contención clara devuelve
    ``None``.
    """
    x, y = punto
    for (columna, fila), celda in celdas.items():
        x0, y0, x1, y1 = celda.limites
        if x0 <= x < x1 and y0 <= y < y1:
            casilla = unir_casilla(columna, fila)
            return casilla if es_casilla_valida(casilla) else None
    return None


def _densidad_bordes_cerca(
    bordes: np.ndarray, punto: Tuple[float, float], radio: int = 12
) -> float:
    """Densidad de píxeles de borde en un entorno cuadrado del ``punto``.

    Sirve de heurística para localizar la punta de la flecha: la cabeza de flecha
    (dos segmentos cortos convergentes) concentra más bordes que la cola. Se
    devuelve la proporción de píxeles de borde en la ventana, en ``[0, 1]``.
    """
    alto, ancho = bordes.shape[:2]
    x = int(round(punto[0]))
    y = int(round(punto[1]))
    x0 = max(0, x - radio)
    y0 = max(0, y - radio)
    x1 = min(ancho, x + radio + 1)
    y1 = min(alto, y + radio + 1)
    ventana = bordes[y0:y1, x0:x1]
    if ventana.size == 0:
        return 0.0
    return float(np.count_nonzero(ventana)) / float(ventana.size)


def detectar_flechas_auto(
    area: np.ndarray,
    celdas: Dict[Tuple[str, int], Casilla],
) -> List[Flecha]:
    """Detección automática best-effort de flechas sobre el tablero enderezado.

    Realiza un preprocesado en escala de grises, realza los bordes con Canny y
    detecta segmentos con ``HoughLinesP``. Después fusiona los segmentos
    colineales en trazos, estima la **punta** de cada trazo (heurística: el
    extremo con mayor densidad de bordes, por la convergencia de la cabeza de
    flecha) para fijar origen y destino, y mapea ambos extremos a casillas de la
    rejilla 8x8 (usando los límites de ``celdas``, salida de ``dividir_en_64``).

    **La fiabilidad es baja por diseño.** Es perfectamente aceptable que esta
    función devuelva pocas flechas o ninguna: nunca inventa flechas donde no hay
    evidencia clara (si algún extremo no cae en una casilla válida, se descarta
    ese trazo). Además, es robusta: ante cualquier problema (imagen inválida,
    OpenCV no disponible, etc.) devuelve una lista vacía sin lanzar excepción. El
    usuario puede corregir o completar el resultado con ``--flecha``.

    :param area: recorte cuadrado del tablero enderezado (salida de
        ``localizar_tablero``); matriz BGR de OpenCV o en escala de grises.
    :param celdas: diccionario ``{(columna, fila): Casilla}`` de
        ``dividir_en_64``, usado para mapear extremos a casillas.
    :returns: lista de :class:`Flecha` con ``fuente="auto"`` (posiblemente vacía).
    """
    if cv2 is None:
        # Sin OpenCV no hay detección automática; el usuario usa --flecha.
        return []

    if area is None or not isinstance(area, np.ndarray) or area.size == 0:
        return []

    if not celdas:
        return []

    try:
        if area.ndim == 3:
            gris = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY)
        else:
            gris = area
        gris = cv2.GaussianBlur(gris, (5, 5), 0)
        bordes = cv2.Canny(gris, 50, 150)

        lineas = cv2.HoughLinesP(
            bordes,
            rho=1,
            theta=np.pi / 180.0,
            threshold=50,
            minLineLength=int(_LONGITUD_MINIMA_TRAZO),
            maxLineGap=int(_DISTANCIA_FUSION),
        )
        if lineas is None:
            return []

        segmentos = [
            (float(x1), float(y1), float(x2), float(y2))
            for x1, y1, x2, y2 in lineas.reshape(-1, 4)
        ]
        trazos = _fusionar_segmentos_colineales(segmentos)

        flechas: List[Flecha] = []
        vistas: set[Tuple[str, str]] = set()
        for extremo_1, extremo_2 in trazos:
            # Heurística de la punta: el extremo con más densidad de bordes es la
            # cabeza de flecha (destino en sentido directo).
            densidad_1 = _densidad_bordes_cerca(bordes, extremo_1)
            densidad_2 = _densidad_bordes_cerca(bordes, extremo_2)

            # Sin una cabeza clara (asimetría de densidad suficiente) no hay
            # evidencia de flecha: probablemente es una línea de la rejilla. Se
            # descarta para no inventar flechas (Requisito 7.5).
            if abs(densidad_1 - densidad_2) < _ASIMETRIA_MINIMA_PUNTA:
                continue

            if densidad_2 >= densidad_1:
                punto_origen, punto_destino = extremo_1, extremo_2
            else:
                punto_origen, punto_destino = extremo_2, extremo_1

            casilla_origen = _casilla_de_punto(punto_origen, celdas)
            casilla_destino = _casilla_de_punto(punto_destino, celdas)

            # No inventar: si algún extremo no cae en casilla válida, se descarta.
            if casilla_origen is None or casilla_destino is None:
                continue
            if casilla_origen == casilla_destino:
                continue

            clave = (casilla_origen, casilla_destino)
            if clave in vistas:
                continue
            vistas.add(clave)

            flechas.append(
                Flecha(
                    origen=casilla_origen,
                    destino=casilla_destino,
                    sentido="directo",
                    fuente="auto",
                )
            )

        return flechas
    except Exception:
        # La detección automática es best-effort: ante cualquier fallo, no se
        # inventan flechas y se deja que el usuario las indique con --flecha.
        return []


# ---------------------------------------------------------------------------
# Combinación de flechas automáticas y manuales
# ---------------------------------------------------------------------------

def combinar_flechas(
    automaticas: List[Flecha],
    manuales: List[Flecha],
) -> List[Flecha]:
    """Combina flechas automáticas y manuales dando prioridad a las manuales.

    Parte de las flechas ``automaticas`` (conservando su orden) y, por cada
    flecha ``manual``:

    - Si coincide en ``(origen, destino)`` con una automática, sustituye esa
      entrada por la manual (se conserva una sola entrada, con ``fuente="manual"``
      y respetando la posición original de la automática sustituida).
    - Si no coincide con ninguna automática, se añade al final (respetando el
      orden de las manuales entre sí y evitando duplicados manuales).

    El resultado es determinista y con orden estable (Requisito 7.1, combinación
    descrita en el diseño).

    :param automaticas: flechas detectadas automáticamente (``fuente="auto"``).
    :param manuales: flechas manuales ya parseadas (``fuente="manual"``).
    :returns: lista combinada de :class:`Flecha`.
    """
    # Copia de trabajo para poder sustituir en su sitio las coincidentes.
    combinadas: List[Flecha] = list(automaticas)

    # Índice de posición por (origen, destino) para localizar coincidencias.
    indice_por_clave: Dict[Tuple[str, str], int] = {}
    for posicion, flecha in enumerate(combinadas):
        indice_por_clave[(flecha.origen, flecha.destino)] = posicion

    for manual in manuales:
        clave = (manual.origen, manual.destino)
        if clave in indice_por_clave:
            # Sustituir la automática coincidente conservando su posición.
            combinadas[indice_por_clave[clave]] = manual
        else:
            # Añadir la manual nueva al final y registrar su posición.
            indice_por_clave[clave] = len(combinadas)
            combinadas.append(manual)

    return combinadas


# ---------------------------------------------------------------------------
# Función de conveniencia: detección + parseo + combinación
# ---------------------------------------------------------------------------

def obtener_flechas(
    area: Optional[np.ndarray],
    celdas: Optional[Dict[Tuple[str, int], Casilla]],
    lista_flechas_manuales: Optional[List[str]],
) -> Tuple[List[Flecha], List[str]]:
    """Obtiene las flechas combinadas y los avisos en un solo paso.

    Hace la detección automática best-effort (si hay imagen y rejilla), parsea
    las flechas manuales de ``--flecha`` y combina ambas dando prioridad a las
    manuales. Devuelve una tupla ``(flechas, avisos)`` donde ``avisos`` recoge,
    en español, cualquier flecha manual descartada por casilla no válida, sin
    inventar casillas (Requisito 7.5).

    :param area: recorte del tablero enderezado, o ``None`` para omitir la
        detección automática (por ejemplo si solo se quieren flechas manuales).
    :param celdas: rejilla ``{(columna, fila): Casilla}`` de ``dividir_en_64``, o
        ``None`` para omitir la detección automática.
    :param lista_flechas_manuales: lista repetible de cadenas ``--flecha``.
    :returns: ``(flechas_combinadas, avisos)``.
    """
    if area is not None and celdas:
        automaticas = detectar_flechas_auto(area, celdas)
    else:
        automaticas = []

    manuales, avisos = parsear_flechas_manuales(lista_flechas_manuales)
    combinadas = combinar_flechas(automaticas, manuales)
    return combinadas, avisos


__all__ = [
    "parsear_flecha_manual",
    "parsear_flechas_manuales",
    "detectar_flechas_auto",
    "combinar_flechas",
    "obtener_flechas",
]
