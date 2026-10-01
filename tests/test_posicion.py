"""Tests unitarios del modelo de datos del formato intermedio de posición.

Cubren el round-trip de (de)serialización JSON y las utilidades de validación
de coordenadas del módulo :mod:`modulos.posicion`.

Todos los nombres, comentarios y mensajes van en español (regla 15).

Requisitos: 2.3
"""

import pytest

from modulos.posicion import (
    COLUMNAS,
    FILAS,
    Dudosa,
    Flecha,
    Orientacion,
    Pieza,
    Posicion,
    Resaltada,
    Validacion,
    es_casilla_valida,
    es_columna_valida,
    es_fila_valida,
    iterar_casillas,
    iterar_casillas_token,
    posicion_a_dict,
    posicion_a_json,
    posicion_desde_dict,
    posicion_desde_json,
    separar_casilla,
    unir_casilla,
)


# ---------------------------------------------------------------------------
# Round-trip de (de)serialización
# ---------------------------------------------------------------------------

def _posicion_completa() -> Posicion:
    """Construye una posición con todos los campos poblados para el round-trip."""
    return Posicion(
        orientacion=Orientacion(detectada="girada", metodo="heuristica"),
        piezas=[
            Pieza(tipo="Rey", color="blanco", columna="e", fila=1, confianza=0.95),
            Pieza(tipo="Torre", color="blanco", columna="a", fila=1, confianza=0.87),
            Pieza(tipo="Peon", color="negro", columna="d", fila=7, confianza=0.90),
        ],
        resaltadas=[
            Resaltada(casilla="g3", color="amarillo"),
            Resaltada(casilla="c5", color="rojo"),
        ],
        flechas=[
            Flecha(origen="e2", destino="e4", sentido="directo", fuente="manual"),
            Flecha(origen="f3", destino="e5", sentido="inverso", fuente="auto"),
        ],
        dudosas=[
            Dudosa(casilla="c6", motivo="confianza_baja"),
            Dudosa(casilla="a6", motivo="validacion"),
        ],
        validacion=Validacion(valida=False, avisos=["Hay dos piezas en A6."]),
    )


def test_round_trip_json_conserva_todos_los_campos():
    """Serializar a JSON y reconstruir produce un diccionario idéntico."""
    original = _posicion_completa()

    texto_json = posicion_a_json(original)
    reconstruida = posicion_desde_json(texto_json)

    assert posicion_a_dict(reconstruida) == posicion_a_dict(original)


def test_round_trip_json_indentado_equivale_al_compacto():
    """El JSON indentado se reconstruye en la misma posición que el compacto."""
    original = _posicion_completa()

    reconstruida = posicion_desde_json(posicion_a_json(original, indentado=True))

    assert reconstruida.a_dict() == original.a_dict()


def test_round_trip_dict():
    """Round-trip mediante diccionario (sin pasar por texto)."""
    original = _posicion_completa()

    reconstruida = posicion_desde_dict(posicion_a_dict(original))

    assert reconstruida.a_dict() == original.a_dict()


def test_round_trip_posicion_vacia():
    """Una posición con valores por defecto también hace round-trip sin pérdida."""
    original = Posicion()

    reconstruida = posicion_desde_json(posicion_a_json(original))

    assert reconstruida.a_dict() == original.a_dict()


def test_json_conserva_caracteres_no_ascii():
    """El JSON preserva tildes y caracteres especiales de los avisos."""
    original = Posicion(
        validacion=Validacion(valida=False, avisos=["La posición no es válida: peón en fila 8."])
    )

    reconstruida = posicion_desde_json(posicion_a_json(original))

    assert reconstruida.validacion.avisos == ["La posición no es válida: peón en fila 8."]


# ---------------------------------------------------------------------------
# Validación de columnas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("columna", list(COLUMNAS))
def test_es_columna_valida_acepta_de_a_a_h(columna):
    """Todas las columnas 'a'-'h' son válidas."""
    assert es_columna_valida(columna) is True


@pytest.mark.parametrize("columna", ["z", "A", "H", "", "aa", "1", 1, None])
def test_es_columna_valida_rechaza_valores_incorrectos(columna):
    """Se rechazan letras fuera de rango, mayúsculas, vacío y no-cadenas."""
    assert es_columna_valida(columna) is False


# ---------------------------------------------------------------------------
# Validación de filas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fila", list(FILAS))
def test_es_fila_valida_acepta_de_1_a_8(fila):
    """Todas las filas 1-8 son válidas."""
    assert es_fila_valida(fila) is True


@pytest.mark.parametrize("fila", [0, 9, -1, 100, "1", 1.0, None])
def test_es_fila_valida_rechaza_valores_incorrectos(fila):
    """Se rechazan filas fuera de rango, cadenas, flotantes y None."""
    assert es_fila_valida(fila) is False


@pytest.mark.parametrize("booleano", [True, False])
def test_es_fila_valida_rechaza_booleanos(booleano):
    """Los booleanos se rechazan aunque sean subtipo de int en Python."""
    assert es_fila_valida(booleano) is False


# ---------------------------------------------------------------------------
# Validación de casillas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("casilla", ["e4", "a1", "h8"])
def test_es_casilla_valida_acepta_tokens_correctos(casilla):
    """Los tokens de casilla bien formados son válidos."""
    assert es_casilla_valida(casilla) is True


@pytest.mark.parametrize("casilla", ["i9", "e0", "e", "ee", "1e", "e10", "", "A1", None])
def test_es_casilla_valida_rechaza_tokens_incorrectos(casilla):
    """Se rechazan tokens mal formados, fuera de rango o no-cadenas."""
    assert es_casilla_valida(casilla) is False


# ---------------------------------------------------------------------------
# unir_casilla / separar_casilla (relación inversa)
# ---------------------------------------------------------------------------

def test_unir_casilla_compone_token():
    """unir_casilla compone correctamente el token."""
    assert unir_casilla("e", 4) == "e4"
    assert unir_casilla("a", 1) == "a1"
    assert unir_casilla("h", 8) == "h8"


def test_separar_casilla_descompone_token():
    """separar_casilla descompone correctamente el token."""
    assert separar_casilla("e4") == ("e", 4)
    assert separar_casilla("a1") == ("a", 1)
    assert separar_casilla("h8") == ("h", 8)


def test_unir_y_separar_son_inversas_en_todas_las_casillas():
    """Para las 64 casillas, separar(unir(c, f)) == (c, f) y viceversa."""
    for columna, fila in iterar_casillas():
        token = unir_casilla(columna, fila)
        assert separar_casilla(token) == (columna, fila)
        assert unir_casilla(*separar_casilla(token)) == token


@pytest.mark.parametrize("columna", ["z", "A", "", "aa"])
def test_unir_casilla_lanza_valueerror_por_columna_invalida(columna):
    """unir_casilla lanza ValueError en español ante columna inválida."""
    with pytest.raises(ValueError, match="Columna no válida"):
        unir_casilla(columna, 4)


@pytest.mark.parametrize("fila", [0, 9, -1])
def test_unir_casilla_lanza_valueerror_por_fila_invalida(fila):
    """unir_casilla lanza ValueError en español ante fila inválida."""
    with pytest.raises(ValueError, match="Fila no válida"):
        unir_casilla("e", fila)


@pytest.mark.parametrize("casilla", ["i9", "e0", "e", "ee", ""])
def test_separar_casilla_lanza_valueerror_por_token_invalido(casilla):
    """separar_casilla lanza ValueError en español ante token inválido."""
    with pytest.raises(ValueError, match="Casilla no válida"):
        separar_casilla(casilla)


# ---------------------------------------------------------------------------
# Iteración de casillas
# ---------------------------------------------------------------------------

def test_iterar_casillas_produce_64_casillas_unicas():
    """iterar_casillas recorre exactamente las 64 casillas sin repetir."""
    casillas = list(iterar_casillas())
    assert len(casillas) == 64
    assert len(set(casillas)) == 64


def test_iterar_casillas_token_produce_64_tokens_unicos_y_validos():
    """iterar_casillas_token produce 64 tokens únicos y todos válidos."""
    tokens = list(iterar_casillas_token())
    assert len(tokens) == 64
    assert len(set(tokens)) == 64
    assert all(es_casilla_valida(token) for token in tokens)
