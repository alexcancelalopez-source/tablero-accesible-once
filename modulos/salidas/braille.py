"""Notación braille pura de la ONCE: tablas y codificación de casilla.

Este submódulo del :mod:`modulos.salidas` implementa la parte pura de la
Notacion_Braille_ONCE (Documento técnico B8 de la Comisión Braille Española),
sin depender de imágenes ni de la composición completa de la salida. Aquí se
definen únicamente:

- Las tablas de notación: filas → número braille en posición baja, tipos de
  pieza → letra de pieza, y las columnas ``a``–``h``.
- La codificación y decodificación de un token de casilla
  ``columna + fila_braille`` (por ejemplo ``e1`` → ``"e⠂"``).
- La codificación de un token de pieza ``Letra + columna + fila_braille`` sin
  ningún separador interno (por ejemplo, Rey en e1 → ``"Re⠂"``).

El ensamblado completo de la salida braille (orden de piezas, líneas de bando,
sección de resaltadas y flechas) se implementa más abajo en :func:`generar_braille`.

Todos los nombres, comentarios y mensajes van en español, según las reglas
del proyecto (regla 15).

_Requirements: 5.1, 5.2, 5.3, 5.4_
"""

from __future__ import annotations

from ..posicion import (
    COLUMNAS,
    TIPOS_PIEZA,
    es_columna_valida,
    es_fila_valida,
)

# ---------------------------------------------------------------------------
# Tablas de notación braille (constantes de datos)
# ---------------------------------------------------------------------------

# Filas → número braille en posición baja (Requisito 5.1).
# Equivalencia exacta: 1⠂ 2⠆ 3⠒ 4⠲ 5⠢ 6⠖ 7⠶ 8⠦.
FILA_A_BRAILLE = {
    1: "⠂",
    2: "⠆",
    3: "⠒",
    4: "⠲",
    5: "⠢",
    6: "⠖",
    7: "⠶",
    8: "⠦",
}

# Inversa de la tabla anterior: número braille → fila (para decodificar).
BRAILLE_A_FILA = {braille: fila for fila, braille in FILA_A_BRAILLE.items()}

# Tipos de pieza → letra de pieza (Requisito 5.4).
# R Rey, D Dama, T Torre, A Alfil, C Caballo, P Peón.
PIEZA_A_LETRA = {
    "Rey": "R",
    "Dama": "D",
    "Torre": "T",
    "Alfil": "A",
    "Caballo": "C",
    "Peon": "P",
}

# Inversa de la tabla anterior: letra de pieza → tipo.
LETRA_A_PIEZA = {letra: tipo for tipo, letra in PIEZA_A_LETRA.items()}


# ---------------------------------------------------------------------------
# Codificación y decodificación de un token de casilla
# ---------------------------------------------------------------------------

def codificar_casilla(columna: str, fila: int) -> str:
    """Codifica una casilla ``(columna, fila)`` a su token braille.

    El token está formado por la letra de columna (``a``–``h``) seguida
    inmediatamente del número de fila en braille de posición baja, sin
    separador (Requisitos 5.1, 5.2). Por ejemplo, ``codificar_casilla("e", 1)``
    devuelve ``"e⠂"``.

    Lanza :class:`ValueError` en español si la columna o la fila no son
    válidas, para no generar nunca casillas fuera del tablero.
    """
    if not es_columna_valida(columna):
        raise ValueError(
            f"Columna no válida: {columna!r}. Debe estar entre 'a' y 'h'."
        )
    if not es_fila_valida(fila):
        raise ValueError(
            f"Fila no válida: {fila!r}. Debe estar entre 1 y 8."
        )
    return f"{columna}{FILA_A_BRAILLE[fila]}"


def decodificar_casilla(token: str) -> tuple[str, int]:
    """Decodifica un token braille de casilla a su ``(columna, fila)``.

    Es la operación inversa de :func:`codificar_casilla`. Por ejemplo,
    ``decodificar_casilla("e⠂")`` devuelve ``("e", 1)``.

    Lanza :class:`ValueError` en español si el token no es una casilla
    braille válida (letra de columna ``a``–``h`` seguida de un número de fila
    braille de posición baja).
    """
    if not isinstance(token, str) or len(token) != 2:
        raise ValueError(
            f"Token de casilla braille no válido: {token!r}. Debe ser una "
            f"letra 'a'-'h' seguida de un número de fila braille, por ejemplo 'e⠂'."
        )
    columna, fila_braille = token[0], token[1]
    if not es_columna_valida(columna):
        raise ValueError(
            f"Columna no válida en el token {token!r}: {columna!r}. "
            f"Debe estar entre 'a' y 'h'."
        )
    if fila_braille not in BRAILLE_A_FILA:
        raise ValueError(
            f"Número de fila braille no válido en el token {token!r}: "
            f"{fila_braille!r}."
        )
    return columna, BRAILLE_A_FILA[fila_braille]


# ---------------------------------------------------------------------------
# Codificación de un token de pieza
# ---------------------------------------------------------------------------

def codificar_pieza(tipo: str, columna: str, fila: int) -> str:
    """Codifica una pieza a su token braille ``Letra+columna+fila_braille``.

    El token concatena, sin ningún espacio ni separador interno, la letra de
    pieza (Requisito 5.4), la letra de columna y el número de fila en braille
    (Requisito 5.3). Por ejemplo, ``codificar_pieza("Rey", "e", 1)`` devuelve
    ``"Re⠂"``.

    Lanza :class:`ValueError` en español si el tipo de pieza, la columna o la
    fila no son válidos.
    """
    if tipo not in PIEZA_A_LETRA:
        tipos_validos = ", ".join(TIPOS_PIEZA)
        raise ValueError(
            f"Tipo de pieza no válido: {tipo!r}. Debe ser uno de: {tipos_validos}."
        )
    # codificar_casilla valida la columna y la fila y lanza ValueError si no
    # son válidas, evitando duplicar las comprobaciones aquí.
    return f"{PIEZA_A_LETRA[tipo]}{codificar_casilla(columna, fila)}"


# ---------------------------------------------------------------------------
# Ensamblado completo de la salida braille (Tarea 4.1)
# ---------------------------------------------------------------------------
#
# Reúne las piezas de cada bando en sus líneas "Blancas:" y "Negras:", añade
# la sección de casillas resaltadas entre ")" y "(" agrupada por color y las
# líneas de flechas en notación braille de la ONCE.
#
# _Requirements: 5.5, 5.6, 5.7, 5.8, 5.9, 6.2, 6.3, 7.2, 7.3, 7.4_

# Orden de salida de los tipos de pieza dentro de cada bando (Requisito 5.7).
# Rey, Dama, Torre, Caballo, Alfil, Peones (equivale a R, D, T, C, A, P).
ORDEN_TIPOS = ("Rey", "Dama", "Torre", "Caballo", "Alfil", "Peon")

# Etiqueta de cada bando por color de pieza (Requisito 5.5, 5.6).
ETIQUETA_BANDO = {
    "blanco": "Blancas:",
    "negro": "Negras:",
}

# Orden de aparición de los colores de resaltado en la sección resaltada
# (Requisito 6.2, 6.3). Se listan solo los colores presentes.
ORDEN_COLORES_RESALTADO = ("amarillo", "rojo", "verde", "azul")

# Marcas braille de las flechas (Requisitos 7.2, 7.3).
UNION_FLECHA = "¬"          # separador entre casilla y marca de flecha
FLECHA_DIRECTA = "⠒⠕"      # sentido directo: origen apunta al destino
FLECHA_INVERSA = "⠪⠒"      # sentido inverso: apunta en sentido contrario


def _indice_columna(columna: str) -> int:
    """Devuelve el índice de ``columna`` en el orden ``a``→``h``.

    Sirve para ordenar las piezas de un mismo tipo de columna ``a`` hacia
    ``h`` (Requisito 5.8). Lanza :class:`ValueError` en español si la columna
    no es válida, para no ordenar nunca sobre coordenadas fuera del tablero.
    """
    if not es_columna_valida(columna):
        raise ValueError(
            f"Columna no válida: {columna!r}. Debe estar entre 'a' y 'h'."
        )
    return COLUMNAS.index(columna)


def _linea_bando(piezas, color: str) -> str:
    """Compone la línea braille de un bando (``blanco`` o ``negro``).

    Filtra las piezas del ``color`` indicado, las ordena por tipo según
    :data:`ORDEN_TIPOS` y, dentro de cada tipo, de columna ``a`` hacia ``h``
    (Requisitos 5.7, 5.8). Codifica cada pieza con :func:`codificar_pieza` y
    une los tokens con un único espacio; los tipos ausentes no aportan tokens
    ni espacios sobrantes (Requisito 5.9).

    Devuelve, por ejemplo, ``"Blancas: Re⠂ Ta⠂ Th⠂"``. Si el bando no tiene
    piezas, devuelve solo la etiqueta (``"Blancas:"``).
    """
    del_bando = [pieza for pieza in piezas if pieza.color == color]

    # Ordenación estable y determinista: primero por orden de tipo, luego por
    # columna a→h. Los tipos desconocidos se colocan al final sin romper el
    # determinismo, aunque el modelo de datos ya restringe los tipos válidos.
    def clave(pieza):
        try:
            indice_tipo = ORDEN_TIPOS.index(pieza.tipo)
        except ValueError:
            indice_tipo = len(ORDEN_TIPOS)
        return (indice_tipo, _indice_columna(pieza.columna))

    del_bando.sort(key=clave)

    # Según el Documento técnico B8 de la ONCE (y como muestran los tableros 2
    # a 6 del documento de referencia), el peón se anota SIN la letra de pieza
    # "P": solo columna + fila braille (por ejemplo, un peón blanco en c4 →
    # "c⠲"). El resto de piezas conservan su letra (R, D, T, C, A). Por eso el
    # peón se codifica con codificar_casilla y las demás con codificar_pieza,
    # sin alterar codificar_pieza (de la que pueden depender otros módulos).
    tokens = [
        codificar_casilla(pieza.columna, pieza.fila)
        if pieza.tipo == "Peon"
        else codificar_pieza(pieza.tipo, pieza.columna, pieza.fila)
        for pieza in del_bando
    ]

    etiqueta = ETIQUETA_BANDO[color]
    if not tokens:
        return etiqueta
    return f"{etiqueta} {' '.join(tokens)}"


def _token_casilla_braille(casilla: str) -> str:
    """Convierte un token de casilla (p. ej. ``"g3"``) a braille (``"g⠒"``).

    Reutiliza :func:`codificar_casilla` sobre la ``(columna, fila)`` que
    compone el token. Lanza :class:`ValueError` en español si la casilla no
    es válida, para no inventar nunca casillas fuera del tablero.
    """
    from ..posicion import separar_casilla

    columna, fila = separar_casilla(casilla)
    return codificar_casilla(columna, fila)


def _seccion_resaltadas(resaltadas) -> str:
    """Compone la sección de casillas resaltadas abierta con ``)``.

    Agrupa las casillas por color en el orden :data:`ORDEN_COLORES_RESALTADO`
    (amarillo, rojo, verde, azul), listando solo los colores presentes
    (Requisitos 6.2, 6.3). Dentro de cada color, las casillas se ordenan de
    forma determinista por columna ``a``→``h`` y fila ``1``→``8`` y se
    representan en braille. Devuelve cadena vacía si no hay resaltadas, de
    modo que la sección se omite por completo (Requisito 6.5).

    IMPORTANTE: esta función NO añade el paréntesis de cierre ``(``. El cierre
    lo coloca :func:`generar_braille` según haya o no flechas: si hay flechas,
    el ``(`` va al final de la última línea de flecha (caso A del documento);
    si no las hay, se cierra en la propia línea de resaltadas (caso B). Así se
    reproduce fielmente el documento de referencia (tableros 1, 5 y 6).
    """
    from ..posicion import separar_casilla

    if not resaltadas:
        return ""

    grupos: list[str] = []
    for color in ORDEN_COLORES_RESALTADO:
        casillas_color = [r.casilla for r in resaltadas if r.color == color]
        if not casillas_color:
            continue
        # Orden determinista por columna a→h y luego fila 1→8.
        casillas_color.sort(key=lambda c: (_indice_columna(separar_casilla(c)[0]),
                                           separar_casilla(c)[1]))
        casillas_braille = [_token_casilla_braille(c) for c in casillas_color]
        if len(casillas_braille) == 1:
            grupos.append(
                f"en {color} la casilla {casillas_braille[0]}"
            )
        else:
            lista = " y ".join(casillas_braille)
            grupos.append(f"en {color} las casillas {lista}")

    if not grupos:
        return ""

    cuerpo = "; ".join(grupos)
    # Solo se abre con ")". El cierre "(" lo decide generar_braille.
    return f")Resaltadas {cuerpo}"


def _linea_flecha(flecha) -> str:
    """Compone la línea braille de una flecha ``origen¬marca¬destino``.

    Usa :data:`FLECHA_DIRECTA` (``⠒⠕``) para el sentido ``directo`` y
    :data:`FLECHA_INVERSA` (``⠪⠒``) para el ``inverso`` (Requisitos 7.2,
    7.3, 7.4), uniendo con ``¬`` los tokens braille de origen y destino.

    Si el origen o el destino no corresponden a una casilla válida, no se
    inventa la flecha: se devuelve un aviso en español (Requisito 7.5).
    """
    from ..posicion import es_casilla_valida

    if not es_casilla_valida(flecha.origen) or not es_casilla_valida(flecha.destino):
        return (
            f"Aviso: flecha no reconocida con origen {flecha.origen!r} y "
            f"destino {flecha.destino!r}; no se representa."
        )

    marca = FLECHA_INVERSA if flecha.sentido == "inverso" else FLECHA_DIRECTA
    origen_braille = _token_casilla_braille(flecha.origen)
    destino_braille = _token_casilla_braille(flecha.destino)
    return f"{origen_braille}{UNION_FLECHA}{marca}{UNION_FLECHA}{destino_braille}"


def generar_braille(posicion) -> str:
    """Genera la salida braille completa de la ONCE para una ``posicion``.

    Ensambla, en este orden y separados por saltos de línea:

    1. La línea ``Blancas:`` con las piezas blancas.
    2. La línea ``Negras:`` con las piezas negras.
    3. La sección de casillas resaltadas entre ``)`` y ``(`` agrupada por
       color, si hay alguna (Requisitos 6.2, 6.3, 6.5).
    4. Una línea por flecha en notación braille (Requisitos 7.2, 7.3, 7.4).

    Dentro de cada bando las piezas van ordenadas por tipo (Rey, Dama, Torre,
    Caballo, Alfil, Peones) y, dentro de cada tipo, de columna ``a`` hacia
    ``h`` (Requisitos 5.7, 5.8); los tokens se separan por un único espacio y
    los tipos ausentes no dejan espacios sobrantes (Requisitos 5.5, 5.6, 5.9).

    La salida es determinista: la misma posición produce siempre el mismo
    texto (Property 2). Acepta cualquier objeto con los atributos ``piezas``,
    ``resaltadas`` y ``flechas`` del formato intermedio de posición.

    El bloque de resaltadas y flechas se compone reproduciendo el documento de
    referencia de la ONCE:

    - Caso A (hay resaltadas Y flechas): la línea de resaltadas abre con ``)``
      y NO cierra; luego una línea por flecha y el ``(`` se pega al final de la
      ÚLTIMA línea de flecha (tableros 5 y 6 del documento).
    - Caso B (hay resaltadas pero NO flechas): la línea de resaltadas se cierra
      en sí misma, ``)Resaltadas …(`` (tablero 1 del documento).
    - Caso C (NO hay resaltadas pero SÍ flechas): las flechas van como líneas
      sueltas sin los paréntesis ``)`` ``(``.
    - Caso D (ni resaltadas ni flechas): solo las líneas ``Blancas:``/``Negras:``.
    """
    lineas: list[str] = [
        _linea_bando(posicion.piezas, "blanco"),
        _linea_bando(posicion.piezas, "negro"),
    ]

    seccion = _seccion_resaltadas(posicion.resaltadas)
    # _seccion_resaltadas abre con ")" pero NO cierra; el cierre "(" lo
    # colocamos aquí según los casos A/B.
    lineas_flecha = [_linea_flecha(flecha) for flecha in posicion.flechas]

    if seccion and lineas_flecha:
        # Caso A: resaltadas + flechas. Las flechas van DENTRO del bloque y el
        # cierre "(" se pega al final de la última línea de flecha.
        lineas.append(seccion)
        lineas.extend(lineas_flecha[:-1])
        lineas.append(f"{lineas_flecha[-1]}(")
    elif seccion:
        # Caso B: solo resaltadas. El bloque se cierra en su propia línea.
        lineas.append(f"{seccion}(")
    elif lineas_flecha:
        # Caso C: solo flechas, como líneas sueltas sin paréntesis.
        lineas.extend(lineas_flecha)
    # Caso D: sin resaltadas ni flechas, no se añade nada más.

    return "\n".join(lineas)
