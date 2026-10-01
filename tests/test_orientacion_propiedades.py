"""Tests basados en propiedades del Modulo_Orientacion (rotación 180°).

Verifica la Property 4 del diseño: aplicar la rotación de orientación de 180°
dos veces devuelve una posición idéntica a la original (mismas piezas en las
mismas casillas). Se prueba tanto sobre coordenadas sueltas
(:func:`rotar_coordenadas_180`) como sobre posiciones completas
(:func:`rotar_posicion_180`).

Se usa Hypothesis con un mínimo de 100 iteraciones por propiedad. Los
generadores construyen posiciones sintéticas sobre el formato intermedio, sin
depender de imágenes.

Todos los nombres, comentarios y mensajes van en español (regla 15).

Requisitos: 3.1, 3.2, 3.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from modulos.posicion import (
    COLORES_PIEZA,
    COLORES_RESALTADO,
    COLUMNAS,
    FILAS,
    FUENTES_FLECHA,
    MOTIVOS_DUDOSA,
    SENTIDOS_FLECHA,
    TIPOS_PIEZA,
    Dudosa,
    Flecha,
    Pieza,
    Posicion,
    Resaltada,
    unir_casilla,
)
from modulos.orientacion.orientacion import (
    corregir_orientacion,
    detectar_orientacion,
    rotar_coordenadas_180,
    rotar_posicion_180,
)


# ---------------------------------------------------------------------------
# Estrategias de generación (formato intermedio)
# ---------------------------------------------------------------------------

# Coordenadas básicas dentro del tablero.
columnas = st.sampled_from(COLUMNAS)
filas = st.sampled_from(FILAS)

# Token de casilla válido, p. ej. "e4", compuesto de columna + fila.
casillas = st.builds(unir_casilla, columnas, filas)


def _piezas():
    """Estrategia de piezas con tipo, color, coordenadas y confianza válidos."""
    return st.builds(
        Pieza,
        tipo=st.sampled_from(TIPOS_PIEZA),
        color=st.sampled_from(COLORES_PIEZA),
        columna=columnas,
        fila=filas,
        confianza=st.floats(min_value=0.0, max_value=1.0),
    )


def _resaltadas():
    """Estrategia de casillas resaltadas con color válido."""
    return st.builds(
        Resaltada,
        casilla=casillas,
        color=st.sampled_from(COLORES_RESALTADO),
    )


def _flechas():
    """Estrategia de flechas con origen, destino, sentido y fuente válidos."""
    return st.builds(
        Flecha,
        origen=casillas,
        destino=casillas,
        sentido=st.sampled_from(SENTIDOS_FLECHA),
        fuente=st.sampled_from(FUENTES_FLECHA),
    )


def _dudosas():
    """Estrategia de casillas dudosas con motivo válido."""
    return st.builds(
        Dudosa,
        casilla=casillas,
        motivo=st.sampled_from(MOTIVOS_DUDOSA),
    )


def _posiciones():
    """Estrategia de posiciones sintéticas para las propiedades de rotación.

    No se exige unicidad de casillas: la rotación actúa coordenada a coordenada,
    por lo que la presencia de casillas repetidas no afecta a la propiedad de
    identidad de la doble rotación.
    """
    return st.builds(
        Posicion,
        piezas=st.lists(_piezas(), max_size=16),
        resaltadas=st.lists(_resaltadas(), max_size=8),
        flechas=st.lists(_flechas(), max_size=4),
        dudosas=st.lists(_dudosas(), max_size=8),
    )


# ---------------------------------------------------------------------------
# Property 4: Girar 180° dos veces es la identidad
# ---------------------------------------------------------------------------

# Feature: tablero-accesible-once, Property 4
@settings(max_examples=100)
@given(_posiciones())
def test_doble_rotacion_posicion_es_identidad(posicion):
    """Rotar una posición 180° dos veces devuelve la posición original.

    Se compara mediante ``a_dict()`` para una igualdad estructural completa
    (mismas piezas, resaltadas, flechas y dudosas en las mismas casillas).

    Feature: tablero-accesible-once, Property 4
    Validates: Requirements 3.1, 3.2, 3.3
    """
    doble_rotada = rotar_posicion_180(rotar_posicion_180(posicion))
    assert doble_rotada.a_dict() == posicion.a_dict()


# Feature: tablero-accesible-once, Property 4
@settings(max_examples=100)
@given(columnas, filas)
def test_doble_rotacion_coordenadas_es_identidad(columna, fila):
    """Rotar una coordenada 180° dos veces devuelve la misma ``(columna, fila)``.

    Feature: tablero-accesible-once, Property 4
    Validates: Requirements 3.1, 3.2, 3.3
    """
    columna_1, fila_1 = rotar_coordenadas_180(columna, fila)
    columna_2, fila_2 = rotar_coordenadas_180(columna_1, fila_1)
    assert (columna_2, fila_2) == (columna, fila)


# ---------------------------------------------------------------------------
# Property 8: La orientación siempre queda resuelta a un estado definido
# ---------------------------------------------------------------------------

# Feature: tablero-accesible-once, Property 8
@settings(max_examples=100)
@given(_posiciones())
def test_orientacion_siempre_queda_resuelta(posicion):
    """La corrección de orientación siempre deja un estado definido y estándar.

    Para toda posición procesada, :func:`corregir_orientacion`:

    - Fija ``orientacion.detectada`` a exactamente uno de los tres valores
      estándar del contrato: ``"estandar"``, ``"girada"`` o ``"asumida"``
      (Requisitos 3.1, 3.5).
    - Anota un ``metodo`` coherente con el estado: ``"heuristica"`` para los
      casos resueltos por heurística (``estandar``/``girada``) e
      ``"indeterminada"`` para el caso asumido (Requisito 3.5).
    - Entrega una posición en orientación estándar. Como invariante robusto, la
      posición corregida no debe volver a detectarse como ``"girada"`` (no
      requiere otra rotación de 180°), lo que refleja que el Modulo_Salidas
      recibe siempre coordenadas correctas (Requisitos 3.4, 3.6).
    - No modifica la posición original; devuelve una posición nueva.

    Feature: tablero-accesible-once, Property 8
    Validates: Requirements 3.1, 3.4, 3.5, 3.6
    """
    # Instantánea de la posición original para comprobar que no se muta.
    original = posicion.a_dict()

    corregida = corregir_orientacion(posicion)

    # El estado detectado es exactamente uno de los tres valores del contrato.
    assert corregida.orientacion.detectada in {"estandar", "girada", "asumida"}

    # El método es coherente con el estado resuelto.
    if corregida.orientacion.detectada == "asumida":
        assert corregida.orientacion.metodo == "indeterminada"
    else:
        assert corregida.orientacion.metodo == "heuristica"

    # La posición entregada está en orientación estándar: no vuelve a
    # detectarse como girada (no necesitaría otra rotación de 180°).
    estado_corregido, _ = detectar_orientacion(corregida)
    assert estado_corregido != "girada"

    # La posición original no se ha modificado.
    assert posicion.a_dict() == original
