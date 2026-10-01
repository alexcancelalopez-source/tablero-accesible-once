"""Tests de ejemplo de la notación braille de la ONCE (Tarea 4.4).

Casos concretos, no basados en propiedades, que fijan la equivalencia exacta
de la Notacion_Braille_ONCE en ejemplos representativos:

- Codificación de piezas y casillas (Rey en e1 → ``Re⠂``, etc.).
- La sección de casillas resaltadas delimitada por ``)`` y ``(``.
- El formato de las líneas de flecha (directo con ``¬⠒⠕¬`` e inverso con ``⠪⠒``).

Todos los nombres, comentarios y mensajes van en español, según las reglas
del proyecto (regla 15).

_Requirements: 5.3, 6.2, 7.2_
"""

from modulos.posicion import Flecha, Pieza, Posicion, Resaltada
from modulos.salidas.braille import (
    codificar_casilla,
    codificar_pieza,
    generar_braille,
)


# ---------------------------------------------------------------------------
# Codificación de piezas (Requisito 5.3)
# ---------------------------------------------------------------------------

def test_codificar_pieza_rey_en_e1():
    """Rey en e1 se codifica como ``Re⠂`` (letra + columna + fila braille)."""
    assert codificar_pieza("Rey", "e", 1) == "Re⠂"


def test_codificar_pieza_torre_en_a1():
    """Torre en a1 se codifica como ``Ta⠂``."""
    assert codificar_pieza("Torre", "a", 1) == "Ta⠂"


def test_peon_en_d5_sin_letra_p_en_la_salida():
    """El peón se anota SIN la letra ``P``: peón en d5 → ``d⠢`` (no ``Pd⠢``).

    Según el Documento técnico B8 de la ONCE (tableros 2 a 6 del documento de
    referencia), el peón omite la letra de pieza. Se comprueba sobre la salida
    completa de :func:`generar_braille`, ya que ``codificar_pieza`` se conserva
    intacta para el resto de piezas.
    """
    posicion = Posicion(
        piezas=[Pieza(tipo="Peon", color="blanco", columna="d", fila=5)],
    )

    salida = generar_braille(posicion)

    assert "d⠢" in salida
    assert "Pd⠢" not in salida


# ---------------------------------------------------------------------------
# Codificación de casillas (Requisitos 5.1, 5.2)
# ---------------------------------------------------------------------------

def test_codificar_casilla_valores_exactos():
    """Cada casilla usa el número de fila braille de posición baja correcto."""
    assert codificar_casilla("e", 1) == "e⠂"
    assert codificar_casilla("g", 3) == "g⠒"
    assert codificar_casilla("f", 3) == "f⠒"
    assert codificar_casilla("e", 5) == "e⠢"
    assert codificar_casilla("a", 1) == "a⠂"
    assert codificar_casilla("h", 8) == "h⠦"


# ---------------------------------------------------------------------------
# Sección de casillas resaltadas (Requisito 6.2)
# ---------------------------------------------------------------------------

def test_seccion_resaltadas_amarillo_g3():
    """La salida incluye la sección resaltada entre ``)`` y ``(``.

    Debe delimitarse con ``)`` y ``(``, nombrar el color ``amarillo`` y
    contener el token braille de la casilla g3 (``g⠒``).
    """
    posicion = Posicion(
        piezas=[Pieza(tipo="Rey", color="blanco", columna="e", fila=1)],
        resaltadas=[Resaltada(casilla="g3", color="amarillo")],
    )

    salida = generar_braille(posicion)

    # El token de la pieza también debe aparecer en la línea de blancas.
    assert "Re⠂" in salida
    # Delimitadores de la sección resaltada.
    assert ")" in salida
    assert "(" in salida
    # Color y casilla resaltada en braille.
    assert "amarillo" in salida
    assert "g⠒" in salida


# ---------------------------------------------------------------------------
# Formato de las líneas de flecha (Requisito 7.2)
# ---------------------------------------------------------------------------

def test_flecha_directa_f3_e5():
    """Una flecha directa f3→e5 usa la marca ``¬⠒⠕¬`` con los tokens braille."""
    posicion = Posicion(
        flechas=[Flecha(origen="f3", destino="e5", sentido="directo", fuente="manual")],
    )

    salida = generar_braille(posicion)

    # Marca de sentido directo y línea completa esperada.
    assert "¬⠒⠕¬" in salida
    assert "f⠒¬⠒⠕¬e⠢" in salida


def test_flecha_inversa_e5_f3():
    """Una flecha inversa e5→f3 usa la marca ``⠪⠒``."""
    posicion = Posicion(
        flechas=[Flecha(origen="e5", destino="f3", sentido="inverso", fuente="manual")],
    )

    salida = generar_braille(posicion)

    assert "⠪⠒" in salida
    assert "e⠢¬⠪⠒¬f⠒" in salida


# ---------------------------------------------------------------------------
# Bloque de resaltadas con flechas dentro (Caso A del documento, tablero 5)
# ---------------------------------------------------------------------------

def test_resaltadas_con_flechas_dentro_del_bloque():
    """Caso A: las flechas van DENTRO del bloque y ``(`` cierra la última flecha.

    Reproduce el patrón del tablero 5 del documento de referencia: la línea de
    resaltadas abre con ``)`` y NO se cierra; cada flecha ocupa su propia línea
    dentro del bloque; el paréntesis de cierre ``(`` se pega al final de la
    ÚLTIMA línea de flecha (nunca en la línea de resaltadas).
    """
    posicion = Posicion(
        resaltadas=[
            Resaltada(casilla="g3", color="amarillo"),
            Resaltada(casilla="f6", color="rojo"),
        ],
        flechas=[
            Flecha(origen="c1", destino="f1", sentido="directo", fuente="manual"),
            Flecha(origen="h5", destino="f6", sentido="directo", fuente="manual"),
        ],
    )

    salida = generar_braille(posicion)
    lineas = salida.split("\n")

    # Localiza la línea de resaltadas: empieza por ")" y NO acaba en "(".
    linea_resaltadas = next(l for l in lineas if l.startswith(")"))
    assert not linea_resaltadas.endswith("("), (
        "La línea de resaltadas no debe cerrarse con '(' cuando hay flechas."
    )
    # Nombra ambos colores y las casillas resaltadas en braille.
    assert "amarillo" in linea_resaltadas
    assert "rojo" in linea_resaltadas
    assert "g⠒" in linea_resaltadas
    assert "f⠖" in linea_resaltadas

    # Cada flecha aparece en su propia línea, DENTRO del bloque (después de la
    # línea de resaltadas y con la marca de flecha).
    indice_resaltadas = lineas.index(linea_resaltadas)
    lineas_flecha = lineas[indice_resaltadas + 1:]
    assert lineas_flecha[0] == "c⠂¬⠒⠕¬f⠂"
    # La última línea de flecha lleva el "(" de cierre del bloque.
    assert lineas_flecha[-1] == "h⠢¬⠒⠕¬f⠖("
    # El "(" solo aparece una vez en toda la salida, al cerrar el bloque.
    assert salida.count("(") == 1
