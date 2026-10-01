"""Test basado en propiedades de consistencia entre braille y audio.

Verifica la propiedad universal de que ambas salidas del
:mod:`modulos.salidas` (braille y audio) describen exactamente el mismo
conjunto de piezas ``(tipo, color, casilla)`` para toda posición válida,
usando Hypothesis con un mínimo de 100 iteraciones.

Todos los nombres, comentarios y mensajes van en español (regla 15).

Requisitos: 5.5, 8.2
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from modulos.posicion import COLORES_PIEZA, COLUMNAS, FILAS, TIPOS_PIEZA, Pieza, Posicion
from modulos.salidas.audio import ETIQUETA_BANDO, NOMBRE_TIPO, generar_audio
from modulos.salidas.braille import (
    BRAILLE_A_FILA,
    ETIQUETA_BANDO as ETIQUETA_BANDO_BRAILLE,
    LETRA_A_PIEZA,
    generar_braille,
)

# ---------------------------------------------------------------------------
# Tablas auxiliares para decodificar las salidas
# ---------------------------------------------------------------------------

# Etiqueta de bando braille ("Blancas:"/"Negras:") → color de pieza.
_ETIQUETA_A_COLOR = {etiqueta: color for color, etiqueta in ETIQUETA_BANDO_BRAILLE.items()}

# Nombre de tipo en español (singular o plural) → tipo interno. Sirve para
# decodificar las frases de la salida de audio, p. ej. "Torres" → "Torre".
_NOMBRE_A_TIPO = {}
for _tipo, (_singular, _plural) in NOMBRE_TIPO.items():
    _NOMBRE_A_TIPO[_singular] = _tipo
    _NOMBRE_A_TIPO[_plural] = _tipo


# ---------------------------------------------------------------------------
# Estrategia: posiciones con casilla única, sin resaltadas ni flechas
# ---------------------------------------------------------------------------

_CASILLAS = [(c, f) for f in FILAS for c in COLUMNAS]


@st.composite
def _posiciones_piezas_unicas(draw):
    """Genera una :class:`Posicion` con a lo sumo una pieza por casilla.

    No incluye resaltadas ni flechas, de modo que la salida braille y la de
    audio contienen únicamente los bloques ``Blancas:`` y ``Negras:`` y el
    conjunto de piezas queda bien definido (sin casillas repetidas).
    """
    n = draw(st.integers(min_value=0, max_value=12))
    casillas = draw(
        st.lists(st.sampled_from(_CASILLAS), min_size=n, max_size=n, unique=True)
    )
    piezas = []
    for columna, fila in casillas:
        tipo = draw(st.sampled_from(TIPOS_PIEZA))
        color = draw(st.sampled_from(COLORES_PIEZA))
        piezas.append(Pieza(tipo=tipo, color=color, columna=columna, fila=fila))
    return Posicion(piezas=piezas)


# ---------------------------------------------------------------------------
# Decodificación del conjunto de piezas de cada salida
# ---------------------------------------------------------------------------

def _conjunto_esperado(posicion):
    """Conjunto ``(tipo, color, casilla)`` construido desde ``posicion.piezas``.

    La casilla se nombra en el mismo formato que la salida de audio (columna
    en mayúscula + fila, p. ej. ``"E1"``) para poder comparar ambos conjuntos.
    """
    return {
        (pieza.tipo, pieza.color, f"{pieza.columna.upper()}{pieza.fila}")
        for pieza in posicion.piezas
    }


def _conjunto_desde_braille(salida):
    """Extrae el conjunto ``(tipo, color, casilla)`` de la salida braille.

    Recorre las líneas ``Blancas:`` y ``Negras:``; cada token de pieza es
    ``Letra + columna + fila_braille``. Decodifica la letra de pieza con
    :data:`LETRA_A_PIEZA`, la columna directamente y la fila braille con
    :data:`BRAILLE_A_FILA`. La casilla se nombra como en audio (columna en
    mayúscula + fila) para comparar ambos conjuntos.
    """
    conjunto = set()
    for linea in salida.split("\n"):
        etiqueta = next(
            (e for e in _ETIQUETA_A_COLOR if linea.startswith(e)), None
        )
        if etiqueta is None:
            continue
        color = _ETIQUETA_A_COLOR[etiqueta]
        resto = linea[len(etiqueta):].strip()
        if not resto:
            continue
        for token in resto.split(" "):
            # Un token que empieza por letra de pieza mayúscula (R, D, T, C, A)
            # es ``Letra + columna + fila_braille``. Un token que empieza por
            # columna minúscula (a–h) es un Peón sin letra: ``columna +
            # fila_braille`` (según el Documento técnico B8 de la ONCE).
            if token[0] in LETRA_A_PIEZA:
                tipo = LETRA_A_PIEZA[token[0]]
                columna = token[1]
                fila = BRAILLE_A_FILA[token[2]]
            else:
                tipo = "Peon"
                columna = token[0]
                fila = BRAILLE_A_FILA[token[1]]
            conjunto.add((tipo, color, f"{columna.upper()}{fila}"))
    return conjunto


def _conjunto_desde_audio(salida):
    """Extrae el conjunto ``(tipo, color, casilla)`` de la salida de audio.

    Recorre los bloques ``Blancas:`` y ``Negras:``. Cada bloque enumera las
    piezas por tipo con frases del tipo ``"Torres en A1 y H1"``. Se analiza
    palabra a palabra: cuando aparece un nombre de tipo (singular o plural de
    :data:`NOMBRE_TIPO`) se fija el tipo en curso; cada nombre de casilla
    (columna en mayúscula + fila, p. ej. ``A1``) se asigna a ese tipo y al
    color del bando. Un bando sin piezas escribe ``sin piezas``.
    """
    etiqueta_a_color = {etiqueta: color for color, etiqueta in ETIQUETA_BANDO.items()}
    conjunto = set()
    for linea in salida.split("\n"):
        etiqueta = next((e for e in etiqueta_a_color if linea.startswith(e)), None)
        if etiqueta is None:
            continue
        color = etiqueta_a_color[etiqueta]
        cuerpo = linea[len(etiqueta):].strip().rstrip(".")
        if not cuerpo or cuerpo == "sin piezas":
            continue
        # Se sustituyen las comas por espacios y se separa por " y " para
        # obtener las palabras sueltas: nombres de tipo, "en" y casillas.
        palabras = cuerpo.replace(",", " ").replace(" y ", " ").split()
        tipo_actual = None
        for palabra in palabras:
            if palabra in _NOMBRE_A_TIPO:
                tipo_actual = _NOMBRE_A_TIPO[palabra]
            elif palabra == "en":
                continue
            else:
                # Nombre de casilla; se asigna al tipo en curso y al color.
                conjunto.add((tipo_actual, color, palabra))
    return conjunto


# Feature: tablero-accesible-once, Property 7: Consistencia entre braille y audio en el conjunto de piezas
# Para toda posición válida, el conjunto de piezas (tipo, color, casilla)
# descrito en la salida braille es igual al conjunto descrito en la salida de
# audio, y ambos coinciden con las piezas de la posición.
# Validates: Requirements 5.5, 8.2
@settings(max_examples=100)
@given(posicion=_posiciones_piezas_unicas())
def test_propiedad_consistencia_braille_audio(posicion):
    """El conjunto de piezas de braille y de audio coincide entre sí y con la posición."""
    esperado = _conjunto_esperado(posicion)
    conjunto_braille = _conjunto_desde_braille(generar_braille(posicion))
    conjunto_audio = _conjunto_desde_audio(generar_audio(posicion))

    assert conjunto_braille == esperado
    assert conjunto_audio == esperado
    assert conjunto_braille == conjunto_audio
