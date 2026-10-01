"""Salida de audio en español natural para lector de pantalla.

Este submódulo del :mod:`modulos.salidas` genera la Salida_Audio: una
descripción de la posición en frases completas en español, apta para lector
de pantalla, **sin ningún símbolo braille**, sin el carácter ``¬`` ni flechas
Unicode (Requisitos 8.1, 8.7, 6.4).

La salida se compone así:

- Un bloque ``Blancas:`` seguido de un bloque ``Negras:`` (Requisito 8.2).
- Si un bando no tiene piezas, se escribe ``sin piezas`` tras su etiqueta
  (Requisito 8.3).
- Dentro de cada bando, las piezas se agrupan por tipo en una sola frase, con
  las casillas separadas por comas y la conjunción "y" antes de la última
  (por ejemplo, "Torres en A1 y H1"); una sola casilla usa la forma singular
  (por ejemplo, "Rey en E1") (Requisitos 8.4, 8.5).
- Las casillas se nombran con la letra de columna en mayúscula seguida del
  número de fila, sin espacio intermedio (por ejemplo, ``E1``) (Requisito 8.6).
- Las casillas resaltadas se describen en español, agrupadas por color, sin
  braille (Requisitos 6.4, 6.5).
- Las flechas se describen con palabras en español (por ejemplo, "Flecha de
  F3 a E5"), nunca con braille, ``¬`` ni flechas Unicode (Requisito 8.7).

Como red de seguridad, toda la salida pasa por :func:`filtrar_caracteres_permitidos`,
que elimina cualquier carácter fuera del conjunto permitido (Requisito 8.7).

El orden de tipos de pieza es el mismo que en braille (Rey, Dama, Torre,
Caballo, Alfil, Peones) y, dentro de cada tipo, de columna ``a`` hacia ``h``.

Todos los nombres, comentarios y mensajes van en español, según las reglas
del proyecto (regla 15).

_Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 6.4_
"""

from __future__ import annotations

from ..posicion import COLUMNAS, es_casilla_valida, es_columna_valida, separar_casilla

# ---------------------------------------------------------------------------
# Tablas y constantes de la salida de audio
# ---------------------------------------------------------------------------

# Orden de salida de los tipos de pieza dentro de cada bando (Requisito 5.7),
# el mismo que en la salida braille: Rey, Dama, Torre, Caballo, Alfil, Peones.
ORDEN_TIPOS = ("Rey", "Dama", "Torre", "Caballo", "Alfil", "Peon")

# Nombre del tipo de pieza en español, en singular y en plural (Requisitos
# 8.4, 8.5). El peón lleva tilde ("Peón"/"Peones"), incluida en el conjunto
# de caracteres permitido.
NOMBRE_TIPO = {
    "Rey": ("Rey", "Reyes"),
    "Dama": ("Dama", "Damas"),
    "Torre": ("Torre", "Torres"),
    "Caballo": ("Caballo", "Caballos"),
    "Alfil": ("Alfil", "Alfiles"),
    "Peon": ("Peón", "Peones"),
}

# Etiqueta de cada bando por color de pieza (Requisito 8.2).
ETIQUETA_BANDO = {
    "blanco": "Blancas:",
    "negro": "Negras:",
}

# Orden de aparición de los colores de resaltado (mismo criterio que braille).
ORDEN_COLORES_RESALTADO = ("amarillo", "rojo", "verde", "azul")

# Conjunto de caracteres permitido en la Salida_Audio (Requisitos 8.1, 8.7):
# letras del alfabeto español (con tildes y ñ), dígitos, espacio y los signos
# coma, punto y dos puntos. Se admite además el salto de línea para separar
# los bloques Blancas/Negras y las descripciones, sin introducir braille,
# ``¬`` ni flechas Unicode.
_LETRAS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ACENTOS = "áéíóúüñÁÉÍÓÚÜÑ"
_DIGITOS = "0123456789"
_SIGNOS = ",.: "
_SALTO = "\n"

CARACTERES_PERMITIDOS = frozenset(_LETRAS + _ACENTOS + _DIGITOS + _SIGNOS + _SALTO)


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def filtrar_caracteres_permitidos(texto: str) -> str:
    """Elimina de ``texto`` todo carácter fuera del conjunto permitido.

    Conserva únicamente las letras del alfabeto español (con tildes y ñ), los
    dígitos ``0``–``9``, el espacio, los signos ``,`` ``.`` ``:`` y el salto de
    línea. Elimina en particular cualquier carácter braille, el carácter ``¬``
    y las flechas Unicode (Requisito 8.7). Actúa como red de seguridad sobre
    la salida completa para garantizar el conjunto de caracteres permitido.
    """
    return "".join(caracter for caracter in texto if caracter in CARACTERES_PERMITIDOS)


def _nombre_casilla(casilla: str) -> str:
    """Devuelve el nombre de una casilla en formato audio, p. ej. ``"E1"``.

    Convierte el token de casilla (``"e1"``) a la letra de columna en
    mayúscula seguida del dígito de fila, sin espacio (Requisito 8.6). Lanza
    :class:`ValueError` en español si la casilla no es válida, para no
    nombrar nunca casillas fuera del tablero.
    """
    columna, fila = separar_casilla(casilla)
    return f"{columna.upper()}{fila}"


def _indice_columna(columna: str) -> int:
    """Devuelve el índice de ``columna`` en el orden ``a``→``h``.

    Sirve para ordenar las piezas de un mismo tipo de columna ``a`` hacia
    ``h``. Lanza :class:`ValueError` en español si la columna no es válida.
    """
    if not es_columna_valida(columna):
        raise ValueError(
            f"Columna no válida: {columna!r}. Debe estar entre 'a' y 'h'."
        )
    return COLUMNAS.index(columna)


def _enumerar_casillas(nombres: list[str]) -> str:
    """Enumera nombres de casilla separados por comas y "y" antes del último.

    Por ejemplo, ``["A1", "H1"]`` produce ``"A1 y H1"`` y
    ``["A1", "D1", "H1"]`` produce ``"A1, D1 y H1"`` (Requisito 8.4). Con un
    solo nombre lo devuelve tal cual.
    """
    if len(nombres) == 1:
        return nombres[0]
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _frase_tipo(tipo: str, piezas_tipo: list) -> str:
    """Compone la frase de un tipo de pieza dentro de un bando.

    Ordena las piezas del tipo de columna ``a`` hacia ``h``, nombra sus
    casillas y elige la forma singular o plural del nombre del tipo según el
    número de casillas (Requisitos 8.4, 8.5). Por ejemplo, devuelve
    ``"Rey en E1"`` o ``"Torres en A1 y H1"``.
    """
    ordenadas = sorted(piezas_tipo, key=lambda p: _indice_columna(p.columna))
    nombres = [_nombre_casilla(p.casilla) for p in ordenadas]
    singular, plural = NOMBRE_TIPO[tipo]
    nombre_tipo = singular if len(nombres) == 1 else plural
    return f"{nombre_tipo} en {_enumerar_casillas(nombres)}"


def _bloque_bando(piezas, color: str) -> str:
    """Compone el bloque de audio de un bando (``blanco`` o ``negro``).

    Agrupa las piezas del ``color`` por tipo en el orden :data:`ORDEN_TIPOS`,
    genera una frase por tipo presente y las une con comas. Si el bando no
    tiene piezas, escribe ``sin piezas`` tras la etiqueta (Requisito 8.3).

    Devuelve, por ejemplo, ``"Blancas: Rey en E1, Torres en A1 y H1."``.
    """
    del_bando = [pieza for pieza in piezas if pieza.color == color]
    etiqueta = ETIQUETA_BANDO[color]

    if not del_bando:
        return f"{etiqueta} sin piezas."

    frases: list[str] = []
    for tipo in ORDEN_TIPOS:
        piezas_tipo = [pieza for pieza in del_bando if pieza.tipo == tipo]
        if piezas_tipo:
            frases.append(_frase_tipo(tipo, piezas_tipo))

    return f"{etiqueta} {', '.join(frases)}."


def _bloque_resaltadas(resaltadas) -> str:
    """Describe las casillas resaltadas en español, agrupadas por color.

    Agrupa las casillas por color en el orden :data:`ORDEN_COLORES_RESALTADO`,
    listando solo los colores presentes, sin braille (Requisitos 6.4, 6.5).
    Dentro de cada color, ordena las casillas de forma determinista por
    columna ``a``→``h`` y fila ``1``→``8``. Devuelve cadena vacía si no hay
    resaltadas, de modo que la sección se omite por completo (Requisito 6.5).

    Devuelve, por ejemplo, ``"Casillas resaltadas: G3 en amarillo."``.
    """
    if not resaltadas:
        return ""

    grupos: list[str] = []
    for color in ORDEN_COLORES_RESALTADO:
        casillas_color = [r.casilla for r in resaltadas if r.color == color]
        if not casillas_color:
            continue
        casillas_color.sort(
            key=lambda c: (_indice_columna(separar_casilla(c)[0]), separar_casilla(c)[1])
        )
        nombres = [_nombre_casilla(c) for c in casillas_color]
        grupos.append(f"{_enumerar_casillas(nombres)} en {color}")

    if not grupos:
        return ""

    return f"Casillas resaltadas: {', '.join(grupos)}."


def _linea_flecha(flecha) -> str:
    """Describe una flecha con palabras en español, sin símbolos confusos.

    Usa una frase natural del tipo ``"Flecha de F3 a E5"`` (o
    ``"Flecha de E5 a F3 en sentido inverso"``), sin braille, ``¬`` ni
    flechas Unicode (Requisito 8.7). Si el origen o el destino no son casillas
    válidas, no se inventa la flecha: se devuelve un aviso en español
    (Requisito 7.5).
    """
    if not es_casilla_valida(flecha.origen) or not es_casilla_valida(flecha.destino):
        return (
            f"Aviso: flecha no reconocida con origen {flecha.origen} y "
            f"destino {flecha.destino}, no se describe."
        )

    origen = _nombre_casilla(flecha.origen)
    destino = _nombre_casilla(flecha.destino)
    if flecha.sentido == "inverso":
        return f"Flecha de {origen} a {destino} en sentido inverso."
    return f"Flecha de {origen} a {destino}."


# ---------------------------------------------------------------------------
# Ensamblado completo de la salida de audio
# ---------------------------------------------------------------------------

def generar_audio(posicion) -> str:
    """Genera la Salida_Audio en español para una ``posicion``.

    Ensambla, en este orden y separados por saltos de línea:

    1. El bloque ``Blancas:`` con las piezas blancas (o ``sin piezas``).
    2. El bloque ``Negras:`` con las piezas negras (o ``sin piezas``).
    3. La descripción de casillas resaltadas agrupadas por color, si hay
       alguna (Requisitos 6.4, 6.5).
    4. Una descripción en español por cada flecha (Requisito 8.7).

    Dentro de cada bando las piezas se agrupan por tipo (Rey, Dama, Torre,
    Caballo, Alfil, Peones) y, dentro de cada tipo, de columna ``a`` hacia
    ``h``; se usa la forma singular o plural del nombre del tipo según el
    número de casillas (Requisitos 8.4, 8.5). Las casillas se nombran con la
    columna en mayúscula y la fila (Requisito 8.6).

    Toda la salida pasa por :func:`filtrar_caracteres_permitidos` como red de
    seguridad, garantizando que solo contiene el conjunto de caracteres
    permitido: letras españolas, dígitos, espacio, ``,`` ``.`` ``:`` y salto
    de línea, sin braille, ``¬`` ni flechas Unicode (Requisito 8.7).

    La salida es determinista: la misma posición produce siempre el mismo
    texto. Acepta cualquier objeto con los atributos ``piezas``,
    ``resaltadas`` y ``flechas`` del formato intermedio de posición.
    """
    lineas: list[str] = [
        _bloque_bando(posicion.piezas, "blanco"),
        _bloque_bando(posicion.piezas, "negro"),
    ]

    bloque_resaltadas = _bloque_resaltadas(posicion.resaltadas)
    if bloque_resaltadas:
        lineas.append(bloque_resaltadas)

    for flecha in posicion.flechas:
        lineas.append(_linea_flecha(flecha))

    return filtrar_caracteres_permitidos("\n".join(lineas))
