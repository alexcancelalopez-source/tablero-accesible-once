"""Comprobaciones de legalidad de la posición (Modulo_Validacion).

Este módulo implementa :func:`validar`, que recibe una :class:`Posicion`
ya orientada y comprueba su legalidad según el Requisito 4:

1. Exactamente un rey blanco y un rey negro (Requisito 4.1).
2. Entre 0 y 8 peones por bando, ambos inclusive (Requisito 4.2).
3. Ningún peón en la fila 1 ni en la fila 8 (Requisito 4.3).
4. Cada casilla contiene 0 o 1 pieza (Requisito 4.4).

Por cada comprobación incumplida se añade un aviso en español que enumera
las casillas afectadas (Requisito 4.5) y se marcan como dudosas —con motivo
``validacion``— las piezas implicadas, **sin eliminarlas** de la posición
(Requisito 4.7). Si la posición contiene casillas dudosas (por confianza
baja, color de resaltado desconocido o por la propia validación) se añade
un aviso enumerando su ubicación (Requisito 4.6). Si todas las
comprobaciones se cumplen y no hay ninguna casilla dudosa, se indica que la
posición es válida (Requisito 4.8).

Nunca se inventan piezas: la validación solo añade avisos y marcas dudosas.

Todos los nombres, comentarios y mensajes van en español, según las reglas
del proyecto (regla 15).
"""

from __future__ import annotations

from typing import Iterable, List

from modulos.posicion import (
    COLUMNAS,
    Dudosa,
    Pieza,
    Posicion,
    separar_casilla,
    unir_casilla,
)


# Mensaje que se muestra cuando la posición pasa todas las comprobaciones y
# no hay ninguna casilla dudosa (Requisito 4.8).
MENSAJE_POSICION_VALIDA = "La posición es válida."


def _clave_orden_casilla(casilla: str) -> tuple[int, int]:
    """Devuelve una clave de orden por columna (``a``→``h``) y luego fila.

    Sirve para enumerar las casillas afectadas de forma estable en los
    avisos, de la columna ``a`` hacia la ``h`` y, dentro de cada columna, de
    la fila 1 a la 8.
    """
    columna, fila = separar_casilla(casilla)
    return (COLUMNAS.index(columna), fila)


def _ordenar_casillas(casillas: Iterable[str]) -> List[str]:
    """Ordena y elimina duplicados de un conjunto de casillas.

    El orden es por columna (``a``→``h``) y, dentro de cada columna, por fila
    ascendente, de modo que la enumeración de los avisos sea determinista.
    """
    unicas = {casilla for casilla in casillas}
    return sorted(unicas, key=_clave_orden_casilla)


def _enumerar(casillas: Iterable[str]) -> str:
    """Compone la enumeración textual de casillas separadas por espacios."""
    return " ".join(_ordenar_casillas(casillas))


def _marcar_dudosas_validacion(posicion: Posicion, casillas: Iterable[str]) -> None:
    """Marca como dudosas (motivo ``validacion``) las casillas indicadas.

    No se eliminan las piezas implicadas: únicamente se añade una entrada en
    ``posicion.dudosas`` con motivo ``validacion`` (Requisito 4.7). Se evita
    crear entradas duplicadas para la misma casilla y motivo.
    """
    existentes = {
        (dudosa.casilla, dudosa.motivo) for dudosa in posicion.dudosas
    }
    for casilla in _ordenar_casillas(casillas):
        clave = (casilla, "validacion")
        if clave not in existentes:
            posicion.dudosas.append(Dudosa(casilla=casilla, motivo="validacion"))
            existentes.add(clave)


def _reyes_por_color(piezas: List[Pieza], color: str) -> List[Pieza]:
    """Devuelve los reyes del ``color`` indicado presentes en ``piezas``."""
    return [p for p in piezas if p.tipo == "Rey" and p.color == color]


def _peones_por_color(piezas: List[Pieza], color: str) -> List[Pieza]:
    """Devuelve los peones del ``color`` indicado presentes en ``piezas``."""
    return [p for p in piezas if p.tipo == "Peon" and p.color == color]


def _comprobar_reyes(posicion: Posicion, avisos: List[str]) -> List[str]:
    """Comprueba que haya exactamente un rey por bando (Requisito 4.1).

    Devuelve la lista de casillas afectadas (las de los reyes del bando cuyo
    recuento no es exactamente 1). Cuando falta el rey de un bando no hay
    casilla que enumerar, pero igualmente se emite el aviso.
    """
    afectadas: List[str] = []
    for color, etiqueta in (("blanco", "blanco"), ("negro", "negro")):
        reyes = _reyes_por_color(posicion.piezas, color)
        if len(reyes) != 1:
            casillas = [rey.casilla for rey in reyes]
            afectadas.extend(casillas)
            if casillas:
                avisos.append(
                    f"Debe haber exactamente un rey {etiqueta}: se han "
                    f"encontrado {len(reyes)}: casillas afectadas "
                    f"{_enumerar(casillas)}."
                )
            else:
                avisos.append(
                    f"Debe haber exactamente un rey {etiqueta}: no se ha "
                    f"encontrado ninguno."
                )
    return afectadas


def _comprobar_numero_peones(posicion: Posicion, avisos: List[str]) -> List[str]:
    """Comprueba que cada bando tenga entre 0 y 8 peones (Requisito 4.2)."""
    afectadas: List[str] = []
    for color, etiqueta in (("blanco", "blancos"), ("negro", "negros")):
        peones = _peones_por_color(posicion.piezas, color)
        if len(peones) > 8:
            casillas = [peon.casilla for peon in peones]
            afectadas.extend(casillas)
            avisos.append(
                f"No puede haber más de 8 peones {etiqueta}: se han "
                f"encontrado {len(peones)}: casillas afectadas "
                f"{_enumerar(casillas)}."
            )
    return afectadas


def _comprobar_peones_filas_extremas(
    posicion: Posicion, avisos: List[str]
) -> List[str]:
    """Comprueba que ningún peón esté en la fila 1 ni en la 8 (Requisito 4.3)."""
    afectadas: List[str] = []
    peones_extremos = [
        p for p in posicion.piezas if p.tipo == "Peon" and p.fila in (1, 8)
    ]
    for fila in (1, 8):
        casillas = [p.casilla for p in peones_extremos if p.fila == fila]
        if casillas:
            afectadas.extend(casillas)
            avisos.append(
                f"Ningún peón puede estar en la fila {fila}: casillas "
                f"afectadas {_enumerar(casillas)}."
            )
    return afectadas


def _comprobar_una_pieza_por_casilla(
    posicion: Posicion, avisos: List[str]
) -> List[str]:
    """Comprueba que cada casilla tenga 0 o 1 pieza (Requisito 4.4)."""
    piezas_por_casilla: dict[str, List[Pieza]] = {}
    for pieza in posicion.piezas:
        piezas_por_casilla.setdefault(pieza.casilla, []).append(pieza)

    afectadas: List[str] = []
    casillas_multiples = [
        casilla
        for casilla, piezas in piezas_por_casilla.items()
        if len(piezas) > 1
    ]
    if casillas_multiples:
        afectadas.extend(casillas_multiples)
        avisos.append(
            "Cada casilla debe tener como mucho una pieza: casillas "
            f"afectadas {_enumerar(casillas_multiples)}."
        )
    return afectadas


def validar(posicion: Posicion) -> Posicion:
    """Comprueba la legalidad de ``posicion`` y registra los avisos.

    Modifica y devuelve la misma :class:`Posicion` recibida:

    - Rellena ``posicion.validacion.avisos`` con un aviso en español por cada
      comprobación incumplida (Requisitos 4.1–4.5) y, si procede, con un
      aviso que enumera las casillas dudosas (Requisito 4.6).
    - Marca como dudosas (motivo ``validacion``) las piezas implicadas en las
      comprobaciones fallidas, sin eliminarlas de ``posicion.piezas``
      (Requisito 4.7).
    - Fija ``posicion.validacion.valida`` a ``True`` solo cuando todas las
      comprobaciones se cumplen y no hay ninguna casilla dudosa; en ese caso
      añade el mensaje de posición válida (Requisito 4.8).

    Nunca se inventan ni se eliminan piezas.
    """
    avisos: List[str] = []
    casillas_afectadas: List[str] = []

    # Comprobaciones de legalidad (Requisitos 4.1–4.4). Cada una añade sus
    # propios avisos y devuelve las casillas de las piezas implicadas.
    casillas_afectadas.extend(_comprobar_reyes(posicion, avisos))
    casillas_afectadas.extend(_comprobar_numero_peones(posicion, avisos))
    casillas_afectadas.extend(_comprobar_peones_filas_extremas(posicion, avisos))
    casillas_afectadas.extend(_comprobar_una_pieza_por_casilla(posicion, avisos))

    hay_fallo_legalidad = len(avisos) > 0

    # Conservar las piezas implicadas marcándolas dudosas sin eliminarlas
    # (Requisito 4.7).
    if casillas_afectadas:
        _marcar_dudosas_validacion(posicion, casillas_afectadas)

    # Enumerar todas las casillas dudosas, incluidas las recién marcadas por
    # validación y las que ya venían de etapas anteriores (Requisito 4.6).
    casillas_dudosas = {dudosa.casilla for dudosa in posicion.dudosas}
    if casillas_dudosas:
        avisos.append(f"Casillas dudosas: {_enumerar(casillas_dudosas)}.")

    # La posición es válida solo si no hay fallos de legalidad ni casillas
    # dudosas de ningún tipo (Requisito 4.8).
    posicion.validacion.valida = not hay_fallo_legalidad and not casillas_dudosas
    if posicion.validacion.valida:
        avisos.append(MENSAJE_POSICION_VALIDA)

    posicion.validacion.avisos = avisos
    return posicion
