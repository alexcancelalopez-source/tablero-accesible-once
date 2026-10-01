"""Tests basados en propiedades de la salida de audio en español.

Verifican propiedades universales de la Salida_Audio generada por
:func:`modulos.salidas.audio.generar_audio` usando Hypothesis, con un mínimo
de 100 iteraciones por propiedad.

Todos los nombres, comentarios y mensajes van en español (regla 15).

Requisitos: 8.1, 8.7
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from modulos.posicion import (
    COLORES_PIEZA,
    COLORES_RESALTADO,
    COLUMNAS,
    FILAS,
    SENTIDOS_FLECHA,
    TIPOS_PIEZA,
    Flecha,
    Pieza,
    Posicion,
    Resaltada,
    unir_casilla,
)
from modulos.salidas.audio import CARACTERES_PERMITIDOS, generar_audio

# ---------------------------------------------------------------------------
# Conjuntos de caracteres prohibidos que deben quedar fuera de la salida audio
# ---------------------------------------------------------------------------
# El rango braille Unicode va de U+2800 a U+28FF; la salida audio nunca debe
# contener ninguno de estos puntos de código (Requisito 8.7).
_RANGO_BRAILLE = range(0x2800, 0x28FF + 1)

# Carácter ``¬`` (U+00AC) usado en las flechas de la salida braille; prohibido
# en audio por leerse mal en un lector de pantalla (Requisitos 8.7, 9).
_NEGACION = "\u00ac"

# Flechas Unicode habituales que un lector de pantalla leería mal; ninguna
# debe aparecer en la salida audio (Requisito 8.7).
_FLECHAS_UNICODE = "\u2192\u2190\u2194\u27f6\u27f5\u2191\u2193"


# ---------------------------------------------------------------------------
# Estrategias auxiliares para generar posiciones aleatorias
# ---------------------------------------------------------------------------
# Se generan posiciones ricas (piezas, resaltadas y flechas en ambos sentidos)
# para ejercitar todas las ramas de generar_audio. Como generar_audio aplica
# el filtro de caracteres permitidos, la salida debe cumplir la propiedad para
# cualquiera de estas entradas.

_CASILLAS = [unir_casilla(c, f) for f in FILAS for c in COLUMNAS]


def _pieza():
    """Estrategia que genera una :class:`Pieza` aleatoria válida."""
    return st.builds(
        Pieza,
        tipo=st.sampled_from(TIPOS_PIEZA),
        color=st.sampled_from(COLORES_PIEZA),
        columna=st.sampled_from(COLUMNAS),
        fila=st.sampled_from(FILAS),
        confianza=st.floats(min_value=0.0, max_value=1.0),
    )


def _resaltada():
    """Estrategia que genera una :class:`Resaltada` aleatoria válida."""
    return st.builds(
        Resaltada,
        casilla=st.sampled_from(_CASILLAS),
        color=st.sampled_from(COLORES_RESALTADO),
    )


def _flecha():
    """Estrategia que genera una :class:`Flecha` aleatoria (directo/inverso)."""
    return st.builds(
        Flecha,
        origen=st.sampled_from(_CASILLAS),
        destino=st.sampled_from(_CASILLAS),
        sentido=st.sampled_from(SENTIDOS_FLECHA),
        fuente=st.sampled_from(("auto", "manual")),
    )


def _posicion():
    """Estrategia que genera una :class:`Posicion` con piezas, resaltadas y flechas."""
    return st.builds(
        Posicion,
        piezas=st.lists(_pieza(), max_size=20),
        resaltadas=st.lists(_resaltada(), max_size=8),
        flechas=st.lists(_flecha(), max_size=6),
    )


# Feature: tablero-accesible-once, Property 6: La salida de audio solo usa el conjunto de caracteres permitido
# Para toda posición, la salida de audio contiene únicamente letras del
# alfabeto español (con tildes y ñ), dígitos 0-9, espacios y los signos , . :;
# en particular no contiene caracteres braille, ¬ ni flechas Unicode.
# Validates: Requirements 8.1, 8.7
@settings(max_examples=100)
@given(posicion=_posicion())
def test_propiedad_conjunto_caracteres_audio(posicion):
    """generar_audio produce solo caracteres del conjunto permitido."""
    salida = generar_audio(posicion)

    # Todo carácter de la salida pertenece al conjunto permitido.
    for caracter in salida:
        assert caracter in CARACTERES_PERMITIDOS, (
            f"Carácter no permitido en la salida audio: {caracter!r} "
            f"(U+{ord(caracter):04X})."
        )

    # Comprobaciones explícitas de que no aparecen caracteres prohibidos.
    for caracter in salida:
        assert ord(caracter) not in _RANGO_BRAILLE, (
            f"Carácter braille en la salida audio: {caracter!r} "
            f"(U+{ord(caracter):04X})."
        )

    # No contiene el carácter de negación ¬ ni flechas Unicode.
    assert _NEGACION not in salida
    for flecha_unicode in _FLECHAS_UNICODE:
        assert flecha_unicode not in salida
