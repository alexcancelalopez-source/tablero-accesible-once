"""Transformación de rotación 180° del Modulo_Orientacion.

Este módulo implementa la parte de *lógica pura* de la corrección de
orientación: la rotación de 180 grados de las coordenadas del tablero, que
se aplica cuando el tablero está visto desde el lado de las negras para
dejarlo en orientación estándar (columna ``a`` a la izquierda y fila ``1``
en el lado de las blancas, Requisitos 3.2, 3.3, 3.4).

La rotación de 180° transforma cada coordenada así::

    (columna, fila) -> (columna_inversa, 9 - fila)

donde ``columna_inversa`` intercambia ``a`` con ``h``, ``b`` con ``g``,
``c`` con ``f`` y ``d`` con ``e`` (índice ``i`` -> ``7 - i`` sobre
:data:`modulos.posicion.COLUMNAS`). El contenido de cada casilla (tipo,
color, confianza de las piezas; color de las resaltadas; sentido y fuente
de las flechas; motivo de las dudosas) se conserva; solo cambian las
coordenadas. Aplicar la rotación dos veces devuelve la posición original.

La detección de la orientación y el caso indeterminado se implementan en la
tarea 7.3; aquí solo vive la transformación pura de coordenadas.

Todos los nombres, comentarios y mensajes van en español, según las reglas
del proyecto (regla 15).
"""

from __future__ import annotations

import copy

from modulos.posicion import (
    COLUMNAS,
    Dudosa,
    Flecha,
    Orientacion,
    Pieza,
    Posicion,
    Resaltada,
    Validacion,
    es_columna_valida,
    es_fila_valida,
    separar_casilla,
    unir_casilla,
)


def rotar_columna(columna: str) -> str:
    """Devuelve la columna inversa por rotación de 180°.

    Intercambia ``a`` con ``h``, ``b`` con ``g``, ``c`` con ``f`` y ``d``
    con ``e``, usando el índice inverso ``7 - i`` sobre
    :data:`modulos.posicion.COLUMNAS`.

    Lanza :class:`ValueError` en español si ``columna`` no es válida, para no
    generar nunca columnas fuera del tablero.
    """
    if not es_columna_valida(columna):
        raise ValueError(
            f"Columna no válida: {columna!r}. Debe estar entre 'a' y 'h'."
        )
    indice = COLUMNAS.index(columna)
    return COLUMNAS[7 - indice]


def rotar_coordenadas_180(columna: str, fila: int) -> tuple[str, int]:
    """Rota una coordenada ``(columna, fila)`` 180 grados.

    Devuelve ``(columna_inversa, 9 - fila)``, conservando así la casilla
    equivalente vista desde el lado contrario del tablero. Por ejemplo,
    ``rotar_coordenadas_180("a", 1)`` devuelve ``("h", 8)``.

    Lanza :class:`ValueError` en español si la columna o la fila no son
    válidas, para no generar nunca casillas fuera del tablero.
    """
    if not es_fila_valida(fila):
        raise ValueError(f"Fila no válida: {fila!r}. Debe estar entre 1 y 8.")
    # rotar_columna valida la columna y lanza ValueError si no es válida.
    return rotar_columna(columna), 9 - fila


def _rotar_casilla(casilla: str) -> str:
    """Rota 180° un token de casilla, p. ej. ``"a1"`` -> ``"h8"``."""
    columna, fila = separar_casilla(casilla)
    columna_rotada, fila_rotada = rotar_coordenadas_180(columna, fila)
    return unir_casilla(columna_rotada, fila_rotada)


def rotar_posicion_180(posicion: Posicion) -> Posicion:
    """Devuelve una nueva :class:`Posicion` con las coordenadas rotadas 180°.

    Cada pieza, casilla resaltada, flecha (origen y destino) y casilla
    dudosa se traslada a su coordenada equivalente vista desde el lado
    contrario del tablero, conservando todo el contenido no espacial (tipo,
    color y confianza de las piezas; color del resaltado; sentido y fuente
    de las flechas; motivo de las dudosas).

    Los metadatos de orientación y de validación no se rotan: se copian tal
    cual, ya que no representan coordenadas del tablero.

    La posición original no se modifica; se devuelve una posición nueva.
    """
    piezas_rotadas = []
    for pieza in posicion.piezas:
        columna_rotada, fila_rotada = rotar_coordenadas_180(pieza.columna, pieza.fila)
        piezas_rotadas.append(
            Pieza(
                tipo=pieza.tipo,
                color=pieza.color,
                columna=columna_rotada,
                fila=fila_rotada,
                confianza=pieza.confianza,
            )
        )

    resaltadas_rotadas = [
        Resaltada(casilla=_rotar_casilla(resaltada.casilla), color=resaltada.color)
        for resaltada in posicion.resaltadas
    ]

    flechas_rotadas = [
        Flecha(
            origen=_rotar_casilla(flecha.origen),
            destino=_rotar_casilla(flecha.destino),
            sentido=flecha.sentido,
            fuente=flecha.fuente,
        )
        for flecha in posicion.flechas
    ]

    dudosas_rotadas = [
        Dudosa(casilla=_rotar_casilla(dudosa.casilla), motivo=dudosa.motivo)
        for dudosa in posicion.dudosas
    ]

    return Posicion(
        orientacion=posicion.orientacion,
        piezas=piezas_rotadas,
        resaltadas=resaltadas_rotadas,
        flechas=flechas_rotadas,
        dudosas=dudosas_rotadas,
        validacion=posicion.validacion,
    )


# ---------------------------------------------------------------------------
# Detección de orientación por heurística y caso indeterminado (tarea 7.3)
# ---------------------------------------------------------------------------
#
# Estrategia en dos niveles descrita en el diseño (Modulo_Orientacion):
#
#   1. Lectura de etiquetas de coordenadas (preferente): necesita la imagen y
#      se integra en las tareas de visión por computador; NO forma parte de
#      esta lógica pura.
#   2. Heurística por posición de reyes y peones (respaldo): opera solo sobre
#      la :class:`Posicion` ya reconocida y es lo que se implementa aquí.
#
# Cuando ni las etiquetas ni la heurística superan un mínimo de confianza
# (tablero casi vacío o simétrico) se asume la orientación estándar y se marca
# el caso como indeterminado (Requisitos 3.5, 3.6).

# Umbral mínimo de coherencia que debe alcanzar la mejor hipótesis para
# aceptarla como una detección heurística fiable. Se fija por encima de la
# contribución de los dos reyes solos (2.0 cada uno) para que un tablero casi
# vacío —por ejemplo únicamente los dos reyes en e1 y e8— no se dé por bien
# orientado: la evidencia es demasiado débil y el caso se considera
# indeterminado. Una posición realista con peones supera holgadamente este
# umbral (cada peón bien colocado aporta 1.0).
_UMBRAL_CONFIANZA_HEURISTICA = 5.0

# Diferencia mínima de coherencia entre las dos hipótesis (estándar vs girada)
# para poder decantarse por una. Si ambas puntúan casi igual (posición
# simétrica) el caso se considera indeterminado.
_MARGEN_MINIMO_HIPOTESIS = 1.0

# Mensaje de aviso en español para el caso indeterminado (regla 15). No usa
# símbolos que el lector de pantalla lea mal (regla 9).
_AVISO_ORIENTACION_INDETERMINADA = (
    "No se pudo determinar la orientación del tablero; se asume la orientación "
    "estándar (blancas abajo, columna a a la izquierda)."
)


def _puntuar_pieza_estandar(pieza: Pieza) -> float:
    """Puntúa cuánto encaja una pieza con la orientación estándar.

    En orientación estándar las blancas están abajo (filas bajas) y las negras
    arriba (filas altas). Se puntúan reyes y peones, que son los indicadores
    más fiables de qué lado del tablero ocupa cada bando:

    - Rey blanco en filas traseras bajas (1-2) suma; en filas altas resta.
    - Rey negro en filas traseras altas (7-8) suma; en filas bajas resta.
    - Peón blanco en filas bajas (2-4) suma; peón negro en filas altas (5-7)
      suma; los peones colocados en el lado contrario restan.

    Una pieza neutra o poco informativa aporta ``0.0``.
    """
    es_blanca = pieza.color == "blanco"
    fila = pieza.fila

    if pieza.tipo == "Rey":
        # El rey suele estar en la fila trasera de su bando.
        if es_blanca:
            return 2.0 if fila <= 2 else (-2.0 if fila >= 7 else 0.0)
        return 2.0 if fila >= 7 else (-2.0 if fila <= 2 else 0.0)

    if pieza.tipo == "Peon":
        # Los peones nunca están en fila 1 u 8; tienden al centro-bajo de su
        # lado (blancas hacia filas bajas, negras hacia filas altas).
        if es_blanca:
            return 1.0 if fila <= 4 else -1.0
        return 1.0 if fila >= 5 else -1.0

    # Otras piezas (Dama, Torre, Alfil, Caballo) no aportan a la heurística.
    return 0.0


def puntuar_orientacion(posicion: Posicion) -> float:
    """Puntúa la coherencia de ``posicion`` con la orientación estándar.

    Suma la contribución de cada pieza según :func:`_puntuar_pieza_estandar`.
    Una puntuación alta indica que la posición, tal cual está, es coherente
    con la orientación estándar (blancas abajo); una puntuación baja o negativa
    sugiere que en realidad está girada 180°.

    Solo se consideran las coordenadas actuales de las piezas; no se modifica
    la posición.
    """
    return sum(_puntuar_pieza_estandar(pieza) for pieza in posicion.piezas)


def detectar_orientacion(posicion: Posicion) -> tuple[str, str]:
    """Detecta la orientación de ``posicion`` por heurística de piezas.

    Devuelve una tupla ``(estado, metodo)`` donde:

    - ``estado`` es ``"estandar"``, ``"girada"`` o ``"asumida"``.
    - ``metodo`` es ``"heuristica"`` (detección fiable) o ``"indeterminada"``
      (caso ambiguo en el que se asume la orientación estándar).

    Se comparan dos hipótesis:

    - La posición **tal cual** es estándar: puntuación ``p_estandar``.
    - La posición está **girada** 180°: se puntúa la versión rotada, cuya
      coherencia con la orientación estándar mide lo bien que encajaría tras
      corregirla (``p_girada``).

    Si la mejor puntuación no alcanza :data:`_UMBRAL_CONFIANZA_HEURISTICA`, o si
    ambas hipótesis quedan a menos de :data:`_MARGEN_MINIMO_HIPOTESIS` (posición
    simétrica o casi vacía), el caso es indeterminado y se devuelve
    ``("asumida", "indeterminada")``. En otro caso se elige la hipótesis con
    mayor coherencia: ``("estandar", "heuristica")`` si la posición ya está bien
    orientada, o ``("girada", "heuristica")`` si conviene rotarla.
    """
    puntuacion_estandar = puntuar_orientacion(posicion)
    puntuacion_girada = puntuar_orientacion(rotar_posicion_180(posicion))

    mejor_puntuacion = max(puntuacion_estandar, puntuacion_girada)
    diferencia = abs(puntuacion_estandar - puntuacion_girada)

    # Evidencia insuficiente (tablero casi vacío) o hipótesis empatadas
    # (posición simétrica): se asume la orientación estándar.
    if mejor_puntuacion < _UMBRAL_CONFIANZA_HEURISTICA or diferencia < _MARGEN_MINIMO_HIPOTESIS:
        return "asumida", "indeterminada"

    if puntuacion_estandar >= puntuacion_girada:
        return "estandar", "heuristica"
    return "girada", "heuristica"


def corregir_orientacion(posicion: Posicion) -> Posicion:
    """Deja ``posicion`` en orientación estándar y anota cómo se detectó.

    Aplica la estrategia de :func:`detectar_orientacion` y actúa según el
    estado resultante (Requisitos 3.1, 3.5, 3.6):

    - ``"estandar"``: la posición ya está bien orientada; se devuelve sin rotar
      con ``orientacion.detectada = "estandar"`` y ``metodo = "heuristica"``.
    - ``"girada"``: se rota 180° para dejarla estándar y se anota
      ``orientacion.detectada = "girada"`` y ``metodo = "heuristica"``.
    - ``"asumida"``: caso indeterminado; se asume la orientación estándar (no se
      rota), se anota ``orientacion.detectada = "asumida"`` y
      ``metodo = "indeterminada"`` y se añade un aviso en español a
      ``validacion.avisos``.

    En todos los casos la posición devuelta está en orientación estándar
    (columna ``a`` a la izquierda, fila ``1`` en el lado de las blancas), de
    modo que el Modulo_Salidas siempre recibe coordenadas correctas. La
    posición original no se modifica; se devuelve una posición nueva.
    """
    estado, metodo = detectar_orientacion(posicion)

    if estado == "girada":
        # Rotar 180° deja la posición en orientación estándar conservando el
        # contenido de cada casilla.
        resultado = rotar_posicion_180(posicion)
    else:
        # "estandar" y "asumida" se entregan sin rotar (en el caso asumido se
        # asume la orientación estándar por defecto). Se trabaja sobre una copia
        # para no modificar la posición original.
        resultado = copy.deepcopy(posicion)

    resultado.orientacion = Orientacion(detectada=estado, metodo=metodo)

    if estado == "asumida":
        avisos = list(resultado.validacion.avisos)
        avisos.append(_AVISO_ORIENTACION_INDETERMINADA)
        resultado.validacion = Validacion(
            valida=resultado.validacion.valida,
            avisos=avisos,
        )

    return resultado
