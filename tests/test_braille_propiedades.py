"""Tests basados en propiedades de la notación braille pura.

Verifican propiedades universales de la codificación y decodificación de
casillas del submódulo :mod:`modulos.salidas.braille` usando Hypothesis, con
un mínimo de 100 iteraciones por propiedad.

Todos los nombres, comentarios y mensajes van en español (regla 15).

Requisitos: 5.1, 5.2
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from modulos.posicion import (
    COLORES_PIEZA,
    COLUMNAS,
    FILAS,
    TIPOS_PIEZA,
    Pieza,
    Posicion,
)
from modulos.salidas.braille import (
    ORDEN_TIPOS,
    PIEZA_A_LETRA,
    codificar_casilla,
    decodificar_casilla,
)


# Feature: tablero-accesible-once, Property 1: Round-trip de coordenadas a braille
# Para toda columna c en a-h y fila f en 1-8, codificar (c, f) al token braille
# de casilla y volver a decodificarlo produce exactamente la misma (c, f).
# Validates: Requirements 5.1, 5.2
@settings(max_examples=100)
@given(
    columna=st.sampled_from(COLUMNAS),
    fila=st.sampled_from(FILAS),
)
def test_propiedad_round_trip_coordenadas_braille(columna, fila):
    """decodificar_casilla(codificar_casilla(c, f)) == (c, f) para toda casilla."""
    token = codificar_casilla(columna, fila)
    assert decodificar_casilla(token) == (columna, fila)


# Estrategias auxiliares para generar posiciones aleatorias
# ---------------------------------------------------------------------------
# Genera piezas con casilla única (a lo sumo una pieza por casilla) para
# respetar el contrato del modelo de datos, con tipo y color aleatorios.

_CASILLAS = [(c, f) for f in FILAS for c in COLUMNAS]


@st.composite
def _piezas_unicas(draw):
    """Genera una lista de piezas sin repetir casilla, con tipo/color al azar."""
    from modulos.posicion import COLORES_PIEZA, TIPOS_PIEZA, Pieza

    n = draw(st.integers(min_value=0, max_value=12))
    casillas = draw(
        st.lists(
            st.sampled_from(_CASILLAS),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    piezas = []
    for columna, fila in casillas:
        tipo = draw(st.sampled_from(TIPOS_PIEZA))
        color = draw(st.sampled_from(COLORES_PIEZA))
        piezas.append(Pieza(tipo=tipo, color=color, columna=columna, fila=fila))
    return piezas


@st.composite
def _posiciones(draw):
    """Genera una :class:`Posicion` con piezas aleatorias y sin flechas ni resaltadas."""
    from modulos.posicion import Posicion

    return Posicion(piezas=draw(_piezas_unicas()))


# Feature: tablero-accesible-once, Property 3: Tipos ausentes no generan tokens ni espacios sobrantes
# Para toda posición y todo bando, si el bando no tiene piezas de un tipo, la
# línea de ese bando no contiene ningún token de ese tipo ni separadores
# adicionales por él: los tokens se separan por un único espacio, sin espacios
# dobles, iniciales ni finales, y su número coincide exactamente con el número
# de piezas de ese bando.
# Validates: Requirements 5.9
@settings(max_examples=100)
@given(posicion=_posiciones())
def test_propiedad_tipos_ausentes_sin_tokens_ni_espacios(posicion):
    """Los tipos ausentes no aportan tokens ni espacios sobrantes por bando."""
    from modulos.salidas.braille import PIEZA_A_LETRA, generar_braille

    salida = generar_braille(posicion)
    lineas = salida.split("\n")
    # Sin flechas ni resaltadas, las dos primeras líneas son los bandos.
    linea_por_etiqueta = {
        "Blancas:": lineas[0],
        "Negras:": lineas[1],
    }

    etiqueta_por_color = {"blanco": "Blancas:", "negro": "Negras:"}

    for color, etiqueta in etiqueta_por_color.items():
        linea = linea_por_etiqueta[etiqueta]
        # La línea siempre empieza por su etiqueta de bando.
        assert linea.startswith(etiqueta)

        # Piezas realmente presentes de este color y tipos presentes/ausentes.
        piezas_color = [p for p in posicion.piezas if p.color == color]
        tipos_presentes = {p.tipo for p in piezas_color}
        tipos_ausentes = set(PIEZA_A_LETRA) - tipos_presentes

        # Parte posterior a la etiqueta, sin el espacio de separación inicial.
        resto = linea[len(etiqueta):]

        if not piezas_color:
            # Sin piezas: la línea es exactamente la etiqueta, sin espacios.
            assert linea == etiqueta
            assert resto == ""
            continue

        # Con piezas: exactamente un espacio tras la etiqueta.
        assert resto.startswith(" ")
        cuerpo = resto[1:]

        # Ni espacios dobles, ni inicial ni final en el cuerpo de tokens.
        assert "  " not in cuerpo
        assert not cuerpo.startswith(" ")
        assert not cuerpo.endswith(" ")

        tokens = cuerpo.split(" ")
        # El número de tokens coincide con el número de piezas del bando: los
        # tipos ausentes no aportan tokens ni separadores adicionales.
        assert len(tokens) == len(piezas_color)

        # El tipo de cada token pertenece a los tipos presentes y ninguno es de
        # un tipo ausente. El peón no lleva letra inicial (empieza por columna
        # a–h); el resto de piezas empiezan por su letra (R, D, T, C, A).
        letras_no_peon = {
            letra for tipo, letra in PIEZA_A_LETRA.items() if tipo != "Peon"
        }
        letra_a_tipo = {letra: tipo for tipo, letra in PIEZA_A_LETRA.items()}
        for token in tokens:
            if token[0] in letras_no_peon:
                tipo_token = letra_a_tipo[token[0]]
            else:
                tipo_token = "Peon"
            assert tipo_token in tipos_presentes
            assert tipo_token not in tipos_ausentes


# ---------------------------------------------------------------------------
# Generadores de posiciones sintéticas para la Property 2
# ---------------------------------------------------------------------------
#
# Se generan piezas aleatorias directamente sobre el formato intermedio, sin
# depender de imágenes. Para el determinismo y el orden no se necesitan
# resaltadas ni flechas, así que las posiciones se construyen solo con piezas.
# Se permiten piezas duplicadas en la misma casilla: el determinismo y el
# orden de la salida braille deben cumplirse igualmente.

# Letra de pieza → tipo, para decodificar el primer carácter de cada token.
LETRA_A_TIPO = {letra: tipo for tipo, letra in PIEZA_A_LETRA.items()}

# Letras de pieza que SÍ aparecen como primer carácter del token (todas menos
# el peón, que se anota sin letra: empieza directamente por su columna a–h).
LETRAS_PIEZA_CON_LETRA = {
    letra for tipo, letra in PIEZA_A_LETRA.items() if tipo != "Peon"
}


def _tipo_y_columna_de_token(token: str) -> tuple[str, str]:
    """Deduce el ``(tipo, columna)`` de un token braille de pieza.

    Si el primer carácter es una letra de pieza mayúscula (R, D, T, C, A), el
    token es ``Letra + columna + fila_braille`` y la columna es el segundo
    carácter. Si el primer carácter es una columna minúscula ``a``–``h``, el
    token es un Peón sin letra (``columna + fila_braille``) y la columna es el
    primer carácter.
    """
    if token[0] in LETRAS_PIEZA_CON_LETRA:
        return LETRA_A_TIPO[token[0]], token[1]
    # Peón sin letra de pieza: el primer carácter es la columna.
    return "Peon", token[0]


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


def _posicion():
    """Estrategia que genera una :class:`Posicion` con piezas aleatorias."""
    return st.builds(
        Posicion,
        piezas=st.lists(_pieza(), max_size=20),
    )


def _tokens_de_linea(texto: str, etiqueta: str) -> list[str]:
    """Extrae los tokens de pieza de la línea ``etiqueta`` (p. ej. "Blancas:").

    Devuelve la lista de tokens (``Letra+columna+fila_braille``) sin la
    etiqueta del bando; lista vacía si la línea no tiene piezas.
    """
    for linea in texto.split("\n"):
        if linea.startswith(etiqueta):
            resto = linea[len(etiqueta):].strip()
            return resto.split() if resto else []
    return []


def _es_orden_correcto(tokens: list[str]) -> bool:
    """Comprueba que ``tokens`` respeta el orden por tipo y por columna.

    La secuencia de tipos debe ser no decreciente según :data:`ORDEN_TIPOS`
    (Rey, Dama, Torre, Caballo, Alfil, Peones) y, dentro del mismo tipo, las
    columnas deben ser no decrecientes de ``a`` hacia ``h`` (Requisitos 5.7,
    5.8). Cada token es ``Letra + columna + fila_braille`` salvo el peón, que
    se anota sin letra (``columna + fila_braille``); :func:`_tipo_y_columna_de_token`
    resuelve ambos casos.
    """
    clave_anterior = None
    for token in tokens:
        tipo, columna = _tipo_y_columna_de_token(token)
        indice_tipo = ORDEN_TIPOS.index(tipo)
        indice_columna = COLUMNAS.index(columna)
        clave = (indice_tipo, indice_columna)
        if clave_anterior is not None and clave < clave_anterior:
            return False
        clave_anterior = clave
    return True


# Feature: tablero-accesible-once, Property 2: Determinismo y orden de la salida braille
# Para toda posición válida, generar la salida braille dos veces produce el mismo
# texto, y en cada bando las piezas aparecen ordenadas por tipo en el orden Rey,
# Dama, Torre, Caballo, Alfil, Peones y, dentro de cada tipo, de columna a hacia h.
# Validates: Requirements 5.5, 5.6, 5.7, 5.8
@settings(max_examples=100)
@given(posicion=_posicion())
def test_propiedad_determinismo_y_orden_braille(posicion):
    """generar_braille es determinista y ordena cada bando por tipo y columna."""
    from modulos.salidas.braille import generar_braille

    # Determinismo: dos llamadas con la misma posición dan el mismo texto.
    salida = generar_braille(posicion)
    assert salida == generar_braille(posicion)

    # Orden: cada bando respeta el orden por tipo y, dentro del tipo, por columna.
    for etiqueta in ("Blancas:", "Negras:"):
        tokens = _tokens_de_linea(salida, etiqueta)
        assert _es_orden_correcto(tokens), (
            f"Orden incorrecto en la línea {etiqueta!r}: {tokens}"
        )
