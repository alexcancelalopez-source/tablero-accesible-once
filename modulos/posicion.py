"""Modelo de datos del formato intermedio de posición.

Este módulo define el contrato compartido entre las etapas del pipeline
(Reconocimiento → Orientación → Validación → Salidas) de la herramienta
"Tablero Accesible ONCE". La estructura :class:`Posicion` es un objeto en
memoria serializable a JSON que cada módulo lee y/o enriquece.

Además de las estructuras de datos, ofrece utilidades de coordenadas
(validación de columna ``a``–``h`` y fila ``1``–``8``, iteración de las 64
casillas) y funciones de (de)serialización a/desde JSON con recorrido de
ida y vuelta sin pérdida.

Todos los nombres, comentarios y mensajes van en español, según las reglas
del proyecto (regla 15).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator, List

# ---------------------------------------------------------------------------
# Constantes del dominio (valores admitidos por el contrato)
# ---------------------------------------------------------------------------

# Columnas del tablero, de izquierda a derecha desde el lado de las blancas.
COLUMNAS = ("a", "b", "c", "d", "e", "f", "g", "h")

# Filas del tablero, del lado de las blancas (1) al de las negras (8).
FILAS = (1, 2, 3, 4, 5, 6, 7, 8)

# Tipos de pieza reconocidos.
TIPOS_PIEZA = ("Rey", "Dama", "Torre", "Alfil", "Caballo", "Peon")

# Colores de pieza reconocidos.
COLORES_PIEZA = ("blanco", "negro")

# Valores admitidos para el estado de orientación detectado.
ORIENTACIONES = ("estandar", "girada", "asumida")

# Valores admitidos para el método de detección de la orientación.
METODOS_ORIENTACION = ("etiquetas", "heuristica", "indeterminada")

# Colores admitidos para las casillas resaltadas.
COLORES_RESALTADO = ("amarillo", "rojo", "verde", "azul")

# Sentidos admitidos para una flecha.
SENTIDOS_FLECHA = ("directo", "inverso")

# Fuentes admitidas para una flecha.
FUENTES_FLECHA = ("auto", "manual")

# Motivos admitidos para marcar una casilla como dudosa.
MOTIVOS_DUDOSA = ("confianza_baja", "color_resaltado_desconocido", "validacion")


# ---------------------------------------------------------------------------
# Utilidades de coordenadas
# ---------------------------------------------------------------------------

def es_columna_valida(columna: object) -> bool:
    """Indica si ``columna`` es una letra de columna válida (``a``–``h``)."""
    return isinstance(columna, str) and columna in COLUMNAS


def es_fila_valida(fila: object) -> bool:
    """Indica si ``fila`` es un número de fila válido (entero ``1``–``8``).

    Se rechazan los booleanos aunque en Python sean subtipo de ``int``.
    """
    return isinstance(fila, int) and not isinstance(fila, bool) and fila in FILAS


def es_casilla_valida(casilla: object) -> bool:
    """Indica si ``casilla`` es un token de casilla válido, p. ej. ``"e4"``.

    Un token válido está formado por una letra de columna ``a``–``h`` seguida
    de un único dígito de fila ``1``–``8`` (por ejemplo ``"a1"`` o ``"h8"``).
    """
    if not isinstance(casilla, str) or len(casilla) != 2:
        return False
    columna, digito_fila = casilla[0], casilla[1]
    if not digito_fila.isdigit():
        return False
    return es_columna_valida(columna) and es_fila_valida(int(digito_fila))


def unir_casilla(columna: str, fila: int) -> str:
    """Compone el token de casilla a partir de ``columna`` y ``fila``.

    Por ejemplo, ``unir_casilla("e", 4)`` devuelve ``"e4"``.

    Lanza :class:`ValueError` en español si la columna o la fila no son
    válidas, para no generar nunca casillas fuera del tablero.
    """
    if not es_columna_valida(columna):
        raise ValueError(f"Columna no válida: {columna!r}. Debe estar entre 'a' y 'h'.")
    if not es_fila_valida(fila):
        raise ValueError(f"Fila no válida: {fila!r}. Debe estar entre 1 y 8.")
    return f"{columna}{fila}"


def separar_casilla(casilla: str) -> tuple[str, int]:
    """Descompone un token de casilla en su ``(columna, fila)``.

    Por ejemplo, ``separar_casilla("e4")`` devuelve ``("e", 4)``.

    Lanza :class:`ValueError` en español si el token no es una casilla válida.
    """
    if not es_casilla_valida(casilla):
        raise ValueError(
            f"Casilla no válida: {casilla!r}. Debe ser una letra 'a'-'h' seguida "
            f"de un número 1-8, por ejemplo 'e4'."
        )
    return casilla[0], int(casilla[1])


def iterar_casillas() -> Iterator[tuple[str, int]]:
    """Itera las 64 casillas del tablero como pares ``(columna, fila)``.

    El recorrido va fila a fila (de la 1 a la 8) y, dentro de cada fila, de la
    columna ``a`` a la ``h``.
    """
    for fila in FILAS:
        for columna in COLUMNAS:
            yield columna, fila


def iterar_casillas_token() -> Iterator[str]:
    """Itera las 64 casillas del tablero como tokens, p. ej. ``"a1"``."""
    for columna, fila in iterar_casillas():
        yield unir_casilla(columna, fila)


# ---------------------------------------------------------------------------
# Estructuras de datos del formato intermedio
# ---------------------------------------------------------------------------

@dataclass
class Orientacion:
    """Estado de orientación del tablero detectado por el pipeline.

    - ``detectada``: ``"estandar"``, ``"girada"`` o ``"asumida"``.
    - ``metodo``: ``"etiquetas"``, ``"heuristica"`` o ``"indeterminada"``.
    """

    detectada: str = "estandar"
    metodo: str = "indeterminada"

    def a_dict(self) -> dict:
        """Devuelve la orientación como diccionario serializable."""
        return {"detectada": self.detectada, "metodo": self.metodo}

    @classmethod
    def desde_dict(cls, datos: dict) -> "Orientacion":
        """Construye una :class:`Orientacion` desde un diccionario."""
        return cls(
            detectada=datos.get("detectada", "estandar"),
            metodo=datos.get("metodo", "indeterminada"),
        )


@dataclass
class Pieza:
    """Pieza reconocida sobre una casilla del tablero.

    - ``tipo``: uno de ``Rey``, ``Dama``, ``Torre``, ``Alfil``, ``Caballo``, ``Peon``.
    - ``color``: ``"blanco"`` o ``"negro"``.
    - ``columna``: letra ``a``–``h``; ``fila``: entero ``1``–``8``.
    - ``confianza``: valor en ``[0.0, 1.0]``.
    """

    tipo: str
    color: str
    columna: str
    fila: int
    confianza: float = 1.0

    @property
    def casilla(self) -> str:
        """Token de casilla de la pieza, por ejemplo ``"e1"``."""
        return unir_casilla(self.columna, self.fila)

    def a_dict(self) -> dict:
        """Devuelve la pieza como diccionario serializable."""
        return {
            "tipo": self.tipo,
            "color": self.color,
            "columna": self.columna,
            "fila": self.fila,
            "confianza": self.confianza,
        }

    @classmethod
    def desde_dict(cls, datos: dict) -> "Pieza":
        """Construye una :class:`Pieza` desde un diccionario."""
        return cls(
            tipo=datos["tipo"],
            color=datos["color"],
            columna=datos["columna"],
            fila=datos["fila"],
            confianza=datos.get("confianza", 1.0),
        )


@dataclass
class Resaltada:
    """Casilla resaltada con su color.

    - ``casilla``: token de casilla, por ejemplo ``"g3"``.
    - ``color``: uno de ``amarillo``, ``rojo``, ``verde``, ``azul``.
    """

    casilla: str
    color: str

    def a_dict(self) -> dict:
        """Devuelve la casilla resaltada como diccionario serializable."""
        return {"casilla": self.casilla, "color": self.color}

    @classmethod
    def desde_dict(cls, datos: dict) -> "Resaltada":
        """Construye una :class:`Resaltada` desde un diccionario."""
        return cls(casilla=datos["casilla"], color=datos["color"])


@dataclass
class Flecha:
    """Flecha que une una casilla de origen con una de destino.

    - ``origen`` y ``destino``: tokens de casilla.
    - ``sentido``: ``"directo"`` (⠒⠕) o ``"inverso"`` (⠪⠒).
    - ``fuente``: ``"auto"`` (detección automática) o ``"manual"`` (--flecha).
    """

    origen: str
    destino: str
    sentido: str = "directo"
    fuente: str = "auto"

    def a_dict(self) -> dict:
        """Devuelve la flecha como diccionario serializable."""
        return {
            "origen": self.origen,
            "destino": self.destino,
            "sentido": self.sentido,
            "fuente": self.fuente,
        }

    @classmethod
    def desde_dict(cls, datos: dict) -> "Flecha":
        """Construye una :class:`Flecha` desde un diccionario."""
        return cls(
            origen=datos["origen"],
            destino=datos["destino"],
            sentido=datos.get("sentido", "directo"),
            fuente=datos.get("fuente", "auto"),
        )


@dataclass
class Dudosa:
    """Casilla marcada como dudosa junto con el motivo.

    - ``casilla``: token de casilla, por ejemplo ``"c6"``.
    - ``motivo``: ``confianza_baja``, ``color_resaltado_desconocido`` o ``validacion``.
    """

    casilla: str
    motivo: str

    def a_dict(self) -> dict:
        """Devuelve la casilla dudosa como diccionario serializable."""
        return {"casilla": self.casilla, "motivo": self.motivo}

    @classmethod
    def desde_dict(cls, datos: dict) -> "Dudosa":
        """Construye una :class:`Dudosa` desde un diccionario."""
        return cls(casilla=datos["casilla"], motivo=datos["motivo"])


@dataclass
class Validacion:
    """Resultado de la validación de legalidad de la posición.

    - ``valida``: ``True`` si la posición pasa todas las comprobaciones y no
      hay casillas dudosas; ``False`` en caso contrario.
    - ``avisos``: lista de mensajes en español que describen cada incidencia.
    """

    valida: bool = False
    avisos: List[str] = field(default_factory=list)

    def a_dict(self) -> dict:
        """Devuelve la validación como diccionario serializable."""
        return {"valida": self.valida, "avisos": list(self.avisos)}

    @classmethod
    def desde_dict(cls, datos: dict) -> "Validacion":
        """Construye una :class:`Validacion` desde un diccionario."""
        return cls(
            valida=datos.get("valida", False),
            avisos=list(datos.get("avisos", [])),
        )


@dataclass
class Posicion:
    """Formato intermedio de posición que fluye por todo el pipeline.

    Reúne las piezas reconocidas, las casillas resaltadas, las flechas, las
    casillas dudosas, el estado de orientación y el resultado de validación.
    Es el contrato serializable a JSON entre las etapas del pipeline.
    """

    orientacion: Orientacion = field(default_factory=Orientacion)
    piezas: List[Pieza] = field(default_factory=list)
    resaltadas: List[Resaltada] = field(default_factory=list)
    flechas: List[Flecha] = field(default_factory=list)
    dudosas: List[Dudosa] = field(default_factory=list)
    validacion: Validacion = field(default_factory=Validacion)

    def a_dict(self) -> dict:
        """Devuelve la posición completa como diccionario serializable."""
        return {
            "orientacion": self.orientacion.a_dict(),
            "piezas": [pieza.a_dict() for pieza in self.piezas],
            "resaltadas": [resaltada.a_dict() for resaltada in self.resaltadas],
            "flechas": [flecha.a_dict() for flecha in self.flechas],
            "dudosas": [dudosa.a_dict() for dudosa in self.dudosas],
            "validacion": self.validacion.a_dict(),
        }

    @classmethod
    def desde_dict(cls, datos: dict) -> "Posicion":
        """Construye una :class:`Posicion` desde un diccionario."""
        return cls(
            orientacion=Orientacion.desde_dict(datos.get("orientacion", {})),
            piezas=[Pieza.desde_dict(p) for p in datos.get("piezas", [])],
            resaltadas=[Resaltada.desde_dict(r) for r in datos.get("resaltadas", [])],
            flechas=[Flecha.desde_dict(f) for f in datos.get("flechas", [])],
            dudosas=[Dudosa.desde_dict(d) for d in datos.get("dudosas", [])],
            validacion=Validacion.desde_dict(datos.get("validacion", {})),
        )


# ---------------------------------------------------------------------------
# (De)serialización a/desde JSON del formato intermedio
# ---------------------------------------------------------------------------

def posicion_a_dict(posicion: Posicion) -> dict:
    """Convierte una :class:`Posicion` en un diccionario serializable."""
    return posicion.a_dict()


def posicion_desde_dict(datos: dict) -> Posicion:
    """Reconstruye una :class:`Posicion` a partir de un diccionario."""
    return Posicion.desde_dict(datos)


def posicion_a_json(posicion: Posicion, *, indentado: bool = False) -> str:
    """Serializa una :class:`Posicion` a texto JSON.

    Con ``indentado=True`` se produce una salida legible con sangría; por
    defecto se genera JSON compacto. En ambos casos ``ensure_ascii`` es
    ``False`` para conservar los caracteres braille y las tildes.
    """
    sangria = 2 if indentado else None
    return json.dumps(posicion.a_dict(), ensure_ascii=False, indent=sangria)


def posicion_desde_json(texto: str) -> Posicion:
    """Reconstruye una :class:`Posicion` a partir de texto JSON."""
    return Posicion.desde_dict(json.loads(texto))
