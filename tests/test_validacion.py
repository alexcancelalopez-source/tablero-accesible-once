"""Tests de ejemplo del Modulo_Validacion (:func:`validar`).

Estos tests comprueban con casos concretos la legalidad de una posición
según el Requisito 4:

- Una posición legal se marca como válida y añade el mensaje
  "La posición es válida." (Requisitos 4.1–4.4, 4.8).
- Casos ilegales (dos reyes del mismo bando, 9 peones, un peón en la fila 8
  y dos piezas en la misma casilla A6, como en el Diagrama 5) se marcan como
  no válidas, generan un aviso en español que enumera las casillas afectadas
  y **conservan** las piezas implicadas sin eliminarlas ni inventar ninguna
  (Requisitos 4.1, 4.2, 4.3, 4.4, 4.5, 4.7).

Todos los nombres, comentarios y mensajes van en español, según las reglas
del proyecto (regla 15).
"""

from __future__ import annotations

from modulos.posicion import Pieza, Posicion
from modulos.validacion.validador import MENSAJE_POSICION_VALIDA, validar


def _piezas_en(posicion: Posicion, casilla: str) -> list[Pieza]:
    """Devuelve todas las piezas de ``posicion`` situadas en ``casilla``."""
    return [pieza for pieza in posicion.piezas if pieza.casilla == casilla]


def _casillas_dudosas_validacion(posicion: Posicion) -> set[str]:
    """Devuelve las casillas marcadas dudosas con motivo ``validacion``."""
    return {
        dudosa.casilla
        for dudosa in posicion.dudosas
        if dudosa.motivo == "validacion"
    }


def test_posicion_legal_es_valida() -> None:
    """Una posición legal se marca como válida (Requisitos 4.1–4.4, 4.8)."""
    posicion = Posicion(
        piezas=[
            Pieza(tipo="Rey", color="blanco", columna="e", fila=1),
            Pieza(tipo="Rey", color="negro", columna="e", fila=8),
            Pieza(tipo="Torre", color="blanco", columna="a", fila=1),
            Pieza(tipo="Torre", color="blanco", columna="h", fila=1),
            Pieza(tipo="Peon", color="blanco", columna="d", fila=2),
            Pieza(tipo="Peon", color="negro", columna="d", fila=7),
        ]
    )

    validar(posicion)

    assert posicion.validacion.valida is True
    assert MENSAJE_POSICION_VALIDA in posicion.validacion.avisos
    # No debe marcarse ninguna casilla dudosa por validación.
    assert _casillas_dudosas_validacion(posicion) == set()


def test_dos_reyes_del_mismo_bando_es_ilegal() -> None:
    """Dos reyes blancos son ilegales; se conservan ambos (Requisitos 4.1, 4.7)."""
    posicion = Posicion(
        piezas=[
            Pieza(tipo="Rey", color="blanco", columna="d", fila=1),
            Pieza(tipo="Rey", color="blanco", columna="e", fila=1),
            Pieza(tipo="Rey", color="negro", columna="e", fila=8),
        ]
    )

    validar(posicion)

    assert posicion.validacion.valida is False
    # Debe existir un aviso sobre el rey que enumere ambas casillas.
    avisos_rey = [a for a in posicion.validacion.avisos if "rey blanco" in a]
    assert avisos_rey, "Se esperaba un aviso sobre el rey blanco."
    assert any("d1" in a and "e1" in a for a in avisos_rey)
    # Ambos reyes blancos siguen presentes (no se eliminan piezas).
    reyes_blancos = [
        p for p in posicion.piezas if p.tipo == "Rey" and p.color == "blanco"
    ]
    assert len(reyes_blancos) == 2
    # Ambas casillas quedan marcadas como dudosas por validación.
    assert {"d1", "e1"} <= _casillas_dudosas_validacion(posicion)


def test_nueve_peones_es_ilegal() -> None:
    """Nueve peones blancos son ilegales; se conservan los 9 (Requisitos 4.2, 4.7)."""
    columnas = ("a", "b", "c", "d", "e", "f", "g", "h")
    peones = [
        Pieza(tipo="Peon", color="blanco", columna=columna, fila=2)
        for columna in columnas
    ]
    # Un noveno peón blanco (en la fila 3) rompe el límite de 8.
    peones.append(Pieza(tipo="Peon", color="blanco", columna="a", fila=3))
    posicion = Posicion(
        piezas=[
            Pieza(tipo="Rey", color="blanco", columna="e", fila=1),
            Pieza(tipo="Rey", color="negro", columna="e", fila=8),
            *peones,
        ]
    )

    validar(posicion)

    assert posicion.validacion.valida is False
    avisos_peones = [
        a for a in posicion.validacion.avisos if "más de 8 peones" in a
    ]
    assert avisos_peones, "Se esperaba un aviso por más de 8 peones."
    # Los 9 peones blancos siguen presentes.
    peones_blancos = [
        p for p in posicion.piezas if p.tipo == "Peon" and p.color == "blanco"
    ]
    assert len(peones_blancos) == 9


def test_peon_en_fila_8_es_ilegal() -> None:
    """Un peón en la fila 8 es ilegal; se conserva (Requisitos 4.3, 4.7)."""
    posicion = Posicion(
        piezas=[
            Pieza(tipo="Rey", color="blanco", columna="e", fila=1),
            Pieza(tipo="Rey", color="negro", columna="e", fila=8),
            Pieza(tipo="Peon", color="blanco", columna="d", fila=8),
        ]
    )

    validar(posicion)

    assert posicion.validacion.valida is False
    avisos_fila = [
        a for a in posicion.validacion.avisos if "fila 8" in a and "d8" in a
    ]
    assert avisos_fila, "Se esperaba un aviso por un peón en la fila 8."
    # El peón de d8 sigue presente (no se elimina).
    assert _piezas_en(posicion, "d8"), "El peón de d8 debe conservarse."
    assert "d8" in _casillas_dudosas_validacion(posicion)


def test_diagrama5_dos_piezas_en_a6_es_ilegal() -> None:
    """Dos piezas en A6 (Diagrama 5) son ilegales; se conservan (Requisitos 4.4, 4.7)."""
    posicion = Posicion(
        piezas=[
            Pieza(tipo="Rey", color="blanco", columna="e", fila=1),
            Pieza(tipo="Rey", color="negro", columna="e", fila=8),
            # Dos piezas ocupando la misma casilla a6.
            Pieza(tipo="Torre", color="negro", columna="a", fila=6),
            Pieza(tipo="Caballo", color="negro", columna="a", fila=6),
        ]
    )

    validar(posicion)

    assert posicion.validacion.valida is False
    avisos_casilla = [
        a
        for a in posicion.validacion.avisos
        if "como mucho una pieza" in a and "a6" in a
    ]
    assert avisos_casilla, "Se esperaba un aviso por más de una pieza en a6."
    # Ambas piezas de a6 se conservan: nunca se inventan ni se eliminan piezas.
    assert len(_piezas_en(posicion, "a6")) == 2
    assert "a6" in _casillas_dudosas_validacion(posicion)
